import pytest

from retail_basket.service import RecommenderService, log_path


def test_log_order_then_retrain_learns_the_new_order():
    svc = RecommenderService()
    before = svc.info()
    assert before["logged_orders"] == 0 and before["pending_orders"] == 0
    svc.log_order(["D7050", "Bosch DS160 Detector"])  # SKU and name both accepted
    mid = svc.info()
    assert mid["logged_orders"] == 1 and mid["pending_orders"] == 1 and mid["n_orders"] == before["n_orders"]
    after = svc.retrain()
    assert after["n_orders"] == before["n_orders"] + 1 and after["pending_orders"] == 0 and after["model_version"] == before["model_version"] + 1
    assert log_path().exists()


def test_log_order_rejects_single_item_and_unknown_items():
    svc = RecommenderService()
    with pytest.raises(ValueError):
        svc.log_order(["D7050"])
    with pytest.raises(ValueError):
        svc.log_order(["D7050", "D7050"])  # duplicates do not make a 2-item order
    with pytest.raises(KeyError):
        svc.log_order(["D7050", "NOPE"])
    assert svc.logged_orders() == []


def test_popular_is_sorted_by_how_often_items_are_bought():
    svc = RecommenderService()
    top = svc.popular(3)
    counts = svc.model.item_count
    assert len(top) == 3 and counts[top[0]] >= counts[top[1]] >= counts[top[2]] >= max(c for s, c in counts.items() if s not in top)
