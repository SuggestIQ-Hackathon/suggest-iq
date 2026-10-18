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


def _open_retail(monkeypatch):
    monkeypatch.setenv("REAL_DOMAINS", "none")
    at = st_testing.AppTest.from_file(APP, default_timeout=60).run()
    _click(at, "Retail")
    return at.run()


def test_empty_cart_suggests_popular_starters_and_browser_lists_products(monkeypatch):
    at = _open_retail(monkeypatch)
    assert not at.exception
    assert any("Customers often start with" in s.value for s in at.subheader)
    assert any(b.key == "add_0806-001" for b in at.button)  # cameras are listed first and any(b.key.startswith("pop_") for b in at.button)
    assert any("Browse products" in s.value for s in at.subheader)


def test_adding_an_item_shows_evidence_labelled_recommendations_that_update_with_the_cart(monkeypatch):
    at = _open_retail(monkeypatch)
    at.button(key="add_0806-001").click()
    at = at.run()
    assert not at.exception and at.session_state["retail_cart"] == ["0806-001"]
    assert any("Customers also bought" in s.value for s in at.subheader)
    assert any("evidence" in m.value and "past orders contain this cart" in m.value for m in at.markdown)
    assert any("of those orders" in m.value for m in at.markdown)
    next(b for b in at.button if b.key.startswith("rec_")).click()
    at = at.run()
    assert len(at.session_state["retail_cart"]) == 2 and at.session_state["retail_cart"][0] == "0806-001"
    _click(at, "Clear")
    at = at.run()
    assert at.session_state["retail_cart"] == []


def test_place_order_logs_it_clears_the_cart_and_retrain_picks_it_up(monkeypatch, tmp_path):
    at = _open_retail(monkeypatch)
    at.button(key="add_0806-001").click()
    at = at.run()
    assert next(b for b in at.button if b.key == "retail_order").disabled  # one item cannot teach anything
    next(b for b in at.button if b.key.startswith("rec_")).click()
    at = at.run()
    next(b for b in at.button if b.key == "retail_order").click()
    at = at.run()
    assert not at.exception and at.session_state["retail_cart"] == []
    assert any("Order placed" in m.value for m in at.markdown)
    assert (tmp_path / "orders_log.jsonl").read_text().count("\n") == 1
    assert any("Orders waiting" in m.value and ">1<" in m.value for m in at.markdown)  # the monitoring tile shows the pending order
    next(b for b in at.button if b.key == "retail_retrain").click()
    at = at.run()
    assert any("Retrained: model v" in m.value for m in at.markdown)
