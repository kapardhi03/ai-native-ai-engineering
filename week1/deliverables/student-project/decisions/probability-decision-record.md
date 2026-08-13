# Probability Decision Record

<!-- Fill the right-hand column only. Keep each entry specific to this project:
     name the actual signals, the actual hidden states, the actual action set,
     and real costs with units. "TBD" is not an entry. -->

| Element | My entry |
| --- | --- |
| Evidence |  |
| Hidden states |  |
| Beliefs |  |
| Event |  |
| Actions |  |
| Costs |  |
| Policy |  |
| Decision |  |
| Audit data |  |

---

## Bayesian update

> **The hidden-state probabilities must sum to 100%.** Check this at the prior
> step and again at the posterior step. If they do not sum to 100%, the model is
> wrong and nothing downstream of it can be trusted.

### 1 Prior

<!-- Belief over the hidden states before the new message arrives, and where
     that prior comes from. Must sum to 100%. -->

### 2 New evidence

<!-- The specific observation from the inbound message. One observation. -->

### 3 Likelihoods

<!-- P(evidence | each hidden state). These do not sum to 100% across states,
     and that is correct — do not normalise them here. -->

### 4 Posterior

<!-- The updated belief after the evidence, with the arithmetic shown. Must sum
     to 100%. -->

### 5 Compare to threshold

<!-- The threshold, where it came from, and how the posterior sits against it. -->

### 6 New action

<!-- The single action the policy selects, and what would have had to be
     different for it to select another one. -->
