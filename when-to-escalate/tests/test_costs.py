"""
The cost matrix, the hard constraint, and the myopic decision rule.

The load-bearing test in this file is
`test_constraint_holds_even_when_the_forbidden_action_is_free`: it proves the
hard constraint is enforced as infeasibility rather than as a large number. If
it were a price, a confident enough belief could buy past it.
"""

from __future__ import annotations

import math

import pytest

READINESS = ("hot", "warm", "cold")


@pytest.fixture
def costs():
    import costs as costs_mod
    return costs_mod


def mk(belief_mod, hot=1/3, warm=1/3, cold=1/3, needs_human=0.0):
    return belief_mod.to_belief(
        {"hot": hot, "warm": warm, "cold": cold, "needs_human": needs_human})


# --------------------------------------------------------------------------- #
# Matrix shape — it must match the table that was approved
# --------------------------------------------------------------------------- #

def test_five_actions(costs):
    assert costs.ACTIONS == ("answer", "ask", "hold", "escalate_notify", "escalate_pause")


def test_every_action_prices_every_state(costs):
    for action in costs.ACTIONS:
        for readiness in READINESS:
            for needs_human in (False, True):
                assert (readiness, needs_human) in costs.COST[action]


def test_matrix_is_thirty_cells(costs):
    assert sum(len(row) for row in costs.COST.values()) == 30


def test_no_negative_costs(costs):
    assert all(c >= 0 for row in costs.COST.values() for c in row.values())


@pytest.mark.parametrize("action,state,expected", [
    ("answer", ("hot", True), 10), ("answer", ("cold", True), 10),
    ("answer", ("hot", False), 0),
    ("hold", ("hot", False), 6), ("hold", ("hot", True), 8),
    ("hold", ("cold", False), 0), ("hold", ("cold", True), 3),
    ("ask", ("warm", False), 2), ("ask", ("warm", True), 4),
    ("escalate_notify", ("warm", False), 3), ("escalate_notify", ("warm", True), 0),
    ("escalate_pause", ("hot", False), 6), ("escalate_pause", ("warm", False), 5),
    ("escalate_pause", ("warm", True), 1), ("escalate_pause", ("hot", True), 2),
])
def test_approved_cells(costs, action, state, expected):
    assert costs.COST[action][state] == expected


# --------------------------------------------------------------------------- #
# The orderings the numbers were chosen to express
# --------------------------------------------------------------------------- #

def test_false_assertion_is_the_maximum(costs):
    """Nothing may exceed it, or 'nearly forbidden' stops being true."""
    worst = max(c for row in costs.COST.values() for c in row.values())
    assert worst == 10 == costs.COST["answer"][("hot", True)]


def test_holding_a_hot_lead_that_needs_a_human_does_not_stack(costs):
    """The additivity ruling: harms overlap, they do not sum. 6 + 10 = 16 would
    make holding worse than lying and break the framing above."""
    overlapped = costs.COST["hold"][("hot", True)]
    assert overlapped == 8
    assert overlapped > costs.COST["hold"][("hot", False)]   # worse than merely hot
    assert overlapped < costs.COST["answer"][("hot", True)]  # still below a lie


def test_no_hotness_premium_on_a_false_answer(costs):
    values = {costs.COST["answer"][(r, True)] for r in READINESS}
    assert values == {10}


def test_error_ranking_matches_the_practitioner_ordering(costs):
    """hold-a-hot-lead > needless pause > needless notify > needless ask."""
    assert (costs.COST["hold"][("hot", False)]
            > costs.COST["escalate_pause"][("warm", False)]
            > costs.COST["escalate_notify"][("warm", False)]
            > costs.COST["ask"][("warm", False)])


def test_correct_actions_are_free_except_pause(costs):
    for r in READINESS:
        assert costs.COST["answer"][(r, False)] == 0
        assert costs.COST["escalate_notify"][(r, True)] == 0
    assert costs.COST["escalate_pause"][("warm", True)] == 1, "residual, not free"


def test_holding_a_cold_no_human_lead_is_free(costs):
    """Holding a blast or a bare emoji is the right move, not a mistake."""
    assert costs.COST["hold"][("cold", False)] == 0


# --------------------------------------------------------------------------- #
# Expected cost — the two-part belief factorises
# --------------------------------------------------------------------------- #

def test_state_probability_factorises(costs, belief):
    b = mk(belief, hot=.6, warm=.3, cold=.1, needs_human=.25)
    p = costs.state_probability(b, costs.State("hot", True))
    assert math.isclose(p, .6 * .25)


def test_state_probabilities_sum_to_one(costs, belief):
    b = mk(belief, hot=.5, warm=.3, cold=.2, needs_human=.4)
    total = sum(costs.state_probability(b, costs.State(r, h))
                for r in READINESS for h in (False, True))
    assert math.isclose(total, 1.0)


def test_certain_belief_gives_the_raw_cell(costs, belief):
    b = mk(belief, hot=1, warm=0, cold=0, needs_human=1.0)
    assert math.isclose(costs.expected_cost("hold", b), 8)
    assert math.isclose(costs.expected_cost("answer", b), 10)


