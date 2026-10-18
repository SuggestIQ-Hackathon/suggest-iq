"""Load the retail transactions and the product catalog. Owner: retail_basket.

Input: resources/Retail.zip -> CMPE256_Hackathon_market_basket_analysis_Release.csv
(transaction_id, item_1..item_5; each item looks like "Bosch D7050 Detector (SKU: D7050)").
Products are identified by SKU everywhere inside the package; names are for display.
"""
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = REPO_ROOT / "resources" / "Retail.zip"
RAW_DIR = REPO_ROOT / "data" / "raw" / "retail"
CSV_NAME = "CMPE256_Hackathon_market_basket_analysis_Release.csv"
_SKU = re.compile(r"\(SKU:\s*([^)]+?)\s*\)\s*$")


CATEGORIES = ["Cameras", "Recorders", "Detectors", "Panels & kits", "Accessories"]


def category_of(name: str) -> str:
    """Shelf category inferred from the product name (the dataset has no category column)."""
    n = name.lower()
    if "camera" in n:
        return "Cameras"
    if "nvr" in n.replace("-", " ").split():
        return "Recorders"
    if any(k in n for k in ("detector base", "keypad", "wireless key", "wireless receiver")):
        return "Accessories"
    if "detector" in n:
        return "Detectors"
    if "control panel" in n or "alarm kit" in n:
        return "Panels & kits"
    return "Other"


@dataclass(frozen=True)
class Item:
    sku: str
    name: str  # full display name, e.g. "Bosch D7050 Detector"
    brand: str
    category: str = ""


def parse_item(raw: str) -> Item:
    """'Bosch D7050 Detector (SKU: D7050)' -> Item(sku='D7050', name='Bosch D7050 Detector', brand='Bosch')."""
    raw = raw.strip()
    m = _SKU.search(raw)
    if not m:
        raise ValueError(f"item has no '(SKU: ...)' suffix: {raw!r}")
    name = raw[: m.start()].strip()
    return Item(sku=m.group(1), name=name, brand=name.split()[0], category=category_of(name))


def _find_csv() -> Optional[Path]:
    for p in (RAW_DIR / CSV_NAME, RAW_DIR / "Retail" / CSV_NAME):
        if p.exists():
            return p
    return None


def csv_path() -> Path:
    """Path of the CSV, unpacking resources/Retail.zip into data/raw/retail on first use."""
    found = _find_csv()
    if found:
        return found
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"{ZIP_PATH} not found; place Retail.zip in resources/")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(RAW_DIR)
    found = _find_csv()
    if not found:
        raise FileNotFoundError(f"{CSV_NAME} not found inside {ZIP_PATH}")
    return found


def load_baskets(path: Optional[Path] = None):
    """Return (baskets, catalog). baskets: list of lists of SKUs (order preserved, duplicates removed).
    catalog: sku -> Item for every product seen."""
    df = pd.read_csv(path or csv_path())
    cols = [c for c in df.columns if c.startswith("item_")]
    catalog: Dict[str, Item] = {}
    baskets: List[List[str]] = []
    for row in df[cols].itertuples(index=False):
        basket: List[str] = []
        for raw in row:
            if not isinstance(raw, str) or not raw.strip():
                continue
            item = parse_item(raw)
            catalog.setdefault(item.sku, item)
            if item.sku not in basket:
                basket.append(item.sku)
        if basket:
            baskets.append(basket)
    return baskets, catalog
