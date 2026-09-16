# Shopora Production Plan

## Completed

- Environment-based configuration with validation, including a hard fail on
  insecure defaults (`SECRET_KEY`, SQLite, missing Groq key) when
  `ENVIRONMENT=production`.
- PostgreSQL-ready SQLAlchemy configuration with a SQLite development/test fallback.
- Dependency-managed DB sessions.
- Redis cache wrapper with graceful degradation (a Redis outage never breaks a request).
- Durable LangGraph PostgreSQL checkpoint support when configured.
- Health and readiness endpoints.
- Trusted-host, CORS, gzip, security headers, request IDs and bounded inputs.
- Per-browser UUID conversation sessions instead of one global session.
- Docker image and local Compose infrastructure.
- `.env.example` and stronger secret handling.
- Frontend API base URL from Vite environment.
- User authentication (JWT access tokens + rotating HttpOnly refresh cookies); every
  cart/order/thread is scoped to the authenticated `customer_id`, both from the
  REST API and from the LangGraph agent's tool layer.
- A `POST /checkout` REST endpoint and the agent's `checkout` tool share the same
  row-locked (`SELECT ... FOR UPDATE`), all-or-nothing order-creation logic, so a
  failed checkout (e.g. insufficient stock) leaves the cart untouched instead of
  partially completing.
- Alembic migrations for the full schema, applied as an explicit deployment step
  (`alembic upgrade head`) rather than ad-hoc `create_all()`.
- Hybrid lexical + semantic product search (pgvector cosine similarity + ILIKE),
  with retrieval-augmented context grounding the agent's product/review answers.
- CI (GitHub Actions) running the backend test suite, Ruff, and the frontend
  build/lint on every push and pull request, against a hermetic test
  configuration that needs no real secrets or external services.

## Next production gates

1. Replace the demo/simulated payment flow with a real provider adapter and webhook verification.
2. Add async background jobs for email notifications, shipment status updates and embedding reindexing.
3. Add OpenTelemetry/LangSmith tracing and metrics dashboards.
4. Extend CI with dependency/security scanning (e.g. `pip-audit`, `npm audit`, container image scanning).
5. Add staging environment, automated backups with restore tests, a secrets manager (rather than plain env vars), and HTTPS termination in front of the API.
6. Add rate limiting on more than just login (currently only `/auth/login` is rate-limited via Redis).

## Why this architecture

SQLAlchemy's engine/session model is designed around a long-lived engine and
scoped sessions, while Alembic provides schema migrations instead of ad-hoc
`create_all()`/`ALTER TABLE` logic. LangGraph documents in-memory checkpointing
for development and PostgreSQL-backed checkpointers for production. Redis's
Python client provides connection pooling and production-oriented retry,
timeout and health-check guidance. FastAPI recommends lifespan for startup/
shutdown resources and containerized deployment for production workloads.

