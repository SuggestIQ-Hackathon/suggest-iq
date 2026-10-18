import json

from p3_sec_csr.recommenders.strategy import CATALOG_PATH, recommend


def test_catalog_has_stable_unique_actions():
    catalog = json.loads(CATALOG_PATH.read_text())
    ids = [item["item_id"] for item in catalog]
    assert len(catalog) >= 12
    assert len(ids) == len(set(ids))
    assert all(item_id.startswith("STRAT-") for item_id in ids)
    assert all(item["assumptions"] for item in catalog)


def test_ranking_is_deterministic_and_explainable():
    context = "Conflict, climate shocks, and food prices threaten food security and nutrition."
    first = recommend(context)
    second = recommend(context)
    assert [item.item_id for item in first] == [item.item_id for item in second]
    assert len(first) == 3
    assert all(0 <= item.confidence_score <= 1 for item in first)
    assert all(
        "impact=" in item.rationale and "semantic_relevance=" in item.rationale
        for item in first
    )
    assert all("assumption:" in item.estimated_impact for item in first)


def test_custom_catalog_obeys_structured_weights():
    catalog = [
        {
            "item_id": "STRAT-HIGH",
            "title": "High impact",
            "category": "Capital Allocation",
            "description": "same context",
            "impact": 5,
            "regulatory_risk": 1,
            "feasibility": 5,
            "evidence_keywords": [],
            "source_hint": "test",
            "assumptions": ["Test assumption."],
        },
        {
            "item_id": "STRAT-LOW",
            "title": "Low impact",
            "category": "Capital Allocation",
            "description": "same context",
            "impact": 1,
            "regulatory_risk": 5,
            "feasibility": 1,
            "evidence_keywords": [],
            "source_hint": "test",
            "assumptions": ["Test assumption."],
        },
    ]
    assert (
        recommend("same context", catalog=catalog, top_k=2)[0].item_id == "STRAT-HIGH"
    )
