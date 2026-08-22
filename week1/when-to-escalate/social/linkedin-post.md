Published: https://www.linkedin.com/posts/kapardhi-kannekanti_when-to-escalate-a-cost-aware-belief-policy-ugcPost-7496717815702462464-7Ila/

I spent this week building a small agent for a problem I actually hit in production: a lead messages you, and you can't tell if they're a real buyer, a competitor fishing for pricing, or a bot. Answer them, ask a qualifying question, hold, or escalate to a human? Every wrong choice costs something different, and most agents treat those costs as equal. This one doesn't.
 
The approach: instead of one confidence score, the agent holds a two-part belief, a readiness distribution (hot/warm/cold) and a separate needs-human probability, then picks the action with the lowest expected cost under a matrix where a missed escalation is priced far above a needless one. A false claim on legal or land documents isn't priced at all, it's a hard constraint the policy can't cross.
 
Then I spent most of the week trying to break my own result, which is the part worth sharing:
 
The cost-aware policy beats the cost-blind one, but the cost-blind baseline turned out to be nothing more than a 0.5 threshold in disguise. So part of that "win" is less than it looks, and the writeup says so.
 
Against an always-escalate policy, it doesn't win on cost at all. What it buys is human load, the same expected cost while escalating 43 conversations out of 100 instead of all 100.
 
Every missed escalation traced to one under-confident marginal. But recalibrating it only halved the misses. The rest survive because the model emits probabilities at one decimal place, and 35% of cases sit pinned at exactly 0.2, just under the threshold. That quantization floor, not the recalibration, was the real finding.
 
And two of the five actions were selected zero times in 100 cases. The five-action design is a three-action policy in practice.
 
None of the numbers transfer to a live inbox, it's synthetic data, and I'm clear about that throughout.
 
I learned more from what didn't hold than from what did. If you've run message agents or any human-in-the-loop system in production: where does a myopic one-step cost policy break in ways a synthetic test can't show? 


