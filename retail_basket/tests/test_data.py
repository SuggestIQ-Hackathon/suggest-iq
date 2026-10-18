import pytest

from retail_basket.data import load_baskets, parse_item


def test_parse_item_extracts_sku_name_and_brand():
    it = parse_item("Bosch D7050 Detector (SKU: D7050)")
    assert (it.sku, it.name, it.brand) == ("D7050", "Bosch D7050 Detector", "Bosch")
    assert parse_item("Axis M3046-V Network Camera (SKU: 0806-001)").sku == "0806-001"


def test_parse_item_rejects_names_without_sku():
    with pytest.raises(ValueError):
        parse_item("Bosch D7050 Detector")


def test_real_dataset_shape():
    baskets, catalog = load_baskets()
    assert len(baskets) == 1000 and len(catalog) == 40
    assert {len(b) for b in baskets} == {2, 3, 4, 5}
    assert all(len(b) == len(set(b)) for b in baskets)  # no item twice in one order
    assert all(sku in catalog for b in baskets for sku in b)


def test_categories_cover_every_product():
    from retail_basket.data import CATEGORIES, category_of

    _, catalog = load_baskets()
    assert {i.category for i in catalog.values()} <= set(CATEGORIES)
    assert category_of("Axis M3046-V Network Camera") == "Cameras"
    assert category_of("Honeywell HEN08104 NVR") == "Recorders" and category_of("Dahua 8-Channel NVR") == "Recorders"
    assert category_of("Bosch F220-B6 Detector Base") == "Accessories"  # a base is an accessory, not a detector
    assert category_of("DSC WS4916 Smoke Detector") == "Detectors"
    assert category_of("GE Interlogix NX-8 Control Panel") == "Panels & kits"
