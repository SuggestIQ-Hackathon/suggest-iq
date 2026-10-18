---
from: p4
to: p2
type: FINDING
status: open
related_todo: P2-03
created: 2026-10-18 08:55
---
# Real benchmark run: three issues in Technology/Clinical retrieval and gating

## Question
`REAL_DOMAINS=all make eval` on `develop` + P4 (37 queries, offline hash embeddings). Technology retrieval hit-rate@5 is 77%, Clinical 9%. Details:

1. **`model` metadata is `None` for most Cisco datasheets.** `TechKB` only sets `model` for files whose names it recognises (`catalyst-8000v-...`, `nb-06-cat8200-...`). `datasheet-c78-744088.pdf` (Catalyst 8300), `data_sheet-c78-732542.pdf` (ISR 4000) and `datasheet-c78-731632.pdf` (ASR 1000) get `model: None`. Effect: a query naming "Catalyst 8300" or "ISR" filters to nothing, `retrieve()` returns `[]`, and the agent answers `INFORMATION_REQUEST` with missing "Relevant Cisco or Google/GCP source evidence" (Q03, Q05; Q36 even with complete diagnostics). Proposed fix: map those three file names to their models (they are in `data/raw/MANIFEST.json`/DataSource-Cisco.txt) and fall back to unfiltered search when a model filter returns nothing.
2. **No Agilent corpus.** Every Agilent product page returned HTTP 403 on this machine (manifest: `failed: HTTPError 403`), so Q06-Q08, Q31, Q37 retrieve nothing relevant (`missing: Relevant local Agilent product evidence`). Needs another source (browser-saved pages or PDFs placed in `resources/`) or an explicit documented gap.
3. **Selection/spec questions are treated as faults.** Q03 ("what IPsec throughput and memory options") and Q06-Q08 ("which Agilent instrument...") describe no failure but return `INFORMATION_REQUEST`. The diagnostics gate should apply to troubleshooting, not to datasheet or selection questions.
Also: Q35 (complete diagnostics, failed power supply) now returns `HYPOTHESIS` with `CISCO-C8200-LICENSE` ranked above `CISCO-C8200-POWER-SUPPLY`; the power supply should rank first (NDCG@3 0.58).

## Proposed answer / workaround I am using meanwhile
None needed; the benchmark keeps reporting these. Full list: `p4_eval_ui/presentation/eval_findings.md`. After a fix run `REAL_DOMAINS=all make eval`.

## Answer
