from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(Path(__file__).resolve().parents[2] / "p4_eval_ui" / "ui" / "dashboard.py")


def _click(at, label):
    next(b for b in at.button if b.label.startswith(label)).click()


def test_home_toggle_opens_retail_checkout_and_back(monkeypatch):
    monkeypatch.setenv("REAL_DOMAINS", "none")
    at = st_testing.AppTest.from_file(APP, default_timeout=60).run()
    assert any(b.label == "Retail" for b in at.button)
    _click(at, "Retail")
    at = at.run()
    assert not at.exception and [t.label for t in at.tabs] == ["Checkout", "Model quality"]
    assert any("Your cart is empty" in m.value for m in at.markdown)
    _click(at, "Consulting")
    at = at.run()
    assert not at.exception and len(at.tabs) == 0 and any(b.label == "Ask Suggest IQ" for b in at.button)


def test_adding_an_item_shows_recommendations_that_update_with_the_cart(monkeypatch):
    monkeypatch.setenv("REAL_DOMAINS", "none")
    at = st_testing.AppTest.from_file(APP, default_timeout=60).run()
    _click(at, "Retail")
    at = at.run()
    at.selectbox(key="retail_pick").select_index(0)
    at = at.run()
    _click(at, "Add to cart")
    at = at.run()
    assert not at.exception and at.session_state["retail_cart"]
    first = at.session_state["retail_cart"][:]
    assert any("Bought together in" in m.value for m in at.markdown)  # a one-item cart always has history
    rec_button = next(b for b in at.button if b.key.startswith("rec_"))
    rec_button.click()
    at = at.run()
    assert len(at.session_state["retail_cart"]) == 2 and at.session_state["retail_cart"][0] == first[0]
    _click(at, "Clear cart")
    at = at.run()
    assert at.session_state["retail_cart"] == []
