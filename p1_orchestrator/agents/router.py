"""Intent classification and query decomposition. Owner: P1.

Classifies incoming queries into one or more domains and decomposes multi-domain
queries into focused sub-queries for parallel execution.
"""
import re
from typing import Dict, List, Optional, Tuple

from core import llm
from core.schemas import DomainType, RoutingDecision

_TECH_HARDWARE_PATTERNS = [
    r"\b(?:catalyst|asr|isr|8200|8000v|4000\s*series)\b",
    r"\b(?:router|routers|switch|switches|wan\s*interface|sfp|optics|firmware|ios-xe)\b",
    r"\b(?:packet\s*loss|connectivity\s*failures?|outage|throughput|ipsec)\b",
    r"\b(?:replacement\s*(?:parts?|components?)|failing\s*intermittently)\b",
    r"\b(?:google\s*cloud|gcp)\b",
]

_TECH_COMPANY_PATTERNS = [
    r"\b(?:cisco|ibm|google)\b",
]

_CLINICAL_INSTRUMENT_PATTERNS = [
    r"\b(?:seahorse|nanozoomer|artisan)\b",
    r"\b(?:pathology|whole-slide\s*imaging|special\s*stains)\b",
    r"\b(?:clinical\s*(?:trial|trials|literature|data)?)\b",
    r"\b(?:metabolic\s*analysis|live\s*cells|diagnostic\s*(?:instrument|instruments|lab|equipment))\b",
    r"\b(?:heart\s*attacks?|type\s*2\s*diabetes|patient|cardiac)\b",
    r"\b(?:covid(?:-19)?|coronavirus|sars-cov-2|lung(?:-image)?|pulmonary|respiratory|radiograph|x-ray|chest)\b",
    r"\b(?:knee\s*(?:injuries?|injury)?|orthopedic)\b",
]

_CLINICAL_COMPANY_PATTERNS = [
    r"\b(?:agilent)\b",
]

_SEC_PATTERNS = [
    r"\b(?:10-k|10-q|sec\s*filings?|annual\s*reports?)\b",
    r"\b(?:financial(?:ly)?\s*(?:stable|risks?|performance)?)\b",
    r"\b(?:revenue|gross\s*margin|ebitda|operating\s*income|fiscal\s*year)\b",
    r"\b(?:regulatory\s*and\s*compliance|compliance\s*exposures?)\b",
    r"\b(?:supply[- ]chain\s*risks?|supplier\s*stability|operational\s*risks?)\b",
    r"\b(?:risk\s*factors?|competitive\s*risks?)\b",
    r"\b(?:long-term\s*supplier)\b",
]

_CSR_PATTERNS = [
    r"\b(?:food\s*insecurity|food\s*security|malnutrition|hunger|famine)\b",
    r"\b(?:state\s*of\s*food\s*security|sofi|nutrition\s*in\s*the\s*world)\b",
    r"\b(?:sustainability|sustainable|esg|csr)\b",
    r"\b(?:corporate\s*responsibility)\b",
    r"\b(?:rising\s*food\s*prices?|carbon\s*footprint|greenhouse\s*gas)\b",
]


def _match_count(query: str, patterns: List[str]) -> int:
    text = query.lower()
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, text, re.IGNORECASE))
    return total


