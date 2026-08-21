# Five wrong decisions

Five decisions the cost-aware policy got wrong, with the belief that produced
each one and the cost it incurred.

**Source:** run analysis — derived from `results/run.json` (n=100, provider
`openai=100`, generated 2026-08-19). Expected-cost vectors are recomputed from
the recorded belief and the `cost_matrix` block in the same file; the
recomputation reproduces the recorded `action`, `margin` and `constraint_bound`
for all 100 cases under both policies, so the numbers below are the ones the
policy actually compared. No constraint was active on any of these five
(`constraints: []`), so the feasible set was all five actions in every case.

## The population these five come from

The cost-aware policy missed 16 escalations over 100 cases — 16 cases where the
true `needs_human` label was `True` and the policy chose a non-escalating
action. That count matches the `missed esc.` column in `results/run.md`.

The 16 misses do not all cost the same:

| realised cost | count | action chosen | subtotal |
| ---: | ---: | --- | ---: |
| 3 | 4 | `hold` (true state `cold\|True`) | 12 |
| 4 | 3 | `hold` (true state `warm\|True`) | 12 |
| 10 | 9 | `answer` | 90 |
| | **16** | | **114** |

`hold` is a partial hedge: it is wrong, but it does not deliver a wrong answer,
so the matrix charges 3 or 4 rather than 10. Treating every miss as a cost-10
event overstates the total by 46. The 24 is what those seven `hold` misses
actually cost; at 10 each they would have cost 70.

## The common failure mode

This is finding **F4** in `build-log.md`. All 16 misses share an under-estimated
`needs_human` marginal, not misread readiness:

- every one carries a belief `needs_human` of 0.30 or below (values 0.00, 0.10,
  0.20, 0.30) against a true label of `True`
- the readiness argmax is spread across all three states — cold 7, hot 5, warm 4
  — and in several cases readiness is read correctly and confidently

So the misses are not cases where the model confused "how ready is this lead"
with "does this need a human". They are cases where one marginal — the
`needs_human` probability — was systematically too low. This is evidence *for*
the independence assumed in locked design 0a, not against it: the failing
quantity is a single miscalibrated marginal, and the other marginal is often fine.

The `needs_human` reliability bins in the same run agree: predicted 0.10 against
observed 0.40 in the 0.1–0.2 bin, and predicted 0.30 against observed 0.588 in
the 0.3–0.4 bin. The belief is under-confident about needing a human in exactly
the range where these decisions were made.

## Where the threshold sits

For each case below, the *flip point* is the smallest `needs_human` value that
would have produced an escalation, holding the readiness distribution fixed.

Two different comparisons set it:

- When the policy chose `answer`, the binding comparison is `answer` against
  `escalate_notify`: `10·p = 3·(1−p)`, so the flip point is `p = 3/13 ≈ 0.2308`.
  Both rows of the matrix are flat across readiness, so this threshold does not
  depend on the readiness distribution at all.
- When the policy chose `hold`, the binding comparison is `hold` against
  `escalate_notify`, and the `hold` row is *not* flat across readiness, so the
  flip point moves with the belief — 0.31 to 0.38 in the cases below.

## The five

### 1. Certain and wrong; the action order broke the tie

| | |
| --- | --- |
| case id | `a11-repeated-097` (dev, archetype *vulgar / off-topic*, variant `11b-repeated`) |
| message | "You sound cute, are you single?" |
| context | `turn_index 9`, `repeat_count 3` |
| true labels | readiness `cold`, `needs_human` **True** |
| belief | readiness `{hot 0.0, warm 0.0, cold 1.0}`, `needs_human` **0.00** |
| expected costs | `answer` 0.000 · `ask` 2.000 · `hold` 0.000 · `escalate_notify` 3.000 · `escalate_pause` 5.000 |
| chose | `answer`, margin **0.000** |
| correct action | `escalate_notify` (cell `cold\|True` = 0) |
| cost incurred | **10** — cell `answer[cold\|True]` |
| flip point | `needs_human` > 0.50 (belief was 0.00) |

