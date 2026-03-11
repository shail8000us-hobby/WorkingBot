"""
MMM State Factory
==================
Creates a fresh or imported MMM session state dict for backtesting.

Reuses the exact same schema from production mmm_state.py so that
the backtesting engine can use all existing MMM logic without modification.
"""

import sys
import os
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional

log = logging.getLogger("backtesting.mmm_state_factory")

# ── Point to production MMM state module ─────────────────────────────────────
_MMM_PATH = Path(__file__).resolve().parents[4] / "webui" / "backend" / "routes" / "mmm"
if str(_MMM_PATH) not in sys.path:
    sys.path.insert(0, str(_MMM_PATH))


def create_fresh_session(
    params: Dict[str, Any],
    session_id: Optional[str] = None,
    expiry_date: str = "",
) -> Dict[str, Any]:
    """
    Create a fresh MMM session state dict using production mmm_state.DEFAULT_PARAMS.

    Args:
        params:      User-provided MMM parameters (overrides DEFAULT_PARAMS)
        session_id:  Optional session ID (generated if not provided)
        expiry_date: "DD-MM-YYYY" expiry date

    Returns:
        Session state dict compatible with all production MMM modules.
    """
    # Set backtest mode flag before importing
    os.environ["BACKTEST_MODE"] = "true"

    try:
        from mmm_state import create_session, DEFAULT_PARAMS
        session = create_session()
        # Merge user params on top of defaults
        session["params"].update(DEFAULT_PARAMS)
        session["params"].update(params)
    except ImportError:
        log.warning("mmm_state.py not importable — using minimal session dict")
        session = _minimal_session()

    # Set session metadata
    session["session_id"]      = session_id or uuid.uuid4().hex[:8]
    session["expiry_date"]     = expiry_date
    session["strategy_status"] = "IDLE"
    session["backtest_mode"]   = True

    log.info(f"Created MMM session: {session['session_id']} for {expiry_date}")
    return session


def create_import_session(
    ce_strike: float,
    ce_lots: int,
    ce_entry_premium: float,
    pe_strike: float,
    pe_lots: int,
    pe_entry_premium: float,
    params: Dict[str, Any],
    session_id: Optional[str] = None,
    expiry_date: str = "",
) -> Dict[str, Any]:
    """
    Create an MMM session that starts from pre-existing positions (Import mode).

    Equivalent to mmm_monitor's init-import process.
    """
    session = create_fresh_session(params, session_id, expiry_date)

    # CE side
    session["ce"]["original_lots"]     = ce_lots
    session["ce"]["original_premium"]  = ce_entry_premium
    session["ce"]["original_strike"]   = ce_strike
    session["ce"]["active_strike"]     = ce_strike
    session["ce"]["active_lots"]       = ce_lots
    session["ce"]["total_lots"]        = ce_lots
    session["ce"]["trigger_snapshot"]  = {str(int(ce_strike)): ce_entry_premium}

    # PE side
    session["pe"]["original_lots"]     = pe_lots
    session["pe"]["original_premium"]  = pe_entry_premium
    session["pe"]["original_strike"]   = pe_strike
    session["pe"]["active_strike"]     = pe_strike
    session["pe"]["active_lots"]       = pe_lots
    session["pe"]["total_lots"]        = pe_lots
    session["pe"]["trigger_snapshot"]  = {str(int(pe_strike)): pe_entry_premium}

    session["strategy_status"] = "RUNNING"
    log.info(
        f"Import session {session['session_id']}: "
        f"CE {ce_lots}L@{ce_strike} p={ce_entry_premium:.1f}, "
        f"PE {pe_lots}L@{pe_strike} p={pe_entry_premium:.1f}"
    )
    return session


def _minimal_session() -> Dict[str, Any]:
    """
    Fallback minimal session dict if mmm_state.py cannot be imported.
    Mirrors the structure of the production session dict.
    """
    def side():
        return {
            "original_lots":        0,
            "original_premium":     0.0,
            "original_strike":      0.0,
            "active_strike":        0.0,
            "adjustment_fills":     [],
            "adjustment_total_lots": 0,
            "adjustment_avg":       0.0,
            "frozen_positions":     [],
            "frozen_total_lots":    0,
            "active_lots":          0,
            "total_lots":           0,
            "trigger_snapshot":     {},
        }

    return {
        "session_id":           "",
        "expiry_date":          "",
        "strategy_status":      "IDLE",
        "backtest_mode":        True,
        "last_aggressor":       "NONE",
        "adjustment_count":     0,
        "reversal_count":       0,
        "shift_count":          0,
        "close_at_5_count":     0,
        "adjustment_history":   [],
        "realized_pnl":         0.0,
        "unrealized_pnl":       0.0,
        "total_premium_collected": 0.0,
        "total_fees":           0.0,
        "peak_pnl":             0.0,
        "harvest_count":        0,
        "harvest_lots_freed":   0,
        "recycle_count":        0,
        "ce":                   side(),
        "pe":                   side(),
        "params": {
            "desired_ce_premium":     150.0,
            "desired_pe_premium":     150.0,
            "initial_lots":           10,
            "min_trigger_move_pct":   3.0,
            "shift_threshold":        50.0,
            "shift_target_premium":   100.0,
            "close_at_threshold":     5.0,
            "premium_buffer_pct":     5.0,
            "max_lots_per_side":      100,
            "max_adjustments":        30,
            "max_loss_amount":        0,
            "stop_adjustment_mins":   15,
            "auto_close_mins":        5,
            "whipsaw_limit":          3,
            "trailing_stop_pct":      50.0,
            "adjustment_interval":    300,
            "adaptive_interval_enabled": True,
            "wind_down_enabled":      True,
            "wind_down_minutes":      120,
            "harvest_enabled":        True,
            "recycle_enabled":        True,
            "perp_hedge_enabled":     False,
        },
    }
