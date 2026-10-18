from p4_eval_ui.ui import theme
from p4_eval_ui.ui import tokens as T
from p4_eval_ui.ui.dashboard import BOILERPLATE, is_unrouted, SUMMARY_PREFIX, answer_status, is_blocked, split_rationale, strip_boilerplate, trim_summary
from p4_eval_ui.ui.flow import build_flow_html


def test_highlight_escapes_html_and_marks_terms():
    out = theme.highlight("<b>Cisco</b> router supply chain", ["router", "supply", "no"])
    assert "&lt;b&gt;" in out and "<mark>router</mark>" in out and "<mark>supply</mark>" in out and "<mark>chain" not in out


def test_query_terms_drop_short_and_stop_words():
    assert theme.query_terms("Which Cisco router should we order?") == ["Cisco", "router", "order"]


def test_trim_summary_only_when_banner_shown():
    s = SUMMARY_PREFIX + ": Preliminary analysis needs (a, b) first. In the technology domain: something."
    assert trim_summary(s, True) == "In the technology domain: something."
    assert trim_summary(s, False) == s
    assert trim_summary("Plain summary.", True) == "Plain summary."


def test_path_ribbon_lists_routed_domains_with_status_colour():
    trace = {"routing": {"domains": ["technology", "sec"]}, "agents": {"technology": {"status": "INFORMATION_REQUEST"}, "sec": {"status": "ANALYSIS_COMPLETE"}}}
    html = theme.path_ribbon(trace)
    assert "Technology" in html and "SEC" in html and T.WARNING in html and T.SUCCESS in html


def test_flow_html_has_controls_and_theme_ink():
    light, dark = build_flow_html(None, dark=False), build_flow_html(None, dark=True)
    assert 'id="pp"' in light and "pauseAnimations" in light and T.INK in light and T.INK_ON_DARK in dark


def test_answer_status_never_calls_a_hypothesis_complete():
    assert answer_status(["HYPOTHESIS"])[0] == "Hypothesis"
    assert answer_status(["ANALYSIS_COMPLETE", "HYPOTHESIS"])[0] == "Hypothesis"
    assert answer_status(["ANALYSIS_COMPLETE", "INFORMATION_REQUEST"])[0] == "Provisional"
    assert answer_status(["CONFIRMED_FAULT"])[0] == "Fault confirmed"
    assert answer_status(["ANALYSIS_COMPLETE"])[0] == "Complete"


def test_scoring_formula_is_moved_out_of_the_rationale():
    friendly, details = split_rationale("Score 0.17 = similarity 0.17, symptom match 0.00. Catalog entry is unverified.")
    assert "Score" not in friendly and details.startswith("Score")
    assert split_rationale("Power supply 1 reports FAILED.") == ("Power supply 1 reports FAILED.", None)


def test_flow_caption_mentions_mock_only_when_mock():
    real = {"routing": {"domains": ["technology"]}, "agents": {"technology": {"real_or_mock": "real", "status": "HYPOTHESIS"}}, "total_ms": 1, "mode": "mock"}
    mock = {"routing": {"domains": ["technology"]}, "agents": {"technology": {"real_or_mock": "mock", "status": "HYPOTHESIS"}}, "total_ms": 1, "mode": "mock"}
    assert "mock agents" not in build_flow_html(real, dark=False).split("<figcaption>")[1]
    assert "mock agents" in build_flow_html(mock, dark=False).split("<figcaption>")[1]


def test_is_blocked_only_when_every_agent_needs_more_information():
    assert is_blocked(["INFORMATION_REQUEST"]) and is_blocked(["INFORMATION_REQUEST", "INFORMATION_REQUEST"])
    assert not is_blocked(["INFORMATION_REQUEST", "ANALYSIS_COMPLETE"])  # cross-domain with one real answer keeps the full layout
    assert not is_blocked(["HYPOTHESIS"]) and not is_blocked([])


def test_strip_boilerplate_removes_the_canned_closing_sentence():
    assert strip_boilerplate("In the technology domain: Hypothesis: x. " + BOILERPLATE) == "In the technology domain: Hypothesis: x."
    assert strip_boilerplate("Plain summary.") == "Plain summary."


def test_status_for_no_analyses_is_not_complete():
    assert answer_status([])[0] == "No match"


def test_is_unrouted_reads_detected_domains():
    class R:
        detected_domains = []

    r = R()
    assert is_unrouted(r)
    r.detected_domains = ["technology"]
    assert not is_unrouted(r)
