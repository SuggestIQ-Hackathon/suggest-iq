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


def _urls_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in re.findall(r"https?://[^\s]+", text)]


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


# --- Browser-saved pages -----------------------------------------------------------------
# agilent.com and cisco.com product pages return HTTP 403 to scripts, so they are saved from a
# browser ("Webpage, Complete") into Sources/URLs/ and ingested from disk here. Each page is
# matched to its URL by the "saved from url=" line the browser writes, cleaned of menus and
# scripts, and written to data/raw/<vendor>/[<section>/]<slug>.html.
AGILENT_SECTIONS = (
    ("real-time-cell-metabolic-analysis", "seahorse"),
    ("digital-pathology", "digital-pathology"),
    ("special-stains", "special-stains"),
    ("/about/newsroom/", "news"),
)
_DROP_TAGS = ["script", "style", "noscript", "svg", "iframe", "template", "nav", "footer", "form", "button", "select"]
_DROP_MARKERS = ("cookie", "onetrust", "modal", "megamenu", "mega-menu", "breadcrumb")
_BLOCK_TAGS = {
    "div", "section", "article", "aside", "ul", "ol", "li", "p", "h1", "h2", "h3", "h4", "h5", "h6", "table",
    "thead", "tbody", "tfoot", "tr", "td", "th", "dl", "dt", "dd", "figure", "figcaption", "blockquote", "pre", "main",
}


def _saved_pages_root() -> Path | None:
    configured = os.getenv("P2_SAVED_PAGES_DIR")
    if configured:
        candidates = [Path(configured).expanduser()]
    elif os.getenv("P2_SOURCE_ROOT"):  # an explicit source root (e.g. test fixtures) also scopes saved pages
        candidates = [Path(os.environ["P2_SOURCE_ROOT"]).expanduser() / "URLs"]
    else:
        candidates = [REPO_ROOT.parent / "Sources" / "URLs", REPO_ROOT / "resources" / "URLs"]
    return next((p for p in candidates if p.is_dir()), None)


def _saved_page_url(text: str) -> str | None:
    match = re.search(r"saved from url=\(\d+\)(\S+)", text[:3000]) or re.search(
        r'<link rel="canonical" href="([^"]+)"', text[:30000]
    )
    return match.group(1).split("#")[0] if match else None


def _saved_page_problem(text: str, url: str) -> str | None:
    title = (re.search(r"<title>(.*?)</title>", text, re.S | re.I) or [None, ""])[1]
    if re.search(r"access denied", title, re.I) or "You don't have permission to access" in text[:5000]:
        return "access denied page"
    if "Agilent404" in url or re.search(r"page not found|\b404\b", title, re.I):
        return "404 page"
    return None


