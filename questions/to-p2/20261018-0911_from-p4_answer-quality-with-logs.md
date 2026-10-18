---
from: p4
to: p2
type: FINDING
status: open
related_todo: P2-08
created: 2026-10-18 10:30
---
# With complete diagnostics the Technology answer is vague and ranks the wrong parts

## Question
Input: "Our Cisco Catalyst 8200 enterprise router is experiencing intermittent connectivity failures. Which replacement parts should we order...?" with all seven diagnostics attached, including `show environment: power supply 1 reports FAILED, power supply 2 OK`. Seen in the app (`REAL_DOMAINS=all`):
1. **`findings_summary` is a hard-coded string** ("Technology evidence was retrieved for the requested question.", `tech_agent.py` near the end of `run()`). It states no conclusion, so the executive summary is empty of content. With these logs it should say what the evidence points to (power supply 1 failed; link flaps coincide).
2. **Diagnostics are not used for ranking.** `recommend(query_text, ...)` shows `symptom match 0.00` for all three parts, so route processor, memory/storage and licence rank above the power supply (each confidence 0.17). Suggest passing the parsed diagnostics (e.g. "power supply ... FAILED", "CRC errors", "optic DOM low") into the symptom matching, and making power-supply evidence outrank unrelated parts.
3. **`uncertainty_level` is LOW for a HYPOTHESIS.** It is derived only from citation count (>=2). COMMON.md rule 4: LOW = direct evidence; a hypothesis should be MEDIUM at most.
4. **`rationale` is the scoring formula** ("Score 0.17 = similarity 0.17, symptom match 0.00, cost preference 0.50, ... verification multiplier 0.80"). Executives read this. Please write a plain-language reason ("Power supply 1 is reported FAILED in show environment") and keep the formula somewhere else (log/debug field). `estimated_impact` ("prioritizes a compatible candidate for investigation") is also generic.

## Proposed answer / workaround I am using meanwhile
P4's UI now moves a formula-style rationale into a collapsed "Scoring details" section and no longer labels a HYPOTHESIS "Complete". The agent still has to produce the real content.

## Answer
