"""Technology knowledge base for Cisco and Google/GCP source material."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from core.rag_base import Hit, VectorIndex, chunk_text

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - the P2 requirements include beautifulsoup4
    BeautifulSoup = None


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_NAMES = ("Catalyst 8300", "Catalyst 8200", "Catalyst 8000V", "ISR 4000", "ASR 1000")


def _model_for(name: str) -> str | None:
    lowered = name.lower()
    for model in MODEL_NAMES:
        if model.lower().replace(" ", "") in lowered.replace(" ", ""):
            return model
    if "8300" in lowered:
        return "Catalyst 8300"
    if "8200" in lowered:
        return "Catalyst 8200"
    if "8000v" in lowered:
        return "Catalyst 8000V"
    if "isr" in lowered or "4000" in lowered:
        return "ISR 4000"
    if "asr" in lowered or "1000" in lowered:
        return "ASR 1000"
    return None


def _text_chunks(path: Path, vendor: str, model: str | None, doc_type: str) -> list:
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
    text = re.sub(r"\s+", " ", text).strip()
    return chunk_text(text, path.name, extra_meta={"vendor": vendor, "model": model, "doc_type": doc_type})


def _pdf_chunks(path: Path, vendor: str, model: str | None, doc_type: str) -> list:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    chunks = []
    try:
        reader = PdfReader(str(path))
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            chunks.extend(
                chunk_text(
                    text,
                    path.name,
                    page=page_number,
                    extra_meta={"vendor": vendor, "model": model, "doc_type": doc_type},
                )
            )
    except Exception:
        return []
    return chunks


class TechKB:
    """Persistent VectorIndex wrapper with metadata-aware technology search."""

    def __init__(self, raw_dir: str | Path | None = None, index_dir: str | Path | None = None):
        self.raw_dir = Path(raw_dir) if raw_dir else REPO_ROOT / "data" / "raw"
        self.index_dir = Path(index_dir) if index_dir else REPO_ROOT / "data" / "index" / "tech"
        self._index: VectorIndex | None = None

    def _chunks(self) -> Iterable:
        cisco = self.raw_dir / "cisco"
        for path in sorted(cisco.glob("*")) if cisco.exists() else []:
            if not path.is_file():
                continue
            model = _model_for(path.name)
            if path.suffix.lower() == ".pdf":
                yield from _pdf_chunks(path, "Cisco", model, "datasheet")
            elif path.suffix.lower() in {".txt", ".html", ".htm"}:
                yield from _text_chunks(path, "Cisco", model, "product_page")
        for folder in (self.raw_dir / "gcp", self.raw_dir / "google"):
            if not folder.exists():
                continue
            for path in sorted(folder.glob("*")):
                if path.is_file() and path.suffix.lower() in {".txt", ".html", ".htm"}:
                    yield from _text_chunks(path, "Google", "GCP", "product_page")

    def build(self) -> VectorIndex:
        index = VectorIndex("technology")
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

    def search(self, query: str, k: int = 5, vendor: str | None = None, model: str | None = None) -> list[Hit]:
        where = {}
        if vendor:
            where["vendor"] = vendor
        if model:
            where["model"] = model
        return self._load().query(query or "", k=k, where=where or None)
