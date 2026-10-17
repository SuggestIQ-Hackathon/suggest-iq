# P2 — Systems & Hardware AI Lead (Technology + Clinical) — TODO

**Goal:** Build the Technology and Clinical knowledge bases, the two domain agents, and the hardware/instrument recommender. Distinguish confirmed faults from hypotheses and request missing diagnostics instead of guessing.

Read first: `../COMMON.md`. Your folder: `p2_tech_clinical/` only.

## Inputs you consume
- `resources/DataSource-Cisco.txt` (5 Cisco datasheet PDF URLs + product pages), `resources/Google GCP.txt`, `resources/Agilent.txt` (page URLs), `resources/Clinical.zip`.
- `core/rag_base.py` (`chunk_text`, `VectorIndex`, `hits_to_citations`, `Hit`), `core/llm.py`, `core/interfaces.py` (`BaseDomainAgent`), `core/schemas.py`.
- Test queries: `core/fixtures/contract_queries.json` (keys `technology`, `clinical`) and benchmark ids Q01–Q10.

## Outputs you must produce
| File | Contract |
|---|---|
| `p2_tech_clinical/knowledge/ingest.py` | CLI `python -m p2_tech_clinical.knowledge.ingest [--only cisco\|agilent\|gcp\|clinical]` downloads/unzips into `data/raw/...`, writes `data/raw/MANIFEST.json` |
| `p2_tech_clinical/knowledge/tech_kb.py` | `class TechKB`: `build()`, `search(query, k=5, vendor=None, model=None) -> list[Hit]`; index in `data/index/tech/` |
| `p2_tech_clinical/knowledge/clinical_kb.py` | `class ClinicalKB`: `build()`, `search(query, k=5, source_type=None) -> list[Hit]`; index in `data/index/clinical/` |
| `p2_tech_clinical/recommenders/catalog/cisco_parts.json`, `agilent_instruments.json` | curated catalog (schema in P2-05) |
| `p2_tech_clinical/recommenders/hardware.py` | `recommend(problem_text, catalog, filters=None, top_k=3) -> list[RecommendationItem]` |
| `p2_tech_clinical/agents/symptoms.py` | symptom parser + diagnostics gate (P2-06) |
| `p2_tech_clinical/agents/tech_agent.py` | `class TechAgent(BaseDomainAgent)`, `domain = DomainType.TECHNOLOGY` |
| `p2_tech_clinical/agents/clinical_agent.py` | `class ClinicalAgent(BaseDomainAgent)`, `domain = DomainType.CLINICAL` |
| `p2_tech_clinical/tests/` | your unit tests |

## Tasks (in order)

