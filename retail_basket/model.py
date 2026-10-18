"""Market-basket recommender: "customers who bought these items also bought ...". Owner: retail_basket.

For a cart C the recommender looks at the historical orders that contain EVERY item in C, and ranks the other items by how
often they appear in those orders:
    support(C)        = number of orders containing all of C
    count(C + i)      = number of orders containing C and item i
    confidence(i | C) = count(C + i) / support(C)
    lift(i | C)       = confidence(i | C) / (orders containing i / all orders)     (> 1 means i is bought MORE often with C than on average)
An item is recommended only if the evidence is strong enough:
    support(C) >= min_support     the cart combination must have been seen often enough
    count(C + i) >= min_count     the pairing itself must have been seen often enough
    lift >= min_lift              and it must beat chance
If the cart combination was not seen (or too rarely), the result is status "no_pattern" with NO recommendations, as the brief
requires, instead of showing irrelevant items. Optional `backoff` re-tries with the cart minus one item and marks the result "partial".
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set


def evidence_level(cart_support: int) -> str:
    """How much history stands behind a recommendation. Small samples can show large lifts by chance, so the UI says so."""
    return "limited" if cart_support < 10 else "moderate" if cart_support < 25 else "strong"


@dataclass
class Rec:
    sku: str
    confidence: float
    lift: float
    count: int  # orders containing the cart AND this item
    cart_support: int  # orders containing the whole cart

    def reason(self) -> str:
        return (f"Bought together in {self.count} of {self.cart_support} past orders with these items "
                f"({100 * self.confidence:.0f}%), {self.lift:.1f}x more often than average.")


@dataclass
class Result:
    status: str  # "ok" | "partial" | "no_pattern" | "empty_cart"
    recs: List[Rec] = field(default_factory=list)
    cart_support: int = 0
    message: str = ""


class BasketRecommender:
    def __init__(self, min_support: int = 5, min_count: int = 2, min_lift: float = 1.0, backoff: bool = False):
        self.min_support, self.min_count, self.min_lift, self.backoff = min_support, min_count, min_lift, backoff
        self.n_orders = 0
        self.item_count: Dict[str, int] = {}
        self._postings: Dict[str, Set[int]] = {}
        self.trained_at: Optional[str] = None

    # ------------------------------------------------------------------ training
    def fit(self, baskets: Iterable[Sequence[str]]) -> "BasketRecommender":
        self._postings = {}
        n = 0
        for idx, basket in enumerate(b for b in (set(x) for x in baskets) if b):
            n += 1
            for sku in basket:
                self._postings.setdefault(sku, set()).add(idx)
        self.n_orders = n
        self.item_count = {sku: len(p) for sku, p in self._postings.items()}
        self.trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self

    @property
    def items(self) -> List[str]:
        return sorted(self.item_count)

    # ------------------------------------------------------------------ querying
    def _orders_with(self, cart: FrozenSet[str]) -> Set[int]:
        sets = [self._postings.get(sku, set()) for sku in cart]
        return set.intersection(*sets) if sets else set()

    def _score(self, cart: FrozenSet[str]) -> (int, List[Rec]):
        orders = self._orders_with(cart)
        support = len(orders)
        if support < self.min_support:
            return support, []
        recs: List[Rec] = []
        for sku, postings in self._postings.items():
            if sku in cart:
                continue
            count = len(orders & postings)
            if count < self.min_count:
                continue
            conf = count / support
            lift = conf / (self.item_count[sku] / self.n_orders)
            if lift >= self.min_lift:
                recs.append(Rec(sku, conf, lift, count, support))
        recs.sort(key=lambda r: (-r.confidence, -r.lift, -r.count, r.sku))
        return support, recs

    def recommend(self, cart: Iterable[str], k: int = 5) -> Result:
        cart_set = frozenset(cart)
        unknown = [s for s in cart_set if s not in self.item_count]
        if unknown:
            raise KeyError(f"unknown item(s): {sorted(unknown)}")
        if not cart_set:
            return Result("empty_cart", message="Add an item to see recommendations.")
        support, recs = self._score(cart_set)
        if recs:
            return Result("ok", recs[:k], support)
        if self.backoff and len(cart_set) > 1:
            merged: Dict[str, List[Rec]] = {}
            for sub in combinations(sorted(cart_set), len(cart_set) - 1):
                _, sub_recs = self._score(frozenset(sub))
                for r in sub_recs:
                    merged.setdefault(r.sku, []).append(r)
            partial = [Rec(sku, sum(x.confidence for x in rs) / len(rs), sum(x.lift for x in rs) / len(rs),
                           min(x.count for x in rs), min(x.cart_support for x in rs))
                       for sku, rs in merged.items() if len(rs) == len(cart_set)]  # must be supported by EVERY sub-cart
            partial.sort(key=lambda r: (-r.confidence, -r.lift, r.sku))
            if partial:
                return Result("partial", partial[:k], support, "Only part of this cart matches past orders.")
        if support == 0:
            msg = "This exact combination of items never appears together in past orders, so no recommendation is shown."
        elif support < self.min_support:
            msg = f"This combination appears in only {support} past order(s), too few to recommend from."
        else:
            msg = "No item is bought together with this cart more often than chance, so no recommendation is shown."
        return Result("no_pattern", [], support, msg)


class PopularityBaseline:
    """Recommend the globally most-bought items not already in the cart (the baseline any recommender must beat)."""

    def fit(self, baskets: Iterable[Sequence[str]]) -> "PopularityBaseline":
        counts: Dict[str, int] = {}
        for b in baskets:
            for sku in set(b):
                counts[sku] = counts.get(sku, 0) + 1
        self.ranked = sorted(counts, key=lambda s: (-counts[s], s))
        return self

    def recommend(self, cart: Iterable[str], k: int = 5) -> List[str]:
        cart_set = set(cart)
        return [s for s in self.ranked if s not in cart_set][:k]
