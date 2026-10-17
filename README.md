# Agentic AI Management Consulting Platform (CMPE 256 Hackathon)

A manager agent routes customer questions to Technology, Clinical, SEC and Corporate-Responsibility agents, grounds answers in source documents with citations, ranks recommendations, and produces an executive consulting report with next steps and KPIs.

**Start here:** `COMMON.md` (rules, contracts, ownership, tests). Then your member folder's `TODO.md`.

| Member | Folder | Role |
|---|---|---|
| P1 | `p1_orchestrator/` | Manager, router, dispatcher, synthesizer, `core/` |
| P2 | `p2_tech_clinical/` | Technology + Clinical RAG, hardware recommender |
| P3 | `p3_sec_csr/` | SEC + CSR RAG, strategy recommender |
| P4 | `p4_eval_ui/` | Evaluation, explainability, dashboard, slides |

```bash
make setup            # venv + deps (needs uv)
cp .env.example .env  # optional; tests run offline regardless
make test-harness     # must be green after cloning
make test-pN          # your slice (N = 1..4)
STRICT=1 make test-pN && make test-integration MEMBER=pN   # handoff gate
```

Using an AI coding agent? Point it at `AGENTS.md` (Codex/Antigravity/Claude read it automatically; Cursor uses `.cursor/rules/common.mdc`).
`resources/` is read-only input data. `Clinical.zip` (52 MB) and `FoodSecurity.zip` (17 MB) are git-ignored because they are heavy: get them from the team drive and place them in `resources/`. All other resource files are tracked.
