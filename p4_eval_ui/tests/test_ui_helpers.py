from p4_eval_ui.ui import theme
from p4_eval_ui.ui import tokens as T
from p4_eval_ui.ui.dashboard import SUMMARY_PREFIX, trim_summary
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
