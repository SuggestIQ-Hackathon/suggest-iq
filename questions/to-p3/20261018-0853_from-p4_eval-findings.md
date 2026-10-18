---
from: p4
to: p3
type: FINDING
status: open
related_todo: P3-05
created: 2026-10-18 08:55
---
# Real benchmark run: SEC and CSR retrieve well; faithfulness is limited by short citation snippets

## Question
`REAL_DOMAINS=all make eval` on `develop` + P4: **SEC retrieval hit-rate@5 = 100%, CSR = 90%**. Nice.
One thing to look at: **faithfulness** (does the cited snippet support each statement?) is only ~0.2 for SEC/CSR even though the summaries are extractive. Cause: `findings_summary` is built from the full retrieved chunk (about 800 characters) but `hits_to_citations` truncates `Citation.snippet` to 300 characters, so most of what the summary says is not visible in the cited snippet (e.g. Q11 first sentence overlaps 0.86, later sentences 0.2-0.3). By COMMON.md rule 1 the snippet should be the text that supports the claim.
Proposal (your call): cite the sentence(s) actually used in the summary, or raise the snippet length for SEC/CSR (e.g. `hits_to_citations(hits, max_snippet=900)`).
Also: strategy gold judgments for Q20, Q22, Q24 now use your real `STRAT-*` ids (P4 judged them from the question, not from your output). Current NDCG@3 on those is low: Q20 returns `STRAT-PARTNER-DUE-DILIGENCE`, `STRAT-SCENARIO-PLANNING`, `STRAT-COLD-CHAIN` while the question asks for technology investments (precision agriculture, cold chain, early-warning dashboards); Q22 returns only `SEC-CISCO-*` items and no sustainability action.

## Proposed answer / workaround I am using meanwhile
None needed. Details: `p4_eval_ui/presentation/eval_findings.md`.

## Answer
