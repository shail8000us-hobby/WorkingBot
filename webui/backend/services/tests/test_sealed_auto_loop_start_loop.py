"""
Contract tests for AutoLoopService.start_loop

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Method: start_loop(loop_id, orders, total_rounds, order_preference)
File: webui/backend/services/auto_loop_service.py

Contracts:
  - Returns state dict on success with required keys
  - Initial status is 'running'
  - current_round starts at 0, stop_requested starts as False
  - Raises ValueError if a loop with same id is already running (thread alive)
  - Stale dead thread is cleaned up and restart is allowed
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
