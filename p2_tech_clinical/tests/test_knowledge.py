from __future__ import annotations

import json
import importlib
from pathlib import Path

from p2_tech_clinical.knowledge.clinical_kb import ClinicalKB
from p2_tech_clinical.knowledge.tech_kb import TechKB, _text_chunks


ingest_module = importlib.import_module("p2_tech_clinical.knowledge.ingest")


def test_tech_kb_preserves_metadata_and_filters(tmp_path: Path):
    raw = tmp_path / "raw"
    cisco = raw / "cisco"
    gcp = raw / "gcp"
    cisco.mkdir(parents=True)
    gcp.mkdir()
    (cisco / "catalyst-8200.txt").write_text("Catalyst 8200 interface options include WAN connectivity and IPsec throughput.")
    (cisco / "catalyst-8300.txt").write_text("Catalyst 8300 supports routed interfaces and secure WAN connectivity.")
    (gcp / "mcp.txt").write_text("Google GCP Model Context Protocol and retrieval augmented generation.")

    kb = TechKB(raw, tmp_path / "index")
    hits = kb.search("Catalyst 8200 WAN interface", k=5, vendor="Cisco", model="Catalyst 8200")
    assert hits
    assert hits[0].chunk.metadata["source_doc"] == "catalyst-8200.txt"
    assert hits[0].chunk.metadata["vendor"] == "Cisco"
    assert hits[0].chunk.metadata["model"] == "Catalyst 8200"
    assert all(hit.chunk.metadata["model"] == "Catalyst 8200" for hit in hits)


def test_tech_kb_cleans_html_before_chunking(tmp_path: Path):
    html = tmp_path / "catalyst-8300.html"
    html.write_text(
        """
        <html><head><script>tracking_secret()</script></head>
        <body><div class='cookie-banner'>cookie notice</div>
        <main><h1>Catalyst 8300</h1><p>Supports secure WAN interfaces.</p></main>
        </body></html>
        """,
        encoding="utf-8",
    )

    chunks = _text_chunks(html, "Cisco", "Catalyst 8300", "product_page")
    combined = " ".join(chunk.text for chunk in chunks)
    assert "Catalyst 8300" in combined
    assert "secure WAN interfaces" in combined
    assert "tracking_secret" not in combined
    assert "cookie notice" not in combined
    assert chunks[0].metadata == {
        "source_doc": "catalyst-8300.html",
        "vendor": "Cisco",
        "model": "Catalyst 8300",
        "doc_type": "product_page",
    }


def test_clinical_kb_filters_trial_source_type(tmp_path: Path):
    raw = tmp_path / "raw"
    agilent = raw / "agilent"
    clinical = raw / "clinical" / "Diabetes"
    agilent.mkdir(parents=True)
    clinical.mkdir(parents=True)
    (agilent / "nanozoomer.txt").write_text("NanoZoomer slide scanner supports whole-slide digital pathology imaging.")
    (clinical / "ctg-studies_diabetes.csv").write_text(
        "NCT Number,Study Title,Brief Summary,Conditions,Interventions,Primary Outcome Measures\n"
        "NCT123,Diabetes study,Study of diabetes outcomes,Diabetes,Intervention,Outcome measure\n"
    )

    kb = ClinicalKB(raw, tmp_path / "index")
    instrument_hits = kb.search("whole-slide digital pathology imaging", k=5, source_type="product_page")
    trial_hits = kb.search("diabetes outcomes", k=5, source_type="trial")
    assert instrument_hits and instrument_hits[0].chunk.metadata["model"] == "NanoZoomer"
    assert trial_hits and trial_hits[0].chunk.metadata["doc_type"] == "trial"
    assert trial_hits[0].chunk.metadata["source_doc"] == "ctg-studies_diabetes.csv"
    assert trial_hits[0].chunk.metadata["section"] == "NCT123"


def test_ingest_records_missing_sources_without_fabrication(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("P2_SOURCE_ROOT", str(tmp_path / "missing"))
    monkeypatch.setattr(ingest_module, "_find_source", lambda _name: None)
    manifest = ingest_module.ingest("clinical", tmp_path / "raw")
    assert manifest["sources"]
    record = manifest["sources"][0]
    assert record["status"].startswith("failed:")
    assert record["sha256"] is None
    assert not list((tmp_path / "raw").rglob("*.pdf"))
    saved = json.loads((tmp_path / "raw" / "MANIFEST.json").read_text())
    assert saved["sources"] == manifest["sources"]


def test_ingest_saved_pages_cleans_and_files_by_section(tmp_path: Path):
    saved_dir = tmp_path / "URLs" / "crawled"
    saved_dir.mkdir(parents=True)
    url = "https://www.agilent.com/en/product/cell-analysis/real-time-cell-metabolic-analysis/xf-analyzers/seahorse-xf-pro-analyzer-1980223"
    (saved_dir / "Seahorse XF Pro _ Agilent.html").write_text(
        f"<!-- saved from url=({len(url):04d}){url} -->\n"
        "<html><head><title>Seahorse XF Pro | Agilent</title></head><body>"
        "<header><nav>Products Applications Sign In</nav></header>"
        "<div id='content'><header><h1>Seahorse XF Pro Analyzer</h1></header>"
        "<p>Measure mitochondrial respiration and glycolysis in a 96-well format with Seahorse XF Pro.</p>"
        + "<p>Detail paragraph about OCR and ECAR measurement.</p>" * 10
        + "<div class='onetrust-banner'>cookie consent text</div></div>"
        "<!-- assets /cs/library/usermanuals/public/xf-pro-user-guide.pdf --></body></html>",
        encoding="utf-8",
    )
    blocked_url = "https://www.agilent.com/en/product/special-stains/special-stains-kits/pas-kit-123456"
    (saved_dir / "Access Denied.html").write_text(
        f"<!-- saved from url=({len(blocked_url):04d}){blocked_url} --><title>Access Denied</title>", encoding="utf-8"
    )

    raw = tmp_path / "raw"
    manifest = {"sources": []}
    saved = ingest_module.collect_saved_pages(tmp_path / "URLs")
    ingest_module.ingest_saved_pages(raw, manifest, "agilent", saved)

    page = raw / "agilent" / "seahorse" / "seahorse-xf-pro-analyzer-1980223.html"
    text = page.read_text(encoding="utf-8")
    assert "Seahorse XF Pro Analyzer" in text and "96-well format" in text
    assert "cookie consent" not in text and "Sign In" not in text
    assert "https://www.agilent.com/cs/library/usermanuals/public/xf-pro-user-guide.pdf" in text
    statuses = {record["url"]: record["status"] for record in manifest["sources"]}
    assert statuses[url] == "local: browser-saved page"
    assert statuses[blocked_url] == "skipped: access denied page"
    assert not list((raw / "agilent").rglob("pas-kit-*"))

    hits = ClinicalKB(raw, tmp_path / "index").search("mitochondrial respiration 96-well", k=3)
    assert hits and hits[0].chunk.metadata["model"] == "Seahorse"
    assert hits[0].chunk.metadata["source_doc"] == "seahorse-xf-pro-analyzer-1980223.html"
