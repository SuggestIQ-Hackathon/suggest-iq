"""Pure evaluation metrics (no I/O). Owner: P4.

Signatures are fixed by COMMON.md section 3 and exercised by tests/contract/test_p4.py.
"""
import math
from typing import Dict, Iterable, List, Sequence, Set


def routing_accuracy(predicted: List[Set[str]], gold: List[Set[str]]) -> float:
    """Exact-set match: a query counts only if the predicted domain set equals the gold set."""
    if len(predicted) != len(gold):
        raise ValueError("predicted and gold must have the same length")
    if not gold:
        return 0.0
    return sum(1 for p, g in zip(predicted, gold) if set(p) == set(g)) / len(gold)


def hit_rate_at_k(retrieved_ids: List[List[str]], relevant_ids: List[Set[str]], k: int) -> float:
    """Fraction of queries whose top-k retrieved ids contain at least one relevant id."""
    if len(retrieved_ids) != len(relevant_ids):
        raise ValueError("retrieved_ids and relevant_ids must have the same length")
    if not retrieved_ids or k <= 0:
        return 0.0
    hits = sum(1 for got, rel in zip(retrieved_ids, relevant_ids) if set(got[:k]) & set(rel))
    return hits / len(retrieved_ids)


def precision_at_k(ranked: Sequence[str], relevant: Set[str], k: int) -> float:
    """Relevant items in the top-k divided by k (a list shorter than k is penalised)."""
    if k <= 0:
        return 0.0
    return sum(1 for item in ranked[:k] if item in relevant) / k


def ndcg_at_k(ranked: Sequence[str], gains: Dict[str, float], k: int) -> float:
    """Graded NDCG with log2 discount. 0.0 when nothing relevant is found or there is no ideal gain."""
    if k <= 0:
        return 0.0
    dcg = sum(gains.get(item, 0.0) / math.log2(i + 2) for i, item in enumerate(ranked[:k]))
    ideal = sorted((g for g in gains.values() if g > 0), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def mean_reciprocal_rank(ranked_lists: List[Sequence[str]], relevant_sets: List[Set[str]]) -> float:
    """Mean of 1/rank of the first relevant item per query (0 when none)."""
    if len(ranked_lists) != len(relevant_sets):
        raise ValueError("ranked_lists and relevant_sets must have the same length")
    if not ranked_lists:
        return 0.0
    total = 0.0
    for ranked, rel in zip(ranked_lists, relevant_sets):
        for i, item in enumerate(ranked):
            if item in rel:
                total += 1.0 / (i + 1)
                break
    return total / len(ranked_lists)


def confusion_matrix(
    predicted: List[Set[str]], gold: List[Set[str]], labels: Iterable[str]
) -> Dict[str, Dict[str, int]]:
    """Multi-label co-occurrence matrix: M[g][p] = number of queries with g in gold AND p in predicted.

    The diagonal M[g][g] is the number of queries where g was correctly detected; row g's total is the
    number of queries whose gold set contains g. The extra column "(none)" counts queries where g was gold
    but nothing was predicted.
    """
    labels = list(labels)
    matrix = {g: {p: 0 for p in labels + ["(none)"]} for g in labels}
    for pred, gld in zip(predicted, gold):
        for g in gld:
            if g not in matrix:
                continue
            if not pred:
                matrix[g]["(none)"] += 1
            for p in pred:
                if p in matrix[g]:
                    matrix[g][p] += 1
    return matrix


def per_label_prf(predicted: List[Set[str]], gold: List[Set[str]], labels: Iterable[str]) -> Dict[str, Dict[str, float]]:
    """Per-domain precision / recall / F1 for the multi-label routing decision."""
    out: Dict[str, Dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for p, g in zip(predicted, gold) if label in p and label in g)
        fp = sum(1 for p, g in zip(predicted, gold) if label in p and label not in g)
        fn = sum(1 for p, g in zip(predicted, gold) if label not in p and label in g)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[label] = {"precision": prec, "recall": rec, "f1": f1, "support": float(tp + fn)}
    return out
