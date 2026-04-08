"""
MMMX Integrity Signature

Provides a lightweight, deterministic state signature that the UI can use for
sequence/hash drift detection.

This is intentionally read-only and side-effect free.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def _stable(v: Any) -> Any:
    """Convert values into a deterministic JSON-safe representation."""
    if isinstance(v, float):
        return round(v, 8)
    if isinstance(v, (int, str, bool)) or v is None:
        return v
    if isinstance(v, list):
        return [_stable(x) for x in v]
    if isinstance(v, tuple):
        return [_stable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _stable(vv) for k, vv in sorted(v.items(), key=lambda kv: str(kv[0]))}
    return str(v)


def _canonical_view(session: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the canonical UI-facing subset used for checksum validation.

    Keep this small and stable. Add fields cautiously and only when they are
    meaningfully part of operator-visible state.
    """
    return {
        'session_id': session.get('session_id'),
        'status': session.get('status'),
        'beat_number': int(session.get('beat_number', 0) or 0),
        'last_beat_at': session.get('_last_beat_at') or session.get('last_beat_at'),
        'portfolio_pnl': float(session.get('portfolio_pnl', 0.0) or 0.0),
        'portfolio_delta': float(session.get('portfolio_delta', 0.0) or 0.0),
        'hard_stop_usd': float(session.get('hard_stop_usd', 0.0) or 0.0),
        'tranches_deployed': int(session.get('tranches_deployed', 0) or 0),
        'tranches_remaining': int(session.get('tranches_remaining', 0) or 0),
        'active_hedges': int(session.get('active_hedges', 0) or 0),
        'ce_reserve_remaining': float(session.get('ce_reserve_remaining', 0.0) or 0.0),
        'pe_reserve_remaining': float(session.get('pe_reserve_remaining', 0.0) or 0.0),
        'reconcile_required': bool(session.get('reconcile_required', False)),
        'deployment_eligible_tranches': [
            _stable(x) for x in (session.get('deployment_eligible_tranches') or [])
        ],
        'naked_positions': [
            _stable(x) for x in (session.get('_naked_positions') or [])
        ],
    }


def build_integrity_signature(
    session: Dict[str, Any],
    *,
    source: str,
) -> Dict[str, Any]:
    """
    Return a deterministic state signature payload.

    Output contract:
      {
        "source": "heartbeat"|"snapshot",
        "schema": "v1",
        "state_version": int,
        "state_checksum": str,
        "generated_at": iso8601,
      }
    """
    canonical = _stable(_canonical_view(session))
    blob = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    checksum = hashlib.sha256(blob.encode('utf-8')).hexdigest()

    return {
        'source': source,
        'schema': 'v1',
        'state_version': int(session.get('beat_number', 0) or 0),
        'state_checksum': checksum,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
