"""P1 Unit Tests: Router accuracy, decomposition, dispatcher isolation, synthesizer rules."""
import asyncio
import pytest

from core.interfaces import BaseDomainAgent
from core.mocks import MockDomainAgent
from core.rag_base import Hit
from core.schemas import (
    ConsultingReport,
    DomainResponse,
    DomainType,
    RecommendationItem,
    RoutingDecision,
)
from p1_orchestrator.agents import dispatcher, router, synthesizer
from tests.helpers import load_benchmark


def test_router_accuracy_on_benchmark():
    benchmark = load_benchmark()
    correct = 0
    total = len(benchmark)
    for item in benchmark:
        rd = router.classify_rules(item["query"])
        actual_domains = set(d.value for d in rd.domains)
        expected_domains = set(item["expected_domains"])
        if actual_domains == expected_domains:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.80, f"Router accuracy was {accuracy:.2f}, expected >= 0.80"


def test_query_decomposition():
    cross_rd = RoutingDecision(
        query="Upgrade network switches with Cisco and check Agilent lab risk and sustainability.",
        domains=[DomainType.TECHNOLOGY, DomainType.CLINICAL, DomainType.CSR],
        is_cross_domain=True,
    )
    sub_queries = router.decompose(cross_rd)
    assert set(sub_queries.keys()) == {"technology", "clinical", "corporate_responsibility"}
    for sub_q in sub_queries.values():
        assert len(sub_q.strip()) > 0


class SlowOrFailingAgent(BaseDomainAgent):
    domain = DomainType.TECHNOLOGY

    def __init__(self, mode="fail"):
        self.mode = mode

    def run(self, query, context=None):
        if self.mode == "fail":
            raise RuntimeError("Hardware database connection dropped")
        elif self.mode == "sleep":
            import time
            time.sleep(2.0)
            return MockDomainAgent(DomainType.TECHNOLOGY).run(query, context)
        return MockDomainAgent(DomainType.TECHNOLOGY).run(query, context)

    def retrieve(self, query, k=5):
        return []


def test_dispatcher_isolation_and_resilience():
    agents = {
        DomainType.TECHNOLOGY: SlowOrFailingAgent(mode="fail"),
        DomainType.SEC: MockDomainAgent(DomainType.SEC),
    }
    rd = RoutingDecision(
        query="Test query",
        domains=[DomainType.TECHNOLOGY, DomainType.SEC],
        is_cross_domain=True,
        sub_queries={"technology": "sub1", "sec": "sub2"},
    )

    findings, traces = asyncio.run(dispatcher.dispatch(agents, rd, timeout_s=1.0))

    # Technology agent should have been safely caught without crashing SEC
    assert "technology" in findings
    assert "sec" in findings
    assert findings["technology"].status == "INFORMATION_REQUEST"
    assert findings["technology"].uncertainty_level == "HIGH"
    assert "failed" in findings["technology"].findings_summary
    assert findings["sec"].status == "ANALYSIS_COMPLETE"
    assert traces["technology"]["error"] is not None
    assert traces["sec"]["error"] is None


def test_synthesizer_missing_diagnostics_first():
    routing = RoutingDecision(
        query="Router failing",
        domains=[DomainType.TECHNOLOGY],
        is_cross_domain=False,
    )
    responses = {
        "technology": DomainResponse(
            domain=DomainType.TECHNOLOGY,
            status="INFORMATION_REQUEST",
            findings_summary="Missing logs.",
            missing_diagnostics_needed=["show tech-support", "CRC error count"],
            recommendations=[
                RecommendationItem(
                    item_id="REC-1",
                    title="Run diagnostic",
                    category="Diagnostic Action",
                    confidence_score=0.9,
                    rationale="Check optics",
                    estimated_impact="Isolates fault",
                )
            ],
            citations=[],
            uncertainty_level="HIGH",
        )
    }
    audit = {"test": True}

    report = synthesizer.synthesize("Router failing", routing, responses, audit)

    # Executive summary must mention missing diagnostics
    assert "CRITICAL DIAGNOSTIC PREREQUISITE" in report.executive_summary
    assert "show tech-support" in report.executive_summary

    # Next steps must put missing diagnostics first
    assert "show tech-support" in report.next_steps[0]
    assert "CRC error count" in report.next_steps[1]
    assert len(report.measuring_impact_kpis) >= 3
