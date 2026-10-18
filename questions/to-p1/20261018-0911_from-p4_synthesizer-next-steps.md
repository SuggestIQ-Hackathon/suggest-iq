---
from: p4
to: p1
type: FINDING
status: open
related_todo: P1-06
created: 2026-10-18 10:30
---
# Next steps and KPIs repeat the raw rationale, and low-confidence parts say "Execute"

## Question
In the app the synthesizer's next steps read: "Execute route processor: Catalyst 8200 route processor family (Score 0.17 = similarity 0.17, symptom match 0.00, ... Catalog entry is unverified; confidence was reduced.)". Problems:
1. The step embeds `rec.rationale` verbatim (a scoring formula when it comes from P2). Suggest a short action sentence from `title` and `category`, with the rationale left to the recommendation card.
2. "Execute ..." is used even when `confidence_score` is 0.17 and the item is unverified. Suggest "Investigate/verify" below a threshold (e.g. < 0.5) and "Order/replace" only when the status is CONFIRMED_FAULT or the confidence is high.
3. KPIs include "Estimated impact: prioritizes a compatible candidate for investigation." copied from `estimated_impact`; skip KPI candidates that are generic/boilerplate or fall back to the domain KPIs.
4. The CLI header still says "SPARTAN CONSULT AI"; the product is Suggest IQ.

## Proposed answer / workaround I am using meanwhile
None needed; the UI shows steps as given.

## Answer
