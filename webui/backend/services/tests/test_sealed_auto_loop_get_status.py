"""
Contract tests for AutoLoopService.get_status

SEALED — v1.0.0 — March 4, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Method: get_status(loop_id=None) -> dict
File: webui/backend/services/auto_loop_service.py

Contracts:
  - Known loop_id → returns copy of state dict
  - Unknown loop_id → returns {'exists': False}
  - No loop_id (None) → returns all loops as {loop_id: state} dict
  - Returned dict is a snapshot (copy), not the live state reference
"""
import pytest

pytestmark = pytest.mark.sealed

from webui.backend.services.auto_loop_service import AutoLoopService


class TestGetStatusSingleLoop:

    def test_known_loop_returns_state(self):
        svc = AutoLoopService()
        svc._loops["l1"] = {"status": "running", "loop_id": "l1", "total_rounds": 3}
        status = svc.get_status("l1")
        assert status["status"] == "running"
        assert status["total_rounds"] == 3

    def test_unknown_loop_id_returns_exists_false(self):
        svc = AutoLoopService()
        status = svc.get_status("ghost")
        assert status == {"exists": False}

    def test_returns_loop_id_field(self):
        svc = AutoLoopService()
        svc._loops["l2"] = {"loop_id": "l2", "status": "completed"}
        status = svc.get_status("l2")
        assert status["loop_id"] == "l2"


class TestGetStatusAllLoops:

    def test_no_loop_id_returns_all_loops(self):
        svc = AutoLoopService()
        svc._loops["a"] = {"status": "running"}
        svc._loops["b"] = {"status": "completed"}
        all_status = svc.get_status()
        assert "a" in all_status
        assert "b" in all_status

    def test_empty_service_returns_empty_dict(self):
        svc = AutoLoopService()
        all_status = svc.get_status()
        assert all_status == {}

    def test_all_loops_contains_correct_statuses(self):
        svc = AutoLoopService()
        svc._loops["x"] = {"status": "running"}
        svc._loops["y"] = {"status": "stopped"}
        all_status = svc.get_status()
        assert all_status["x"]["status"] == "running"
        assert all_status["y"]["status"] == "stopped"