def test_expected_cost_interpolates(costs, belief):
    b = mk(belief, hot=1, warm=0, cold=0, needs_human=0.5)
    assert math.isclose(costs.expected_cost("answer", b), 0.5 * 0 + 0.5 * 10)


def test_unknown_action_is_rejected(costs, belief):
    with pytest.raises(costs.CostModelError, match="unknown action"):
        costs.expected_cost("panic", mk(belief))


def test_unknown_readiness_is_rejected(costs):
    with pytest.raises(costs.CostModelError, match="unknown readiness"):
        costs.State("lukewarm", False)


# --------------------------------------------------------------------------- #
# Constraints — infeasibility, NOT a price
# --------------------------------------------------------------------------- #

def test_constraint_removes_the_action(costs):
    assert "answer" not in costs.feasible_actions(["no_direct_answer"])
    assert len(costs.feasible_actions(["no_direct_answer"])) == 4


def test_no_constraints_leaves_everything(costs):
    assert costs.feasible_actions() == costs.ACTIONS


def test_unknown_constraint_is_rejected(costs):
    with pytest.raises(costs.CostModelError, match="unknown constraint"):
        costs.feasible_actions(["no_being_rude"])


def test_constraint_holds_even_when_the_forbidden_action_is_free(costs, belief, monkeypatch):
    """THE test for decision 0c.

    Make `answer` cost zero in every state — strictly cheaper than everything
    else — and confirm a constrained case still refuses it. A high price could be
    outbid by a confident belief; infeasibility cannot.
    """
    monkeypatch.setitem(costs.COST, "answer", {(r, h): 0.0 for r in READINESS
                                               for h in (False, True)})
    b = mk(belief, hot=1, warm=0, cold=0, needs_human=0.99)

    free = costs.choose_action(b)
    assert free.action == "answer", "sanity: it really is the cheapest"

    constrained = costs.choose_action(b, ["no_direct_answer"])
    assert constrained.action != "answer"
    assert constrained.constrained is True
    assert "answer" in constrained.forbidden


@pytest.mark.parametrize("needs_human", [0.0, 0.01, 0.5, 0.99, 1.0])
def test_no_belief_can_buy_past_the_constraint(costs, belief, needs_human):
    """Sweep the belief: `answer` is unreachable at every confidence level."""
    b = mk(belief, hot=.8, warm=.15, cold=.05, needs_human=needs_human)
    assert costs.choose_action(b, ["no_direct_answer"]).action != "answer"


def test_expected_cost_is_still_reported_for_forbidden_actions(costs, belief):
    """Kept for auditing: what the rule would have cost is worth seeing."""
    d = costs.choose_action(mk(belief), ["no_direct_answer"])
    assert "answer" in d.expected_costs


def test_constrained_flag_is_false_when_the_rule_did_not_bind(costs, belief):
    """A constraint that removes an action nobody wanted did not change anything."""
    b = mk(belief, hot=.1, warm=.2, cold=.7, needs_human=0.95)
    d = costs.choose_action(b, ["no_direct_answer"])
    assert d.action == "escalate_notify" and d.constrained is False


# --------------------------------------------------------------------------- #
# The decision rule
# --------------------------------------------------------------------------- #

def test_confident_no_human_hot_lead_gets_answered(costs, belief):
    assert costs.choose_action(mk(belief, hot=.9, warm=.08, cold=.02,
                                  needs_human=0.02)).action == "answer"


def test_confident_needs_human_gets_notified(costs, belief):
    assert costs.choose_action(mk(belief, hot=.5, warm=.3, cold=.2,
                                  needs_human=0.95)).action == "escalate_notify"


def test_cold_junk_is_held_or_answered_cheaply(costs, belief):
    d = costs.choose_action(mk(belief, hot=.02, warm=.08, cold=.9, needs_human=0.02))
    assert d.action in ("answer", "hold")


def test_decision_reports_every_action(costs, belief):
    d = costs.choose_action(mk(belief))
    assert set(d.expected_costs) == set(costs.ACTIONS)


def test_margin_is_the_gap_to_next_best(costs, belief):
    d = costs.choose_action(mk(belief, hot=.9, warm=.05, cold=.05, needs_human=0.02))
    ranked = sorted(d.expected_costs[a] for a in d.feasible)
    assert math.isclose(d.margin, ranked[1] - ranked[0])


def test_ties_break_deterministically(costs, belief):
    b = mk(belief, hot=.4, warm=.35, cold=.25, needs_human=0.5)
    assert costs.choose_action(b).action == costs.choose_action(b).action


def test_pause_is_never_the_cheapest_action(costs, belief):
    """A finding, not an accident: escalate-pause is an emergency stop invoked by
    the hard constraint, never the minimum-expected-cost choice. Swept over the
    belief simplex. Recorded in build-log as finding F1."""
    chosen = set()
    for hot in range(0, 11):
        for warm in range(0, 11 - hot):
            cold = 10 - hot - warm
            for nh in (0, .1, .25, .5, .75, .9, 1.0):
                b = mk(belief, hot=hot / 10 or 1e-9, warm=warm / 10 or 1e-9,
                       cold=cold / 10 or 1e-9, needs_human=nh)
                chosen.add(costs.choose_action(b).action)
    assert "escalate_pause" not in chosen, f"pause became price-optimal: {chosen}"


