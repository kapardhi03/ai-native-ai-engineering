"""
robustness.py — the checks the reported run does not currently make.

`run_policies.py` produces the headline numbers. This file interrogates them. It
reads `results/run.json` and touches no provider, so it is offline, deterministic
and reproducible from the committed artifact alone.

Every check here exists because a claim in the paper is asserted without a test.
The check names map onto those claims:

  resolution      "missed the escalation threshold by 0.031" — is a third decimal
                  measurable, given what the elicitation actually emits?
  binding         3/13 is presented as *the* threshold. Which action pair does the
                  decision rule actually compare?
  cost_sweep      "their ORDERING is the load-bearing part, not the exact
                  magnitudes" — perturb magnitudes, hold ordering, see what moves.
  threshold_rule  "the asymmetry does most of the work" — against a uniform matrix
                  that turns out to be a 0.5 threshold. What does a TUNED scalar
                  threshold do? This is the rival the claim needs to beat.
  ece_interval    ECE 0.142 is reported to three decimals with no interval, and is
                  the lowest of the three values in run.md. Bootstrap it.
  recalibration   "should recover most of the misses" — a prediction, never run.
                  Run it, at its in-sample ceiling, and count what survives.
  action_census   Which of the five actions are ever selected, and did the hard
                  constraint ever change an outcome? (build-log F5 and F6.)
  constraint_leak `no_direct_answer` is treated as an observable. It is also
                  perfectly correlated with the hidden state on the cases that
                  carry it, which flatters one baseline and hides a deployment
                  risk. Simulate a detector that is wrong sometimes.
  reweight        The case mix is not the author's own stated prior. Reweight to
                  it and see which conclusions are properties of the policy and
                  which are properties of the sample.

Usage
    python experiments/robustness.py                    # human-readable report
    python experiments/robustness.py --json out.json    # machine-readable too
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.belief import Belief                                    # noqa: E402
from src.costs import (ACTIONS, COST, READINESS_LABELS,           # noqa: E402
                       UNIFORM_COST, State, choose_action, expected_cost,
                       feasible_actions, tie_break_order)

RUN_JSON = ROOT / "results" / "run.json"

ESCALATIONS = frozenset({"escalate_notify", "escalate_pause"})

#: The author's live prior, verbatim from decisions/probability-decision-record.md
#: section 1: "out of 100 fresh leads I'd put 2 hot, 13 warm, and 85 cold".
#: Labelled there as judgment, not measured frequency. Used here only as a
#: reweighting target, never as an input to any decision.
AUTHOR_PRIOR_READINESS = {"hot": 0.02, "warm": 0.13, "cold": 0.85}

#: Bootstrap resamples for the ECE interval. Fixed seed: this file must give the
#: same answer twice, or it cannot be cited in a paper.
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20260821


# --------------------------------------------------------------------------- #
# Loading and shared scoring
# --------------------------------------------------------------------------- #

def load_rows() -> tuple[list[dict], dict]:
    payload = json.loads(RUN_JSON.read_text())
    if not payload.get("reportable"):
        print("WARNING: run.json is not marked reportable.", file=sys.stderr)
    return payload["rows"], payload


def belief_of(row: dict) -> Belief:
    return Belief.from_dict(row["belief"])


def realised_cost(action: str, row: dict, matrix=COST) -> float:
    """What the action actually cost, priced against the case's TRUE labels.

    Always the practitioner matrix by default, whatever matrix the policy used to
    decide. Scoring a policy under its own ruler proves nothing (run_policies.py
    design point 1), and that applies to every variant scored in this file too.
    """
    labels = row["labels"]
    return matrix[action][(labels["readiness"], bool(labels["needs_human"]))]


def is_miss(action: str, row: dict) -> bool:
    """A miss: a human was genuinely needed and the agent did not fetch one."""
    return bool(row["labels"]["needs_human"]) and action not in ESCALATIONS


def score(actions: list[str], rows: list[dict], weights=None) -> dict:
    """Summary for one action-per-case assignment.

    `weights` lets the same scorer serve the reweighting check; None means every
    case counts once, which is what the paper reports.
    """
    w = [1.0] * len(rows) if weights is None else weights
    total_w = sum(w)

    cost = sum(wi * realised_cost(a, r) for a, wi, r in zip(actions, w, rows))
    misses = sum(wi for a, wi, r in zip(actions, w, rows) if is_miss(a, r))
    escalated = sum(wi for a, wi in zip(actions, w) if a in ESCALATIONS)

    needed = sum(wi for wi, r in zip(w, rows) if r["labels"]["needs_human"])
    tp = sum(wi for a, wi, r in zip(actions, w, rows)
             if a in ESCALATIONS and r["labels"]["needs_human"])

    return {
        "mean_cost": cost / total_w,
        "misses": misses,
        "escalations": escalated,
        "precision": (tp / escalated) if escalated else None,
        "recall": (tp / needed) if needed else None,
    }


# --------------------------------------------------------------------------- #
# resolution — is the third decimal of the threshold measurable?
# --------------------------------------------------------------------------- #

def check_resolution(rows: list[dict]) -> dict:
    """What values does the elicited needs_human marginal actually take?

    The paper reports a case that "missed the escalation threshold by 0.031". That
    number has resolution only if the elicitation can land inside the interval it
    is measured across. If the emitted values are coarse, then a whole INTERVAL of
    thresholds produces byte-identical decisions, and quoting one point inside it
    to three decimals is precision the instrument does not have.
    """
    values = Counter(round(belief_of(r).needs_human, 6) for r in rows)
    distinct = sorted(values)

    threshold = 3 / 13
    below = max((v for v in distinct if v <= threshold), default=None)
    above = min((v for v in distinct if v > threshold), default=None)

    # Any threshold strictly inside (below, above] orders every case's needs_human
    # marginal identically, so it cannot change a single decision.
    return {
        "n_distinct_values": len(distinct),
        "values": {f"{v:.2f}": values[v] for v in distinct},
        "all_one_decimal": all(abs(v * 10 - round(v * 10)) < 1e-9 for v in distinct),
        "threshold": threshold,
        "nearest_below": below,
        "nearest_above": above,
        "equivalent_threshold_interval": [below, above],
        "cases_in_open_interval": sum(
            1 for v in distinct if below is not None and below < v < (above or 1.0)),
    }


# --------------------------------------------------------------------------- #
# binding — which comparison does the rule actually make?
# --------------------------------------------------------------------------- #

def check_binding(rows: list[dict]) -> dict:
    """Census of (chosen, runner-up) pairs under the cost-aware policy.

    3/13 is the answer-vs-notify crossover. It governs behaviour only in cases
    where those two are the top two feasible actions. Everywhere else a different
    comparison binds, and for `hold` the threshold is readiness-dependent because
    the hold row is not flat across readiness.
    """
    pairs = Counter()
    for row in rows:
        belief = belief_of(row)
        available = feasible_actions(row["constraints"])
        costs = {a: expected_cost(a, belief) for a in available}
        ranked = sorted(available, key=lambda a: (costs[a], ACTIONS.index(a)))
        if len(ranked) > 1:
            pairs[(ranked[0], ranked[1])] += 1

    answer_notify = sum(n for (a, b), n in pairs.items()
                        if {a, b} == {"answer", "escalate_notify"})
    return {
        "runner_up_pairs": {f"{a} vs {b}": n for (a, b), n in pairs.most_common()},
        "cases_where_3_13_binds": answer_notify,
        "n": len(rows),
    }


def _notify_vs_hold_crossover(readiness_dist: dict) -> float | None:
    """The needs_human value at which notify overtakes hold, for one readiness
    distribution.

    Both rows are linear in p once readiness is marginalised out, so this is one
    division. It is a function of the readiness distribution, not a constant,
    because the hold row is not flat across readiness — which is exactly why the
    paper's single 3/13 cannot be the operative threshold when hold competes.
    """
    def line(action):
        f = sum(readiness_dist[r] * COST[action][(r, False)] for r in READINESS_LABELS)
        t = sum(readiness_dist[r] * COST[action][(r, True)] for r in READINESS_LABELS)
        return f, t - f                      # value at p=0, slope in p

    n0, ns = line("escalate_notify")
    h0, hs = line("hold")
    denom = ns - hs
    return None if denom == 0 else (h0 - n0) / denom


def check_hold_threshold(rows: list[dict]) -> dict:
    """The paper states the hold-competing crossover falls in [0.018, 0.500] on the
    73 cases where it lands in [0, 1] at all. Check that against both readings.

    Pure readiness states give one set of crossovers; the actual per-case readiness
    distributions give another. Only the second is a claim about this experiment,
    so both are reported rather than assuming which the paper meant.
    """
    pure = {}
    for r in READINESS_LABELS:
        pure[r] = _notify_vs_hold_crossover({k: (1.0 if k == r else 0.0)
                                             for k in READINESS_LABELS})

    per_case = [_notify_vs_hold_crossover(belief_of(row).readiness) for row in rows]
    finite = [v for v in per_case if v is not None]
    # Only cases where hold is genuinely in contention tell us anything about the
    # operative threshold; a crossover below 0 means notify already beats hold.
    in_range = [v for v in finite if 0.0 <= v <= 1.0]

    return {
        "pure_readiness_states": pure,
        "per_case_min": min(finite) if finite else None,
        "per_case_max": max(finite) if finite else None,
        "per_case_in_unit_range": {
            "n": len(in_range),
            "min": min(in_range) if in_range else None,
            "max": max(in_range) if in_range else None,
        },
        "paper_claimed_in_unit_range": [0.018, 0.500],
    }


# --------------------------------------------------------------------------- #
# cost_sweep — is it really the ordering and not the magnitudes?
# --------------------------------------------------------------------------- #

def _decide_all(rows: list[dict], matrix) -> list[str]:
    return [choose_action(belief_of(r), r["constraints"], matrix).action for r in rows]


def _perturbed(cell_action: str, needs_human: bool, value: float):
    """COST with one cell replaced. Everything else, including the ordering the
    paper says is load-bearing, is untouched."""
    matrix = {a: dict(row) for a, row in COST.items()}
    for r in READINESS_LABELS:
        matrix[cell_action][(r, needs_human)] = value
    return matrix


def check_cost_sweep(rows: list[dict]) -> dict:
    """Perturb one cell at a time, preserving the cost ORDERING, and watch the
    error counts. If the paper's claim holds, nothing much should move."""
    out = {}

    # The false-assertion cost: answer when a human was needed. Nominally 10.
    out["answer_when_human_needed"] = {}
    for v in (4, 5, 6, 7, 8, 10, 12, 15, 20, 30):
        acts = _decide_all(rows, _perturbed("answer", True, v))
        out["answer_when_human_needed"][v] = score(acts, rows)

    # The needless-notify cost: escalate when no human was needed. Nominally 3.
    out["notify_when_not_needed"] = {}
    for v in (1, 2, 2.5, 3, 3.5, 4, 5, 6):
        acts = _decide_all(rows, _perturbed("escalate_notify", False, v))
        out["notify_when_not_needed"][v] = score(acts, rows)

    return out


