"""Mock domain agents. Owner: P1. Always valid against the schemas; used by every test and by the UI before real agents exist."""
from typing import List

from core.interfaces import BaseDomainAgent, Context
from core.rag_base import Chunk, Hit
from core.schemas import Citation, DomainResponse, DomainType, RecommendationItem

_DIAG_DOMAINS = {DomainType.TECHNOLOGY, DomainType.CLINICAL}


class MockDomainAgent(BaseDomainAgent):
    def __init__(self, domain: DomainType):
        if domain == DomainType.CROSS_DOMAIN:
            raise ValueError("CROSS_DOMAIN is not a real agent")
        self.domain = domain

    def _citation(self) -> Citation:
        return Citation(source_doc=f"MOCK_{self.domain.value}.pdf", section="Mock Section", page=1,
                        snippet=f"Mock evidence for the {self.domain.value} domain.")

    def _rec(self, category: str) -> RecommendationItem:
        return RecommendationItem(
            item_id=f"MOCK-{self.domain.value}-001", title=f"Mock {self.domain.value} recommendation", category=category,
            confidence_score=0.5, rationale="Mock rationale.", compatibility_notes=None,
            estimated_impact="Mock impact estimate (not a real number).",
        )

    def run(self, query: str, context: Context = None) -> DomainResponse:
        has_diag = bool(context and context.get("diagnostics"))
        if self.domain in _DIAG_DOMAINS and not has_diag:
            return DomainResponse(
                domain=self.domain, status="INFORMATION_REQUEST",
                findings_summary="Hypotheses only (mock); more diagnostics are required before any component is recommended.",
                missing_diagnostics_needed=["show tech-support (or equivalent instrument log)", "error counters", "software/firmware version"],
                recommendations=[self._rec("Diagnostic Action")], citations=[self._citation()], uncertainty_level="HIGH",
            )
        status = "HYPOTHESIS" if self.domain in _DIAG_DOMAINS else "ANALYSIS_COMPLETE"
        return DomainResponse(
            domain=self.domain, status=status, findings_summary=f"Mock findings for: {query[:80]}",
            recommendations=[self._rec("Capital Allocation" if not self.domain in _DIAG_DOMAINS else "Replacement Part")],
            citations=[self._citation()], uncertainty_level="MEDIUM",
        )

    def retrieve(self, query: str, k: int = 5) -> List[Hit]:
        c = self._citation()
        chunk = Chunk(id=f"mock-{self.domain.value}-0", text=c.snippet, metadata={"source_doc": c.source_doc, "page": 1})
        return [Hit(chunk=chunk, score=1.0)][:k]
