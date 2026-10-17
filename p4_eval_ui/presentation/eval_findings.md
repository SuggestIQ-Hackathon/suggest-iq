# Evaluation findings (2026-10-17T23:34:36.544011+00:00)

37 queries, llm_mode=mock, agents: technology=mock, clinical=mock, sec=mock, corporate_responsibility=mock

> **Partial run.** Mock agents for: technology, clinical, sec, corporate_responsibility. Retrieval, recommendation and faithfulness findings below are artefacts of the mocks, not defects. Re-run `make eval` with `REAL_DOMAINS=all` after integration.

## Routing: worst queries
- `Q29` (owner p1): expected ['corporate_responsibility'] got ['technology']: How many people were undernourished globally according to the FAO repo
- `Q32` (owner p1): expected ['technology', 'sec'] got ['technology']: Can Google Cloud managed services reduce our router maintenance burden
- `Q33` (owner p1): expected ['corporate_responsibility', 'technology'] got ['technology']: How could sensor networks reduce food waste, and which Cisco hardware 

## Retrieval: worst queries
- `Q01` (owner p2): no expected source in top-5 for technology: Our Cisco Catalyst 8200 edge router has intermittent connect
- `Q02` (owner p2): no expected source in top-5 for technology: Which Cisco router family supports redundant route processor
- `Q03` (owner p2): no expected source in top-5 for technology: What IPsec throughput and memory options does the Cisco Cata

## Recommendation relevance: worst queries
- `Q02` (owner p2): NDCG@3=0.00: Which Cisco router family supports redundant route processor
- `Q03` (owner p2): NDCG@3=0.00: What IPsec throughput and memory options does the Cisco Cata
- `Q04` (owner p2): NDCG@3=0.00: Can we run Cisco Catalyst 8000V on a public cloud instead of

## Faithfulness: worst queries
- `Q01` (owner p2): faithfulness=0.00, 1 unsupported statement(s)
- `Q02` (owner p2): faithfulness=0.00, 1 unsupported statement(s)
- `Q03` (owner p2): faithfulness=0.00, 1 unsupported statement(s)

## Diagnostic gate: worst queries
- none
