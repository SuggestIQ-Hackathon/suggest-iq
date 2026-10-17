# COMMON.md — Single source of truth (read this first, every session)

Project: **Agentic AI Management Consulting Platform** (SJSU CMPE 256 Hackathon, Oct 17 2026).
Team of 4. Each member builds one folder with their own coding agent (Codex / Cursor / Antigravity / Claude). This file defines what everyone shares. Per-member work lives in `pN_*/TODO.md`.

> **If you are a coding agent:** read this file fully, then your member folder's `AGENTS.md` and `TODO.md`. Build ONLY what your `TODO.md` lists. Do not build anything in another member's TODO. When confused, follow the *Conflict protocol* (section 6).

---

## 1. What we are building

A hierarchical multi-agent consulting platform. A **Manager Agent** (P1) classifies a customer question, routes it to one or more **domain agents**, and merges their answers into a **ConsultingReport** (executive summary, evidence, recommendations, next steps, KPIs).

```
customer query -> Manager (classify -> decompose -> dispatch in parallel -> synthesize)
                     |-- TechnologyAgent (P2)  Cisco / Google (IBM = known gap)
                     |-- ClinicalAgent   (P2)  Agilent instruments + clinical literature/trials
                     |-- SECAgent        (P3)  Cisco / Agilent / Alphabet SEC filings
                     |-- CSRAgent        (P3)  FAO food security (SOFI 2023/2024) + sustainability
                  -> ConsultingReport -> evaluation scorecard + Streamlit dashboard (P4)
```

### The 7 graded capabilities and who owns each

| # | Capability | Owner | Where |
|---|---|---|---|
| 1 | Multi-agent orchestration (classify, route) | P1 | `p1_orchestrator/agents/manager.py` |
| 2 | Domain knowledge grounding (knowledge bases) | P2 (tech, clinical), P3 (sec, csr) | `pN/knowledge/` |
| 3 | RAG with citations | P2, P3 (agents) on P1's `core/rag_base.py` | `pN/agents/` |
| 4 | Intelligent recommender (similarity + rules + ranking) | P2 (hardware/instruments), P3 (strategic actions) | `pN/recommenders/` |
| 5 | Cross-domain reasoning | P1 | `p1_orchestrator/agents/synthesizer.py` |
| 6 | Explainability and evaluation (routing, retrieval, relevance, quality; confidence) | P4 | `p4_eval_ui/evaluation/` |
| 7 | Business value (next steps, why, KPIs) | P1 composes; P4 presents | synthesizer + dashboard |

Out of scope (see `FUTURE.md`): the retail market-basket recommender. **Do not build it.**

---

## 2. Repository map and ownership

**Rule: you may create or edit files ONLY under your own folder.** Everything else is read-only for you. If you need a change elsewhere, add a request to `QUESTIONS.md` and use the mock/interface in the meantime.

| Path | Owner | Notes |
|---|---|---|
| `COMMON.md`, `AGENTS.md`, `CLAUDE.md`, `.cursor/`, `README.md`, `FUTURE.md`, `QUESTIONS.md` (append-only) | P1 | everyone may *append* to `QUESTIONS.md` |
| `core/` (schemas, interfaces, registry, mocks, llm, rag_base) | P1 | **LOCKED**. See section 3 |
| `core/fixtures/benchmark_queries.json` | P4 after kickoff | schema fixed (section 5) |
| `core/fixtures/contract_queries.json` | P1 | |
| `tests/`, `conftest.py`, `pytest.ini`, `Makefile`, `requirements.txt`, `.env.example` | P1 | shared test harness, section 5 |
| `p1_orchestrator/` | P1 | manager, router, dispatcher, synthesizer, CLI |
| `p2_tech_clinical/` | P2 | Tech + Clinical knowledge, agents, hardware recommender |
| `p3_sec_csr/` | P3 | SEC + CSR knowledge, agents, strategy recommender |
| `p4_eval_ui/` | P4 | metrics, benchmark runner, explainability, dashboard, slides |
| `resources/` | nobody | **READ-ONLY** raw inputs (see section 7) |
| `data/` | gitignored | generated: `data/raw/<domain>/`, `data/index/<kb>/`, `data/eval/` |

