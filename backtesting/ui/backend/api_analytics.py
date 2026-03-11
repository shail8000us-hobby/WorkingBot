"""
Analytics API
==============
REST API for analytics computation and comparison.

GET /api/analytics/session/<id>      — compute metrics for a result
GET /api/analytics/portfolio         — aggregate metrics for multiple results
GET /api/analytics/compare           — side-by-side comparison of result sets
GET /api/analytics/probes/<id>       — weakness probe report for a result
"""

import json
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request

log = logging.getLogger("backtesting.api_analytics")
analytics_bp = Blueprint("analytics", __name__)

_RESULTS_DIR = Path(__file__).resolve().parents[3] / "results"


def _load_result(result_id: str) -> dict:
    path = _RESULTS_DIR / f"{result_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


@analytics_bp.route("/session/<result_id>")
def session_metrics(result_id):
    """Compute metrics for a single session result."""
    result = _load_result(result_id)
    if not result:
        return jsonify({"success": False, "error": "Result not found"}), 404
    try:
        from backtesting.analytics import compute_session_metrics
        metrics = compute_session_metrics(result)
        return jsonify({"success": True, "result_id": result_id, "metrics": metrics})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route("/portfolio")
def portfolio_metrics():
    """
    Aggregate portfolio metrics for a list of result IDs.
    ?result_ids=id1,id2,id3
    """
    ids_param = request.args.get("result_ids", "")
    if not ids_param:
        return jsonify({"success": False, "error": "result_ids query param required"}), 400

    result_ids = [r.strip() for r in ids_param.split(",") if r.strip()]
    results = []
    for rid in result_ids:
        r = _load_result(rid)
        if r:
            results.append(r)

    if not results:
        return jsonify({"success": False, "error": "None of the result IDs found"}), 404

    try:
        from backtesting.analytics import compute_portfolio_metrics
        portfolio = compute_portfolio_metrics(results)
        return jsonify({"success": True, "portfolio": portfolio, "n_results": len(results)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route("/probes/<result_id>")
def weakness_probes(result_id):
    """Run weakness probes on a single session."""
    result = _load_result(result_id)
    if not result:
        return jsonify({"success": False, "error": "Result not found"}), 404
    try:
        from backtesting.analytics import compute_weakness_probes
        probes = compute_weakness_probes([result])
        return jsonify({"success": True, "probes": probes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route("/compare")
def compare():
    """
    Compare two sets of results side-by-side.
    ?set_a=id1,id2&set_b=id3,id4&label_a=V1&label_b=V2
    """
    ids_a   = [r.strip() for r in request.args.get("set_a", "").split(",") if r.strip()]
    ids_b   = [r.strip() for r in request.args.get("set_b", "").split(",") if r.strip()]
    label_a = request.args.get("label_a", "Set A")
    label_b = request.args.get("label_b", "Set B")

    results_a = [r for rid in ids_a if (r := _load_result(rid))]
    results_b = [r for rid in ids_b if (r := _load_result(rid))]

    if not results_a or not results_b:
        return jsonify({"success": False, "error": "Both sets need at least one valid result"}), 400

    try:
        from backtesting.analytics import compute_portfolio_metrics, compute_weakness_probes
        pa = compute_portfolio_metrics(results_a)
        pb = compute_portfolio_metrics(results_b)
        ca = compute_weakness_probes(results_a)
        cb = compute_weakness_probes(results_b)
        return jsonify({
            "success": True,
            "comparison": {
                label_a: {"portfolio": pa, "probes": ca},
                label_b: {"portfolio": pb, "probes": cb},
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route("/report/<result_id>")
def text_report(result_id):
    """Generate a formatted text report for a session."""
    result = _load_result(result_id)
    if not result:
        return jsonify({"success": False, "error": "Result not found"}), 404
    verbose = request.args.get("verbose", "false").lower() == "true"
    try:
        from backtesting.analytics.session_report import generate_session_report
        report = generate_session_report(result, verbose=verbose)
        return jsonify({"success": True, "report": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
