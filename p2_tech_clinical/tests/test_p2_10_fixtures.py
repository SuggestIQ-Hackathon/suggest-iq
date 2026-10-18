from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from pathlib import Path

import pytest

from core.rag_base import Chunk, Hit
from p2_tech_clinical.agents.clinical_agent import ClinicalAgent
from p2_tech_clinical.agents.tech_agent import TechAgent
from p2_tech_clinical.knowledge.clinical_kb import ClinicalKB
from p2_tech_clinical.knowledge.tech_kb import TechKB, _model_for
from p2_tech_clinical.recommenders.hardware import recommend


ingest_module = importlib.import_module("p2_tech_clinical.knowledge.ingest")
FIXTURES = Path(__file__).parent / "fixtures"
CATALOG_DIR = Path(__file__).parents[1] / "recommenders" / "catalog"


@pytest.fixture(autouse=True)
def _offline_mode(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODE", "hash")
    monkeypatch.setenv("LLM_MODE", "mock")


class FakeKB:
    def __init__(self, hits: list[Hit]):
        self.hits = hits

    def search(self, query, k=5, vendor=None, model=None, source_type=None):
        selected = [
            hit for hit in self.hits
            if source_type is None or hit.chunk.metadata.get("doc_type") == source_type
        ]
        return selected[:k]


def _hit(text: str, source_doc: str, *, doc_type: str | None = None, model: str | None = None, page: int | None = None) -> Hit:
    metadata = {"source_doc": source_doc}
    if doc_type:
        metadata["doc_type"] = doc_type
    if model:
        metadata["model"] = model
    if page is not None:
        metadata["page"] = page
    return Hit(chunk=Chunk(id=source_doc, text=text, metadata=metadata), score=0.9)


def test_p201_ingestion_uses_local_fixtures_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("P2_SOURCE_ROOT", str(FIXTURES))

    def fake_download(url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURES / "cisco-fixture.txt", destination)
        return "downloaded", ingest_module.sha256_file(destination)

    monkeypatch.setattr(ingest_module, "_download", fake_download)
    raw_root = tmp_path / "raw"
    first = ingest_module.ingest("cisco", raw_root)
    destination = raw_root / "cisco" / "cisco-fixture.txt"
    assert destination.read_text(encoding="utf-8").startswith("Catalyst 8300")
    assert first["sources"][0]["status"] == "downloaded"
    assert first["sources"][0]["sha256"] == hashlib.sha256(destination.read_bytes()).hexdigest()

    second = ingest_module.ingest("cisco", raw_root)
    assert second["sources"][0]["status"] == "cached"
    manifest = json.loads((raw_root / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["sources"][0]["source"] == "cisco-fixture.txt"


def test_p201_page_ingestion_uses_local_html_fixtures(tmp_path, monkeypatch):
    monkeypatch.setenv("P2_SOURCE_ROOT", str(FIXTURES))

    def fake_webpage(url, destination):
        source = FIXTURES / ("gcp-fixture.html" if "gcp" in url else "agilent-fixture.html")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return "downloaded", ingest_module.sha256_file(destination)

    monkeypatch.setattr(ingest_module, "_webpage", fake_webpage)
    raw_root = tmp_path / "raw"
    agilent = ingest_module.ingest("agilent", raw_root)
    gcp = ingest_module.ingest("gcp", raw_root)
    assert agilent["sources"][0]["status"] == "downloaded"
    assert gcp["sources"][0]["status"] == "downloaded"
    assert list((raw_root / "agilent").glob("*.txt"))
    assert list((raw_root / "gcp").glob("*.txt"))


def test_p202_and_p203_fixture_chunks_preserve_metadata_and_search(tmp_path):
    tech = TechKB(FIXTURES, tmp_path / "tech-index")
    tech_hits = tech.search("Catalyst 8300 secure WAN", vendor="Cisco", model="Catalyst 8300")
    assert tech_hits
    assert tech_hits[0].chunk.metadata["source_doc"] == "catalyst-8300.txt"
    assert tech_hits[0].chunk.metadata["model"] == "Catalyst 8300"

    clinical = ClinicalKB(FIXTURES, tmp_path / "clinical-index")
    paper_hits = clinical.search("Fixture diabetes evidence", source_type="paper")
    trial_hits = clinical.search("diabetes fixture intervention", source_type="trial")
    assert paper_hits
    assert paper_hits[0].chunk.metadata["source_doc"] == "fixture-diabetes.pdf"
    assert paper_hits[0].chunk.metadata["page"] == 1
    assert paper_hits[0].chunk.metadata["source_doc"]
    assert trial_hits
    assert trial_hits[0].chunk.metadata["source_doc"] == "ctg-studies_diabetes.csv"
    assert trial_hits[0].chunk.metadata["section"] == "NCT-FIXTURE"


def test_p205_catalogs_match_required_schema():
    required = {
        "item_id", "vendor", "name", "category", "compatible_models", "specs",
        "typical_failure_symptoms", "cost_tier", "lead_time_tier", "source_doc",
        "source_page", "verified",
    }
    item_ids = []
    for path in (CATALOG_DIR / "cisco_parts.json", CATALOG_DIR / "agilent_instruments.json"):
        entries = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(entries, list)
        for entry in entries:
            assert required <= set(entry)
            assert isinstance(entry["compatible_models"], list)
            assert isinstance(entry["specs"], dict)
            assert isinstance(entry["typical_failure_symptoms"], list)
            assert 1 <= entry["cost_tier"] <= 5
            assert entry["lead_time_tier"] is None or 1 <= entry["lead_time_tier"] <= 5
            assert isinstance(entry["verified"], bool)
            item_ids.append(entry["item_id"])
    assert len(item_ids) == len(set(item_ids))


def test_p205_hardware_compatibility_and_deterministic_ranking():
    catalog = [
        {
            "item_id": "CISCO-FIXTURE-A",
            "vendor": "Cisco",
            "name": "Catalyst 8300 interface module",
            "category": "interface",
            "compatible_models": ["Catalyst 8300"],
            "specs": {},
            "typical_failure_symptoms": ["packet loss"],
            "cost_tier": 3,
            "lead_time_tier": 3,
            "source_doc": "fixture.pdf",
            "source_page": 1,
            "verified": True,
        },
        {
            "item_id": "CISCO-FIXTURE-Z",
            "vendor": "Cisco",
            "name": "ASR 1000 interface module",
            "category": "interface",
            "compatible_models": ["ASR 1000"],
            "specs": {},
            "typical_failure_symptoms": ["packet loss"],
            "cost_tier": 3,
            "lead_time_tier": 3,
            "source_doc": "fixture.pdf",
            "source_page": 1,
            "verified": True,
        },
    ]
    first = recommend("Catalyst 8300 packet loss", catalog, filters={"model": "Catalyst 8300"}, top_k=3)
    second = recommend("Catalyst 8300 packet loss", catalog, filters={"model": "Catalyst 8300"}, top_k=3)
    assert [item.item_id for item in first] == ["CISCO-FIXTURE-A"]
    assert [item.item_id for item in first] == [item.item_id for item in second]


def test_p206_missing_diagnostics_returns_information_request():
    agent = ClinicalAgent()
    agent.kb = FakeKB([_hit(
        "NanoZoomer instrument evidence describes imaging.",
        "nanozoomer.html",
        doc_type="product_page",
        model="NanoZoomer",
    )])
    response = agent.run("The Agilent NanoZoomer has an instrument error code.")
    assert response.status == "INFORMATION_REQUEST"
    assert response.missing_diagnostics_needed
    assert all(item.category == "Diagnostic Action" for item in response.recommendations)


def test_p208_technology_agent_returns_citations():
    agent = TechAgent()
    agent.kb = FakeKB([_hit(
        "Catalyst 8300 interface evidence supports secure WAN connectivity.",
        "fixture-catalyst-8300.pdf",
        model="Catalyst 8300",
        page=1,
    )])
    response = agent.run("Which Cisco Catalyst 8300 interface supports secure WAN connectivity?")
    assert response.citations
    assert response.citations[0].source_doc == "fixture-catalyst-8300.pdf"


def test_p209_clinical_agent_returns_disclaimer_and_summary():
    agent = ClinicalAgent()
    agent.kb = FakeKB([_hit(
        "A diabetes fixture study evaluates an intervention and reports outcomes.",
        "fixture-diabetes.pdf",
        doc_type="paper",
        page=1,
    )])
    response = agent.run("What does the diabetes clinical study report about its intervention?")
    assert response.citations
    assert "fixture-diabetes.pdf reports:" in response.findings_summary
    assert "Informational only; not medical advice." in response.findings_summary


def test_p210_empty_and_malformed_inputs_are_safe():
    clinical = ClinicalAgent()
    clinical.kb = FakeKB([])
    assert clinical.run("").status == "INFORMATION_REQUEST"
    assert clinical.run(None).status == "INFORMATION_REQUEST"
    assert clinical.retrieve(None) == []
    assert recommend("fixture problem", [{"item_id": "malformed"}]) == []


def test_p209_s540md_is_product_matching_not_troubleshooting():
    agent = ClinicalAgent()
    agent.kb = FakeKB([_hit(
        "Agilent S540MD Slide Scanner System provides fast whole-slide imaging for pathology workflows.",
        "agilent-digital-pathology-scanners.html",
        doc_type="product_page",
        model="S540MD",
    )])
    response = agent.run("Agilent S540MD Slide Scanner System")
    assert response.status == "ANALYSIS_COMPLETE"
    assert "S540MD" in response.findings_summary
    assert response.recommendations[0].item_id == "AGILENT-S540MD-SLIDE-SCANNER"


def test_p209_academic_medical_query_enters_literature_mode():
    agent = ClinicalAgent()
    agent.kb = FakeKB([_hit(
        "Roy et al. proposed a Bilateral-Branch Network (BBN) framework for predicting a dengue fever outbreak.",
        "Fog-Driven_Heart_Attack_Prediction_from_Wearable_Edge_Devices.pdf",
        doc_type="paper",
        page=2,
    )])
    response = agent.run("What is the Bilateral-Branch Network (BBN) framework for prediction of a dengue fever outbreak?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert "BBN" in response.findings_summary
    assert response.citations[0].source_doc.startswith("Fog-Driven_")
    assert "Informational only; not medical advice." in response.findings_summary


def test_p203_maps_downloaded_cisco_datasheet_filenames_to_models():
    assert _model_for("datasheet-c78-744088.pdf") == "Catalyst 8300"
    assert _model_for("data_sheet-c78-732542.pdf") == "ISR 4000"
    assert _model_for("datasheet-c78-731632.pdf") == "ASR 1000"


def test_p208_unsupported_technology_model_abstains_instead_of_using_nearby_evidence():
    agent = TechAgent()
    agent.kb = FakeKB([_hit(
        "Catalyst 8300 interface evidence supports secure WAN connectivity.",
        "fixture-catalyst-8300.pdf",
        model="Catalyst 8300",
        page=1,
    )])
    response = agent.run("What IPsec throughput does the Cisco Catalyst 9999 provide?")
    assert response.status == "INFORMATION_REQUEST"
    assert response.uncertainty_level == "HIGH"
    assert response.citations == []


def test_p208_clinical_literature_query_fails_closed_when_sent_to_technology():
    agent = TechAgent()
    agent.kb = FakeKB([_hit(
        "Cisco datasheet mentions detection and network methods.",
        "unrelated-cisco.pdf",
        model="Catalyst 8300",
    )])
    response = agent.run("What wearable or IoT-based methods are described for heart-attack detection?")
    assert response.status == "INFORMATION_REQUEST"
    assert response.uncertainty_level == "HIGH"
    assert response.citations == []


def test_p209_wrong_instrument_model_abstains_instead_of_using_nearby_evidence():
    agent = ClinicalAgent()
    agent.kb = FakeKB([_hit(
        "Agilent S540MD Slide Scanner System provides whole-slide imaging.",
        "agilent-digital-pathology-scanners.html",
        doc_type="product_page",
        model="S540MD",
    )])
    response = agent.run("What are the specifications of the Agilent S999MD Slide Scanner System?")
    assert response.status == "INFORMATION_REQUEST"
    assert response.uncertainty_level == "HIGH"
    assert response.citations == []
