# P1 — Lead Architect & Orchestrator — TODO

**Goal:** Build the Manager Agent that classifies a query, routes it to domain agents, dispatches them in parallel, and synthesizes a `ConsultingReport`. Also own the shared `core/` contracts and the integration merge.

Read first: `../COMMON.md`. Your folder: `p1_orchestrator/` (+ you own `core/`, `tests/`, root docs).

## Inputs you consume
- `core/schemas.py`, `core/interfaces.py`, `core/registry.py`, `core/mocks.py`, `core/llm.py` (all already exist; you own them).
- Domain agents ONLY via `core.registry.get_agents()` (real or mock). Never import `p2_*` or `p3_*`.
- `core/fixtures/benchmark_queries.json` (25 labelled queries) to test routing.

## Outputs you must produce (exact paths and signatures)
| File | Contract |
|---|---|
| `p1_orchestrator/agents/manager.py` | `class ManagerAgent(agents: dict[DomainType, BaseDomainAgent] \| None = None)`; `classify(query)->RoutingDecision`; `handle(query, context=None)->ConsultingReport`; `async ahandle(...)`. Default `agents=core.registry.get_agents()`. |
| `p1_orchestrator/agents/router.py` | intent classifier used by the manager (rules + LLM) |
| `p1_orchestrator/agents/dispatcher.py` | async parallel dispatch with timeout and error isolation |
| `p1_orchestrator/agents/synthesizer.py` | `synthesize(query, routing, responses, audit)->ConsultingReport` |
| `p1_orchestrator/main.py` | CLI: `python -m p1_orchestrator.main "<query>" [--json] [--context-file path.json]` |
| `p1_orchestrator/tests/` | your unit tests |

## Tasks (do in order; tick the box when its acceptance test passes)

- [x] **P1-01 Verify the scaffold.** Run `make setup && make test-harness && make test-p1`. Fix any defect in `core/` / `tests/` you find. *Accept:* harness green; `make test-p1` shows only skipped manager tests.
- [x] **P1-02 Rule-based router** (`router.py`, function `classify_rules(query)->RoutingDecision`). Keyword/regex signals per domain: technology (Cisco, router, switch, Catalyst, ISR, ASR, IBM, Google, GCP, outage, connectivity, firmware), clinical (Agilent, Seahorse, NanoZoomer, pathology, diagnostic, instrument, clinical, trial, patient, diabetes, heart, covid, knee), sec (SEC, 10-K, filing, annual report, revenue, margin, risk factors, financial, competitive, regulatory, supplier stability), corporate_responsibility (food security, hunger, malnutrition, SOFI, sustainability, ESG, CSR, carbon, nutrition, famine). Multi-label. Never returns `CROSS_DOMAIN` in `domains`; sets `is_cross_domain`. Falls back to the highest-scoring single domain; if nothing matches, return `technology` with `confidence=0.0`. *Accept:* on the 25 benchmark queries, exact-set routing accuracy >= 0.80 in mock mode (test prints per-query misses).
- [x] **P1-03 LLM router.** In `router.py`, `classify_llm(query)` using `core.llm.complete_json(..., RoutingDecision)` with a few-shot prompt built from 6+ examples from the benchmark (do not leak all 25). `classify(query)` = LLM when `not core.llm.is_mock()`, else rules; on any LLM error/`LLMMockMode` fall back to rules and note it in `rationale`. *Accept:* in mock mode, `classify` == `classify_rules`.
- [x] **P1-04 Query decomposition.** `decompose(routing)->dict[domain_value, sub_query]`. Each sub-query restates the user's question focused on that domain (e.g. for a Tech+SEC query: tech sub-query asks about parts/compat; SEC sub-query asks about the named company's risks). LLM when live, template fallback in mock. Single-domain queries keep the original query. *Accept:* every domain in `routing.domains` has a non-empty sub-query; keys are `DomainType.value`.
- [x] **P1-05 Async dispatcher** (`dispatcher.py`): `async dispatch(agents, routing, context, timeout_s=60) -> (dict[domain_value, DomainResponse], trace)`. `asyncio.gather` over `agent.arun(sub_query, context)`. Per-agent timeout and exception isolation: a failing agent yields a `DomainResponse(status="INFORMATION_REQUEST", uncertainty_level="HIGH", findings_summary="Agent <x> failed: <reason>", missing_diagnostics_needed=["<agent> unavailable"])` and is recorded in the trace. Do NOT pass sibling results to siblings (parallel only). *Accept:* unit test with a sleeping agent and a raising agent; the other agents' results survive.
- [x] **P1-06 Synthesizer** (`synthesizer.py`) producing a full `ConsultingReport`:
  - `executive_summary`: 3–5 sentences; lead with the main recommendation; if any domain returned `INFORMATION_REQUEST`, say what is missing before anything else.
  - `consolidated_recommendations`: union of all domain recommendations, de-duplicated by `item_id`, sorted by `confidence_score` desc. **Do not re-score or invent items.**
  - `cross_domain_synthesis`: required (non-empty) when >=2 domains; must name at least one explicit trade-off between domains (e.g. capex vs supply-chain risk); LLM when live, template over domain summaries in mock.
  - `next_steps`: ordered; first items are the missing diagnostics from any `INFORMATION_REQUEST`; then top recommendations as actions; then preventive actions. At least 1 entry always.
  - `measuring_impact_kpis`: at least 3, derived from recommendations' `estimated_impact` where possible, else generic per-domain KPIs (MTTR, outage hours, procurement lead time, risk exposure, food-security-relevant outcome metric, ...).
  - `detected_domains`, `domain_findings` (keys = domain values), `audit_trace` (P1-07).
  *Accept:* `make test-p1` manager contract passes on all 25 benchmark queries with mock agents.
