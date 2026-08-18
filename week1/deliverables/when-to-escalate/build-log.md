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

---

## Open questions carried into the build

Not decisions yet. Listed so they are not lost between steps.

| # | Question | Blocking? | Where it lands |
| --- | --- | --- | --- |
| Q1 | Should the rule-based fallback be deleted outright, or kept behind a flag that defaults to off and raises during experiment runs? | Blocks the restructure | Decision row, next step |
| Q2 | `.env` is inert today — `belief.py` has no `dotenv` import and no `os.environ` read. Where does config loading live once the structure is modular? | Blocks real LLM calls | Decision row, next step |
| Q3 | `DEFAULT_CACHE_PATH` is relative to the working directory, so running from the repo root and from `when-to-escalate/` write different caches. Anchor it to the module, the repo root, or `.env`? | Blocks the "identical beliefs" guarantee | Decision row, next step |
| Q4 | Reasons for rows `0c`, `0e`, and `3` are still blank. | Not blocking | Fill in above |

---

## Environment note

The `.env` holding the real OpenAI and Gemini keys exists on KK's machine and is
gitignored, so it is correctly **not** present in the build container. Any step
that needs a live LLM call has to run locally; the container can only exercise
offline paths.
