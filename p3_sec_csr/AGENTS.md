# Agent instructions for P3 — Enterprise Strategy & Governance Lead (SEC + CSR)

You are a coding agent working for **P3** only. Your folder: `p3_sec_csr/`. 

## Read in this order, before writing any code
1. `../COMMON.md` (shared rules, locked contracts, ownership, test commands).
2. `./TODO.md` (your exact task list; this is your complete scope).
3. Other members' `TODO.md` files **only** to find the interfaces they provide or to check whether something is theirs.

## Rules
- Build **only** the items in `./TODO.md`, in order. Tick each box when its acceptance test passes.
- Create/edit files **only** under `p3_sec_csr/` (plus anything your TODO says you own). Everything else is read-only: `core/`, `tests/`, `resources/`, other members' folders.
- If something appears in another member's TODO, do **not** build it. Use `core.mocks.MockDomainAgent` or the interface in `COMMON.md` section 3.
- If something is needed but in nobody's TODO, do not invent it: append a line to `../QUESTIONS.md` and move to the next task.
- Do not import other members' packages. Use `core.*` and `core.registry` only.
- Use `core/llm.py` and `core/rag_base.py`; never call a provider SDK or build your own vector store.
- Every LLM step needs a rule-based fallback for `LLM_MODE=mock`. Tests run offline.
- No uncited claims; no invented numbers; label estimates (see `COMMON.md` section 3, hard rules).
- No extra features, refactors of shared code, or "nice to haves".

## Verify your work (from the repo root)
- Day to day: `make test-p3`
- Handoff gate: `STRICT=1 make test-p3` and `make test-integration MEMBER=p3` must both be green.
