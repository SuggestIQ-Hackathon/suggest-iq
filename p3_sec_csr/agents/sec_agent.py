"""SEC filing analysis agent for Cisco, Agilent, and Alphabet."""

from __future__ import annotations

import re

from core.interfaces import BaseDomainAgent, Context
from core.rag_base import Hit, hits_to_citations
from core.schemas import Citation, DomainResponse, DomainType, RecommendationItem
from p3_sec_csr.agents.evidence import source_marker, uncertainty_for
from p3_sec_csr.agents.risk_extractor import (
    CATEGORY_QUERIES,
    RiskFinding,
    extract_risks,
)
from p3_sec_csr.knowledge.sec_kb import SECKB

COMPANY_ALIASES = {
    "cisco": "Cisco",
    "agilent": "Agilent",
    "alphabet": "Alphabet",
    "google": "Alphabet",
}

# Questions about a company's current market position require live market data,
# which is intentionally outside this filing-only agent's approved corpus.
OUT_OF_SCOPE_PATTERNS = (
    r"\bstock price\b",
    r"\bshare price\b",
    r"\bmarket cap(?:italization)?\b",
    r"\bcurrent price\b",
    r"\btoday'?s price\b",
    r"\breal[ -]?time\b",
    r"\blatest news\b",
    r"\banalyst rating\b",
)

SEC_ANALYSIS_TERMS = (
    "annual report",
    "annual filing",
    "10-k",
    "sec filing",
    "filing",
    "risk",
    "supply chain",
    "supply-chain",
    "competitive",
    "competition",
    "regulatory",
    "operational",
    "operations",
    "revenue",
    "gross margin",
    "income",
    "financial",
    "compare",
    "comparison",
)


def _unique_citations(citations: list[Citation]) -> list[Citation]:
    seen = set()
    result = []
    for citation in citations:
        key = (citation.source_doc, citation.page, citation.snippet)
        if key not in seen:
            seen.add(key)
            result.append(citation)
    return result


def _truncate(text: str, limit: int = 380) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


def _metric_evidence(hits: list[Hit], phrase: str) -> tuple[str, Hit] | None:
    candidates = []
    for hit in hits:
        for sentence in re.split(r"(?<=[.!?])\s+", hit.chunk.text):
            cleaned = re.sub(r"\s+", " ", sentence).strip()
            if phrase in cleaned.lower() and len(cleaned) >= 45:
                comparison_terms = sum(
                    term in cleaned.lower()
                    for term in ("increase", "decrease", "compared", "fiscal")
                )
                candidates.append(
                    (
                        2
                        if cleaned.lower().startswith(f"total {phrase}")
                        else int(cleaned.lower().startswith(phrase)),
                        "quarter" not in cleaned.lower(),
                        comparison_terms,
                        len(re.findall(r"[$%0-9]", cleaned)),
                        cleaned,
                        hit,
                    )
                )
    if not candidates:
        return None
    selected = max(
        candidates, key=lambda row: (row[0], row[1], row[2], row[3], row[4])
    )
    return _truncate(selected[4]), selected[5]


