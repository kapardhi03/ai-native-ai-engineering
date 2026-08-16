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

<!-- Only accounts I have opened and checked. "Active" and the keep/remove reason
     reflect what I found when I opened the profile, not a pre-made list. Dormant
     or off-topic accounts are kept in the table with the reason, so the removal
     is auditable rather than silent. -->

| Account | Handle | Checked on | Active | Relevant to my problem | Keep or remove, and why |
| --- | --- | --- | --- | --- | --- |
| Hussein Mozannar | @HsseinMzannar | 14/08/2026 | Yes | Yes | Keep. Learning-to-defer author, now at MS Research; best-matched researcher and most plausibly engageable of the academic set. Follow + attempt one substantive reply. |
| Jerry Liu | @jerryjliu0 | 14/08/2026 | Yes | Partial | Keep (low expectation). LlamaIndex co-founder; relevant to applied agents/orchestration, but posts product/ecosystem content, not deferral theory. Follow for pulse, not for topical debate. |
| Yarin Gal | @yaringal | 14/08/2026 | Low (last ~Jul) | Yes (citation) | Keep as citation-follow. Bayesian deep learning / uncertainty; only mildly active, so treat as read-the-work, not a discussion target. |
| David Sontag | @david_sontag / @layerhealth | 14/08/2026 | Yes | No (current content) | Remove for discussion. Real L2D pedigree but pivoted to health (Layer Health CEO); current feed is medical, not my problem. Cite his past work if used; don't expect topical engagement. |
| Gomez-Rodriguez | @autreche | 14/08/2026 | Very low | Yes (work) | Remove for discussion, keep for citation. Triage/deferral work is relevant; account rarely active, so no realistic discussion. |
| Nastaran Okati | @Nastaranokt | 14/08/2026 | No (no content) | Yes (work) | Remove for discussion. Paper verified real on Scholar; X account has no content, so it can't yield a discussion. Cite the paper, not the account. |
| Balaji Lakshminarayanan | @balajiln | 14/08/2026 | No (last 2022) | Yes (work) | Remove. Calibration/uncertainty work is relevant but account dormant since 2022. Read/cite only. |
## Five sources

<!-- Papers, articles, repos, or datasets. Fill a block in only after reading
     the source, not after finding it. -->

### Source 1

- Type: Paper (peer-reviewed, ML)
- Title: Consistent Estimators for Learning to Defer to an Expert (Mozannar & Sontag)
- Link: https://arxiv.org/pdf/2006.01862
- Why it matters here: Formal basis for treating "escalate to a human" as a costed decision, where the human is a second decision-maker with its own error and cost, not an automatic safe fallback.
- What I took from it: The framework that justifies pricing escalation as a real cost in my policy. I use it conceptually, not by implementing its joint surrogate loss, my project keeps an explicit belief and a myopic expected-cost rule rather than a jointly trained defer-classifier.
### Source 2

- Type: Paper (peer-reviewed, ML)
- Title: Predict Responsibly: Improving Fairness and Accuracy by Learning to Defer (Madras, Pitassi, Zemel)
- Link: https://arxiv.org/pdf/1711.06664
- Why it matters here: Frames rejection as a special case of deferral, and shows a fair model composed with a fair human can still yield an unfair system , relevant to my ethics/limitations, not my method.
- What I took from it: The system-level fairness point: even if each part is fair, escalation delays can fall unevenly (e.g. on non-standard or code-switched messages). I treat this as a limitations/ethics concern for a production deployment, not as a fairness objective I optimise in the Week 1 policy.

### Source 3

- Type: Paper (peer-reviewed, ML)
- Title: On Calibration of Modern Neural Networks (Guo, Pleiss, Sun, Weinberger)
- Link: https://arxiv.org/pdf/1706.04599
- Why it matters here: My myopic policy thresholds on a belief, so whether that belief's probabilities are calibrated is load-bearing. Source for ECE, reliability diagrams, and temperature scaling.
- What I took from it: That overconfidence would make automated actions look artificially cheap and suppress escalation, which is exactly my failure mode. I plan to measure ECE / plot a reliability diagram before trusting any threshold, and recalibrate if needed. Method depends on my belief source (LLM-derived), so it may be closer to Platt/isotonic than textbook temperature scaling. to be decided empirically.

### Source 4

- Type: Paper (peer-reviewed, ML)
- Title: Selective Classification for Deep Neural Networks (Geifman & El-Yaniv)
- Link: https://arxiv.org/pdf/1705.08500
- Why it matters here: Formal backbone for my "hold" and "escalate-on-low-confidence" actions as a reject option, and for reporting risk vs coverage instead of accuracy alone.
- What I took from it: (reword) A post-hoc rejection layer over a fixed belief source fits my design better than joint training, and softmax-response (max belief) is a cheap confidence signal for triggering escalation on low-confidence/OOD input. I report risk-coverage; the SGR formal guarantee is the principled version I approximate with empirical threshold tuning.
### Source 5

- Type: Paper (survey)
- Title: Planning and Acting in Partially Observable Stochastic Domains (Kaelbling, Littman & Cassandra)
- Link: https://people.smp.uq.edu.au/YoniNazarathy/Control4406_2014/resources/KaelblingLittmanCassandra1998.pdf
- Why it matters here: Grounds belief-as-sufficient-statistic and the intractability of exact POMDP planning, which is the justification for solving myopically rather than planning over belief space.
- What I took from it: The formal warrant for my scope: full belief-state planning is intractable, so a myopic one-step expected-cost policy is a defensible approximation. It also names the tension I care about — a strict myopic rule undervalues "ask a qualifying question," which is where VOI/EVSI comes in (implement vs. name as future work still open). I do not use RL or an RNN belief; my belief update is explicit.
<!-- Source 5 is provisional until verified. If it drops, the replacement is
     whichever VOI/EVSI or POMDP reference I actually read: search "Information
     Value Theory Howard 1966" or "expected value of sample information". Do not
     fill a block for a source I have not opened. -->

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