# --------------------------------------------------------------------------- #
# threshold_rule — the rival baseline the paper omits
# --------------------------------------------------------------------------- #

def _threshold_action(row: dict, t: float) -> str:
    """One free parameter: escalate iff the needs_human marginal clears t.

    No cost matrix, no readiness, no factored state. Falls back to notify when a
    constraint forbids answering, which is what a system with the rule and no
    belief would do — same fallback run_policies.py gives the degenerate policies.
    """
    wanted = "escalate_notify" if belief_of(row).needs_human >= t else "answer"
    available = feasible_actions(row["constraints"])
    return wanted if wanted in available else "escalate_notify"


def check_threshold_rule(rows: list[dict]) -> dict:
    """Tune a single scalar threshold on dev, report it on test and on all.

    Two tuning objectives, because they disagree and the disagreement is itself a
    finding: mean cost is measured by the very matrix under scrutiny, so tuning on
    cost cannot be treated as independent evidence for the matrix.

    Minimising misses alone is NOT one of them — it degenerates to t=0, escalate
    everything, zero misses. The honest comparison is at matched human load: find
    the thresholds bracketing the cost-aware policy's escalation count and compare
    misses there. Belief quantization means no threshold hits the count exactly,
    and that gap is reported rather than interpolated away.
    """
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]
    grid = [i / 100 for i in range(0, 101, 5)]

    sweep = {}
    for t in grid:
        sweep[t] = {
            "dev": score([_threshold_action(r, t) for r in dev], dev),
            "test": score([_threshold_action(r, t) for r in test], test),
            "all": score([_threshold_action(r, t) for r in rows], rows),
        }

    best_by_cost = min(grid, key=lambda t: (sweep[t]["dev"]["mean_cost"], t))

    # Matched-load bracket against the reported cost-aware policy.
    ca_actions = [r["decisions"]["cost_aware"]["action"] for r in rows]
    ca = score(ca_actions, rows)
    budget = ca["escalations"]
    at_or_below = [t for t in grid if sweep[t]["all"]["escalations"] <= budget]
    at_or_above = [t for t in grid if sweep[t]["all"]["escalations"] >= budget]
    # Tightest bracket: the fewest escalations still >= budget, and the most <= it.
    lower = max(at_or_below, key=lambda t: sweep[t]["all"]["escalations"], default=None)
    upper = min(at_or_above, key=lambda t: sweep[t]["all"]["escalations"], default=None)

    # Is the uniform-cost baseline just a 0.5 threshold wearing a matrix?
    uniform_acts = _decide_all(rows, UNIFORM_COST)
    half_acts = [_threshold_action(r, 0.5) for r in rows]
    agree = sum(1 for a, b in zip(uniform_acts, half_acts) if a == b)

    return {
        "sweep": {f"{t:.2f}": v for t, v in sweep.items()},
        "tuned_on_dev_by_cost": {"t": best_by_cost, **sweep[best_by_cost]},
        "cost_aware_reference": ca,
        "matched_load": {
            "escalation_budget": budget,
            "exact_match_possible": any(
                sweep[t]["all"]["escalations"] == budget for t in grid),
            "nearest_below": None if lower is None else {
                "t": lower, **sweep[lower]["all"]},
            "nearest_above": None if upper is None else {
                "t": upper, **sweep[upper]["all"]},
        },
        "uniform_baseline_vs_half_threshold": {
            "cases_agreeing": agree, "n": len(rows),
        },
    }


