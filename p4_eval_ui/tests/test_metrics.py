import math

import pytest

from p4_eval_ui.evaluation import metrics as m


def test_routing_accuracy_edges():
    assert m.routing_accuracy([], []) == 0.0
    assert m.routing_accuracy([{"a"}], [{"a"}]) == 1.0
    assert m.routing_accuracy([{"a", "b"}], [{"a"}]) == 0.0  # extra domain is wrong (exact set)
    with pytest.raises(ValueError):
        m.routing_accuracy([{"a"}], [])


def test_hit_rate_and_precision_edges():
    assert m.hit_rate_at_k([], [], 3) == 0.0
    assert m.hit_rate_at_k([["a", "b", "c"]], [{"c"}], k=2) == 0.0  # outside top-k
    assert m.hit_rate_at_k([["a", "b", "c"]], [{"c"}], k=5) == 1.0  # k larger than list
    assert m.precision_at_k([], {"a"}, 3) == 0.0
    assert m.precision_at_k(["a"], {"a"}, 3) == pytest.approx(1 / 3)  # short list is penalised
    assert m.precision_at_k(["a"], {"a"}, 0) == 0.0


def test_ndcg_values():
    gains = {"a": 3.0, "b": 2.0, "c": 0.0}
    assert m.ndcg_at_k(["a", "b"], gains, 2) == pytest.approx(1.0)
    swapped = m.ndcg_at_k(["b", "a"], gains, 2)
    expected = (2 / 1 + 3 / math.log2(3)) / (3 / 1 + 2 / math.log2(3))
    assert swapped == pytest.approx(expected)
    assert m.ndcg_at_k([], gains, 3) == 0.0
    assert m.ndcg_at_k(["a"], {}, 3) == 0.0
    assert m.ndcg_at_k(["a"], {"a": 1.0}, 0) == 0.0


def test_mrr():
    assert m.mean_reciprocal_rank([["x", "a"], ["b"]], [{"a"}, {"zz"}]) == pytest.approx(0.25)
    assert m.mean_reciprocal_rank([], []) == 0.0


def test_confusion_and_prf():
    pred = [{"t"}, {"t", "s"}, set()]
    gold = [{"t"}, {"t"}, {"s"}]
    cm = m.confusion_matrix(pred, gold, ["t", "s"])
    assert cm["t"]["t"] == 2 and cm["t"]["s"] == 1
    assert cm["s"]["(none)"] == 1
    prf = m.per_label_prf(pred, gold, ["t", "s"])
    assert prf["t"]["recall"] == 1.0 and prf["t"]["precision"] == 1.0
    assert prf["s"]["precision"] == 0.0 and prf["s"]["recall"] == 0.0
