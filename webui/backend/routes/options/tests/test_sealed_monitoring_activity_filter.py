"""
Sealed contract tests for get_monitoring_activity — active-limits filter (#monitor-filter-1..6)

Function : get_monitoring_activity()
File     : webui/backend/routes/options/options_control.py
Sealed   : 2026-04-18

Bug fixed: get_all_strike_max_loss() / get_all_expiry_max_loss() return rows where
           enabled=1 OR triggered=1, so old triggered/expired entries were counted
           and displayed as "active" in the Monitoring Activity panel.

Fix      : Route now filters to only enabled=True entries before building the
           response, so strikeLimits / expiryLimits / activeLimits counts only
           include limits where monitoring is actively running.

Contracts:
  C1  Only enabled strike limits appear in strikeLimits (triggered excluded)
  C2  Only enabled expiry limits appear in expiryLimits (triggered excluded)
  C3  activeLimits.strike = count of enabled strike limits only
  C4  activeLimits.expiry = count of enabled expiry limits only
  C5  activeLimits.total  = strike + expiry (enabled only)
  C6  Response always has success=True and timestamp key

MOCK OR LIVE    : MOCK
CONFIRMED WORKING ON : 2026-04-18
"""

import json
import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.sealed

BASE_ROUTE = "webui.backend.routes.options.options_control"
# get_activity_log / get_max_loss_monitor are imported INSIDE the function body,
# so they must be patched at their source module, not at BASE_ROUTE.
MAX_LOSS_MGR_MODULE = "webui.backend.options_strategy.max_loss_manager"


def _make_app():
    from flask import Flask
    from webui.backend.routes.options.options_control import options_bp
    app = Flask(__name__)
    app.register_blueprint(options_bp)
    app.config['TESTING'] = True
    return app.test_client()


def _mock_manager(strike_rows, expiry_rows):
    """Return a mock MaxLossManager returning given rows."""
    mgr = MagicMock()
    mgr.get_all_strike_max_loss.return_value = strike_rows
    mgr.get_all_expiry_max_loss.return_value = expiry_rows
    return mgr


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _enabled_strike(symbol="C-BTC-70000-250526"):
    return {"symbol": symbol, "max_loss": 50.0, "enabled": True, "triggered": False, "triggered_at": None}

def _triggered_strike(symbol="C-BTC-71000-250326"):
    """enabled=False, triggered=True — old expired entry."""
    return {"symbol": symbol, "max_loss": 40.0, "enabled": False, "triggered": True, "triggered_at": "2026-03-25T14:00:00"}

def _enabled_expiry(code="250526"):
    return {"expiry_code": code, "max_loss": 200.0, "enabled": True, "triggered": False, "triggered_at": None}

def _triggered_expiry(code="250326"):
    return {"expiry_code": code, "max_loss": 120.0, "enabled": False, "triggered": True, "triggered_at": "2026-03-25T14:00:00"}


# ---------------------------------------------------------------------------
# C1  Only enabled strike limits appear in strikeLimits
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_triggered_strike_excluded_from_strike_limits():
    """
    A strike limit with enabled=False / triggered=True must NOT appear in
    strikeLimits. Showing it would display expired/settled contracts as active.
    """
    client = _make_app()
    manager = _mock_manager(
        strike_rows=[_enabled_strike(), _triggered_strike()],
        expiry_rows=[],
    )
    with patch(f"{BASE_ROUTE}.get_max_loss_manager", return_value=manager), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_max_loss_monitor", return_value=None), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_activity_log", return_value=[]), \
         patch(f"{BASE_ROUTE}.get_hedge_events_snapshot", return_value=[]):
        resp = client.get("/api/options/monitoring-activity")

    data = json.loads(resp.data)
    assert resp.status_code == 200
    symbols = [s["symbol"] for s in data["strikeLimits"]]
    assert "C-BTC-70000-250526" in symbols, "Enabled strike must be included"
    assert "C-BTC-71000-250326" not in symbols, (
        "Triggered strike (enabled=False) must NOT appear in strikeLimits"
    )


# ---------------------------------------------------------------------------
# C2  Only enabled expiry limits appear in expiryLimits
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_triggered_expiry_excluded_from_expiry_limits():
    """
    An expiry limit with enabled=False / triggered=True must NOT appear in
    expiryLimits. Showing it would display settled expiries as active.
    """
    client = _make_app()
    manager = _mock_manager(
        strike_rows=[],
        expiry_rows=[_enabled_expiry(), _triggered_expiry()],
    )
    with patch(f"{BASE_ROUTE}.get_max_loss_manager", return_value=manager), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_max_loss_monitor", return_value=None), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_activity_log", return_value=[]), \
         patch(f"{BASE_ROUTE}.get_hedge_events_snapshot", return_value=[]):
        resp = client.get("/api/options/monitoring-activity")

    data = json.loads(resp.data)
    codes = [e["expiry_code"] for e in data["expiryLimits"]]
    assert "250526" in codes, "Enabled expiry must be included"
    assert "250326" not in codes, (
        "Triggered expiry (enabled=False) must NOT appear in expiryLimits"
    )


