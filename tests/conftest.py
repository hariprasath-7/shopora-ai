"""Shared pytest configuration.

Sets safe, hermetic environment variables *before* any application module is
imported, so the test suite never depends on a developer's local .env file,
a running Postgres/Redis instance, or a real Groq API key.
"""
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LANGGRAPH_DATABASE_URL", "")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-automated-tests-only")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
# "testserver" is the Host header FastAPI's TestClient sends by default.
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("SEMANTIC_SEARCH_ENABLED", "false")
