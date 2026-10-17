"""Shared test helpers. Owner: P1."""
import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "core" / "fixtures"


def not_implemented(what: str):
    """Skip (default) or FAIL (STRICT=1) when a member's real module does not exist yet."""
    if os.getenv("STRICT") == "1":
        pytest.fail(f"NOT IMPLEMENTED: {what}", pytrace=False)
    pytest.skip(f"not implemented yet: {what}")


def load_benchmark():
    return json.loads((FIXTURES / "benchmark_queries.json").read_text())


def load_contract_queries():
    return json.loads((FIXTURES / "contract_queries.json").read_text())
