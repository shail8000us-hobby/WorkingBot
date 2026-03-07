"""
Contract tests for AutoLoopService.clear_finished

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Method: clear_finished() -> int
File: webui/backend/services/auto_loop_service.py

Contracts:
  - Removes loops with status 'completed', 'stopped', 'error'
  - Keeps loops with status 'running' or 'stopping'
  - Returns count of removed loops
  - Returns 0 when nothing to clear
"""
import pytest

pytestmark = pytest.mark.sealed

from webui.backend.services.auto_loop_service import AutoLoopService


class TestClearFinishedRemovals:

    def test_removes_completed_loop(self):
        svc = AutoLoopService()
        svc._loops["done"] = {"status": "completed"}
        svc.clear_finished()
        assert "done" not in svc._loops

    def test_removes_stopped_loop(self):
        svc = AutoLoopService()
        svc._loops["halted"] = {"status": "stopped"}
        svc.clear_finished()
        assert "halted" not in svc._loops

    def test_removes_error_loop(self):
        svc = AutoLoopService()
        svc._loops["broken"] = {"status": "error"}
        svc.clear_finished()
        assert "broken" not in svc._loops

    def test_keeps_running_loop(self):
        svc = AutoLoopService()
        svc._loops["active"] = {"status": "running"}
        svc.clear_finished()
        assert "active" in svc._loops

    def test_keeps_stopping_loop(self):
        svc = AutoLoopService()
        svc._loops["winding_down"] = {"status": "stopping"}
        svc.clear_finished()
        assert "winding_down" in svc._loops


class TestClearFinishedCount:

    def test_returns_count_of_removed_loops(self):
        svc = AutoLoopService()
        svc._loops["d1"] = {"status": "completed"}
        svc._loops["d2"] = {"status": "stopped"}
        svc._loops["d3"] = {"status": "error"}
        count = svc.clear_finished()
        assert count == 3

    def test_returns_zero_when_nothing_to_clear(self):
        svc = AutoLoopService()
        svc._loops["active"] = {"status": "running"}
        count = svc.clear_finished()
        assert count == 0

    def test_returns_zero_for_empty_service(self):
        svc = AutoLoopService()
        count = svc.clear_finished()
        assert count == 0

    def test_mixed_keeps_and_removes(self):
        svc = AutoLoopService()
        svc._loops["r"] = {"status": "running"}
        svc._loops["c"] = {"status": "completed"}
        svc._loops["e"] = {"status": "error"}
        count = svc.clear_finished()
        assert count == 2
        assert "r" in svc._loops
        assert "c" not in svc._loops
        assert "e" not in svc._loops
