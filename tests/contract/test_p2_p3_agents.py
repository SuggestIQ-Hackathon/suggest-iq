"""P2 (technology, clinical) and P3 (sec, corporate_responsibility) agent contract."""
import pytest

from core.registry import load_real
from core.schemas import DomainType
from tests.contract.checks import check_agent
from tests.helpers import load_contract_queries, not_implemented

CASES = [
    pytest.param(DomainType.TECHNOLOGY, marks=pytest.mark.member("p2")),
    pytest.param(DomainType.CLINICAL, marks=pytest.mark.member("p2")),
    pytest.param(DomainType.SEC, marks=pytest.mark.member("p3")),
    pytest.param(DomainType.CSR, marks=pytest.mark.member("p3")),
]


@pytest.mark.parametrize("domain", CASES, ids=lambda d: d.value)
def test_real_agent_contract(domain):
    agent = load_real(domain)
    if agent is None:
        not_implemented(f"real agent for {domain.value}")
    assert agent.domain == domain
    check_agent(agent, load_contract_queries()[domain.value])