<<<<<<< Updated upstream
- [x] **P1-07 Audit trace** (`audit_trace` dict, always non-empty): `routing` (the `RoutingDecision` dump), `agents` (per domain: status, uncertainty, latency_ms, real_or_mock, error), `mode` (`llm_mode`), `started_at`, `total_ms`, `fallbacks_used` (list). P4's dashboard reads exactly these keys.
- [x] **P1-08 CLI** `main.py`: prints a readable report (summary, per-domain status + citations, recommendations, next steps, KPIs); `--json` prints `ConsultingReport` JSON; `--context-file` loads the `context` dict. Uses `core.registry.get_agents()` (honours `REAL_DOMAINS`). *Accept:* `python -m p1_orchestrator.main "Our Cisco router fails intermittently"` works on mocks.
- [x] **P1-09 Own unit tests** in `p1_orchestrator/tests/` (router accuracy, decomposition, dispatcher isolation, synthesizer rules incl. "INFORMATION_REQUEST first in next_steps").
- [ ] **P1-10 Integration lead.** At the integration freeze: merge branches, run `make test-all`, route failures to the owner via `questions/to-pN/`. Answer `questions/to-p1/` daily (`make questions MEMBER=p1`); apply approved `SCHEMA-CHANGE`s (additive only) and announce them.
=======
- [x] **P1-07 Audit trace** (`audit_trace` dict, always non-empty): `routing` (the `RoutingDecision` dump), `agents` (per domain: status, uncertainty, latency_ms, real_or_mock, error), `mode` (`llm_mode`), `started_at`, `total_ms`, `fallbacks_used` (list). P4's dashboard reads exactly these keys.
- [x] **P1-08 CLI** `main.py`: prints a readable report (summary, per-domain status + citations, recommendations, next steps, KPIs); `--json` prints `ConsultingReport` JSON; `--context-file` loads the `context` dict. Uses `core.registry.get_agents()` (honours `REAL_DOMAINS`). *Accept:* `python -m p1_orchestrator.main "Our Cisco router fails intermittently"` works on mocks.
- [x] **P1-09 Own unit tests** in `p1_orchestrator/tests/` (router accuracy, decomposition, dispatcher isolation, synthesizer rules incl. "INFORMATION_REQUEST first in next_steps").
- [ ] **P1-10 Integration lead.** At the integration freeze: merge branches, run `make test-all`, route failures to the owner via `QUESTIONS.md`. Answer `QUESTIONS.md` items daily; apply approved `SCHEMA-CHANGE`s (additive only) and announce them.
>>>>>>> Stashed changes
- [ ] **P1-11 Keep `requirements.txt` and `core/` healthy.** Add shared deps only if two members need them.

## DO NOT build (belongs to others)
- Knowledge bases, document ingestion, chunking of domain data -> P2 / P3.
- Any recommender or part/instrument/strategy ranking -> P2 / P3 (you only merge their items).
- Domain agents (`TechAgent`, `ClinicalAgent`, `SECAgent`, `CSRAgent`) -> P2 / P3. Use mocks.
- Metrics, benchmark runner, confidence calibration, Streamlit UI, slides -> P4.
- FastAPI service or the retail market-basket model -> out of scope (`FUTURE.md`).

## Handoff gate (all must be green)
`STRICT=1 make test-p1` · `make test-integration MEMBER=p1` · all boxes above checked.

## Interfaces you depend on from others
- P2/P3 agents: `BaseDomainAgent` contract in `COMMON.md` section 3. See `../p2_tech_clinical/TODO.md`, `../p3_sec_csr/TODO.md`.
- P4 reads your `audit_trace` keys and `ConsultingReport` fields: `../p4_eval_ui/TODO.md` (P4-05, P4-06).
