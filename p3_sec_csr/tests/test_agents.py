from typing import ClassVar
from types import SimpleNamespace

from core.rag_base import Chunk, Hit
from p3_sec_csr.agents import risk_extractor
from p3_sec_csr.agents.csr_agent import CSRAgent
from p3_sec_csr.agents.risk_extractor import extract_risks
from p3_sec_csr.agents.sec_agent import SECAgent


class StubSECKB:
    manifest: ClassVar[list[dict]] = [
        {"company": "Cisco", "fiscal_year": 2026},
        {"company": "Cisco", "fiscal_year": 2025},
        {"company": "Agilent", "fiscal_year": 2025},
        {"company": "Alphabet", "fiscal_year": 2025},
    ]

    def search(self, query, k=5, company=None, item=None, fiscal_year=None):
        generic_query = company is None
        company = company or "Alphabet"
        text = (
            "As a Delaware corporation, Alphabet is subject to Delaware anti-takeover "
            "provisions governing business combinations with holders of 15% or more of "
            "its voting stock."
            if generic_query
            else (
                f"{company} disclosed supply chain, competitive, regulatory, operational, and financial risks. "
                "Component availability and supplier concentration may disrupt operations."
            )
        )
        chunk = Chunk(
            id=f"{company}-risk",
            text=text,
            metadata={
                "source_doc": f"{company}_10-K_FY{fiscal_year or 2025}.pdf",
                "page": 10,
                "section": item or "Item 1A. Risk Factors",
                "item": item or "Item 1A. Risk Factors",
                "company": company,
                "fiscal_year": fiscal_year or 2025,
            },
        )
        return [Hit(chunk=chunk, score=0.8)][:k]


class StubCSRKB:
    def search(self, query, k=5, report_year=None):
        year = report_year or 2024
        chunk = Chunk(
            id=f"sofi-{year}",
            text="Conflict, climate extremes, economic downturns, and unaffordable healthy diets drive food insecurity and malnutrition.",
            metadata={
                "source_doc": f"SOFI-{year}.pdf",
                "page": 20,
                "section": "EXECUTIVE SUMMARY",
                "report_year": year,
            },
        )
        return [Hit(chunk=chunk, score=0.9)][:k]


def test_risk_extractor_returns_verbatim_citation():
    findings = extract_risks("Cisco", "supply_chain", StubSECKB(), fiscal_year=2026)
    assert findings
    assert findings[0].company == "Cisco"
    assert findings[0].citation.snippet.startswith("Cisco disclosed")
    assert findings[0].citation.section == "Item 1A. Risk Factors"


def test_live_risk_extraction_frames_filing_text_as_untrusted(monkeypatch):
    captured = {}

    def fake_complete_json(prompt, _schema):
        captured["prompt"] = prompt
        return SimpleNamespace(statement="Grounded risk statement.")

    monkeypatch.setattr(risk_extractor.llm, "is_mock", lambda: False)
    monkeypatch.setattr(risk_extractor.llm, "complete_json", fake_complete_json)
    findings = risk_extractor.extract_risks(
        "Cisco", "supply_chain", StubSECKB(), fiscal_year=2026
    )
    assert findings[0].statement == "Grounded risk statement."
    assert "untrusted evidence" in captured["prompt"]
    assert "<filing_excerpt>" in captured["prompt"]


def test_sec_agent_handles_latest_and_comparison():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run(
        "Compare Cisco and Agilent supply-chain risks from their SEC filings."
    )
    assert response.status == "ANALYSIS_COMPLETE"
    assert {citation.source_doc for citation in response.citations} == {
        "Cisco_10-K_FY2026.pdf",
        "Agilent_10-K_FY2025.pdf",
    }
    assert response.recommendations


def test_sec_agent_honors_an_explicit_fiscal_year():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run(
        "Compare Cisco and Agilent financial, competitive, and operational risks in their 2025 annual reports."
    )
    assert response.status == "ANALYSIS_COMPLETE"
    assert {citation.source_doc for citation in response.citations} == {
        "Cisco_10-K_FY2025.pdf",
        "Agilent_10-K_FY2025.pdf",
    }
    assert "Cisco FY2025" in response.findings_summary
    assert "Agilent FY2025" in response.findings_summary


def test_sec_agent_reports_an_unavailable_explicit_fiscal_year():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run("What Cisco risks were disclosed in the 2024 annual report?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert "does not contain an FY2024 filing" in response.findings_summary


def test_sec_agent_labels_out_of_corpus_entity_high_uncertainty():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run("What risks does Microsoft disclose in its annual report?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert "outside the local SEC corpus" in response.findings_summary
    assert response.citations
    assert all(citation.snippet.startswith('"company":') for citation in response.citations)


def test_sec_agent_searches_all_filings_for_supported_topic_without_company():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run("What is Delaware law?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level != "HIGH"
    assert response.citations[0].source_doc == "Alphabet_10-K_FY2025.pdf"
    assert "not general legal advice" in response.findings_summary
    assert not response.recommendations


def test_sec_agent_corrects_supported_topic_typo_before_retrieval():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run("Tell me about Delware law")
    assert response.uncertainty_level != "HIGH"
    assert response.citations[0].source_doc == "Alphabet_10-K_FY2025.pdf"


def test_sec_agent_abstains_from_current_market_data_requests():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run("What is Cisco stock price today?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert "does not support current market-data" in response.findings_summary
    assert not response.recommendations


def test_sec_agent_abstains_when_requested_metric_is_not_in_evidence():
    agent = SECAgent()
    agent.kb = StubSECKB()
    response = agent.run("What was Cisco gross margin in its latest annual filing?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert "did not contain a directly supporting sentence" in response.findings_summary
    assert not response.recommendations


def test_csr_agent_filters_year_and_adds_investment_recommendations():
    agent = CSRAgent()
    agent.kb = StubCSRKB()
    response = agent.run(
        "Which technology investments could improve food security in 2023?"
    )
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.citations[0].source_doc == "SOFI-2023.pdf"
    assert len(response.recommendations) == 3
    assert all(
        "Evidence source:" in (recommendation.compatibility_notes or "")
        for recommendation in response.recommendations
    )
    assert {recommendation.item_id for recommendation in response.recommendations}.isdisjoint(
        {"STRAT-SCENARIO-PLANNING", "STRAT-PARTNER-DUE-DILIGENCE"}
    )
    assert "[SOFI-2023.pdf" in response.findings_summary


def test_csr_agent_labels_unsupported_year_high_uncertainty():
    agent = CSRAgent()
    agent.kb = StubCSRKB()
    response = agent.run("What changed in food security in 2025?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert "does not contain a 2025 report" in response.findings_summary


def test_csr_agent_corrects_supported_topic_typo_before_retrieval():
    agent = CSRAgent()
    agent.kb = StubCSRKB()
    response = agent.run("Tell me about foood security")
    assert response.uncertainty_level != "HIGH"
    assert response.citations[0].source_doc == "SOFI-2024.pdf"
    assert "food insecurity" in response.findings_summary.lower()


def test_csr_agent_rejects_unrelated_questions():
    agent = CSRAgent()
    agent.kb = StubCSRKB()
    response = agent.run("What is the capital of France?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert not response.citations
    assert not response.recommendations


def test_csr_agent_does_not_invent_company_emissions_metrics():
    agent = CSRAgent()
    agent.kb = StubCSRKB()
    response = agent.run("What are Cisco Scope 1 and Scope 2 emissions?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert "did not retrieve a directly supporting" in response.findings_summary
    assert not response.recommendations
