# When to Escalate - Project

This folder holds a full week's project: the research file, the record of public
discussions, the agent and probability-model decision records, the synthetic test
harness and its results, the AI review record, the LaTeX preprint, and the two
social posts.

## Paper

**When to Escalate: A Cost-Aware Belief Policy for Conversational Agents Under
Hidden Intent**

## Problem

The agent observes an inbound message from a sales lead. It must select one action
from {`answer`, `ask`, `hold`, `escalate_notify`, `escalate_pause`} because the
lead's true intent and buying-readiness are not known. `ask` is a qualifying
question rather than an answer; `escalate_notify` tells a human while the
conversation continues; `escalate_pause` stops the agent and hands over. The two
escalations are separate actions because they carry different costs (build
decision 25, superseding the original four-action set).

The agent holds a belief over the lead's hidden intent and readiness and chooses
the action with the lowest expected cost, then is compared against a baseline. The
problem is framed as a POMDP but solved with a myopic (one-step) expected-cost
policy over the belief, not full belief-state planning.

## Repository layout

- `research-file.md` — technical terms, search queries, verified communities and
  accounts, sources, and open questions.
- `discussion-record.md` — public-discussion log and the design change (if any)
  each useful reply produced.
- `review-record.md` — AI review comments, with accept/reject and reason for each.
- `decisions/probability-decision-record.md` — one worked belief-update-to-action
  record for a single case.
- `paper/` — LaTeX source, references, figures, and the compiled preprint.
- `src/` — agent, belief update, cost model, and policy.
- `data/` — the synthetic conversation set used for testing.
- `experiments/` — the test harness.
- `results/` — predictions, actions, metrics, and figures from a run.
- `social/` — the LinkedIn post and the X thread.

## How to reproduce the test

<!-- To fill in once the harness exists. Must cover: environment and dependencies;
     how the synthetic conversation set in data/ is produced (script + seed, so it
     regenerates identically); the exact command that runs the harness in
     experiments/; where output lands in results/; and how to check a run against
     the numbers reported in the paper. Do not write these steps until they are
     real and have been run. -->

## AI-use statement

<!-- To fill in. State which AI tools were used and for what (e.g. preparing
     research terms and queries, drafting and repairing code, LaTeX assistance,
     review passes), and affirm that all content was verified by me and that no
     fabricated conversations, untested results, or unread references are included. -->