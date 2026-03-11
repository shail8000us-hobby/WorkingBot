"""
Data API
=========
Routes for data collection status and available expiry dates.

GET  /api/data/status          — overall collection summary
GET  /api/data/dates           — list of collected expiry dates
GET  /api/data/check/<date>    — integrity check for one date
GET  /api/data/job/<job_id>    — poll a running collection job
POST /api/data/collect         — start data collection job (background thread)
"""

import threading
import logging
import uuid
import time as _time
from flask import Blueprint, jsonify, request
from backtesting.data_store import DataStore, ChainIndex, check_expiry

log = logging.getLogger("backtesting.api_data")
data_bp = Blueprint("data", __name__)

# ── In-memory job registry ────────────────────────────────────────────────────
_JOBS: dict = {}   # job_id → {status, message, progress, done, error, results}


# ─────────────────────────────────────────────────────────────────────────────
@data_bp.route("/status")
def status():
    """Overall collection index summary."""
    try:
        idx = ChainIndex()
        summary = idx.summary()
        store = DataStore()
        collected = idx.list_collected("BTC")
        recent = collected[:10]
        details = []
        for d in recent:
            details.append({
                "date":    d,
                "rows":    idx.get_row_count(d, "BTC"),
                "size_mb": store.file_size_mb(d, "BTC"),
            })
        return jsonify({"success": True, "summary": summary, "recent": details})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@data_bp.route("/dates")
def dates():
    """List all collected expiry dates for an underlying."""
    underlying = request.args.get("underlying", "BTC").upper()
    try:
        idx = ChainIndex()
        collected = idx.list_collected(underlying)
        failed    = idx.list_failed(underlying)
        return jsonify({
            "success":    True,
            "collected":  collected,
            "failed":     failed,
            "underlying": underlying,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@data_bp.route("/check/<date>")
def check_date(date):
    """Run integrity check on a collected date."""
    underlying = request.args.get("underlying", "BTC").upper()
    try:
        issues = check_expiry(date, underlying)
        return jsonify({
            "success":    True,
            "date":       date,
            "underlying": underlying,
            "issues":     [{"severity": i.severity, "issue": i.issue} for i in issues],
            "is_clean":   not any(i.severity == "ERROR" for i in issues),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Job status endpoint ───────────────────────────────────────────────────────
@data_bp.route("/job/<job_id>")
def job_status(job_id):
    """Poll the status of a background collection job."""
    job = _JOBS.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    return jsonify({"success": True, **job})


# ── Start collection ──────────────────────────────────────────────────────────
@data_bp.route("/collect", methods=["POST"])
def collect():
    """
    Start a data collection job.
    POST body: { "start": "DD-MM-YYYY", "end": "DD-MM-YYYY", "underlying": "BTC", "overwrite": false }
    Runs in background — poll GET /api/data/job/<job_id> to check progress / completion.
    """
    body       = request.get_json() or {}
    start_date = body.get("start", "")
    end_date   = body.get("end",   "")
    underlying = body.get("underlying", "BTC").upper()
    overwrite  = body.get("overwrite",  False)

    if not start_date or not end_date:
        return jsonify({"success": False, "error": "start and end dates are required"}), 400

    job_id = uuid.uuid4().hex[:10]
    _JOBS[job_id] = {
        "job_id":      job_id,
        "status":      "running",
        "message":     f"Starting collection for {underlying} {start_date}→{end_date}",
        "progress":    0,
        "total":       0,
        "done":        False,
        "error":       None,
        "results":     [],
        "started_at":  _time.time(),
    }

    def _run():
        from backtesting.data_collector import collect_date_range
        from backtesting.data_collector.expiry_resolver import get_expiry_range
        try:
            expiries = get_expiry_range(start_date, end_date)
            _JOBS[job_id]["total"] = len(expiries)
            _JOBS[job_id]["message"] = f"Collecting {len(expiries)} expiry dates for {underlying}"

            def _cb(expiry_date, step, done_count, total_count):
                pct = (done_count / max(total_count, 1)) * 100
                _JOBS[job_id]["message"] = f"[{expiry_date}] {step} ({done_count}/{total_count})"
                _JOBS[job_id]["progress"] = pct

            results = collect_date_range(
                start_date, end_date, underlying,
                overwrite=overwrite,
                progress_callback=_cb,
            )

            _JOBS[job_id]["results"]  = [
                {
                    "date":    r.expiry_date,
                    "success": r.success,
                    "rows":    r.row_count,
                    "error":   r.error,
                }
                for r in results
            ]
            ok   = sum(1 for r in results if r.success)
            fail = sum(1 for r in results if not r.success)

            if fail > 0 and ok == 0:
                _JOBS[job_id]["status"]  = "error"
                _JOBS[job_id]["message"] = (
                    f"All {fail} date(s) failed — Delta Exchange only retains data for ~7 days. "
                    f"Please enter dates within the last 6 days."
                )
                _JOBS[job_id]["error"] = "No data available for the requested date range."
            elif fail > 0:
                _JOBS[job_id]["status"]  = "partial"
                _JOBS[job_id]["message"] = f"Completed: {ok} succeeded, {fail} failed"
            else:
                _JOBS[job_id]["status"]  = "done"
                _JOBS[job_id]["message"] = f"✅ {ok} date(s) collected successfully"

            _JOBS[job_id]["progress"] = 100
            _JOBS[job_id]["done"]     = True

        except Exception as e:
            log.error(f"Background collection error: {e}", exc_info=True)
            _JOBS[job_id]["status"]  = "error"
            _JOBS[job_id]["message"] = f"Error: {str(e)}"
            _JOBS[job_id]["error"]   = str(e)
            _JOBS[job_id]["done"]    = True

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({
        "success": True,
        "job_id":  job_id,
        "message": f"Collection started for {underlying} {start_date}→{end_date}",
    })
