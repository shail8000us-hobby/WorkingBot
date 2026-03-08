"""
Options AI Engine — Flask Blueprint Routes

Exposes the AI engine via HTTP endpoints.
Register in app.py with a single try/except block (see integration instructions).

Routes:
  GET  /api/options-ai/status       → engine status
  POST /api/options-ai/analyze      → trigger immediate analysis
  POST /api/options-ai/toggle-auto  → toggle automation mode
  GET  /api/options-ai/history      → last N decisions
  GET  /api/options-ai/memory       → full memory log
"""

import logging
from flask import Blueprint, jsonify, request
from .engine import get_engine
from . import memory_store

log = logging.getLogger(__name__)

options_ai_bp = Blueprint("options_ai", __name__, url_prefix="/api/options-ai")


@options_ai_bp.route("/status", methods=["GET"])
def get_status():
    """Return engine status, last analysis time, mode (suggest/auto)."""
    try:
        engine = get_engine()
        return jsonify({"success": True, "data": engine.get_status()})
    except Exception as e:
        log.error(f"[routes] /status error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_bp.route("/analyze", methods=["POST"])
def trigger_analysis():
    """
    Trigger an immediate full AI analysis cycle.

    Optional JSON body:
      { "risk_preference": "conservative" | "moderate" | "aggressive" }
    """
    try:
        data = request.get_json(silent=True) or {}
        risk_pref = data.get("risk_preference", "moderate")
        engine = get_engine()
        result = engine.analyze(risk_pref=risk_pref)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        log.error(f"[routes] /analyze error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_bp.route("/toggle-auto", methods=["POST"])
def toggle_automation():
    """
    Enable or disable automation mode.

    Required JSON body:
      { "enabled": true | false }
    """
    try:
        data = request.get_json(silent=True) or {}
        if "enabled" not in data:
            return jsonify({"success": False, "error": "Missing 'enabled' field"}), 400
        enabled = bool(data["enabled"])
        engine = get_engine()
        result = engine.toggle_automation(enabled)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        log.error(f"[routes] /toggle-auto error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_bp.route("/history", methods=["GET"])
def get_history():
    """
    Return the last N AI decisions from the memory store.
    Query param: ?n=10 (default from config)
    """
    try:
        n = int(request.args.get("n", 10))
        records = memory_store.load_recent(n)
        return jsonify({"success": True, "data": records, "count": len(records)})
    except Exception as e:
        log.error(f"[routes] /history error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@options_ai_bp.route("/memory", methods=["GET"])
def get_memory():
    """Return the full AI decision learning log."""
    try:
        records = memory_store.load_all()
        return jsonify({"success": True, "data": records, "count": len(records)})
    except Exception as e:
        log.error(f"[routes] /memory error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
