"""Clinical and Agilent domain agent backed only by local P2 evidence.

The agent has two modes: Agilent instrument matching/troubleshooting and
clinical literature/trial evidence. It does not diagnose patients or invent
instrument specifications; all evidence returned to the manager comes from
``ClinicalKB`` citations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from core.interfaces import BaseDomainAgent, Context
from core.rag_base import Hit, hits_to_citations
from core.schemas import DomainResponse, DomainType, RecommendationItem

from p2_tech_clinical.agents.symptoms import (
    diagnostics_gate_passes,
    missing_diagnostics,
    parse,
)
from p2_tech_clinical.knowledge.clinical_kb import ClinicalKB


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "p2_tech_clinical" / "recommenders" / "catalog" / "agilent_instruments.json"

_INSTRUMENT_TERMS = (
    "agilent", "instrument", "analyzer", "scanner", "pathology", "consumable",
    "accessory", "sample type", "throughput", "assay", "imaging", "seahorse",
    "nanozoomer", "artisan link pro", "special stains",
)
_LITERATURE_TERMS = (
    "clinical research", "research", "paper", "papers", "study", "studies",
    "clinical trial", "clinical trials", "trial", "trials", "nct", "evidence",
    "diabetes", "heart attack", "heart disease", "covid", "knee injury",
    "knee injuries", "intervention", "treatment", "outcome", "patient",
)
_MEDICAL_TERMS = (
    "diabetes", "heart attack", "heart disease", "covid", "knee injury",
    "knee injuries", "symptom", "symptoms", "test result", "diagnosis",
    "diagnostic", "treatment", "therapy", "patient", "medical condition",
)
_MODEL_ALIASES = {
    "seahorse": "Seahorse",
    "nanozoomer": "NanoZoomer",
    "artisan link pro": "Artisan Link Pro",
    "digital pathology": "Digital Pathology",
}
_TOPIC_ALIASES = {
    "diabetes": ("diabetes", "glycemic"),
    "covid": ("covid", "coronavirus"),
    "heart attack": ("heart", "cardiac", "hearattack"),
    "knee injuries": ("knee",),
    "knee injury": ("knee",),
}


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _has_term(query: str, terms: tuple[str, ...]) -> bool:
    lowered = str(query or "").lower()
    return any(term in lowered for term in terms)


def _is_medical_query(query: str) -> bool:
    return _has_term(query, _MEDICAL_TERMS)


def _disclaimer(query: str) -> str:
    if not _is_medical_query(query):
        return ""
    return (
        " This is not a diagnosis or treatment recommendation. Personal medical "
        "decisions should be discussed with a qualified healthcare professional. "
        "Informational only; not medical advice."
    )


def _load_catalog() -> list[dict[str, Any]]:
    try:
        value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _model_from_query(query: str, parsed_model: str | None, context: Context) -> str | None:
    if isinstance(context, Mapping) and context.get("product_model"):
        return str(context["product_model"])
    if parsed_model:
        return parsed_model
    lowered = str(query or "").lower()
    for alias, model in _MODEL_ALIASES.items():
        if alias in lowered:
            return model
    return None


def _is_instrument_question(query: str, model: str | None) -> bool:
    return bool(model) or _has_term(query, _INSTRUMENT_TERMS)


def _is_literature_question(query: str) -> bool:
    return _has_term(query, _LITERATURE_TERMS)


def _topic_for_query(query: str) -> tuple[str, ...]:
    lowered = str(query or "").lower()
    for topic, aliases in _TOPIC_ALIASES.items():
        if topic in lowered:
            return aliases
    return ()


def _topic_filtered_hits(query: str, hits: list[Hit]) -> list[Hit]:
    """Keep condition-specific results grounded in the matching local topic."""
    aliases = _topic_for_query(query)
    if not aliases:
        return hits
    filtered = []
    for hit in hits:
        metadata = hit.chunk.metadata
        searchable = " ".join(
            [str(metadata.get("source_doc", "")), str(metadata.get("model", ""))]
        ).lower()
        if any(alias in searchable for alias in aliases):
            filtered.append(hit)
    return filtered


def _is_troubleshooting(query: str, symptom_count: int) -> bool:
    return bool(symptom_count) or bool(
        re.search(
            r"\b(?:error|failure|failed|failing|fault|issue|problem|troubleshoot|maintenance|calibration|firmware|replacement|replace|inconsistent|drift)\b",
            str(query or ""),
            re.I,
        )
    )


def _citations(hits: list[Hit]) -> list:
    try:
        return hits_to_citations(hits)
    except (KeyError, TypeError, ValueError):
        return []


def _diagnostic_recommendations(missing: list[str]) -> list[RecommendationItem]:
    return [
        RecommendationItem(
            item_id=f"DIAG-CLINICAL-{number:02d}",
            title=f"Collect {diagnostic}",
            category="Diagnostic Action",
            confidence_score=0.5,
            rationale=f"The clinical troubleshooting gate requires the missing check: {diagnostic}.",
            compatibility_notes="Collect this evidence before selecting an instrument, accessory, or consumable.",
            estimated_impact="Estimated impact: improves evidence available for instrument fault isolation.",
        )
        for number, diagnostic in enumerate(missing, 1)
    ]


def _supported_by_hits(item: dict[str, Any], hits: list[Hit]) -> bool:
    source_tokens = _terms(str(item.get("source_doc", "")))
    name_tokens = _terms(" ".join(
        [str(item.get("name", "")), str(item.get("category", "")), " ".join(item.get("compatible_models", []))]
    ))
    for hit in hits:
        hit_source = _terms(hit.chunk.metadata.get("source_doc", ""))
        hit_text = _terms(hit.chunk.text)
        if len(source_tokens & hit_source) >= 2:
            return True
        if len(name_tokens & hit_text) >= 2:
            return True
    return False


def _instrument_recommendations(query: str, model: str | None, hits: list[Hit]) -> list[RecommendationItem]:
    catalog = _load_catalog()
    if not catalog or not hits:
        return []
    query_terms = _terms(query)
    best_evidence = max(0.0, min(1.0, max((float(hit.score) for hit in hits), default=0.0)))
    ranked: list[tuple[float, str, RecommendationItem]] = []
    for item in catalog:
        item_id = item.get("item_id")
        compatible = item.get("compatible_models")
        if not isinstance(item_id, str) or not isinstance(compatible, list):
            continue
        if model and model not in compatible:
            continue
        if not _supported_by_hits(item, hits):
            continue
        item_text = " ".join(
            [str(item.get("name", "")), str(item.get("category", "")), str(item.get("specs", "")), " ".join(map(str, compatible))]
        )
        overlap = len(query_terms & _terms(item_text)) / max(1, len(query_terms))
        model_match = 1.0 if model and model in compatible else 0.0
        score = 0.50 * best_evidence + 0.30 * model_match + 0.20 * overlap
        verified = bool(item.get("verified", False))
        if not verified:
            score *= 0.8
        score = max(0.0, min(1.0, score))
        source_doc = str(item.get("source_doc", "local Agilent catalog"))
        rationale = (
            f"Local evidence supports this candidate; catalog source: {source_doc}."
            + (" The catalog entry is unverified." if not verified else "")
        )
        ranked.append(
            (
                score,
                item_id,
                RecommendationItem(
                    item_id=item_id,
                    title=str(item.get("name", item_id)),
                    category=str(item.get("category", "instrument")),
                    confidence_score=score,
                    rationale=rationale,
                    compatibility_notes=(
                        "Compatible model listed in the local catalog: "
                        + ", ".join(map(str, compatible))
                    ),
                    estimated_impact="Estimated impact: prioritizes a locally evidenced Agilent candidate for investigation.",
                ),
            )
        )
    ranked.sort(key=lambda value: (-value[0], value[1]))
    return [item for _, _, item in ranked[:3]]


class ClinicalAgent(BaseDomainAgent):
    """Answer Agilent and local clinical-evidence questions conservatively."""

    domain = DomainType.CLINICAL

    def __init__(self) -> None:
        self.kb = ClinicalKB()

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        query_text = str(query or "")
        parsed = parse(query_text, None)
        model = _model_from_query(query_text, parsed.product_model, None)
        try:
            if _is_instrument_question(query_text, model) and not _is_literature_question(query_text):
                return self.kb.search(query_text, k=k, source_type="product_page")
            if _is_literature_question(query_text):
                hits = self.kb.search(query_text, k=k, source_type="paper")
                if len(hits) < k:
                    trial_hits = self.kb.search(query_text, k=k, source_type="trial")
                    hits.extend(trial_hits)
                    hits.sort(key=lambda hit: (-float(hit.score), hit.chunk.id))
                return _topic_filtered_hits(query_text, hits)[:k]
            return self.kb.search(query_text, k=k)
        except Exception:
            return []

    def _information_request(
        self,
        query: str,
        reason: str,
        missing: list[str],
        hits: list[Hit] | None = None,
        recommendations: list[RecommendationItem] | None = None,
    ) -> DomainResponse:
        citations = _citations(hits or [])
        return DomainResponse(
            domain=self.domain,
            status="INFORMATION_REQUEST",
            findings_summary=reason + _disclaimer(query),
            missing_diagnostics_needed=missing or ["Relevant local Agilent or clinical evidence"],
            recommendations=recommendations or [],
            citations=citations,
            uncertainty_level="HIGH",
        )

    def run(self, query: str, context: Context = None) -> DomainResponse:
        query_text = str(query or "").strip()
        if not query_text:
            return self._information_request(
                query_text,
                "Please provide an Agilent instrument question or a clinical research topic.",
                ["A specific instrument, study, trial, or clinical evidence topic"],
            )

        parsed = parse(query_text, context)
        model = _model_from_query(query_text, parsed.product_model, context)
        instrument_mode = _is_instrument_question(query_text, model) and not _is_literature_question(query_text)
        try:
            if instrument_mode:
                troubleshooting = _is_troubleshooting(query_text, len(parsed.symptoms))
                hits = self.kb.search(query_text, k=5, source_type="product_page")
                if troubleshooting and not diagnostics_gate_passes(self.domain, parsed):
                    missing = missing_diagnostics(self.domain, parsed)
                    return self._information_request(
                        query_text,
                        "Possible instrument causes remain hypotheses and require diagnostic confirmation.",
                        missing,
                        hits,
                        _diagnostic_recommendations(missing),
                    )
                if not hits:
                    return self._information_request(
                        query_text,
                        "No relevant local Agilent product evidence supports an instrument recommendation.",
                        ["Relevant local Agilent product evidence"],
                    )
                recommendations = _instrument_recommendations(query_text, model, hits)
                return DomainResponse(
                    domain=self.domain,
                    status="HYPOTHESIS" if troubleshooting else "ANALYSIS_COMPLETE",
                    findings_summary=(
                        "Local Agilent evidence was retrieved for instrument matching."
                        + (" Troubleshooting causes remain hypotheses." if troubleshooting else "")
                    ),
                    missing_diagnostics_needed=[],
                    recommendations=recommendations,
                    citations=_citations(hits),
                    uncertainty_level="MEDIUM" if troubleshooting else "LOW",
                )

            if _is_literature_question(query_text):
                hits = self.retrieve(query_text, k=5)
                if not hits:
                    return self._information_request(
                        query_text,
                        "The available local clinical sources do not support an answer to this question.",
                        ["Relevant local clinical paper or trial evidence"],
                    )
                return DomainResponse(
                    domain=self.domain,
                    status="ANALYSIS_COMPLETE",
                    findings_summary=(
                        "Local clinical papers and/or trial records were retrieved for review."
                        + _disclaimer(query_text)
                    ),
                    missing_diagnostics_needed=[],
                    recommendations=[],
                    citations=_citations(hits),
                    uncertainty_level="MEDIUM",
                )

            return self._information_request(
                query_text,
                "The query could not be matched to a supported local Agilent or clinical-evidence mode.",
                ["A supported Agilent instrument question or clinical research topic"],
            )
        except Exception:
            return self._information_request(
                query_text,
                "The available local clinical sources could not support a reliable response.",
                ["Relevant local evidence"],
            )
