"""Offline-friendly ingestion for the P2 technology and clinical corpora.

The command writes generated files below the repository's ``data/raw`` directory.
It never substitutes invented text for a source that could not be downloaded; a
failed source is recorded in the manifest and ingestion continues.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOTS = (
    REPO_ROOT / "resources",
    Path("/Users/manalimankad/SJSU/Recommender System/Hackathon/Sources"),
    Path("/Users/manalimankad/Downloads"),
)
MANIFEST_NAME = "MANIFEST.json"
USER_AGENT = "suggest-iq-p2-ingest/1.0"


def _source_root() -> Path:
    configured = os.getenv("P2_SOURCE_ROOT")
    if configured:
        return Path(configured).expanduser()
    for root in DEFAULT_SOURCE_ROOTS:
        if root.exists():
            return root
    return REPO_ROOT / "resources"


def _find_source(name: str) -> Path | None:
    root = _source_root()
    candidates = [root / name, REPO_ROOT / "resources" / name]
    if name == "Agilent.txt":
        candidates.append(Path("/Users/manalimankad/Downloads/Agilent.txt"))
    if name == "Clinical.zip":
        candidates.append(Path("/Users/manalimankad/SJSU/Recommender System/Hackathon/Sources/Clinical.zip"))
    return next((p for p in candidates if p.exists()), None)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_path(raw_root: Path) -> Path:
    return raw_root / MANIFEST_NAME


def _read_manifest(raw_root: Path) -> dict[str, Any]:
    path = _manifest_path(raw_root)
    if not path.exists():
        return {"generated_at": None, "sources": [], "clinical_row_cap": 3000}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("sources", [])
        data.setdefault("clinical_row_cap", 3000)
        return data
    except (OSError, json.JSONDecodeError):
        return {"generated_at": None, "sources": [], "clinical_row_cap": 3000}


def _upsert(manifest: dict[str, Any], record: dict[str, Any]) -> None:
    sources = manifest.setdefault("sources", [])
    key = (record.get("source"), record.get("url"), record.get("destination"))
    sources[:] = [r for r in sources if (r.get("source"), r.get("url"), r.get("destination")) != key]
    sources.append(record)


def _write_manifest(raw_root: Path, manifest: dict[str, Any]) -> None:
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    _manifest_path(raw_root).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _urls_from_file(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [(line.strip(), line.strip()) for line in re.findall(r"https?://[^\s]+", text)]


def _download(url: str, destination: Path) -> tuple[str, str | None]:
    """Download ``url`` into ``destination`` and return status plus sha256."""
    try:
        import requests
    except ImportError as exc:
        return f"failed: missing requests ({exc})", None
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return "downloaded", sha256_file(destination)
    except Exception as exc:  # network failures must not abort other sources
        return f"failed: {type(exc).__name__}: {exc}", None


def _webpage(url: str, destination: Path) -> tuple[str, str | None]:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        return f"failed: missing web dependency ({exc})", None
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        text = soup.get_text(" ", strip=True)
        if not text:
            return "failed: empty page text", None
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        return "downloaded", sha256_file(destination)
    except Exception as exc:
        return f"failed: {type(exc).__name__}: {exc}", None


def _record_local(path: Path, destination: Path, source: str, manifest: dict[str, Any], *, url: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != destination.resolve():
        shutil.copy2(path, destination)
    _upsert(manifest, {"source": source, "url": url, "destination": str(destination), "status": "local", "sha256": sha256_file(destination)})


def ingest_cisco(raw_root: Path, manifest: dict[str, Any]) -> None:
    source = _find_source("DataSource-Cisco.txt")
    if source is None:
        _upsert(manifest, {"source": "DataSource-Cisco.txt", "url": None, "status": "failed: source file not found", "sha256": None})
        return
    urls = _urls_from_file(source)
    for index, url in enumerate(urls, 1):
        parsed = Path(urlparse(url).path).name or f"cisco-{index}.download"
        target = raw_root / "cisco" / parsed
        if target.exists():
            status, digest = "cached", sha256_file(target)
        else:
            status, digest = _download(url, target)
        _upsert(manifest, {"source": parsed, "url": url, "destination": str(target), "status": status, "sha256": digest})


def ingest_pages(kind: str, filename: str, raw_root: Path, manifest: dict[str, Any]) -> None:
    source = _find_source(filename)
    if source is None:
        _upsert(manifest, {"source": filename, "url": None, "status": "failed: source file not found", "sha256": None})
        return
    for index, url in enumerate(_urls_from_file(source), 1):
        parsed = Path(urlparse(url).path).name or f"page-{index}"
        target = raw_root / kind / f"{index:02d}-{parsed}.txt"
        if target.exists():
            status, digest = "cached", sha256_file(target)
        else:
            status, digest = _webpage(url, target)
        _upsert(manifest, {"source": target.name, "url": url, "destination": str(target), "status": status, "sha256": digest})


def ingest_clinical(raw_root: Path, manifest: dict[str, Any]) -> None:
    source = _find_source("Clinical.zip")
    if source is None:
        _upsert(manifest, {"source": "Clinical.zip", "url": None, "status": "failed: source file not found", "sha256": None})
        return
    target = raw_root / "clinical"
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source) as archive:
            archive.extractall(target)
        status = "extracted"
        digest = sha256_file(source)
    except (OSError, zipfile.BadZipFile) as exc:
        status, digest = f"failed: {type(exc).__name__}: {exc}", None
    _upsert(manifest, {"source": source.name, "url": None, "destination": str(target), "status": status, "sha256": digest})


def ingest(only: str | None = None, raw_root: Path | None = None) -> dict[str, Any]:
    raw_root = raw_root or (REPO_ROOT / "data" / "raw")
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(raw_root)
    selected = {only} if only else {"cisco", "agilent", "gcp", "clinical"}
    if "cisco" in selected:
        ingest_cisco(raw_root, manifest)
    if "agilent" in selected:
        ingest_pages("agilent", "Agilent.txt", raw_root, manifest)
    if "gcp" in selected:
        ingest_pages("gcp", "Google GCP.txt", raw_root, manifest)
    if "clinical" in selected:
        ingest_clinical(raw_root, manifest)
    _write_manifest(raw_root, manifest)
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest P2 technology and clinical sources")
    parser.add_argument("--only", choices=("cisco", "agilent", "gcp", "clinical"))
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = ingest(args.only)
    print(json.dumps({"manifest": str(_manifest_path(REPO_ROOT / "data" / "raw")), "sources": len(manifest["sources"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
