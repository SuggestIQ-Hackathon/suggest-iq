from pathlib import Path

from core.rag_base import Chunk, VectorIndex
from p3_sec_csr.knowledge.csr_kb import CSRKB, detect_heading
from p3_sec_csr.knowledge.retrieval import hybrid_search
from p3_sec_csr.knowledge.sec_kb import SECKB, detect_section, load_manifest


def test_manifest_identifies_all_five_filings():
    manifest = load_manifest()
    assert len(manifest) == 5
    assert len({entry["file"] for entry in manifest}) == 5
    assert {(entry["company"], entry["fiscal_year"]) for entry in manifest} == {
        ("Agilent", 2025),
        ("Alphabet", 2024),
        ("Alphabet", 2025),
        ("Cisco", 2025),
        ("Cisco", 2026),
    }
    assert all(entry["form"] == "10-K" and entry["pages"] > 0 for entry in manifest)


def test_section_detection_uses_headings_not_cross_references():
    assert (
        detect_section(
            "Item 1A. Risk Factors\nSupply constraints may affect operations."
        )
        == "Item 1A. Risk Factors"
    )
    assert (
        detect_section(
            "This discussion refers to Item 1A. Risk Factors elsewhere in this report.",
            "Item 1. Business",
        )
        == "Item 1. Business"
    )
    assert detect_section(
        "Item 7. Management’s Discussion and Analysis of Financial Condition"
    ) == ("Item 7. Management's Discussion and Analysis")


def test_sec_search_applies_company_and_item_filters(tmp_path: Path):
    index = VectorIndex("test-sec")
    index.add(
        [
            Chunk(
                id="cisco",
                text="Cisco supply chain component availability risk.",
                metadata={
                    "source_doc": "Cisco.pdf",
                    "company": "Cisco",
                    "item": "Item 1A. Risk Factors",
                },
            ),
            Chunk(
                id="agilent",
                text="Agilent supply chain component availability risk.",
                metadata={
                    "source_doc": "Agilent.pdf",
                    "company": "Agilent",
                    "item": "Item 1A. Risk Factors",
                },
            ),
        ]
    )
    kb = SECKB(tmp_path / "unused")
    kb._index = index
    hits = kb.search("supply chain risk", company="Cisco", item="Item 1A. Risk Factors")
    assert hits
    assert {hit.chunk.metadata["company"] for hit in hits} == {"Cisco"}


def test_csr_search_filters_report_year(tmp_path: Path):
    index = VectorIndex("test-csr")
    index.add(
        [
            Chunk(
                id="2023",
                text="Conflict and climate shocks affect food security.",
                metadata={"source_doc": "SOFI-2023.pdf", "report_year": 2023},
            ),
            Chunk(
                id="2024",
                text="Financing food security and nutrition interventions.",
                metadata={"source_doc": "SOFI-2024.pdf", "report_year": 2024},
            ),
        ]
    )
    kb = CSRKB(tmp_path / "unused")
    kb._index = index
    hits = kb.search("food security", report_year=2023)
    assert hits and {hit.chunk.metadata["report_year"] for hit in hits} == {2023}


def test_heading_detection_carries_last_heading():
    assert detect_heading("CHAPTER 3\nFinancing for food security") == "CHAPTER 3"
    assert detect_heading("ordinary body text", "CHAPTER 3") == "CHAPTER 3"


def test_hybrid_search_preserves_exact_identifiers_and_metadata_filters():
    index = VectorIndex("hybrid")
    index.add(
        [
            Chunk(
                id="exact",
                text="The filing identifies supplier component ABC-917 as constrained.",
                metadata={"source_doc": "Cisco.pdf", "company": "Cisco"},
            ),
            Chunk(
                id="semantic",
                text="The company discusses general supplier and component availability risk.",
                metadata={"source_doc": "Agilent.pdf", "company": "Agilent"},
            ),
        ]
    )
    hits = hybrid_search(index, "ABC-917 component", k=2)
    assert hits[0].chunk.id == "exact"
    assert all(0.0 <= hit.score <= 1.0 for hit in hits)
    assert hybrid_search(index, "component", k=2, where={"company": "Agilent"})[
        0
    ].chunk.id == "semantic"
