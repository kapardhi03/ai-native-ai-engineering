# Probability Decision Record — case `a02-deep-018`

## The case

A lead deep in an existing conversation (turn 14) sends:
"I need actual site photos before I discuss with my wife."

Model belief: readiness {hot 0.40, warm 0.50, cold 0.10}, needs_human 0.30.
True labels: warm, needs_human = True.
Decision threshold on needs_human: 3/13 ≈ 0.23 (above it, escalate; below it, answer).

## Summary (template elements)

| Element | Entry |
| --- | --- |
| Evidence | Turn-14 message: "I need actual site photos before I discuss with my wife" |
| Hidden states | readiness {hot, warm, cold}; needs_human {True, False} |
| Beliefs | readiness {0.40, 0.50, 0.10}; needs_human 0.30 |
| Event | Whether this lead needs a human (needs_human = True) |
| Actions | answer, ask, hold, escalate_notify, escalate_pause |
| Costs | wrong answer 10; needless notify 3; correct notify 0 (full matrix in costs.py / run.json) |
| Policy | Minimum expected cost; escalate when needs_human > 3/13 ≈ 0.23 (this case; the threshold is readiness-dependent when hold is the alternative) |
| Decision | escalate_notify — belief 0.30 clears the threshold; realised cost 0 |
| Audit data | See audit table below |

## 1. Prior — before reading the message

My priors here are estimates from live traffic, not measured frequencies, so I
mark them as judgment. In real estate the junk rate is high: from what I've seen
live, roughly 5 of 20 leads even send a second message. So out of 100 fresh
leads I'd put 2 hot, 13 warm, and 85 cold. Cold here includes genuine
tire-kickers and non-leads — blasts, wrong numbers, no-signal pings — so cold
absorbs them and readiness sums to 100. In production these are distinct, but the
model collapses them into cold, which is limitation L2. Separately, 30–40 out of
100 end up needing a human — for trust, legal, or hand-holding reasons — even
though far fewer are hot.

Worth noting: my needs_human base rate (30–40%) is much higher than my hot rate
(1–2%). Readiness and needs_human clearly move on different axes — a warm or even
cold lead can still need a human. This is the independence assumed in locked
design 0a, showing up in my own gut numbers before any model runs.

## 2. Evidence — what the message is

"discuss with my wife" pulls readiness down slightly — it's a deferral, the
decision isn't his alone. But "I need actual photos" pushes back up: it's a
proof demand, the kind of thing a buyer asks, not a time-waster. Net, readiness
is roughly neutral to slightly up. On needs_human it points clearly up — this is
about trust and a family decision, exactly where a human closer adds value. Not
an emergency, so the right shape is notify (tell a human, bot keeps going), not
pause.

## 3. Likelihood — how strong is this signal

A message combining a family decision with a demand for proof is a stronger-
than-average needs_human signal. People who bring emotion and family into it are
less likely to be junk — in this market, coming to visit with family is a normal
step toward buying. So relative to my 30–40% base rate, a message like this
should sit above average, not at it.

## 4. Posterior — belief after the evidence

The model put needs_human at 0.30. Given my read in step 3, that's under-reading
it — I'd have put it closer to 0.55 for a message this loaded. The model has the
direction right (above the threshold) but the magnitude low. This is the F4
calibration gap in one case: the model isn't confusing the two axes, it's
under-confident on the needs_human marginal for exactly these emotional/trust
messages.

## 5. Threshold comparison

At needs_human 0.30 the belief clears the 0.23 threshold by 0.07. The argmin
flips from answer to escalate_notify at p = 3/13, and only the answer and
escalate_notify rows enter that comparison — both flat across readiness — so the
crossover is independent of the readiness split. Even the model's low 0.30 was
enough to tip the decision the right way.

## 6. Decision and why cost-awareness won

Cost-aware policy chose escalate_notify, expected cost 2.10, realised cost 0 —
correct. The uniform baseline, blind to cost asymmetry, chose answer at an
apparent 0.30 and ate a realised cost of 10.

The cost matrix let the first agent see what the second couldn't: being wrong in
one direction (answering when a human was needed) costs 10, being wrong in the
other (a needless notify) costs 3. Given that gap, even a modest 30%
chance of needing a human was already enough to make escalating the cheaper bet.
The baseline treated both mistakes as equal, so answering looked cheapest, and it
walked straight into the expensive error.

## Audit

| field | value |
| --- | --- |
| case_id | a02-deep-018 |
| split | dev |
| data version | cases.json, seed 20260818 |
| model / provider | gpt-4o-mini belief provider |
| policy version | cost_aware vs uniform_baseline, run dcd2132 |
| threshold | needs_human > 3/13 ≈ 0.2308 |
| priors | author judgment, not measured frequencies (refer to section 1) |
