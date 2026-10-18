"""Deterministic multi-criteria ranking for strategic consulting actions."""

from __future__ import annotations

import json
from pathlib import Path

from core.rag_base import embed
from core.schemas import RecommendationItem

CATALOG_PATH = Path(__file__).with_name("strategy_catalog.json")
IMPACT_WEIGHT = 0.40
REGULATORY_WEIGHT = 0.30
FEASIBILITY_WEIGHT = 0.30
STRUCTURED_BLEND = 0.80
SIMILARITY_BLEND = 0.20
TECHNOLOGY_INVESTMENT_TAG = "technology_investment"


def _normalise_rating(value: float) -> float:
    return max(0.0, min(1.0, (float(value) - 1.0) / 4.0))


def _load_catalog(catalog: list[dict] | None) -> list[dict]:
    return catalog if catalog is not None else json.loads(CATALOG_PATH.read_text())


def recommend(
    context_text: str,
    catalog: list[dict] | None = None,
    top_k: int = 3,
    required_tag: str | None = None,
) -> list[RecommendationItem]:
    """Rank actions using 80% structured score and 20% semantic relevance.

    structured = 0.40*impact + 0.30*(1-regulatory_risk) + 0.30*feasibility,
    with all 1-5 ratings normalised to 0-1. Negative cosine values are floored at
    zero so unrelated text cannot produce a negative confidence score.
    """
    actions = _load_catalog(catalog)
    if required_tag:
        actions = [
            action for action in actions if required_tag in action.get("intent_tags", [])
        ]
    if not actions or top_k <= 0:
        return []
    action_texts = [
        " ".join(
            [
                action["title"],
                action["description"],
                " ".join(action.get("evidence_keywords", [])),
                action.get("source_hint", ""),
            ]
        )
        for action in actions
    ]
    vectors = embed([context_text or "strategic action", *action_texts])
    similarities = vectors[1:] @ vectors[0]

    ranked: list[tuple[float, str, RecommendationItem]] = []
    for action, similarity in zip(actions, similarities):
        impact = _normalise_rating(action["impact"])
        regulatory_safety = 1.0 - _normalise_rating(action["regulatory_risk"])
        feasibility = _normalise_rating(action["feasibility"])
        structured = (
            IMPACT_WEIGHT * impact
            + REGULATORY_WEIGHT * regulatory_safety
            + FEASIBILITY_WEIGHT * feasibility
        )
        semantic = max(0.0, float(similarity))
        score = max(
            0.0, min(1.0, STRUCTURED_BLEND * structured + SIMILARITY_BLEND * semantic)
        )
        assumption = action.get(
            "assumptions", ["Validate assumptions before investment."]
        )[0]
        item = RecommendationItem(
            item_id=action["item_id"],
            title=action["title"],
            category=action["category"],
            confidence_score=round(score, 4),
            rationale=(
                f"impact={impact:.2f}, regulatory_safety={regulatory_safety:.2f}, "
                f"feasibility={feasibility:.2f}, semantic_relevance={semantic:.2f}; "
                "weights=40/30/30 and blend=80/20."
            ),
            compatibility_notes=action.get("source_hint"),
            estimated_impact=f"Estimated qualitative benefit; assumption: {assumption}",
        )
        ranked.append((score, action["item_id"], item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in ranked[:top_k]]
