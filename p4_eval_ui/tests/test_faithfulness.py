from core.schemas import Citation, ConsultingReport, DomainResponse, DomainType, RecommendationItem
from p4_eval_ui.evaluation import faithfulness


def _report(summary, rationale, snippet):
    resp = DomainResponse(
        domain=DomainType.TECHNOLOGY, status="ANALYSIS_COMPLETE", findings_summary=summary, uncertainty_level="LOW",
        citations=[Citation(source_doc="d.pdf", page=1, snippet=snippet)],
        recommendations=[RecommendationItem(item_id="X", title="X", category="Replacement Part", confidence_score=0.5,
                                            rationale=rationale, estimated_impact="est.")],
    )
    return ConsultingReport(query="q", detected_domains=[DomainType.TECHNOLOGY], executive_summary="s",
                            domain_findings={"technology": resp}, consolidated_recommendations=resp.recommendations,
                            next_steps=["n"], measuring_impact_kpis=["k"], audit_trace={"x": 1})


SNIPPET = "The Catalyst 8200 supports dual power supplies and modular network interface slots for WAN connectivity."


def test_supported_statement_scores_high():
    r = _report("The Catalyst 8200 supports dual power supplies and modular network interface slots.",
                "Dual power supplies keep WAN connectivity running on the Catalyst 8200.", SNIPPET)
    out = faithfulness.judge(r)
    assert out["score"] >= 0.9 and out["unsupported"] == []
    assert out["hallucination_rate"] == 1 - out["score"] and out["method"] == "lexical"


def test_unsupported_statement_is_flagged():
    r = _report("Quantum entanglement guarantees zero packet loss across continental backbones forever.",
                "Purchase titanium flux capacitors immediately for guaranteed reliability improvements.", SNIPPET)
    out = faithfulness.judge(r)
    assert out["score"] == 0.0 and len(out["unsupported"]) == 2


def test_no_citations_means_unsupported_and_empty_report_is_none():
    r = _report("The Catalyst 8200 supports dual power supplies and slots.", "Replace the power supply module today.", SNIPPET)
    r.domain_findings["technology"].citations.clear()
    assert faithfulness.judge(r)["score"] == 0.0
    r.domain_findings["technology"].findings_summary = "short"
    r.domain_findings["technology"].recommendations.clear()
    assert faithfulness.judge(r)["score"] is None
