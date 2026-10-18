"""Evidence-quality helpers shared by the SEC and CSR agents."""

from __future__ import annotations

import re

from core.rag_base import Hit
from core.schemas import Citation, RecommendationItem

_STOPWORDS = {
    "about",
    "annual",
    "could",
    "describe",
    "explain",
    "filing",
    "from",
    "latest",
    "list",
    "major",
    "most",
    "report",
    "should",
    "their",
    "what",
    "which",
    "with",
    "would",
}


def source_marker(source: Hit | Citation) -> str:
    """Return a compact, human-auditable source and location marker."""
    if isinstance(source, Hit):
        metadata = source.chunk.metadata
        source_doc = str(metadata["source_doc"])
        page = metadata.get("page")
        section = metadata.get("section")
    else:
        source_doc = source.source_doc
        page = source.page
        section = source.section
    parts = [source_doc]
    if page is not None:
        parts.append(f"p. {page}")
    if section:
        parts.append(str(section))
    return "[" + " · ".join(parts) + "]"


def evidence_coverage(query: str, hits: list[Hit]) -> float:
    """Fraction of meaningful query terms present in retrieved source text."""
    terms = {
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 3 and token not in _STOPWORDS
    }
    if not terms or not hits:
        return 0.0
    evidence_terms = set(
        re.findall(r"[a-z0-9]+", " ".join(hit.chunk.text for hit in hits).lower())
    )
    return len(terms & evidence_terms) / len(terms)


def uncertainty_for(query: str, hits: list[Hit]) -> str:
    """Calibrate uncertainty from evidence quantity and query-term coverage."""
    coverage = evidence_coverage(query, hits)
    if len(hits) >= 2 and coverage >= 0.5:
        return "LOW"
    if hits and coverage > 0.0:
        return "MEDIUM"
    return "HIGH"


def anchor_recommendations(
    recommendations: list[RecommendationItem], hits: list[Hit]
) -> list[RecommendationItem]:
    """Attach the most relevant retrieved source marker to every recommendation."""
    if not hits:
        return []
    anchored: list[RecommendationItem] = []
    for recommendation in recommendations:
        recommendation_terms = set(
            re.findall(
                r"[a-z0-9]+",
                f"{recommendation.title} {recommendation.rationale}".lower(),
            )
        )
        best_hit = max(
            hits,
            key=lambda hit: (
                len(
                    recommendation_terms
                    & set(re.findall(r"[a-z0-9]+", hit.chunk.text.lower()))
                ),
                hit.score,
            ),
        )
        marker = source_marker(best_hit)
        notes = recommendation.compatibility_notes or ""
        notes = f"{notes.rstrip()} Evidence source: {marker}".strip()
        anchored.append(
            recommendation.model_copy(
                update={
                    "rationale": f"{recommendation.rationale} Grounded in {marker}.",
                    "compatibility_notes": notes,
                }
            )
        )
    return anchored
