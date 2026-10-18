from p3_sec_csr.agents.risk_extractor import CATEGORY_QUERIES, extract_risks
from p3_sec_csr.agents.csr_agent import CSRAgent
from p3_sec_csr.agents.sec_agent import SECAgent
from p3_sec_csr.knowledge.csr_kb import CSRKB
from p3_sec_csr.knowledge.sec_kb import SECKB


def test_real_sec_risk_categories_have_item_1a_evidence():
    kb = SECKB()
    for company in ("Cisco", "Agilent"):
        for category in CATEGORY_QUERIES:
            findings = extract_risks(company, category, kb)
            assert findings, (company, category)
            assert findings[0].citation.section == "Item 1A. Risk Factors"


def test_professor_prompts_retrieve_expected_sofi_year():
    kb = CSRKB()
    prompts = [
        ("List major food insecurity reasons in 2023", 2023),
        ("List major food insecurity reasons in 2024", 2024),
    ]
    for query, year in prompts:
        hits = kb.search(query, k=5, report_year=year)
        assert len(hits) == 5
        assert {hit.chunk.metadata["report_year"] for hit in hits} == {year}


def test_remaining_professor_prompts_return_evidence():
    kb = CSRKB()
    for query in (
        "Explain malnutrition in war zones",
        "Explain increase prices impact on food security",
    ):
        assert kb.search(query, k=5)


def test_real_agents_answer_the_two_primary_hackathon_questions():
    sec_response = SECAgent().run(
        "What are the financial, competitive, and operational risks associated "
        "with Cisco and Agilent in their 2025 annual reports?"
    )
    assert sec_response.status == "ANALYSIS_COMPLETE"
    assert sec_response.recommendations
    assert {citation.source_doc for citation in sec_response.citations} == {
        "Cisco_10-K_FY2025.pdf",
        "Agilent_10-K_FY2025.pdf",
    }

    csr_response = CSRAgent().run(
        "Which technology investments could improve food security and sustainability outcomes?"
    )
    assert csr_response.status == "ANALYSIS_COMPLETE"
    assert len(csr_response.recommendations) == 3
    assert csr_response.citations
    assert all(citation.source_doc.startswith("SOFI-") for citation in csr_response.citations)


def test_real_sec_agent_searches_supported_filing_topic_without_company_name():
    response = SECAgent().run("What is Delaware law?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "LOW"
    assert response.citations
    assert all(citation.source_doc.startswith("Alphabet_10-K_") for citation in response.citations)
    assert "15%" in response.findings_summary


def test_real_sec_agent_answers_generic_cybersecurity_filing_question():
    response = SECAgent().run("What do the filings say about cybersecurity?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "LOW"
    assert response.citations
    assert "cybersecurity" in response.findings_summary.lower()


def test_real_sec_agent_answers_generic_share_repurchase_question():
    response = SECAgent().run("Board of Directors authorized how much shares?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "LOW"
    assert any(
        citation.source_doc == "Alphabet_10-K_FY2025.pdf"
        for citation in response.citations
    )
    assert all(
        citation.source_doc == "Alphabet_10-K_FY2025.pdf"
        for citation in response.citations
    )
    assert "$70.0 billion" in response.findings_summary
    assert "additional $70.0 billion" in response.findings_summary


def test_real_sec_agent_answers_filing_section_heading_without_company_name():
    response = SECAgent().run("Expanded AI Offerings in the Products and Services")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "LOW"
    assert response.citations
    assert all(
        citation.source_doc == "Alphabet_10-K_FY2025.pdf"
        for citation in response.citations
    )
    assert response.findings_summary.startswith("According to Alphabet FY2025's filing:")
    assert "ai" in response.findings_summary.lower()
    assert "AI Overviews" in response.findings_summary
    assert "Google Cloud Platform" in response.findings_summary


def test_real_sec_agent_answers_natural_language_question_for_supported_company():
    response = SECAgent().run(
        "How is Alphabet expanding its AI products and services?"
    )
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "LOW"
    assert response.citations
    assert all(
        citation.source_doc == "Alphabet_10-K_FY2025.pdf"
        for citation in response.citations
    )
    assert "AI Overviews" in response.findings_summary


def test_real_csr_agent_rejects_unrelated_question():
    response = CSRAgent().run("What is the capital of France?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert not response.citations


def test_real_csr_agent_corrects_food_security_typo_to_substantive_evidence():
    response = CSRAgent().run("Tell me about foood security")
    assert response.uncertainty_level == "LOW"
    assert response.citations
    assert any(
        concept in response.findings_summary.lower()
        for concept in ("availability", "malnutrition", "food security")
    )


def test_real_csr_agent_answers_supported_heading_without_scope_keywords():
    response = CSRAgent().run("What Regional progress")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "LOW"
    assert response.citations
    assert all(citation.source_doc == "SOFI-2023.pdf" for citation in response.citations)
    assert "progress" in response.findings_summary.lower()


def test_real_csr_agent_rejects_unrelated_pokemon_question():
    response = CSRAgent().run("What is Pokemon?")
    assert response.status == "ANALYSIS_COMPLETE"
    assert response.uncertainty_level == "HIGH"
    assert not response.citations
