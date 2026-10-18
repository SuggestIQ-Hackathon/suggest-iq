---
from: p4
to: p1
type: FINDING
status: open
related_todo: P1-06
created: 2026-10-18 12:00
---
# A vague question ("sjsu") produces an empty-but-confident report

## Question
With the live router, the question "sjsu" returned `domains: []` (router confidence 0.9). The synthesizer still produced a full `ConsultingReport`:
- executive summary = only the canned line "A prioritized action plan and measurable risk-mitigation framework are detailed below ..."
- next steps = "Conduct comprehensive operational review and baseline validation." (generic filler)
- `measuring_impact_kpis` = the same KPI string three times (the `while len(kpis) < 3` padding loop appends the identical default)
- audit trace says "Your question went to no agent"

Proposals (your call):
1. Router: never return an empty domain list silently. Either return a clarification (e.g. `RoutingDecision.clarification` text, additive optional field) or low `confidence` so callers can tell, and do not run the synthesizer on zero domains.
2. Synthesizer: when there are no domain responses, return a report whose summary says no specialist matched; skip the canned closing sentence, generic next steps and KPIs. Pad KPIs with distinct items only (dedupe).
3. Out-of-scope questions that DO match a domain by keyword (e.g. "best pizza place in San Jose" -> technology) still get a confident answer with irrelevant citations; a relevance threshold on retrieval (min score) would let agents abstain.

## Proposed answer / workaround I am using meanwhile
P4's UI now detects `detected_domains == []` and shows a helpful "We couldn't tell what you want to decide" view (areas covered, rephrase box, example chips), and de-duplicates KPI chips. No contract change needed from P1 for that.

## Answer