class SECAgent(BaseDomainAgent):
    domain = DomainType.SEC

    def __init__(self):
        self.kb = SECKB()

    def _companies(self, query: str, context: Context) -> list[str]:
        found: list[str] = []
        lowered = query.lower()
        for alias, company in COMPANY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", lowered) and company not in found:
                found.append(company)
        if context:
            for raw in context.get("companies", []) or []:
                company = COMPANY_ALIASES.get(str(raw).lower())
                if company and company not in found:
                    found.append(company)
        return found

    def _latest_year(self, company: str) -> int:
        return max(
            entry["fiscal_year"]
            for entry in self.kb.manifest
            if entry["company"] == company
        )

    @staticmethod
    def _requested_year(query: str) -> int | None:
        """Return an explicitly requested fiscal year, when the user provides one."""
        match = re.search(r"\b(20\d{2})\b", query)
        return int(match.group(1)) if match else None

    def _has_fiscal_year(self, company: str, fiscal_year: int) -> bool:
        return any(
            entry["company"] == company and entry["fiscal_year"] == fiscal_year
            for entry in self.kb.manifest
        )

    @staticmethod
    def _is_in_scope(query: str) -> bool:
        """Return whether a question can be grounded in the local SEC filings."""
        lowered = query.lower()
        if any(re.search(pattern, lowered) for pattern in OUT_OF_SCOPE_PATTERNS):
            return False
        return any(term in lowered for term in SEC_ANALYSIS_TERMS)

    def _out_of_scope_response(self, companies: list[str]) -> DomainResponse:
        company_names = ", ".join(companies)
        return DomainResponse(
            domain=self.domain,
            status="ANALYSIS_COMPLETE",
            findings_summary=(
                f"The local SEC filing corpus does not support current market-data or "
                f"other out-of-scope questions about {company_names}. It can answer "
                "grounded questions about annual-filing risks, financial metrics, and comparisons."
            ),
            citations=self._coverage_citations(companies),
            uncertainty_level="HIGH",
        )

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        companies = self._companies(query, None)
        company = companies[0] if len(companies) == 1 else None
        year = self._requested_year(query)
        if year is None and company and "latest" in query.lower():
            year = self._latest_year(company)
        return self.kb.search(query, k=k, company=company, fiscal_year=year)

    def _risk_categories(self, query: str) -> list[str]:
        lowered = query.lower().replace("-", "_")
        categories = [category for category in CATEGORY_QUERIES if category in lowered]
        if "supply chain" in query.lower() and "supply_chain" not in categories:
            categories.append("supply_chain")
        if "competition" in lowered and "competitive" not in categories:
            categories.append("competitive")
        return categories or ["supply_chain", "competitive", "regulatory"]

    def _recommendations(self, findings: list[RiskFinding]) -> list[RecommendationItem]:
        recommendations = []
        for finding in findings[:3]:
            title = {
                "supply_chain": "Validate supplier resilience and alternatives",
                "competitive": "Review competitive differentiation assumptions",
                "regulatory": "Strengthen regulatory-change monitoring",
                "financial": "Stress-test financial exposure",
                "operational": "Exercise operational continuity plans",
            }[finding.category]
            recommendations.append(
                RecommendationItem(
                    item_id=f"SEC-{finding.company.upper()}-{finding.category.upper()}",
                    title=title,
                    category="Vendor Due Diligence"
                    if finding.category in {"financial", "competitive"}
                    else "Risk Mitigation",
                    confidence_score=round(
                        max(0.55, min(0.9, 0.55 + max(0.0, finding.retrieval_score))), 4
                    ),
                    rationale=(
                        f"Base confidence 0.55 plus retrieval relevance {max(0.0, finding.retrieval_score):.2f}; "
                        f"the action addresses the cited {finding.category.replace('_', ' ')} disclosure "
                        f"{source_marker(finding.citation)}."
                    ),
                    estimated_impact="Estimated reduction in exposure; validate through scenario analysis and owner review.",
                )
            )
        return recommendations

    def _coverage_citations(self, companies: list[str] | None = None) -> list[Citation]:
        companies = companies or sorted({entry["company"] for entry in self.kb.manifest})
        return [
            Citation(
                source_doc="sec_manifest.json",
                section="Corpus coverage",
                snippet=f'"company": "{company}",',
            )
            for company in companies
        ]

    def run(self, query: str, context: Context = None) -> DomainResponse:
        try:
            if not query.strip():
                return DomainResponse(
                    domain=self.domain,
                    status="INFORMATION_REQUEST",
                    findings_summary="A company and SEC-analysis question are required.",
                    missing_diagnostics_needed=[
                        "Company name",
                        "Risk, financial metric, or comparison question",
                    ],
                    uncertainty_level="HIGH",
                )
            companies = self._companies(query, context)
            if not companies:
                coverage = ", ".join(
                    sorted({entry["company"] for entry in self.kb.manifest})
                )
                return DomainResponse(
                    domain=self.domain,
                    status="ANALYSIS_COMPLETE",
                    findings_summary=f"The requested entity is outside the local SEC corpus, which covers {coverage}.",
                    citations=self._coverage_citations(),
                    uncertainty_level="HIGH",
                )

            if not self._is_in_scope(query):
                return self._out_of_scope_response(companies)

            lowered = query.lower()
            financial = any(
                term in lowered
                for term in ("revenue", "gross margin", "financial metric", "income")
            )
            citations: list[Citation] = []
            summaries: list[str] = []
            findings: list[RiskFinding] = []
            evidence_hits: list[Hit] = []
            missing_evidence: list[str] = []
            requested_year = self._requested_year(query)

            if financial:
                requested_metrics = [
                    metric
                    for metric in ("revenue", "gross margin", "income")
                    if metric in lowered
                ] or ["revenue", "gross margin", "income"]
                for company in companies:
                    if requested_year is not None and not self._has_fiscal_year(
                        company, requested_year
                    ):
                        missing_evidence.append(company)
                        citations.extend(self._coverage_citations([company]))
                        summaries.append(
                            f"{company}: the local SEC corpus does not contain an FY{requested_year} filing."
                        )
                        continue
                    year = requested_year or self._latest_year(company)
                    hits = self.kb.search(query, k=5, company=company, fiscal_year=year)
                    supported = [
                        evidence
                        for metric in requested_metrics
                        if (evidence := _metric_evidence(hits, metric)) is not None
                    ]
                    if supported:
                        selected_hits = [hit for _, hit in supported]
                        evidence_hits.extend(selected_hits)
                        citations.extend(hits_to_citations(selected_hits))
                        evidence = [
                            f"{sentence} {source_marker(hit)}"
                            for sentence, hit in supported
                        ]
                        summaries.append(
                            f"{company} FY{year}: {' '.join(evidence[:2])}"
                        )
                    else:
                        missing_evidence.append(company)
                        evidence_hits.extend(hits[:1])
                        citations.extend(hits_to_citations(hits[:1]))
                        summaries.append(
                            f"{company} FY{year}: the retrieved filing excerpts did not "
                            "contain a directly supporting sentence for the requested metric."
                        )
            else:
                for company in companies:
                    if requested_year is not None and not self._has_fiscal_year(
                        company, requested_year
                    ):
                        missing_evidence.append(company)
                        citations.extend(self._coverage_citations([company]))
                        summaries.append(
                            f"{company}: the local SEC corpus does not contain an FY{requested_year} filing."
                        )
                        continue
                    year = requested_year or self._latest_year(company)
                    company_findings: list[RiskFinding] = []
                    for category in self._risk_categories(query):
                        extracted = extract_risks(
                            company, category, self.kb, fiscal_year=year
                        )
                        if extracted:
                            company_findings.append(extracted[0])
                    findings.extend(company_findings)
                    citations.extend(finding.citation for finding in company_findings)
                    if company_findings:
                        evidence = "; ".join(
                            f"{f.statement} {source_marker(f.citation)}"
                            for f in company_findings
                        )
                        summaries.append(f"{company} FY{year}: {evidence}")
                    else:
                        missing_evidence.append(company)
                        summaries.append(
                            f"{company} FY{year}: no directly supporting risk-factor excerpt was retrieved."
                        )

            citations = _unique_citations(citations)
            if not citations:
                return DomainResponse(
                    domain=self.domain,
                    status="INFORMATION_REQUEST",
                    findings_summary="No supporting filing excerpt was retrieved for the requested analysis.",
                    missing_diagnostics_needed=["A more specific SEC filing question"],
                    uncertainty_level="HIGH",
                )
            return DomainResponse(
                domain=self.domain,
                status="ANALYSIS_COMPLETE",
                findings_summary=" ".join(summaries),
                recommendations=[] if financial else self._recommendations(findings),
                citations=citations,
                uncertainty_level=(
                    "HIGH"
                    if missing_evidence
                    else (
                        uncertainty_for(query, evidence_hits)
                        if financial
                        else ("LOW" if len(citations) >= 2 else "MEDIUM")
                    )
                ),
            )
        except Exception as error:  # noqa: BLE001 - agent boundary must never raise
            return DomainResponse(
                domain=self.domain,
                status="INFORMATION_REQUEST",
                findings_summary=f"SEC analysis could not complete: {error}",
                missing_diagnostics_needed=[
                    "Verify that the SEC archive and local index are available"
                ],
                uncertainty_level="HIGH",
            )
