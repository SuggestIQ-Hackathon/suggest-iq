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


_STOPWORDS = {"the", "and", "for", "from", "with", "which", "what", "does", "are", "our", "this", "that", "into", "about"}

_CLINICAL_QUERY_MARKERS = re.compile(
    r"\b(?:covid(?:-19)?|long\s+covid|coronavirus|heart\s+attack|myocardial\s+infarction|"
    r"myocardial\s+ischemia|cardiac|clinical\s+trial|trial\b|nct\d{8}|patient|disease|"
    r"biomarker|hepatic\s+glucose|pneumonia|dengue|wearable|iot\s+(?:based|based)?|"
    r"deep[- ]learning|medical\s+literature|clinical\s+literature)\b",
    re.I,
)


def _looks_like_clinical_literature(query: str) -> bool:
    """Fail closed when a clinical/literature query is accidentally sent to Tech."""
    return bool(_CLINICAL_QUERY_MARKERS.search(query or ""))


def _relevant_hits(query: str, hits: list[Hit]) -> list[Hit]:
    """Keep only evidence containing the query's product/content anchors.

    Hash retrieval is deterministic but approximate. This lexical gate prevents
    a nearby product document from being presented as an answer to a different
    model or unsupported identifier.
    """
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    content_tokens = query_tokens - _STOPWORDS
    anchors = {token for token in content_tokens if any(char.isdigit() for char in token)}
    anchors.update(token for token in content_tokens if token in {"asr", "isr", "gcp", "google", "ibm"})
    relevant: list[Hit] = []
    for hit in hits:
        metadata = hit.chunk.metadata
        searchable = " ".join(
            [str(hit.chunk.text or ""), str(metadata.get("source_doc", "")), str(metadata.get("vendor", "")), str(metadata.get("model", ""))]
        ).lower()
        searchable_tokens = set(re.findall(r"[a-z0-9]+", searchable))
        if anchors and not anchors.issubset(searchable_tokens):
            continue
        overlap = len(content_tokens & searchable_tokens)
        if overlap >= (1 if anchors else 2):
            relevant.append(hit)
    return relevant


def _evidence_summary(hits: list[Hit], prefix: str = "Technology evidence") -> str:
    """Build an extractive, citation-backed answer from retrieved chunks."""
    excerpts: list[str] = []
    seen: set[str] = set()
    for hit in hits[:5]:
        source = str(hit.chunk.metadata.get("source_doc", "local technology source"))
        text = re.sub(r"\s+", " ", str(hit.chunk.text or "")).strip()
        if not text:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        excerpt = next((sentence.strip() for sentence in sentences if len(re.findall(r"[A-Za-z]{3,}", sentence)) >= 8), text)
        if len(excerpt) > 280:
            excerpt = excerpt[:280].rstrip(" ,;:") + "..."
        key = f"{source}: {excerpt}"
        if key not in seen:
            seen.add(key)
            excerpts.append(f"{source} reports: {excerpt}")
    if not excerpts:
        return "No readable technology evidence was retrieved for the requested question."
    return f"{prefix}: " + " ".join(excerpts)


class TechAgent(BaseDomainAgent):
    """Answer technology questions from the P2 technology knowledge base."""

    domain = DomainType.TECHNOLOGY

    def __init__(self) -> None:
        self.kb = TechKB()

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        parsed = parse(query, None)
        hits = self.kb.search(query or "", k=max(k, 20), vendor=parsed.vendor, model=parsed.product_model)
        return _relevant_hits(query or "", hits)[:k]

    def run(self, query: str, context: Context = None) -> DomainResponse:
        query_text = str(query or "")
        parsed = parse(query_text, context)
        model = parsed.product_model
        if isinstance(context, Mapping) and context.get("product_model"):
            model = str(context["product_model"])
        vendor = parsed.vendor
        troubleshooting = _is_troubleshooting(query_text, len(parsed.symptoms))

        if _looks_like_clinical_literature(query_text) and not vendor and not model:
            return DomainResponse(
                domain=self.domain,
                status="INFORMATION_REQUEST",
                findings_summary=(
                    "This appears to be a clinical or medical-literature question, "
                    "not a Cisco or Google/GCP technology question."
                ),
                missing_diagnostics_needed=["Clinical-domain routing or clinical source evidence"],
                recommendations=[],
                citations=[],
                uncertainty_level="HIGH",
            )

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
            if not model:
                missing.insert(0, "router model")
            hits = _relevant_hits(query_text, self.kb.search(query_text, k=20, vendor=vendor, model=model))[:5]
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

        hits = _relevant_hits(query_text, self.kb.search(query_text, k=20, vendor=vendor, model=model))[:5]
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
        recommendation_text = query_text
        if isinstance(context, Mapping) and context.get("diagnostics"):
            recommendation_text += "\n" + str(context["diagnostics"])
        if troubleshooting and model and vendor in {"Cisco", None} and diagnostics_gate_passes(self.domain, parsed):
            recommendations = recommend(
                recommendation_text,
                _load_catalog(),
                filters={"model": model, "vendor": vendor or "Cisco"},
                top_k=3,
            )
        status = "HYPOTHESIS" if troubleshooting else "ANALYSIS_COMPLETE"
        uncertainty = "MEDIUM" if troubleshooting else ("LOW" if _usable_citation_count(citations) >= 2 else "MEDIUM")
        return DomainResponse(
            domain=self.domain,
            status=status,
            findings_summary=_evidence_summary(
                hits,
                prefix=("Technology hypotheses supported by retrieved evidence" if troubleshooting else "Technology answer from retrieved evidence"),
            ),
            missing_diagnostics_needed=[],
            recommendations=recommendations,
            citations=citations,
            uncertainty_level=uncertainty,
        )
