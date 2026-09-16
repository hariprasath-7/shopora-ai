# Shopora — Production-Grade AI Shopping Agent

Shopora is an AI shopping assistant built with **FastAPI, PostgreSQL, Redis, LangGraph, LangChain, React/Vite and pgvector**. A conversational agent handles product discovery, comparisons, and the full purchase lifecycle (cart → checkout → order → shipment), backed by a REST API the React frontend also talks to directly for anything that doesn't need the LLM in the loop.

## What is implemented

- Secure registration/login with Argon2 password hashing
- Short-lived JWT access tokens + rotating HttpOnly refresh sessions
- User-scoped carts, orders, payments and shipment data
- Admin-only order status changes and embedding rebuilds
- PostgreSQL + pgvector semantic retrieval
- Hybrid lexical + semantic product search
- Local Sentence Transformers embeddings
- Retrieval-augmented product/review context for grounded AI answers
- Personalized recommendations from purchase/category/quality signals
- LangGraph conversation persistence
- Redis caching (fails open — a Redis outage degrades to "no cache", never a 500)
- A `POST /checkout` REST endpoint for the React cart page, sharing the same locking/stock logic as the agent's `checkout` tool, so checkout works whether the shopper uses the chat agent or the plain UI
- Alembic migrations
- Docker Compose for PostgreSQL + pgvector + Redis + API
- React frontend authentication
- A Streamlit console for exercising the agent directly, with a demo-identity switcher (see below)
- CI (GitHub Actions), a hermetic pytest suite, and Ruff/ESLint linting

## Architecture

```text
React/Vite                     Streamlit (agent demo console)
   │                                   │
   ▼                                   ▼
FastAPI ── JWT/Auth ── PostgreSQL ── LangGraph agent
   │                      ├── relational data     ├── shopping tools (cart/checkout/orders/…)
   │                      └── pgvector embeddings  ├── hybrid search
   └── Redis cache                                 ├── RAG retrieval
                                                    └── recommendations
```

## Local development

1. Copy `.env.example` to `.env` and add a fresh `GROQ_API_KEY` and random `SECRET_KEY`.
   **Never commit a real `.env`** — it's already gitignored. If a real key or secret ever ends up in a file you share (e.g. a zip export), rotate it immediately; treat it as compromised.
2. Start Redis:

```bash
docker run -d --name shopora-redis -p 6379:6379 redis:8-alpine
```

3. Install Python dependencies:

```bash
uv sync --dev
```

4. Create/migrate the database:

```bash
uv run alembic upgrade head
uv run python -m src.seed
uv run python -m src.seed_reviews
```

This also works against the default SQLite database with no Postgres/Redis running at all — handy for a quick local check of the REST API without the full AI stack (semantic search and the embeddings table just no-op until you're on Postgres + pgvector).

5. Start the API:

```bash
uv run fastapi dev src/api.py
```

6. Start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

7. (Optional) Run the Streamlit agent console:

```bash
uv run streamlit run streamlit_app/app.py
```

This is a lightweight console for poking at the LangGraph agent directly — it does **not** use the real login flow. It scopes cart/order/checkout tool calls to a demo identity you pick in the sidebar (auto-created on first use), so different labels behave like different shoppers without needing a password.

## Testing & CI

```bash
uv run pytest -q         # backend unit + API tests (SQLite in-memory, no external services needed)
uv run ruff check src tests
cd frontend && npm run lint && npm run build
```

`tests/conftest.py` sets safe defaults for every required environment variable before any app module is imported, so the suite never depends on your local `.env`, a running Postgres/Redis instance, or a real Groq key — it's the same thing GitHub Actions runs on every push/PR (`.github/workflows/`).

`scripts/` holds a couple of manual smoke-test scripts (hitting a real running server / real DB) that are useful when poking at things by hand — they're intentionally outside `tests/` and not part of CI.

## PostgreSQL + vector search

For the full AI retrieval stack, use the supplied Compose file:

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
export GROQ_API_KEY="your-new-key"
docker compose up --build
```

Then run migrations inside the API container:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m src.seed
docker compose exec api python -m src.seed_reviews
docker compose exec api python -m src.index_embeddings
```

The embedding model is `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions). The model is loaded lazily and product vectors are stored in PostgreSQL with pgvector.

## Security model

- Passwords are never stored in plaintext.
- Access tokens expire quickly.
- Refresh tokens are stored only as SHA-256 hashes and rotated on refresh.
- Refresh tokens are sent through an HttpOnly cookie.
- Every cart/order query is scoped by authenticated `customer_id`.
- LLM tools receive authenticated user context and cannot select another customer's order by ID.
- Admin-only actions (like changing an order's status) are enforced server-side, independent of what the LLM decides to call.
- Product/catalog endpoints remain public; personal endpoints require authentication.
- Production secrets are environment variables only.
- `TrustedHostMiddleware` rejects requests with an unrecognized `Host` header — set `ALLOWED_HOSTS` to include every hostname your deployment is actually reached through (your domain, and any internal health-check hostname), or health checks/load balancers will get a 400.

## Important production prerequisites

The payment flow remains a **demo/simulated payment** and must be replaced with a real provider and webhook verification before accepting real money. You should also put the API behind HTTPS and a reverse proxy, configure a real domain, rotate secrets, add centralized monitoring, and perform load/security testing before a public launch.

