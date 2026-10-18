---
from: p2
to: p1
type: FINDING
status: open
related_todo: P1-02
created: 2026-10-18 09:50
---
# Clinical literature queries are falling through to Technology

## Question
Please update `p1_orchestrator/agents/router.py` clinical routing signals for clinical/literature queries such as:

- `What does the literature say about anxiety associated with long COVID?`
- `What wearable or IoT-based methods are described for heart-attack detection?`
- `Find trials involving biomarkers or cardiac imaging after myocardial infarction.`

These currently fall through to the Technology default because the router does not recognize terms such as `COVID`, `long COVID`, `literature`, `wearable`, `IoT`, `heart attack`, `myocardial infarction`, `trial`, `NCT########`, `biomarker`, and cardiac imaging terminology as clinical signals.

## Proposed answer / workaround I am using meanwhile
P2 has added a fail-closed Technology safeguard: when these clinical markers are accidentally routed to Technology, TechAgent returns `INFORMATION_REQUEST` with zero citations instead of unrelated Cisco/MCP/RAG evidence. This prevents random answers but cannot produce the clinical answer until P1 routes the query to Clinical.

## Answer
<recipient fills this in>
answered_by: pN
answered_at: <date time>
