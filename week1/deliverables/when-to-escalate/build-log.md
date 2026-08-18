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
| 0b | pre-build | Decision rule = myopic one-step minimum-expected-cost over {answer, ask, hold, escalate} | Locked at outset | Full belief-state planning is intractable, so a one-step rule is the defensible approximation (Kaelbling, Littman & Cassandra — Source 5 in `research-file.md`). | policy (not yet built) |
| 0c | pre-build | Wrong assertion is a **hard constraint**, not a priced term in the cost matrix | Locked at outset | *Reason not yet given — to be filled in by KK.* | policy (not yet built) |
| 0d | pre-build | Belief comes from a real LLM call, cached to JSON per case id | Locked at outset | Both policies must run over identical beliefs, so the non-deterministic call happens exactly once per case and is then frozen. | `src/belief.py` |
| 0e | pre-build | Baseline = same decision logic with a uniform cost matrix | Locked at outset | *Reason not yet given — to be filled in by KK.* | baseline (not yet built) |
| 0f | pre-build | Public boundary: no product name, no client data, no real prompts | Locked at outset | Everything stays at the general problem level. The prompt in `belief.py` is synthetic and written for this experiment. | all files |
| 1 | 2026-08-18 | `build-log.md` lives at `week1/deliverables/when-to-escalate/build-log.md`, **committed**, not gitignored | Approved | Sits alongside the other record files. Initially asked for it gitignored; reversed once it was clear the build runs in an ephemeral container, where a gitignored file dies with the container and the decision record would be lost entirely. | this file |
| 2 | 2026-08-18 | Log includes the pre-build locked design as rows `0a`–`0f` (Option B), not just decisions made during the build | Approved | "Clean and more readable, i.e. provides wider information." The log should stand alone for a reader who was not present for the locked design. | this file |
| 3 | 2026-08-18 | Belief must come from a real LLM call. API key supplied via `.env`, which is gitignored | Approved | *Reason not yet given — to be filled in by KK.* Consequence: the rule-based keyword fallback must not silently satisfy an experiment run. | `src/belief.py`, `.env` |
| 4 | 2026-08-18 | "Modular" means the **wider `src/` structure**, not the log's layout | Approved | Future integrations should be easy to drop in. Clarified after ambiguity in the original instruction. | `src/` |
| 5 | 2026-08-18 | Work proceeds one step at a time; no file is created or changed until that specific step is approved | Approved | Keeps every change traceable to an explicit decision instead of arriving in a batch. | process |
| 6 | 2026-08-18 | Rule-based fallback **kept**, but gated: `BELIEF_ALLOW_RULE_FALLBACK` in `.env`, and the provider that produced a belief is surfaced to callers | Approved | "Offline smoke tests keep working; a real run can't silently degrade." Deleting it would break offline runs; leaving it silent would void decision 3, since a run where both APIs fail would produce keyword beliefs that look identical to LLM beliefs in the cache. | `src/config.py`, `src/belief.py` |
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

---

## Open questions carried into the build

Not decisions yet. Listed so they are not lost between steps.

| # | Question | Status | Outcome |
| --- | --- | --- | --- |
| Q1 | Should the rule-based fallback be deleted, or kept behind a flag? | **Closed** | Kept, gated by `BELIEF_ALLOW_RULE_FALLBACK`. See decision 6. |
| Q2 | `.env` is inert — where does config loading live? | **Closed** | `src/config.py`, via `python-dotenv`. See decisions 7 and 10. |
| Q3 | `DEFAULT_CACHE_PATH` is relative to the working directory. | **Closed** | Read from `.env`, resolved against the repo root. See decision 8. |
| Q4 | Reasons for rows `0c`, `0e`, `3`, `10`, `13`, `14`, `17`, `18` and `20` are still blank. | Open | Fill in above. |
| Q5 | `belief.py` does not yet use `config.py`. | **Closed** | Rewired. See decision 12. |
| Q6 | Is the belief calibrated enough to threshold on (research-file Q1)? Cannot be answered while any cached belief may be keyword-derived — ECE over a mixed cache is not LLM calibration. | Open | Now checkable via `cache_provenance()`. Needs a real strict run, which must happen on KK's machine — the build container has no keys. |
| Q7 | Providers still live inside `belief.py`. | **Closed** | Extracted to `src/providers/`. See decision 16. |
| Q8 | No test file exists. | **Closed** | 208 tests under `tests/`. See decision 19. |
| Q9 | `BELIEF_ALLOW_RULE_FALLBACK` still defaults to **true**, so an unconfigured run can produce a mixed cache. Should strict be the default, given decision 15? | Open | Proposed, not yet decided. |
| Q10 | No synthetic case set exists yet in `data/`, so nothing has been run against a real LLM. Decision 15 is enforced but never exercised against a live API. | Open | Needs a run on KK's machine. |

---

## Environment note

The `.env` holding the real OpenAI and Gemini keys exists on KK's machine and is
gitignored, so it is correctly **not** present in the build container. Any step
that needs a live LLM call has to run locally; the container can only exercise
offline paths.