- [ ] **P2-01 Ingestion script.** Download the 5 Cisco datasheet PDFs (URLs in `DataSource-Cisco.txt`) to `data/raw/cisco/`; fetch and save text of the Agilent pages (`Agilent.txt`) and GCP pages (`Google GCP.txt`) to `data/raw/agilent/`, `data/raw/gcp/` (requests + BeautifulSoup); unzip `Clinical.zip` to `data/raw/clinical/`. Record each source, URL, status and sha256 in `data/raw/MANIFEST.json`. If a download is blocked, write the failure into the manifest, continue, and add a `QUESTIONS.md` note (do not fabricate content). *Accept:* manifest lists every source; script is idempotent.
- [ ] **P2-02 Chunking with metadata.** Use `core.rag_base.chunk_text` and `extra_meta`. PDFs: page-by-page via `pypdf`, metadata `source_doc` (file name), `page`, `vendor` (`Cisco`/`Agilent`/`Google`/`Research`), `model` (`Catalyst 8200`, `Catalyst 8300`, `Catalyst 8000V`, `ISR 4000`, `ASR 1000`, `Seahorse`, `NanoZoomer`, `Artisan Link Pro`), `doc_type` (`datasheet`, `product_page`, `paper`, `trial`). Clinical CSVs: one chunk per study row from columns NCT Number, Study Title, Brief Summary, Conditions, Interventions, Primary Outcome Measures (`source_doc` = `ctg-studies_<topic>.csv`, `section` = NCT id, `doc_type=trial`). Cap CSV rows per file with a documented constant if indexing is slow (e.g. 3000) — state it in the manifest. *Accept:* unit test: every chunk has `source_doc`; Cisco chunks carry `model`.
- [ ] **P2-03 `TechKB`.** Build/load index for Cisco + GCP; `search()` supports `vendor`/`model` metadata filters. *Accept:* gold test — for 5 hand-written questions about the 5 Cisco models (e.g. "IPsec throughput of Catalyst 8300"), the correct datasheet is in top-5 for >= 4 of 5; print the table.
- [ ] **P2-04 `ClinicalKB`.** Index Agilent pages + clinical PDFs + trial rows; `search(source_type=...)`. *Accept:* gold test — Seahorse / NanoZoomer / Artisan questions return the right Agilent page in top-5; diabetes/heart-attack literature questions return the right topic folder.
- [ ] **P2-05 Component & instrument catalog.** `cisco_parts.json` (>= 20 entries: route processors, memory/storage modules, network interface modules, power supplies, fans, SFP/optics, licences — each tied to the models whose datasheet lists them) and `agilent_instruments.json` (>= 8 entries from the Agilent pages: instrument, consumables/accessories). Schema per entry: `item_id`, `vendor`, `name`, `category`, `compatible_models` (list), `specs` (dict), `typical_failure_symptoms` (list of keywords), `cost_tier` (1–5, relative, **no invented prices**), `lead_time_tier` (1–5 or null), `source_doc`, `source_page`, `verified` (true only if the fact is visible in a datasheet you ingested; otherwise false). Entries with `verified=false` must lower the recommendation's confidence. *Accept:* schema test; no duplicate `item_id`.
- [ ] **P2-06 Symptom parser + diagnostics gate** (`agents/symptoms.py`). `parse(query, context) -> ParsedSymptoms` (vendor, model, symptoms list, diagnostics_present: set). `required_diagnostics(domain, symptoms) -> list[str]`. Technology required set (at least): `show tech-support`, `show logging` (recent crashes/flaps), `show interfaces` counters (CRC, input/output errors), `show environment` (power/temperature/fans), `show platform` hardware status, software version, optic/DOM readings for fibre links. Clinical: instrument log/error codes, last calibration/maintenance date, consumable lot/age, firmware/software version. *Rule:* if `context['diagnostics']` is missing or does not contain evidence for the required checks -> the agent returns `INFORMATION_REQUEST`. *Accept:* "intermittent connectivity failures" with no context -> `INFORMATION_REQUEST`, `missing_diagnostics_needed` non-empty.
- [ ] **P2-07 Hardware recommender** (`recommenders/hardware.py`). Score = `0.50*cosine(problem_embedding, catalog_item_text_embedding)` (use `core.rag_base.embed`) `+ 0.25*symptom_keyword_match + 0.15*(1 - norm(cost_tier)) + 0.10*(1 - norm(lead_time_tier))`, then **hard filter** on compatibility (an item whose `compatible_models` excludes the detected model is removed, never down-weighted: an ASR 1000 module is never offered for a Catalyst 8200), then multiply by 0.8 if `verified=false`. Return top-3 `RecommendationItem`s with `confidence_score`, `rationale` naming the score components, `compatibility_notes`. Weights are module constants + documented. *Accept:* unit tests: compatibility filter, deterministic ordering, `confidence_score` in [0,1].
- [ ] **P2-08 `TechAgent`.** Flow: parse -> gate -> retrieve (`TechKB`) -> if gate fails: `INFORMATION_REQUEST` with ranked *hypotheses* in `findings_summary` (each labelled "hypothesis"), `Diagnostic Action` recommendations only, **no `Replacement Part`**; if diagnostics present: evaluate against rules/evidence; `CONFIRMED_FAULT` only if diagnostics directly show it, else `HYPOTHESIS`; parts via `recommend()`. Always attach citations via `hits_to_citations`. Uncertainty per `COMMON.md` section 3 rule 4. Out-of-corpus vendor (IBM) -> `HIGH`. `retrieve()` = `TechKB.search`. *Accept:* `make test-p2` technology cases pass.
- [ ] **P2-09 `ClinicalAgent`.** Two modes decided by query keywords: (a) **instrument matching/troubleshooting** (Agilent): match stated lab requirements (sample type, throughput, assay, imaging need) to catalog + page evidence; troubleshooting follows the same gate as P2-06; (b) **literature/trial evidence**: summarize what retrieved papers/trials say, citing the paper/NCT id. Never give patient-specific medical advice or diagnosis; add the sentence "Informational only; not medical advice." to `findings_summary` for any condition-related answer. *Accept:* `make test-p2` clinical cases pass.
- [ ] **P2-10 Own unit tests** in `p2_tech_clinical/tests/` for P2-01..P2-09 (use mock mode; no network in tests — use small fixture files you create under `p2_tech_clinical/tests/fixtures/`).

## DO NOT build (belongs to others)
- Routing / deciding which agent answers, query decomposition, report synthesis -> P1.
- SEC filings, 10-K parsing, financial/competitive risk analysis -> P3.
- Food security, CSR/ESG, strategic investment ranking -> P3.
- Metrics, hit-rate scoring, benchmark, UI, confidence calibration -> P4 (you only expose `retrieve()`).
- Your own LLM wrapper, vector store or chunker -> use `core/`.
- Anything in `core/` or `tests/`.

## Handoff gate
`STRICT=1 make test-p2` · `make test-integration MEMBER=p2` · all boxes checked.

## Interfaces
- You provide: `TechAgent`, `ClinicalAgent` (paths fixed in `COMMON.md`). P1 calls `run/arun`; P4 calls `retrieve`.
- You read: nothing from P3. For recommender item ids P4 will need `item_id`s from your catalogs: keep them stable (`CISCO-...`, `AGILENT-...`). See `../p4_eval_ui/TODO.md` P4-01.
