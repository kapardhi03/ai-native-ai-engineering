# Policy run — results

Generated 2026-08-19T18:39:34.564339+00:00 · provider `openai=100` · 100 cases

## DEV — n=50

| policy | total cost | mean | missed esc. | precision | recall | violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **cost_aware** | 86 | 1.72 | 8 | 0.5652 | 0.619 | 0 |
| **uniform_baseline** | 129 | 2.58 | 12 | 0.75 | 0.4286 | 0 |
| always_answer | 170 | 3.4 | 17 | 1.0 | 0.1905 | 0 |
| always_notify | 87 | 1.74 | 0 | 0.42 | 1.0 | 0 |
| always_ask | 142 | 2.84 | 21 | None | 0.0 | 0 |

Disagreements: **23** (46%) · cost delta (cost-aware − baseline): **-43**

ECE `needs_human`: **0.168** · ECE readiness (argmax): 0.096

## TEST — n=50

| policy | total cost | mean | missed esc. | precision | recall | violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **cost_aware** | 86 | 1.72 | 8 | 0.65 | 0.619 | 0 |
| **uniform_baseline** | 129 | 2.58 | 12 | 0.75 | 0.4286 | 0 |
| always_answer | 170 | 3.4 | 17 | 1.0 | 0.1905 | 0 |
| always_notify | 87 | 1.74 | 0 | 0.42 | 1.0 | 0 |
| always_ask | 142 | 2.84 | 21 | None | 0.0 | 0 |

Disagreements: **23** (46%) · cost delta (cost-aware − baseline): **-43**

ECE `needs_human`: **0.184** · ECE readiness (argmax): 0.128

## ALL — n=100

| policy | total cost | mean | missed esc. | precision | recall | violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **cost_aware** | 172 | 1.72 | 16 | 0.6047 | 0.619 | 0 |
| **uniform_baseline** | 258 | 2.58 | 24 | 0.75 | 0.4286 | 0 |
| always_answer | 340 | 3.4 | 34 | 1.0 | 0.1905 | 0 |
| always_notify | 174 | 1.74 | 0 | 0.42 | 1.0 | 0 |
| always_ask | 284 | 2.84 | 42 | None | 0.0 | 0 |

Disagreements: **46** (46%) · cost delta (cost-aware − baseline): **-86**

ECE `needs_human`: **0.142** · ECE readiness (argmax): 0.11
