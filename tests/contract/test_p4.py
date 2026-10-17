"""P4 contract: metric functions have the agreed signatures and sane behaviour."""
import importlib

import pytest

from tests.helpers import not_implemented

pytestmark = pytest.mark.member("p4")


@pytest.fixture(scope="module")
def metrics():
    try:
        return importlib.import_module("p4_eval_ui.evaluation.metrics")
    except ModuleNotFoundError as err:
        if err.name and "p4_eval_ui" in err.name:
            not_implemented("p4_eval_ui.evaluation.metrics")
        raise


def test_routing_accuracy(metrics):
    pred = [{"technology"}, {"sec", "technology"}, {"clinical"}]
    gold = [{"technology"}, {"technology", "sec"}, {"sec"}]
    assert metrics.routing_accuracy(pred, gold) == pytest.approx(2 / 3)
    assert metrics.routing_accuracy(gold, gold) == 1.0


def test_ranking_metrics(metrics):
    assert metrics.hit_rate_at_k([["a", "b"], ["c", "d"]], [{"b"}, {"x"}], k=2) == pytest.approx(0.5)
    assert metrics.precision_at_k(["a", "b", "c"], {"a", "c"}, k=3) == pytest.approx(2 / 3)
    assert metrics.ndcg_at_k(["a", "b"], {"a": 3.0, "b": 1.0}, k=2) == pytest.approx(1.0)
    assert metrics.ndcg_at_k(["b", "a"], {"a": 3.0, "b": 1.0}, k=2) < 1.0
    assert metrics.ndcg_at_k(["z"], {"a": 1.0}, k=1) == 0.0


def test_run_benchmark_on_mocks(metrics):
    from core.registry import get_agents, load_manager
    from p4_eval_ui.evaluation import benchmark

    manager = load_manager(get_agents(real=[]))
    if manager is None:
        not_implemented("p1 ManagerAgent (needed by run_benchmark)")
    result = benchmark.run_benchmark(manager)
    for key in ("routing_accuracy", "retrieval_hit_rate", "recommendation_ndcg_at_3", "faithfulness", "per_query"):
        assert key in result, f"run_benchmark() result missing '{key}'"
