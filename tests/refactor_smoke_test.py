"""
Phase 1 refactor safety net.

This suite verifies that core packages import cleanly and that the primary
Flask application still responds on key read-only endpoints. It is intended
to run quickly and provide immediate feedback when refactors touch shared
utilities or routing.
"""

from __future__ import annotations

import importlib
from typing import Iterable

import pytest


PACKAGE_IMPORT_TARGETS: Iterable[str] = (
    "bot",
    "bot.reconciliation_service",
    "bot.guardian.guardian_bot",
    "bot.observability.errors.catalog",
    "webui.backend.app",
    "webui.backend.recon_routes",
    "services",
    "services.error_monitor",
    "services.error_resolver",
    "services.quick_error_scan",
)


@pytest.mark.parametrize("module_path", PACKAGE_IMPORT_TARGETS)
def test_core_modules_import(module_path: str) -> None:
    """Ensure key modules remain importable."""
    importlib.import_module(module_path)


@pytest.fixture(scope="session")
def flask_app():
    """Provide the Flask application configured for testing."""
    from webui.backend.app import app as application

    application.config.update(TESTING=True)
    return application


@pytest.fixture(scope="session")
def client(flask_app):
    """Expose a Flask test client for endpoint checks."""
    return flask_app.test_client()


def test_health_endpoint(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert payload.get("status") in {"healthy", "error"}


def test_config_endpoint(client) -> None:
    response = client.get("/api/config")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert payload, "Expected non-empty configuration payload"


def test_positions_endpoint(client) -> None:
    response = client.get("/api/positions")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "positions" in payload
    assert "summary" in payload


def test_reconciliation_status_endpoint(client) -> None:
    response = client.get("/api/recon/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    expected_keys = {"status", "enabled", "timestamp"}
    missing = expected_keys.difference(payload.keys())
    assert not missing, f"Missing reconciliation keys: {sorted(missing)}"
