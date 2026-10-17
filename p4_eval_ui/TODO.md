# P4 — Evaluation, Explainability & UI/Presentation — TODO

**Goal:** Prove the system works with numbers (routing, retrieval, recommendation relevance, response quality), make every answer explainable, and present it (Streamlit dashboard, slides, demo video).

Read first: `../COMMON.md`. Your folder: `p4_eval_ui/` only (+ you own edits to `core/fixtures/benchmark_queries.json` after kickoff).

## Inputs you consume
- `core/fixtures/benchmark_queries.json` (25 seed queries), `core/schemas.py`, `core/registry.py`.
- The Manager only via `core.registry.load_manager()`; agents' retrieval only via `agent.retrieve(query, k)` (through the manager's agents or `core.registry.get_agents()`). Never import `p1_*`, `p2_*`, `p3_*`.
- `ConsultingReport.audit_trace` keys (defined in `../p1_orchestrator/TODO.md` P1-07): `routing`, `agents`, `mode`, `started_at`, `total_ms`, `fallbacks_used`.
- Recommender catalogs (read-only, once they exist): `p2_tech_clinical/recommenders/catalog/*.json`, `p3_sec_csr/recommenders/strategy_catalog.json` — for `item_id`s only.

## Outputs you must produce
| File | Contract |
|---|---|
| `p4_eval_ui/evaluation/metrics.py` | exactly the 4 functions in `COMMON.md` section 3 (pure, no I/O) |
| `p4_eval_ui/evaluation/benchmark.py` | `run_benchmark(manager, queries_path=None, k=5) -> dict` + CLI (`python -m p4_eval_ui.evaluation.benchmark`) writing `data/eval/scorecard.json`, `data/eval/per_query.csv` |
| `p4_eval_ui/evaluation/faithfulness.py` | `judge(report) -> dict` (claim-support score) |
| `p4_eval_ui/evaluation/explain.py` | `explain(report) -> ExplanationView` (pydantic defined here) |
| `p4_eval_ui/evaluation/gold_relevance.json` | graded relevance judgments for recommendations |
| `p4_eval_ui/ui/dashboard.py` | Streamlit app (`streamlit run p4_eval_ui/ui/dashboard.py`) |
| `p4_eval_ui/presentation/` | `slides.md` (source), final `slides.pdf`, `demo_script.md` |
| `p4_eval_ui/tests/` | your unit tests |

## Tasks (in order)

