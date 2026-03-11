"""
Optimizer API
==============
Routes for running parameter optimization jobs.

POST /api/optimizer/grid        — start grid search
POST /api/optimizer/walk_forward — start walk-forward
POST /api/optimizer/bayesian    — start Bayesian optimization
GET  /api/optimizer/jobs        — list running/completed jobs
GET  /api/optimizer/result/<id> — fetch optimizer result
"""

import uuid
import json
import logging
import threading
from pathlib import Path
from flask import Blueprint, jsonify, request

log = logging.getLogger("backtesting.api_optimizer")
optimizer_bp = Blueprint("optimizer", __name__)

_OPT_DIR = Path(__file__).resolve().parents[3] / "optimizer_results"
_OPT_DIR.mkdir(parents=True, exist_ok=True)
_OPT_JOBS = {}  # job_id → {status, result_id, error}


def _save_opt_result(data: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    with open(_OPT_DIR / f"{job_id}.json", "w") as f:
        json.dump(data, f, indent=2, default=str)
    return job_id


def _run_grid_search(job_id: str, body: dict):
    from backtesting.optimizer.grid_search import GridSearch
    from backtesting.data_collector.expiry_resolver import get_expiry_range

    try:
        expiry_dates = get_expiry_range(body["start"], body["end"])
        param_grid = body.get("param_grid", {})
        gs = GridSearch(
            param_grid=param_grid,
            expiry_dates=expiry_dates,
            underlying=body.get("underlying", "BTC"),
            slippage_bps=body.get("slippage_bps", 2.0),
        )
        results = gs.run()
        result_id = _save_opt_result({"mode": "grid", "results": results[:20]})
        _OPT_JOBS[job_id] = {"status": "done", "result_id": result_id}
    except Exception as e:
        log.error(f"Grid search job {job_id} failed: {e}", exc_info=True)
        _OPT_JOBS[job_id] = {"status": "error", "error": str(e)}


def _run_walk_forward(job_id: str, body: dict):
    from backtesting.optimizer.walk_forward import WalkForwardOptimizer
    try:
        wfo = WalkForwardOptimizer(
            param_grid=body.get("param_grid", {}),
            start_date=body["start"],
            end_date=body["end"],
            train_days=body.get("train_days", 20),
            test_days=body.get("test_days", 5),
            underlying=body.get("underlying", "BTC"),
        )
        report = wfo.run()
        result_id = _save_opt_result({"mode": "walk_forward", **report})
        _OPT_JOBS[job_id] = {"status": "done", "result_id": result_id}
    except Exception as e:
        _OPT_JOBS[job_id] = {"status": "error", "error": str(e)}


@optimizer_bp.route("/grid", methods=["POST"])
def start_grid():
    body = request.get_json() or {}
    if not body.get("param_grid") or not body.get("start") or not body.get("end"):
        return jsonify({"success": False, "error": "param_grid, start, end required"}), 400
    job_id = uuid.uuid4().hex[:8]
    _OPT_JOBS[job_id] = {"status": "running"}
    t = threading.Thread(target=_run_grid_search, args=(job_id, body), daemon=True)
    t.start()
    return jsonify({"success": True, "job_id": job_id})


@optimizer_bp.route("/walk_forward", methods=["POST"])
def start_walk_forward():
    body = request.get_json() or {}
    if not body.get("param_grid") or not body.get("start") or not body.get("end"):
        return jsonify({"success": False, "error": "param_grid, start, end required"}), 400
    job_id = uuid.uuid4().hex[:8]
    _OPT_JOBS[job_id] = {"status": "running"}
    t = threading.Thread(target=_run_walk_forward, args=(job_id, body), daemon=True)
    t.start()
    return jsonify({"success": True, "job_id": job_id})


@optimizer_bp.route("/jobs")
def list_jobs():
    return jsonify({"success": True, "jobs": _OPT_JOBS})


@optimizer_bp.route("/result/<job_id>")
def get_result(job_id):
    job = _OPT_JOBS.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    if job.get("status") != "done":
        return jsonify({"success": True, "status": job.get("status"), "error": job.get("error")})
    result_path = _OPT_DIR / f"{job['result_id']}.json"
    if not result_path.exists():
        return jsonify({"success": False, "error": "Result file not found"}), 404
    with open(result_path) as f:
        data = json.load(f)
    return jsonify({"success": True, "status": "done", "result": data})