# --------------------------------------------------------------------------- #
# The baseline
# --------------------------------------------------------------------------- #

def test_baseline_has_the_same_shape(costs):
    assert set(costs.UNIFORM_COST) == set(costs.COST)
    for action in costs.ACTIONS:
        assert set(costs.UNIFORM_COST[action]) == set(costs.COST[action])


def test_baseline_agrees_on_which_cells_are_correct(costs):
    """The ONLY difference from COST is magnitude. If the baseline disagreed
    about which action is right in a state, the comparison would be measuring
    two different notions of correctness rather than the value of asymmetry."""
    for action in costs.ACTIONS:
        for state, cost in costs.COST[action].items():
            assert (cost == 0) == (costs.UNIFORM_COST[action][state] == 0), (action, state)


def test_baseline_costs_are_zero_or_one(costs):
    assert {c for row in costs.UNIFORM_COST.values()
            for c in row.values()} == {0.0, 1.0}


def test_baseline_and_real_matrix_can_disagree(costs, belief):
    """If they always chose the same action there would be nothing to report."""
    differs = False
    for hot in (0.1, 0.4, 0.7, 0.9):
        for nh in (0.15, 0.3, 0.45, 0.6):
            b = mk(belief, hot=hot, warm=(1 - hot) / 2, cold=(1 - hot) / 2, needs_human=nh)
            if (costs.choose_action(b).action
                    != costs.choose_action(b, matrix=costs.UNIFORM_COST).action):
                differs = True
    assert differs, "the two policies never disagree — the experiment has no content"


def test_describe_matrix_renders_every_action(costs):
    text = costs.describe_matrix()
    for action in costs.ACTIONS:
        assert action in text


# --------------------------------------------------------------------------- #
# Tie-breaking — an exact tie must not be resolved by asserting
# --------------------------------------------------------------------------- #

def test_tie_break_order_is_derived_from_worst_case_cost(costs):
    """Not hand-written. Same reason UNIFORM_COST is derived: a hardcoded order
    could drift away from the matrix it is supposed to reflect."""
    order = costs.tie_break_order()
    assert order == ("escalate_notify", "ask", "escalate_pause", "hold", "answer")
    worst = [max(costs.COST[a].values()) for a in order]
    assert worst == sorted(worst), "order must be non-decreasing in worst-case cost"


def test_tie_break_order_follows_a_changed_matrix(costs):
    """If `answer` stops being the riskiest action, it stops being last."""
    matrix = {a: dict(row) for a, row in costs.COST.items()}
    for state in matrix["answer"]:
        matrix["answer"][state] = 0.0
    assert costs.tie_break_order(matrix)[0] == "answer"


def test_exact_tie_resolves_to_the_safer_action(costs, belief):
    """b_h=0 on a cold lead ties `answer` and `hold` at 0.000. The safe rule must
    pick `hold`; the legacy rule picked `answer`, the action with the worst
    downside. This is the a11-repeated-097 case from the paper's failure analysis.
    """
    b = mk(belief, hot=0.0, warm=0.0, cold=1.0, needs_human=0.0)
    costs_by_action = {a: costs.expected_cost(a, b) for a in costs.ACTIONS}
    assert math.isclose(costs_by_action["answer"], costs_by_action["hold"]), \
        "fixture no longer produces a tie; the rest of this test proves nothing"

    assert costs.choose_action(b).action == "hold"
    assert costs.choose_action(b, legacy_tie_break=True).action == "answer"


def test_tie_break_never_changes_a_strict_winner(costs, belief):
    """The tie-break must only touch exact ties. Swept over the simplex: wherever
    the two rules disagree, the chosen actions must have had equal expected cost.
    """
    for hot in range(0, 11):
        for warm in range(0, 11 - hot):
            cold = 10 - hot - warm
            for nh in (0, .1, .2, .25, .3, .5, .7, 1.0):
                b = mk(belief, hot=hot / 10, warm=warm / 10, cold=cold / 10,
                       needs_human=nh)
                safe = costs.choose_action(b)
                legacy = costs.choose_action(b, legacy_tie_break=True)
                if safe.action != legacy.action:
                    assert math.isclose(
                        safe.expected_costs[safe.action],
                        legacy.expected_costs[legacy.action]), (
                        f"tie-break changed a strict winner at "
                        f"({hot},{warm},{cold},{nh})")


def test_safe_tie_break_never_costs_more_in_the_worst_case(costs, belief):
    """The property that justifies the change, stated directly."""
    for nh in (0.0, 0.25, 0.5):
        b = mk(belief, hot=1/3, warm=1/3, cold=1/3, needs_human=nh)
        safe = costs.choose_action(b).action
        legacy = costs.choose_action(b, legacy_tie_break=True).action
        assert (max(costs.COST[safe].values())
                <= max(costs.COST[legacy].values()))