Each member's package is importable by its folder name (`p2_tech_clinical.agents.tech_agent`). Never import another member's package **directly** (except `core.*`). Cross-member calls go through `core.registry`.

---

## 3. Locked contracts (`core/`)

Read `core/schemas.py`, `core/interfaces.py`, `core/registry.py` — they are short. Summary:

**Schemas** (`core/schemas.py`): `DomainType`, `Citation`, `RecommendationItem`, `DomainResponse`, `RoutingDecision`, `ConsultingReport`. Domain values: `technology`, `clinical`, `sec`, `corporate_responsibility` (+ `cross_domain` as a label only).

**Domain agent interface** (`core/interfaces.py`) — P2 and P3 subclass `BaseDomainAgent`:
```python
class XAgent(BaseDomainAgent):
    domain = DomainType.<...>
    def run(self, query: str, context: dict | None = None) -> DomainResponse
    def retrieve(self, query: str, k: int = 5) -> list[Hit]    # top-k raw hits, best first (P4 evaluates this)
    # arun() is inherited
```
Constructors take **no arguments** and must be cheap-ish (load prebuilt index lazily; build on first use if missing). `run()` must never raise on empty/odd input; return an `INFORMATION_REQUEST` or HIGH-uncertainty response instead.

**Exact class paths** the registry imports (create exactly these names):

| Class | Path | Owner |
|---|---|---|
| `TechAgent` | `p2_tech_clinical/agents/tech_agent.py` | P2 |
| `ClinicalAgent` | `p2_tech_clinical/agents/clinical_agent.py` | P2 |
| `SECAgent` | `p3_sec_csr/agents/sec_agent.py` | P3 |
| `CSRAgent` | `p3_sec_csr/agents/csr_agent.py` | P3 |
| `ManagerAgent(agents: dict[DomainType, BaseDomainAgent] \| None = None)` | `p1_orchestrator/agents/manager.py` | P1 |

`ManagerAgent` methods: `classify(query) -> RoutingDecision`, `handle(query, context=None) -> ConsultingReport`, `async ahandle(...)`.

**P4 public API** (`p4_eval_ui/evaluation/metrics.py`): `routing_accuracy(predicted: list[set[str]], gold: list[set[str]]) -> float` (exact set match), `hit_rate_at_k(retrieved_ids: list[list[str]], relevant_ids: list[set[str]], k: int) -> float`, `precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float`, `ndcg_at_k(ranked: list[str], gains: dict[str, float], k: int) -> float`. And `p4_eval_ui/evaluation/benchmark.py`: `run_benchmark(manager, queries_path=None, k=5) -> dict` with keys `routing_accuracy`, `retrieval_hit_rate`, `recommendation_ndcg_at_3`, `faithfulness`, `per_query`.

**Context keys** a caller may pass: `diagnostics` (str, pasted logs/telemetry), `product_model` (str), `companies` (list[str]). Agents ignore unknown keys.

**Status semantics** (`DomainResponse.status`):
- `INFORMATION_REQUEST` — evidence is insufficient; `missing_diagnostics_needed` MUST be non-empty. No replacement parts recommended.
- `HYPOTHESIS` — ranked possible causes, not confirmed.
- `CONFIRMED_FAULT` — only when supplied diagnostics/evidence directly establish it; `uncertainty_level` must not be HIGH.
- `ANALYSIS_COMPLETE` — analysis (SEC, CSR, selection tasks) finished.