def _clean_saved_html(text: str, url: str) -> tuple[str, int]:
    """Return a small clean HTML document (headings, paragraphs, table rows, PDF links) and its text length."""
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag.get("content", "") if desc_tag else ""
    raw = text.replace("\\/", "/").replace('\\"', '"')
    pdfs = sorted(
        set(re.findall(r"https?://[^\"'\s<>()]+?\.pdf", raw, re.I))
        | {"https://www.agilent.com" + p for p in re.findall(r"/cs/library/[A-Za-z0-9_\-/.%]+?\.pdf", raw, re.I)}
    )
    # Main content area; if it is nearly empty (e.g. Agilent press releases keep only a sign-in
    # notice in #content), use the whole body minus the site header/nav/footer instead.
    candidates = soup.select("main, [role=main], #content, article")
    root = max(candidates, key=lambda el: len(el.get_text(" ", strip=True)), default=None)
    if root is None or len(root.get_text(" ", strip=True)) < 300:
        root = soup.body or soup
    for node in root.find_all(_DROP_TAGS):
        node.decompose()
    for node in root.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    for node in list(root.find_all(True)):
        if node.attrs is None:  # already removed with a parent
            continue
        labels = " ".join([str(node.get("id", "")), " ".join(node.get("class", []) or [])]).lower()
        if any(marker in labels for marker in _DROP_MARKERS) or "footer" in str(node.get("id", "")).lower() or node.get("role") in ("navigation", "dialog"):
            node.decompose()
    if root is soup.body:
        for header in root.find_all("header", recursive=False):
            header.decompose()

    def clean(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    out: list[str] = []

    def walk(node) -> None:
        for child in node.find_all(True, recursive=False):
            name = child.name.lower()
            if re.fullmatch(r"h[1-6]", name):
                value = clean(child.get_text(" "))
                if value:
                    level = min(int(name[1]), 4)
                    out.append(f"<h{level}>{html_escape(value)}</h{level}>")
            elif name == "tr":
                cells = [html_escape(clean(td.get_text(" "))) for td in child.find_all(["td", "th"], recursive=False)]
                if "".join(cells):
                    out.append("<tr><td>" + "</td><td>".join(cells) + "</td></tr>")
            elif not any(grand.name and grand.name.lower() in _BLOCK_TAGS for grand in child.find_all(True, recursive=False)):
                value = clean(child.get_text(" "))
                if value:
                    out.append(f"<li>{html_escape(value)}</li>" if name == "li" else f"<p>{html_escape(value)}</p>")
            else:
                walk(child)

    walk(root)
    seen: set[str] = set()
    lines = [line for line in out if not (line in seen or seen.add(line))]
    body = re.sub(r"((?:<tr>.*?</tr>\n?)+)", lambda m: "<table>\n" + m.group(1) + "</table>\n", "\n".join(lines), flags=re.S)
    text_len = len(clean(re.sub(r"<[^>]+>", " ", body)))
    if pdfs:
        body += "\n<h2>Documents (PDF links found on page)</h2>\n<ul class=\"pcs-pdfs\">\n" + "\n".join(
            f'<li><a href="{html_escape(u)}">{html_escape(u.rsplit("/", 1)[-1])}</a></li>' for u in pdfs
        ) + "\n</ul>"
    document = (
        f"<!-- saved from url=({len(url):04d}){url} -->\n<!doctype html>\n<html><head><meta charset=\"utf-8\">\n"
        f"<title>{html_escape(title)}</title>\n<link rel=\"canonical\" href=\"{html_escape(url)}\">\n"
        f"<meta name=\"description\" content=\"{html_escape(desc)}\">\n</head><body><main>\n{body}\n</main></body></html>\n"
    )
    return document, text_len


def html_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# Pages that were ingested before under these names keep them, so catalog `source_doc` values and
# citations stay stable (COMMON.md rule 5).
LEGACY_NAMES = {
    "https://www.agilent.com/en/product/digital-pathology": "agilent-digital-pathology.html",
    "https://www.agilent.com/en/product/digital-pathology/digital-pathology-scanners": "agilent-digital-pathology-scanners.html",
    "https://www.agilent.com/en/product/digital-pathology/digital-pathology-scanners/nanozoomer-slide-scanner-system-4370282": "agilent-nanozoomer-slide-scanner.html",
    "https://www.agilent.com/en/product/special-stains": "artisan-link-pro-special-stains.html",
    "https://www.agilent.com/about/newsroom/presrel/2023/07mar-ca23010.html": "agilent-scientists-choice-awards.html",
    "https://www.agilent.com/en/product/cell-analysis/real-time-cell-metabolic-analysis": "agilent-seahorse-real-time-cell-metabolic-analysis.html",
}
CISCO_PRODUCT_PAGES = (  # saved Cisco product pages -> the names already used in data/raw/cisco
    ("catalyst-8300", "cisco-catalyst-8300-product-page.html"),
    ("catalyst-8200", "cisco-catalyst-8200-product-page.html"),
    ("catalyst-8000v", "cisco-catalyst-8000v-product-page.html"),
    ("4000-series-integrated-services-routers", "cisco-isr-4000-product-page.html"),
    ("asr-1000", "cisco-asr-1000-product-page.html"),
)


def _saved_page_destination(raw_root: Path, url: str) -> Path | None:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.rstrip("/")
    slug = Path(path).name.removesuffix(".html") or "index"
    if host.endswith("agilent.com"):
        section = next((name for marker, name in AGILENT_SECTIONS if marker in url), "other")
        return raw_root / "agilent" / section / LEGACY_NAMES.get(url.rstrip("/"), f"{slug}.html")
    if host.endswith("cisco.com"):
        if slug == "index":
            name = next((legacy for marker, legacy in CISCO_PRODUCT_PAGES if marker in path), None)
            return raw_root / "cisco" / (name or f"{Path(path).parent.name}.html")
        return raw_root / "cisco" / f"{slug}.html"
    return None


def collect_saved_pages(root: Path | None = None) -> dict[str, tuple[Path, str]]:
    """Map each saved page URL to (saved file, page text). If a URL was saved twice, keep the larger file."""
    root = root or _saved_pages_root()
    pages: dict[str, tuple[Path, str]] = {}
    if root is None:
        return pages
    for path in sorted(root.rglob("*.htm*")):
        if any(part.endswith("_files") for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        url = _saved_page_url(text)
        if not url:
            continue
        key = url.rstrip("/")
        if key not in pages or len(text) > len(pages[key][1]):
            pages[key] = (path, text)
    return pages


def ingest_saved_pages(raw_root: Path, manifest: dict[str, Any], vendor: str, saved: dict[str, tuple[Path, str]] | None = None) -> None:
    saved = collect_saved_pages() if saved is None else saved
    for url, (path, text) in sorted(saved.items()):
        destination = _saved_page_destination(raw_root, url)
        if destination is None or destination.parts[len(raw_root.parts)] != vendor:
            continue
        problem = _saved_page_problem(text, url)
        if problem:
            _upsert(manifest, {"source": path.name, "url": url, "destination": None, "status": f"skipped: {problem}", "sha256": None})
            continue
        document, text_len = _clean_saved_html(text, url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")
        _upsert(manifest, {
            "source": destination.name, "url": url, "destination": str(destination),
            "status": "local: browser-saved page", "sha256": sha256_file(destination),
            "saved_file": str(path), "text_chars": text_len,
        })


def ingest_cisco(raw_root: Path, manifest: dict[str, Any], saved: dict[str, tuple[Path, str]] | None = None) -> None:
    source = _find_source("DataSource-Cisco.txt")
    if source is None:
        _upsert(manifest, {"source": "DataSource-Cisco.txt", "url": None, "status": "failed: source file not found", "sha256": None})
        return
    urls = _urls_from_file(source)
    for index, url in enumerate(urls, 1):
        parsed = Path(urlparse(url).path).name or f"cisco-{index}.download"
        target = raw_root / "cisco" / parsed
        equivalent = _saved_equivalent(url, saved or {})
        if equivalent:
            _upsert(manifest, {"source": parsed, "url": url, "destination": str(target), "sha256": None,
                               "status": f"local: see browser-saved page {_saved_page_destination(raw_root, equivalent).name}"})
            continue
        if target.exists():
            status, digest = "cached", sha256_file(target)
        else:
            status, digest = _download(url, target)
        _upsert(manifest, {"source": parsed, "url": url, "destination": str(target), "status": status, "sha256": digest})


def _saved_equivalent(url: str, saved: dict[str, tuple[Path, str]]) -> str | None:
    """URL of a browser-saved copy of ``url`` (exact match, or the same Cisco product page under its new path)."""
    key = url.split("#")[0].rstrip("/")
    if key in saved:
        return key
    if "cisco.com" in key and key.endswith("index.html"):
        marker = next((m for m, _ in CISCO_PRODUCT_PAGES if m in key), None)
        if marker:
            return next((u for u in saved if "cisco.com" in u and marker in u and u.endswith("index.html")), None)
    return None


def ingest_pages(kind: str, filename: str, raw_root: Path, manifest: dict[str, Any], saved: dict[str, tuple[Path, str]] | None = None) -> None:
    source = _find_source(filename)
    if source is None:
        _upsert(manifest, {"source": filename, "url": None, "status": "failed: source file not found", "sha256": None})
        return
    for index, url in enumerate(_urls_from_file(source), 1):
        parsed = Path(urlparse(url).path).name or f"page-{index}"
        target = raw_root / kind / f"{index:02d}-{parsed}.txt"
        equivalent = _saved_equivalent(url, saved or {})
        if equivalent:
            # Covered by a browser-saved page (separate manifest entry); don't request the blocked site.
            _upsert(manifest, {"source": target.name, "url": url, "destination": None, "sha256": None,
                               "status": f"local: see browser-saved page {_saved_page_destination(raw_root, equivalent).name}"})
            continue
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
    saved = collect_saved_pages() if selected & {"cisco", "agilent"} else {}
    if "cisco" in selected:
        ingest_saved_pages(raw_root, manifest, "cisco", saved)
        ingest_cisco(raw_root, manifest, saved)
    if "agilent" in selected:
        ingest_saved_pages(raw_root, manifest, "agilent", saved)
        ingest_pages("agilent", "Agilent.txt", raw_root, manifest, saved)
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
