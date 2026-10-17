# Agent instructions (all tools: Codex, Cursor, Antigravity, Claude)

This repo is built by 4 people, each with their own coding agent. **Your human tells you which member (P1–P4) you are working for. If unclear, ask before writing anything.**

1. Read `COMMON.md` (shared source of truth).
2. Read `<your member folder>/AGENTS.md`, then `<your member folder>/TODO.md`.
3. Build only what your TODO lists. Never edit outside your folder. Never build something in another member's TODO.
4. When confused, follow the conflict protocol in `COMMON.md` section 6 (re-read COMMON.md, read the other members' TODO files, then append to `QUESTIONS.md`).
5. Verify with `make test-pN` from the repo root; finish with `STRICT=1 make test-pN` and `make test-integration MEMBER=pN`.

Members: P1 `p1_orchestrator/` · P2 `p2_tech_clinical/` · P3 `p3_sec_csr/` · P4 `p4_eval_ui/`.
