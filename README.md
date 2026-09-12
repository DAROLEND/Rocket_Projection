# Rocket Trajectory API

*Також доступно [українською](README.uk.md).*

> 🔗 Live site: **[rocket-projection.onrender.com](https://rocket-projection.onrender.com)** — hosted on Render's free tier, which sleeps after 15 minutes of inactivity, so the first load can take up to a minute.

A backend that simulates rocket flight with air resistance, plus a layer on top that lets you query that data in natural language and drive simulations through an AI agent. It started as a plain physics problem — computing the trajectory of a body launched at an angle — and grew into a small but complete stack: an async API, a database, vector search, a tool-use chat agent, and a custom canvas visualizer with no frontend framework.

## Screenshots

| | |
|---|---|
| ![Simulation comparison + agent](static/images/preview/compare.png) | ![Creation form: engine, parachute, optimal angle](static/images/preview/create-form.png) |
| **Comparison** — multiple trajectories at once, the agent switches to comparison mode on its own and comments on the differences | **New simulation** — engine, parachute, RK4/Euler, optimal-angle search right from the form |
| ![Telemetry + RAG question](static/images/preview/ask.png) | ![Editing an existing simulation](static/images/preview/edit-form.png) |
| **Telemetry and RAG** — drag along the trajectory, plus an "Ask" chat mode with a confidence badge and links to the simulations it drew on | **Editing** — the same form, but recomputes an existing simulation in place (same id) instead of creating a new one |

## What it does

- Computes rocket trajectory with air resistance using two integration methods (Euler and RK4), optionally with an engine (thrust, burn time, fuel consumption) and a parachute that deploys at apogee.
- Finds the launch angle with maximum range. Without air resistance the answer is always 45°; with drag there's no closed-form formula anymore, so the angle is found numerically via golden-section search.
- Computes Monte Carlo landing dispersion: runs the same launch hundreds of times with small noise added to angle and speed, and reports how spread out the landing points are.
- Answers natural-language questions about past simulations (RAG: vector search over ChromaDB → structured answer from Claude).
- Gives an AI agent access to tools — run a simulation, compare several, find the optimal angle — with conversation memory and real-time streaming of the response.
- Displays all of this in a custom canvas visualizer: flight animation, dragging a point along the trajectory with the mouse, comparing multiple launches at once, and a form for creating a new simulation right in the UI.

## Stack

- **Backend:** FastAPI (async), SQLAlchemy 2.0 (async), SQLite locally / Postgres in production
- **AI/ML:** Claude API (Anthropic SDK, streaming + tool use), ChromaDB (embeddings via the built-in ONNX variant of all-MiniLM-L6-v2, no torch), Instructor (structured output on top of Pydantic v2)
- **Frontend:** plain JS + HTML5 Canvas, no frameworks

## Structure

```
app/
├── main.py                # FastAPI app, all endpoints
├── models.py               # SQLAlchemy Simulation model
├── schemas.py               # Pydantic schemas (request/response)
├── database.py               # async engine, sessions
├── config.py                  # pydantic-settings, reads .env
├── simulation_service.py       # wrapper over the physics (physics/)
├── rag_service.py                # embeddings + ChromaDB + /ask (RAG)
└── agent.py                       # tool-use agent: conversation memory + NDJSON streaming

physics/
├── rocket.py               # Rocket class
└── environment.py           # SimulationEnvironment class — integrates motion with air resistance

static/
├── index.html               # UI: canvas visualizer + telemetry + chat
├── style.css
└── script.js                  # animation, drag, simulation comparison, chat

tests/
├── test_physics.py           # physics: apogee without drag, drag, engine, parachute, Euler vs RK4
├── test_optimization.py       # angle search, Monte Carlo dispersion
└── test_api.py                  # endpoints: create/list/get/delete/update, optimal-angle, dispersion
```

## API

- `POST /simulate` — new simulation (with optional engine/parachute/RK4)
- `GET /simulations`, `GET /simulations/{id}` — list and details
- `PUT /simulations/{id}` — recompute with new parameters (same id)
- `DELETE /simulations/{id}` — deletion (from SQL and from ChromaDB)
- `POST /simulate/optimal-angle` — find the angle with maximum range
- `POST /simulate/dispersion` — Monte Carlo landing dispersion (analysis only, not stored in the DB)
- `POST /ask` — natural-language questions about existing simulations (RAG)
- `POST /agent/chat`, `POST /agent/chat/stream` — the same tool-use agent, the second variant streams NDJSON: response tokens plus an event for every tool call

Full interactive documentation is at `/docs`.

## Running locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # and fill in your ANTHROPIC_API_KEY
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/static/index.html (visualizer) or http://127.0.0.1:8000/docs (Swagger).

## Running in Docker

```bash
docker compose up --build
```

Requires a `.env` with `ANTHROPIC_API_KEY` in the project root. Without `DB_*` in `.env`, the container still works fine on local SQLite (`rocket.db` and `chroma_data/` are mounted as volumes so data isn't lost on restart).

## Database: SQLite locally, Postgres in production

Without `DB_HOST` in the settings, the app falls back to a local `rocket.db` file — nothing extra to set up for development. If `DB_HOST` is set (in production it points to a free Postgres from Supabase or Neon), it switches to that via `asyncpg`. The app creates its own schema on startup (no full Alembic setup — a lightweight ad-hoc migration in `app/database.py` that works with both dialects).

ChromaDB (the vector index for `/ask`) still lives on the container's local disk and doesn't survive a redeploy on Render (free plan, no persistent disk) — but that's not a problem: on every startup the app re-reads all simulations from Postgres and rebuilds the index from scratch (`reindex_all` in `rag_service.py`). So the source of truth is always Postgres; Chroma can be lost and rebuilt freely.

## Deployment

Deployed on [Render](https://render.com) as a Docker Web Service, the same approach as my other projects (e.g. [CoffeeTime](https://github.com/DAROLEND/CoffeeTime)) — via `render.yaml` (Blueprint):

1. Set up a free Postgres on [Supabase](https://supabase.com) or [Neon](https://neon.tech) and get the host/port/name/user/password from there.
2. Push the repository to GitHub (done).
3. In Render: **New → Blueprint**, connect this repository — Render reads `render.yaml` on its own and spins up the service.
4. In the service settings, fill in the `ANTHROPIC_API_KEY` and `DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASS` secrets (deliberately not in `render.yaml`, so they don't end up in git).
5. Enable the GitHub App for auto-deploy on push: [github.com/settings/installations](https://github.com/settings/installations) → Render → add this repository.

If `DB_*` isn't set, the service still comes up fine — just on the container's local SQLite file, in which case data really is wiped on every redeploy (Render's free plan has no persistent disk).

## Tests

```bash
uv run pytest
```

27 tests: physics (apogee without drag checked against the analytical formula, effects of drag/engine/parachute, Euler vs RK4 consistency), optimization (the angle found is never worse than 45°, dispersion grows with noise), and API (all endpoints against a separate test SQLite database — the real `rocket.db` and ChromaDB index are never touched).

## Honest about the limitations

- `confidence` in `/ask` is the model's self-assessment (high/medium/low), not a metric tied to actual embedding distance. The model doesn't always judge its own confidence well — the correct fix is to tie it to the retrieval score, but the thresholds for that need tuning on real data, so it's left as-is for now.
- The agent's conversation memory lives in the process's RAM, with no persistence. Fine for a demo, but it won't survive a server restart or multiple instances.
- The ad-hoc migration in `database.py` can only add new nullable columns — changing a column's type or anything more complex would need real Alembic (it's in the dependencies but not wired up).
- Render's free plan gives 512MB of RAM — even after switching from `sentence-transformers`/`torch` to ChromaDB's lighter built-in ONNX embedding, peak memory under load sits right at the limit (~460MB measured locally under several requests in a row). That's enough for demo-level traffic, but a burst of concurrent requests could theoretically OOM the process.
- The engine is a simplified model (constant thrust + linear mass burn), without the Tsiolkovsky rocket equation or specific impulse. The parachute deploys instantly the moment the fall begins, with no delay. Monte Carlo dispersion is along range only, no crosswind.
- Endpoints are public, with no authentication — this is a learning project, not production.

## How this was built

I worked out the architecture, physics, and test scenarios myself, and wrote it paired with Claude Code — the AI handles the routine work (boilerplate, endpoints, tests) while I check the logic and make the decisions. For an AI Engineer role, I think that's part of the actual skill: working with AI tools as a pair programmer, not just knowing the theory behind LLMs.
