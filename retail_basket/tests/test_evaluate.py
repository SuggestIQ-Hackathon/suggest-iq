import random

from retail_basket.evaluate import cross_validate, kfold, make_carts, signal_check, summarize
from retail_basket.model import BasketRecommender

BUNDLES = [["a1", "a2", "a3"], ["b1", "b2", "b3"], ["c1", "c2", "c3"], ["d1", "d2", "d3"]]


def structured(n=400, seed=0):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        out.append(list(rng.choice(BUNDLES)))  # customers buy a whole bundle: a real co-purchase signal
    return out


def random_baskets(n=400, seed=0):
    rng = random.Random(seed)
    items = [f"i{x}" for x in range(30)]
    return [rng.sample(items, rng.randint(2, 5)) for _ in range(n)]


def test_make_carts_are_prefixes_with_the_rest_as_targets():
    carts = make_carts([["x", "y", "z"]], seed=1)
    assert len(carts) == 2 and [len(c) for c, _ in carts] == [1, 2]
    for cart, targets in carts:
        assert not set(cart) & targets and set(cart) | targets == {"x", "y", "z"}


def test_kfold_partitions_every_order_exactly_once():
    data = [[str(i), "z"] for i in range(50)]
    seen = [tuple(b) for _, test in kfold(data, 5) for b in test]
    assert sorted(seen) == sorted(tuple(b) for b in data)


def test_abstaining_counts_as_a_miss_but_not_against_coverage_hit_rate():
    rows = [(["a"], {"a"}), ([], {"a"}), (["b"], {"a"}), ([], {"a"})]
    r = summarize(rows, k=5)
    assert r["coverage"] == 0.5 and r["hit@5"] == 0.25 and r["hit@5_covered"] == 0.5


def test_pipeline_detects_a_real_signal_and_beats_popularity():
    cv = cross_validate(structured(), lambda: BasketRecommender(min_support=3, min_count=2, min_lift=1.0), k=2, folds=4)
    assert cv["model"]["hit@2_covered"] > 0.95
    assert cv["model"]["hit@2"] > cv["popularity"]["hit@2"] + 0.3
    assert not signal_check(structured())["looks_random"]


def test_signal_check_flags_random_baskets():
    sc = signal_check(random_baskets(), shuffles=15)
    assert sc["looks_random"] and "indistinguishable" in sc["verdict"]
