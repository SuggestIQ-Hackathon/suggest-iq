"""Registry: maps domains to agents and decides real vs mock. Owner: P1. LOCKED import paths below.

REAL_DOMAINS env var (used by main.py, UI and integration tests):
  auto (default) -> use the real agent when its module exists, otherwise the mock
  none           -> all mocks
  all            -> all real; error if one is missing
  technology,sec -> comma list of domains that must be real; the rest are mocks
"""
import importlib
import os
from typing import Any, Dict, Iterable, Optional

from core.interfaces import BaseDomainAgent
from core.mocks import MockDomainAgent
from core.schemas import DomainType

REAL_AGENT_PATHS: Dict[DomainType, str] = {
    DomainType.TECHNOLOGY: "p2_tech_clinical.agents.tech_agent:TechAgent",
    DomainType.CLINICAL: "p2_tech_clinical.agents.clinical_agent:ClinicalAgent",
    DomainType.SEC: "p3_sec_csr.agents.sec_agent:SECAgent",
    DomainType.CSR: "p3_sec_csr.agents.csr_agent:CSRAgent",
}
MANAGER_PATH = "p1_orchestrator.agents.manager:ManagerAgent"
REAL_DOMAIN_LIST = list(REAL_AGENT_PATHS)


def load_symbol(path: str) -> Optional[Any]:
    """Import 'pkg.module:Name'. Returns None when that module/attribute does not exist yet.
    Errors INSIDE an existing module (syntax errors, missing third-party deps) are raised, not hidden."""
    mod, _, attr = path.partition(":")
    try:
        module = importlib.import_module(mod)
    except ModuleNotFoundError as err:
        if err.name and (mod == err.name or mod.startswith(err.name + ".")):
            return None
        raise
    return getattr(module, attr, None)


def load_real(domain: DomainType) -> Optional[BaseDomainAgent]:
    cls = load_symbol(REAL_AGENT_PATHS[domain])
    return cls() if cls else None


def _requested(real: Optional[Iterable[DomainType]]) -> Dict[DomainType, bool]:
    """Returns {domain: must_be_real}. Domains missing from the dict are 'auto'."""
    if real is not None:
        wanted = set(real)
        return {d: (d in wanted) for d in REAL_DOMAIN_LIST}
    raw = os.getenv("REAL_DOMAINS", "auto").strip().lower()
    if raw == "none":
        return {d: False for d in REAL_DOMAIN_LIST}
    if raw == "all":
        return {d: True for d in REAL_DOMAIN_LIST}
    if raw == "auto":
        return {}
    names = {n.strip() for n in raw.split(",") if n.strip()}
    return {d: (d.value in names) for d in REAL_DOMAIN_LIST}


def get_agents(real: Optional[Iterable[DomainType]] = None) -> Dict[DomainType, BaseDomainAgent]:
    """Return one agent per real domain. `real=[]` forces all mocks; `real=None` follows REAL_DOMAINS."""
    req = _requested(real)
    agents: Dict[DomainType, BaseDomainAgent] = {}
    for d in REAL_DOMAIN_LIST:
        if req.get(d, None) is False:
            agents[d] = MockDomainAgent(d)
            continue
        agent = load_real(d)
        if agent is None:
            if req.get(d) is True:
                raise ImportError(f"Real agent for {d.value} requested but {REAL_AGENT_PATHS[d]} does not exist yet")
            agent = MockDomainAgent(d)
        agents[d] = agent
    return agents


def load_manager(agents: Optional[Dict[DomainType, BaseDomainAgent]] = None):
    """Return a ManagerAgent wired to `agents` (default: get_agents()), or None if P1 has not built it yet."""
    cls = load_symbol(MANAGER_PATH)
    return cls(agents=agents if agents is not None else get_agents()) if cls else None
