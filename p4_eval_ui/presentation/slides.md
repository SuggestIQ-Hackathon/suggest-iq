# Suggest IQ
- Guiding enterprises from questions to decisions
- SJSU CMPE 256 Recommender Systems Hackathon, Oct 17 2026
- A manager agent routes customer problems to specialist agents and returns an evidence-backed consulting recommendation
- Every answer shows: what to do next, why, and how the impact is measured

---
# The problem
- Enterprises ask questions that span hardware, labs, finance and sustainability
- A single chatbot guesses; consultants need evidence, caveats and next actions
- Goal: grounded recommendations with citations, explicit uncertainty, and measurable quality

---
# Architecture: hierarchical multi-agent
- Manager agent: intent detection, query decomposition, parallel dispatch, executive synthesis
- Technology agent (Cisco, Google), Clinical agent (Agilent, clinical literature and trials)
- SEC agent (Cisco, Agilent, Alphabet filings), Corporate Responsibility agent (FAO food security reports)
- Shared contract: every agent returns the same typed DomainResponse; the manager returns a ConsultingReport

---
# Grounding and RAG with citations
- Domain knowledge bases built from datasheets, filings, papers and FAO reports, with source, page and section metadata
- Retrieval feeds each agent; every claim carries a verbatim citation snippet
- No citation, no claim: numbers appear only if present in a retrieved snippet

---
# Never guess a fault
- Example: "Cisco router has intermittent connectivity failures"
- Without logs the system returns INFORMATION_REQUEST: ranked hypotheses plus the exact diagnostics needed, and no replacement parts
- With diagnostics it can move to HYPOTHESIS or CONFIRMED_FAULT and rank compatible parts
- We measure this: diagnostic-gate compliance in the benchmark

---
# Intelligent recommendations
- Hardware and instruments: cosine similarity + hard compatibility filter + cost and lead-time ranking
- Strategic actions: weighted impact, regulatory risk and feasibility scoring
- Each recommendation has a confidence score, rationale and compatibility notes

---
# Cross-domain reasoning
- Example: replace a Cisco router, check Cisco's supply-chain risk, and weigh sustainability impact
- Agents run in parallel; the synthesizer names explicit trade-offs (capex vs supplier risk vs sustainability)
- The audit trace shows who ran, how long they took, and whether they were real or mock

---
# How we evaluate
- 37-query benchmark: single-domain, cross-domain and differently phrased routing queries, plus out-of-scope probes
- Routing accuracy (exact set match, per-domain precision/recall, confusion matrix)
- Retrieval hit-rate@k, recommendation NDCG@3 and precision@3 against graded judgments
- Faithfulness (claim support by citations; hallucination rate = 1 - faithfulness)

---
# Scorecard
{{SCORECARD}}

---
# Business value and KPIs
- What to do next: ordered actions, starting with the missing diagnostics
- Why: rationale plus evidence sources and a confidence bucket for each recommendation
- How we measure impact: outage hours and MTTR, procurement lead time, vendor risk exposure, lab throughput, food-security outcome metrics

---
# Honest limitations
- No IBM documents; Agilent material is product pages, not service manuals
- No company ESG reports; the CSR agent relies on the FAO food-security reports
- Recommendations are estimates, not guarantees; uncertainty is shown wherever evidence is thin

---
# Next steps
- Add IBM and Agilent service documentation, and company ESG disclosures
- Grow the benchmark and judgments with domain experts
- Future scope: market-basket recommender for retail checkout
