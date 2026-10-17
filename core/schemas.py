"""LOCKED shared contracts. Owner: P1. Do not edit without a SCHEMA-CHANGE question in questions/to-p1/.

Every module in the repo talks to every other module only through these types.
"""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DomainType(str, Enum):
    TECHNOLOGY = "technology"
    CLINICAL = "clinical"
    SEC = "sec"
    CSR = "corporate_responsibility"
    CROSS_DOMAIN = "cross_domain"  # only for labelling a query; never a real agent


# The four values a domain agent may return in DomainResponse.status.
Status = Literal["CONFIRMED_FAULT", "HYPOTHESIS", "INFORMATION_REQUEST", "ANALYSIS_COMPLETE"]
Uncertainty = Literal["LOW", "MEDIUM", "HIGH"]


class Citation(BaseModel):
    source_doc: str  # logical document name, e.g. "Cisco_Catalyst_8200_Datasheet.pdf"
    section: Optional[str] = None  # e.g. "Item 1A. Risk Factors"
    page: Optional[int] = None  # 1-based page number when known
    snippet: str  # verbatim text from the source that supports the claim


class RecommendationItem(BaseModel):
    item_id: str
    title: str
    category: str  # e.g. "Replacement Part", "Diagnostic Action", "Capital Allocation"
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    compatibility_notes: Optional[str] = None
    estimated_impact: str  # e.g. "Reduces packet loss by 95%" (state it as an estimate)


class DomainResponse(BaseModel):
    domain: DomainType
    status: Status
    findings_summary: str
    missing_diagnostics_needed: List[str] = Field(default_factory=list)
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    uncertainty_level: Uncertainty


class RoutingDecision(BaseModel):
    """Output of the Manager's intent classifier (P1)."""

    query: str
    domains: List[DomainType]  # real domains only; never CROSS_DOMAIN
    is_cross_domain: bool  # True iff len(domains) >= 2
    sub_queries: Dict[str, str] = Field(default_factory=dict)  # key = DomainType.value
    rationale: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ConsultingReport(BaseModel):
    query: str
    detected_domains: List[DomainType]
    executive_summary: str
    domain_findings: Dict[str, DomainResponse]  # key = DomainType.value
    cross_domain_synthesis: Optional[str] = None
    consolidated_recommendations: List[RecommendationItem]
    next_steps: List[str]
    measuring_impact_kpis: List[str]
    audit_trace: Dict[str, Any]
