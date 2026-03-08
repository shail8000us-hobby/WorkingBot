"""
AI Advisor Memory Store
========================
Persists analysis sessions to data/options_ai_memory.json.
Tracks: flags triggered, rule-based suggestions, optional Claude response,
        and P&L outcome after 1h / 4h.

File schema:
  {
      "sessions": [
          {
              "session_id": "uuid4",
              "timestamp":  "ISO8601",
              "snapshot":   { positions, greeks, margin_pct, spot },
              "rule_analysis": { risk_level, flags, suggestions, summary },
              "ai_response": null | { summary, risk_level, suggestions, ... },
              "outcome_1h":  null | { pnl_delta, verdict },
              "outcome_4h":  null | { pnl_delta, verdict },
          },
          ...
      ]
  }
"""

import json
import uuid
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_MEMORY_FILE = Path(__file__).parent.parent.parent.parent / "data" / "options_ai_memory.json"
_MAX_SESSIONS = 100
_lock = threading.Lock()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        if _MEMORY_FILE.exists():
            return json.loads(_MEMORY_FILE.read_text())
    except Exception as e:
        log.warning(f"[ai_memory] Failed to read memory file: {e}")
    return {"sessions": []}


def _save(data: dict):
    try:
        _MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _MEMORY_FILE.write_text(json.dumps(data, indent=2, default=str))
    except Exception as e:
        log.error(f"[ai_memory] Failed to write memory file: {e}")


# ─── Public API ──────────────────────────────────────────────────────────────

def save_session(
    rule_analysis: dict,
    snapshot: dict,
    ai_response: dict | None = None,
) -> str:
    """
    Create and persist a new analysis session.

    Args:
        rule_analysis: Output from ai_rules_engine.analyze_portfolio()
        snapshot:      Live data captured at analysis time
        ai_response:   Parsed Claude/LLM response (optional, added later via submit_response)

    Returns:
        session_id (str)
    """
    session_id = str(uuid.uuid4())
    session = {
        "session_id":    session_id,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "snapshot":      snapshot,
        "rule_analysis": rule_analysis,
        "ai_response":   ai_response,
        "outcome_1h":    None,
        "outcome_4h":    None,
    }
    with _lock:
        data = _load()
        data["sessions"].append(session)
        # Trim to max size (keep most recent)
        data["sessions"] = data["sessions"][-_MAX_SESSIONS:]
        _save(data)
    log.info(f"[ai_memory] Saved session {session_id[:8]}…")
    return session_id


def attach_ai_response(session_id: str, ai_response: dict) -> bool:
    """
    Attach a parsed LLM response to an existing session.
    Returns True if the session was found and updated.
    """
    with _lock:
        data = _load()
        for s in data["sessions"]:
            if s["session_id"] == session_id:
                s["ai_response"] = ai_response
                _save(data)
                log.info(f"[ai_memory] Attached AI response to session {session_id[:8]}…")
                return True
    log.warning(f"[ai_memory] Session not found for attach: {session_id}")
    return False


def record_outcome(session_id: str, hours: int, pnl_delta: float) -> bool:
    """
    Record P&L delta at 1h or 4h mark.
    Called by a background checker thread.
    Calculates 'verdict': positive if pnl improved, negative otherwise.
    """
    key = f"outcome_{hours}h"
    verdict = "positive" if pnl_delta >= 0 else "negative"
    with _lock:
        data = _load()
        for s in data["sessions"]:
            if s["session_id"] == session_id:
                s[key] = {
                    "pnl_delta": round(pnl_delta, 2),
                    "verdict":   verdict,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
                _save(data)
                return True
    return False


def get_recent_sessions(n: int = 10) -> list:
    """Return the last n sessions (most recent first)."""
    data = _load()
    sessions = data.get("sessions", [])
    return list(reversed(sessions[-n:]))


def get_outcome_summary() -> dict:
    """
    Return accuracy stats across all sessions that have outcomes recorded.
    """
    data = _load()
    sessions = data.get("sessions", [])
    total = 0
    positive_1h = 0
    positive_4h = 0
    for s in sessions:
        o1 = s.get("outcome_1h")
        o4 = s.get("outcome_4h")
        if o1 or o4:
            total += 1
            if o1 and o1.get("verdict") == "positive":
                positive_1h += 1
            if o4 and o4.get("verdict") == "positive":
                positive_4h += 1
    return {
        "total_evaluated": total,
        "positive_1h": positive_1h,
        "positive_4h": positive_4h,
        "accuracy_1h_pct": round(positive_1h / total * 100, 1) if total else None,
        "accuracy_4h_pct": round(positive_4h / total * 100, 1) if total else None,
    }
