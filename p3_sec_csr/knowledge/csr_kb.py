"""Retrieval over the 2023 and 2024 SOFI food-security reports."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from core.rag_base import Hit, VectorIndex, chunk_text
from p3_sec_csr.knowledge.retrieval import hybrid_search

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "data" / "index" / "csr"

def detect_heading(text: str, current: str | None = None) -> str | None:
    """Return a useful chapter/section heading from the start of a PDF page."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()[:30]]
    for line in lines:
        if re.match(
            r"^(CHAPTER|PART|SECTION|ANNEX)\s+[A-Z0-9]+\b", line, re.IGNORECASE
        ):
            return line[:180]
    for line in lines:
        letters = [char for char in line if char.isalpha()]
        if (
            8 <= len(line) <= 140
            and letters
            and sum(char.isupper() for char in letters) / len(letters) >= 0.85
        ):
            return line[:180]
    return current


class CSRKB:
    """Lazy-loading SOFI vector index with report-year filtering."""

    def __init__(self, index_path: Path | str = INDEX_PATH):
        self.index_path = Path(index_path)
        self._index: VectorIndex | None = None

    def build(self, *, force: bool = False) -> int:
        if not force and (self.index_path / "chunks.json").exists():
            self._index = VectorIndex.load(self.index_path)
            return len(self._index)
        from p3_sec_csr.knowledge.ingest import ensure_extracted

        raw_root = ensure_extracted("csr")
        pdfs = sorted(raw_root.rglob("SOFI-*.pdf"))
        if not pdfs:
            raise FileNotFoundError(f"No SOFI PDFs found below {raw_root}")
        index = VectorIndex("csr")
        all_chunks = []
        for pdf in pdfs:
            year_match = re.search(r"(20\d{2})", pdf.name)
            if not year_match:
                continue
            year = int(year_match.group(1))
            reader = PdfReader(str(pdf))
            section = None
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    continue
                section = detect_heading(text, section)
                all_chunks.extend(
                    chunk_text(
                        text,
                        source_doc=pdf.name,
                        page=page_number,
                        section=section,
                        size=1100,
                        overlap=150,
                        extra_meta={"report_year": year, "doc_type": "SOFI report"},
                    )
                )
        index.add(all_chunks)
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
        self, query: str, k: int = 5, report_year: int | None = None
    ) -> list[Hit]:
        where = {"report_year": report_year} if report_year is not None else None
        return hybrid_search(
            self._load(), query or "food security", k=k, where=where
        )
