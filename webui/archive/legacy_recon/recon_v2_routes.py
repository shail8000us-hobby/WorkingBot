from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request


recon_v2_bp = Blueprint("reconciliation_v2", __name__, url_prefix="/api/recon/v2")

_service = None
_run_lock = Lock()


def init_reconciliation_v2_service(service) -> None:
    global _service
    _service = service


def _current_time() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@recon_v2_bp.route("/status", methods=["GET"])
def recon_v2_status():
    if not _service:
        return jsonify({"available": False, "error": "service_unavailable"}), 503

    report = _service.get_last_report()
    if not report:
        return jsonify({"available": False, "server_time": _current_time()}), 200

    return jsonify(
        {
            "available": True,
            "server_time": _current_time(),
            "report": report,
        }
    )


def _background_run(dry_run: Optional[bool]) -> None:
    try:
        _service.run_cycle(dry_run=dry_run)
    finally:
        _run_lock.release()


@recon_v2_bp.route("/run", methods=["POST"])
def recon_v2_run():
    if not _service:
        return jsonify({"accepted": False, "error": "service_unavailable"}), 503

    if not _run_lock.acquire(blocking=False):
        return jsonify(
            {
                "accepted": False,
                "error": "already_running",
                "server_time": _current_time(),
                "last": _service.get_last_report(),
            }
        )

    payload = request.get_json(silent=True) or {}
    dry_run_param = payload.get("dry_run")
    dry_run_value = bool(dry_run_param) if dry_run_param is not None else None

    thread = Thread(target=_background_run, args=(dry_run_value,), daemon=True)
    thread.start()

    return jsonify(
        {
            "accepted": True,
            "server_time": _current_time(),
            "last": _service.get_last_report(),
        }
    )


def _load_report_or_404() -> Optional[Dict[str, Any]]:
    if not _service:
        return None
    return _service.get_last_report()


@recon_v2_bp.route("/mismatches", methods=["GET"])
def recon_v2_mismatches():
    if not _service:
        return jsonify({"error": "service_unavailable"}), 503

    report = _load_report_or_404()
    if not report:
        return jsonify({"error": "no_snapshot"}), 404

    records = report.get("records", [])

    kind = request.args.get("kind")
    if kind == "all":
        kind = None
    provenance = request.args.get("provenance")
    search = request.args.get("search")

    filtered = []
    for item in records:
        if kind:
            if kind == "mismatches":
                if item["kind"] == "synced":
                    continue
            elif item["kind"] != kind:
                continue
        else:
            if item["kind"] == "synced":
                continue

        if provenance and provenance != "any" and item.get("provenance") != provenance:
            continue

        if search:
            needle = search.lower()

            def _record_matches(record: Optional[Dict[str, Any]]) -> bool:
                if not record:
                    return False
                for key in ("id", "clientOrderId", "symbol"):
                    value = record.get(key)
                    if value and needle in str(value).lower():
                        return True
                return False

            if not (
                _record_matches(item.get("exchange"))
                or _record_matches(item.get("bot"))
            ):
                continue

        filtered.append(item)

    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(min(int(request.args.get("page_size", 50)), 500), 1)
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = filtered[start:end]

    return jsonify(
        {
            "items": paginated,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "server_time": _current_time(),
        }
    )


@recon_v2_bp.route("/provenance", methods=["GET"])
def recon_v2_provenance():
    if not _service:
        return jsonify({"error": "service_unavailable"}), 503

    report = _load_report_or_404()
    if not report:
        return jsonify({"error": "no_snapshot"}), 404

    return jsonify(
        {
            "server_time": _current_time(),
            "counts": report.get("counts", {}),
            "provenance": report.get("provenance", {}),
            "totals": report.get("totals", {}),
        }
    )
