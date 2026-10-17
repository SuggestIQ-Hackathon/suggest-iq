from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

APP = str(Path(__file__).resolve().parents[1] / "ui" / "dashboard.py")


def _click(at, label):
    next(b for b in at.button if b.label == label).click()


def test_dashboard_renders_on_mocks_and_runs_a_query(monkeypatch):
    monkeypatch.setenv("REAL_DOMAINS", "none")
    at = st_testing.AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.text_area(key="query").set_value("Our Cisco router has intermittent connectivity failures. Which parts should we order?")
    at = at.run()
    _click(at, "Get consulting recommendation")
    at = at.run()
    assert not at.exception
    assert any("Executive summary" in s.value for s in at.subheader)
    assert any("Provisional answer" in w.value for w in at.warning)  # no diagnostics -> banner
    assert len(at.tabs) == 4
