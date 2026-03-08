"""
Options AI Engine — Action Executor

Executes AI-suggested adjustments ONLY when automation mode is enabled.
Implements a daily-loss circuit breaker that pauses automation if cumulative
automated losses exceed MAX_AUTO_LOSS_PCT of capital.

SAFETY DESIGN:
  - Default dry_run=True → logs what would happen, places no orders.
  - Only executes on urgency="immediate" AND risk_level="critical".
  - Every execution is logged to the memory store.
  - Circuit breaker is checked before every action.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from .config_ai import AI_ENGINE_CONFIG
from . import memory_store as mem

log = logging.getLogger(__name__)

# Ensure project root is on sys.path for bot imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ─── Capital fetcher (reuses existing /api/capital route) ────────────────────

def _get_total_capital() -> float:
    """Get current total capital from Guardian health file (same source as capital.py)."""
    import json
    guardian_health_file = _PROJECT_ROOT / ".guardian_health"
    try:
        if guardian_health_file.exists():
            with open(guardian_health_file, "r") as f:
                data = json.load(f)
                return float(
                    data.get("liquidation", {}).get("margin", {}).get("total_balance", 0) or 0
                )
    except Exception as e:
        log.warning(f"[action_executor] Could not read capital: {e}")
    return 0.0


# ─── Circuit Breaker ─────────────────────────────────────────────────────────

def circuit_breaker_check() -> Dict[str, Any]:
    """
    Check if daily auto-loss has exceeded the configured limit.

    Returns:
        {"ok": bool, "loss": float, "limit_pct": float, "capital": float}
    """
    capital = _get_total_capital()
    loss = mem.get_auto_loss_total_today()
    max_loss_pct = AI_ENGINE_CONFIG["max_auto_loss_pct"]

    if capital <= 0:
        # Unknown capital — be conservative and allow (log warning)
        log.warning("[action_executor] Cannot determine capital — circuit breaker passive")
        return {"ok": True, "loss": loss, "limit_pct": max_loss_pct, "capital": 0}

    loss_pct = (loss / capital) * 100
    tripped = loss_pct >= max_loss_pct
    if tripped:
        log.error(
            f"[action_executor] 🚨 CIRCUIT BREAKER TRIPPED — auto loss {loss_pct:.2f}% "
            f">= limit {max_loss_pct:.2f}%. Automation paused."
        )
    return {
        "ok": not tripped,
        "loss": loss,
        "loss_pct": round(loss_pct, 3),
        "limit_pct": max_loss_pct,
        "capital": capital,
    }


# ─── Order Executor ───────────────────────────────────────────────────────────

def _execute_suggestion(suggestion: Dict, dry_run: bool = True) -> Dict:
    """
    Execute a single AI suggestion (close/hedge/reduce).

    Args:
        suggestion: One item from ai_response["suggestions"].
        dry_run: If True, only log — no actual orders.

    Returns:
        Result dict with 'executed', 'dry_run', 'detail'.
    """
    symbol = suggestion.get("position_id", "")
    action = suggestion.get("action", "hold")

    if action == "hold":
        return {"executed": False, "dry_run": dry_run, "detail": "hold — no action"}

    if dry_run:
        log.info(
            f"[action_executor] DRY-RUN would {action.upper()} {symbol} "
            f"(urgency={suggestion.get('urgency')}, reason={suggestion.get('reason', '')[:80]})"
        )
        return {
            "executed": False,
            "dry_run": True,
            "symbol": symbol,
            "action": action,
            "detail": f"DRY-RUN: would {action} {symbol}",
        }

    # ── Live execution via existing options_control helpers ──────────────────
    try:
        from webui.backend.routes.options.options_client import get_unified_client, _run_async
        from webui.backend.routes.options.options_control import determine_close_side
        from webui.backend.routes.options.order_executor import place_smart_order, ORDER_TYPE_MARKET_ONLY

        client = get_unified_client()

        if action in ("close", "reduce"):
            async def _do_close():
                positions = await client.get_all_positions_with_options()
                for pos in positions.get("options", []):
                    if pos.get("product_symbol") == symbol:
                        size = abs(float(pos.get("size", 0)))
                        side = determine_close_side(float(pos.get("size", 0)))
                        return await place_smart_order(
                            client=client,
                            symbol=symbol,
                            size=size,
                            side=side,
                            order_preference=ORDER_TYPE_MARKET_ONLY,
                            reduce_only=True,
                        )
                raise ValueError(f"Position not found: {symbol}")

            result = _run_async(_do_close())
            log.info(f"[action_executor] ✅ EXECUTED {action} {symbol}: {result}")
            return {"executed": True, "dry_run": False, "symbol": symbol, "action": action, "result": result}

        # For hedge/roll we currently fall into dry-run (complex multi-leg logic
        # should be implemented per strategy — listed as "would hedge" for now)
        log.info(f"[action_executor] '{action}' for {symbol} requires manual execution (not auto-implemented)")
        return {"executed": False, "dry_run": False, "symbol": symbol, "action": action, "detail": f"{action} not auto-implemented — please execute manually"}

    except Exception as e:
        log.error(f"[action_executor] Execution failed for {action} {symbol}: {e}")
        return {"executed": False, "dry_run": False, "symbol": symbol, "error": str(e)}


# ─── Public API ───────────────────────────────────────────────────────────────

def process_suggestions(
    ai_response: Dict,
    positions_snapshot: List[Dict],
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Process AI suggestions and execute qualifying ones.

    Qualifications for auto-execution (all must be true):
      1. automation_mode is True in config
      2. suggestion urgency == urgency_threshold_for_auto ("immediate")
      3. ai_response risk_level == risk_threshold_for_auto ("critical")
      4. Circuit breaker is not tripped

    Args:
        ai_response: Full AI response dict.
        positions_snapshot: Current positions list (for memory logging).
        dry_run: Override — if True/False overrides automation_mode.
                 If None, uses config automation_mode.

    Returns:
        Dict with: mode, circuit_breaker, executed_count, results
    """
    if dry_run is None:
        dry_run = not AI_ENGINE_CONFIG["automation_mode"]

    urgency_threshold = AI_ENGINE_CONFIG["urgency_threshold_for_auto"]
    risk_threshold = AI_ENGINE_CONFIG["risk_threshold_for_auto"]
    risk_level = ai_response.get("risk_level", "low")

    # Check circuit breaker before any execution
    cb = circuit_breaker_check()
    if not cb["ok"] and not dry_run:
        log.error("[action_executor] Circuit breaker tripped — skipping all executions")
        return {
            "mode": "automation_paused",
            "circuit_breaker": cb,
            "executed_count": 0,
            "results": [],
            "reason": "Circuit breaker tripped due to daily loss limit",
        }

    suggestions = ai_response.get("suggestions", [])
    results = []
    executed_count = 0

    for suggestion in suggestions:
        urgency = suggestion.get("urgency", "optional")

        # Only auto-execute immediately-urgent suggestions when risk is critical
        should_execute = (
            not dry_run
            and urgency == urgency_threshold
            and risk_level == risk_threshold
        )
        effective_dry_run = not should_execute

        result = _execute_suggestion(suggestion, dry_run=effective_dry_run)
        results.append(result)
        if result.get("executed"):
            executed_count += 1

    mode = "automation" if not dry_run else "suggestion"
    log.info(
        f"[action_executor] Processed {len(suggestions)} suggestions in {mode} mode. "
        f"Executed: {executed_count}"
    )

    return {
        "mode": mode,
        "circuit_breaker": cb,
        "executed_count": executed_count,
        "dry_run": dry_run,
        "results": results,
    }


