# Research File

## Problem statement

The agent observes an inbound message from a sales lead. It must
select one action from {answer, ask a qualifying question, hold, escalate to a
human} because the lead's true intent and buying-readiness are not known.

---

## Project objective

Design and test a decision policy for a conversational sales agent that must choose, on each inbound message, whether to answer, ask a qualifying question, hold, or escalate to a human, when the lead's true intent and buying-readiness cannot be observed. The agent maintains an explicit belief over that hidden state and selects the action with the lowest expected cost, where the costs reflect real business damage rather than what is easy to detect. The goal is to compare this cost-aware policy against a baseline and show where reasoning about the cost of each mistake changes the decision.

## Technical terms

| Term | My definition |
| --- | --- |
| Bayes decision rule (minimum-expected-cost action) | Choose the action with the lowest expected cost under the current belief over hidden states. |
| Loss / cost matrix | Table of costs for each (action, true-state) pair; asymmetric when some errors cost far more than others. |
| Cost-sensitive classification | Optimizing expected cost rather than raw error rate, because misclassifications aren't equally expensive. |
| Reject option / abstention | Letting the agent decline to act (defer/hold) instead of forcing a decision when expected cost warrants. |
| Selective prediction / selective classification | Acting only on a subset of cases (coverage) and abstaining on the rest; trades coverage against risk. |
| Risk-coverage curve / AURC | Error (risk) plotted against fraction of cases acted on (coverage); AURC is the area under it, lower is better. |
| Learning to defer (L2D) | Training the agent to choose between deciding itself or deferring to a human, modeling the human's own error and cost. |
| Learning to complement | Training the agent to be strong specifically where the human is weak, as a team, not standalone. |
| Human-AI deferral / triage / routing | Sending each case to whichever decision-maker (agent or human) has the lower expected cost. |
| POMDP | Sequential decision problem where the true state is hidden; the agent acts on noisy observations while maintaining a belief. |
| Belief state | Probability distribution over hidden states given everything observed so far; a sufficient statistic for choosing an action. |
| Belief update / Bayesian filtering | Revising the belief with new evidence via Bayes' rule (prior × likelihood → posterior). |
| Belief-state MDP | Recasting a POMDP as an MDP over beliefs; optimal in principle but generally intractable to solve exactly. |
| Myopic / one-step-lookahead policy | Pick the action minimizing *immediate* expected cost under the current belief, without planning over future belief changes. My chosen approach. |
| Value of information (VOI) / myopic VOI | Expected reduction in decision cost from gathering evidence before acting; myopic = evaluated only one step ahead. This is how "ask a qualifying question" earns its place. |
| EVSI (expected value of sample information) | VOI for one specific piece of evidence, e.g. the answer to a single qualifying question. |
| Optimal stopping | Deciding when to stop waiting/gathering versus act; the conceptual home of my "hold" action. |
| Probability calibration | Whether predicted probabilities match reality: a stated 70% should be right about 70% of the time. |
| Reliability diagram | Predicted probability vs observed frequency; the diagonal is perfect calibration. |
| ECE / MCE | Expected / Maximum Calibration Error: average / worst gap between confidence and accuracy across probability bins. |
| Proper scoring rule (Brier, log loss) | Scoring rule minimized only by reporting true probabilities; rewards calibration and sharpness together. |
| Sharpness vs calibration | Sharpness = how confident/concentrated predictions are; calibration = whether those probabilities are correct. Want both. |
| Temperature / Platt scaling, isotonic regression | Post-hoc methods that remap raw model scores into calibrated probabilities. |
| Verbalized / elicited confidence | Confidence a model states in words or numbers rather than derived from logits; often poorly calibrated in RLHF'd LLMs. |
| Lead qualification / BANT / MEDDIC | Sales frameworks (Budget, Authority, Need, Timeline, etc.) that are human-built proxies for my hidden buying-readiness state. |
| Buying-intent detection / lead scoring | Estimating conversion likelihood from observable signals. |
| Escalation / human handoff | Transferring a case from the automated agent to a human. |
| SLA / response-time budget | Expected maximum response time; what makes "hold" costly and makes the problem genuinely sequential. |
| Deflection rate | Support-side metric: fraction of cases resolved without a human. |

## Search queries

Deferral / reject option (core academic)

