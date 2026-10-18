---
from: p4
to: p1
type: FINDING
status: open
related_todo: P1-02
created: 2026-10-17 16:00
---
# Router misses 3 of the 37 benchmark queries (real finding, not a mock artefact)

## Question
`make eval` (routing is real, agents are mock) gives 91.9% exact-set routing accuracy. Misses:
- Q29 "How many people were undernourished globally according to the FAO report?" expected `corporate_responsibility`, got `technology` (no matching keyword: "undernourished", "FAO", "undernourishment").
- Q32 "Can Google Cloud managed services reduce our router maintenance burden, and what cloud risks does Alphabet disclose?" expected `technology, sec`, got `technology` (SEC signal missing for "Alphabet disclose", "risks").
- Q33 "How could sensor networks reduce food waste, and which Cisco hardware would support them?" expected `corporate_responsibility, technology`, got `technology` ("food waste" not treated as a CSR signal).
Also: out-of-scope probes (`p4_eval_ui/evaluation/edge_cases.json`) currently pass (confidence below 0.5).

## Proposed answer / workaround I am using meanwhile
Add keyword signals (FAO, undernourish*, food waste, malnutrition synonyms; Alphabet/Google + "disclose"/"risks"/"10-K" for SEC). Nothing blocks P4; the benchmark simply keeps reporting these.

## Answer
