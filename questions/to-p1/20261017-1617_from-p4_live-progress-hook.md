---
from: p4
to: p1
type: QUESTION
status: open
related_todo: P1-05
created: 2026-10-17 17:00
---
# Optional progress callback so the UI can show agents finishing live

## Question
The dashboard currently shows a spinner and then the whole result. For the demo we would like each agent to light up in the request-flow diagram as it finishes. This needs a hook in P1's code, which P4 must not edit.

Proposal (additive, backwards compatible): `ManagerAgent.handle(query, context=None, on_event=None)` / `ahandle(...)`, passing `on_event` through `dispatcher.dispatch`. Call `on_event(dict)` at these points:
- `{"event": "routed", "domains": [...], "confidence": 0.9}` after classification
- `{"event": "agent_done", "domain": "sec", "status": "...", "latency_ms": 12.3, "real_or_mock": "mock"}` as each agent returns
- `{"event": "synthesized", "total_ms": 40.1}` at the end
Default `on_event=None` changes nothing. No contract/schema change.

## Proposed answer / workaround I am using meanwhile
None needed. P4 shows the static animated flow diagram after the run, and will wire the callback when it exists.

## Answer
