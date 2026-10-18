from __future__ import annotations

from core.rag_base import Chunk, Hit
from core.schemas import DomainType

from p2_tech_clinical.agents.tech_agent import TechAgent


class FakeTechKB:
    def __init__(self):
        self.hit = Hit(
            chunk=Chunk(
                id="fixture#1",
                text="Catalyst 8200 interface options support WAN connectivity.",
                metadata={"source_doc": "fixture-catalyst-8200.pdf", "page": 1, "vendor": "Cisco", "model": "Catalyst 8200"},
            ),
            score=0.9,
        )

    def search(self, query, k=5, vendor=None, model=None):
        return [self.hit][:k]


def test_tech_agent_returns_cited_analysis_for_answerable_query():
    agent = TechAgent()
    agent.kb = FakeTechKB()
    response = agent.run("Which Cisco Catalyst 8200 interface options are available for WAN connectivity?")
    assert response.domain == DomainType.TECHNOLOGY
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.citations[0].source_doc == "fixture-catalyst-8200.pdf"


def test_tech_agent_requests_diagnostics_without_replacement_parts():
    agent = TechAgent()
    agent.kb = FakeTechKB()
    response = agent.run("Our Cisco Catalyst 8200 has intermittent connectivity failures")
    assert response.status == "INFORMATION_REQUEST"
    assert response.missing_diagnostics_needed
    assert all(item.category != "Replacement Part" for item in response.recommendations)
    assert all("hypothesis" in response.findings_summary.lower() for _ in [0])


def test_tech_agent_can_recommend_only_after_diagnostics_gate():
    agent = TechAgent()
    agent.kb = FakeTechKB()
    diagnostics = """
    show tech-support output; show logging; show interfaces counters CRC zero;
    show environment; show platform hardware status; show version;
    optic DOM readings
    """
    response = agent.run(
        "Our Cisco Catalyst 8200 has packet loss; which replacement part should we investigate?",
        {"diagnostics": diagnostics},
    )
    assert response.status == "HYPOTHESIS"
    assert response.citations
    assert response.recommendations
    assert all(item.item_id.startswith("CISCO-") for item in response.recommendations)


def test_tech_agent_retrieve_returns_hits():
    agent = TechAgent()
    agent.kb = FakeTechKB()
    hits = agent.retrieve("Cisco Catalyst 8200 WAN", k=1)
    assert len(hits) == 1
    assert isinstance(hits[0], Hit)


def test_tech_agent_does_not_mark_markup_only_evidence_low_confidence():
    agent = TechAgent()
    agent.kb = FakeTechKB()
    response = agent.run("What Cisco Catalyst 8200 interface options are available?")
    response.citations[0].snippet = '<script nonce="x">tracking()</script>'
    # Re-run with a KB that returns markup-only snippets to exercise the guard.
    class MarkupKB(FakeTechKB):
        def search(self, query, k=5, vendor=None, model=None):
            hit = Hit(
                chunk=Chunk(
                    id="markup#1",
                    text='<script nonce="x">tracking()</script>',
                    metadata={"source_doc": "page.html", "vendor": "Cisco", "model": "Catalyst 8200"},
                ),
                score=0.9,
            )
            return [hit][:k]

    agent.kb = MarkupKB()
    response = agent.run("Which Cisco Catalyst 8200 interface options are available?")
    assert response.uncertainty_level == "MEDIUM"
