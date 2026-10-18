"""Clinical and Agilent knowledge base."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable

from core.rag_base import Hit, VectorIndex, chunk_text

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional in minimal contract environments
    BeautifulSoup = None


REPO_ROOT = Path(__file__).resolve().parents[2]
ROW_CAP = 3000
# data/raw/agilent/<section>/ folder -> model metadata when the file name does not name one.
SECTION_MODELS = {"seahorse": "Seahorse", "special-stains": "Artisan Link Pro"}


def _agilent_model(name: str) -> str | None:
    lowered = name.lower()
    if "s540md" in lowered or "s540 md" in lowered:
        return "S540MD"
    if "seahorse" in lowered:
        return "Seahorse"
    if "nanozoomer" in lowered or "scanner" in lowered:
        return "NanoZoomer"
    if "artisan" in lowered or "special" in lowered:
        return "Artisan Link Pro"
    return None


def _text_chunks(path: Path, vendor: str, model: str | None, doc_type: str, *, section: str | None = None) -> list:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"} and BeautifulSoup is not None:
        soup = BeautifulSoup(text, "html.parser")
        for element in soup.find_all(["script", "style", "noscript", "template", "svg", "iframe", "canvas"]):
            element.decompose()
        for element in list(soup.find_all(True)):
            attrs = element.attrs or {}
            labels = " ".join(
                [str(attrs.get("id", "")), " ".join(str(value) for value in attrs.get("class", []))]
            ).lower()
            style = str(attrs.get("style", "")).lower().replace(" ", "")
            if any(marker in labels for marker in ("cookie", "consent", "onetrust", "privacy", "tracking", "analytics")):
                element.decompose()
            elif "display:none" in style or "visibility:hidden" in style:
                element.decompose()
        text = soup.get_text(" ", strip=True)
    if model is None and path.suffix.lower() in {".html", ".htm", ".txt"}:
        lowered = text.lower()
        if "s540md" in lowered or "s540 md" in lowered:
            model = "S540MD"
        elif "nanozoomer" in lowered:
            model = "NanoZoomer"
        elif "artisan link pro" in lowered:
            model = "Artisan Link Pro"
        elif "seahorse" in lowered:
            model = "Seahorse"
    return chunk_text(text, path.name, section=section, extra_meta={"vendor": vendor, "model": model, "doc_type": doc_type})


def _pdf_chunks(path: Path, vendor: str, model: str | None, doc_type: str) -> list:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    chunks = []
    try:
        reader = PdfReader(str(path))
        for page_number, page in enumerate(reader.pages, 1):
            chunks.extend(
                chunk_text(
                    page.extract_text() or "",
                    path.name,
                    page=page_number,
                    extra_meta={"vendor": vendor, "model": model, "doc_type": doc_type},
                )
            )
    except Exception:
        return []
    return chunks


def _csv_chunks(path: Path) -> list:
    chunks = []
    try:
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
            reader = csv.DictReader(handle)
            for number, row in enumerate(reader):
                if number >= ROW_CAP:
                    break
                fields = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k}
                nct = fields.get("nct number") or fields.get("nct_number") or fields.get("nct id") or f"row-{number + 1}"
                selected = [
                    fields.get(key, "")
                    for key in (
                        "nct number", "study title", "brief summary", "conditions",
                        "interventions", "primary outcome measures",
                    )
                ]
                text = " ".join(value for value in selected if value)
                if text:
                    chunks.extend(chunk_text(text, path.name, section=nct, extra_meta={"vendor": "ClinicalTrials.gov", "model": None, "doc_type": "trial"}))
    except (OSError, csv.Error):
        return []
    return chunks


class ClinicalKB:
    """Persistent index for Agilent pages, research PDFs, and trial CSV rows."""

    def __init__(self, raw_dir: str | Path | None = None, index_dir: str | Path | None = None):
        self.raw_dir = Path(raw_dir) if raw_dir else REPO_ROOT / "data" / "raw"
        self.index_dir = Path(index_dir) if index_dir else REPO_ROOT / "data" / "index" / "clinical"
        self._index: VectorIndex | None = None

    def _chunks(self) -> Iterable:
        agilent = self.raw_dir / "agilent"
        if agilent.exists():
            # Pages live in section folders (seahorse/, digital-pathology/, special-stains/, news/);
            # files directly in agilent/ are still read for older layouts.
            for path in sorted(agilent.rglob("*")):
                if not path.is_file():
                    continue
                model = _agilent_model(path.name) or SECTION_MODELS.get(path.parent.name)
                suffix = path.suffix.lower()
                if suffix in {".txt", ".html", ".htm"}:
                    yield from _text_chunks(path, "Agilent", model, "product_page")
                elif suffix == ".pdf":
                    yield from _pdf_chunks(path, "Agilent", model, "datasheet")
        clinical = self.raw_dir / "clinical"
        if clinical.exists():
            for path in sorted(clinical.rglob("*")):
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix == ".pdf":
                    topic = path.parent.name.replace("_", " ")
                    yield from _pdf_chunks(path, "Research", topic, "paper")
                elif suffix == ".csv":
                    yield from _csv_chunks(path)
                elif suffix in {".txt", ".html", ".htm"}:
                    yield from _text_chunks(path, "Research", path.parent.name, "paper")

    def build(self) -> VectorIndex:
        index = VectorIndex("clinical")
        index.add(list(self._chunks()))
        index.save(self.index_dir)
        self._index = index
        return index

    def _load(self) -> VectorIndex:
        if self._index is not None:
            return self._index
        try:
            self._index = VectorIndex.load(self.index_dir)
        except (FileNotFoundError, OSError, ValueError, KeyError):
            self._index = self.build()
        return self._index

    def search(self, query: str, k: int = 5, source_type: str | None = None) -> list[Hit]:
        where = {"doc_type": source_type} if source_type else None
        return self._load().query(query or "", k=k, where=where)
