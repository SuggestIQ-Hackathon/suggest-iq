"""Harness self-test (no member marker: runs for everyone). Proves the checks are valid against the mocks."""
import pytest

from core.mocks import MockDomainAgent
from core.registry import REAL_DOMAIN_LIST, get_agents
from core.schemas import ConsultingReport, DomainResponse, DomainType, RoutingDecision
from tests.contract.checks import check_agent
from tests.helpers import load_benchmark, load_contract_queries


@pytest.mark.parametrize("domain", REAL_DOMAIN_LIST, ids=lambda d: d.value)
def test_mock_satisfies_contract(domain):
    check_agent(MockDomainAgent(domain), load_contract_queries()[domain.value])


def test_registry_all_mocks():
    agents = get_agents(real=[])
    assert set(agents) == set(REAL_DOMAIN_LIST)
    assert all(isinstance(a, MockDomainAgent) for a in agents.values())


def test_benchmark_fixture_valid():
    bench = load_benchmark()
    assert len(bench) >= 20
    ids = [b["id"] for b in bench]
    assert len(ids) == len(set(ids))
    valid = {d.value for d in REAL_DOMAIN_LIST}
    for b in bench:
        assert set(b["expected_domains"]) <= valid and b["expected_domains"]
        assert b["type"] == ("cross" if len(b["expected_domains"]) > 1 else "single")
        assert b["query"].strip() and b["expected_sources"] and b["expected_keywords"]


def test_schema_roundtrip():
    resp = MockDomainAgent(DomainType.SEC).run("x")
    assert DomainResponse.model_validate_json(resp.model_dump_json()) == resp
    rd = RoutingDecision(query="q", domains=[DomainType.SEC], is_cross_domain=False)
    assert rd.confidence == 0.0
    assert ConsultingReport.model_fields  # importable and defined
