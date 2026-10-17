# Demo script (3-5 minutes)

Setup before recording: `REAL_DOMAINS=all` (when integrated), `LLM_MODE=live` if keys exist, `make eval` already run, `streamlit run p4_eval_ui/ui/dashboard.py`. Use the sidebar example buttons; do not type live.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:25 | Slide: architecture | "One manager agent routes a customer problem to four specialist agents and returns a consulting recommendation with evidence." |
| 0:25-1:25 | **Consult** tab: click *Brief example: Cisco router*, run | "With no logs the system does not guess. It asks for the exact diagnostics and gives ranked hypotheses; no parts are recommended yet." Point at the yellow banner and the confidence bars. |
| 1:25-2:05 | Click *Add diagnostics example*, run again | "With a failed power supply in the logs it now ranks compatible parts, each with a confidence bucket and sources." Open **Evidence**: show a citation with page and snippet. |
| 2:05-2:30 | Sidebar: SEC example | "Same architecture, SEC question: risk factors grounded in the filing, cited by page." |
| 2:30-2:50 | Sidebar: food-security example | "FAO report question, answered only from the cited report year." |
| 2:50-3:40 | Sidebar: cross-domain example (tech + SEC + CSR) | "Three agents ran in parallel." Open **Agent trace** (routing decision, per-agent latency, real vs mock), then show the cross-domain synthesis trade-off, next steps and KPIs. |
| 3:40-4:30 | **Evaluation** tab | Read the scorecard: routing accuracy, retrieval hit-rate, recommendation NDCG, faithfulness, diagnostic-gate compliance. Show the confusion matrix and calibration table. Be candid about weak spots. |
| 4:30-5:00 | Slide: business value + limitations | "Next steps, why, and how impact is measured. Known gaps: no IBM docs, no company ESG reports." |
