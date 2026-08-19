# Build Log

> **Working record, not a graded deliverable.** Same status as `PLAN.md` — nobody
> reviews this file. It exists so every design decision in this project has a
> written reason attached to it, recorded when the decision was made rather than
> reconstructed afterwards.
>
> **This is not `review-record.md`.** That file is reserved for the three formal
> AI reviews of the finished project. This one is the running build. Keep them
> separate.

## How to read this

One row per decision. Never edit a row after the fact — if a decision is
reversed, add a new row that supersedes it and say so in the reason. The point of
the log is that it shows what was believed at the time, including the parts that
turned out wrong.

**Verdict** is one of:

| Verdict | Meaning |
| --- | --- |
| `Locked at outset` | Decided before the build started. Not up for reopening. |
| `Approved` | Proposed during the build, accepted. |
| `Rejected` | Proposed during the build, turned down. Reason records why. |
| `Superseded` | Was live, later replaced. Names the row that replaced it. |

`Reason` is the human's reason, in the human's words. Where a reason has not been
given yet, the cell says so explicitly rather than being filled with a guess.

---

## Decisions

| # | Date | Decision | Verdict | Reason | Affected |
| --- | --- | --- | --- | --- | --- |
| 0a | pre-build | Belief = readiness distribution over {hot, warm, cold} summing to 1, **plus** a separate independent `needs_human` probability | Locked at outset | Two separate judgments, not one score. A hot lead can have low `needs_human`; a cold lead can have high `needs_human`. | `src/belief.py` |
| 0b | pre-build | Decision rule = myopic one-step minimum-expected-cost over {answer, ask, hold, escalate} | **Superseded by 25** | Full belief-state planning is intractable, so a one-step rule is the defensible approximation (Kaelbling, Littman & Cassandra — Source 5 in `research-file.md`). | policy (not yet built) |
| 0c | pre-build | Wrong assertion is a **hard constraint**, not a priced term in the cost matrix | Locked at outset | Concretely: the AI has no right to send legal or land documents. No cost number should ever make sending land papers acceptable, so it cannot be a term that a large enough benefit outweighs. Archetype 5 is the worked example. | policy (not yet built) |
| 0d | pre-build | Belief comes from a real LLM call, cached to JSON per case id | Locked at outset | Both policies must run over identical beliefs, so the non-deterministic call happens exactly once per case and is then frozen. | `src/belief.py` |
| 0e | pre-build | Baseline = same decision logic with a uniform cost matrix | Locked at outset | *Reason not yet given — to be filled in by KK.* | baseline (not yet built) |
| 0f | pre-build | Public boundary: no product name, no client data, no real prompts | Locked at outset | Everything stays at the general problem level. The prompt in `belief.py` is synthetic and written for this experiment. | all files |
| 1 | 2026-08-18 | `build-log.md` lives at `week1/deliverables/when-to-escalate/build-log.md`, **committed**, not gitignored | Approved | Sits alongside the other record files. Initially asked for it gitignored; reversed once it was clear the build runs in an ephemeral container, where a gitignored file dies with the container and the decision record would be lost entirely. | this file |
| 2 | 2026-08-18 | Log includes the pre-build locked design as rows `0a`–`0f` (Option B), not just decisions made during the build | Approved | "Clean and more readable, i.e. provides wider information." The log should stand alone for a reader who was not present for the locked design. | this file |
| 3 | 2026-08-18 | Belief must come from a real LLM call. API key supplied via `.env`, which is gitignored | Approved | *Reason not yet given — to be filled in by KK.* Consequence: the rule-based keyword fallback must not silently satisfy an experiment run. | `src/belief.py`, `.env` |
| 4 | 2026-08-18 | "Modular" means the **wider `src/` structure**, not the log's layout | Approved | Future integrations should be easy to drop in. Clarified after ambiguity in the original instruction. | `src/` |
| 5 | 2026-08-18 | Work proceeds one step at a time; no file is created or changed until that specific step is approved | Approved | Keeps every change traceable to an explicit decision instead of arriving in a batch. | process |
| 6 | 2026-08-18 | *(fallback default later reversed by decision 21)* Rule-based fallback **kept**, but gated: `BELIEF_ALLOW_RULE_FALLBACK` in `.env`, and the provider that produced a belief is surfaced to callers | Approved | "Offline smoke tests keep working; a real run can't silently degrade." Deleting it would break offline runs; leaving it silent would void decision 3, since a run where both APIs fail would produce keyword beliefs that look identical to LLM beliefs in the cache. | `src/config.py`, `src/belief.py` |
| 7 | 2026-08-18 | `python-dotenv` adopted as a real dependency; `requirements.txt` created at the repo root | Approved | Chosen over a hand-rolled parser. Consequence: the repo now needs dependency management, which it had none of. `requirements.txt` added in the same step since a dependency undeclared anywhere is worse than the parser would have been. | `requirements.txt` |
| 8 | 2026-08-18 | Cache path read from `.env` as `BELIEF_CACHE_PATH`; relative values resolve against the **repo root**, never the working directory | Approved | Closes Q3. Verified: the same relative path now resolves to one absolute path whether run from the repo root or from `when-to-escalate/`. | `src/config.py` |
| 9 | 2026-08-18 | The restructure proceeds one sub-step at a time, committing at coherent points rather than after every file | Approved | Same reasoning as decision 5, applied to a multi-file change. | process |
| 10 | 2026-08-18 | Config is loaded once per process and memoised; secrets are masked in `__repr__` and in `describe()` | Approved | *Reason not yet given — proposed by Claude.* A run must not see configuration change halfway through, and this repo is public, so a settings object that prints an API key into a traceback or a run log is a live leak risk. | `src/config.py` |
| 11 | 2026-08-18 | `Belief` stays the pure mathematical object; provenance moves to a separate `BeliefMeta`. `get_belief()` returns the pair | Approved | "Put it separate." Keeps the code's `Belief` identical to the paper's belief, so bookkeeping never contaminates the object the policy reasons over. Cost: callers unpack a tuple. | `src/belief.py` |
| 12 | 2026-08-18 | `belief.py` rewired onto `config.py`: no module constants, no ambient env reads, keys passed explicitly into each provider | Approved | Closes Q5. Makes the Q3 cache-path fix actually take effect, and makes `config.py` the only place configuration resolves. | `src/belief.py` |
| 13 | 2026-08-18 | Cache writes are atomic (temp file + `os.replace`) | Approved | *Reason not yet given — proposed by Claude.* The previous version truncated the real cache before writing, so a crash or interrupt mid-write destroyed every belief already collected — expensive, since each one costs an API call. | `src/belief.py` |
| 14 | 2026-08-18 | `cache_provenance()` added: counts cache entries by provider | Approved | *Reason not yet given — proposed by Claude.* Makes Q6 checkable in one call before reporting calibration, rather than relying on remembering how a run went. | `src/belief.py` |
| 15 | 2026-08-18 | The reported belief cache must be **LLM-only**; a mixed cache is not a valid basis for calibration | Approved | "It should be LLM Belief." Generate the reported cache with `BELIEF_ALLOW_RULE_FALLBACK=false`. Closes the intent behind Q6. | `src/belief.py`, `.env` |
| 16 | 2026-08-18 | Providers extracted to `src/providers/`: one file per source, a registry, a shared prompt, and a shared JSON extractor | Approved | Closes Q7. Adding a provider is now a new file plus one `register()` call, with no edit to `belief.py`. `belief.py` keeps the belief, the provider *policy*, and the cache; it no longer knows how any provider works. | `src/providers/`, `src/belief.py` |
| 17 | 2026-08-18 | `config.VALID_PROVIDERS` replaced by a lookup against the live registry | Approved | *Reason not yet given — proposed by Claude.* Found by a test: registering a provider did not make it selectable, because config validated against a hardcoded tuple. The registry was decorative until this was fixed. | `src/config.py` |
| 18 | 2026-08-18 | `extract_json` rejects any JSON that is not an object | Approved | *Reason not yet given — proposed by Claude.* Found by a test: a model replying `null` or `[]` parsed cleanly, then every `.get()` missed and produced a confident uniform belief instead of a visible failure. | `src/providers/json_utils.py` |
| 19 | 2026-08-18 | Full pytest suite added under `tests/`, with stubbed SDKs; no test may make a network call | Approved | "Build the test files. Include every edge case and consider all the cases." Stubs exercise the real provider code path, including the SDK import, so the tests cover production behaviour rather than a parallel implementation. | `tests/`, `pytest.ini` |
| 20 | 2026-08-18 | `assert_llm_only()` added: raises unless every cached belief came from a real model | Approved | *Reason not yet given — proposed by Claude.* Turns decision 15 into a check that runs, rather than a rule someone has to remember before quoting an ECE figure. | `src/belief.py` |
| 21 | 2026-08-18 | `BELIEF_ALLOW_RULE_FALLBACK` now defaults to **false**. Keyword scoring must be opted into | Approved | Closes Q9. Follows from decision 15: silence should give the safe answer. Previously an unconfigured run produced a mixed cache and you had to remember the flag; now a keyless run stops at load with an explanation. Supersedes the permissive default set in decision 6. | `src/config.py` |
| 22 | 2026-08-18 | Pinning `BELIEF_PROVIDER=rule` while `BELIEF_ALLOW_RULE_FALLBACK=false` stays a hard error rather than being auto-resolved | Approved | *Reason not yet given — proposed by Claude.* It is a genuine contradiction and either silent resolution would be a guess about intent. Cost: an offline run sets two variables instead of one. | `src/config.py` |
| 23 | 2026-08-18 | GitHub Actions workflow added: runs the suite and the offline smoke test on every push and PR, on Python 3.10 and 3.12 | Approved | Makes the tests load-bearing instead of advisory. The strict gate protecting the calibration claim was only verified when someone remembered to run pytest. No secrets are configured for the job, so a test that started making real network calls fails there rather than silently billing someone. | `.github/workflows/tests.yml` |
| 24 | 2026-08-18 | `.env.example` committed with placeholder values only | Approved | *Reason not yet given — proposed by Claude.* Gives the variable names and the strict-mode guidance a real place to live; `.gitignore` whitelists it while still ignoring `.env`. | `.env.example` |
| 25 | 2026-08-18 | **Action set expanded to five**: {answer, ask, hold, escalate-notify, escalate-pause}. Supersedes locked design 0b | Approved | Design change forced by case construction. My own production archetypes showed notify and pause carry different costs — pause risks a live lead going cold; notify spends human attention but keeps the conversation alive. Collapsing them would throw away the core cost asymmetry the project is about. | policy, cost matrix (not yet built) |
| 26 | 2026-08-18 | Optional `context` (turn index, repeat count) added to `get_belief`, fed into the prompt | Approved | Keeps the context-dependent archetypes intact and gives evidence to answer research-file question 8: single-message belief is insufficient for ~1/3 of archetypes. Belief stays a pure function of (message + context) so caching is still honest. | `src/belief.py`, `src/providers/` |
| 27 | 2026-08-18 | Readiness stays **three states**. Non-leads (competitor, abuse, spam blast) are labelled `cold` as a known approximation | Approved | Not adding a `not_a_lead` state — too many locked pieces moving at once for Week 1, and every calibration bin would shift. The approximation is recorded explicitly so it surfaces in the paper as a limitation. | `data/`, paper |
| 28 | 2026-08-18 | Case set is **100 cases**, split by a fixed seed into 50 dev / 50 test, committed | Approved | Same 50 to develop on, same 50 to report on, frozen. No random per-run draw — reproducibility comes first. Rejects the earlier "random 50 each run" idea, which would have made published numbers irreproducible and confounded the policy comparison with the draw. | `data/` |
| 29 | 2026-08-18 | Cache fingerprint renamed `msg_hash` → `input_hash`, computed over message **and** context | Approved | *Reason not yet given — proposed by Claude.* Hashing the message alone would let context drift silently while the cache still reported a match, which would break the "identical beliefs" guarantee in a way nothing would detect. | `src/belief.py` |
| 30 | 2026-08-18 | Providers receive `message` and `context` **separately**; only text-to-model providers render them together | Approved | *Reason not yet given — proposed by Claude.* Found by a test after I initially rendered context for every provider: the phrase "already received" contains "ready", a hot keyword, so the keyword provider read a no-signal opener as a hot lead. A substring matcher must only ever see what the lead wrote. | `src/providers/`, `src/belief.py` |
| 31 | 2026-08-18 | Case-set distribution approved: 4=16, 5=12, 1=10, 10=10, 2/3/6/7/8=8, 9=6, 11=6 | Approved | Weighted toward the archetypes where the cost asymmetry bites, thinning the over-sharer, while protecting a block of clean answer-only cases (sub-variant 4a) so the set is not so escalation-heavy that an always-escalate policy scores well by default. | `data/cases.json` |
| 32 | 2026-08-18 | 100 cases written to `data/cases.json`, generated by `data/build_cases.py` | Approved | Labels reviewed and confirmed before writing. The generator is committed alongside the data so the seeded split can be re-derived, but `cases.json` is the source of truth — the messages are hand-authored, not generated. | `data/` |
| 33 | 2026-08-18 | **Cost: wrong answer / false assertion = 10** | Approved | Hard constraint (false legal/land claims, tail risk). Sits at the top, nearly forbidden. My earlier 6 contradicted the paper's own thesis and under-priced the one thing no revenue should ever justify. | cost matrix |
| 34 | 2026-08-18 | **Cost: hold a hot lead = 6** | Approved | A hot, ready-to-buy lead left waiting is the worst outcome short of the hard constraint. Recoverable but the most damaging non-forbidden mistake in my market. | cost matrix |
| 35 | 2026-08-18 | **Cost: needless escalate-pause = 5** | Approved | An active stop is bad, but I judge losing a hot lead to a wait as worse than a needless freeze. | cost matrix |
| 36 | 2026-08-18 | **Cost: needless escalate-notify = 3** | Approved | Spent a human glance, cheap. | cost matrix |
| 37 | 2026-08-18 | **Cost: needless ask = 2** | Approved | Cheapest. One question, mild friction, keeps the lead alive and improves the belief for the next turn. My earlier 7 would have made "ask" a dead action and pre-answered research-file Q2 in the wrong direction. | cost matrix |
| 38 | 2026-08-18 | **Cost: correct actions = 0; correct escalate-pause = 1 residual** | Approved | Human time plus a brief wait, so the policy does not treat correct pausing as free and over-escalate. | cost matrix |
| 39 | 2026-08-18 | `tests/test_cases.py` added: validates the committed case set | Approved | *Reason not yet given — proposed by Claude.* `data/cases.json` is what the reported numbers are computed over. A hand-edited label, a lost case, or a split that stopped being balanced would change published results with nothing to notice. | `tests/test_cases.py` |
| 40 | 2026-08-18 | Full 30-cell cost matrix approved as proposed | Approved | The additivity reasoning is right — hold on hot+needs-human is 8, not 16. The harms overlap, they don't stack; anything above 10 would break the false-assertion-is-top framing. No hotness premium on a false answer. | `src/costs.py` |
| 41 | 2026-08-18 | `escalate-pause` stays constraint-driven and is never the minimum-expected-cost action | Approved | Correct by design, not a repeat of the "ask" bug. Pause is an emergency stop, not a routine cost choice — you pause because continuing is unacceptable, not because it's cheapest. Unlike "ask", it is not supposed to win on price. To be stated in the paper as finding F1 so it does not read as an accident. | `src/costs.py`, paper |
| 42 | 2026-08-18 | `"constraints": ["no_direct_answer"]` added to the 8 restricted cases; regenerated with the same seed and split | Approved | The constraint rides on the case because the belief cannot encode it. Verified: case ids, labels and split are byte-identical to the previous generation; only the new field differs. | `data/cases.json` |
| 43 | 2026-08-18 | `src/costs.py` written; the hard constraint is enforced as **infeasibility**, never as a price | Approved | A constraint expressed as a large number can be outbid by a sufficiently confident belief, which is exactly what a hard constraint must forbid. Confirmed by a test that sets `answer` to cost 0 in every state and shows a constrained case still refuses it. | `src/costs.py` |
| 44 | 2026-08-18 | Baseline `UNIFORM_COST` is **derived** from `COST` (0 stays 0, every non-zero becomes 1) rather than hand-written | Approved | *Reason not yet given — proposed by Claude.* Keeps the two policies agreeing on which action is correct in each state, so the only difference is the magnitude of the asymmetry. A hand-written baseline could disagree about correctness, and the comparison would then measure two different notions of "right" instead of the value of pricing errors differently. | `src/costs.py` |

