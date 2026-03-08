"""
Options AI Engine — Memory Store

Persists AI decisions and outcomes to a JSON file.
The last N decisions (configurable) are injected into each new AI prompt
so the AI can learn from its own track record.
"""

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config_ai import AI_ENGINE_CONFIG

log = logging.getLogger(__name__)

# Resolve memory file path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
MEMORY_FILE = _PROJECT_ROOT / AI_ENGINE_CONFIG["memory_file"]


def _read_all() -> List[Dict]:
    """Load all records from the JSON file (safe — returns [] on error)."""
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception as e:
        log.warning(f"[memory_store] read error: {e}")
    return []


def _write_all(records: List[Dict]) -> None:
    """Overwrite the JSON file atomically."""
    import tempfile, os
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=MEMORY_FILE.parent, suffix=".tmp"
        ) as f:
            tmp = f.name
            json.dump(records, f, indent=2, default=str)
        os.replace(tmp, str(MEMORY_FILE))
    except Exception as e:
        if tmp:
            try:
                os.remove(tmp)
            except Exception:
                pass
        log.error(f"[memory_store] write error: {e}")


# ─── Public API ──────────────────────────────────────────────────────────────

def save_decision(
    positions_snapshot: List[Dict],
    ai_response: Dict,
    action_taken: str = "suggested",
    automated: bool = False,
) -> str:
    """
    Append a new decision record and return its unique ID.

    Args:
        positions_snapshot: List of position dicts at time of analysis.
        ai_response: The full AI JSON response dict.
        action_taken: 'suggested' | 'executed' | 'ignored'
        automated: Whether action was taken autonomously (automation mode).

    Returns:
        The generated record ID.
    """
    record_id = str(uuid.uuid4())[:8]
    record = {
        "id": record_id,
        "timestamp": datetime.now().isoformat(),
        "position_count": len(positions_snapshot),
        "symbols": [p.get("product_symbol", p.get("symbol", "?")) for p in positions_snapshot],
        "risk_level": ai_response.get("risk_level", "unknown"),
        "summary": ai_response.get("summary", ""),
        "suggestion_count": len(ai_response.get("suggestions", [])),
        "confidence": ai_response.get("confidence", 0.0),
        "action_taken": action_taken,
        "automated": automated,
        "outcome_1h": None,
        "outcome_4h": None,
        "outcome_24h": None,
        "pnl_before": sum(p.get("unrealized_pnl", 0) for p in positions_snapshot),
        "pnl_after": None,
        "verdict": None,          # "correct" | "incorrect" | "neutral"
    }
    records = _read_all()
    records.append(record)
    # Keep at most 200 records to bound file size
    if len(records) > 200:
        records = records[-200:]
    _write_all(records)
    log.info(f"[memory_store] saved decision {record_id} (risk={record['risk_level']})")
    return record_id


def update_outcome(record_id: str, pnl_after: float, period: str = "1h") -> bool:
    """
    Update the P&L outcome for a previously saved decision.

    Args:
        record_id: ID returned by save_decision.
        pnl_after: Current unrealised P&L total at check time.
        period: '1h' | '4h' | '24h'

    Returns:
        True if the record was found and updated.
    """
    records = _read_all()
    for r in records:
        if r.get("id") == record_id:
            field = f"outcome_{period}"
            r[field] = pnl_after
            r["pnl_after"] = pnl_after
            pnl_before = r.get("pnl_before", 0)
            if pnl_after is not None and pnl_before is not None:
                delta = pnl_after - pnl_before
                # Verdict: if risk was high/critical and P&L improved → correct
                risk = r.get("risk_level", "low")
                if risk in ("high", "critical"):
                    r["verdict"] = "correct" if delta > 0 else "incorrect"
                else:
                    r["verdict"] = "neutral"
            _write_all(records)
            log.info(f"[memory_store] updated outcome for {record_id} (period={period})")
            return True
    log.warning(f"[memory_store] record {record_id} not found for outcome update")
    return False


def load_recent(n: Optional[int] = None) -> List[Dict]:
    """Return the most recent N memory records (default: config memory_window)."""
    if n is None:
        n = AI_ENGINE_CONFIG["memory_window"]
    records = _read_all()
    return records[-n:] if len(records) > n else records


def load_all() -> List[Dict]:
    """Return the full decision history."""
    return _read_all()


def get_auto_loss_total_today() -> float:
    """
    Sum all automated losses recorded today (for circuit breaker).
    Losses are expressed as negative values; this returns a positive number.
    """
    from datetime import date
    today = date.today().isoformat()
    total_loss = 0.0
    for r in _read_all():
        if not r.get("automated"):
            continue
        ts = r.get("timestamp", "")
        if not ts.startswith(today):
            continue
        before = r.get("pnl_before") or 0
        after = r.get("pnl_after")
        if after is not None:
            delta = after - before
            if delta < 0:
                total_loss += abs(delta)
    return total_loss


# ─── Standalone Test ─────────────────────────────────────────────────────────

def test():
    import os
    # Use a temp file for the test
    import tempfile
    global MEMORY_FILE
    orig = MEMORY_FILE
    tmp_dir = Path(tempfile.mkdtemp())
    MEMORY_FILE = tmp_dir / "test_memory.json"

    print("=== memory_store.test() ===")
    mock_positions = [
        {"product_symbol": "C-BTC-120000-280326", "unrealized_pnl": -1200},
        {"product_symbol": "P-BTC-100000-280326", "unrealized_pnl": 800},
    ]
    mock_ai = {
        "risk_level": "high",
        "summary": "Test summary",
        "suggestions": [{"action": "hedge"}],
        "confidence": 0.75,
    }
    rid = save_decision(mock_positions, mock_ai)
    print(f"  Saved decision: {rid}")

    recent = load_recent(5)
    print(f"  Loaded {len(recent)} recent records")
    assert len(recent) == 1
    assert recent[0]["id"] == rid

    ok = update_outcome(rid, pnl_after=-300, period="1h")
    print(f"  Updated outcome: {ok}")
    assert ok

    updated = load_all()
    assert updated[0]["pnl_after"] == -300
    print(f"  Verdict: {updated[0]['verdict']}")
    print("  PASSED ✅")

    MEMORY_FILE = orig
    import shutil; shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    test()
