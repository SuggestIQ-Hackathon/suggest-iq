# P3 — Enterprise Strategy & Governance Lead (SEC + CSR) — TODO

**Goal:** Build the SEC and Corporate Responsibility knowledge bases, the two domain agents, and the strategic-action recommender, all grounded with citations.

Read first: `../COMMON.md`. Your folder: `p3_sec_csr/` only.

## Inputs you consume
- `resources/UnitedStatesSecuritiesandExchangeCommission(SEC).zip` (Agilent 1, Alphabet 2, Cisco 2 PDFs with GUID names), `resources/FoodSecurity.zip` (SOFI-2023.pdf, SOFI-2024.pdf).
- `core/rag_base.py`, `core/llm.py`, `core/interfaces.py`, `core/schemas.py`.
- Test queries: `core/fixtures/contract_queries.json` (keys `sec`, `corporate_responsibility`), benchmark ids Q11–Q20.
- The brief's sample CSR prompts (must work): "List major Food insecurity reason in 2023 from within the context of State of Food Security and Nutrition in the World 2023 report"; "...in 2024"; "Explain malnutrition in war zones"; "Explain increase prices impact on food security".

## Outputs you must produce
| File | Contract |
|---|---|
| `p3_sec_csr/knowledge/ingest.py` | CLI `python -m p3_sec_csr.knowledge.ingest [--only sec\|csr]`: unzip to `data/raw/sec/`, `data/raw/csr/`; writes `p3_sec_csr/knowledge/sec_manifest.json` |
| `p3_sec_csr/knowledge/sec_manifest.json` | committed; per file: `file`, `logical_name`, `company`, `form`, `fiscal_year`, `period_end`, `pages` |
| `p3_sec_csr/knowledge/sec_kb.py` | `class SECKB`: `build()`, `search(query, k=5, company=None, item=None, fiscal_year=None) -> list[Hit]`; index `data/index/sec/` |
| `p3_sec_csr/knowledge/csr_kb.py` | `class CSRKB`: `build()`, `search(query, k=5, report_year=None) -> list[Hit]`; index `data/index/csr/` |
| `p3_sec_csr/agents/risk_extractor.py` | `extract_risks(company, category, kb) -> list[RiskFinding]` (pydantic, defined in this file) |
| `p3_sec_csr/agents/sec_agent.py` | `class SECAgent(BaseDomainAgent)`, `domain = DomainType.SEC` |
| `p3_sec_csr/agents/csr_agent.py` | `class CSRAgent(BaseDomainAgent)`, `domain = DomainType.CSR` |
| `p3_sec_csr/recommenders/strategy_catalog.json` | >= 12 candidate actions (P3-06) |
| `p3_sec_csr/recommenders/strategy.py` | `recommend(context_text, catalog=None, top_k=3) -> list[RecommendationItem]` |
| `p3_sec_csr/tests/` | your unit tests |

## Tasks (in order)

