"""Executive consulting memo synthesizer. Owner: P1.

Merges domain responses into a unified ConsultingReport following strict McKinsey-style
consulting deliverables: Executive Summary, Trade-offs, Ranked Recommendations, Next Steps, and KPIs.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from core import llm
from core.schemas import (
    ConsultingReport,
    DomainResponse,
    DomainType,
    RecommendationItem,
    RoutingDecision,
)

_GENERIC_KPIS = {
    DomainType.TECHNOLOGY: [
        "Network availability target: 99.999% uptime",
        "Mean Time to Resolution (MTTR) reduction: -40%",
        "Interface packet error and CRC drop rate: < 0.001%",
    ],
    DomainType.CLINICAL: [
        "Diagnostic specimen throughput turnaround time (TAT): -25%",
        "Instrument uptime & assay reproducibility index: > 98%",
        "Laboratory consumables cost per test reduction: -15%",
    ],
    DomainType.SEC: [
        "Supply chain single-source concentration risk exposure: < 15%",
        "Capital expenditure payback period & NPV target alignment",
        "Regulatory & compliance disclosure audit readiness score: 100%",
    ],
    DomainType.CSR: [
        "Supply chain cold-chain loss reduction: -30%",
        "Data center energy efficiency (PUE) improvement: < 1.25",
        "Targeted community food security nutritional reach expansion",
    ],
}


def _build_trade_off(routing: RoutingDecision, responses: Dict[str, DomainResponse]) -> str:
    """Generate explicit cross-domain trade-off analysis."""
    domains = routing.domains
    domain_names = [d.value for d in domains]

    if DomainType.TECHNOLOGY in domains and DomainType.SEC in domains and DomainType.CSR in domains:
        return (
            "Cross-Domain Strategic Synthesis: Upgrading technical infrastructure (Technology) introduces capital "
            "expenditure and supplier dependency risks cited in SEC disclosures (SEC), but creates long-term energy "
            "efficiency and food-security supply-chain resilience (CSR). Strategic recommendation is a phased rollout "
            "conditioned on verified supplier stability and energy ROI benchmarks."
        )
    elif DomainType.CLINICAL in domains and DomainType.SEC in domains and DomainType.CSR in domains:
        return (
            "Cross-Domain Strategic Synthesis: Deploying high-throughput clinical diagnostic platforms (Clinical) addresses "
            "healthcare outcomes (CSR) but requires balancing capital allocation against supplier concentration and operational "
            "risks outlined in 2025 SEC filings (SEC). We advise structured vendor SLA guarantees to mitigate financial exposure."
        )
    elif DomainType.TECHNOLOGY in domains and DomainType.SEC in domains:
        return (
            "Cross-Domain Strategic Synthesis: Immediate procurement of enterprise hardware components resolves operational "
            "outage risks (Technology) but must be weighed against supplier supply chain volatility and inventory lead times "
            "disclosed in Cisco's recent SEC 10-K filings (SEC)."
        )
    elif DomainType.CLINICAL in domains and DomainType.SEC in domains:
        return (
            "Cross-Domain Strategic Synthesis: Instrument acquisition satisfies laboratory precision requirements (Clinical), "
            "yet requires scrutiny of Agilent's disclosed operational and competitive risk factors (SEC) before long-term service lock-in."
        )
    elif DomainType.TECHNOLOGY in domains and DomainType.CSR in domains:
        return (
            "Cross-Domain Strategic Synthesis: Modernizing network and cloud equipment delivers performance gains but must be "
            "benchmarked against corporate sustainability and power consumption targets."
        )
    else:
        return (
            f"Cross-Domain Strategic Synthesis: Multi-domain collaboration across {', '.join(domain_names)} balancing "
            "immediate operational implementation costs against strategic risk mitigation and institutional sustainability."
        )


def synthesize(
    query: str,
    routing: RoutingDecision,
    responses: Dict[str, DomainResponse],
    audit: Dict[str, Any],
) -> ConsultingReport:
    """Synthesize domain findings into a ConsultingReport."""
    # 1. Check for INFORMATION_REQUEST in any domain
    info_requests: List[str] = []
    for d_val, resp in responses.items():
        if resp.status == "INFORMATION_REQUEST":
            for diag in resp.missing_diagnostics_needed:
                if diag not in info_requests:
                    info_requests.append(diag)

    # 2. Executive Summary (3-5 sentences)
    # If any domain returned INFORMATION_REQUEST, state missing info first!
    sentences = []
    if info_requests:
        missing_str = ", ".join(info_requests[:3])
        sentences.append(
            f"CRITICAL DIAGNOSTIC PREREQUISITE: Preliminary analysis requires missing diagnostics ({missing_str}) "
            "before definitive hardware replacement or procurement can be certified."
        )
    
    # Lead recommendation / core domain findings
    for d in routing.domains:
        resp = responses.get(d.value)
        if resp:
            sentences.append(f"In the {d.value} domain: {resp.findings_summary.strip()}")

    sentences.append(
        "A prioritized action plan and measurable risk-mitigation framework are detailed below to ensure business continuity."
    )
    executive_summary = " ".join(sentences[:5])

    # 3. Consolidated Recommendations
    # Union of all recommendations, deduplicated by item_id, sorted by confidence_score desc
    seen_ids: Set[str] = set()
    all_recs: List[RecommendationItem] = []
    for resp in responses.values():
        for rec in resp.recommendations:
            if rec.item_id not in seen_ids:
                seen_ids.add(rec.item_id)
                all_recs.append(rec)

    all_recs.sort(key=lambda r: r.confidence_score, reverse=True)

    # 4. Cross-domain synthesis
    cross_synth: Optional[str] = None
    if routing.is_cross_domain:
        if not llm.is_mock():
            try:
                prompt = (
                    f"User Query: {query}\n"
                    f"Domains: {[d.value for d in routing.domains]}\n"
                    f"Findings: {[(d, r.findings_summary) for d, r in responses.items()]}\n\n"
                    "Provide a 2-3 sentence strategic cross-domain synthesis naming explicit trade-offs (capex vs risk vs sustainability)."
                )
                cross_synth = llm.complete(prompt, system="You are an enterprise management consultant.")
            except Exception:
                cross_synth = _build_trade_off(routing, responses)
        else:
            cross_synth = _build_trade_off(routing, responses)

    # 5. Next Steps
    # Ordered: 1) missing diagnostics from INFORMATION_REQUEST; 2) top recommendations; 3) preventive actions
    next_steps: List[str] = []
    for diag in info_requests:
        next_steps.append(f"Collect and verify required diagnostic telemetry: {diag}")

    for rec in all_recs[:3]:
        next_steps.append(f"Execute {rec.category.lower()}: {rec.title} ({rec.rationale})")

    if not next_steps:
        next_steps.append("Conduct comprehensive operational review and baseline validation.")
    next_steps.append("Establish ongoing monitoring and quarterly vendor risk assessment.")

    # 6. Measuring Impact KPIs (at least 3)
    kpis: List[str] = []
    for rec in all_recs:
        if rec.estimated_impact and rec.estimated_impact not in kpis:
            kpis.append(rec.estimated_impact)

    # Fill from generic KPIs per domain if fewer than 3
    for d in routing.domains:
        domain_kpis = _GENERIC_KPIS.get(d, [])
        for k in domain_kpis:
            if len(kpis) >= 4:
                break
            if k not in kpis:
                kpis.append(k)

    while len(kpis) < 3:
        kpis.append("Overall Enterprise Service Level Agreement (SLA) fulfillment: > 99.5%")

    # Assemble report
    report = ConsultingReport(
        query=query,
        detected_domains=routing.domains,
        executive_summary=executive_summary,
        domain_findings=responses,
        cross_domain_synthesis=cross_synth,
        consolidated_recommendations=all_recs,
        next_steps=next_steps,
        measuring_impact_kpis=kpis,
        audit_trace=audit,
    )
    return report