def classify_rules(query: str) -> RoutingDecision:
    """Keyword/regex signals per domain. Multi-label. Never returns CROSS_DOMAIN in domains.
    Sets is_cross_domain = len(domains) >= 2.
    """
    lower_q = query.lower()

    tech_hw = _match_count(query, _TECH_HARDWARE_PATTERNS)
    tech_co = _match_count(query, _TECH_COMPANY_PATTERNS)
    
    clin_inst = _match_count(query, _CLINICAL_INSTRUMENT_PATTERNS)
    clin_co = _match_count(query, _CLINICAL_COMPANY_PATTERNS)

    sec_count = _match_count(query, _SEC_PATTERNS)
    csr_count = _match_count(query, _CSR_PATTERNS)

    # Disambiguation:
    # If SEC signals are strong (10-K, annual report, revenue, financial risk, etc.)
    # and there are NO hardware/instrument words, company names (Cisco/Agilent/Alphabet) are SEC targets, not Tech/Clinical.
    has_strong_sec = sec_count > 0 and (
        re.search(r"\b(?:10-k|annual\s*report|revenue|gross\s*margin|sec\s*filing|filings|financial(?:ly)?|fiscal\s*year|regulatory|risk\s*factors?)\b", lower_q)
    )

    # Compute domain presence
    has_tech = False
    if tech_hw > 0:
        has_tech = True
    elif tech_co > 0 and not has_strong_sec:
        has_tech = True

    has_clin = False
    if clin_inst > 0:
        has_clin = True
    elif clin_co > 0 and not has_strong_sec:
        has_clin = True

    has_sec = sec_count > 0
    has_csr = csr_count > 0

    # Cross-domain check for queries like Q20: "Which technology investments could most improve food security..."
    # If CSR is present and tech is just the word "technology" (no cisco/gcp/router/switch), it is CSR only.
    if has_csr and not re.search(r"\b(?:cisco|google|gcp|ibm|router|switch|hardware|cloud)\b", lower_q):
        has_tech = False

    selected_domains: List[DomainType] = []
    if has_tech:
        selected_domains.append(DomainType.TECHNOLOGY)
    if has_clin:
        selected_domains.append(DomainType.CLINICAL)
    if has_sec:
        selected_domains.append(DomainType.SEC)
    if has_csr:
        selected_domains.append(DomainType.CSR)

    if not selected_domains:
        selected_domains = [DomainType.TECHNOLOGY]

    is_cross = len(selected_domains) >= 2
    total_signals = tech_hw + tech_co + clin_inst + clin_co + sec_count + csr_count
    confidence = min(1.0, max(0.5, total_signals / 3.0)) if total_signals > 0 else 0.0

    domain_order = [DomainType.TECHNOLOGY, DomainType.CLINICAL, DomainType.SEC, DomainType.CSR]
    selected_domains = [d for d in domain_order if d in selected_domains]

    routing = RoutingDecision(
        query=query,
        domains=selected_domains,
        is_cross_domain=is_cross,
        rationale=f"Rule-based matched: {[d.value for d in selected_domains]}",
        confidence=round(confidence, 2),
    )
    routing.sub_queries = decompose(routing)
    return routing


def decompose(routing: RoutingDecision) -> Dict[str, str]:
    """Break multi-domain queries into domain-specific sub-queries.
    Single-domain queries preserve the original query.
    Keys are DomainType.value.
    """
    if not routing.is_cross_domain:
        return {d.value: routing.query for d in routing.domains}

    sub_queries: Dict[str, str] = {}
    query = routing.query

    for domain in routing.domains:
        if domain == DomainType.TECHNOLOGY:
            sub_queries[domain.value] = f"Evaluate technical hardware, network components, and operational requirements for: {query}"
        elif domain == DomainType.CLINICAL:
            sub_queries[domain.value] = f"Analyze diagnostic instrument specifications, clinical requirements, and lab equipment for: {query}"
        elif domain == DomainType.SEC:
            sub_queries[domain.value] = f"Assess financial, supply chain, operational, and regulatory risks from SEC 10-K filings for: {query}"
        elif domain == DomainType.CSR:
            sub_queries[domain.value] = f"Evaluate sustainability, ESG outcomes, and food security impacts for: {query}"
        else:
            sub_queries[domain.value] = query

    return sub_queries


