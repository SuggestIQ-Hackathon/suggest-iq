VENV := .venv
PY := $(VENV)/bin/python
PYTEST := $(PY) -m pytest -q

.PHONY: questions setup test-harness test-p1 test-p2 test-p3 test-p4 test-integration test-all eval
setup:
	uv venv $(VENV)
	uv pip install --python $(PY) -r requirements.txt $(foreach f,$(wildcard p*/requirements.txt),-r $(f))

# Shared harness self-test: proves mocks, schemas, fixtures and the checks themselves are valid.
test-harness:
	$(PYTEST) tests/contract -m "not member"  || test $$? -eq 5

# Contract tests + the member's own unit tests. Skips unimplemented parts; add STRICT=1 to make skips fail (handoff gate).
test-p1: ; $(PYTEST) tests/contract --member p1 p1_orchestrator/tests
test-p2: ; $(PYTEST) tests/contract --member p2 p2_tech_clinical/tests
test-p3: ; $(PYTEST) tests/contract --member p3 p3_sec_csr/tests
test-p4: ; $(PYTEST) tests/contract --member p4 p4_eval_ui/tests

# Real module for MEMBER (p1..p4) + mocks for everyone else, run through the Manager over the benchmark.
test-integration: ; $(PYTEST) tests/integration --member $(MEMBER)

# Everything, all real modules (use before the integration merge).
test-all: ; REAL_DOMAINS=all STRICT=1 $(PYTEST) tests p1_orchestrator/tests p2_tech_clinical/tests p3_sec_csr/tests p4_eval_ui/tests

eval: ; LLM_MODE=$${LLM_MODE:-mock} $(PY) -m p4_eval_ui.evaluation.benchmark

# Agent mailbox. `make questions MEMBER=p2` = open questions TO p2. Add FROM=1 for questions SENT BY p2.
questions: ; $(PY) scripts/questions.py $(if $(MEMBER),--member $(MEMBER)) $(if $(FROM),--sent)
