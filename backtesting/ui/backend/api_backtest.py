"""
Backtest API
=============
REST + SocketIO endpoints for running backtest sessions.

POST /api/backtest/run         — run one session (blocking, for quick tests)
POST /api/backtest/run_async   — start session, stream progress via SocketIO
GET  /api/backtest/result/<id> — fetch stored result
GET  /api/backtest/history     — list all result IDs
DELETE /api/backtest/result/<id> — delete a result
"""

import uuid
import json
import logging
import threading
from pathlib import Path
from typing import Dict
from flask import Blueprint, jsonify, request

log = logging.getLogger("backtesting.api_backtest")
backtest_bp = Blueprint("backtest", __name__)

# In-memory result store (persisted to JSON on disk)
_RESULTS_DIR = Path(__file__).resolve().parents[3] / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Active session thread references
_active_sessions: Dict[str, dict] = {}
_socketio_ref = None


def register_socketio(socketio_instance):
    global _socketio_ref
    _socketio_ref = socketio_instance


def _emit(event, data):
    if _socketio_ref:
        _socketio_ref.emit(event, data)


# ── Synchronous run (quick test) ──────────────────────────────────────────────

@backtest_bp.route("/run", methods=["POST"])
def run_backtest():
    """
    Run a single backtest session synchronously.
    Returns immediately with the result.

    POST body:
    {
      "expiry_date":    "DD-MM-YYYY",
      "underlying":     "BTC",
      "entry_time":     "09:15",
      "mode":           "fresh",
      "slippage_bps":   2.0,
      "params": { "desired_ce_premium": 150, ... }
    }
    """
    body = request.get_json() or {}
    expiry_date = body.get("expiry_date", "")
    underlying  = body.get("underlying", "BTC").upper()
    mode        = body.get("mode", "fresh")
    entry_time  = body.get("entry_time", "09:15")
    slippage    = body.get("slippage_bps", 2.0)
    margin      = body.get("initial_margin_usd", 500_000.0)
    params      = body.get("params", {})

    if not expiry_date:
        return jsonify({"success": False, "error": "expiry_date required"}), 400

    try:
        from backtesting.data_store import DataStore
        from backtesting.engine import run_session
        from backtesting.strategies.mmm import MMMAdapter
        from backtesting.analytics import result_to_summary_dict

        store  = DataStore()
        df     = store.read_options_data(expiry_date, underlying)
        perp   = store.read_perp_data(expiry_date, underlying)
        params["expiry_date"] = expiry_date

        result = run_session(
            df=df, algo_adapter=MMMAdapter(mode=mode), params=params,
            entry_ist_time=entry_time, expiry_date=expiry_date, underlying=underlying,
            slippage_bps=slippage, initial_margin_usd=margin, perp_df=perp,
        )

        # Save result
        result_id = _save_result(result)
        return jsonify({"success": True, "result_id": result_id, "summary": result_to_summary_dict(result)})

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": f"No data: {e}"}), 404
    except Exception as e:
        log.error(f"Backtest error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ── Async run with SocketIO streaming ─────────────────────────────────────────

@backtest_bp.route("/run_async", methods=["POST"])
def run_async():
    """
    Start a backtest session asynchronously.
    Progress is streamed via SocketIO events: backtest_tick, backtest_done.
    """
    body        = request.get_json() or {}
    session_id  = uuid.uuid4().hex[:8]

    def _run():
        from backtesting.data_store import DataStore
        from backtesting.engine import run_session
        from backtesting.strategies.mmm import MMMAdapter
        from backtesting.analytics import result_to_summary_dict

        expiry   = body.get("expiry_date", "")
        under    = body.get("underlying", "BTC").upper()
        mode     = body.get("mode", "fresh")
        entry_t  = body.get("entry_time", "09:15")
        slippage = body.get("slippage_bps", 2.0)
        margin   = body.get("initial_margin_usd", 500_000.0)
        params   = body.get("params", {})
        params["expiry_date"] = expiry

        def on_tick(ts_ms, fills_df):
            _emit("backtest_tick", {
                "session_id": session_id,
                "ts_ms":      ts_ms,
                "fill_count": len(fills_df) if hasattr(fills_df, "__len__") else 0,
            })

        def on_progress(pct, ts_ms):
            _emit("backtest_progress", {
                "session_id": session_id,
                "pct":        round(pct * 100, 1),
            })

        try:
            store  = DataStore()
            df     = store.read_options_data(expiry, under)
            perp   = store.read_perp_data(expiry, under)

            result = run_session(
                df=df, algo_adapter=MMMAdapter(mode=mode), params=params,
                entry_ist_time=entry_t, expiry_date=expiry, underlying=under,
                slippage_bps=slippage, initial_margin_usd=margin, perp_df=perp,
                on_tick_callback=on_tick, progress_callback=on_progress,
            )
            result_id = _save_result(result)
            _emit("backtest_done", {
                "session_id": session_id,
                "result_id":  result_id,
                "summary":    result_to_summary_dict(result),
            })
        except Exception as e:
            log.error(f"Async backtest error: {e}", exc_info=True)
            _emit("backtest_error", {"session_id": session_id, "error": str(e)})

    t = threading.Thread(target=_run, daemon=True)
    _active_sessions[session_id] = {"thread": t, "status": "running"}
    t.start()

    return jsonify({"success": True, "session_id": session_id})


# ── Result management ─────────────────────────────────────────────────────────

@backtest_bp.route("/result/<result_id>")
def get_result(result_id):
    path = _RESULTS_DIR / f"{result_id}.json"
    if not path.exists():
        return jsonify({"success": False, "error": "Not found"}), 404
    with open(path) as f:
        data = json.load(f)
    return jsonify({"success": True, "result": data})


@backtest_bp.route("/history")
def history():
    results = []
    for p in sorted(_RESULTS_DIR.glob("*.json"), reverse=True)[:50]:
        try:
            with open(p) as f:
                d = json.load(f)
            results.append({
                "result_id":      p.stem,
                "expiry_date":    d.get("expiry_date"),
                "strategy_status": d.get("strategy_status"),
                "net_pnl":        d.get("net_pnl", 0),
                "adjustment_count": d.get("adjustment_count", 0),
            })
        except Exception:
            pass
    return jsonify({"success": True, "results": results})


@backtest_bp.route("/result/<result_id>", methods=["DELETE"])
def delete_result(result_id):
    path = _RESULTS_DIR / f"{result_id}.json"
    if path.exists():
        path.unlink()
    return jsonify({"success": True})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_result(result: dict) -> str:
    result_id = uuid.uuid4().hex[:12]
    path = _RESULTS_DIR / f"{result_id}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    return result_id
