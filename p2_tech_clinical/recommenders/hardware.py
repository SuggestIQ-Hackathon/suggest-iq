"""Deterministic hardware and instrument recommender.

The ranking score is:

    0.50 * cosine(problem, item)
    + 0.25 * symptom_keyword_match
    + 0.15 * (1 - normalised_cost_tier)
    + 0.10 * (1 - normalised_lead_time_tier)

where cost and lead-time tiers are normalised from 1..5 to 0..1. A missing
lead-time tier contributes a neutral 0.5 component because the catalog has no
evidence for either a short or long lead time. The final score is multiplied
by 0.8 for ``verified=false`` entries. Compatibility is a hard filter applied
before scoring, never a penalty. Cosine values are clipped to [0, 1] so the
returned confidence score remains a valid RecommendationItem confidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.rag_base import embed
from core.schemas import RecommendationItem


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = Path(__file__).resolve().parent / "catalog"

COSINE_WEIGHT = 0.50
SYMPTOM_WEIGHT = 0.25
COST_WEIGHT = 0.15
LEAD_TIME_WEIGHT = 0.10
UNVERIFIED_MULTIPLIER = 0.80

KNOWN_MODELS = ("Catalyst 8300", "Catalyst 8200", "Catalyst 8000V", "ISR 4000", "ASR 1000", "Seahorse", "NanoZoomer", "Artisan Link Pro", "Digital Pathology")


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _load_catalog(catalog: Any) -> list[dict[str, Any]]:
    if catalog is None:
        items: list[dict[str, Any]] = []
        for path in (CATALOG_DIR / "cisco_parts.json", CATALOG_DIR / "agilent_instruments.json"):
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                items.extend(loaded if isinstance(loaded, list) else loaded.get("items", []))
        return items
    if isinstance(catalog, (str, Path)):
        loaded = json.loads(Path(catalog).read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, list) else loaded.get("items", [])
    if isinstance(catalog, Mapping):
        return list(catalog.get("items", []))
    return list(catalog)


def _requested_model(problem_text: str, filters: Mapping[str, Any] | None) -> str | None:
    filters = filters or {}
    for key in ("model", "product_model", "compatible_model"):
        if filters.get(key):
            value = filters[key]
            if isinstance(value, (list, tuple, set)):
                return str(next(iter(value), "")) or None
            return str(value)
    lowered = problem_text.lower()
    for model in KNOWN_MODELS:
        if model.lower() in lowered:
            return model
    return None


def _model_matches(item: Mapping[str, Any], model: str | None) -> bool:
    if not model:
        return True
    wanted = _norm(model)
    return any(_norm(candidate) == wanted for candidate in item.get("compatible_models", []))


def _vendor_matches(item: Mapping[str, Any], vendor: Any) -> bool:
    if not vendor:
        return True
    values = vendor if isinstance(vendor, (list, tuple, set)) else [vendor]
    return any(_norm(item.get("vendor", "")) == _norm(value) for value in values)


def _symptom_match(problem_text: str, item: Mapping[str, Any]) -> float:
    symptoms = [str(value).lower().strip() for value in item.get("typical_failure_symptoms", []) if str(value).strip()]
    if not symptoms:
        return 0.0
    problem = problem_text.lower()
    return sum(1 for symptom in symptoms if symptom in problem) / len(symptoms)


def _tier_component(value: Any, *, missing: float = 0.5) -> float:
    if value is None or value == "":
        return missing
    try:
        tier = max(1.0, min(5.0, float(value)))
    except (TypeError, ValueError):
        return missing
    normalised = (tier - 1.0) / 4.0
    return 1.0 - normalised


def _cosine(problem_text: str, item_text: str) -> float:
    vectors = embed([problem_text, item_text])
    value = float(vectors[0] @ vectors[1])
    return max(0.0, min(1.0, value))


def _item_text(item: Mapping[str, Any]) -> str:
    specs = item.get("specs", {})
    return " ".join(
        [
            str(item.get("vendor", "")),
            str(item.get("name", "")),
            str(item.get("category", "")),
            " ".join(str(model) for model in item.get("compatible_models", [])),
            " ".join(str(symptom) for symptom in item.get("typical_failure_symptoms", [])),
            " ".join(f"{key} {value}" for key, value in specs.items()),
        ]
    )


def recommend(
    problem_text: str,
    catalog: Any = None,
    filters: Mapping[str, Any] | None = None,
    top_k: int = 3,
) -> list[RecommendationItem]:
    """Return up to ``top_k`` compatible hardware recommendations.

    ``filters`` accepts ``model``/``product_model``/``compatible_model`` and
    ``vendor``. A model found in ``problem_text`` is also treated as a hard
    compatibility requirement when no explicit model filter is supplied.
    """
    problem_text = str(problem_text or "")
    filters = filters or {}
    model = _requested_model(problem_text, filters)
    candidates = [
        item for item in _load_catalog(catalog)
        if _model_matches(item, model) and _vendor_matches(item, filters.get("vendor"))
    ]
    scored: list[tuple[float, str, dict[str, Any], dict[str, float]]] = []
    for item in candidates:
        cosine = _cosine(problem_text, _item_text(item))
        symptom = _symptom_match(problem_text, item)
        cost = _tier_component(item.get("cost_tier"), missing=0.5)
        lead_time = _tier_component(item.get("lead_time_tier"), missing=0.5)
        verified_multiplier = 1.0 if item.get("verified", False) else UNVERIFIED_MULTIPLIER
        raw_score = (
            COSINE_WEIGHT * cosine
            + SYMPTOM_WEIGHT * symptom
            + COST_WEIGHT * cost
            + LEAD_TIME_WEIGHT * lead_time
        )
        score = max(0.0, min(1.0, raw_score * verified_multiplier))
        components = {"cosine": cosine, "symptom_keyword_match": symptom, "cost_component": cost, "lead_time_component": lead_time, "verified_multiplier": verified_multiplier}
        scored.append((score, str(item.get("item_id", "")), item, components))
    scored.sort(key=lambda row: (-row[0], row[1]))

    recommendations: list[RecommendationItem] = []
    for score, item_id, item, components in scored[: max(0, int(top_k))]:
        compatible = ", ".join(str(value) for value in item.get("compatible_models", [])) or "not specified"
        rationale = (
            f"Score components: cosine={components['cosine']:.4f}; "
            f"symptom_keyword_match={components['symptom_keyword_match']:.4f}; "
            f"cost_component={components['cost_component']:.4f}; "
            f"lead_time_component={components['lead_time_component']:.4f}; "
            f"verified_multiplier={components['verified_multiplier']:.2f}."
        )
        recommendations.append(
            RecommendationItem(
                item_id=item_id,
                title=str(item.get("name", item_id)),
                category="Replacement Part",
                confidence_score=score,
                rationale=rationale,
                compatibility_notes=f"Catalog compatibility: {compatible}.",
                estimated_impact="Estimated impact requires diagnostic confirmation and depends on the selected component.",
            )
        )
    return recommendations
