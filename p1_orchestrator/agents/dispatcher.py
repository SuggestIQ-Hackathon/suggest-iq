"""Async parallel dispatcher for domain agents. Owner: P1.

Dispatches sub-queries to domain agents concurrently using asyncio.gather,
with per-agent timeouts and isolated error handling.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

from core.interfaces import BaseDomainAgent, Context
from core.mocks import MockDomainAgent
from core.schemas import DomainResponse, DomainType, RoutingDecision


async def _run_single(
    domain: DomainType,
    agent: Optional[BaseDomainAgent],
    sub_query: str,
    context: Context,
    timeout_s: float,
) -> Tuple[DomainResponse, Dict[str, Any]]:
    start_t = time.perf_counter()
    if agent is None:
        agent = MockDomainAgent(domain)

    is_mock = "mock" in type(agent).__name__.lower()
    try:
        resp = await asyncio.wait_for(agent.arun(sub_query, context), timeout=timeout_s)
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        meta = {
            "status": resp.status,
            "uncertainty": resp.uncertainty_level,
            "latency_ms": latency_ms,
            "real_or_mock": "mock" if is_mock else "real",
            "error": None,
        }
        return resp, meta
    except Exception as err:
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        err_msg = str(err) or type(err).__name__
        fallback_resp = DomainResponse(
            domain=domain,
            status="INFORMATION_REQUEST",
            uncertainty_level="HIGH",
            findings_summary=f"Agent {domain.value} failed: {err_msg}",
            missing_diagnostics_needed=[f"{domain.value} unavailable: {err_msg}"],
            recommendations=[],
            citations=[],
        )
        meta = {
            "status": "INFORMATION_REQUEST",
            "uncertainty": "HIGH",
            "latency_ms": latency_ms,
            "real_or_mock": "mock" if is_mock else "real",
            "error": err_msg,
        }
        return fallback_resp, meta


async def dispatch(
    agents: Dict[DomainType, BaseDomainAgent],
    routing: RoutingDecision,
    context: Context = None,
    timeout_s: float = 60.0,
) -> Tuple[Dict[str, DomainResponse], Dict[str, Any]]:
    """Dispatch sub-queries to domain agents in parallel.
    Returns (domain_findings, agent_traces).
    Keys in domain_findings are DomainType.value.
    """
    tasks = []
    for domain in routing.domains:
        agent = agents.get(domain)
        sub_query = routing.sub_queries.get(domain.value, routing.query)
        tasks.append(_run_single(domain, agent, sub_query, context, timeout_s))

    results = await asyncio.gather(*tasks)

    domain_findings: Dict[str, DomainResponse] = {}
    agent_traces: Dict[str, Any] = {}

    for domain, (resp, meta) in zip(routing.domains, results):
        domain_findings[domain.value] = resp
        agent_traces[domain.value] = meta

    return domain_findings, agent_traces
