from __future__ import annotations

from pathlib import Path

from core.rag_base import Chunk, Hit

from p2_tech_clinical.agents.clinical_agent import ClinicalAgent


class FakeClinicalKB:
    def __init__(self, hits=None):
        self.hits = hits if hits is not None else [
            Hit(
                chunk=Chunk(
                    id="agilent#1",
                    text="NanoZoomer slide scanner evidence for whole-slide digital pathology imaging.",
                    metadata={
                        "source_doc": "agilent-nanozoomer-slide-scanner.html",
                        "vendor": "Agilent",
                        "model": "NanoZoomer",
                        "doc_type": "product_page",
                    },
                ),
                score=0.9,
            )
        ]

    def search(self, query, k=5, source_type=None):
        selected = [
            hit for hit in self.hits
            if source_type is None or hit.chunk.metadata.get("doc_type") == source_type
        ]
        return selected[:k]


def test_agilent_instrument_matching_returns_catalog_candidate_and_citation():
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB()
    response = agent.run("Which Agilent NanoZoomer instrument supports digital pathology imaging?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.citations[0].source_doc == "agilent-nanozoomer-slide-scanner.html"
    assert response.recommendations
    assert response.recommendations[0].item_id.startswith("AGILENT-NANOZOOMER")
    assert response.recommendations[0].compatibility_notes
    assert response.uncertainty_level == "MEDIUM"


def test_agilent_instrument_matching_is_low_only_with_two_readable_citations():
    first = FakeClinicalKB().hits[0]
    second = Hit(
        chunk=Chunk(
            id="agilent#2",
            text="NanoZoomer evidence also describes digital pathology slide scanning workflows.",
            metadata={
                "source_doc": "agilent-digital-pathology-scanners.html",
                "vendor": "Agilent",
                "model": "NanoZoomer",
                "doc_type": "product_page",
            },
        ),
        score=0.8,
    )
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB([first, second])
    response = agent.run("Which Agilent NanoZoomer instrument supports digital pathology imaging?")
    assert response.uncertainty_level == "LOW"


def test_agilent_markup_only_evidence_returns_high_uncertainty():
    markup_hit = Hit(
        chunk=Chunk(
            id="markup#1",
            text='<script nonce="x">tracking()</script>',
            metadata={
                "source_doc": "agilent-page.html",
                "vendor": "Agilent",
                "model": "NanoZoomer",
                "doc_type": "product_page",
            },
        ),
        score=0.9,
    )
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB([markup_hit])
    response = agent.run("Which Agilent NanoZoomer instrument supports digital pathology imaging?")
    assert response.status == "INFORMATION_REQUEST"
    assert response.uncertainty_level == "HIGH"


def test_clinical_literature_retrieval_returns_citations_and_disclaimer():
    paper_hit = Hit(
        chunk=Chunk(
            id="paper#1",
            text="A diabetes research study evaluates an intervention and reports study outcomes.",
            metadata={"source_doc": "diabetes-paper.pdf", "page": 2, "doc_type": "paper"},
        ),
        score=0.8,
    )
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB([paper_hit])
    response = agent.run("What does the diabetes clinical research report about the intervention?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.citations[0].source_doc == "diabetes-paper.pdf"
    assert "diabetes-paper.pdf reports:" in response.findings_summary
    assert "diabetes research study evaluates an intervention" in response.findings_summary
    assert "Informational only; not medical advice." in response.findings_summary


def test_instrument_troubleshooting_requests_all_missing_diagnostics():
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB()
    response = agent.run("The Agilent NanoZoomer has an imaging issue.")
    assert response.status == "INFORMATION_REQUEST"
    assert response.missing_diagnostics_needed
    assert response.citations


def test_troubleshooting_never_returns_replacement_without_diagnostics():
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB()
    response = agent.run("The Agilent NanoZoomer has an instrument error code.")
    assert all(item.category == "Diagnostic Action" for item in response.recommendations)
    assert all(item.category != "Replacement Part" for item in response.recommendations)
    assert all(item.category != "instrument" for item in response.recommendations)


def test_empty_and_unknown_input_are_safe():
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB()
    empty = agent.run("")
    unknown = agent.run("Tell me something unrelated to the supported corpus.")
    assert empty.status == "INFORMATION_REQUEST"
    assert empty.missing_diagnostics_needed
    assert unknown.status == "INFORMATION_REQUEST"
    assert unknown.uncertainty_level == "HIGH"


def test_missing_data_or_index_is_safe(tmp_path: Path):
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB([])
    response = agent.run("Which Agilent instrument supports whole-slide imaging?")
    assert response.status == "INFORMATION_REQUEST"
    assert response.uncertainty_level == "HIGH"
    assert response.citations == []


def test_no_local_evidence_returns_high_uncertainty():
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB([])
    response = agent.run("What do the COVID clinical trials report?")
    assert response.status == "INFORMATION_REQUEST"
    assert response.uncertainty_level == "HIGH"
    assert "Informational only; not medical advice." in response.findings_summary


def test_retrieve_returns_hits_and_is_safe_for_missing_data():
    agent = ClinicalAgent()
    agent.kb = FakeClinicalKB()
    assert isinstance(agent.retrieve("NanoZoomer imaging", k=1)[0], Hit)
    agent.kb = FakeClinicalKB([])
    assert agent.retrieve("NanoZoomer imaging", k=1) == []
