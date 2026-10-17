"""P1 contract: core utilities + ManagerAgent behaviour with mock domain agents."""
import asyncio

import pytest

from core import llm
from core.rag_base import Chunk, VectorIndex, chunk_text, hits_to_citations
from core.registry import get_agents, load_manager
from core.schemas import ConsultingReport, DomainType, RoutingDecision
from tests.helpers import load_benchmark, not_implemented

pytestmark = pytest.mark.member("p1")


def test_llm_mock_mode():
    assert llm.is_mock()
    assert llm.complete("hello").startswith("[MOCK LLM]")
    with pytest.raises(llm.LLMMockMode):
        llm.complete_json("x", RoutingDecision)


def test_rag_base_roundtrip(tmp_path):
    idx = VectorIndex("t")
    idx.add(chunk_text("The Catalyst 8200 supports IPsec throughput and WAN interfaces. " * 5, "a.pdf", page=2, extra_meta={"vendor": "Cisco"}))
    idx.add(chunk_text("Food insecurity is driven by conflict, climate extremes and economic slowdowns. " * 5, "b.pdf", page=7))
    hits = idx.query("what drives food insecurity", k=2)
    assert hits[0].chunk.metadata["source_doc"] == "b.pdf"
    assert idx.query("router", k=5, where={"vendor": "Cisco"})[0].chunk.metadata["vendor"] == "Cisco"
    idx.save(tmp_path)
    again = VectorIndex.load(tmp_path)
    assert len(again) == len(idx)
    cites = hits_to_citations(hits)
    assert cites[0].page == 7 and cites[0].snippet
    with pytest.raises(ValueError):
        VectorIndex("x").add([Chunk(id="1", text="t", metadata={})])


@pytest.fixture(scope="module")
def manager():
    m = load_manager(get_agents(real=[]))
    if m is None:
        not_implemented("p1_orchestrator.agents.manager:ManagerAgent")
    return m


@pytest.mark.parametrize("item", load_benchmark(), ids=lambda b: b["id"])
def test_manager_contract(manager, item):
    rd = manager.classify(item["query"])
    assert isinstance(rd, RoutingDecision) and rd.query == item["query"]
    assert rd.domains and DomainType.CROSS_DOMAIN not in rd.domains
    assert rd.is_cross_domain == (len(rd.domains) >= 2)
    assert set(rd.sub_queries) <= {d.value for d in rd.domains}
    report = asyncio.run(manager.ahandle(item["query"]))
    assert isinstance(report, ConsultingReport) and report.query == item["query"]
    assert report.executive_summary.strip() and report.next_steps and report.measuring_impact_kpis
    assert set(report.domain_findings) == {d.value for d in report.detected_domains}
    assert isinstance(report.audit_trace, dict) and report.audit_trace
    if len(report.detected_domains) >= 2:
        assert report.cross_domain_synthesis and report.cross_domain_synthesis.strip()
    assert manager.handle(item["query"]).query == item["query"]