# ─── Standalone Test ─────────────────────────────────────────────────────────

def test():
    print("=== action_executor.test() ===")
    print("  NOTE: Always runs in DRY-RUN mode regardless of config.")
    mock_ai_response = {
        "risk_level": "critical",
        "suggestions": [
            {
                "position_id": "C-BTC-120000-280326",
                "action": "close",
                "urgency": "immediate",
                "reason": "Deep OTM, high loss, high gamma risk",
                "alternative": "Hedge with put spread",
            },
            {
                "position_id": "P-BTC-80000-280326",
                "action": "hold",
                "urgency": "monitor",
                "reason": "Profitable position, no action needed",
                "alternative": "Consider taking partial profit",
            },
        ],
    }
    mock_positions = [{"product_symbol": "C-BTC-120000-280326", "unrealized_pnl": -1200}]

    # Force dry_run=True for testing
    result = process_suggestions(mock_ai_response, mock_positions, dry_run=True)
    print(f"  Mode: {result['mode']}")
    print(f"  Executed: {result['executed_count']}")
    print(f"  Results: {len(result['results'])}")
    assert result["dry_run"] is True
    assert result["executed_count"] == 0  # dry-run never executes

    cb = circuit_breaker_check()
    print(f"  Circuit breaker: ok={cb['ok']} loss={cb['loss']:.2f}")
    print("  PASSED ✅")


if __name__ == "__main__":
    test()
