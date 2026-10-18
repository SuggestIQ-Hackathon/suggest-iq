"""Central Management Consulting Manager Agent. Owner: P1.

Orchestrates intent classification, parallel dispatch, and cross-domain synthesis.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core import llm
from core.interfaces import BaseDomainAgent, Context, Manager
from core.registry import get_agents
from core.schemas import ConsultingReport, DomainType, RoutingDecision
from p1_orchestrator.agents import dispatcher, router, synthesizer


class ManagerAgent(Manager):
    """Hierarchical Management Consulting Supervisor Agent."""

    def __init__(self, agents: Optional[Dict[DomainType, BaseDomainAgent]] = None):
        self.agents = agents if agents is not None else get_agents()

    def classify(self, query: str) -> RoutingDecision:
        """Classify incoming query into domains with sub-query decomposition."""
        return router.classify(query)

    def handle(self, query: str, context: Context = None) -> ConsultingReport:
        """Synchronous consulting pipeline execution."""
        return asyncio.run(self.ahandle(query, context))

    async def ahandle(self, query: str, context: Context = None) -> ConsultingReport:
        """Asynchronous consulting pipeline execution."""
        start_t = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        # Step 1: Intent Routing & Decomposition
        routing = self.classify(query)

        # Step 2: Parallel Async Dispatch
        domain_findings, agent_traces = await dispatcher.dispatch(
            agents=self.agents,
            routing=routing,
            context=context,
        )

        total_ms = round((time.perf_counter() - start_t) * 1000, 2)

        # Step 3: Construct Audit Trace
        audit = {
            "routing": routing.model_dump(),
            "agents": agent_traces,
            "mode": llm.llm_mode(),
            "started_at": started_at,
            "total_ms": total_ms,
            "fallbacks_used": [routing.rationale] if "fallback" in routing.rationale.lower() else [],
        }

        # Step 4: Executive Synthesis
        report = synthesizer.synthesize(
            query=query,
            routing=routing,
            responses=domain_findings,
            audit=audit,
        )
        return report