**Hard rules for every agent**
1. **No uncited claims.** Every recommendation and every factual statement must be backed by a `Citation` whose `snippet` is verbatim text from a retrieved chunk. Numbers (revenue, throughput, percentages) may only appear if they appear in a retrieved snippet.
2. **Never assume a fault.** Technology and Clinical agents must distinguish confirmed faults from hypotheses and ask for missing diagnostics (no parts recommended without them).
3. **Estimates are labelled.** `estimated_impact` is an estimate, worded as such ("est.", "typically"), never a guarantee.
4. **Uncertainty rule**: `LOW` = direct evidence, >=2 citations agree; `MEDIUM` = partial or hypothesis; `HIGH` = no/weak evidence, out-of-corpus entity, or missing diagnostics. `confidence_score` of a recommendation is in [0,1] and must be explainable from its components (document the formula in the code docstring).
5. **Logical source names.** `Citation.source_doc` is the original file name (e.g. `datasheet-c78-744088.pdf`, `SOFI-2023.pdf`) or a clear logical name recorded in the member's manifest. Pages are 1-based.
6. **Offline fallback.** Any step using `core.llm` MUST have a rule-based fallback used when `LLM_MODE=mock` (`core.llm.complete_json` raises `LLMMockMode` there). Tests always run in mock mode.

**Shared plumbing — do not reimplement:** `core/llm.py` (`complete`, `complete_json`, `is_mock`) and `core/rag_base.py` (`chunk_text`, `VectorIndex.add/query/save/load`, `hits_to_citations`, `Hit`). Embeddings default to an offline hash embedder (`EMBEDDING_MODE=hash`); switch to `local` or `litellm` for quality runs. Indices must be rebuilt if the mode changes.

**Changing a locked contract:** only P1, and only by appending a `SCHEMA-CHANGE` entry to `QUESTIONS.md` first; everyone adapts. Additive, optional fields only.

---

## 4. LLM and environment

- Python >= 3.11. `make setup` creates `.venv` and installs `requirements.txt` + every `pN_*/requirements.txt`. Add YOUR extra libraries only to YOUR `pN_*/requirements.txt`.
- Copy `.env.example` to `.env` (never commit). `LLM_MODE=mock|live`, `LLM_MODEL` (any LiteLLM string), provider key.
- Tests ignore `.env` and force offline mock mode.

---

## 5. Common test method (same commands for everyone, run from the repo root)

| Command | What it does |
|---|---|
| `make setup` | create venv, install deps |
| `make test-harness` | self-test of mocks/schemas/fixtures (run once after cloning; must be green) |
| `make test-pN` (N = 1..4) | contract tests for YOUR slice + your own unit tests in `pN_*/tests/` |
| `STRICT=1 make test-pN` | **handoff gate**: fails on anything not implemented (skips become failures) |
| `make test-integration MEMBER=pN` | your REAL module(s) + mocks for everyone else, driven by the real Manager over all benchmark queries; every `ConsultingReport` must validate. Proves your slice will work with the others. |
| `make test-all` | all real modules together (`REAL_DOMAINS=all STRICT=1`); run at integration merge |
| `make eval` | P4's benchmark -> scorecard in `data/eval/` |

How it works: `tests/contract/checks.py` defines the contract (schema validity, citations present, `INFORMATION_REQUEST` rules, no parts without diagnostics, `retrieve()` returns `Hit`s, runs offline in time). `make test-pN` runs it against your **real** class; until it exists the test is skipped (visible as `s`). Your slice is *done* when `STRICT=1 make test-pN` and `make test-integration MEMBER=pN` are both green.

You may add more tests under your own `pN_*/tests/`. Do not edit anything in `tests/`; if a check is wrong or too strict, write it in `QUESTIONS.md`.

**Benchmark fixture** (`core/fixtures/benchmark_queries.json`, 25 queries: 5 each tech, clinical, sec, csr + 5 cross-domain). Each item: `id`, `query`, `expected_domains` (list of domain values), `type` (`single`|`cross`), `expected_sources` (substrings of expected `source_doc`s), `expected_keywords`. P4 may extend it (keep existing ids).

---

## 6. Conflict protocol (when an agent is unsure)

