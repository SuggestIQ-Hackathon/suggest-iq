import pytest

from core.mocks import MockDomainAgent
from core.schemas import ConsultingReport, DomainType
from p4_eval_ui.evaluation import explain


def _report(domains, context=None):
    findings = {d.value: MockDomainAgent(d).run("q", context) for d in domains}
    recs = [r for f in findings.values() for r in f.recommendations]
    return ConsultingReport(query="q", detected_domains=domains, executive_summary="s", domain_findings=findings,
                            consolidated_recommendations=recs, next_steps=["n"], measuring_impact_kpis=["k"], audit_trace={"a": 1})


@pytest.mark.parametrize("score,bucket", [(0.0, "Low"), (0.499, "Low"), (0.5, "Medium"), (0.749, "Medium"), (0.75, "High"), (1.0, "High")])
def test_bucket_thresholds(score, bucket):
    assert explain.confidence_bucket(score) == bucket


def test_information_request_banner_lists_missing_diagnostics_verbatim():
    view = explain.explain(_report([DomainType.TECHNOLOGY]))
    assert view.banner and "show tech-support (or equivalent instrument log)" in view.banner
    assert view.overall_confidence.endswith("(provisional)")
    assert any(w.startswith("Supplying:") for w in view.what_would_change_this_answer)
    assert view.recommendations[0].domain == "technology" and view.recommendations[0].evidence_count == 1


def test_no_banner_when_analysis_complete():
    view = explain.explain(_report([DomainType.SEC]))
    assert view.banner is None and view.domains[0].status == "ANALYSIS_COMPLETE"


def test_calibration_table_buckets():
    rows = [{"top_rec_confidence": 0.9, "top_rec_relevant": True}, {"top_rec_confidence": 0.8, "top_rec_relevant": False},
            {"top_rec_confidence": 0.2, "top_rec_relevant": False}, {"id": "no gold"}]
    table = {r["bucket"]: r for r in explain.calibration_table(rows)}
    assert table["High"]["n"] == 2 and table["High"]["observed_precision"] == 0.5
    assert table["Low"]["n"] == 1 and table["Medium"]["n"] == 0 and table["Medium"]["observed_precision"] is None
