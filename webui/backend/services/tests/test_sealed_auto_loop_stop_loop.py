"""
Contract tests for AutoLoopService.stop_loop

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Method: stop_loop(loop_id) -> bool
File: webui/backend/services/auto_loop_service.py

Contracts:
  - Returns True when a running loop is successfully stopped
  - Returns False when loop_id doesn't exist
  - Returns False when loop is not in 'running' status
  - Sets stop_requested=True on the state dict
  - Sets status to 'stopping'
"""
import pytest

pytestmark = pytest.mark.sealed

from webui.backend.services.auto_loop_service import AutoLoopService


class TestStopLoopRunning:

    def test_returns_true_for_running_loop(self):
        svc = AutoLoopService()
        svc._loops["active"] = {"status": "running", "stop_requested": False}
        result = svc.stop_loop("active")
        assert result is True

    def test_sets_stop_requested_true(self):
        svc = AutoLoopService()
        svc._loops["active"] = {"status": "running", "stop_requested": False}
        svc.stop_loop("active")
        assert svc._loops["active"]["stop_requested"] is True

    def test_sets_status_to_stopping(self):
        svc = AutoLoopService()
        svc._loops["active"] = {"status": "running", "stop_requested": False}
        svc.stop_loop("active")
        assert svc._loops["active"]["status"] == "stopping"


class TestStopLoopNonRunning:

    def test_returns_false_for_unknown_loop(self):
        svc = AutoLoopService()
        result = svc.stop_loop("nonexistent")
        assert result is False

    def test_returns_false_for_completed_loop(self):
        svc = AutoLoopService()
        svc._loops["done"] = {"status": "completed", "stop_requested": False}
        result = svc.stop_loop("done")
        assert result is False

    def test_returns_false_for_error_loop(self):
        svc = AutoLoopService()
        svc._loops["bad"] = {"status": "error", "stop_requested": False}
        result = svc.stop_loop("bad")
        assert result is False

    def test_completed_loop_not_modified(self):
        svc = AutoLoopService()
        svc._loops["done2"] = {"status": "completed", "stop_requested": False}
        svc.stop_loop("done2")
        assert svc._loops["done2"]["stop_requested"] is False
