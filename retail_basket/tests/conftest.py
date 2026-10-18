import pytest


@pytest.fixture(autouse=True)
def isolated_order_log(tmp_path, monkeypatch):
    """Orders placed during tests go to a temp file, never into the real data/ folder."""
    monkeypatch.setenv("RETAIL_ORDERS_LOG", str(tmp_path / "orders_log.jsonl"))
