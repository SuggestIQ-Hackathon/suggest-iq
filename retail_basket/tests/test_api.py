import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from retail_basket import api  # noqa: E402


@pytest.fixture()
def client():
    api._service = None  # fresh model and counters per test
    return TestClient(api.app)


def test_health_and_items(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["n_orders"] == 1000 and h["n_items"] == 40
    items = client.get("/items").json()
    assert len(items) == 40 and {"sku", "name", "brand"} <= set(items[0])


def test_recommend_by_sku_or_name_returns_ranked_items_with_reasons(client):
    body = client.post("/recommend", json={"cart": ["D7050"], "k": 3}).json()
    assert body["status"] == "ok" and 1 <= len(body["recommendations"]) <= 3 and body["cart"] == ["D7050"]
    top = body["recommendations"][0]
    assert top["sku"] != "D7050" and top["reason"] and top["orders_with_both"] >= 2
    by_name = client.post("/recommend", json={"cart": ["Bosch D7050 Detector"], "k": 3}).json()
    assert by_name["recommendations"] == body["recommendations"]


def test_no_pattern_returns_an_empty_list_not_a_guess(client):
    skus = [i["sku"] for i in client.get("/items").json()]
    body = client.post("/recommend", json={"cart": skus[:6], "k": 5}).json()  # 6 items together never occur in 2-5 item orders
    assert body["status"] == "no_pattern" and body["recommendations"] == [] and body["message"]


def test_unknown_item_is_a_422_and_empty_cart_is_handled(client):
    assert client.post("/recommend", json={"cart": ["D7050", "NOPE"]}).status_code == 422
    assert client.post("/recommend", json={"cart": []}).json()["status"] == "empty_cart"
    assert client.post("/recommend", json={"cart": ["D7050"], "k": 0}).status_code == 422


def test_metrics_track_usage_and_retrain_bumps_the_version(client):
    client.post("/recommend", json={"cart": ["D7050"]})
    client.post("/recommend", json={"cart": ["NOPE"]})
    m = client.get("/metrics").json()
    assert m["requests"] == 2 and m["errors"] == 1 and m["avg_latency_ms"] >= 0
    assert client.post("/retrain").json()["model_version"] == m["model_version"] + 1
