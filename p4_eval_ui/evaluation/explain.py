"""Explainability layer. Owner: P4. Read-only over finished ConsultingReports; agents never import this."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from core.schemas import ConsultingReport, DomainResponse

HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.50


def confidence_bucket(score: float) -> str:
    return "High" if score >= HIGH_THRESHOLD else "Medium" if score >= MEDIUM_THRESHOLD else "Low"


class RecommendationExplanation(BaseModel):
    item_id: str
    title: str
    category: str
    confidence_score: float
    confidence_bucket: str
    why: str
    domain: Optional[str] = None
    evidence_count: int = 0
    evidence_sources: List[str] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)


class DomainStatusView(BaseModel):
    domain: str
    status: str
    uncertainty_level: str
    n_citations: int
    note: str


class ExplanationView(BaseModel):
    banner: Optional[str] = None  # shown prominently when evidence/diagnostics are missing
    overall_confidence: str = "n/a"
    recommendations: List[RecommendationExplanation] = Field(default_factory=list)
    domains: List[DomainStatusView] = Field(default_factory=list)
    what_would_change_this_answer: List[str] = Field(default_factory=list)


_STATUS_NOTE = {
    "INFORMATION_REQUEST": "Not enough evidence yet; more information is needed before any firm recommendation.",
    "HYPOTHESIS": "Plausible causes only; none is confirmed.",
    "CONFIRMED_FAULT": "Supplied diagnostics directly establish the fault.",
    "ANALYSIS_COMPLETE": "Analysis finished from the retrieved sources.",
}


def _owner_domain(item_id: str, findings: Dict[str, DomainResponse]) -> Optional[str]:
    for d, resp in findings.items():
        if any(r.item_id == item_id for r in resp.recommendations):
            return d
    return None


def explain(report: ConsultingReport) -> ExplanationView:
    findings = report.domain_findings
    missing: List[str] = []
    for resp in findings.values():
        for m in resp.missing_diagnostics_needed:
            if m not in missing:
                missing.append(m)
    high_unc = [d for d, r in findings.items() if r.uncertainty_level == "HIGH"]
    info_req = [d for d, r in findings.items() if r.status == "INFORMATION_REQUEST"]

    banner = None
    if info_req:
        banner = ("Provisional answer: " + ", ".join(info_req) + " needs more information before parts or actions can be "
                  "confirmed. Missing: " + "; ".join(missing) + ".")
    elif high_unc:
        banner = "High uncertainty in: " + ", ".join(high_unc) + ". Treat these findings as indicative only."

    recs: List[RecommendationExplanation] = []
    for rec in report.consolidated_recommendations:
        dom = _owner_domain(rec.item_id, findings)
        resp = findings.get(dom) if dom else None
        cites = resp.citations if resp else []
        sources = sorted({c.source_doc + (f" p.{c.page}" if c.page else "") for c in cites})
        caveats = []
        if not cites:
            caveats.append("No supporting citation attached.")
        if resp and resp.status != "ANALYSIS_COMPLETE":
            caveats.append(_STATUS_NOTE.get(resp.status, resp.status))
        if resp and resp.uncertainty_level == "HIGH":
            caveats.append("Source domain reported HIGH uncertainty.")
        if rec.compatibility_notes:
            caveats.append("Compatibility: " + rec.compatibility_notes)
        recs.append(RecommendationExplanation(
            item_id=rec.item_id, title=rec.title, category=rec.category, confidence_score=rec.confidence_score,
            confidence_bucket=confidence_bucket(rec.confidence_score), why=rec.rationale, domain=dom,
            evidence_count=len(cites), evidence_sources=sources, caveats=caveats,
        ))

    domains = [DomainStatusView(domain=d, status=r.status, uncertainty_level=r.uncertainty_level,
                                n_citations=len(r.citations), note=_STATUS_NOTE.get(r.status, r.status))
               for d, r in findings.items()]
    overall = "n/a"
    if recs:
        overall = confidence_bucket(sum(r.confidence_score for r in recs) / len(recs))
        if info_req:
            overall += " (provisional)"
    changes = [f"Supplying: {m}" for m in missing]
    changes += [f"Additional sources for {d} (currently HIGH uncertainty)" for d in high_unc if d not in info_req]
    return ExplanationView(banner=banner, overall_confidence=overall, recommendations=recs, domains=domains,
                           what_would_change_this_answer=changes)


def calibration_table(per_query: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Confidence vs observed relevance, from benchmark per_query rows that carry gold judgments.

    A row needs `top_rec_confidence` (float) and `top_rec_relevant` (bool). Returns one row per bucket.
    """
    buckets = {"Low": [], "Medium": [], "High": []}
    for row in per_query:
        c, rel = row.get("top_rec_confidence"), row.get("top_rec_relevant")
        if c is None or rel is None:
            continue
        buckets[confidence_bucket(c)].append((c, bool(rel)))
    out = []
    for name in ("Low", "Medium", "High"):
        items = buckets[name]
        out.append({
            "bucket": name, "n": len(items),
            "mean_confidence": (sum(c for c, _ in items) / len(items)) if items else None,
            "observed_precision": (sum(1 for _, r in items if r) / len(items)) if items else None,
        })
    return out
