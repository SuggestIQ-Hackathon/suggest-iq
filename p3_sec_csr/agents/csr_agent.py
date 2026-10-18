"""Corporate-responsibility agent grounded in the SOFI 2023/2024 reports."""

from __future__ import annotations

import re

from core.interfaces import BaseDomainAgent, Context
from core.rag_base import Hit, hits_to_citations
from core.schemas import Citation, DomainResponse, DomainType
from p3_sec_csr.agents.evidence import (
    anchor_recommendations,
    source_marker,
    uncertainty_for,
)
from p3_sec_csr.agents.query_normalization import normalize_query
from p3_sec_csr.knowledge.csr_kb import CSRKB
from p3_sec_csr.recommenders.strategy import TECHNOLOGY_INVESTMENT_TAG, recommend

AVAILABLE_YEARS = {2023, 2024}
CSR_QUERY_VOCABULARY = (
    "food",
    "security",
    "sustainability",
    "nutrition",
    "malnutrition",
    "agrifood",
    "hunger",
    "climate",
    "resilience",
    "affordability",
    "emissions",
    "carbon",
    "technology",
    "investment",
)
CSR_SCOPE_TERMS = (
    "food",
    "nutrition",
    "malnutrition",
    "hunger",
    "sustainability",
    "agrifood",
    "agriculture",
    "climate",
    "diet",
    "affordability",
    "emission",
    "carbon",
    "esg",
    "corporate responsibility",
    "csr",
    "sources of financing",
    "financing to end hunger",
    "synergies",
    "alignment",
)

# The SOFI reports are not a source for general-world facts. These explicit
# patterns prevent coincidental word matches (for example, a report discussion
# of financial capital and a country name) from being presented as an answer.
CSR_OUT_OF_SCOPE_PATTERNS = (
    r"\bcapital of\b",
    r"\bweather\b",
    r"\bsports?\b",
    r"\bpokemon\b",
)

CSR_TOPIC_STOPWORDS = {
    "about",
    "are",
    "does",
    "from",
    "have",
    "how",
    "is",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
}


def _expanded_query(query: str) -> str:
    lowered = query.lower()
    additions = []
    if "food security" in lowered:
        additions.append(
            "food insecurity hunger malnutrition healthy diets nutrition agrifood"
        )
    if "food insecurity" in lowered and any(
        term in lowered for term in ("reason", "driver", "cause")
    ):
        additions.append(
            "drivers conflict climate variability extremes economic slowdowns downturns inequality"
        )
    if any(term in lowered for term in ("war", "conflict", "humanitarian")):
        additions.append(
            "conflict humanitarian crisis acute food insecurity malnutrition nutrition"
        )
    if any(term in lowered for term in ("price", "afford", "inflation")):
        additions.append(
            "food prices inflation affordability healthy diet economic access"
        )
    return " ".join([query, *additions])