learning to defer to an expert
consistent surrogate loss learning to reject
classification with a reject option cost
learning to complement human
human-AI deferral calibration

Selective prediction / abstention

selective classification risk coverage
selective prediction deep learning coverage
abstention cost-sensitive threshold

POMDP / myopic VOI

myopic value of information POMDP
belief state one-step lookahead policy
value of information active sensing agent
expected value of sample information decision

Cost-sensitive decision theory

cost-sensitive classification loss matrix
Bayes minimum risk decision threshold asymmetric cost

LLM confidence / calibration (your belief source)

LLM confidence calibration overconfident
verbalized confidence language model calibration
selective prediction large language models

Applied human-AI handoff (practitioner + applied research)

chatbot escalation to human policy
when should an AI agent defer to a human
LLM agent confidence-based escalation
customer support automation deflection escalation tradeoff

Sales/ops framing (for the cost side)

lead qualification model cost of missed lead
sales lead routing human vs automation cost

## Verified Reddit communities

| Community | Checked on | Active | Relevant | Keep or remove, and why |
| --- | --- | --- | --- | --- |
| r/reinforcementlearning | 14/08/26| Yes | Yes | Keep. Active, and found a poster with my exact structure (hidden state, noisy signals, asymmetric escalation cost, POMDP-vs-heuristic doubt) in a medical domain. Strong venue for the myopic-vs-planning question and for a completed 2+ reply discussion. |
| r/sales | 14/08/26| Yes | Yes | Keep. Active with decent replies. Best venue for the error-cost reality (over-escalate vs mis-answer a hot lead) and whether a qualifying question backfires. Frame in sales language, watch anti-self-promo. |
| r/LocalLLaMA | 14/08/26| Yes | Yes (LLM-only) | Keep. Very active. On-topic only for LLM-confidence/calibration questions; code not allowed, so keep posts conceptual/applied. My venue for the "is elicited LLM confidence trustworthy enough to act on" thread. |
| r/AI_Agents | 14/08/26| Yes | Yes | Keep. Already joined and posted. Continue that thread as replies come in to hit the 2+ reply bar. Still need to judge whether replies are substantive humans vs promotional noise. |
| r/LanguageTechnology | 14/08/26| Yes | Yes | Keep (secondary). Rules align, active, but replies are thin. Use for one targeted intent-as-hidden-state post; don't rely on it for a completed discussion. |
| r/AskStatistics | 14/08/26| Yes | Partial | Keep only if reframed. Bans AI questions, but calibration / decision-threshold / proper-scoring questions are on-topic in pure stats language (predicted probabilities, loss matrix, threshold). No LLM/agent framing. |
| r/MachineLearning | 14/08/26| Yes | Partial | Deprioritize. Redirects Q&A elsewhere and reads paper/news-curated; felt beginner-heavy for me. Not for asking. Possible later home for a results/preprint post only. |
| r/datascience | 14/08/26| Low (for me) | Partial | Remove / deprioritize. I found it quiet with low activity, so it fails the reply test. r/sales covers the cost-intuition side better. |

## X accounts

| Account | Why I followed it | What it posts about |
| --- | --- | --- |
|  |  |  |

## Five sources

<!-- Papers, articles, repos, or datasets. Fill a block in only after reading
     the source, not after finding it. -->

### Source 1

- Type:
- Title:
- Link:
- Why it matters here:
- What I took from it:

### Source 2

- Type:
- Title:
- Link:
- Why it matters here:
- What I took from it:

### Source 3

- Type:
- Title:
- Link:
- Why it matters here:
- What I took from it:

### Source 4

- Type:
- Title:
- Link:
- Why it matters here:
- What I took from it:

### Source 5

- Type:
- Title:
- Link:
- Why it matters here:
- What I took from it:

## Questions to answer

<!-- Questions that can actually be closed by the end of the week, and how I
     would know each one is closed. -->

| # | Question | How I will know it is answered |
| --- | --- | --- |
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |

## AI prompts and important AI errors

### Prompts used

<!-- The prompt text, the tool it went to, and what it was for. Keep the
     prompts that mattered, not every throwaway one. -->

### Important AI errors

<!-- Every case where an AI tool was confidently wrong. This section is
     evidence that the output was checked rather than trusted. -->

| Tool | What it claimed | How I caught it | What was actually true |
| --- | --- | --- | --- |
|  |  |  |  |