---

## Open questions carried into the build

Not decisions yet. Listed so they are not lost between steps.

| # | Question | Status | Outcome |
| --- | --- | --- | --- |
| Q1 | Should the rule-based fallback be deleted, or kept behind a flag? | **Closed** | Kept, gated by `BELIEF_ALLOW_RULE_FALLBACK`. See decision 6. |
| Q2 | `.env` is inert — where does config loading live? | **Closed** | `src/config.py`, via `python-dotenv`. See decisions 7 and 10. |
| Q3 | `DEFAULT_CACHE_PATH` is relative to the working directory. | **Closed** | Read from `.env`, resolved against the repo root. See decision 8. |
| Q4 | Reasons for rows `0e`, `3`, `10`, `13`, `14`, `17`, `18`, `20`, `22`, `24`, `29`, `30` and `39` are still blank. `0c` is filled. | Open | Fill in above. |
| Q5 | `belief.py` does not yet use `config.py`. | **Closed** | Rewired. See decision 12. |
| Q6 | Is the belief calibrated enough to threshold on (research-file Q1)? Cannot be answered while any cached belief may be keyword-derived — ECE over a mixed cache is not LLM calibration. | Open | Now checkable via `cache_provenance()`. Needs a real strict run, which must happen on KK's machine — the build container has no keys. |
| Q7 | Providers still live inside `belief.py`. | **Closed** | Extracted to `src/providers/`. See decision 16. |
| Q8 | No test file exists. | **Closed** | 208 tests under `tests/`. See decision 19. |
| Q9 | `BELIEF_ALLOW_RULE_FALLBACK` defaults to true, so an unconfigured run can produce a mixed cache. | **Closed** | Default flipped to false. See decision 21. |
| Q10 | No synthetic case set exists in `data/`. | **Closed** | 100 cases written and validated. See decisions 31–32. |
| Q12 | Cost numbers for the five actions are unset. | **Closed** | Set by KK with per-cost reasoning. See decisions 33–38. |
| Q13 | The cost matrix is a **ranking**, not a full (action × state) table. Costs for correct actions are 0 and correct pause is 1, but the mapping from these five error costs onto all 5 actions × 6 states is not yet written down. | Open | Next step: the cost module. |
| Q14 | The 42% `needs_human` rate is far above a real inbound base rate, so precision and recall on this set will not transfer to production. Deliberate — needed for measurability — but must be stated as a limitation. | Open | Paper, limitations section. |
| Q11 | Nothing downstream of the belief exists yet: no cost matrix, no policy, no baseline. The decision rule (now 25) and hard constraint (0c) are unimplemented. | Open | After the case set. |
| Q12 | The five-action set (25) means the cost matrix gains a column, and `escalate-notify` vs `escalate-pause` need relative costs. Those numbers are unset. | Open | Needs KK's cost ratios; research-file question 3. |

