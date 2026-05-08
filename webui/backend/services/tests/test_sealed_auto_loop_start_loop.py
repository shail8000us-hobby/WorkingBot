"""
Contract tests for AutoLoopService.start_loop

SEALED — v1.1.0 — May 6, 2026
(Originally sealed v1.0.0 March 4, 2026; UNSEAL granted by user 2026-05-06
to add hybrid-trigger model + partial-fill tracking; resealed v1.1.0.)

Do not modify without UNSEAL command in AI_SEAL.md

Method: start_loop(loop_id, orders, total_rounds, order_preference,
                   interval_seconds=None)
File: webui/backend/services/auto_loop_service.py

v1.0.0 contracts (preserved):
  - Returns state dict on success with required keys
  - Initial status is 'running'
  - current_round starts at 0, stop_requested starts as False
  - Raises ValueError if a loop with same id is already running (thread alive)
  - Stale dead thread is cleaned up and restart is allowed

v1.1.0 contracts (new):
  - State dict carries rounds=[], interval_seconds, next_fire_at=None,
    cancel_pending_requested=False, version='1.1.0'
  - interval_seconds defaults to None (legacy fill-gated)
  - interval_seconds non-positive / non-numeric values normalize to None
  - cancel_pending() returns {requested, stopped} and is idempotent for unknown ids
"""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.sealed

from webui.backend.services.auto_loop_service import AutoLoopService

ORDERS = [{"symbol": "C-BTC-100000-300126", "size": 1, "side": "buy"}]


class TestStartLoopReturnShape:

    def test_returns_dict_with_loop_id(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l1", ORDERS, 3, "maker_first")
        assert state["loop_id"] == "l1"

    def test_initial_status_is_running(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l2", ORDERS, 1, "market_only")
        assert state["status"] == "running"

    def test_total_rounds_stored_correctly(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l3", ORDERS, 5, "maker_first")
        assert state["total_rounds"] == 5

    def test_current_round_starts_at_zero(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l4", ORDERS, 2, "maker_first")
        assert state["current_round"] == 0

    def test_stop_requested_starts_false(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l5", ORDERS, 1, "maker_first")
        assert state["stop_requested"] is False

    def test_order_preference_stored(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l6", ORDERS, 1, "market_only")
        assert state["order_preference"] == "market_only"

    def test_orders_stored_in_state(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("l7", ORDERS, 1, "maker_first")
        assert state["orders"] == ORDERS


class TestStartLoopDuplicatePrevention:

    def test_raises_value_error_if_loop_running_with_live_thread(self):
        svc = AutoLoopService()
        svc._loops["dup"] = {"status": "running"}
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        svc._threads["dup"] = mock_thread
        with pytest.raises(ValueError, match="already running"):
            svc.start_loop("dup", ORDERS, 1, "maker_first")

    def test_allows_restart_when_thread_is_dead(self):
        svc = AutoLoopService()
        svc._loops["dup2"] = {"status": "running"}
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False
        svc._threads["dup2"] = mock_thread
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("dup2", ORDERS, 1, "maker_first")
        assert state["status"] == "running"


# ── v1.1.0 contracts ──────────────────────────────────────────────────


class TestStartLoopV11ReturnShape:
    """v1.1.0 added fields must be present and defaulted correctly."""

    def test_rounds_field_starts_empty_list(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11a", ORDERS, 2, "maker_first")
        assert state["rounds"] == []

    def test_interval_seconds_defaults_to_none(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11b", ORDERS, 2, "maker_first")
        assert state["interval_seconds"] is None

    def test_interval_seconds_stored_when_positive(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11c", ORDERS, 2, "maker_first", interval_seconds=300)
        assert state["interval_seconds"] == 300.0

    def test_interval_seconds_normalized_to_none_on_zero(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11d", ORDERS, 2, "maker_first", interval_seconds=0)
        assert state["interval_seconds"] is None

    def test_interval_seconds_normalized_to_none_on_negative(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11e", ORDERS, 2, "maker_first", interval_seconds=-30)
        assert state["interval_seconds"] is None

    def test_interval_seconds_normalized_to_none_on_non_numeric(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11f", ORDERS, 2, "maker_first", interval_seconds="oops")
        assert state["interval_seconds"] is None

    def test_next_fire_at_starts_none(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11g", ORDERS, 2, "maker_first", interval_seconds=300)
        assert state["next_fire_at"] is None

    def test_cancel_pending_requested_starts_false(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11h", ORDERS, 2, "maker_first")
        assert state["cancel_pending_requested"] is False

    def test_version_field_marks_v110(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            state = svc.start_loop("v11i", ORDERS, 2, "maker_first")
        assert state["version"] == "1.1.0"


class TestCancelPendingContract:
    """cancel_pending(loop_id) is the new v1.1.0 control surface."""

    def test_unknown_loop_returns_not_requested(self):
        svc = AutoLoopService()
        out = svc.cancel_pending("nope")
        assert out == {"requested": False, "stopped": False}

    def test_running_loop_marks_cancel_pending_and_stops(self):
        svc = AutoLoopService()
        with patch.object(svc, "_run_loop"):
            svc.start_loop("cp1", ORDERS, 2, "maker_first")
        out = svc.cancel_pending("cp1")
        assert out == {"requested": True, "stopped": True}
        assert svc._loops["cp1"]["cancel_pending_requested"] is True
        assert svc._loops["cp1"]["stop_requested"] is True
        assert svc._loops["cp1"]["status"] == "stopping"
