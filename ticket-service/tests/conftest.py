import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _get_or_create_token(client, username, email, password, role):
    """Registers the user if not already present, then logs in and returns a token."""
    client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password, "role": role},
    )
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, f"Could not log in as {username}: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(client):
    return _get_or_create_token(client, "test_admin", "test_admin@example.com", "testpass123", "admin")


@pytest.fixture(scope="session")
def reporter_token(client):
    return _get_or_create_token(client, "test_reporter", "test_reporter@example.com", "testpass123", "reporter")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def reporter_headers(reporter_token):
    return {"Authorization": f"Bearer {reporter_token}"}