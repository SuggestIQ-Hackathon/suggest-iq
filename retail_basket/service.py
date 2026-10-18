"""Shared model holder: loads data, trains, serves recommendations, tracks usage. Owner: retail_basket.

Used by the FastAPI app (api.py) and the Streamlit checkout page (ui.py) so both behave identically.
"""
import threading
import time
from typing import Dict, List, Optional

from retail_basket.data import Item, load_baskets
from retail_basket.model import BasketRecommender, Result


class RecommenderService:
    def __init__(self, path=None, **model_kwargs):
        self._path, self._kw = path, model_kwargs
        self._lock = threading.Lock()
        self.version = 0
        self.stats = {"requests": 0, "no_pattern": 0, "errors": 0, "latency_ms_total": 0.0}
        self.catalog: Dict[str, Item] = {}
        self.model = BasketRecommender(**model_kwargs)
        self.retrain()

    def retrain(self) -> dict:
        """(Re)load the orders and refit. Call again when new orders are added to the CSV (periodic retraining)."""
        baskets, catalog = load_baskets(self._path)
        model = BasketRecommender(**self._kw).fit(baskets)
        with self._lock:
            self.model, self.catalog, self.version = model, catalog, self.version + 1
        return self.info()

    def info(self) -> dict:
        m = self.model
        return {"model_version": self.version, "trained_at": m.trained_at, "n_orders": m.n_orders, "n_items": len(m.item_count),
                "config": {"min_support": m.min_support, "min_count": m.min_count, "min_lift": m.min_lift, "backoff": m.backoff}}

    def resolve(self, ref: str) -> str:
        """Accept a SKU or a full product name (case-insensitive) and return the SKU; KeyError when unknown."""
        if ref in self.catalog:
            return ref
        low = ref.strip().lower()
        for sku, item in self.catalog.items():
            if item.name.lower() == low or sku.lower() == low:
                return sku
        raise KeyError(ref)

    def recommend(self, cart: List[str], k: int = 5) -> Result:
        t = time.perf_counter()
        try:
            skus = [self.resolve(c) for c in cart]
            result = self.model.recommend(skus, k)
        except KeyError:
            self.stats["errors"] += 1
            raise
        finally:
            self.stats["requests"] += 1
            self.stats["latency_ms_total"] += (time.perf_counter() - t) * 1000
        if result.status in ("no_pattern",):
            self.stats["no_pattern"] += 1
        return result

    def metrics(self) -> dict:
        n = self.stats["requests"]
        return {**self.info(), "requests": n, "errors": self.stats["errors"],
                "no_pattern_rate": (self.stats["no_pattern"] / n) if n else 0.0,
                "avg_latency_ms": (self.stats["latency_ms_total"] / n) if n else 0.0}