# ---------------------------------------------------------------------------
# C3  activeLimits.strike = count of enabled strike limits only
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_active_limits_strike_count_excludes_triggered():
    """
    activeLimits.strike must equal the number of enabled strike limits,
    not the total rows returned by get_all_strike_max_loss().
    """
    client = _make_app()
    manager = _mock_manager(
        strike_rows=[_enabled_strike("C-BTC-70000-250526"), _triggered_strike("C-BTC-71000-250326")],
        expiry_rows=[],
    )
    with patch(f"{BASE_ROUTE}.get_max_loss_manager", return_value=manager), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_max_loss_monitor", return_value=None), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_activity_log", return_value=[]), \
         patch(f"{BASE_ROUTE}.get_hedge_events_snapshot", return_value=[]):
        resp = client.get("/api/options/monitoring-activity")

    data = json.loads(resp.data)
    assert data["activeLimits"]["strike"] == 1, (
        f"Expected activeLimits.strike=1 (only enabled), got {data['activeLimits']['strike']}"
    )


# ---------------------------------------------------------------------------
# C4  activeLimits.expiry = count of enabled expiry limits only
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_active_limits_expiry_count_excludes_triggered():
    """activeLimits.expiry must count only enabled expiry limits."""
    client = _make_app()
    manager = _mock_manager(
        strike_rows=[],
        expiry_rows=[_enabled_expiry("250526"), _triggered_expiry("250326")],
    )
    with patch(f"{BASE_ROUTE}.get_max_loss_manager", return_value=manager), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_max_loss_monitor", return_value=None), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_activity_log", return_value=[]), \
         patch(f"{BASE_ROUTE}.get_hedge_events_snapshot", return_value=[]):
        resp = client.get("/api/options/monitoring-activity")

    data = json.loads(resp.data)
    assert data["activeLimits"]["expiry"] == 1, (
        f"Expected activeLimits.expiry=1 (only enabled), got {data['activeLimits']['expiry']}"
    )


# ---------------------------------------------------------------------------
# C5  activeLimits.total = strike + expiry (enabled only)
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_active_limits_total_is_sum_of_enabled_only():
    """
    activeLimits.total must equal (enabled strikes) + (enabled expiries).
    With 1 enabled strike + 1 triggered strike + 1 enabled expiry + 1 triggered expiry
    the total must be 2, not 4.
    """
    client = _make_app()
    manager = _mock_manager(
        strike_rows=[_enabled_strike(), _triggered_strike()],
        expiry_rows=[_enabled_expiry(), _triggered_expiry()],
    )
    with patch(f"{BASE_ROUTE}.get_max_loss_manager", return_value=manager), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_max_loss_monitor", return_value=None), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_activity_log", return_value=[]), \
         patch(f"{BASE_ROUTE}.get_hedge_events_snapshot", return_value=[]):
        resp = client.get("/api/options/monitoring-activity")

    data = json.loads(resp.data)
    assert data["activeLimits"]["total"] == 2, (
        f"Expected activeLimits.total=2 (1 enabled strike + 1 enabled expiry), "
        f"got {data['activeLimits']['total']}"
    )
    assert data["activeLimits"]["total"] == (
        data["activeLimits"]["strike"] + data["activeLimits"]["expiry"]
    ), "total must equal strike + expiry"


# ---------------------------------------------------------------------------
# C6  Response always has success=True and timestamp key
# ---------------------------------------------------------------------------

@pytest.mark.sealed
def test_response_always_has_success_and_timestamp():
    """GET /monitoring-activity always returns success=True and a timestamp."""
    client = _make_app()
    manager = _mock_manager(strike_rows=[], expiry_rows=[])
    with patch(f"{BASE_ROUTE}.get_max_loss_manager", return_value=manager), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_max_loss_monitor", return_value=None), \
         patch(f"{MAX_LOSS_MGR_MODULE}.get_activity_log", return_value=[]), \
         patch(f"{BASE_ROUTE}.get_hedge_events_snapshot", return_value=[]):
        resp = client.get("/api/options/monitoring-activity")

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data.get("success") is True, "Response must have success=True"
    assert "timestamp" in data, "Response must include a timestamp key"