_FEW_SHOT_EXAMPLES = """
Example 1:
Query: "Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement parts should we order?"
Response: {"query": "Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement parts should we order?", "domains": ["technology"], "is_cross_domain": false, "sub_queries": {"technology": "Our Cisco enterprise router is experiencing intermittent connectivity failures. Which replacement parts should we order?"}, "rationale": "Cisco router failure and replacement parts.", "confidence": 0.95}

Example 2:
Query: "Which Agilent instrument is best for real-time metabolic analysis of live cells in our lab?"
Response: {"query": "Which Agilent instrument is best for real-time metabolic analysis of live cells in our lab?", "domains": ["clinical"], "is_cross_domain": false, "sub_queries": {"clinical": "Which Agilent instrument is best for real-time metabolic analysis of live cells in our lab?"}, "rationale": "Agilent lab equipment and metabolic cell analysis.", "confidence": 0.95}

Example 3:
Query: "What are the main risk factors Cisco discloses in its latest 10-K?"
Response: {"query": "What are the main risk factors Cisco discloses in its latest 10-K?", "domains": ["sec"], "is_cross_domain": false, "sub_queries": {"sec": "What are the main risk factors Cisco discloses in its latest 10-K?"}, "rationale": "10-K SEC filing risk factors query.", "confidence": 0.95}

Example 4:
Query: "List major food insecurity reasons in 2024 from the State of Food Security and Nutrition report."
Response: {"query": "List major food insecurity reasons in 2024 from the State of Food Security and Nutrition report.", "domains": ["corporate_responsibility"], "is_cross_domain": false, "sub_queries": {"corporate_responsibility": "List major food insecurity reasons in 2024 from the State of Food Security and Nutrition report."}, "rationale": "Food security and SOFI report query.", "confidence": 0.95}

Example 5:
Query: "Our Cisco enterprise router is failing intermittently. What should we order, and is Cisco financially stable enough to rely on as our long-term supplier?"
Response: {"query": "Our Cisco enterprise router is failing intermittently. What should we order, and is Cisco financially stable enough to rely on as our long-term supplier?", "domains": ["technology", "sec"], "is_cross_domain": true, "sub_queries": {"technology": "Evaluate Cisco router failure and compatible replacement parts.", "sec": "Analyze Cisco financial stability and supplier viability from SEC filings."}, "rationale": "Cross-domain query combining Cisco hardware failure and SEC financial stability.", "confidence": 0.92}

Example 6:
Query: "We are upgrading lab network switches with Cisco gear and want to understand Cisco's supply chain risk and the sustainability impact of the upgrade."
Response: {"query": "We are upgrading lab network switches with Cisco gear and want to understand Cisco's supply chain risk and the sustainability impact of the upgrade.", "domains": ["technology", "sec", "corporate_responsibility"], "is_cross_domain": true, "sub_queries": {"technology": "Assess Cisco switch upgrade specifications.", "sec": "Evaluate Cisco supply chain risks from SEC filings.", "corporate_responsibility": "Assess sustainability and environmental impact of switch upgrade."}, "rationale": "Spans network technology, SEC supply chain risks, and corporate sustainability.", "confidence": 0.94}
"""


def classify_llm(query: str) -> RoutingDecision:
    """LLM router using few-shot prompt with automatic fallback to rules."""
    prompt = f"""You are a multi-agent intent classification router for an enterprise consulting platform.
Classify the user query into one or more of these valid domains:
- "technology": Cisco/IBM/Google networking, hardware, cloud, specifications, router failures.
- "clinical": Agilent laboratory instruments, diagnostic equipment, clinical trial evidence.
- "sec": Cisco/Agilent SEC filings, 10-K reports, financial risks, regulatory disclosures.
- "corporate_responsibility": Food security, sustainability, ESG, SOFI reports, malnutrition.

Never use "cross_domain" in domains. Set is_cross_domain = true if len(domains) >= 2.

{_FEW_SHOT_EXAMPLES}

Classify this query:
"{query}"
"""
    try:
        decision = llm.complete_json(prompt, RoutingDecision, system="You are an expert enterprise query router.")
        if not decision.sub_queries or len(decision.sub_queries) != len(decision.domains):
            decision.sub_queries = decompose(decision)
        return decision
    except Exception as err:
        fallback = classify_rules(query)
        fallback.rationale = f"[Fallback to rules: {type(err).__name__}] {fallback.rationale}"
        return fallback


def classify(query: str) -> RoutingDecision:
    """Public entry point: uses LLM when live, rules when mock or on error."""
    if llm.is_mock():
        return classify_rules(query)
    return classify_llm(query)
