"""The contract every DomainAgent must satisfy. Used on mocks (harness) and on real agents. Owner: P1."""
import asyncio
import time

from core.rag_base import Hit
from core.schemas import DomainResponse, DomainType

DIAG_DOMAINS = {DomainType.TECHNOLOGY, DomainType.CLINICAL}
MAX_SECONDS = 30


def check_response(resp, domain: DomainType, label: str = "") -> None:
    assert isinstance(resp, DomainResponse), f"{label}: run() must return DomainResponse, got {type(resp)}"
    DomainResponse.model_validate(resp.model_dump())  # re-validate
    assert resp.domain == domain, f"{label}: response.domain={resp.domain} but agent domain={domain}"
    assert resp.findings_summary.strip(), f"{label}: findings_summary is empty"
    for r in resp.recommendations:
        assert 0.0 <= r.confidence_score <= 1.0
        assert r.rationale.strip() and r.estimated_impact.strip()
    if resp.status in ("CONFIRMED_FAULT", "HYPOTHESIS", "ANALYSIS_COMPLETE") or resp.recommendations:
        assert resp.citations, f"{label}: status={resp.status} with recommendations requires >=1 citation"
    for c in resp.citations:
        assert c.snippet.strip() and c.source_doc.strip(), f"{label}: citation needs source_doc and snippet"
    if resp.status == "INFORMATION_REQUEST":
        assert resp.missing_diagnostics_needed, f"{label}: INFORMATION_REQUEST must list missing_diagnostics_needed"
    if resp.status == "CONFIRMED_FAULT":
        assert resp.uncertainty_level != "HIGH", f"{label}: a CONFIRMED_FAULT cannot have HIGH uncertainty"


def check_underspecified(resp) -> None:
    """Tech/Clinical must NOT confirm a fault or push parts when no diagnostics were supplied."""
    assert resp.status != "CONFIRMED_FAULT", "Must not confirm a fault without diagnostics"
    assert resp.missing_diagnostics_needed, "Must request the missing diagnostics"
    assert not any(r.category == "Replacement Part" for r in resp.recommendations), \
        "Must not recommend replacement parts before diagnostics are provided"
    assert resp.uncertainty_level in ("MEDIUM", "HIGH")


def check_agent(agent, queries: dict) -> None:
    domain = agent.domain
    t0 = time.time()
    resp = agent.run(queries["answerable"], None)
    check_response(resp, domain, "answerable/sync")
    assert time.time() - t0 < MAX_SECONDS, f"run() took longer than {MAX_SECONDS}s in mock mode"
    check_response(asyncio.run(agent.arun(queries["answerable"], None)), domain, "answerable/async")
    if domain in DIAG_DOMAINS and "underspecified" in queries:
        resp = agent.run(queries["underspecified"], None)
        check_response(resp, domain, "underspecified")
        check_underspecified(resp)
        with_diag = agent.run(queries["underspecified"], {"diagnostics": "show tech-support output: no errors found; uptime 90 days"})
        check_response(with_diag, domain, "with-diagnostics")
    hits = agent.retrieve(queries["answerable"], k=3)
    assert isinstance(hits, list) and len(hits) <= 3 and all(isinstance(h, Hit) for h in hits), "retrieve() must return <=k Hit objects"
    assert agent.run("", None) is not None, "run() must not raise on empty input"
