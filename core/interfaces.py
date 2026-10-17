"""LOCKED interfaces. Owner: P1.

Domain agents (P2, P3) subclass BaseDomainAgent. The Manager (P1) is the only caller.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from core.rag_base import Hit
from core.schemas import ConsultingReport, DomainResponse, DomainType, RoutingDecision

# Keys the Manager (or UI) may pass in `context`. Agents must ignore keys they do not know.
#   "diagnostics":   str   raw logs / telemetry pasted by the customer (Technology, Clinical)
#   "product_model": str   e.g. "Catalyst 8200"
#   "companies":     list  e.g. ["Cisco", "Agilent"]
#   "prior_findings": dict DomainType.value -> DomainResponse (never set in parallel dispatch)
Context = Optional[Dict[str, Any]]


class BaseDomainAgent(ABC):
    domain: DomainType

    @abstractmethod
    def run(self, query: str, context: Context = None) -> DomainResponse:
        """Answer `query` from this domain's knowledge base. Must never raise on bad input."""

    async def arun(self, query: str, context: Context = None) -> DomainResponse:
        return await asyncio.to_thread(self.run, query, context)

    @abstractmethod
    def retrieve(self, query: str, k: int = 5) -> List[Hit]:
        """Evaluation hook (used by P4): return the top-k raw retrieval hits, best first."""


class Manager(Protocol):
    def classify(self, query: str) -> RoutingDecision: ...

    def handle(self, query: str, context: Context = None) -> ConsultingReport: ...

    async def ahandle(self, query: str, context: Context = None) -> ConsultingReport: ...
