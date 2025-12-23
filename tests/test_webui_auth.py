import base64

import pytest

from webui.backend.app import app


@pytest.fixture
def client():
    with app.test_client() as test_client:
        yield test_client


def test_config_requires_auth(client):
    response = client.get("/api/config")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") is not None


def test_config_allows_bearer_token(client):
    response = client.get(
        "/api/config",
        headers={"Authorization": "Bearer unit-test-token"},
    )
    assert response.status_code == 200


def test_config_allows_basic_auth(client):
    basic_token = base64.b64encode(b"unit:unit-secret").decode()
    response = client.get(
        "/api/config",
        headers={"Authorization": f"Basic {basic_token}"},
    )
    assert response.status_code == 200
