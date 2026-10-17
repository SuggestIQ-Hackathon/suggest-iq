"""Root pytest config: --member selection, offline defaults, STRICT mode."""
import os

import pytest

# Contract/integration tests are always offline and deterministic.
os.environ["LLM_MODE"] = "mock"
os.environ["EMBEDDING_MODE"] = "hash"


def pytest_addoption(parser):
    parser.addoption("--member", action="store", default=None, help="run only tests for p1|p2|p3|p4 (plus shared harness tests)")


def pytest_configure(config):
    config.addinivalue_line("markers", "member(name): owner of the test")


def pytest_collection_modifyitems(config, items):
    member = config.getoption("--member")
    if not member:
        return
    keep, drop = [], []
    for item in items:
        owners = [m.args[0] for m in item.iter_markers("member")]
        (keep if (not owners or member in owners) else drop).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep

