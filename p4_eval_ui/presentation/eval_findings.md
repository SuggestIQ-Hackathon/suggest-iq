# Evaluation findings (2026-10-18T15:53:34.048629+00:00)

37 queries, llm_mode=mock, agents: technology=real, clinical=real, sec=real, corporate_responsibility=real

## Routing: worst queries
- `Q29` (owner p1): expected ['corporate_responsibility'] got ['technology']: How many people were undernourished globally according to the FAO repo
- `Q32` (owner p1): expected ['technology', 'sec'] got ['technology']: Can Google Cloud managed services reduce our router maintenance burden
- `Q33` (owner p1): expected ['corporate_responsibility', 'technology'] got ['technology']: How could sensor networks reduce food waste, and which Cisco hardware 

## Retrieval: worst queries
- `Q03` (owner p2): no expected source in top-5 for technology: What IPsec throughput and memory options does the Cisco Cata
- `Q05` (owner p2): no expected source in top-5 for technology: What WAN interface modules can I add to a Cisco 4000 Series 
- `Q06` (owner p2): no expected source in top-5 for clinical: Which Agilent instrument is best for real-time metabolic ana

## Recommendation relevance: worst queries
- `Q02` (owner p2): NDCG@3=0.00: Which Cisco router family supports redundant route processor
- `Q03` (owner p2): NDCG@3=0.00: What IPsec throughput and memory options does the Cisco Cata
- `Q04` (owner p2): NDCG@3=0.00: Can we run Cisco Catalyst 8000V on a public cloud instead of

## Faithfulness: worst queries
- `Q01` (owner p2): faithfulness=0.00, 7 unsupported statement(s)
- `Q02` (owner p2): faithfulness=0.00, 1 unsupported statement(s)
- `Q03` (owner p2): faithfulness=0.00, 1 unsupported statement(s)

## Diagnostic gate: worst queries
- none
