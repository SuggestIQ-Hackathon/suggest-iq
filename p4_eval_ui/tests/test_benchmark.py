"""run_benchmark on a tiny stub manager defined here (no dependency on other members' code)."""
import json

from core.mocks import MockDomainAgent
from core.rag_base import Chunk, Hit
from core.registry import REAL_DOMAIN_LIST
from core.schemas import ConsultingReport, DomainType, RoutingDecision
from p4_eval_ui.evaluation import benchmark


class _Agent(MockDomainAgent):
    def retrieve(self, query, k=5):
        return [Hit(chunk=Chunk(id="c", text="t", metadata={"source_doc": "datasheet.pdf", "model": "Catalyst 8200"}), score=1.0)]


class StubManager:
    def __init__(self, route=("technology",), gate_ok=True):
        self.agents = {d: _Agent(d) for d in REAL_DOMAIN_LIST}
        self.route, self.gate_ok = route, gate_ok

    def classify(self, query):
        doms = [DomainType(r) for r in self.route]
        return RoutingDecision(query=query, domains=doms, is_cross_domain=len(doms) > 1, confidence=0.9 if query in ("router", "filing") else 0.1)

    def handle(self, query, context=None):
        rd = self.classify(query)
        findings = {d.value: self.agents[d].run(query, context) for d in rd.domains}
        recs = [r for f in findings.values() for r in f.recommendations]
        if not self.gate_ok:
            recs[0] = recs[0].model_copy(update={"category": "Replacement Part"})
        return ConsultingReport(query=query, detected_domains=rd.domains, executive_summary="s", domain_findings=findings,
                                consolidated_recommendations=recs, next_steps=["n"], measuring_impact_kpis=["k"],
                                audit_trace={"routing": rd.model_dump(), "agents": {d: {"real_or_mock": "mock"} for d in findings}, "total_ms": 5.0})


def _write(tmp_path):
    q = [
        {"id": "A", "query": "router", "expected_domains": ["technology"], "type": "single", "expected_sources": ["8200"], "expected_keywords": ["x"], "expected_status": "INFORMATION_REQUEST"},
        {"id": "B", "query": "filing", "expected_domains": ["sec"], "type": "single", "expected_sources": ["Cisco"], "expected_keywords": ["x"]},
    ]
    gold = {"A": {"MOCK-technology-001": 3}, "B": {"TODO-X": 3}}
    (tmp_path / "q.json").write_text(json.dumps(q))
    (tmp_path / "g.json").write_text(json.dumps(gold))
    return tmp_path / "q.json", tmp_path / "g.json"


def test_run_benchmark_numbers(tmp_path):
    qp, gp = _write(tmp_path)
    res = benchmark.run_benchmark(StubManager(), qp, gold_path=gp, edge_path=benchmark.EDGE_PATH)
    assert res["n_queries"] == 2
    assert res["routing_accuracy"] == 0.5  # A correct, B routed to technology instead of sec
    assert res["retrieval_hit_rate_by_domain"]["technology"] == 1.0  # model metadata contains 8200
    assert res["retrieval_hit_rate_by_domain"]["sec"] == 0.0
    assert res["retrieval_hit_rate"] == 0.5
    assert res["recommendation_ndcg_at_3"] == 1.0 and res["gold_coverage"]["queries_with_gold"] == 1  # placeholder gold skipped
    assert res["diagnostic_gate_compliance"] == 1.0  # mock asks for diagnostics and recommends no part
    assert res["out_of_scope_low_confidence_rate"] == 1.0
    assert res["agents_real"]["technology"] == "mock"
    for key in ("routing_accuracy", "retrieval_hit_rate", "recommendation_ndcg_at_3", "faithfulness", "per_query"):
        assert key in res


def test_gate_violation_detected_and_scorecard_written(tmp_path):
    qp, gp = _write(tmp_path)
    res = benchmark.run_benchmark(StubManager(gate_ok=False), qp, gold_path=gp)
    assert res["diagnostic_gate_compliance"] == 0.0
    out = benchmark.write_scorecard(res, tmp_path / "out")
    assert json.loads(out.read_text())["n_queries"] == 2 and (tmp_path / "out" / "per_query.csv").exists()
    assert "Routing accuracy" in benchmark.format_scorecard(res) and "MOCKS" in benchmark.format_scorecard(res)


def test_crashing_manager_is_recorded_not_raised(tmp_path):
    class Boom(StubManager):
        def handle(self, query, context=None):
            raise RuntimeError("boom")

    qp, gp = _write(tmp_path)
    res = benchmark.run_benchmark(Boom(), qp, gold_path=gp)
    assert res["errors"] == 2 and res["per_query"][0]["error"].startswith("RuntimeError")


def test_fallbacks_are_counted_and_flagged(tmp_path, monkeypatch):
    class FlakyLive(StubManager):
        def handle(self, query, context=None):
            r = super().handle(query, context)
            r.audit_trace["fallbacks_used"] = ["[Fallback to rules: RateLimitError] x"]
            return r

    qp, gp = _write(tmp_path)
    monkeypatch.setenv("LLM_MODE", "live")
    res = benchmark.run_benchmark(FlakyLive(), qp, gold_path=gp)
    assert res["queries_with_fallback"] == 2
    assert "NOT a clean live run" in benchmark.format_scorecard(res)