---

## Limitations to carry into the paper

Recorded here as they surface, so the limitations section is written from a list
rather than from memory.

| # | Limitation | Where it came from |
| --- | --- | --- |
| L1 | The `needs_human` base rate in `data/cases.json` is 42%, far above a real inbound stream. Inflated deliberately so the asymmetry is measurable, but it means **precision and recall on this set will not transfer to production base rates**. | Decision 31, Q14 |
| L2 | Non-leads — competitor fishing, abuse, spam blasts — are labelled `cold` rather than given their own state. A known approximation; readiness calibration is slightly distorted by it. | Decision 27 |
| L3 | Readiness labels are *authored intent*, not observed outcomes. Calibration on readiness measures agreement with my labelling, not with what the lead actually did. `needs_human` labels are stronger, being true by construction. | Two-label decision |
| L4 | The synthetic set makes missed escalation measurable precisely because it is not real. In production there is no follow-up signal, so recall would be unmeasurable — this is the trade the set makes. | research-file Q6 |
| L5 | The state space is **too coarse to separate competitor-fishing from abuse**: both are `(cold, needs_human=True)`, yet the archetypes want different actions — answer-price-only versus stop-and-pause. The cost matrix cannot price them differently. Evidence that a richer state, or a separate intent flag alongside readiness, would be needed. A real finding about the factorisation, not a confession. | Decision 40, Q2 ruling |
| L6 | The hard constraint is treated as **observable and error-free**, while the hidden state is not. `constraints` rides on the case; in production a detector would fire it and would carry its own false-positive and false-negative rates, which this experiment does not model. | Decision 42, Q3 ruling |
| L7 | **F7 names a failure class this test set cannot exhibit by construction.** Every case in `data/cases.json` carries `message` as a single string and `context` as `{turn_index, repeat_count}`, and the harness evaluates one message per turn, so a turn containing two messages — one routine, one carrying the only `needs_human` signal — cannot occur in the set. This is narrower and more concrete than L1–L6: it is a specific instance of what the realism-for-measurability trade in L4 hides, namely an entire failure class that is invisible to a one-message-per-case harness rather than merely distorted by it. Surfacing it would require multi-message-per-turn cases and a per-message evaluation step before the turn is acted on; this experiment has neither, so no number reported here bears on it. | F7, `data/cases.json` schema |