# --------------------------------------------------------------------------- #
# ece_interval — how much does 0.142 actually pin down?
# --------------------------------------------------------------------------- #

def _ece(pairs, bins: int = 10) -> float | None:
    """Identical binning to run_policies.expected_calibration_error, so the point
    estimate here reproduces the reported one exactly."""
    if not pairs:
        return None
    buckets = defaultdict(list)
    for p, o in pairs:
        buckets[min(int(p * bins), bins - 1)].append((p, o))
    total, ece = len(pairs), 0.0
    for members in buckets.values():
        mean_p = sum(p for p, _ in members) / len(members)
        obs = sum(1 for _, o in members if o) / len(members)
        ece += (len(members) / total) * abs(mean_p - obs)
    return ece


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson interval. Chosen over normal-approximation because several bins here
    have an observed frequency at or near 0, where the normal interval is useless."""
    if n == 0:
        return (0.0, 1.0)
    p, z2 = k / n, z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z / denom) * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5)
    return (max(0.0, centre - half), min(1.0, centre + half))


def check_ece_interval(rows: list[dict]) -> dict:
    """Bootstrap the ECE, split it by half, and put an interval on every bin.

    Binned ECE on 100 cases with a coarse predictor is a noisy statistic that is
    biased downward: empty and near-empty bins contribute nothing, and the bias
    shows up as a bootstrap median above the point estimate.
    """
    def pairs_for(subset):
        return [(belief_of(r).needs_human, bool(r["labels"]["needs_human"]))
                for r in subset]

    all_pairs = pairs_for(rows)
    point = _ece(all_pairs)

    rng = random.Random(BOOTSTRAP_SEED)
    n = len(all_pairs)
    draws = sorted(_ece([all_pairs[rng.randrange(n)] for _ in range(n)])
                   for _ in range(BOOTSTRAP_N))
    lo, hi = draws[int(0.025 * BOOTSTRAP_N)], draws[int(0.975 * BOOTSTRAP_N)]

    # Per-bin intervals. A bin whose interval covers its own predicted value is
    # not evidence of miscalibration in either direction.
    buckets = defaultdict(list)
    for p, o in all_pairs:
        buckets[min(int(p * 10), 9)].append((p, o))
    per_bin = []
    for idx in sorted(buckets):
        members = buckets[idx]
        k, nb = sum(1 for _, o in members if o), len(members)
        mean_p = sum(p for p, _ in members) / nb
        w_lo, w_hi = _wilson(k, nb)
        per_bin.append({
            "bin": f"{idx / 10:.1f}-{(idx + 1) / 10:.1f}",
            "n": nb, "mean_predicted": round(mean_p, 4),
            "observed": round(k / nb, 4), "gap": round(mean_p - k / nb, 4),
            "observed_ci95": [round(w_lo, 4), round(w_hi, 4)],
            "ci_covers_predicted": w_lo <= mean_p <= w_hi,
            "contains_threshold": idx / 10 <= 3 / 13 < (idx + 1) / 10,
        })

    return {
        "point_estimate_all": round(point, 4),
        "bootstrap_ci95": [round(lo, 4), round(hi, 4)],
        "bootstrap_median": round(draws[BOOTSTRAP_N // 2], 4),
        "dev": round(_ece(pairs_for([r for r in rows if r["split"] == "dev"])), 4),
        "test": round(_ece(pairs_for([r for r in rows if r["split"] == "test"])), 4),
        "per_bin": per_bin,
    }


# --------------------------------------------------------------------------- #
# recalibration — run the paper's own proposed fix
# --------------------------------------------------------------------------- #

def check_recalibration(rows: list[dict]) -> dict:
    """Histogram-bin recalibration of the needs_human marginal, in sample.

    This is deliberately the most generous possible version of the fix: it uses
    the TEST labels to build the mapping, so it is an upper bound on what any
    honest held-out recalibration could achieve. If the paper's "should recover
    most of the misses" fails here, it fails everywhere.
    """
    buckets = defaultdict(list)
    for row in rows:
        buckets[min(int(belief_of(row).needs_human * 10), 9)].append(row)
    mapping = {
        idx: sum(1 for r in members if r["labels"]["needs_human"]) / len(members)
        for idx, members in buckets.items()
    }

    before_actions, after_actions = [], []
    for row in rows:
        belief = belief_of(row)
        before_actions.append(choose_action(belief, row["constraints"]).action)
        recal = Belief(readiness=belief.readiness,
                       needs_human=mapping[min(int(belief.needs_human * 10), 9)])
        after_actions.append(choose_action(recal, row["constraints"]).action)

    # Where does the residual sit? If it concentrates in the bin that CONTAINS the
    # threshold, the floor is not "one case far from the threshold" — it is
    # structural, because recalibration cannot move a bin across a threshold that
    # sits inside it. Recalibration can also CREATE misses, by moving a bin down;
    # those are counted separately because a net figure would hide them.
    survivors, created, fixed = defaultdict(int), [], 0
    for row, before, after in zip(rows, before_actions, after_actions):
        was, now = is_miss(before, row), is_miss(after, row)
        if was and now:
            survivors[f"b_h={belief_of(row).needs_human:.2f}"] += 1
        elif was and not now:
            fixed += 1
        elif now and not was:
            created.append({"case_id": row["case_id"],
                            "b_h": belief_of(row).needs_human,
                            "before": before, "after": after})

    return {
        "mapping": {f"{i / 10:.1f}-{(i + 1) / 10:.1f}": round(v, 4)
                    for i, v in sorted(mapping.items())},
        "before": score(before_actions, rows),
        "after": score(after_actions, rows),
        "misses_fixed": fixed,
        "misses_created": created,
        "surviving_misses_by_original_belief": dict(sorted(survivors.items())),
        "n_surviving": sum(survivors.values()),
    }


# --------------------------------------------------------------------------- #
# action_census — build-log F5 and F6, as numbers
# --------------------------------------------------------------------------- #

def check_action_census(rows: list[dict], payload: dict) -> dict:
    """Which actions are ever selected, and did the constraint ever bind?

    The paper's "Note on the action set" defends splitting escalate into two
    actions. Table 2's caption reports zero hard-constraint violations. Both
    statements read very differently if the second escalate action is never
    chosen and the constraint never changed an outcome.
    """
    out = {}
    for policy in payload["rows"][0]["decisions"]:
        counts = Counter(r["decisions"][policy]["action"] for r in rows)
        bound = sum(1 for r in rows if r["decisions"][policy]["constraint_bound"])
        out[policy] = {
            "action_counts": {a: counts.get(a, 0) for a in ACTIONS},
            "never_selected": [a for a in ACTIONS if counts.get(a, 0) == 0],
            "constraint_changed_outcome": bound,
        }
    out["_cases_carrying_a_constraint"] = sum(1 for r in rows if r["constraints"])
    return out


# --------------------------------------------------------------------------- #
# constraint_leak — the observable that is also the answer key
# --------------------------------------------------------------------------- #

def check_constraint_leak(rows: list[dict]) -> dict:
    """Is `no_direct_answer` independent of the hidden state, as the design assumes?

    If every case carrying the flag also has needs_human=True, the flag is an
    oracle on exactly the subset where a miss is most expensive. Two consequences:
    a baseline that escalates only when forbidden to answer scores as perfectly
    precise for free, and a real detector's false negatives land entirely on the
    highest-harm cases. Neither is visible in the reported run.
    """
    flagged = [r for r in rows if r["constraints"]]
    n_true = sum(1 for r in flagged if r["labels"]["needs_human"])

    # Detector error simulation. Sweep a false-negative rate over the flagged
    # cases: with probability fn the flag is missed, so `answer` becomes feasible.
    rng = random.Random(BOOTSTRAP_SEED)
    sim = {}
    for fn in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5):
        trials = []
        for _ in range(400):
            actions = []
            for row in rows:
                cons = tuple(c for c in row["constraints"] if rng.random() >= fn)
                actions.append(choose_action(belief_of(row), cons).action)
            trials.append(score(actions, rows))
        sim[fn] = {
            "mean_cost": round(sum(t["mean_cost"] for t in trials) / len(trials), 4),
            "misses": round(sum(t["misses"] for t in trials) / len(trials), 2),
        }

    return {
        "n_flagged": len(flagged),
        "n_flagged_with_needs_human_true": n_true,
        "flag_is_perfect_oracle": len(flagged) > 0 and n_true == len(flagged),
        "always_answer_escalations": sum(
            1 for r in rows if r["decisions"]["always_answer"]["action"] in ESCALATIONS),
        "detector_false_negative_sweep": sim,
    }


# --------------------------------------------------------------------------- #
# reweight — is the result a property of the policy or of the sample?
# --------------------------------------------------------------------------- #

def check_reweight(rows: list[dict], payload: dict) -> dict:
    """Importance-reweight every policy to the author's own stated readiness prior.

    The paper's L1 flags the inflated needs_human base rate and says nothing about
    readiness. The sample is roughly balanced across readiness; the author's stated
    prior is 85% cold. That is a large distribution shift, and any headline number
    that moves under it is a property of the case mix, not of the policy.
    """
    empirical = Counter(r["labels"]["readiness"] for r in rows)
    weights_by_label = {
        r: (AUTHOR_PRIOR_READINESS[r] * len(rows) / empirical[r]) if empirical[r] else 0.0
        for r in READINESS_LABELS
    }
    weights = [weights_by_label[r["labels"]["readiness"]] for r in rows]

    out = {"empirical_readiness": dict(empirical),
           "author_prior": AUTHOR_PRIOR_READINESS,
           "weights": {k: round(v, 4) for k, v in weights_by_label.items()},
           "policies": {}}
    for policy in rows[0]["decisions"]:
        actions = [r["decisions"][policy]["action"] for r in rows]
        out["policies"][policy] = {
            "as_reported": score(actions, rows),
            "reweighted": score(actions, rows, weights),
        }
    return out


# --------------------------------------------------------------------------- #
# fixes — do the two code-level defects matter, and does the old path still hold?
# --------------------------------------------------------------------------- #

def check_fixes(rows: list[dict]) -> dict:
    """Measure the tie-break and clipping fixes, and verify reproducibility.

    The first assertion here is the important one: recomputing every decision with
    `legacy_tie_break=True` must return exactly what results/run.json recorded. If
    it does not, the committed artifact and the code have drifted and nothing else
    in this file can be trusted.
    """
    legacy, fixed, clipped, both = [], [], [], []
    for row in rows:
        belief = belief_of(row)
        cons = row["constraints"]
        legacy.append(choose_action(belief, cons, legacy_tie_break=True).action)
        fixed.append(choose_action(belief, cons).action)
        clipped.append(choose_action(belief.clipped(), cons,
                                     legacy_tie_break=True).action)
        both.append(choose_action(belief.clipped(), cons).action)

    recorded = [r["decisions"]["cost_aware"]["action"] for r in rows]
    mismatches = [(r["case_id"], rec, leg)
                  for r, rec, leg in zip(rows, recorded, legacy) if rec != leg]

    changed = [{"case_id": r["case_id"], "b_h": belief_of(r).needs_human,
                "from": a, "to": b, "margin": r["decisions"]["cost_aware"]["margin"]}
               for r, a, b in zip(rows, legacy, fixed) if a != b]

    return {
        "legacy_reproduces_run_json": not mismatches,
        "mismatches": mismatches,
        "tie_break_order": list(tie_break_order()),
        "decisions_changed_by_tie_break": changed,
        "scores": {
            "as_reported (legacy tie-break)": score(legacy, rows),
            "safe tie-break": score(fixed, rows),
            "legacy + clipped belief": score(clipped, rows),
            "safe tie-break + clipped belief": score(both, rows),
        },
    }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

def _f(v, nd=3):
    if v is None:
        return "--"
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="also write the raw findings here")
    args = ap.parse_args()

    rows, payload = load_rows()
    findings = {
        "n_cases": len(rows),
        "resolution": check_resolution(rows),
        "binding": check_binding(rows),
        "hold_threshold": check_hold_threshold(rows),
        "cost_sweep": check_cost_sweep(rows),
        "threshold_rule": check_threshold_rule(rows),
        "ece_interval": check_ece_interval(rows),
        "recalibration": check_recalibration(rows),
        "action_census": check_action_census(rows, payload),
        "constraint_leak": check_constraint_leak(rows),
        "reweight": check_reweight(rows, payload),
        "fixes": check_fixes(rows),
    }

    r = findings["resolution"]
    print(f"\n=== 1. Belief resolution ({findings['n_cases']} cases) ===")
    print(f"distinct needs_human values: {r['n_distinct_values']}  "
          f"all at one decimal: {r['all_one_decimal']}")
    print(f"  {r['values']}")
    print(f"threshold 3/13 = {r['threshold']:.4f} sits in the gap "
          f"({r['nearest_below']}, {r['nearest_above']}]; "
          f"{r['cases_in_open_interval']} cases lie strictly inside it")
    print("  => every threshold in that interval produces identical decisions")

    b = findings["binding"]
    print("\n=== 2. Which comparison actually binds ===")
    for pair, n in b["runner_up_pairs"].items():
        print(f"  {pair:<34} {n}")
    print(f"cases where the 3/13 (answer vs notify) comparison binds: "
          f"{b['cases_where_3_13_binds']} / {b['n']}")

    h = findings["hold_threshold"]
    print("\n=== 2b. Where notify actually overtakes hold ===")
    print("  pure readiness states: "
          + ", ".join(f"{k} {v:.3f}" for k, v in h["pure_readiness_states"].items()
                      if v is not None))
    u = h["per_case_in_unit_range"]
    print(f"  over the 100 real readiness distributions: "
          f"[{h['per_case_min']:.3f}, {h['per_case_max']:.3f}]; "
          f"{u['n']} of 100 fall inside [0,1] "
          f"(range [{u['min']:.3f}, {u['max']:.3f}])")
    print(f"  paper claims the in-range span is {h['paper_claimed_in_unit_range']}")

    print("\n=== 3. Cost-magnitude sensitivity (ordering preserved throughout) ===")
    for cell, sweep in findings["cost_sweep"].items():
        print(f"  {cell}:")
        print(f"    {'value':>7} {'mean cost':>10} {'misses':>7} {'escalations':>12}")
        for v, s in sweep.items():
            print(f"    {v:>7} {s['mean_cost']:>10.3f} {s['misses']:>7.0f} "
                  f"{s['escalations']:>12.0f}")

    t = findings["threshold_rule"]
    print("\n=== 4. Tuned scalar threshold (the omitted baseline) ===")
    print(f"uniform_baseline agrees with a plain 0.5 threshold on "
          f"{t['uniform_baseline_vs_half_threshold']['cases_agreeing']}"
          f"/{t['uniform_baseline_vs_half_threshold']['n']} cases")
    d = t["tuned_on_dev_by_cost"]
    print(f"  tuned on dev by mean cost -> t={d['t']:.2f}  "
          f"all: cost {d['all']['mean_cost']:.3f}, "
          f"misses {d['all']['misses']:.0f}, "
          f"escalations {d['all']['escalations']:.0f}")
    print("    (cost alone cannot select a threshold here: correct escalation is "
          "priced at 0,\n     so the objective is minimised by escalating "
          "everything)")
    m = t["matched_load"]
    ref = t["cost_aware_reference"]
    print(f"  matched human load. cost_aware: {ref['escalations']:.0f} escalations, "
          f"{ref['misses']:.0f} misses")
    print(f"    a threshold hitting {m['escalation_budget']:.0f} exactly exists: "
          f"{m['exact_match_possible']}  (quantized beliefs)")
    for side in ("nearest_below", "nearest_above"):
        s = m[side]
        if s:
            print(f"    {side:<14} t={s['t']:.2f}  escalations {s['escalations']:>3.0f}  "
                  f"misses {s['misses']:>3.0f}  cost {s['mean_cost']:.3f}")
    print(f"    {'t':>5} {'cost':>7} {'misses':>7} {'esc':>5}")
    for tv in ("0.10", "0.20", "0.25", "0.30", "0.35", "0.50"):
        s = t["sweep"][tv]["all"]
        print(f"    {tv:>5} {s['mean_cost']:>7.3f} {s['misses']:>7.0f} "
              f"{s['escalations']:>5.0f}")

    e = findings["ece_interval"]
    print("\n=== 5. ECE with an interval ===")
    print(f"point (all) {e['point_estimate_all']}   "
          f"bootstrap 95% CI {e['bootstrap_ci95']}   median {e['bootstrap_median']}")
    print(f"dev {e['dev']}   test {e['test']}   "
          f"=> the pooled figure is below both halves")
    print(f"  {'bin':>9} {'n':>4} {'pred':>6} {'obs':>6} {'gap':>7} "
          f"{'obs 95% CI':>16}  covers pred?")
    for row_ in e["per_bin"]:
        mark = "  <-- contains 3/13" if row_["contains_threshold"] else ""
        print(f"  {row_['bin']:>9} {row_['n']:>4} {row_['mean_predicted']:>6.3f} "
              f"{row_['observed']:>6.3f} {row_['gap']:>+7.3f} "
              f"[{row_['observed_ci95'][0]:.3f}, {row_['observed_ci95'][1]:.3f}]"
              f"   {'yes' if row_['ci_covers_predicted'] else 'no':>3}{mark}")

    c = findings["recalibration"]
    print("\n=== 6. The paper's proposed fix, run (in-sample ceiling) ===")
    for label in ("before", "after"):
        s = c[label]
        print(f"  {label:>7}: cost {s['mean_cost']:.3f}  misses {s['misses']:.0f}  "
              f"escalations {s['escalations']:.0f}  "
              f"precision {_f(s['precision'])}  recall {_f(s['recall'])}")
    print(f"  misses fixed {c['misses_fixed']}, still missed {c['n_surviving']} "
          f"{c['surviving_misses_by_original_belief']}, "
          f"newly created {len(c['misses_created'])}")
    for nm in c["misses_created"]:
        print(f"    created: {nm['case_id']} b_h={nm['b_h']:.2f} "
              f"{nm['before']} -> {nm['after']}")

    a = findings["action_census"]
    print("\n=== 7. Action census and constraint binds ===")
    print(f"cases carrying a constraint: {a['_cases_carrying_a_constraint']}")
    for policy, d in a.items():
        if policy.startswith("_"):
            continue
        print(f"  {policy:<17} {d['action_counts']}")
        print(f"    never selected: {d['never_selected'] or 'none'};  "
              f"constraint changed the outcome: {d['constraint_changed_outcome']}")

    k = findings["constraint_leak"]
    print("\n=== 8. Is the constraint flag independent of the hidden state? ===")
    print(f"flagged cases: {k['n_flagged']}; of those, needs_human=True: "
          f"{k['n_flagged_with_needs_human_true']}  "
          f"=> perfect oracle: {k['flag_is_perfect_oracle']}")
    print(f"always_answer escalates on {k['always_answer_escalations']} cases "
          f"(exactly the flagged ones), which is where its precision comes from")
    print(f"    {'detector FN rate':>17} {'mean cost':>10} {'misses':>8}")
    for fn, s in k["detector_false_negative_sweep"].items():
        print(f"    {fn:>17.2f} {s['mean_cost']:>10.3f} {s['misses']:>8.2f}")

    w = findings["reweight"]
    print("\n=== 9. Reweighted to the author's own stated prior ===")
    print(f"empirical readiness {w['empirical_readiness']} vs prior "
          f"{w['author_prior']}; weights {w['weights']}")
    print(f"  {'policy':<18} {'as reported':>12} {'reweighted':>12}")
    for policy, d in w["policies"].items():
        print(f"  {policy:<18} {d['as_reported']['mean_cost']:>12.3f} "
              f"{d['reweighted']['mean_cost']:>12.3f}")

    fx = findings["fixes"]
    print("\n=== 10. The two code-level fixes ===")
    print(f"legacy path reproduces results/run.json exactly: "
          f"{fx['legacy_reproduces_run_json']}")
    if fx["mismatches"]:
        print(f"  MISMATCHES: {fx['mismatches']}")
    print(f"safest-first tie-break order (by worst-case cost): "
          f"{' < '.join(fx['tie_break_order'])}")
    print(f"decisions the tie-break changes: {len(fx['decisions_changed_by_tie_break'])}")
    for d in fx["decisions_changed_by_tie_break"]:
        print(f"  {d['case_id']}  b_h={d['b_h']:.2f}  margin={d['margin']}  "
              f"{d['from']} -> {d['to']}")
    print(f"  {'variant':<34} {'cost':>7} {'misses':>7} {'esc':>5}")
    for name, s in fx["scores"].items():
        print(f"  {name:<34} {s['mean_cost']:>7.3f} {s['misses']:>7.0f} "
              f"{s['escalations']:>5.0f}")

    if args.json:
        args.json.write_text(json.dumps(findings, indent=2, default=str))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