- [x] **P4-01 Benchmark and gold data.** *(DONE: fixture now has 37 queries: Q26-Q34 routing-only, Q35-Q37 with diagnostics `context`, optional `expected_status`; the out-of-scope probes live in `p4_eval_ui/evaluation/edge_cases.json` because the shared harness requires non-empty `expected_domains`; strategy gold uses `TODO-` placeholders until P3 publishes item_ids and the runner skips them.)* Review the 25 seed queries; improve wording and `expected_sources`/`expected_keywords` (keep ids; schema fixed in `COMMON.md` section 5). Create `gold_relevance.json`: `{ "<query id>": {"<item_id>": gain(0-3), ...} }` for >= 8 queries with recommendations (Q01, Q06, Q07, Q09, Q18, Q19, ... — use `item_id`s from the P2/P3 catalogs when they appear; until then use placeholders prefixed `TODO-` and replace them later). Add 10 extra routing-only queries (id `Q26+`) including ambiguous phrasing and one out-of-scope query. *Accept:* `make test-harness` still green (fixture validity test).
- [x] **P4-02 `metrics.py`.** Implement `routing_accuracy` (exact set match), `hit_rate_at_k`, `precision_at_k`, `ndcg_at_k` (graded gains, standard log2 discount, 0.0 when no gain found, 1.0 for ideal order). Add `confusion_matrix(predicted, gold, labels)` and `mean_reciprocal_rank`. *Accept:* `make test-p4` `test_routing_accuracy` and `test_ranking_metrics` pass; your own tests cover edge cases (empty lists, k > len).
- [x] **P4-03 Faithfulness** (`faithfulness.py`): for each recommendation/finding sentence, check support by its citation snippets. Live: `core.llm.complete_json` judge (supported / partially / unsupported). Mock fallback: lexical overlap of content words with the snippets (threshold documented). Returns `{score: 0-1, unsupported: [...]}`; report hallucination rate = 1 - score. *Accept:* unit test with a supported and an unsupported statement.
- [x] **P4-04 Benchmark runner** (`benchmark.py`). For each query: `manager.classify` -> routing accuracy (+ confusion matrix per domain); for the expected domains: `agent.retrieve(sub-query, k)` -> retrieval hit-rate@k where a hit = hit `source_doc` contains any `expected_sources` substring; `manager.handle` -> recommendation ranking vs `gold_relevance.json` (precision@3, NDCG@3) where gold exists; faithfulness via P4-03; latency and `uncertainty` distribution. Return dict with keys `routing_accuracy`, `retrieval_hit_rate`, `recommendation_ndcg_at_3`, `faithfulness`, `per_query` (list) plus `confusion_matrix`, `precision_at_3`, `latency_ms_p50`. Metrics with no data = `None` (never fake). Write scorecard JSON/CSV. *Accept:* `make test-p4` `test_run_benchmark_on_mocks` passes once P1's manager exists; `make eval` prints a scorecard table.
- [x] **P4-05 Explainability** (`explain.py`). `ExplanationView` per report: for each recommendation: why (rationale + evidence count + source list), `confidence_bucket` (High >=0.75, Medium 0.5–0.75, Low <0.5), uncertainty banner text when any domain is `INFORMATION_REQUEST`/HIGH (listing missing diagnostics verbatim), "what would change this answer" (missing inputs), and a `calibration` helper `calibration_table(per_query)` bucketing confidence vs observed relevance from benchmark results. Read-only over finished reports. *Accept:* unit tests for bucket thresholds and banner.
- [x] **P4-06 Streamlit dashboard** *(DONE and redesigned: light theme via `python -m p4_eval_ui.ui.launch`, animated request-flow diagram with pause/replay, follow-up diagnostics box, evidence highlighting, scorecard targets and run history; live per-agent progress waits on P1, see `questions/to-p1/`)* (`ui/dashboard.py`). Works fully on mocks (`core.registry.load_manager()`; if None, show a clear "Manager not built yet" message). Tabs: **Consult** (query box, optional diagnostics text area -> `context`, executive summary, recommendations with confidence meters, next steps, KPIs), **Agent trace** (from `audit_trace`: routing decision, per-agent status/latency/mock-vs-real, fallbacks), **Evidence** (domain cards with collapsible citations: source_doc, page, section, snippet), **Evaluation** (scorecard from `data/eval/scorecard.json`, metric charts, confusion matrix, calibration). Include 5 one-click example queries (from the benchmark + the Cisco router example in the brief). Add deps to `p4_eval_ui/requirements.txt` only. *Accept:* `streamlit run` shows all four tabs on mocks without errors.
- [ ] **P4-07 Evaluation run & report.** *(STATUS: tooling done: `make eval`, `python -m p4_eval_ui.evaluation.findings [--post-questions]`. Real run pending: P3 agents and P2's TechAgent/ClinicalAgent are not merged yet, so the committed `eval_findings.md` is a mock-agent run and is labelled as partial.)* After integration, run `make eval` with real agents (`REAL_DOMAINS=all`, `LLM_MODE=live` if keys exist), save results, list the 3 worst-performing queries per metric in `p4_eval_ui/presentation/eval_findings.md` and send each as a question to the owning member's inbox (`questions/to-pN/`) for them to fix.
- [ ] **P4-08 Presentation.** *(STATUS: `slides.md`, `build_slides.py` -> `slides.pdf` and `demo_script.md` done; the scorecard slide is filled from `data/eval/scorecard.json` and flags partial runs. Still to do: rebuild the PDF after the real eval run and record the video.)* `slides.md` -> `slides.pdf` (architecture, data/grounding, RAG + citations, recommender, cross-domain demo, evaluation scorecard with real numbers, honest limitations: known data gaps in `COMMON.md` section 7, business value/KPIs). `demo_script.md` for a 3–5 minute video that walks: Cisco router example (INFORMATION_REQUEST then with diagnostics), a SEC question, a SOFI question, a cross-domain question, the scorecard. Record the video.
- [x] **P4-09 Own unit tests** in `p4_eval_ui/tests/` (metrics edge cases, faithfulness, explain, benchmark on a tiny stub manager you define inside the test).

## DO NOT build (belongs to others)
- Routing, orchestration, synthesis, audit-trace production -> P1 (you only read `audit_trace`).
- Knowledge bases, agents, recommenders -> P2 / P3. Agents set their own confidence; you never feed scores back into them.
- Do not edit `core/schemas.py`, `tests/`, or other members' folders.
- Do not build the retail market-basket model or a FastAPI service.

## Handoff gate
`STRICT=1 make test-p4` · `make test-integration MEMBER=p4` · dashboard runs on mocks and on real agents · all boxes checked.

## Interfaces
- You consume: `ManagerAgent` and agents' `retrieve()` (COMMON.md section 3); `audit_trace` keys from `../p1_orchestrator/TODO.md` P1-07; item ids from `../p2_tech_clinical/TODO.md` P2-05 and `../p3_sec_csr/TODO.md` P3-06.
- You provide: `metrics.py`, `benchmark.run_benchmark` (used by `make eval` and the contract tests).