The belief put all mass on `cold` and `needs_human` at exactly zero, which zeroes
the expected cost of both `answer` and `hold`. The margin is 0.000: the policy
had no expected-cost preference between them, and `answer` was selected only
because it precedes `hold` in `ACTIONS`. In the true state `cold|True`, `hold`
costs 3 and `answer` costs 10, so the tie-break alone accounts for 7 of the 10.

### 2. Readiness read correctly, `needs_human` missed

| | |
| --- | --- |
| case id | `a04-booking-042` (dev, archetype *ready buyer*, variant `4b-booking`) |
| message | "Please arrange a visit, I want to close this week" |
| context | `turn_index 1`, `repeat_count 0` |
| true labels | readiness `hot`, `needs_human` **True** |
| belief | readiness `{hot 0.8, warm 0.2, cold 0.0}`, `needs_human` **0.10** |
| expected costs | `answer` 1.000 · `ask` 2.200 · `hold` 5.220 · `escalate_notify` 2.700 · `escalate_pause` 5.400 |
| chose | `answer`, margin **1.200** |
| correct action | `escalate_notify` (cell `hot\|True` = 0) |
| cost incurred | **10** — cell `answer[hot\|True]` |
| flip point | `needs_human` ≥ 0.231 (belief was 0.10, short by 0.131) |

The clearest single illustration of F4. Readiness is right and confident — 0.8 on
`hot` against a true label of `hot` — and the message is an explicit request to
arrange a visit and close. Only the `needs_human` estimate failed. This is also
the largest margin of the five at 1.200, so it is the most confidently wrong: no
small calibration correction reaches it.

### 3. Just below the threshold

| | |
| --- | --- |
| case id | `a02-deep-015` (test, archetype *send photos*, variant `2b-deep`) |
| message | "Send photos, I want to see the actual site not the brochure ones" |
| context | `turn_index 9`, `repeat_count 0` |
| true labels | readiness `warm`, `needs_human` **True** |
| belief | readiness `{hot 0.6, warm 0.3, cold 0.1}`, `needs_human` **0.20** |
| expected costs | `answer` 2.000 · `ask` 2.400 · `hold` 4.380 · `escalate_notify` 2.400 · `escalate_pause` 4.800 |
| chose | `answer`, margin **0.400** |
| correct action | `escalate_notify` (cell `warm\|True` = 0) |
| cost incurred | **10** — cell `answer[warm\|True]` |
| flip point | `needs_human` ≥ 0.231 (belief was 0.20, short by **0.031**) |

The narrowest miss in the set: the belief was 0.031 below the threshold. Worth
reading against `a02-deep-018`, the same archetype and variant, where the belief
put `needs_human` at 0.30, the policy escalated, and the cost was 0. Two cases
from one archetype straddle `3/13`, and a 0.10 difference in one marginal is the
whole distance between a cost of 0 and a cost of 10.

### 4. `hold` as a hedge, on a lead misread as cold

| | |
| --- | --- |
| case id | `a03-followup-024` (dev, archetype *one-word ping*, variant `3b-followup`) |
| message | "Hello?" |
| context | `turn_index 9`, `repeat_count 0` |
| true labels | readiness `warm`, `needs_human` **True** |
| belief | readiness `{hot 0.1, warm 0.2, cold 0.7}`, `needs_human` **0.30** |
| expected costs | `answer` 3.000 · `ask` 2.600 · `hold` 1.670 · `escalate_notify` 2.100 · `escalate_pause` 3.900 |
| chose | `hold`, margin **0.430** |
| correct action | `escalate_notify` (cell `warm\|True` = 0) |
| cost incurred | **4** — cell `hold[warm\|True]` |
| flip point | `needs_human` ≥ 0.373 (belief was 0.30, short by 0.073) |

