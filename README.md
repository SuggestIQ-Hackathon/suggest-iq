# Agentic AI Management Consulting Platform (CMPE 256 Hackathon)

**Suggest IQ** was built by our team as part of the **CMPE 256 (Recommender Systems) hackathon** at San José State University.

**Live link: https://suggest-iq.fly.dev/**

## Team

- Manali Vijay Mankad
- Vedanti Vilas Kanade
- Ayushi Vishwas Surange
- Jagath Jijo

## About

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

Agents talk to each other through `questions/` (one file per question, addressed to a member's agent; see `questions/README.md`). Check yours with `make questions MEMBER=pN`.

Using an AI coding agent? Point it at `AGENTS.md` (Codex/Antigravity/Claude read it automatically; Cursor uses `.cursor/rules/common.mdc`).
`resources/` is read-only input data. `Clinical.zip` (52 MB) and `FoodSecurity.zip` (17 MB) are git-ignored because they are heavy: get them from the team drive and place them in `resources/`. All other resource files are tracked.


## Hosting (Docker)

The whole app (consulting agents, retail checkout, dashboard) runs from one container. All search indexes are **built inside the image** from `resources/`
(offline, about a minute), so nothing is downloaded when the container starts.

```bash
make data-check                      # optional: verify data/ is complete locally (python scripts/prepare_data.py --check)
make docker-build                    # docker build -t suggest-iq .
make docker-run                      # http://localhost:8501  (mock LLM unless .env sets LLM_MODE=live)
```

| Environment variable | Default in the image | Notes |
|---|---|---|
| `LLM_MODE` | `mock` | `live` makes real model calls (needs a provider key). Without a key the app still runs with built-in rules. |
| `LLM_MODEL` | provider default | e.g. `gemini/gemini-3.1-flash-lite` |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | none | set as a **host secret**, never in the image or git |
| `REAL_DOMAINS` | `all` | use the four real agents |
| `PORT` | `8501` | hosts such as Render and Cloud Run set this for you |
| `RETAIL_ORDERS_LOG` | `/app/data/retail/orders_log.jsonl` | mount a volume at `/app/data/retail` to keep demo orders across restarts |

Notes for hosting platforms
- The app is a long-running Streamlit server with WebSockets and per-user session state in memory: run **one instance** (or enable session affinity).
- Memory: about 350 MB in use with every agent and the retail model loaded, so a 1 GB instance is enough.
- Health check: `/_stcore/health`.
- Updating data: replace files in `resources/`, run `make docker-build`, redeploy. The retail order log is the only data written at run time.
- A free Gemini key allows about 20 requests per model per day. For a public demo use a billed key, or leave `LLM_MODE=mock`.

### Deploy to Fly.io
One-time setup (needs a Fly account with a card on file, and Docker running):
```bash
brew install flyctl && fly auth login
fly apps create suggest-iq                  # pick another name if taken, and change `app` in fly.toml
fly volumes create orders --size 1 --region sjc   # keeps retail orders across deploys
fly secrets set GEMINI_API_KEY=...          # only if you switch LLM_MODE to live
make deploy                                 # builds locally with Docker, pushes, one always-on machine
```
The app is then at `https://<app>.fly.dev`. To go live with a real model: `fly secrets set LLM_MODE=live LLM_MODEL=gemini/gemini-3.1-flash-lite GEMINI_API_KEY=...`.
`scripts/docker-entrypoint.sh` fixes the volume ownership at start, then runs the app as a non-root user.
