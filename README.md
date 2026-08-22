# Cost-aware escalation

When should a conversational agent stop talking and get a human involved?

A sales agent has to decide, on every inbound message, whether to answer, ask a
qualifying question, hold, notify a human while the conversation continues, or
pause and hand over. It has to decide without knowing whether the lead is a
serious buyer, or whether this is the kind of conversation a person should be in.
The usual move is to classify the lead and route on the label. I wanted to see
what changes when the agent reasons about the cost of being wrong instead.

So the policy keeps an explicit belief over the hidden state — a distribution over
{hot, warm, cold}, plus a separate probability that the lead needs a human — and
picks whichever action has the lowest expected cost under a 30-cell matrix where
the costs are business damage rather than what happens to be easy to measure.
Answering someone who needed a human costs 10. A needless notification costs 3.
That asymmetry is the whole mechanism: choosing between answering and notifying,
it is already worth escalating once the chance of needing a human clears 3/13 —
about 23%, well short of likely. Against holding, the crossover sits higher and
moves with the readiness split.

## What happened

Over 100 synthetic cases the cost-aware policy costs 172, against 258 for a
baseline that sees the same belief but flattens every non-zero cost to 1. They
disagree on 46 of the 100 cases.

The claim I'd attack if I were reviewing this: escalating every single message
scores 174, within 2 of the cost-aware policy. Under this matrix human attention
is cheap enough that blanket escalation is nearly free, so the honest version is
that the policy reaches about the same cost while escalating far less often —
precision 0.60 against 0.42 — not that it wins on cost. A matrix where humans are
scarcer would separate the two properly.

It also misses 16 escalations, and all 16 share one cause: the `needs_human`
probability is read too low, while readiness is often read correctly. That is the
most useful thing the experiment produced, and it's written up case by case.

## Where things are

Everything is under
[`when-to-escalate/`](when-to-escalate/).

| | |
| --- | --- |
| the policy, belief, and cost matrix | [`src/costs.py`](when-to-escalate/src/costs.py), [`src/belief.py`](when-to-escalate/src/belief.py) |
| the run every number above comes from | [`results/run.md`](when-to-escalate/results/run.md), [`results/run.json`](when-to-escalate/results/run.json) |
| the 16 misses, worked through | [`results/wrong-decisions.md`](when-to-escalate/results/wrong-decisions.md) |
| one decision reasoned out by hand | [`decisions/probability-decision-record.md`](when-to-escalate/decisions/probability-decision-record.md) |
| every design choice, and why | [`build-log.md`](when-to-escalate/build-log.md) |
| the paper | [`paper/main.tex`](when-to-escalate/paper/main.tex) |

Beliefs come from `gpt-4o-mini`. The cache behind the reported numbers is
committed, so every number above is reproducible without calling the model again.
