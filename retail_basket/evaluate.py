"""Offline evaluation of the market-basket recommender. Owner: retail_basket.

    python -m retail_basket.evaluate          (or: make retail-eval)

Protocol: 5-fold cross-validation over orders. For every held-out order we simulate checkout: shuffle the items (seeded) and, for each
prefix of length 1..n-1, treat the prefix as the cart and the remaining items as the ones the customer will go on to buy. A recommendation
is a HIT if at least one shown item is in that remaining set.
  hit@k (all carts)      misses count when the model abstains ("no_pattern"), so it cannot win by only answering easy carts
  coverage               share of carts with at least one recommendation
  hit@k (covered carts)  hit rate on only the carts the model answered, to compare with baselines on the SAME carts
  precision@k            hits among the items shown (covered carts)
Baselines: global popularity (items most often bought overall) and random. Bootstrap 95% confidence intervals show whether differences are real.
"""
import collections
import itertools
import json
import math
import random
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from retail_basket.data import load_baskets  # noqa: E402
from retail_basket.model import BasketRecommender, PopularityBaseline

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "data" / "eval" / "retail.json"
Cart = Tuple[List[str], set]  # (cart items, items bought later in the same order)


def make_carts(baskets: Sequence[Sequence[str]], seed: int = 0) -> List[Cart]:
    rng = random.Random(seed)
    carts: List[Cart] = []
    for basket in baskets:
        order = list(basket)
        rng.shuffle(order)
        for m in range(1, len(order)):
            carts.append((order[:m], set(order[m:])))
    return carts


def kfold(baskets: Sequence, k: int = 5, seed: int = 0):
    idx = list(range(len(baskets)))
    random.Random(seed).shuffle(idx)
    for f in range(k):
        test = [baskets[i] for i in idx[f::k]]
        train = [baskets[i] for j, i in enumerate(idx) if j % k != f]
        yield train, test


def _ndcg(recs: List[str], targets: set, k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(recs[:k]) if s in targets)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(targets))))
    return dcg / ideal if ideal else 0.0


def summarize(rows: List[Tuple[List[str], set]], k: int, seed: int = 0) -> Dict[str, float]:
    """rows: (recommended skus, target set) per cart; an empty list means the model abstained."""
    n = len(rows)
    covered = [(r, t) for r, t in rows if r]
    hits_all = [1.0 if set(r[:k]) & t else 0.0 for r, t in rows]
    hits_cov = [1.0 if set(r[:k]) & t else 0.0 for r, t in covered]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(hits_all) for _ in range(n)) / n for _ in range(300)) if n else [0.0]
    return {
        "carts": n,
        "coverage": len(covered) / n if n else 0.0,
        f"hit@{k}": sum(hits_all) / n if n else 0.0,
        f"hit@{k}_ci95": [boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]],
        f"hit@{k}_covered": sum(hits_cov) / len(covered) if covered else 0.0,
        f"precision@{k}": (sum(len(set(r[:k]) & t) / len(r[:k]) for r, t in covered) / len(covered)) if covered else 0.0,
        f"ndcg@{k}": sum(_ndcg(r, t, k) for r, t in rows) / n if n else 0.0,
    }


def cross_validate(baskets, factory: Callable[[], BasketRecommender], k: int = 5, folds: int = 5, seed: int = 0) -> Dict[str, Dict]:
    model_rows, pop_rows, rand_rows, pop_on_covered = [], [], [], []
    for train, test in kfold(baskets, folds, seed):
        model = factory().fit(train)
        pop = PopularityBaseline().fit(train)
        items = model.items
        rng = random.Random(seed)
        for cart, targets in make_carts(test, seed):
            res = model.recommend(cart, k)
            shown = [r.sku for r in res.recs]
            model_rows.append((shown, targets))
            p = pop.recommend(cart, k)
            pop_rows.append((p, targets))
            rand_rows.append((rng.sample([s for s in items if s not in cart], k), targets))
            if shown:
                pop_on_covered.append((p, targets))
    return {
        "model": summarize(model_rows, k, seed),
        "popularity": summarize(pop_rows, k, seed),
        "random": summarize(rand_rows, k, seed),
        "popularity_on_model_covered_carts": summarize(pop_on_covered, k, seed),
    }


def sweep(baskets, k: int = 5) -> List[Dict]:
    out = []
    for ms in (1, 3, 5, 8):
        for mc in (1, 2, 3):
            for ml in (1.0, 1.2):
                for bo in (False, True):
                    r = cross_validate(baskets, lambda: BasketRecommender(ms, mc, ml, bo), k)["model"]
                    out.append({"min_support": ms, "min_count": mc, "min_lift": ml, "backoff": bo, **{x: r[x] for x in ("coverage", f"hit@{k}", f"hit@{k}_covered", f"precision@{k}")}})
    return out


