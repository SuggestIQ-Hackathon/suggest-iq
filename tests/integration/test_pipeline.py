"""Integration: real module(s) of ONE member + mocks for everyone else, run through the real Manager.

Select the member with `--member pN` (make test-integration MEMBER=pN). Proves pN's slice plugs into the others.
"""
import pytest

from core.registry import get_agents, load_manager, load_real
from core.schemas import ConsultingReport, DomainType
from tests.helpers import load_benchmark, not_implemented

REAL_FOR = {
    "p1": [],
    "p2": [DomainType.TECHNOLOGY, DomainType.CLINICAL],
    "p3": [DomainType.SEC, DomainType.CSR],
    "p4": [],
}


@pytest.mark.parametrize("member", [pytest.param(m, marks=pytest.mark.member(m)) for m in REAL_FOR])
def test_member_slice_in_pipeline(member):
    real = REAL_FOR[member]
    for d in real:
        if load_real(d) is None:
            not_implemented(f"real agent for {d.value}")
    manager = load_manager(get_agents(real=real))
    if manager is None:
        not_implemented("p1 ManagerAgent")
    for item in load_benchmark():
        report = manager.handle(item["query"])
        assert isinstance(report, ConsultingReport), item["id"]
        ConsultingReport.model_validate(report.model_dump())
        assert report.domain_findings, f"{item['id']}: no domain findings"
        for finding in report.domain_findings.values():
            assert finding.findings_summary.strip()
    if member == "p4":
        from p4_eval_ui.evaluation import benchmark

        assert isinstance(benchmark.run_benchmark(manager), dict)
