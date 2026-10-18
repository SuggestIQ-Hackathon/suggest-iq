from __future__ import annotations

from p2_tech_clinical.recommenders.hardware import recommend


def _item(item_id: str, name: str, model: str, *, verified: bool = True, symptoms=None):
    return {
        "item_id": item_id,
        "vendor": "Cisco",
        "name": name,
        "category": "network interface module",
        "compatible_models": [model],
        "specs": {},
        "typical_failure_symptoms": symptoms or [],
        "cost_tier": 3,
        "lead_time_tier": 3,
        "source_doc": "fixture.pdf",
        "source_page": 1,
        "verified": verified,
    }


def test_hardware_recommender_hard_filters_incompatible_models():
    catalog = [
        _item("CISCO-C8200-IF", "Catalyst 8200 interface module", "Catalyst 8200"),
        _item("CISCO-ASR1000-IF", "ASR 1000 interface module", "ASR 1000"),
    ]
    results = recommend("WAN interface issue", catalog, filters={"model": "Catalyst 8200"}, top_k=3)
    assert [item.item_id for item in results] == ["CISCO-C8200-IF"]


def test_hardware_recommender_order_is_deterministic_and_scores_are_bounded():
    catalog = [
        _item("CISCO-C8200-Z", "Catalyst 8200 interface module", "Catalyst 8200", symptoms=["packet loss"]),
        _item("CISCO-C8200-A", "Catalyst 8200 interface module", "Catalyst 8200", symptoms=["packet loss"]),
    ]
    first = recommend("packet loss", catalog, filters={"product_model": "Catalyst 8200"}, top_k=2)
    second = recommend("packet loss", catalog, filters={"product_model": "Catalyst 8200"}, top_k=2)
    assert [item.item_id for item in first] == [item.item_id for item in second]
    assert [item.item_id for item in first] == ["CISCO-C8200-A", "CISCO-C8200-Z"]
    assert all(0.0 <= item.confidence_score <= 1.0 for item in first)
    assert all("similarity" in item.rationale and "symptom match" in item.rationale for item in first)


def test_empty_inputs_and_top_k_are_safe():
    catalog = [_item("CISCO-C8200-IF", "Catalyst 8200 interface module", "Catalyst 8200")]
    assert recommend("", catalog) == []
    assert recommend("WAN interface", [], top_k=3) == []
    assert len(recommend("WAN interface", catalog, top_k=1)) == 1


def test_unverified_items_receive_the_0_8_penalty():
    catalog = [
        _item("CISCO-VERIFIED", "Catalyst 8200 interface module", "Catalyst 8200", verified=True),
        _item("CISCO-UNVERIFIED", "Catalyst 8200 interface module", "Catalyst 8200", verified=False),
    ]
    results = recommend("WAN interface", catalog, filters={"model": "Catalyst 8200"}, top_k=2)
    scores = {item.item_id: item.confidence_score for item in results}
    assert scores["CISCO-UNVERIFIED"] == scores["CISCO-VERIFIED"] * 0.8
    assert "unverified" in next(item.rationale for item in results if item.item_id == "CISCO-UNVERIFIED").lower()


def test_malformed_catalog_entries_are_skipped():
    catalog = [
        {"item_id": "bad"},
        _item("CISCO-C8200-IF", "Catalyst 8200 interface module", "Catalyst 8200"),
    ]
    results = recommend("WAN interface", catalog, filters={"model": "Catalyst 8200"})
    assert [item.item_id for item in results] == ["CISCO-C8200-IF"]
