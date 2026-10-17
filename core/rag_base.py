"""Generic chunk + embed + index + query. Owner: P1. P2 and P3 USE this; they do not reimplement it.

EMBEDDING_MODE=hash   (default) deterministic offline hashed bag-of-words, no downloads, no keys.
EMBEDDING_MODE=local  sentence-transformers (pip install sentence-transformers); model from LOCAL_EMBEDDING_MODEL.
EMBEDDING_MODE=litellm provider embeddings via litellm.embedding using EMBEDDING_MODEL.
The index is brute-force cosine similarity over a numpy matrix, which is plenty for this corpus size.
"""
import json
import math
import os
import re
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import numpy as np
from pydantic import BaseModel, Field

from core.schemas import Citation

HASH_DIM = 1024


class Chunk(BaseModel):
    id: str
    text: str
    # REQUIRED key: "source_doc". Common optional keys: page (int), section (str), vendor, model,
    # company, form, fiscal_year, report_year, doc_type.
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Hit(BaseModel):
    chunk: Chunk
    score: float


def chunk_text(
    text: str,
    source_doc: str,
    page: Optional[int] = None,
    section: Optional[str] = None,
    size: int = 800,
    overlap: int = 100,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> List[Chunk]:
    """Split `text` into ~`size`-character chunks on whitespace with `overlap` characters of overlap."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    meta: Dict[str, Any] = {"source_doc": source_doc, **(extra_meta or {})}
    if page is not None:
        meta["page"] = page
    if section is not None:
        meta["section"] = section
    chunks: List[Chunk] = []
    start, n = 0, 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            space = text.rfind(" ", start + size // 2, end)
            end = space if space != -1 else end
        piece = text[start:end].strip()
        if piece:
            chunks.append(Chunk(id=f"{source_doc}#p{page if page is not None else 0}#{n}", text=piece, metadata=dict(meta)))
            n += 1
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


def _embed_hash(texts: List[str]) -> np.ndarray:
    out = np.zeros((len(texts), HASH_DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        for tok in _tokens(t):
            h = zlib.crc32(tok.encode())
            out[i, h % HASH_DIM] += 1.0 if (h >> 16) & 1 else -1.0
        out[i] = np.sign(out[i]) * np.log1p(np.abs(out[i]))
    return _normalize(out)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


def embedding_mode() -> str:
    return os.getenv("EMBEDDING_MODE", "hash").lower()


def embed(texts: List[str]) -> np.ndarray:
    """Return an (len(texts), dim) L2-normalised float32 matrix."""
    mode = embedding_mode()
    if mode == "hash":
        return _embed_hash(texts)
    if mode == "local":
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
        return _normalize(np.asarray(model.encode(texts, show_progress_bar=False), dtype=np.float32))
    if mode == "litellm":
        import litellm

        resp = litellm.embedding(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), input=texts)
        return _normalize(np.asarray([d["embedding"] for d in resp["data"]], dtype=np.float32))
    raise ValueError(f"Unknown EMBEDDING_MODE={mode!r}")


def _matches(meta: Dict[str, Any], where: Optional[Dict[str, Any]]) -> bool:
    if not where:
        return True
    for key, want in where.items():
        have = meta.get(key)
        if isinstance(want, (list, tuple, set)):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


class VectorIndex:
    def __init__(self, name: str):
        self.name = name
        self.chunks: List[Chunk] = []
        self._matrix: Optional[np.ndarray] = None

    def __len__(self) -> int:
        return len(self.chunks)

    def add(self, chunks: Iterable[Chunk], batch_size: int = 256) -> None:
        new = list(chunks)
        for c in new:
            if "source_doc" not in c.metadata:
                raise ValueError(f"Chunk {c.id} is missing metadata['source_doc']")
        for i in range(0, len(new), batch_size):
            batch = new[i : i + batch_size]
            vecs = embed([c.text for c in batch])
            self._matrix = vecs if self._matrix is None else np.vstack([self._matrix, vecs])
            self.chunks.extend(batch)

    def query(self, text: str, k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Hit]:
        """Top-k chunks by cosine similarity. `where` = exact-match metadata filter (value or list of values)."""
        if self._matrix is None or not self.chunks:
            return []
        scores = self._matrix @ embed([text])[0]
        order = np.argsort(-scores)
        hits: List[Hit] = []
        for idx in order:
            c = self.chunks[int(idx)]
            if _matches(c.metadata, where):
                hits.append(Hit(chunk=c, score=float(scores[idx])))
                if len(hits) == k:
                    break
        return hits

    def save(self, directory: Union[str, Path]) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        (d / "chunks.json").write_text(
            json.dumps({"name": self.name, "embedding_mode": embedding_mode(), "chunks": [c.model_dump() for c in self.chunks]})
        )
        if self._matrix is not None:
            np.save(d / "matrix.npy", self._matrix)

    @classmethod
    def load(cls, directory: Union[str, Path]) -> "VectorIndex":
        d = Path(directory)
        data = json.loads((d / "chunks.json").read_text())
        if data["embedding_mode"] != embedding_mode():
            raise ValueError(
                f"Index built with EMBEDDING_MODE={data['embedding_mode']} but current mode is {embedding_mode()}; rebuild it."
            )
        idx = cls(data["name"])
        idx.chunks = [Chunk(**c) for c in data["chunks"]]
        mat = d / "matrix.npy"
        idx._matrix = np.load(mat) if mat.exists() else None
        return idx


def hits_to_citations(hits: List[Hit], max_snippet: int = 300) -> List[Citation]:
    """Convert retrieval hits to schema Citations (verbatim snippet from the chunk)."""
    cites: List[Citation] = []
    for h in hits:
        m = h.chunk.metadata
        page = m.get("page")
        cites.append(
            Citation(
                source_doc=str(m["source_doc"]),
                section=m.get("section"),
                page=int(page) if isinstance(page, (int, float)) and not math.isnan(page) else None,
                snippet=h.chunk.text[:max_snippet],
            )
        )
    return cites
