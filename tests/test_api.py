from fastapi.testclient import TestClient

from src.api import app
from src.database import Base, engine


def setup_module():
    Base.metadata.create_all(engine)


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200


def test_auth_and_user_owned_cart():
    with TestClient(app) as client:
        email = "api-test@example.com"
        response = client.post("/auth/register", json={"name": "API Test", "email": email, "password": "StrongPass123!"})
        assert response.status_code == 201
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/auth/me", headers=headers).status_code == 200
        assert client.get("/cart", headers=headers).status_code == 200
        assert client.get("/orders", headers=headers).status_code == 200


def test_protected_routes_require_auth():
    with TestClient(app) as client:
        assert client.get("/cart").status_code == 401
        assert client.get("/orders").status_code == 401
        assert client.post("/chat", json={"message": "find me a laptop"}).status_code == 401


def test_product_endpoint_not_found():
    with TestClient(app) as client:
        assert client.get("/products/999999999").status_code == 404