def _evidence_sentence(text: str, query: str, limit: int = 420) -> str:
    terms = {token for token in re.findall(r"[a-z]+", query.lower()) if len(token) > 4}
    cleaned = re.sub(
        r"(?:THE STATE OF FOOD SECURITY AND NUTRITION IN THE WORLD|FOOD SECURITY AND NUTRITION IN THE WORLD)\s*20\d{2}",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    sentences = [
        re.sub(r"\s+", " ", sentence).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
    ]
    sentences = [sentence for sentence in sentences if len(sentence) >= 70]
    if cleaned[:1].islower() and len(sentences) > 1:
        sentences = sentences[1:]
    if not sentences:
        return re.sub(r"\s+", " ", cleaned).strip()[:limit]
    selected = max(
        sentences,
        key=lambda sentence: (
            len(terms & set(re.findall(r"[a-z]+", sentence.lower()))),
            -sentences.index(sentence),
        ),
    )
    return selected[:limit].rstrip()


class CSRAgent(BaseDomainAgent):
    domain = DomainType.CSR

    def __init__(self):
        self.kb = CSRKB()

    @staticmethod
    def _requested_year(query: str) -> int | None:
        match = re.search(r"\b(20\d{2})\b", query)
        return int(match.group(1)) if match else None

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        query = normalize_query(query, CSR_QUERY_VOCABULARY)
        year = self._requested_year(query)
        return self.kb.search(
            _expanded_query(query),
            k=k,
            report_year=year if year in AVAILABLE_YEARS else None,
        )

    @staticmethod
    def _is_investment_question(query: str) -> bool:
        lowered = query.lower()
        return any(
            term in lowered
            for term in (
                "invest",
                "recommend",
                "technology",
                "action",
                "should we",
                "strategy",
            )
        )

    @staticmethod
    def _is_technology_investment_question(query: str) -> bool:
        lowered = query.lower()
        return "invest" in lowered and any(
            term in lowered
            for term in ("technology", "digital", "data", "infrastructure", "platform")
        )

    @staticmethod
    def _requests_company_esg_metric(query: str) -> bool:
        lowered = query.lower()
        metric_terms = (
            "scope 1",
            "scope 2",
            "scope 3",
            "carbon emissions",
            "carbon footprint",
            "greenhouse gas",
            "ghg emissions",
            "esg metric",
        )
        return any(term in lowered for term in metric_terms)

    @staticmethod
    def _is_in_scope(query: str) -> bool:
        lowered = query.lower()
        return any(term in lowered for term in CSR_SCOPE_TERMS)

    def _has_grounded_topic(self, query: str) -> bool:
        """Allow a copied SOFI heading when its meaningful words co-occur in evidence."""
        lowered = query.lower()
        if any(re.search(pattern, lowered) for pattern in CSR_OUT_OF_SCOPE_PATTERNS):
            return False
        terms = {
            token
            for token in re.findall(r"[a-z0-9]+", lowered)
            if len(token) > 3 and token not in CSR_TOPIC_STOPWORDS
        }
        if not terms:
            return False
        for hit in self.kb.search(query, k=5):
            evidence_terms = set(re.findall(r"[a-z0-9]+", hit.chunk.text.lower()))
            if terms.issubset(evidence_terms):
                return True
        return False

    def _out_of_scope_response(self) -> DomainResponse:
        return DomainResponse(
            domain=self.domain,
            status="ANALYSIS_COMPLETE",
            findings_summary=(
                "The local SOFI corpus covers food security, nutrition, sustainability, "
                "and agrifood systems. It does not support this unrelated question."
            ),
            uncertainty_level="HIGH",
        )

    def run(self, query: str, context: Context = None) -> DomainResponse:
        try:
            query = normalize_query(query, CSR_QUERY_VOCABULARY)
            if not query.strip():
                return DomainResponse(
                    domain=self.domain,
                    status="INFORMATION_REQUEST",
                    findings_summary="A food-security or sustainability question is required.",
                    missing_diagnostics_needed=[
                        "Question and, when relevant, report year"
                    ],
                    uncertainty_level="HIGH",
                )
            if self._requests_company_esg_metric(query):
                coverage_hits = self.kb.search(
                    "food security sustainability report scope and indicators", k=2
                )
                return DomainResponse(
                    domain=self.domain,
                    status="ANALYSIS_COMPLETE",
                    findings_summary=(
                        "The local SOFI corpus did not retrieve a directly supporting "
                        "company-level emissions or ESG metric for this request. A corporate "
                        "sustainability filing or verified emissions inventory is required."
                    ),
                    citations=hits_to_citations(coverage_hits),
                    uncertainty_level="HIGH",
                )
            if not self._is_in_scope(query) and not self._has_grounded_topic(query):
                return self._out_of_scope_response()
            year = self._requested_year(query)
            if year is not None and year not in AVAILABLE_YEARS:
                coverage_hits = self.kb.search(
                    "State of Food Security and Nutrition report", k=2
                )
                return DomainResponse(
                    domain=self.domain,
                    status="ANALYSIS_COMPLETE",
                    findings_summary=f"The local SOFI corpus does not contain a {year} report; only 2023 and 2024 are available.",
                    citations=hits_to_citations(coverage_hits),
                    uncertainty_level="HIGH",
                )

            retrieval_query = _expanded_query(query)
            hits = self.kb.search(retrieval_query, k=5, report_year=year)
            citations: list[Citation] = hits_to_citations(hits)
            if not hits:
                return DomainResponse(
                    domain=self.domain,
                    status="INFORMATION_REQUEST",
                    findings_summary="No supporting SOFI passage was retrieved for this question.",
                    missing_diagnostics_needed=[
                        "A more specific food-security or sustainability question"
                    ],
                    uncertainty_level="HIGH",
                )

            evidence_summary = " ".join(
                f"{_evidence_sentence(hit.chunk.text, retrieval_query)} {source_marker(hit)}"
                for hit in hits[:3]
            )
            prefix = f"SOFI {year} evidence" if year else "SOFI evidence"
            recommendations = (
                anchor_recommendations(
                    recommend(
                        " ".join(hit.chunk.text for hit in hits),
                        top_k=3,
                        required_tag=(
                            TECHNOLOGY_INVESTMENT_TAG
                            if self._is_technology_investment_question(query)
                            else None
                        ),
                    ),
                    hits,
                )
                if self._is_investment_question(query)
                else []
            )
            return DomainResponse(
                domain=self.domain,
                status="ANALYSIS_COMPLETE",
                findings_summary=f"{prefix}: {evidence_summary}",
                recommendations=recommendations,
                citations=citations,
                uncertainty_level=uncertainty_for(query, hits),
            )
        except Exception as error:  # noqa: BLE001 - agent boundary must never raise
            return DomainResponse(
                domain=self.domain,
                status="INFORMATION_REQUEST",
                findings_summary=f"CSR analysis could not complete: {error}",
                missing_diagnostics_needed=[
                    "Verify that FoodSecurity.zip and the local CSR index are available"
                ],
                uncertainty_level="HIGH",
            )