def signal_check(baskets: Sequence[Sequence[str]], catalog=None, shuffles: int = 30, seed: int = 0) -> Dict:
    """Is there any real co-purchase structure, or do the orders look like random baskets?

    Compares the most frequent item pair with the same statistic on baskets re-drawn at random with the same sizes (a null model), and counts
    pairs that are unusually frequent (z > 3) against the number expected by chance.
    """
    items = sorted({i for b in baskets for i in b})
    n_items = len(items)
    pair = collections.Counter(p for b in baskets for p in itertools.combinations(sorted(set(b)), 2))
    exp = sum(len(b) * (len(b) - 1) / 2 for b in baskets) / (n_items * (n_items - 1) / 2)
    z3 = sum(1 for n in pair.values() if (n - exp) / math.sqrt(exp) > 3)
    rng = random.Random(seed)
    flat = [i for b in baskets for i in b]
    sizes = [len(b) for b in baskets]
    null_max = []
    for _ in range(shuffles):
        rng.shuffle(flat)
        it = iter(flat)
        drawn = [list(dict.fromkeys(next(it) for _ in range(sz))) for sz in sizes]
        null_max.append(max(collections.Counter(p for b in drawn for p in itertools.combinations(sorted(set(b)), 2)).values()))
    observed = max(pair.values())
    chance_z3 = 0.00135 * len(pair)
    looks_random = observed <= max(null_max) and z3 <= max(3, 3 * chance_z3)
    out = {"observed_max_pair_count": observed, "shuffled_max_pair_count_range": [min(null_max), max(null_max)],
           "pairs_with_z_gt_3": z3, "pairs_with_z_gt_3_expected_by_chance": round(chance_z3, 1), "n_pairs_seen": len(pair),
           "possible_pairs": n_items * (n_items - 1) // 2, "looks_random": looks_random}
    out["verdict"] = ("These orders are statistically indistinguishable from randomly drawn baskets, so no recommender can find a reliable "
                      "'bought together' pattern here. The pipeline is correct, but expect no lift over popularity on this dataset."
                      if looks_random else "Some item pairs occur more often than chance, so a bought-together signal exists.")
    return out


def run(k: int = 5, do_sweep: bool = True) -> Dict:
    baskets, _ = load_baskets()
    default = BasketRecommender()
    result = {"k": k, "n_orders": len(baskets), "config": {"min_support": default.min_support, "min_count": default.min_count,
                                                          "min_lift": default.min_lift, "backoff": default.backoff},
              "cross_validation": cross_validate(baskets, BasketRecommender, k)}
    result["signal_check"] = signal_check(baskets)
    if do_sweep:
        result["sweep"] = sweep(baskets, k)
    return result


def format_report(res: Dict) -> str:
    k = res["k"]
    cv = res["cross_validation"]
    pct = lambda v: f"{100 * v:5.1f}%"  # noqa: E731
    lines = [f"Retail market-basket evaluation: {res['n_orders']} orders, 5-fold CV, k={k}, config {res['config']}", ""]
    lines.append(f"{'':34s}{'coverage':>10s}{'hit@'+str(k):>9s}{'hit (covered)':>15s}{'precision':>11s}{'ndcg':>8s}")
    for name in ("model", "popularity", "random", "popularity_on_model_covered_carts"):
        r = cv[name]
        lines.append(f"{name:34s}{pct(r['coverage']):>10s}{pct(r[f'hit@{k}']):>9s}{pct(r[f'hit@{k}_covered']):>15s}{pct(r[f'precision@{k}']):>11s}{r[f'ndcg@{k}']:>8.3f}")
    m = cv["model"][f"hit@{k}_ci95"]
    sc = res.get("signal_check")
    if sc:
        lines.append(f"\nData check: most frequent pair appears {sc['observed_max_pair_count']}x; random baskets give {sc['shuffled_max_pair_count_range'][0]}-{sc['shuffled_max_pair_count_range'][1]}x. "
                     f"Unusual pairs: {sc['pairs_with_z_gt_3']} (chance expects {sc['pairs_with_z_gt_3_expected_by_chance']}).\n  -> {sc['verdict']}")
    lines.append(f"\nmodel hit@{k} 95% CI: {pct(m[0])} to {pct(m[1])}; popularity: {pct(cv['popularity'][f'hit@{k}_ci95'][0])} to {pct(cv['popularity'][f'hit@{k}_ci95'][1])}")
    return "\n".join(lines)


def main() -> None:
    res = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2))
    print(format_report(res))
    print(f"\nWritten: {OUT}")


if __name__ == "__main__":
    main()
