import pytest

from retail_basket.model import BasketRecommender, PopularityBaseline

# 10 orders: A+B together 6 times (A alone with C twice), B appears 8 times overall, D is a popular loner
ORDERS = [["A", "B"]] * 6 + [["A", "C"]] * 2 + [["B", "D"]] * 2


def model(**kw):
    kw.setdefault("min_support", 1)
    kw.setdefault("min_count", 1)
    kw.setdefault("min_lift", 0.0)
    return BasketRecommender(**kw).fit(ORDERS)


def test_confidence_lift_and_support_are_computed_exactly():
    res = model().recommend(["A"], k=5)
    assert res.status == "ok" and res.cart_support == 8
    b = next(r for r in res.recs if r.sku == "B")
    assert b.count == 6 and b.confidence == pytest.approx(6 / 8)
    assert b.lift == pytest.approx((6 / 8) / (8 / 10))  # B is in 8 of 10 orders
    assert [r.sku for r in res.recs] == ["B", "C"]  # ranked by confidence


def test_cart_order_does_not_matter_and_cart_items_are_never_recommended():
    m = BasketRecommender(min_support=1, min_count=1, min_lift=0).fit([["A", "B", "C"]] * 3 + [["A", "B", "D"]])
    assert [r.sku for r in m.recommend(["A", "B"]).recs] == [r.sku for r in m.recommend(["B", "A"]).recs]
    assert all(r.sku not in ("A", "B") for r in m.recommend(["A", "B"]).recs)


def test_unseen_combination_returns_no_pattern_and_nothing():
    res = model().recommend(["C", "D"])  # never bought together
    assert res.status == "no_pattern" and res.recs == [] and "never appears" in res.message


def test_too_rare_combination_returns_no_pattern():
    res = model(min_support=3).recommend(["C"])  # C is in only 2 orders
    assert res.status == "no_pattern" and "only 2" in res.message


def test_lift_threshold_filters_items_that_are_just_popular():
    res = BasketRecommender(min_support=1, min_count=1, min_lift=1.0).fit(ORDERS).recommend(["A"])
    assert [r.sku for r in res.recs] == ["C"]  # B has lift 0.94 < 1: popular, not specifically associated with A


def test_empty_cart_and_unknown_items():
    assert model().recommend([]).status == "empty_cart"
    with pytest.raises(KeyError):
        model().recommend(["NOPE"])


def test_k_limits_the_number_of_recommendations():
    m = BasketRecommender(min_support=1, min_count=1, min_lift=0).fit([["A", "B", "C", "D"]] * 3)
    assert len(m.recommend(["A"], k=2).recs) == 2


def test_backoff_returns_partial_only_when_every_sub_cart_agrees_and_is_off_by_default():
    orders = [["A", "B", "X"]] * 4 + [["A", "C", "X"]] * 4 + [["B", "C", "X"]] * 4  # {A,B,C} itself never occurs
    strict = BasketRecommender(min_support=1, min_count=1, min_lift=0).fit(orders)
    assert strict.recommend(["A", "B", "C"]).status == "no_pattern"
    loose = BasketRecommender(min_support=1, min_count=1, min_lift=0, backoff=True).fit(orders)
    res = loose.recommend(["A", "B", "C"])
    assert res.status == "partial" and [r.sku for r in res.recs] == ["X"] and "part of this cart" in res.message


def test_popularity_baseline_ranks_by_count_and_excludes_the_cart():
    pop = PopularityBaseline().fit(ORDERS)  # counts: A=8, B=8, C=2, D=2
    assert pop.recommend(["B"], k=2) == ["A", "C"]
    assert pop.recommend(["A", "B"], k=5) == ["C", "D"]


def test_evidence_level_thresholds():
    from retail_basket.model import evidence_level

    assert [evidence_level(n) for n in (5, 9, 10, 24, 25, 90)] == ["limited", "limited", "moderate", "moderate", "strong", "strong"]