---

## Findings for the paper

| # | Finding | Source | Evidence |
| --- | --- | --- | --- |
| F1 | **`escalate-pause` is never the minimum-expected-cost action.** Swept across the belief simplex it is never chosen on price; it is invoked only by the hard constraint. This is the correct shape for an emergency stop — you pause because continuing is unacceptable, not because it is cheapest — and is stated as a design finding rather than left to look like an accident. | Test — exhaustive simplex sweep | `tests/test_costs.py::test_pause_is_never_the_cheapest_action` |
| F2 | **Single-message belief is insufficient for roughly a third of the archetypes.** Archetypes 1, 3 and 11 need conversation position to be decidable at all. Answers research-file question 8. | Design — case construction | Decision 26, `data/cases.json` |
| F3 | **The cost-aware policy and the uniform baseline disagree over a wide band of beliefs**, not just at the edges — the baseline keeps answering while the cost-aware policy escalates, from around P(needs_human) ≈ 0.3 upward at high readiness. | Test | `tests/test_costs.py::test_baseline_and_real_matrix_can_disagree` |
| F4 | **Every missed escalation came from an under-estimated `needs_human`, not from misread readiness.** All 16 cases the cost-aware policy failed to escalate carry a belief `needs_human` of 0.30 or below — the values are 0.00, 0.10, 0.20 and 0.30 — against a true label of `True`. The readiness argmax on those same cases is spread across cold (7), hot (5) and warm (4), so high readiness is not what suppressed the escalation; the `needs_human` estimate is low regardless of readiness. This is consistent with the reliability bins, where the model is under-confident in exactly this range (bin 0.1–0.2: predicted 0.10, observed 0.40; bin 0.3–0.4: predicted 0.30, observed 0.588). It is therefore evidence **for** the independence assumed in locked design 0a rather than against it: the failure is a miscalibrated marginal, not a leak between the two parts of the state. One of the 16, `a11-repeated-097`, was decided at margin 0.0 — a tie broken by `ACTIONS` order, not by cost. | Run analysis — LLM run, n=100 | `results/run.json`, 16 rows where `labels.needs_human` is true and `decisions.cost_aware.action` is not an escalation. Realised costs are 3, 4 and 10, not uniform. |
| F5 | **Two of the five actions are never selected under LLM beliefs, and only one of them is dead by design.** Over the reported run the cost-aware policy chooses `escalate_notify` 43 times, `answer` 30 and `hold` 27. `escalate_pause` is absent by design (F1). `ask` is not: it is squeezed from both sides, with `hold` cheaper whenever holding is right and `escalate_notify` cheaper whenever a human is needed, so it is never the argmin at any belief the model actually produced. It is not dead in principle — under keyword beliefs the same cost matrix selects `ask` on 4 cases — so the action's viability is a property of the belief distribution, not of the cost matrix alone. This answers research-file question 2 empirically, and it undercuts the reasoning in decision 37, which set `ask` = 2 specifically to stop it becoming a dead action. | Run analysis — LLM run vs dry run | `results/run.json` action counts (43/30/27, no `ask`, no `escalate_pause`); `results/run_DRY.json` selects `ask` on 4 cases |
| F6 | **The hard constraint's value scales inversely with belief quality.** `no_direct_answer` binds — removes `answer` in a case where `answer` would otherwise have been selected — on 4 of the 8 restricted cases under keyword beliefs and 0 of 8 under LLM beliefs for the cost-aware policy. For the uniform baseline it is 7 of 8 versus 1 of 8. The constraint does the most work exactly when the belief is worst and almost none when the belief is good. It should be reported as insurance whose expected payout falls as the model improves, not as a contributing component of the headline result. | Run analysis — LLM run vs dry run | `decisions.*.constraint_bound` in `results/run.json` (0 and 1) and `results/run_DRY.json` (4 and 7), over the 8 cases carrying `no_direct_answer` |
| F7 | **A batched high-cost signal was dropped because the turn, not the message, was the unit of decision.** A callback request arrived in the same turn as a routine information request. The agent acted on the routine message and dropped the callback, which was the only one carrying a `needs_human` signal — a rare, high-cost signal averaged out by common, low-cost traffic because the two messages were treated as a single turn. Distinct from the synthetic misses: those are belief-scoring errors on a single message, whereas this is a turn-boundary error in which the important message never got its own belief evaluation. Motivates a per-message critical-trigger scan before acting on a turn as a whole. | Live run — single incident | Live run, not the synthetic set — no repo artifact. Every case in `data/cases.json` has `message` as a single string and `context` as `{turn_index, repeat_count}`, so the harness cannot currently produce this failure. |

---

## Failure analysis — kept for the paper

**Context-token leakage into a keyword belief.** Rendering the conversation
context block into *every* provider let the keyword fallback score my own
generated prose. `"already received"` contains `"ready"`, a hot keyword, so a
template opener with no buying signal scored hot = 0.545 instead of 0.286.

Worth citing because of the shape, not the size: it pushed cold leads toward hot
(the direction that *suppresses* escalation), the resulting belief was a valid
distribution with a normal provenance record so nothing downstream could detect
it, and it fired only on the archetypes that carry context — so it would have
biased one subgroup rather than adding uniform noise.

Caught by a test, not by reading the code. Fixed by decision 30. Full note in
`src/belief.py` above `BeliefSourceError`; regression test is
`tests/test_context.py::test_context_does_not_change_the_keyword_belief`.

---

## Environment note

The `.env` holding the real OpenAI and Gemini keys exists on KK's machine and is
gitignored, so it is correctly **not** present in the build container. Any step
that needs a live LLM call has to run locally; the container can only exercise
offline paths.