- [ ] **P3-01 Verify the SEC PDFs first.** Unzip; read page 1–2 of each PDF (via `pypdf`) and fill `sec_manifest.json` with company, form type (10-K etc.), fiscal year/period end. Set `logical_name` like `Cisco_10-K_FY2025.pdf` from what the document says (never guess). **Immediately** post what you found as a `FINDING` in `questions/to-all/`, especially if the filings are not 2025 (everyone's test queries mention "latest"/"2025"). *Accept:* manifest complete; all 5 files identified.
- [ ] **P3-02 SEC ingestion & section-aware chunking.** `pypdf` page-by-page; detect 10-K items by regex (`Item 1.`, `Item 1A. Risk Factors`, `Item 7. Management's Discussion...`, `Item 7A`, `Item 8`) and set `section` accordingly (carry the last seen item forward across pages). Metadata: `source_doc` (= `logical_name`), `page`, `company`, `form`, `fiscal_year`, `item`. Use `core.rag_base.chunk_text`. *Accept:* unit test (fixture text) assigns Item 1A correctly; `SECKB.search("supply chain risk", company="Cisco")` returns only Cisco chunks.
- [ ] **P3-03 CSR ingestion.** Parse SOFI 2023/2024 (large PDFs, loop pages, skip empty); metadata `source_doc` (`SOFI-2023.pdf`/`SOFI-2024.pdf`), `page`, `report_year`, `section` (chapter/heading if detectable). `CSRKB.search(report_year=...)` filters by year. *Accept:* for the 4 sample prompts above, top-5 hits come from the requested year (2023 prompts -> SOFI-2023; "2024" -> SOFI-2024); print the table.
- [ ] **P3-04 Risk extractor.** For `category in {financial, operational, competitive, supply_chain, regulatory}`: query `SECKB` (with company filter, preferring `Item 1A`), return `RiskFinding(category, company, statement, citation)` where `statement` is a short paraphrase **and** `citation.snippet` is verbatim. LLM summarisation when live; mock fallback = first sentence of the best chunk. *Accept:* each category returns >=1 finding for Cisco and Agilent with Item 1A citations where available.
- [ ] **P3-05 `SECAgent`.** Detect company (Cisco / Agilent / Alphabet; support "Google" -> Alphabet) and question type (risk, financial metrics, comparison). Always `ANALYSIS_COMPLETE` unless the entity is not in the corpus -> `ANALYSIS_COMPLETE` with `uncertainty_level="HIGH"` and a summary saying so (no invented data). Numbers (revenue, margin, %) may only be quoted if present in a retrieved snippet; otherwise say the filing excerpt retrieved did not state it. Mention the fiscal year from the manifest in every summary. Recommendations (category `Risk Mitigation`/`Vendor Due Diligence`) tie to cited risks. `retrieve()` = `SECKB.search`. *Accept:* `make test-p3` sec cases pass.
- [ ] **P3-06 Strategic recommender.** `strategy_catalog.json`: >= 12 candidate actions (e.g. precision-agriculture sensing, cold-chain monitoring, supply-chain visibility/traceability, climate-resilient network infrastructure, energy-efficient network refresh, lab-diagnostics access for malnutrition screening, supplier diversification, ...). Each: `item_id` (`STRAT-...`), `title`, `category` (`Capital Allocation`/`Operational Change`/`Risk Mitigation`), `description`, `impact` (1–5), `regulatory_risk` (1–5, higher = riskier), `feasibility` (1–5), `evidence_keywords`, `source_hint` (which SOFI/SEC theme supports it), `assumptions` (list). Score = `0.40*norm(impact) + 0.30*(1 - norm(regulatory_risk)) + 0.30*norm(feasibility)`, blended 80/20 with the cosine similarity between the context text and the action text (`core.rag_base.embed`). Weights are module constants + documented. Return top-3 `RecommendationItem`s; `rationale` shows the three components; `estimated_impact` is worded as an estimate with its assumption. *Accept:* deterministic ordering test; `confidence_score` in [0,1]; every recommendation links to >=1 retrieved citation in the agent (P3-07).
- [ ] **P3-07 `CSRAgent`.** Answer food-security/sustainability questions strictly from SOFI retrieval (with `report_year` filter if the query names a year; if the query names a year we do not have, return HIGH uncertainty and say so). For "which technology investments..." questions: retrieve evidence, call `strategy.recommend`, and cite the SOFI passages behind each action. Projected impact is expressed as a range or qualitative statement labelled *assumption*, never as a fact. ESG metrics/carbon numbers not in SOFI -> HIGH uncertainty. `retrieve()` = `CSRKB.search`. *Accept:* `make test-p3` csr cases pass; the 4 sample prompts return cited answers from the right report year.
- [ ] **P3-08 Own unit tests** in `p3_sec_csr/tests/` for P3-01..P3-07 (mock mode, small fixtures in `p3_sec_csr/tests/fixtures/`, no network).

## DO NOT build (belongs to others)
- Routing, decomposition, merging of domain answers -> P1.
- Cisco router fixes, replacement parts, Agilent instruments, clinical literature -> P2.
- Metrics, benchmark runner, calibration, dashboard, slides -> P4 (you only expose `retrieve()`).
- Your own LLM wrapper/vector store/chunker -> use `core/`.
- Anything in `core/` or `tests/`.

## Handoff gate
`STRICT=1 make test-p3` · `make test-integration MEMBER=p3` · all boxes checked.

## Interfaces
- You provide: `SECAgent`, `CSRAgent` (paths fixed in `COMMON.md`). P1 calls `run/arun`; P4 calls `retrieve`.
- Keep `item_id`s in `strategy_catalog.json` stable (P4 builds relevance judgments from them): `../p4_eval_ui/TODO.md` P4-01. Do not read P2 code; cross-domain flows happen in P1.
