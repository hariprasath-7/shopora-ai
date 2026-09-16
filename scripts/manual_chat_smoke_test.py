"""Manual smoke test for the /chat endpoint against a *running* API server.

Not part of the automated pytest suite (see tests/ for that) — this hits a
real HTTP server and a real LLM, so it needs:
  1. `uv run fastapi dev src/api.py` (or docker compose) running on :8000
  2. A configured GROQ_API_KEY so the agent can actually respond

Usage:
    python scripts/manual_chat_smoke_test.py
"""
import io
import json
import sys
import urllib.request
from uuid import uuid4

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_URL = "http://localhost:8000"


def _post(path: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))


def get_access_token() -> str:
    """/chat requires auth — register a throwaway demo account (or log in if it
    already exists) and return an access token."""
    credentials = {"email": "manual-smoke-test@example.com", "password": "StrongPass123!"}
    try:
        data = _post("/auth/register", {"name": "Manual Smoke Test", **credentials})
    except Exception:
        data = _post("/auth/login", credentials)
    return data["access_token"]


try:
    token = get_access_token()
    data = _post(
        "/chat",
        {"message": "Laptop for AI development under 80000", "thread_id": str(uuid4())},
        token=token,
    )
    print("Response text:", (data.get("response") or "")[:200])
    print("Products count:", len(data.get("products", [])))
    for p in data.get("products", []):
        print(f" - {p['name']} | {p['price']} | {p['match_score']}%")
except Exception as e:
    print("Error:", e)
