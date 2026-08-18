"""
costs.py — the cost matrix, the hard constraints, and the decision rule.

Three things live here, deliberately separated.

1. COST: what each (action, hidden state) pair costs. Numbers set by the
   practitioner, one reason each, recorded in build-log.md rows 33-38.

2. CONSTRAINTS: actions that are removed from consideration entirely. A
   constraint is NOT a large number. `answer` on a request for land papers is not
   expensive, it is unavailable — no belief, however confident, can select it.
   Pricing it instead would mean a sufficiently strong belief could buy its way
   past the rule, which is exactly what a hard constraint must forbid.

3. The myopic decision rule: pick the feasible action with the lowest expected
   cost under the current belief. One step, no planning over future beliefs.

On the two-part belief. readiness and needs_human are independent by design
(locked decision 0a), so the probability of a joint state factorises:

    P(readiness=r, needs_human=h) = P(r) x P(h)

That factorisation is the whole reason the belief is kept as two separate
judgments. A single collapsed score could not express "hot AND needs a human",
which is the case the cost matrix treats most severely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

READINESS_LABELS = ("hot", "warm", "cold")

#: Five actions (build decision 25, superseding the original four). escalate
#: splits into notify — a human is told, the conversation continues — and pause —
#: the agent stops and hands over. They carry different costs.
ACTIONS = ("answer", "ask", "hold", "escalate_notify", "escalate_pause")


class CostModelError(ValueError):
    """The cost model was asked something it cannot answer."""


@dataclass(frozen=True)
class State:
    """A hidden state: buying readiness, and whether a human is genuinely needed."""

    readiness: str
    needs_human: bool

    def __post_init__(self) -> None:
        if self.readiness not in READINESS_LABELS:
            raise CostModelError(
                f"unknown readiness {self.readiness!r}; "
                f"expected one of {READINESS_LABELS}")


#: The 5 x 6 matrix. Rows are actions, columns are states.
#:
#: Reading the interesting column, (hot, needs_human=True) — a lead ready to buy
#: who also needs a person:
#:   answer 10  a false assertion is a false assertion regardless of how ready
#:              the buyer is; no hotness premium
#:   hold    8  the two harms OVERLAP rather than stack. Summing hold-a-hot-lead
#:              (6) with the missed handoff (10) would give 16 and make holding
#:              worse than lying, which would break the framing that puts false
#:              assertion at the top. 8 keeps both orderings: worse than holding
#:              a merely-hot lead, still below a false assertion.
#:   ask     4  defers a needed handoff, but keeps the lead alive
#:   pause   2  correct, plus a premium for making a hot lead wait
#:   notify  0  correct
COST: dict[str, dict[tuple[str, bool], float]] = {
    "answer": {
        ("hot", False): 0, ("warm", False): 0, ("cold", False): 0,
        ("hot", True): 10, ("warm", True): 10, ("cold", True): 10,
    },
    "ask": {
        ("hot", False): 2, ("warm", False): 2, ("cold", False): 2,
        ("hot", True): 4, ("warm", True): 4, ("cold", True): 4,
    },
    "hold": {
        # Holding a cold lead or a blast is the right move, hence 0.
        ("hot", False): 6, ("warm", False): 1, ("cold", False): 0,
        ("hot", True): 8, ("warm", True): 4, ("cold", True): 3,
    },
    "escalate_notify": {
        ("hot", False): 3, ("warm", False): 3, ("cold", False): 3,
        ("hot", True): 0, ("warm", True): 0, ("cold", True): 0,
    },
    "escalate_pause": {
        # A needless pause on a hot lead is at least as bad as holding one: it
        # stops the conversation AND loses the lead.
        ("hot", False): 6, ("warm", False): 5, ("cold", False): 5,
        ("hot", True): 2, ("warm", True): 1, ("cold", True): 1,
    },
}

#: The baseline (locked decision 0e): same decision rule, same notion of which
#: action is correct in each state, but every mistake costs the same. Derived
#: from COST rather than written by hand, so the ONLY difference between the two
#: policies is the magnitude of the asymmetry — never which action counts as
#: right. That is what isolates "does pricing errors differently change the
#: decision" from "did someone define correctness differently".
UNIFORM_COST: dict[str, dict[tuple[str, bool], float]] = {
    action: {state: (0.0 if cost == 0 else 1.0) for state, cost in row.items()}
    for action, row in COST.items()
}

#: Hard constraints. A constraint names actions that are unavailable, full stop.
#: Deliberately NOT expressed as a cost — see the module docstring.
CONSTRAINT_FORBIDS: dict[str, frozenset[str]] = {
    "no_direct_answer": frozenset({"answer"}),
}


def feasible_actions(constraints: Iterable[str] = ()) -> tuple[str, ...]:
    """Actions still available once every constraint has been applied.

    Raises if the constraints leave nothing to choose, rather than returning an
    empty set for a caller to trip over later.
    """
    forbidden: set[str] = set()
    for name in constraints:
        if name not in CONSTRAINT_FORBIDS:
            raise CostModelError(
                f"unknown constraint {name!r}; "
                f"known: {', '.join(sorted(CONSTRAINT_FORBIDS))}")
        forbidden |= CONSTRAINT_FORBIDS[name]

    remaining = tuple(a for a in ACTIONS if a not in forbidden)
    if not remaining:
        raise CostModelError(
            f"constraints {list(constraints)} forbid every action; "
            "there is nothing left to choose")
    return remaining


def state_probability(belief, state: State) -> float:
    """P(state) under the two-part belief, using the independence of the parts."""
    p_readiness = belief.readiness[state.readiness]
    p_human = belief.needs_human if state.needs_human else (1.0 - belief.needs_human)
    return p_readiness * p_human


def expected_cost(action: str, belief, matrix: Optional[dict] = None) -> float:
    """Expected cost of one action under the current belief.

    Sums over all six joint states. Feasibility is not considered here — that is
    the decision rule's job, and keeping them apart means an infeasible action's
    expected cost can still be reported for inspection.
    """
    matrix = matrix if matrix is not None else COST
    if action not in matrix:
        raise CostModelError(f"unknown action {action!r}; expected one of {ACTIONS}")

    row = matrix[action]
    return sum(
        state_probability(belief, State(readiness, needs_human)) * row[(readiness, needs_human)]
        for readiness in READINESS_LABELS
        for needs_human in (False, True)
    )


@dataclass(frozen=True)
class Decision:
    """One decision, with everything needed to audit it after the fact."""

    action: str
    expected_costs: dict          # every action, including infeasible ones
    feasible: tuple               # what was actually available
    forbidden: tuple              # what a constraint removed
    constrained: bool             # did a constraint change the outcome?

    @property
    def margin(self) -> float:
        """Gap to the next-best feasible action. Near zero means the belief
        barely decided it, which is where calibration error matters most."""
        ranked = sorted(self.expected_costs[a] for a in self.feasible)
        return (ranked[1] - ranked[0]) if len(ranked) > 1 else float("inf")


def choose_action(belief, constraints: Iterable[str] = (),
                  matrix: Optional[dict] = None) -> Decision:
    """The myopic rule: lowest expected cost among the feasible actions.

    Constraints are applied by REMOVING actions before the comparison, never by
    inflating their cost. A forbidden action is not merely a bad deal that a
    confident enough belief could justify — it is not on the menu.

    Ties break in ACTIONS order, which is deterministic and recorded here rather
    than left to whatever `min` happens to do.
    """
    constraints = tuple(constraints)
    available = feasible_actions(constraints)
    removed = tuple(a for a in ACTIONS if a not in available)

    costs = {a: expected_cost(a, belief, matrix) for a in ACTIONS}
    best = min(available, key=lambda a: (costs[a], ACTIONS.index(a)))

    unconstrained_best = min(ACTIONS, key=lambda a: (costs[a], ACTIONS.index(a)))
    constrained = best != unconstrained_best

    if constrained:
        logger.info(
            "Constraint changed the decision: %s was cheapest (%.3f) but is "
            "forbidden; chose %s (%.3f).",
            unconstrained_best, costs[unconstrained_best], best, costs[best],
        )

    return Decision(action=best, expected_costs=costs, feasible=available,
                    forbidden=removed, constrained=constrained)


def describe_matrix(matrix: Optional[dict] = None) -> str:
    """The matrix as a table. For the paper and for run logs."""
    matrix = matrix if matrix is not None else COST
    states = [(r, h) for h in (False, True) for r in READINESS_LABELS]
    header = "".join(f"{r + ('/human' if h else ''):>13}" for r, h in states)
    lines = [f"{'action':<17}{header}"]
    for action in ACTIONS:
        row = "".join(f"{matrix[action][s]:>13.0f}" for s in states)
        lines.append(f"{action:<17}{row}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("COST\n" + describe_matrix(COST))
    print("\nUNIFORM_COST (baseline)\n" + describe_matrix(UNIFORM_COST))
