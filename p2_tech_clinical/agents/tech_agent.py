"""Technology domain agent for Cisco and Google/GCP questions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from core.interfaces import BaseDomainAgent, Context
from core.rag_base import Hit, hits_to_citations
from core.schemas import DomainResponse, DomainType, RecommendationItem

from p2_tech_clinical.agents.symptoms import diagnostics_gate_passes, missing_diagnostics, parse
from p2_tech_clinical.knowledge.tech_kb import TechKB
from p2_tech_clinical.recommenders.hardware import recommend


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "p2_tech_clinical" / "recommenders" / "catalog" / "cisco_parts.json"


def _is_troubleshooting(query: str, symptom_count: int) -> bool:
    if symptom_count:
        return True
    return bool(
        re.search(
            r"\b(?:fault|failure|failed|failing|issue|problem|replace|replacement|troubleshoot|outage|error|down|crash|overheat)\b",
            query,
            re.I,
        )
    )


def _load_catalog() -> list[dict[str, Any]]:
    try:
        value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _diagnostic_recommendations(missing: list[str]) -> list[RecommendationItem]:
    recommendations = []
    for index, diagnostic in enumerate(missing, 1):
        recommendations.append(
            RecommendationItem(
                item_id=f"DIAG-TECH-{index:02d}",
                title=f"Collect {diagnostic}",
                category="Diagnostic Action",
                confidence_score=0.5,
                rationale=f"The diagnostic gate requires the missing check: {diagnostic}.",
                compatibility_notes="Collect the output for the affected equipment before selecting a replacement part.",
                estimated_impact="Estimated impact: improves evidence available for fault isolation.",
            )
        )
    return recommendations


def _usable_citation_count(citations: list) -> int:
    """Count citations with enough natural-language text to support a claim."""
    usable = 0
    for citation in citations:
        snippet = str(citation.snippet or "")
        lowered = snippet.lower()
        if any(marker in lowered for marker in ("<script", "</script", "nonce=", "javascript:", "display:none")):
            continue
        if len(re.findall(r"[A-Za-z]{3,}", snippet)) >= 12:
            usable += 1
    return usable


class TechAgent(BaseDomainAgent):
    """Answer technology questions from the P2 technology knowledge base."""

    domain = DomainType.TECHNOLOGY

    def __init__(self) -> None:
        self.kb = TechKB()

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        parsed = parse(query, None)
        return self.kb.search(query or "", k=k, vendor=parsed.vendor, model=parsed.product_model)

    def run(self, query: str, context: Context = None) -> DomainResponse:
        query_text = str(query or "")
        parsed = parse(query_text, context)
        model = parsed.product_model
        if isinstance(context, Mapping) and context.get("product_model"):
            model = str(context["product_model"])
        vendor = parsed.vendor
        troubleshooting = _is_troubleshooting(query_text, len(parsed.symptoms))

        if vendor == "IBM":
            return DomainResponse(
                domain=self.domain,
                status="INFORMATION_REQUEST",
                findings_summary="The P2 technology corpus does not contain grounded IBM source material.",
                missing_diagnostics_needed=["A supported Cisco or Google/GCP product, or IBM source material"],
                recommendations=[],
                citations=[],
                uncertainty_level="HIGH",
            )

        if troubleshooting and not diagnostics_gate_passes(self.domain, parsed):
            missing = missing_diagnostics(self.domain, parsed)
            hits = self.kb.search(query_text, k=5, vendor=vendor, model=model)
            citations = hits_to_citations(hits)
            hypotheses = parsed.symptoms or ["the reported technology issue"]
            summary = " ".join(f"Hypothesis: {symptom} requires diagnostic confirmation." for symptom in hypotheses)
            return DomainResponse(
                domain=self.domain,
                status="INFORMATION_REQUEST",
                findings_summary=summary,
                missing_diagnostics_needed=missing,
                recommendations=_diagnostic_recommendations(missing) if citations else [],
                citations=citations,
                uncertainty_level="HIGH",
            )

        hits = self.kb.search(query_text, k=5, vendor=vendor, model=model)
        citations = hits_to_citations(hits)
        if not hits:
            return DomainResponse(
                domain=self.domain,
                status="INFORMATION_REQUEST",
                findings_summary="No retrieved technology evidence supports a grounded answer for this query.",
                missing_diagnostics_needed=["Relevant Cisco or Google/GCP source evidence"],
                recommendations=[],
                citations=[],
                uncertainty_level="HIGH",
            )

        recommendations = []
        if troubleshooting and model and vendor in {"Cisco", None} and diagnostics_gate_passes(self.domain, parsed):
            recommendations = recommend(
                query_text,
                _load_catalog(),
                filters={"model": model, "vendor": vendor or "Cisco"},
                top_k=3,
            )
        status = "HYPOTHESIS" if troubleshooting else "ANALYSIS_COMPLETE"
        uncertainty = "LOW" if _usable_citation_count(citations) >= 2 else "MEDIUM"
        return DomainResponse(
            domain=self.domain,
            status=status,
            findings_summary="Technology evidence was retrieved for the requested question.",
            missing_diagnostics_needed=[],
            recommendations=recommendations,
            citations=citations,
            uncertainty_level=uncertainty,
        )
