#!/usr/bin/env python3
"""
Reconciliation API Blueprint
Endpoints for Exchange↔Bot memory reconciliation and provenance tracking
"""

from flask import Blueprint, jsonify, request
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

recon_bp = Blueprint('reconciliation', __name__, url_prefix='/api/recon')

# Global reconciliation service instance (set by app.py)
recon_service = None


def init_reconciliation_service(service):
    """Initialize the global reconciliation service"""
    global recon_service
    recon_service = service


@recon_bp.route('/status', methods=['GET'])
def get_status():
    """
    Get reconciliation service health status
    
    Returns:
        - is_running: bool
        - last_run: timestamp
        - last_success: timestamp
        - last_error: str
        - counters: summary statistics
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        status = recon_service.get_status()
        
        # If we have a recent reconciliation, include summary
        if hasattr(recon_service, '_last_summary'):
            status['summary'] = recon_service._last_summary
        
        return jsonify(status), 200
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route('/table', methods=['GET'])
def get_table():
    """
    Get paginated reconciliation diff table with filters
    
    Query params:
        - filter: all | mismatched | bot | user | open | filled | acknowledged
        - sort_by: severity | age | symbol
        - page: int (default 1)
        - per_page: int (default 100)
    
    Returns:
        - records: list of ReconciliationRecord
        - pagination: page info
        - counters: summary stats
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        # Run reconciliation to get fresh data
        result = recon_service.reconcile()
        
        if result.get("status") != "success":
            return jsonify(result), 500
        
        records = result.get("records", [])
        counters = result.get("counters", {})
        
        # Apply filters
        filter_type = request.args.get('filter', 'all')
        
        if filter_type == 'mismatched':
            records = [r for r in records if r.get("discrepancy") and not r.get("acknowledged")]
        elif filter_type == 'bot':
            records = [r for r in records if r.get("source") == "Bot"]
        elif filter_type == 'user':
            records = [r for r in records if r.get("source") == "User"]
        elif filter_type == 'open':
            records = [r for r in records if r.get("exchange_status") == "open" or r.get("bot_status") == "open"]
        elif filter_type == 'filled':
            records = [r for r in records if r.get("exchange_status") == "filled"]
        elif filter_type == 'acknowledged':
            records = [r for r in records if r.get("acknowledged")]
        
        # Sort
        sort_by = request.args.get('sort_by', 'age')
        
        if sort_by == 'severity':
            severity_order = {'critical': 0, 'warning': 1, 'info': 2, None: 3}
            records.sort(
                key=lambda r: severity_order.get(
                    r.get("discrepancy", {}).get("severity") if r.get("discrepancy") else None,
                    3
                )
            )
        elif sort_by == 'age':
            records.sort(key=lambda r: r.get("age_seconds", 0), reverse=True)
        elif sort_by == 'symbol':
            records.sort(key=lambda r: r.get("symbol", ""))
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 100))
        
        total = len(records)
        start = (page - 1) * per_page
        end = start + per_page
        
        paginated = records[start:end]
        
        return jsonify({
            "status": "success",
            "records": paginated,
            "counters": counters,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            },
            "timestamp": result.get("timestamp")
        }), 200
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route('/resync-json', methods=['POST'])
def resync_json():
    """
    Manually resync local JSON for specific order(s)
    No exchange writes - idempotent local fix only
    
    Body:
        - order_ids: list of order IDs to resync
    
    Returns:
        - results: dict of order_id -> result
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])
        
        if not order_ids:
            return jsonify({
                "error": "No order_ids provided"
            }), 400
        
        results = {}
        
        for order_id in order_ids:
            result = recon_service.resync_order(order_id)
            results[order_id] = result
        
        return jsonify({
            "status": "success",
            "results": results
        }), 200
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route('/acknowledge', methods=['POST'])
def acknowledge():
    """
    Mark discrepancy as acknowledged (suppress future alerts)
    
    Body:
        - order_ids: list of order IDs to acknowledge
    
    Returns:
        - acknowledged: count
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])
        
        if not order_ids:
            return jsonify({
                "error": "No order_ids provided"
            }), 400
        
        for order_id in order_ids:
            recon_service.acknowledge_order(order_id)
        
        return jsonify({
            "status": "success",
            "acknowledged": len(order_ids),
            "order_ids": order_ids
        }), 200
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route('/ignore', methods=['POST'])
def ignore():
    """
    Temporarily ignore order discrepancies (time-boxed)
    
    Body:
        - order_ids: list of order IDs to ignore
        - duration_hours: int (default 24)
    
    Returns:
        - ignored: count
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])
        duration_hours = data.get('duration_hours', 24)
        
        if not order_ids:
            return jsonify({
                "error": "No order_ids provided"
            }), 400
        
        for order_id in order_ids:
            recon_service.ignore_order(order_id, duration_hours)
        
        return jsonify({
            "status": "success",
            "ignored": len(order_ids),
            "order_ids": order_ids,
            "duration_hours": duration_hours
        }), 200
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route('/run', methods=['POST'])
def run_reconciliation():
    """
    Manually trigger reconciliation run (on-demand)
    
    Returns:
        - summary: reconciliation results
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        # Clear cache to force fresh data
        if hasattr(recon_service, '_cache'):
            with recon_service._cache_lock:
                recon_service._cache.clear()
        
        result = recon_service.reconcile()
        
        return jsonify(result), 200 if result.get("status") == "success" else 500
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route('/audit', methods=['GET'])
def get_audit_trail():
    """
    Get reconciliation audit trail
    
    Query params:
        - limit: int (default 100)
        - action: filter by action type
    
    Returns:
        - audit_records: list of audit entries
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        limit = int(request.args.get('limit', 100))
        action_filter = request.args.get('action')
        
        audit_file = recon_service.recon_audit
        
        if not audit_file.exists():
            return jsonify({
                "status": "success",
                "audit_records": []
            }), 200
        
        records = []
        with open(audit_file) as f:
            for line in f:
                if line.strip():
                    import json
                    record = json.loads(line)
                    
                    if action_filter and record.get("action") != action_filter:
                        continue
                    
                    records.append(record)
        
        # Return most recent first
        records.reverse()
        
        return jsonify({
            "status": "success",
            "audit_records": records[:limit],
            "total": len(records)
        }), 200
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@recon_bp.route("/test", methods=["GET"])
def test_reconciliation():
    """
    Test reconciliation service directly
    """
    if not recon_service:
        return jsonify({
            "error": "Reconciliation service not initialized"
        }), 503
    
    try:
        # Test the reconciliation service directly
        result = recon_service.reconcile()
        return jsonify({
            "test_result": result,
            "service_type": str(type(recon_service)),
            "base_dir": str(recon_service.base_dir)
        })
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "service_type": str(type(recon_service)),
            "base_dir": str(recon_service.base_dir)
        }), 500