The one case of the five where readiness is also wrong — 0.7 on `cold` against a
true label of `warm`. That error is what makes `hold` look cheap: the `cold|False`
cell of `hold` is 0, so mass on `cold` pulls the expected cost of `hold` down to
1.670 and it beats `escalate_notify`. The readiness error does not cause the miss
on its own — `needs_human` at 0.30 is still under the 0.373 flip point — but it
raises the flip point the belief had to clear.

### 5. The cheapest possible miss

| | |
| --- | --- |
| case id | `a10-persistent-091` (test, archetype *polite time-waster*, variant `10b-persistent`) |
| message | "I can't come for a visit but give me the discount price" |
| context | `turn_index 14`, `repeat_count 3` |
| true labels | readiness `cold`, `needs_human` **True** |
| belief | readiness `{hot 0.1, warm 0.6, cold 0.3}`, `needs_human` **0.20** |
| expected costs | `answer` 2.000 · `ask` 2.400 · `hold` 1.780 · `escalate_notify` 2.400 · `escalate_pause` 4.300 |
| chose | `hold`, margin **0.220** |
| correct action | `escalate_notify` (cell `cold\|True` = 0) |
| cost incurred | **3** — cell `hold[cold\|True]` |
| flip point | `needs_human` ≥ 0.305 (belief was 0.20, short by 0.105) |

The lowest-cost miss available in the matrix. `hold` on a lead that is genuinely
`cold` incurs 3 rather than 10, because holding a cold lead wastes little even
when a human was in fact needed. Included to keep the set honest about the
spread: a miss on a cold lead and a miss on a hot ready-to-close buyer are not
the same event, and reporting a single "missed escalation" count hides that.

## Which of the five costs most

Three of the five realise 10, the largest single-decision cost in the matrix:
`a11-repeated-097`, `a04-booking-042` and `a02-deep-015`. On realised cost alone
they tie.

**`a11-repeated-097` is the worst of the three.** Two reasons, neither of which
is the cost number:

1. Its belief is furthest from the flip point. It needed `needs_human` above 0.50
   to escalate and reported 0.00 — a gap of over 0.50, against 0.131 for
   `a04-booking-042` and 0.031 for `a02-deep-015`. Recalibrating the marginal
   fixes the other two and does not fix this one.
2. It was not decided by the cost model at all. The margin is 0.000; `answer` and
   `hold` had identical expected cost and the `ACTIONS` ordering picked between
   them. Had the order been different, the same belief and the same matrix would
   have produced `hold` and a cost of 3. Seven of the ten are attributable to a
   tie-break, which is a property of the implementation rather than of the policy.

The distinction matters for what each failure implies. `a02-deep-015` and
`a04-booking-042` are calibration errors and argue for improving the
`needs_human` estimate. `a11-repeated-097` argues for something else: a belief
that returns 0.00 for a marginal it cannot actually rule out, and a tie-break
that resolves toward the highest-cost action rather than the lowest.

## Cost-matrix cells charged

Every cell above, from the `cost_matrix` block of `results/run.json`:

| cell | value | where it appears |
| --- | ---: | --- |
| `answer[hot\|True]` | 10 | case 2 |
| `answer[warm\|True]` | 10 | case 3 |
| `answer[cold\|True]` | 10 | case 1 |
| `hold[warm\|True]` | 4 | case 4 |
| `hold[cold\|True]` | 3 | case 5; the counterfactual in case 1 |
| `escalate_notify[hot\|True]` | 0 | correct action, case 2 |
| `escalate_notify[warm\|True]` | 0 | correct action, cases 3 and 4 |
| `escalate_notify[cold\|True]` | 0 | correct action, cases 1 and 5 |

`escalate_notify` is the unique cost-minimising action in all three `needs_human
= True` states, so "the correct action" is unambiguous for every case here.

## What this set does not cover

These are all single-message belief-scoring errors. Finding **F7** in
`build-log.md` records a different failure class — a high-cost signal dropped at
a turn boundary — which this test set cannot exhibit by construction, because
every case carries one `message` string. See limitation **L7**.
