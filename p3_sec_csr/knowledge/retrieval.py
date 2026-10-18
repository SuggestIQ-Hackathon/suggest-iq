"""Deterministic hybrid retrieval for the P3 knowledge bases.

Enterprise research systems need both semantic recall and exact-term precision.
This module combines the repository's shared vector index with a lightweight
BM25 lexical score over the same filtered corpus.  It deliberately keeps the
original chunk text unchanged so every citation remains verbatim source text.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from core.rag_base import Chunk, Hit, VectorIndex

SEMANTIC_WEIGHT = 0.65
LEXICAL_WEIGHT = 0.35
BM25_K1 = 1.5
BM25_B = 0.75

_CONTEXT_FIELDS = (
    "source_doc",
    "company",
    "form",
    "fiscal_year",
    "period_end",
    "item",
    "section",
    "report_year",
    "doc_type",
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _matches(metadata: Mapping[str, Any], where: Mapping[str, Any] | None) -> bool:
    if not where:
        return True
    for key, expected in where.items():
        actual = metadata.get(key)
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _search_text(chunk: Chunk) -> str:
    """Add deterministic document context for retrieval, not for citation text."""
    context = " ".join(
        str(chunk.metadata[field])
        for field in _CONTEXT_FIELDS
        if chunk.metadata.get(field) not in (None, "")
    )
    return f"{context} {chunk.text}".strip()


def _bm25(chunks: list[Chunk], query: str) -> dict[str, float]:
    query_terms = _tokens(query)
    if not chunks or not query_terms:
        return {chunk.id: 0.0 for chunk in chunks}

    documents = [_tokens(_search_text(chunk)) for chunk in chunks]
    average_length = sum(map(len, documents)) / max(1, len(documents))
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    scores: dict[str, float] = {}
    corpus_size = len(documents)
    for chunk, document in zip(chunks, documents):
        frequencies = Counter(document)
        length_normalizer = BM25_K1 * (
            1.0 - BM25_B + BM25_B * len(document) / max(1.0, average_length)
        )
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            inverse_document_frequency = math.log(
                1.0
                + (corpus_size - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            score += inverse_document_frequency * (
                frequency * (BM25_K1 + 1.0)
                / (frequency + length_normalizer)
            )
        scores[chunk.id] = score
    return scores


def hybrid_search(
    index: VectorIndex,
    query: str,
    *,
    k: int = 5,
    where: Mapping[str, Any] | None = None,
) -> list[Hit]:
    """Return metadata-filtered results using 65% vector and 35% BM25 score.

    Semantic cosine scores are clipped to ``[0, 1]``. BM25 scores are divided
    by the best score in the filtered corpus. The resulting fused score remains
    in ``[0, 1]`` and has deterministic chunk-id tie breaking.
    """
    if k <= 0:
        return []
    filtered = [
        chunk for chunk in index.chunks if _matches(chunk.metadata, where)
    ]
    if not filtered:
        return []

    semantic_hits = index.query(query or "evidence", k=len(filtered), where=dict(where or {}))
    semantic_scores = {
        hit.chunk.id: max(0.0, min(1.0, float(hit.score)))
        for hit in semantic_hits
    }
    lexical_scores = _bm25(filtered, query)
    lexical_max = max(lexical_scores.values(), default=0.0)

    ranked: list[Hit] = []
    for chunk in filtered:
        semantic = semantic_scores.get(chunk.id, 0.0)
        lexical = (
            lexical_scores.get(chunk.id, 0.0) / lexical_max
            if lexical_max > 0.0
            else 0.0
        )
        score = SEMANTIC_WEIGHT * semantic + LEXICAL_WEIGHT * lexical
        ranked.append(Hit(chunk=chunk, score=max(0.0, min(1.0, score))))
    ranked.sort(key=lambda hit: (-hit.score, hit.chunk.id))
    return ranked[:k]
