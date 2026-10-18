"""Section-aware retrieval over the provided SEC filings."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from pypdf import PdfReader

from core.rag_base import Hit, VectorIndex, chunk_text
from p3_sec_csr.knowledge.retrieval import hybrid_search

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(__file__).with_name("sec_manifest.json")
INDEX_PATH = REPO_ROOT / "data" / "index" / "sec"
SECTION_PATTERNS = (
    ("Item 1. Business", re.compile(r"\bitem\s+1\.?\s+business\b", re.IGNORECASE)),
    (
        "Item 1A. Risk Factors",
        re.compile(r"\bitem\s+1a\.?\s+risk\s+factors\b", re.IGNORECASE),
    ),
    (
        "Item 7. Management's Discussion and Analysis",
        re.compile(r"\bitem\s+7\.?\s+management.?s\s+discussion", re.IGNORECASE),
    ),
    (
        "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
        re.compile(r"\bitem\s+7a\.?\s+quantitative\s+and\s+qualitative", re.IGNORECASE),
    ),
    (
        "Item 8. Financial Statements and Supplementary Data",
        re.compile(r"\bitem\s+8\.?\s+financial\s+statements", re.IGNORECASE),
    ),
)


def detect_section(text: str, current: str | None = None) -> str | None:
    """Detect a 10-K item heading while ignoring body-text cross-references."""
    for raw_line in text.splitlines()[:60]:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not re.match(r"^item\s+", line, re.IGNORECASE):
            continue
        for name, pattern in SECTION_PATTERNS:
            if pattern.search(line):
                return name
    return current


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text())


class SECKB:
    """Lazy-loading SEC vector index with exact metadata filters."""

    def __init__(self, index_path: Path | str = INDEX_PATH):
        self.index_path = Path(index_path)
        self._index: VectorIndex | None = None

    @property
    def manifest(self) -> list[dict]:
        return load_manifest()

    def _pdf_path(self, raw_root: Path, entry: dict) -> Path:
        direct = raw_root / entry["file"]
        if direct.exists():
            return direct
        matches = list(raw_root.rglob(Path(entry["file"]).name))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"Could not uniquely locate {entry['file']} below {raw_root}"
            )
        return matches[0]

    def _chunks_for_entry(self, raw_root: Path, entry: dict) -> Iterable:
        reader = PdfReader(str(self._pdf_path(raw_root, entry)))
        section = None
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            section = detect_section(text, section)
            yield from chunk_text(
                text,
                source_doc=entry["logical_name"],
                page=page_number,
                section=section,
                size=1100,
                overlap=150,
                extra_meta={
                    "company": entry["company"],
                    "form": entry["form"],
                    "fiscal_year": entry["fiscal_year"],
                    "item": section,
                    "period_end": entry["period_end"],
                },
            )

    def build(self, *, force: bool = False) -> int:
        if not force and (self.index_path / "chunks.json").exists():
            self._index = VectorIndex.load(self.index_path)
            return len(self._index)
        from p3_sec_csr.knowledge.ingest import ensure_extracted

        raw_root = ensure_extracted("sec")
        index = VectorIndex("sec")
        for entry in self.manifest:
            index.add(self._chunks_for_entry(raw_root, entry))
        index.save(self.index_path)
        self._index = index
        return len(index)

    def _load(self) -> VectorIndex:
        if self._index is None:
            if (self.index_path / "chunks.json").exists():
                self._index = VectorIndex.load(self.index_path)
            else:
                self.build()
        return self._index

    def search(
        self,
        query: str,
        k: int = 5,
        company: str | None = None,
        item: str | None = None,
        fiscal_year: int | None = None,
    ) -> list[Hit]:
        where = {
            key: value
            for key, value in {
                "company": company,
                "item": item,
                "fiscal_year": fiscal_year,
            }.items()
            if value is not None
        }
        return hybrid_search(
            self._load(), query or "SEC filing", k=k, where=where
        )