1. Re-read this file (sections 2 and 3).
2. Read the other members' `TODO.md`. If the work item appears in **someone else's** TODO, **do not build it**. Use the mock (`core.mocks.MockDomainAgent`) or the interface in section 3.
3. If a needed thing is in nobody's TODO, do **not** invent it. Append to `QUESTIONS.md`: `[date] [Pn] [QUESTION|SCHEMA-CHANGE|BLOCKED] <what you need, which TODO item, proposed answer>`, then continue with the next TODO item.
4. Never edit files outside your folder to "fix" something. Never rename or move another member's files.
5. Never add features beyond your TODO ("nice to haves" included) until every box in your TODO is checked and the handoff gate is green.

### Boundaries that have caused overlap before (decided)
- Retrieval/LLM plumbing -> P1's `core/`; P2/P3 only call it.
- Recommenders: P2 ranks hardware/instruments; P3 ranks strategic actions; P1's synthesizer only **merges and orders** `RecommendationItem`s by `confidence_score` and never re-scores or invents recommendations.
- Confidence/uncertainty: each agent sets its own `confidence_score`/`uncertainty_level` using the rule in section 3. P4's explainability code reads finished responses only; agents never import P4.
- Routing logic is P1 only. P2/P3 agents do not decide whether a question belongs to them; the Manager does.
- Metrics, benchmark runner and UI are P4 only. Agents expose `retrieve()`; P4 computes hit-rate.

---

## 7. Resources (`resources/`, read-only)

| File | Content | Used by |
|---|---|---|
| `SJSU_CMPE256_Hackathon_20261017_v7_Release.pdf` | official brief (also contains the retail task = `FUTURE.md`) | all |
| `Agentic_AI_Consulting_Hackathon_Team_Plan.docx` | original team plan; this repo's structure supersedes its task split | all |
| `DataSource-Cisco.txt` | Cisco router pages + 5 datasheet PDF URLs (Catalyst 8300, 8200, 8000V, ISR 4000, ASR 1000) — links only, must be downloaded | P2 |
| `Google GCP.txt` | GCP MCP / RAG doc links | P2 |
| `Agilent.txt` | Agilent product page links (Seahorse, digital pathology, NanoZoomer, Artisan Link Pro) — links only | P2 |
| `Clinical.zip` | 20 research PDFs (Covid, Diabetes, Heart_attack, KneeInjuries) + 4 ClinicalTrials.gov CSVs (~110 MB) | P2 |
| `UnitedStatesSecuritiesandExchangeCommission(SEC).zip` | Agilent (1), Alphabet (2), Cisco (2) filings, GUID file names; company/year/form to be verified | P3 |
| `FoodSecurity.zip` | FAO SOFI 2023 and SOFI 2024 | P3 |
| `Retail.zip` | market-basket CSV | nobody (future) |

Unzip into `data/raw/<domain>/` (gitignored) with your ingest script. Do not modify `resources/`.

**Known data gaps (accepted, handle gracefully, be honest in the demo):**
- No IBM files -> Technology agent covers Cisco and Google; IBM questions return `HIGH` uncertainty.
- Agilent material is web pages, not manuals -> P2 builds an instrument catalog from them.
- No company ESG reports -> CSR agent is grounded in SOFI; ESG-metric questions are `HIGH` uncertainty.
- SEC filing year may not be 2025 -> P3 verifies and reports in `QUESTIONS.md`.

---

## 8. Milestones (build today, test tomorrow)

1. **Kickoff (now):** everyone clones, runs `make setup && make test-harness` (green), reads this file and their TODO.
2. **Independent build (today):** work your TODO in order, committing to `feature/pN-*`. `make test-pN` stays runnable at all times. Post `[Status] [Working On] [Needs From Others]` updates.
3. **Integration freeze (tonight):** merge feature branches to `main`, run `make test-all`. P1 leads the merge; broken contracts are fixed by the **owner** of the failing module.
4. **Tomorrow:** `make eval`, fix retrieval/routing failures found by the benchmark (owners fix their own), UI polish, demo video, slides, submission.

Git: `main` is protected; branches `feature/p1-orchestrator`, `feature/p2-tech-clinical`, `feature/p3-sec-csr`, `feature/p4-eval-ui`. Because folders are disjoint, merges should not conflict; if they do, someone edited outside their folder.
