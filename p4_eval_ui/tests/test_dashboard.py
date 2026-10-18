from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

APP = str(Path(__file__).resolve().parents[1] / "ui" / "dashboard.py")
QUESTION = "Our Cisco router has intermittent connectivity failures. Which parts should we order?"


def _app(monkeypatch):
    monkeypatch.setenv("REAL_DOMAINS", "none")
    return st_testing.AppTest.from_file(APP, default_timeout=60).run()


def _click(at, label):
    next(b for b in at.button if b.label == label).click()


def test_home_is_just_a_question_box(monkeypatch):
    at = _app(monkeypatch)
    assert not at.exception
    assert len(at.tabs) == 0  # no tabs before a question is asked
    assert any("Guiding enterprises from" in m.value and "decisions" in m.value for m in at.markdown)
    assert at.text_area(key="query") is not None
    assert any(b.label == "Ask Suggest IQ" for b in at.button)


def test_asking_shows_answer_flow_and_tabs(monkeypatch):
    at = _app(monkeypatch)
    at.text_area(key="query").set_value(QUESTION)
    _click(at, "Ask Suggest IQ")  # form values are committed together with the submit click
    at = at.run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Answer", "Evidence", "Trace"]
    assert any("More information needed" in m.value for m in at.markdown)  # no diagnostics -> checklist card
    assert any(b.label == "Add diagnostics and re-run" for b in at.button)
    # nothing could be answered yet (no logs): a focused view, with the routing tucked away instead of a big diagram
    titles = [x.value for x in at.subheader]
    assert "What we know so far" in titles
    assert not {"Recommendations", "Next steps", "How impact will be measured", "How Suggest IQ routed your question"} & set(titles)
    assert any("How your question was routed" in e.label for e in at.expander)


def test_example_chip_asks_in_one_click(monkeypatch):
    at = _app(monkeypatch)
    _click(at, "With logs attached")
    at = at.run()
    assert not at.exception
    assert len(at.tabs) == 3
    assert not any("More information needed" in m.value for m in at.markdown)  # logs were attached


def test_followup_diagnostics_clears_the_request(monkeypatch):
    at = _app(monkeypatch)
    at.text_area(key="query").set_value(QUESTION)
    _click(at, "Ask Suggest IQ")
    at = at.run()
    at.text_area(key="followup_diag").set_value("show environment: power supply 1 FAILED")
    at = at.run()
    _click(at, "Add diagnostics and re-run")
    at = at.run()
    assert not at.exception
    assert not any("More information needed" in m.value for m in at.markdown)


def test_new_question_returns_home(monkeypatch):
    at = _app(monkeypatch)
    _click(at, "Failing Cisco router")
    at = at.run()
    _click(at, "New question")
    at = at.run()
    assert not at.exception and len(at.tabs) == 0


def test_evaluation_reachable_from_home(monkeypatch):
    at = _app(monkeypatch)
    _click(at, "Evaluation")
    at = at.run()
    assert not at.exception
    assert any(s.value == "Evaluation" for s in at.subheader)


def test_answer_comes_before_how_it_was_routed(monkeypatch):
    at = _app(monkeypatch)
    _click(at, "With logs attached")  # logs supplied, so agents can answer and the full layout is shown
    at = at.run()
    titles = [s.value for s in at.subheader]
    assert titles.index("Executive summary") < titles.index("Recommendations") < titles.index("Next steps") < titles.index("How Suggest IQ routed your question")


def test_navbar_is_on_every_screen_with_the_app_switch(monkeypatch):
    at = _app(monkeypatch)
    labels = lambda: {b.label for b in at.button}  # noqa: E731
    assert {"Consulting", "Retail", "Evaluation"} <= labels()  # home
    _click(at, "Failing Cisco router")
    at = at.run()
    assert {"Consulting", "Retail", "Evaluation", "New question"} <= {b.label for b in at.button}  # results
    _click(at, "Retail")
    at = at.run()
    assert {"Consulting", "Retail"} <= {b.label for b in at.button} and "Evaluation" not in {b.label for b in at.button}  # retail
    _click(at, "Consulting")
    at = at.run()
    assert len(at.tabs) == 3  # back on the consulting result the user left, not reset


def test_full_layout_returns_once_diagnostics_are_supplied(monkeypatch):
    at = _app(monkeypatch)
    _click(at, "With logs attached")
    at = at.run()
    titles = [x.value for x in at.subheader]
    assert "Executive summary" in titles and "Recommendations" in titles and "How Suggest IQ routed your question" in titles


def _unrouted_report():
    from core.schemas import ConsultingReport

    kpi = "Overall Enterprise Service Level Agreement (SLA) fulfillment: > 99.5%"
    return ConsultingReport(query="sjsu", detected_domains=[], executive_summary="A prioritized action plan is detailed below.", domain_findings={},
                            consolidated_recommendations=[], next_steps=["Conduct comprehensive operational review."], measuring_impact_kpis=[kpi, kpi, kpi],
                            audit_trace={"routing": {"domains": [], "confidence": 0.9}, "agents": {}, "mode": "live", "total_ms": 5.0, "fallbacks_used": []})


def test_question_matched_to_no_specialist_gets_a_helpful_view_not_an_empty_report(monkeypatch):
    monkeypatch.setenv("REAL_DOMAINS", "none")
    at = st_testing.AppTest.from_file(APP, default_timeout=60)
    at.session_state["report"] = _unrouted_report()
    at.session_state["view"] = "result"
    at = at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "No specialist matched this question" in text and "We couldn\'t tell what you want to decide" in text
    titles = [s.value for s in at.subheader]
    assert not {"Executive summary", "Recommendations", "Next steps", "How impact will be measured", "How Suggest IQ routed your question"} & set(titles)
    assert "0 of 0" not in text
    assert at.text_area(key="rephrase_text").value == "sjsu" and any(b.key == "rephrase_go" for b in at.button)
    assert sum(1 for b in at.button if b.key.startswith("un_")) == 3  # example chips offered
    at.text_area(key="rephrase_text").set_value("Which parts should we order for our failing Cisco router?")
    at = at.run()
    next(b for b in at.button if b.key == "rephrase_go").click()
    at = at.run()
    assert not at.exception and at.session_state["report"].query.startswith("Which parts should we order")  # re-asked
