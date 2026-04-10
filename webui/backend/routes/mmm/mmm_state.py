"""
MMM State Management — Money Mind & Method

Defines the complete state model for the MMM algorithm as specified in
MONEY_POWER_CALCULATION_LOGIC.md Section 2 (State) and Section 19 (Parameters).

Per-side state (CE/PE), global state, and session dataclass.

Created: February 15, 2026
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from copy import deepcopy

from .mmm_constants import strike_key as strike_key_fn
from webui.backend.sealed import sealed

log = logging.getLogger('mmm_state')


# =============================================================================
# Section 2: Per-Side State
# =============================================================================

# Fix #23: Unified Position Ledger helpers

def _migrate_side_to_positions(side_state: Dict) -> None:
    """
    Fix #23: Migrate old 3-array format to Unified Position Ledger.

    Converts legacy fields (original_lots scalar + adjustment_fills[] +
    frozen_positions[]) into a single positions[] list with unique IDs and
    lifecycle status. Called automatically by recompute_side_lots() when
    positions[] key is absent. Idempotent.
    """
    if side_state.get('_positions_migrated'):
        return

    now = datetime.now(timezone.utc).isoformat()
    positions = []
    counter = 0
    side = side_state.get('side', 'XX').lower()

    # Migrate original_lots → original position (active)
    orig_lots = side_state.get('original_lots', 0)
    if orig_lots > 0:
        counter += 1
        positions.append({
            'id': f"{side}_orig",
            'strike': (
                side_state.get('original_strike')
                or side_state.get('active_strike', 0)
            ),
            'lots': orig_lots,
            'entry_premium': side_state.get('original_premium', 0),
            'premium': side_state.get('original_premium', 0),
            'type': 'original',
            'status': 'active',
            'created_at': now,
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,
        })

    # Migrate adjustment_fills → active non-original positions
    for fill in side_state.get('adjustment_fills', []):
        lots = fill.get('lots', 0)
        if lots <= 0:
            continue
        counter += 1
        positions.append({
            'id': f"{side}_adj_{counter:03d}",
            'strike': fill.get('strike', side_state.get('active_strike', 0)),
            'lots': lots,
            'entry_premium': fill.get('premium', 0),
            'premium': fill.get('premium', 0),
            'type': fill.get('type', 'adjustment'),
            'status': 'active',
            'created_at': fill.get('timestamp', now),
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': fill.get('timestamp', now),
        })

    # Migrate frozen_positions → shifted positions
    for frozen in side_state.get('frozen_positions', []):
        lots = frozen.get('lots', 0)
        if lots <= 0:
            continue
        counter += 1
        positions.append({
            'id': f"{side}_frozen_{counter:03d}",
            'strike': frozen.get('strike', 0),
            'lots': lots,
            'entry_premium': frozen.get('entry_premium', 0),
            'premium': frozen.get('entry_premium', 0),
            'type': frozen.get('type', 'adjustment'),
            'status': 'shifted',
            'created_at': frozen.get('timestamp', now),
            'shifted_at': frozen.get('frozen_at', now),
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': frozen.get('timestamp', now),
            'source': frozen.get('source', ''),
        })

    side_state['positions'] = positions
    side_state['_pos_counter'] = counter
    side_state['_positions_migrated'] = True
    if '_positions_migrating' in side_state:
        del side_state['_positions_migrating']
    
    # Fix F2.5: Validate position ID uniqueness — defense-in-depth
    ids = [p['id'] for p in positions]
    if len(ids) != len(set(ids)):
        log.error(f"[Fix F2.5] Migration created duplicate position IDs: {ids}")
        # Deduplicate by appending counter suffix to duplicates
        seen = set()
        for pos in positions:
            if pos['id'] in seen:
                counter += 1
                pos['id'] = f"{pos['id']}_{counter:03d}"
            seen.add(pos['id'])
        side_state['_pos_counter'] = counter
    
    log.debug(
        f"[Fix #23] Migrated {side} to Unified Position Ledger: "
        f"{len(positions)} position(s)"
    )


def create_side_state(
    side: str,
    original_lots: int = 0,
    original_premium: float = 0.0,
    original_strike: float = 0.0,
) -> Dict[str, Any]:
    """
    Create initial per-side state for CE or PE.

    Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 2: Per-Side State.

    Fix #23: positions[] is now the single source of truth. All other
    position-related fields are backward-compatible derived values computed
    by recompute_side_lots(). Do NOT write to adjustment_fills, frozen_positions,
    or original_lots directly — write to positions[] instead.

    Args:
        side: 'CE' or 'PE'
        original_lots: Lots sold at entry
        original_premium: Premium per lot at entry
        original_strike: Strike price at entry

    Returns:
        Dictionary with all per-side state fields
    """
    now = datetime.now(timezone.utc).isoformat()
    positions = []
    counter = 0

    # Fix #23: Add initial position to the Unified Position Ledger
    if original_lots > 0:
        counter += 1
        positions.append({
            'id': f"{side.lower()}_orig",
            'strike': original_strike,
            'lots': original_lots,
            'entry_premium': original_premium,
            'premium': original_premium,     # backward-compat alias
            'type': 'original',
            'status': 'active',
            'created_at': now,
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,                # backward-compat alias
        })

    return {
        'side': side,

        # Fix #23: Unified Position Ledger — single authoritative source
        'positions': positions,
        '_pos_counter': counter,

        # Active strike tracking (starts as original, changes on shift)
        'active_strike': original_strike,

        # Trigger snapshot: {strike_key → premium_at_last_trigger_update}
        'trigger_snapshot': {},

        # --- Backward-compatible derived fields ---
        # Populated by recompute_side_lots() from positions[].
        # Do NOT write to these directly — they are overwritten on every recompute.
        'original_lots': original_lots,
        'original_premium': original_premium,
        'original_strike': original_strike,   # Set at creation; never changed by recompute
        'adjustment_fills': [],
        'adjustment_total_lots': 0,
        'adjustment_avg': 0.0,
        'frozen_positions': [],
        'frozen_total_lots': 0,
        'active_lots': original_lots,
        'total_lots': original_lots,
    }


@sealed
def recompute_side_lots(side_state: Dict) -> Dict:
    """
    Recompute all position counts and backward-compatible views from positions[].

    Fix #23: positions[] is the single source of truth. This function:
      1. Auto-migrates old sessions (no positions[] key) to the new format
      2. Rebuilds adjustment_fills, frozen_positions, original_lots from positions[]
      3. Derives all scalar lot counts (active_lots, total_lots, etc.)

    Call this after any mutation to positions[]. The derived fields
    (adjustment_fills, frozen_positions, etc.) are read-only views — do NOT
    mutate them directly, as they will be overwritten on the next recompute.

    Args:
        side_state: The per-side state dictionary (mutated in place)

    Returns:
        Updated side_state
    """
    # Fix #23: Auto-migrate old 3-array format if positions[] not present
    if 'positions' not in side_state:
        _migrate_side_to_positions(side_state)

    # M-18 fix: validate positions type after migration/load
    positions = side_state.get('positions', [])
    if not isinstance(positions, list):
        log.error(f"Invalid positions type {type(positions)} — resetting")
        positions = []
        side_state['positions'] = []

    # Auto-normalize: active positions at non-active strikes should be shifted.
    # Handles the case where set_active_strike (📌) or operator inject (💉) at a
    # different strike left positions at old strikes still marked 'active'.
    _active_strike = side_state.get('active_strike', 0)
    if _active_strike > 0:
        _now_str = datetime.now(timezone.utc).isoformat()
        for _pos in positions:
            if _pos.get('status') == 'active':
                _pos_strike = float(_pos.get('strike', 0))
                if _pos_strike > 0 and abs(_pos_strike - _active_strike) >= 1:
                    _pos['status'] = 'shifted'
                    if not _pos.get('shifted_at'):
                        _pos['shifted_at'] = _now_str
                    log.info(
                        f"recompute_side_lots: auto-shifted pos {_pos.get('id', '?')} "
                        f"at strike {int(_pos_strike)} (active_strike={int(_active_strike)})"
                    )

    # Partition by lifecycle status
    active_positions = [p for p in positions if p.get('status') == 'active']
    shifted_positions = [p for p in positions if p.get('status') == 'shifted']

    # --- Rebuild original_lots / original_premium scalar ---
    # AUDIT FIX BUG1: Sum ALL active originals (not just first) to prevent lot drops
    orig_positions = [p for p in active_positions if p.get('type') == 'original']
    if len(orig_positions) > 1:
        log.warning(
            f"recompute_side_lots: found {len(orig_positions)} active originals — "
            f"summing lots (expected 1). Check for duplicate position records."
        )
    total_orig_lots = sum(p.get('lots', 0) for p in orig_positions)
    side_state['original_lots'] = total_orig_lots
    if orig_positions:
        # Use lot-weighted average premium for multiple originals
        total_prem_wt = sum(
            p.get('lots', 0) * p.get('entry_premium', p.get('premium', 0))
            for p in orig_positions
        )
        side_state['original_premium'] = (
            total_prem_wt / total_orig_lots if total_orig_lots > 0 else 0.0
        )
    else:
        side_state['original_premium'] = 0.0
    # original_strike is set at creation and never changed by recompute

    # --- Rebuild adjustment_fills view (active non-original positions) ---
    # Each entry includes '_pos_id' for O(1) removal by ID (Fix #23)
    adj_positions = [p for p in active_positions if p.get('type') != 'original']
    side_state['adjustment_fills'] = [
        {
            'lots': p.get('lots', 0),
            'premium': p.get('entry_premium', p.get('premium', 0)),
            'strike': p.get('strike', 0),
            'timestamp': p.get('created_at', p.get('timestamp', '')),
            'type': p.get('type', 'adjustment'),
            '_pos_id': p.get('id', ''),  # Fix #23: O(1) ID-based removal
            '_being_closed': p.get('_being_closed', False),  # AUDIT FIX: propagate in-flight flag
            '_being_closed_at': p.get('_being_closed_at', 0),  # required for TTL auto-clear
        }
        for p in adj_positions
    ]

    # --- Rebuild frozen_positions view (shifted positions) ---
    # Each entry includes '_pos_id' for O(1) removal by ID (Fix #23)
    side_state['frozen_positions'] = [
        {
            'strike': p.get('strike', 0),
            'lots': p.get('lots', 0),
            'entry_premium': p.get('entry_premium', p.get('premium', 0)),
            'type': p.get('type', 'adjustment'),
            'frozen_at': p.get('shifted_at', ''),
            '_pos_id': p.get('id', ''),  # Fix #23: O(1) ID-based removal
            '_being_closed': p.get('_being_closed', False),  # AUDIT FIX: propagate in-flight flag
            '_being_closed_at': p.get('_being_closed_at', 0),  # required for TTL auto-clear
            'source': p.get('source', ''),
        }
        for p in shifted_positions
    ]

    # --- Derive scalars from views ---
    adj_fills = side_state['adjustment_fills']
    side_state['adjustment_total_lots'] = sum(f.get('lots', 0) for f in adj_fills)

    if side_state['adjustment_total_lots'] > 0:
        total_prem = sum(f.get('lots', 0) * f.get('premium', 0) for f in adj_fills)
        side_state['adjustment_avg'] = total_prem / side_state['adjustment_total_lots']
    else:
        side_state['adjustment_avg'] = 0.0

    frozen = side_state['frozen_positions']
    side_state['frozen_total_lots'] = sum(f.get('lots', 0) for f in frozen)

    side_state['active_lots'] = (
        side_state['original_lots'] + side_state['adjustment_total_lots']
    )
    side_state['total_lots'] = side_state['active_lots'] + side_state['frozen_total_lots']

    return side_state


# =============================================================================
# Section 2: Global State + Section 19: Parameters → MMMSession
# =============================================================================

# Default parameter values from Section 19
DEFAULT_PARAMS = {
    'desired_ce_premium': 100.0,
    'desired_pe_premium': 100.0,
    'initial_lots': 10,
    'expiry': '',                       # Set at entry

    # Hot-reloadable parameters
    'adjustment_interval': 300,         # seconds between checks
    'min_trigger_move': 10.0,           # minimum premium move above trigger
    'min_trigger_dollar': 0.0,          # dollar floor: also trigger if active-strike USD loss > this (0 = disabled)
    'min_frozen_trigger_dollar': 0.2,   # fallback: trigger from frozen positions if their USD loss > this (0 = disabled)
    'shift_threshold': 50.0,            # min premium to sell at current strike
    'shift_target_premium': 100.0,      # target premium for new strike on shift
    'shift_premium_tolerance': 10.0,   # ±$ tolerance around shift_target_premium for candidate validation
    'close_at_threshold': 5.0,          # close positions at this premium or below
    'close_at_use_bid': True,           # use bid price (not mark) for close_at_5 checks — more accurate for illiquid options
    'close_at_watch_interval': 30,      # seconds between proactive close-at-5 watcher checks (0 = disabled)
    'close_at_max_per_beat': 3,         # max positions to close per heartbeat (prevents heartbeat stall on mass-close)
    'close_at_watcher_force_enabled': False,  # UI toggle: force watcher on regardless of expiry window
    'close_at_watch_hours_before_expiry': 3.0,  # watcher auto-activates within this many hours of expiry (0 = always on)
    'close_at_watch_near_expiry_interval': 10,  # watcher interval (seconds) when inside expiry window — faster for 0DTE
    'premium_buffer_pct': 0.05,         # 5% extra lots for slippage
    'max_lots_per_side': 100,           # maximum total lots per CE or PE
    # Split Ledger Phase 1
    'max_total_exposure': 0,            # absolute ceiling on active+frozen lots per side. 0 = auto (2× max_lots_per_side)
    # Split Ledger Phase 2: Shift-Time Recycle
    'shift_recycle_enabled': False,             # proactive cleanup at shift time. Start disabled.
    'shift_recycle_premium_floor': 20.0,        # only close frozen positions with premium < this. 0 = dynamic mode
    'shift_recycle_max_pct': 1.0,               # max fraction of frozen lots to close per shift (0.0-1.0)
    'shift_recycle_floor_ratio': 0.40,          # when premium_floor<=0, floor = new_strike_premium × this ratio
    'shift_recycle_pressure_threshold': 0.7,    # only run if total_lots/max_lots >= this (0=always run)
    'max_adjustments': 500,             # maximum adjustment events
    'max_loss_amount': 100.0,          # hard stop P&L threshold
    'stop_adjustment_mins': 15,         # stop adjusting N mins before expiry
    'auto_close_mins': 5,              # auto-close all N mins before expiry
    'cooldown_on_reversal': True,       # skip 1 interval on reversal
    'whipsaw_limit': 3,                 # DEPRECATED — backward compat alias for whipsaw_cooldown_score
    'trailing_stop_pct': 0.0,           # protect profit at N% of peak (0 = disabled)

    # Adaptive Whipsaw Guard — graduated response to alternating adjustments
    'whipsaw_window_mins': 30,           # rolling window: only count alternations within this window
    'whipsaw_spot_move_pct': 0.3,        # spot move % to consider alternation 'justified' (not noise)
    'whipsaw_caution_score': 2,          # score to widen triggers +50%
    'whipsaw_restrict_score': 3,         # score to widen triggers +100% and halve lots
    'whipsaw_cooldown_score': 4,         # score to skip one interval (NOT full pause)
    'theta_acceleration_window': 120,   # minutes before expiry to widen triggers
    'shift_threshold_pct': 0.0,            # dynamic shift: max(shift_threshold, hedge_premium * pct). 0 = disabled
    'shift_match_opposite_lots': True,     # delta-neutral: match opposite side's lot count on strike shift
    'pre_sell_shift_enabled': False,       # shift to target premium BEFORE selling when hedge premium < shift_target_premium
    'shift_cooldown_sec': 120,             # minimum seconds between consecutive strike shifts
    'shift_fallback_enabled': True,     # when no new strike meets threshold, try fallback sell at current (decayed) strike
    'shift_fallback_min_premium': 25.0, # fallback only fires if decayed premium >= this; below = skip (near-worthless adds delta risk for no credit)

    # Dangerous Mode — operator-controlled expiry sprint
    'dangerous_mode': False,            # bypass all safety gates (cooldowns, regime, whipsaw, asymmetry). max_loss, ITM guard, and auto-close near expiry still active. OPERATOR MUST TYPE CONFIRM TO ENABLE.

    # Adaptive interval
    'adaptive_interval_enabled': True,     # auto-scale heartbeat frequency based on time-to-expiry

    # Wind-down mode
    'wind_down_enabled': False,            # reduce positions instead of adding near expiry
    'wind_down_hours_before_expiry': 2.0,  # activate wind-down N hours before expiry
    'wind_down_buyback_pct': 0.25,         # fraction of lots to buy back per trigger
    'wind_down_close_threshold': 20.0,     # elevated close-at-5 during wind-down
    'wind_down_min_lots_to_keep': 0,       # never go below this many lots per side (0 = full unwind allowed)
    'wind_down_floor_action': 'skip',      # what to do at floor: skip|normal|pause
    'wind_down_on_atm': False,             # auto-activate wind-down when original strike goes ATM

    # Margin Guardian (P1 safety layer)
    'margin_monitor_enabled': False,       # disabled until user opts in
    'margin_green_pct': 50.0,             # below this = normal operation
    'margin_yellow_pct': 60.0,            # caution — block new sells
    'margin_orange_pct': 75.0,            # auto wind-down (aggressive buyback)
    'margin_red_pct': 85.0,              # emergency reduce (taker orders)
    'margin_critical_pct': 90.0,          # survival — close ALL, stop session
    'margin_target_pct': 50.0,            # target utilization to wind down to

    # Regime Controls — pre-adjustment risk intelligence
    'regime_enabled': False,                 # MASTER switch for ALL regime controls (vol/gamma/trend)
    # Section A: Volatility Regime Filter
    'vol_regime_enabled': True,            # per-subsystem switch for vol regime filter
    'vol_iv_spike_pct': 30,               # IV change % threshold to trigger ELEVATED/HIGH
    'vol_rv_threshold': 80,               # annualized RV % threshold
    'vol_lookback_beats': 5,              # beats for IV rate calculation
    'vol_rv_window': 20,                  # beats for RV window
    'vol_regime_action': 'block_sells',   # action: block_sells / pause / wind_down
    'vol_regime_cooldown_beats': 10,      # beats below threshold before NORMAL

    # Section B: Portfolio Gamma Cap
    'gamma_cap_enabled': True,             # master switch for gamma cap
    'gamma_soft_limit': 2500.0,           # dollar gamma soft limit (warning) — BTC-scaled
    'gamma_hard_limit': 5000.0,           # dollar gamma hard limit (block sells) — BTC-scaled
    'gamma_emergency_limit': 10000.0,     # dollar gamma emergency (force reduce) — BTC-scaled
    'gamma_near_expiry_multiplier': 0.5,  # tighten limits by this factor in last 30 min
    # Tier B: per-side gamma imbalance threshold
    'gamma_side_imbalance_ratio': 1.5,    # one side must have ≥ this × other's gamma to be "dominant"
    # Tier C: DTE-aware hedge limit relaxation
    'gamma_dte_relax_hours': 2.0,         # hours before expiry where hedge limit is relaxed
    'gamma_dte_hedge_multiplier': 2.0,    # multiply hard_limit by this for hedge sells in DTE window
    # Tier D: delta rescue — override gamma block for forced hedge sell near expiry
    'gamma_rescue_window_minutes': 120,   # minutes to expiry within which delta rescue can fire
    # Directional dead-band: minimum % move from anchor to trust anchor direction
    'gamma_directional_min_pct': 0.10,    # below this, direction is ambiguous → fall to per-side gamma

    # Section C: Trend Detection Guard — Tiered Response (IMP-2)
    'trend_enabled': True,                 # master switch for trend guard
    'trend_tier1_pct': 0.5,              # % move from anchor → Tier 1 (alert + lot reduction)
    'trend_tier2_pct': 1.0,              # % move from anchor → Tier 2 (block aggressor-side sells)
    'trend_tier3_pct': 1.5,              # % move from anchor → Tier 3 (block ALL sells)
    'trend_tier4_pct': 2.0,              # % move from anchor → Tier 4 (auto wind-down)
    'trend_tier1_lot_reduction': 0.30,   # lot reduction at Tier 1 (0.30 = reduce by 30%)
    'trend_move_pct': 1.5,               # DEPRECATED — kept for backward compat, use tier2_pct
    'trend_retrace_pct': 30,             # % retracement required to reset
    'trend_ema_period': 10,              # EMA period in beats
    'trend_ema_slope_threshold': 25,     # EMA slope threshold (Tier 1 confirmation only)
    'trend_action': 'block_sells',       # action: block_sells / pause / wind_down
    'trend_reset_beats': 5,              # beats calm required before reset
    'trend_plateau_reset_beats': 5,      # beats of flat EMA + raw_tier < current_tier → plateau reset
    'trend_t4_timeout_beats': 20,        # beats of flat EMA at Tier 4 → slide anchor, exit lock
    'trend_acceleration_window_s': 600,  # acceleration window in seconds (10 min)
    'trend_acceleration_pct': 0.5,       # fast-move % to bypass EMA (within accel window)

    # M1: Profit Harvesting
    'harvest_enabled': True,               # master switch for M1 profit harvesting
    'harvest_profit_pct': 40.0,            # min % profit to harvest (entry - current) / entry * 100
    'harvest_min_age_mins': 30,            # min minutes since frozen before eligible
    'harvest_max_per_beat': 3,             # max positions to harvest per heartbeat
    'harvest_pressure_threshold': 0.5,     # min capacity pressure (total/max) to trigger harvest (lowered from 0.7 for Split Ledger)

    # M2: Lot Recycling
    'recycle_enabled': True,               # master switch for M2 lot recycling
    'recycle_min_premium_ratio': 2.5,      # min ratio: new_premium / avg_recycle_premium
    'recycle_premium_ceiling': 50.0,       # max premium (USD) to consider for buyback
    'recycle_max_pct': 0.50,               # max fraction of side lots to recycle at once
    'recycle_cooldown_sec': 300,           # seconds between recycle operations
    'recycle_min_lot_gain': 5,             # min net lot gain required for viability
    'recycle_free_lot_buffer': 10,         # extra lots to free beyond estimated need
    'recycle_protect_original': True,      # protect original entry position from recycling

    # M3: Asymmetry Rebalancing
    'rebalance_enabled': True,             # master switch for M3 asymmetry-aware harvesting
    'rebalance_asymmetry_threshold': 5.0,  # lots ratio threshold for extreme asymmetry boost
    'rebalance_pressure_threshold': 0.7,   # capacity pressure threshold for asymmetry boost

    # Trend Boost — aggressive safe-side selling during confirmed trends
    'trend_boost_enabled': False,          # master switch: boost safe-side lots during trend
    'trend_boost_tier1_mult': 1.3,         # safe-side lot multiplier at Tier 1 (ALERT)
    'trend_boost_tier2_mult': 1.5,         # safe-side lot multiplier at Tier 2 (GUARD)
    'trend_boost_tier3_mult': 2.0,         # safe-side lot multiplier at Tier 3 (BLOCK)

    # Lot Velocity Limiter (T2-4) — cap lot growth rate to prevent runaway accumulation
    'lot_velocity_enabled': True,           # master switch
    'lot_velocity_limit': 30,               # max lots added per velocity window
    'lot_velocity_window_mins': 30,         # rolling window in minutes

    # Gamma-Aware Lot Multiplier (T3-2) — extra lots when premium has spiked aggressively
    'gamma_aware_enabled': True,            # master switch
    'gamma_aware_max_multiplier': 1.3,      # cap on multiplier (1.3 = 30% more lots max)

    # Proactive Shift Scanner (T3-1)
    'proactive_shift_enabled': True,        # master switch

    # Consecutive CRITICAL margin escalation (T1-3)
    'consecutive_critical_threshold': 3,    # beats at CRITICAL tier before force-stop

    # Pre-Adjustment Delta Projection for Perp Hedge (T4-3)
    'perp_hedge_project_adjustment': True,  # pass projected lots/side to perp hedge
    'perp_hedge_approx_option_delta': 0.5,  # approximate delta per lot for projection

    # P1-B: Reversal cooldown configurable
    'reversal_cooldown_seconds': 0,       # 0 = use adjustment_interval × 1 (legacy), >0 = fixed seconds

    # IMP-3: Asymmetry 3-tier hard block
    'asymmetry_5to1_lot_reduction': 0.5,  # lot multiplier at 5:1 ratio (0.5 = 50% reduction)
    'asymmetry_7to1_hard_block': True,    # hard-block all sells at 7:1 ratio

    # IMP-5: Consecutive same-direction adjustment limiter
    'consecutive_dir_limit': 3,           # after N consecutive same-dir adjustments, apply lot cap
    'consecutive_dir_lot_cap_pct': 0.25,  # lot cap = initial_lots × this fraction
    'consecutive_dir_block_after': 5,     # after N adjustments, block until force-heartbeat
    'consecutive_dir_auto_resume_mins': 10,  # auto-clear block after N mins (0 = require manual force-heartbeat)

    # IMP-4: Strike shift OTM lot scaling
    'strike_shift_use_lot_scaling': False, # master switch (default off for backward compat)
    'strike_shift_otm_tier1': 1.0,         # below this % OTM → multiplier 0.25
    'strike_shift_otm_tier2': 2.0,         # below this % OTM → multiplier 0.50
    'strike_shift_otm_tier3': 3.0,         # below this % OTM → multiplier 0.75

    # IMP-9: Full delta perp mode when position cap hit
    'perp_full_delta_on_cap': True,       # switch perp to full delta mode when cap hit
    'perp_full_delta_max_lots': 0,        # 0 = auto: min(perp_hedge_max_lots, 3 × initial_lots)

    # Perpetual Futures Delta Hedge (Fix #26)
    'perp_hedge_enabled': False,           # master switch — disabled until user opts in
    'perp_hedge_mode': 'atm_only',         # 'full' = always hedge, 'atm_only' = hedge only when original strike ≈ ATM
    'perp_hedge_atm_threshold_pct': 1.5,   # ATM proximity %: perp activates when original strike is within this % of spot
    'perp_hedge_delta_threshold': 0.02,    # min |Δ| to open initial hedge (BTC units)
    'perp_hedge_ratio': 1.0,              # fraction of delta to neutralize (0.3–1.0)
    'perp_hedge_rebalance_band': 0.005,   # min |effective_Δ| to trigger rebalance
    'perp_hedge_max_lots': 50,            # hard cap on perp position size (lots)
    'perp_hedge_cooldown_sec': 30,        # minimum seconds between hedge executions
    'perp_hedge_max_flips_per_hour': 6,   # M-8: max direction flips per hour

    # FSU: Favorable Scale-Up
    'scale_enabled': False,               # master switch — disabled until user opts in
    'scale_min_decay_pct': 35.0,          # both CE and PE must have decayed this % from trigger snapshot
    'scale_lots_pct': 50.0,               # lots per side = initial_lots × this% (e.g., 50% of 10 = 5 lots)
    'scale_max_events': 3,                # max scale-up events per session
    'scale_cooldown_mins': 30,            # minutes between scale-up events
    'scale_target_premium': 100.0,        # target premium for new strikes (same unit as shift_target_premium)
    'scale_min_premium': 30.0,            # reject strikes with premium below this (liquidity/theta floor)
    # ATM Shield — Close & Retreat
    'atm_shield_enabled': True,
    'atm_shield_proximity_pct': 0.5,
    'atm_shield_target_otm_pct': 1.0,
    'atm_shield_loss_split_aggressor': 0.3,
    'atm_shield_max_per_session': 3,
    'atm_shield_cooldown_mins': 10,

    # Breakeven Engine — real-time portfolio breakeven awareness
    'breakeven_control_enabled': True,   # master switch
    'breakeven_warning_pct': 2.0,         # distance % → Warning zone (multiplier ramps 1.0→1.3)
    'breakeven_danger_pct': 1.0,          # distance % → Danger zone (multiplier ramps 1.3→2.0)
    'breakeven_critical_pct': 0.5,        # distance % → Critical zone (multiplier ramps 2.0→max)
    'breakeven_aggression_max': 3.0,      # max multiplier at Critical zone boundary
    'breakeven_scan_range_pct': 5.0,      # min scan width as % of spot (floor; auto-expands)
    'max_combined_lot_multiplier': 3.0,   # cap on combined gamma × breakeven × trend multiplier
    'breakeven_narrow_band_threshold': 5.0,  # warn when band width < this % of spot
    # Breakeven DTE-aware controls
    'breakeven_dte_threshold_mult': 1.0,     # √T multiplier (1.0 = disabled, backward-compatible)
    'breakeven_dte_aggression_damp': 0.0,    # manual lot boost reduction in WARNING/DANGER [0,0.4]
    'breakeven_dte_vol_regime_damp': 0.2,    # auto-damp when vol regime is ELEVATED/HIGH
    'breakeven_dte_pnl_clamp_pct': 1.5,      # reset dte_scale when |pnl|/premium > this ratio
    'breakeven_tv_credit_factor': 0.0,       # reserved (Tier 3 — not yet active)
    'breakeven_high_risk_mode': False,        # override all damps; auto-expires via session field
    'breakeven_critical_lot_ceiling': 4.0,   # ceiling when zone=CRITICAL (overrides combined cap)

    # Gamma Detector Engine — portfolio curvature scanning
    'gamma_detector_enabled': True,           # master switch
    'gamma_step_pct': 0.5,                    # step size as % of spot for second-difference
    'gamma_scan_steps': 40,                   # steps to scan outward in each direction
    'gamma_warning_distance_pct': 3.0,        # nearest gamma boundary within 3% → WARNING
    'gamma_danger_distance_pct': 1.5,         # nearest gamma boundary within 1.5% → DANGER
    'gamma_detect_epsilon': 0.3,              # abs threshold for detecting a kink (USD)
    'gamma_severity_multiplier_enabled': True,   # enable trading impact (lot multiplier in DANGER zone)
    'gamma_severity_max_multiplier': 1.5,     # max lot multiplier applied in DANGER zone
    'gamma_severity_proportional': True,      # F6: smooth distance-proportional curve (False = legacy binary)
    'gamma_severity_warning_mult': 1.1,       # F6: lot multiplier applied in WARNING zone
    'gamma_severity_shift_distance_mult': 1.2,  # F6: widen shift distance when in DANGER zone

    # Feature 9: Data Confidence Gate — scales lot sizing when market data quality degrades
    'data_confidence_enabled': True,          # master switch; False = multiplier always 1.0 (no effect)
    'confidence_stale_penalty': 0.25,         # subtracted from confidence per stale premium side (CE or PE)
    'confidence_ws_failure_penalty': 0.04,    # subtracted per consecutive WS emission failure
    'confidence_min_floor': 0.20,             # confidence never drops below this (20% = 1/5 max lots)

    # Guardian — heartbeat-level integrity checks
    'guardian_enabled': True,              # master switch for MMM Guardian
    'guardian_max_close_per_beat': 50,     # max lots bought back per single heartbeat (all mechanisms combined)
    'guardian_max_beat_sec': 120,          # max wall-clock seconds for a single heartbeat
    'guardian_side_wipeout_floor': 10,     # side must have >N lots before guardian flags a side-to-0 wipeout

    # Shift-Time Recycle per-beat cap
    'shift_recycle_max_per_beat': 10,      # max lots to close per heartbeat during shift-time recycle

    # Delta-neutral lot matching inflation cap
    'shift_match_max_inflate_mult': 1.5,   # cap inflation: lots = min(opposite_lots, formula_lots × this)

    # Multi-Expiry DTE Presets
    'dte_category': '',                    # '0DTE', '5DTE', 'SHORT_WINDOW' — set at session creation
    'total_dte_hours': 0.0,                # total hours from creation to expiry (computed)
    'session_window_hours': 0.0,           # Short Window: 0 = disabled, >0 = auto-exit after N hours
    'global_max_loss': 50000.0,            # aggregate max loss across all active sessions ($)

    # Adaptive Tuning Engine — parameter optimization per market regime
    # See tasks/MMM_ADAPTIVE_TUNING_PLAN.md for full design
    'adaptive_mode': 'manual',             # 'manual' | 'preset' | 'adaptive'
    'adaptive_preset': 'strangle',         # 'strangle' | 'straddle' | 'short_window'
    'adaptive_dry_run': False,             # compute changes but only log, don't apply
    'atm_shield_partial_pct': 1.0,        # fraction of lots to close on shield fire (1.0 = full)
    'atm_shield_defer_resell_beats': 0,   # beats to wait before re-sell after shield close (0 = immediate)

    # Auto-Replenish Leg — re-enter empty side instead of pausing
    'replenish_enabled': True,             # master switch — ON by default
    'replenish_lot_mode': 'match_active',  # 'match_active' | 'initial'
    'replenish_max_per_session': 10,       # cap to prevent infinite re-entry
    'replenish_cooldown_sec': 300,         # 5 min between replenishments
    'replenish_min_premium': 30.0,         # reject strikes with premium below this ($)
    'replenish_retry_max': 3,              # fast-path retries within one _process_replenish call
    'replenish_retry_delay_sec': 2,        # seconds between retry attempts
    'replenish_max_reprice_attempts': 2,   # reprice cycles per smart_execute call (cap per retry)

    # ── Straddle Roll ──
    'straddle_roll_enabled':            False,  # off by default; preset enables it
    'straddle_roll_trigger_pct':        1.0,
    'straddle_roll_max_per_session':    3,
    'straddle_roll_cooldown_mins':      15,
    'straddle_roll_emergency_mult':     2.0,    # bypass cooldown at N× trigger distance
    'straddle_roll_min_time_to_expiry': 90,
    'straddle_roll_min_credit_pct':     0.30,
    'straddle_roll_slippage_factor':    0.03,
    'straddle_roll_loss_abort_mult':    3.0,
    'straddle_roll_lot_scale':          1.0,
    'straddle_roll_iv_spike_mult':      2.0,
    'straddle_roll_price_max_age_secs': 5,   # Gate 9 freshness check (was hardcoded)
    '_straddle_roll_trigger_pts':       0,   # computed at session startup

    # Price Guard (STRADDLE_WITH_ADJUSTMENT real-time monitoring)
    'price_guard_enabled': True,
    'price_guard_interval_secs': 5,
    'price_guard_buffer_pts': 50,
    'price_guard_cooldown_secs': 30,
    'straddle_roll_max_spread_pct': 15.0,  # reject roll if avg bid-ask spread > this %

    # Auto-Reconciliation — periodic drift check between bot state and exchange
    # Runs every N heartbeats; emits SAFETY_ALERT on mismatch (does not self-heal).
    # 0 = disabled.  Default 50 beats ≈ 25 min at 30s heartbeat interval.
    'auto_recon_interval_beats':        50,

    # ── Reverse Mode ──
    'reverse_enabled': False,
    'reverse_capacity_pct': 10.0,
    'reverse_num_slots': 5,
    'reverse_slot_size_override': 0,
    'reverse_max_adjustments': 3,
    'reverse_time_start': '',
    'reverse_time_end': '',
    'reverse_duration_mins': 120,
    'reverse_mode_type': 'strict_alternating',
    'reverse_cooldown_mins': 5,
    'reverse_max_loss': 100.0,
    'reverse_close_at_threshold': 8.0,
    'reverse_unhedged_emergency_loss': 200.0,
}

# Which parameters can be changed while algo is running
HOT_RELOAD_PARAMS = {
    'dte_category', 'total_dte_hours', 'session_window_hours',
    'adjustment_interval', 'min_trigger_move', 'min_trigger_dollar', 'min_frozen_trigger_dollar', 'shift_threshold',
    'shift_threshold_pct', 'shift_target_premium', 'shift_premium_tolerance', 'shift_match_opposite_lots',
    'pre_sell_shift_enabled', 'shift_fallback_enabled', 'shift_fallback_min_premium', 'shift_cooldown_sec', 'dangerous_mode',
    'close_at_threshold', 'close_at_watch_interval', 'close_at_max_per_beat',
    'close_at_watcher_force_enabled', 'close_at_watch_hours_before_expiry', 'close_at_watch_near_expiry_interval',
    'premium_buffer_pct', 'max_lots_per_side',
    # Split Ledger
    'max_total_exposure',
    'shift_recycle_enabled', 'shift_recycle_premium_floor', 'shift_recycle_max_pct',
    'shift_recycle_floor_ratio', 'shift_recycle_pressure_threshold',
    'max_adjustments', 'max_loss_amount', 'stop_adjustment_mins',
    'auto_close_mins', 'cooldown_on_reversal', 'whipsaw_limit',
    'trailing_stop_pct', 'theta_acceleration_window',
    # Adaptive Whipsaw Guard
    'whipsaw_window_mins', 'whipsaw_spot_move_pct',
    'whipsaw_caution_score', 'whipsaw_restrict_score', 'whipsaw_cooldown_score',
    'adaptive_interval_enabled',
    'wind_down_enabled', 'wind_down_hours_before_expiry',
    'wind_down_buyback_pct', 'wind_down_close_threshold',
    'wind_down_min_lots_to_keep', 'wind_down_floor_action',
    'wind_down_on_atm',
    # Margin Guardian
    'margin_monitor_enabled', 'margin_green_pct', 'margin_yellow_pct',
    'margin_orange_pct', 'margin_red_pct', 'margin_critical_pct',
    'margin_target_pct',
    # Regime Controls
    'regime_enabled',
    'vol_regime_enabled', 'vol_iv_spike_pct', 'vol_rv_threshold',
    'vol_lookback_beats', 'vol_rv_window', 'vol_regime_action',
    'vol_regime_cooldown_beats',
    'gamma_cap_enabled', 'gamma_soft_limit', 'gamma_hard_limit',
    'gamma_emergency_limit', 'gamma_near_expiry_multiplier',
    'gamma_side_imbalance_ratio', 'gamma_dte_relax_hours',
    'gamma_dte_hedge_multiplier', 'gamma_rescue_window_minutes',
    'gamma_directional_min_pct',
    'trend_enabled', 'trend_tier1_pct', 'trend_tier2_pct',
    'trend_tier3_pct', 'trend_tier4_pct', 'trend_tier1_lot_reduction',
    'trend_move_pct', 'trend_retrace_pct',
    'trend_ema_period', 'trend_ema_slope_threshold', 'trend_action',
    'trend_reset_beats', 'trend_plateau_reset_beats', 'trend_t4_timeout_beats',
    'trend_acceleration_window_s', 'trend_acceleration_pct',
    # Perpetual Futures Delta Hedge
    'perp_hedge_enabled', 'perp_hedge_mode', 'perp_hedge_atm_threshold_pct',
    'perp_hedge_delta_threshold', 'perp_hedge_ratio',
    'perp_hedge_rebalance_band', 'perp_hedge_max_lots', 'perp_hedge_cooldown_sec',
    'perp_hedge_max_flips_per_hour',
    # Lot Lifecycle (M1/M2/M3)
    'harvest_enabled', 'harvest_profit_pct', 'harvest_min_age_mins',
    'harvest_max_per_beat', 'harvest_pressure_threshold',
    'recycle_enabled', 'recycle_min_premium_ratio', 'recycle_premium_ceiling',
    'recycle_max_pct', 'recycle_cooldown_sec', 'recycle_min_lot_gain',
    'recycle_free_lot_buffer', 'recycle_protect_original',
    'rebalance_enabled', 'rebalance_asymmetry_threshold', 'rebalance_pressure_threshold',
    # Trend Boost
    'trend_boost_enabled', 'trend_boost_tier1_mult', 'trend_boost_tier2_mult', 'trend_boost_tier3_mult',
    # Lot Velocity Limiter (T2-4)
    'lot_velocity_enabled', 'lot_velocity_limit', 'lot_velocity_window_mins',
    # Gamma-Aware Lot Multiplier (T3-2)
    'gamma_aware_enabled', 'gamma_aware_max_multiplier',
    # Proactive Shift (T3-1)
    'proactive_shift_enabled',
    # Consecutive CRITICAL margin escalation (T1-3)
    'consecutive_critical_threshold',
    # Perp projection (T4-3)
    'perp_hedge_project_adjustment', 'perp_hedge_approx_option_delta',
    # P1-B: Reversal cooldown
    'reversal_cooldown_seconds',
    # IMP-3: Asymmetry tiers
    'asymmetry_5to1_lot_reduction', 'asymmetry_7to1_hard_block',
    # IMP-5: Consecutive direction limiter
    'consecutive_dir_limit', 'consecutive_dir_lot_cap_pct', 'consecutive_dir_block_after',
    'consecutive_dir_auto_resume_mins',
    # IMP-4: Strike shift OTM scaling
    'strike_shift_use_lot_scaling', 'strike_shift_otm_tier1', 'strike_shift_otm_tier2',
    'strike_shift_otm_tier3',
    # IMP-9: Full delta perp on cap
    'perp_full_delta_on_cap', 'perp_full_delta_max_lots',
    # AUDIT FIX BUG3: close_at_use_bid was missing from hot-reload
    'close_at_use_bid',
    # FSU: Favorable Scale-Up
    'scale_enabled', 'scale_min_decay_pct', 'scale_lots_pct',
    'scale_max_events', 'scale_cooldown_mins', 'scale_target_premium',
    'scale_min_premium',
    # ATM Shield
    'atm_shield_enabled', 'atm_shield_proximity_pct', 'atm_shield_target_otm_pct',
    'atm_shield_loss_split_aggressor', 'atm_shield_max_per_session',
    'atm_shield_cooldown_mins',
    # Multi-Expiry
    'global_max_loss',
    # Guardian
    'guardian_enabled', 'guardian_max_close_per_beat', 'guardian_max_beat_sec',
    'guardian_side_wipeout_floor',
    # Shift-Time Recycle per-beat cap
    'shift_recycle_max_per_beat',
    # Delta-neutral lot matching inflation cap
    'shift_match_max_inflate_mult',
    # Breakeven Engine
    'breakeven_control_enabled', 'breakeven_warning_pct', 'breakeven_danger_pct',
    'breakeven_critical_pct', 'breakeven_aggression_max', 'breakeven_scan_range_pct',
    'max_combined_lot_multiplier', 'breakeven_narrow_band_threshold',
    # Breakeven DTE-aware controls
    'breakeven_dte_threshold_mult', 'breakeven_dte_aggression_damp',
    'breakeven_dte_vol_regime_damp', 'breakeven_dte_pnl_clamp_pct',
    'breakeven_tv_credit_factor', 'breakeven_high_risk_mode',
    'breakeven_critical_lot_ceiling',
    # Gamma Detector Engine (gamma_severity_multiplier_enabled is NOT hot-reloadable)
    'gamma_detector_enabled', 'gamma_step_pct', 'gamma_scan_steps',
    'gamma_warning_distance_pct', 'gamma_danger_distance_pct', 'gamma_detect_epsilon',
    'gamma_severity_max_multiplier',
    # Adaptive Tuning Engine
    'adaptive_mode', 'adaptive_preset', 'adaptive_dry_run',
    'atm_shield_partial_pct', 'atm_shield_defer_resell_beats',
    # Auto-Replenish Leg
    'replenish_enabled', 'replenish_lot_mode', 'replenish_max_per_session',
    'replenish_cooldown_sec', 'replenish_min_premium',
    'replenish_retry_max', 'replenish_retry_delay_sec', 'replenish_max_reprice_attempts',
    # Straddle Roll
    'straddle_roll_enabled', 'straddle_roll_trigger_pct',
    'straddle_roll_max_per_session', 'straddle_roll_cooldown_mins',
    'straddle_roll_emergency_mult', 'straddle_roll_min_time_to_expiry',
    'straddle_roll_min_credit_pct', 'straddle_roll_slippage_factor',
    'straddle_roll_loss_abort_mult', 'straddle_roll_lot_scale',
    'straddle_roll_iv_spike_mult',
    'straddle_roll_price_max_age_secs',
    # Price Guard
    'price_guard_enabled', 'price_guard_interval_secs',
    'price_guard_buffer_pts', 'price_guard_cooldown_secs',
    'straddle_roll_max_spread_pct',
    # Reverse Mode
    'reverse_enabled', 'reverse_capacity_pct', 'reverse_num_slots',
    'reverse_slot_size_override', 'reverse_max_adjustments',
    'reverse_time_start', 'reverse_time_end', 'reverse_duration_mins',
    'reverse_mode_type', 'reverse_cooldown_mins', 'reverse_max_loss',
    'reverse_close_at_threshold', 'reverse_unhedged_emergency_loss',
}


def create_session(
    session_id: str = None,
    mode: str = 'fresh',
    params: Dict = None,
) -> Dict[str, Any]:
    """
    Create a new MMM session with full state.

    Maps to MONEY_POWER_CALCULATION_LOGIC.md:
      - Section 2: State
      - Section 3: Initialization
      - Section 19: User Parameters

    Args:
        session_id: Optional session ID (auto-generated if None)
        mode: 'fresh' (auto-find strikes) or 'import' (existing positions)
        params: User-provided parameters (merged with defaults)

    Returns:
        Complete session dictionary
    """
    merged_params = {**DEFAULT_PARAMS}
    if params:
        merged_params.update(params)

    # Multi-Expiry: Apply DTE preset if specified
    dte_category = merged_params.get('dte_category', '')
    if dte_category:
        from .mmm_dte_presets import (apply_preset, STRADDLE_WITH_ADJUSTMENT_CATEGORY,
                                       SHORT_STRADDLE_CATEGORY)
        user_params = params or {}
        if dte_category in (STRADDLE_WITH_ADJUSTMENT_CATEGORY, SHORT_STRADDLE_CATEGORY):
            # Dynamic preset: must read expiry from raw user params BEFORE the
            # DEFAULT_PARAMS reset, because DEFAULT_PARAMS has expiry=''.
            # Build preset first, then layer: DEFAULT_PARAMS < preset < user_params.
            from .mmm_dte_presets import compute_total_dte_hours, build_straddle_adjustment_preset
            _expiry = user_params.get('expiry', '')
            if not _expiry:
                raise ValueError("STRADDLE_WITH_ADJUSTMENT preset requires 'expiry' param")
            _hours = compute_total_dte_hours(
                _expiry,
                user_params.get('expiry_hour_utc', 12),
                user_params.get('expiry_minute_utc', 0),
            )
            _preset = build_straddle_adjustment_preset(_hours)
            merged_params = {**DEFAULT_PARAMS}
            merged_params.update(_preset)       # preset overrides DEFAULT_PARAMS
            merged_params.update(user_params)   # user overrides preset
            merged_params['dte_category'] = '0DTE'
            merged_params['_preset_source'] = STRADDLE_WITH_ADJUSTMENT_CATEGORY
        else:
            merged_params = {**DEFAULT_PARAMS}
            merged_params = apply_preset(merged_params, dte_category)
            merged_params.update(user_params)
            merged_params['dte_category'] = dte_category

    # Multi-Expiry: Compute total_dte_hours at creation time
    expiry_str = merged_params.get('expiry', '')
    if expiry_str and not merged_params.get('total_dte_hours'):
        from .mmm_dte_presets import compute_total_dte_hours
        total_dte_hours = compute_total_dte_hours(
            expiry_str,
            merged_params.get('expiry_hour_utc', 12),
            merged_params.get('expiry_minute_utc', 0),
        )
        merged_params['total_dte_hours'] = max(0.0, total_dte_hours)

    # C-4 fix: enforce expiry is present — a session without expiry is a zombie
    if not merged_params.get('expiry'):
        raise ValueError("params['expiry'] is required to create a session")

    # C-6 fix: guard against overwriting an existing session
    if session_id is not None:
        from .mmm_storage import get_storage as _get_storage
        _existing = _get_storage().get_session(session_id)
        if _existing is not None:
            raise RuntimeError(
                f"Session '{session_id}' already exists. "
                "Use resume, not create_session()."
            )

    if session_id is None:
        # Generate informative session ID: mmm18feb26-1
        expiry = merged_params.get('expiry', '')
        if expiry:
            # Parse expiry: 19022026 → 19feb26
            try:
                day = expiry[:2]
                month_num = expiry[2:4]
                year = expiry[6:8] if len(expiry) >= 8 else expiry[4:6]
                month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                             'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                month = month_names[int(month_num) - 1]
                expiry_str = f"{day}{month}{year}"
            except (ValueError, IndexError):
                # Fallback to old format if parsing fails
                expiry_str = uuid.uuid4().hex[:6]
            
            # Count existing sessions for this expiry (to get next sequence number)
            # CRITICAL: Must guarantee unique ID — never overwrite an existing session
            from .mmm_storage import get_storage
            storage = get_storage()
            try:
                all_sessions = storage.list_sessions()
                same_expiry = [s for s in all_sessions if s.get('params', {}).get('expiry') == expiry]
                count = len(same_expiry) + 1
            except Exception as e:
                log.warning(f"Failed to count existing sessions for expiry {expiry}: {e}")
                count = 1
            
            # Collision guard: keep incrementing until we find an unused ID
            candidate_id = f"mmm{expiry_str}-{count}"
            try:
                existing = storage.get_session(candidate_id)
                while existing is not None:
                    count += 1
                    candidate_id = f"mmm{expiry_str}-{count}"
                    existing = storage.get_session(candidate_id)
            except Exception as e:
                log.warning(f"Collision check failed: {e}, using uuid fallback")
                # Fix #20: Use 8 hex chars (4B combinations) instead of 4 (65K) to prevent collision
                candidate_id = f"mmm{expiry_str}-{uuid.uuid4().hex[:8]}"
            
            session_id = candidate_id
        else:
            # No expiry provided, fallback to random
            short_uuid = uuid.uuid4().hex[:6]
            session_id = f"mmm_{short_uuid}"

    session = {
        'session_id': session_id,
        'mode': mode,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),

        # Per-side state (initialized empty, populated on entry)
        'ce': create_side_state('CE'),
        'pe': create_side_state('PE'),

        # Global state (Section 2)
        'last_aggressor': 'NONE',
        'adjustment_count': 0,
        'adjustment_history': [],   # [{side, lots_sold, premium, strike, timestamp, type}]
        'realized_pnl': 0.0,
        'total_premium_collected': 0.0,
        'ce_premium_collected': 0.0,
        'pe_premium_collected': 0.0,
        'total_fees': 0.0,
        'strategy_status': 'IDLE',  # IDLE → RUNNING → PAUSED/BOTH_SIDES_UP → STOPPED
                                     # RUNNING/PAUSED/BOTH_SIDES_UP → EXITING → STOPPED (graceful exit)

        # Manual position reductions (user-triggered buybacks)
        'manual_reductions': [],     # [{side, lots, strike, avg_price, realized_pnl, timestamp}]
        'manual_reduction_pnl': 0.0, # cumulative realized P&L from manual reductions

        # P&L tracking
        'unrealized_pnl': 0.0,
        'peak_pnl': 0.0,

        # P&L Attribution (T2-5) — breakdown by source
        'pnl_initial': 0.0,       # P&L from closing original entry positions
        'pnl_adjustment': 0.0,    # P&L from closing adjustment-filled positions
        'pnl_harvest': 0.0,       # P&L from M1 harvesting
        'pnl_recycle': 0.0,       # P&L from M2 Phase A buybacks (net: success only)
        'pnl_perp': 0.0,          # Mirror of perp_hedge.realized_pnl

        # Reversal tracking
        'reversal_count': 0,
        'cooldown_active': False,
        'cooldown_until': None,

        # Strike shift tracking
        'shift_count': 0,
        'close_at_5_count': 0,

        # Timing
        'entry_time': None,
        # M-17 fix: Initialize to creation time so callers don't crash on None
        'last_heartbeat': datetime.now(timezone.utc).isoformat(),
        'next_heartbeat': None,
        # C-5 fix: compute expiry_time from params['expiry'] at creation
        'expiry_time': None,      # populated below
        'session_deadline_utc': None,  # Short Window: set when monitor starts

        # Parameters
        'params': merged_params,

        # Heartbeat history for P&L chart
        'pnl_history': [],  # [{timestamp, total_pnl, realized, unrealized, ce_premium, pe_premium}]

        # Fill ledger — single source of truth for realized P&L (mmm_pnl_core)
        '_fill_ledger': [],

        # Error tracking
        'last_error': None,
        'error_count': 0,

        # H-4 fix: monitor generation counter — incremented on every monitor
        # start/watchdog restart. Used by _save_session() to reject stale saves
        # from old monitor threads that haven't exited yet.
        '_monitor_generation': 0,

        # Regime Controls — runtime state (persisted for crash recovery)
        '_vol_regime': 'NORMAL',
        '_vol_regime_since': None,
        '_vol_iv_history': [],       # ring buffer [(timestamp, iv_avg), ...]
        '_vol_spot_history': [],     # ring buffer [(timestamp, spot), ...]
        '_vol_regime_beats_below': 0,
        '_vol_iv_change_pct': 0.0,
        '_vol_rv_annualized': 0.0,
        '_vol_regime_score': 0.0,

        '_portfolio_gamma': 0.0,
        '_portfolio_dollar_gamma': 0.0,
        '_ce_dollar_gamma': 0.0,
        '_pe_dollar_gamma': 0.0,
        '_gamma_regime': 'NORMAL',
        '_gamma_history': [],        # ring buffer [(timestamp, dollar_gamma), ...]
        '_gamma_blocked_count': 0,
        '_gamma_data_incomplete': False,

        '_trend_regime': 'NORMAL',
        '_trend_tier': 0,                # Tiered trend level: 0=none, 1=alert, 2=guard, 3=block, 4=wind_down
        '_trend_direction': 'none',      # 'up', 'down', 'none'
        '_trend_since': None,
        '_trend_anchor_spot': 0.0,
        '_trend_high': 0.0,
        '_trend_low': 0.0,
        '_trend_calm_beats': 0,
        '_trend_plateau_beats': 0,   # BUG-C2 fix: regime reads these
        '_trend_t4_beats': 0,        # BUG-C2 fix: regime reads these
        '_trend_ema': 0.0,
        '_trend_ema_prev': 0.0,
        '_trend_ema_slope': 0.0,
        '_trend_move_pct': 0.0,
        '_trend_acceleration_move_pct': 0.0,  # Rolling fast-move %

        '_regime_action': 'NORMAL',

        # Session Analytics (institutional-level exposure tracking)
        'analytics': {
            'session_start_time': None,
            'session_end_time': None,
            'session_duration_seconds': 0,
            
            # Initial exposure
            'initial_ce_lots': 0,
            'initial_pe_lots': 0,
            
            # Peak exposure (maximum at any point)
            'max_ce_lots': 0,
            'max_pe_lots': 0,
            'max_combined_lots': 0,
            'peak_risk_timestamp': None,
            
            # Cumulative trading volume
            'total_ce_lots_traded': 0,  # Total CE lots sold (initial + all adjustments)
            'total_pe_lots_traded': 0,  # Total PE lots sold (initial + all adjustments)
            'total_combined_lots_traded': 0,
            
            # Exit statistics
            'auto_close_events': [],  # [{timestamp, side, strike, lots, reason}]
            'auto_close_total_lots': 0,
            'manual_close_events': [],  # [{timestamp, side, strike, lots}]
            'manual_close_total_lots': 0,
            
            # Adjustment breakdown
            'adjustment_events_by_side': {'ce': 0, 'pe': 0},
            'adjustment_events_by_type': {
                'standard': 0,
                'reversal': 0,
                'first_reversal': 0,
            },
            
            # Risk events
            'reversal_timestamps': [],
            'shift_timestamps': [],
            'both_sides_up_timestamps': [],
            'safety_trigger_events': [],  # [{timestamp, type, level}]
            
            # P&L milestones
            'time_to_first_profit': None,  # seconds from start
            'time_to_peak_pnl': None,      # seconds from start
            'max_drawdown_from_peak': 0,
            'max_drawdown_timestamp': None,
            
            # Greeks tracking
            'max_abs_delta': 0,
            'max_abs_delta_timestamp': None,
        },

        # Reverse Mode — isolated state namespace
        '_reverse': {
            'active': False,
            'enabled_at': None,
            'disabled_at': None,
            'disable_reason': None,
            'slots_used': 0,
            'slots_remaining': 5,
            'last_reverse_side': None,
            'last_reverse_at': None,
            'adjustment_count': 0,
            'total_lots': 0,
            'positions': [],
            'total_premium_collected': 0.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'net_pnl': 0.0,
            'delta_exposure': 0.0,
            'history': [],
        },

        # Perpetual Futures Delta Hedge (Fix #26)
        'perp_hedge': {
            'lots': 0,               # signed; positive = long, negative = short
            'avg_entry': 0.0,        # average fill price of current position
            'realized_pnl': 0.0,     # cumulative realized P&L
            'unrealized_pnl': 0.0,   # mark-to-market P&L on current position
            'last_hedge_time': None,  # ISO8601 timestamp of last execution
            'total_hedge_count': 0,   # total executions this session
            'last_flip_at': None,     # timestamp of last long↔short flip
            'target_lots': 0,         # target lots from last computation
            'last_delta': 0.0,        # portfolio_delta at last hedge
            # M-8 fix: sliding window of direction flip timestamps for rate limiting
            'flip_timestamps': [],    # ISO timestamps of the last N flips (pruned to 1h)
        },
    }

    # C-5 fix: compute expiry_time from params['expiry'] at session creation
    expiry_str = merged_params.get('expiry', '')
    if expiry_str:
        try:
            d, m, y_full = int(expiry_str[0:2]), int(expiry_str[2:4]), int(expiry_str[4:8])
            session['expiry_time'] = datetime(
                y_full, m, d,
                merged_params.get('expiry_hour_utc', 12),
                merged_params.get('expiry_minute_utc', 0),
                0, tzinfo=timezone.utc
            ).isoformat()
        except (ValueError, IndexError) as _e:
            log.warning(f"Failed to parse expiry string '{expiry_str}' into expiry_time: {_e}")

    return session


def initialize_side_from_entry(
    session: Dict,
    side: str,
    strike: float,
    premium: float,
    lots: int,
) -> Dict:
    """
    Initialize a side with entry data (after auto-find or import).

    Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 3: Initial State After Entry.

    Args:
        session: The session dictionary
        side: 'ce' or 'pe'
        strike: Entry strike price
        premium: Fill premium per lot
        lots: Number of lots sold

    Returns:
        Updated session (mutated in place)
    """
    side_key = side.lower()
    # L-6 fix: Guard against silently overwriting an already-initialized side
    existing = session.get(side_key, {})
    if existing.get('original_lots', 0) > 0:
        log.warning(
            f"initialize_side_from_entry: {side_key.upper()} already has "
            f"{existing['original_lots']} lots — skipping re-init"
        )
        return session
    session[side_key] = create_side_state(
        side=side.upper(),
        original_lots=lots,
        original_premium=premium,
        original_strike=strike,
    )
    session[side_key]['trigger_snapshot'] = {strike_key_fn(strike): premium}
    session[side_key] = recompute_side_lots(session[side_key])

    return session


def _backfill_side_premiums(session: Dict):
    """
    Compute ce_premium_collected / pe_premium_collected from existing session data
    when they were not tracked (sessions created before this feature).

    Sources (in order of addition to total_premium_collected):
      1. Initial entry:  ce.entry_fill_price * original_lots * 0.001
      2. Adjustments:    adjustment_history entries (side + premium_collected)
    """
    LOT = 0.001
    ce = session.get('ce', {})
    pe = session.get('pe', {})
    original_lots = session.get('lots', 0) or ce.get('original_lots', 0) or 0

    ce_prem = (ce.get('entry_fill_price') or ce.get('original_premium', 0)) * original_lots * LOT
    pe_prem = (pe.get('entry_fill_price') or pe.get('original_premium', 0)) * original_lots * LOT

    for entry in session.get('adjustment_history', []):
        side = (entry.get('side') or '').upper()
        collected = entry.get('premium_collected', 0) or 0
        if side == 'CE':
            ce_prem += collected
        elif side == 'PE':
            pe_prem += collected

    return round(ce_prem, 6), round(pe_prem, 6)


def get_session_summary(session: Dict) -> Dict:
    """
    Get a compact summary of the session for WebUI display.

    Returns:
        Summary dictionary with key metrics
    """
    ce = session.get('ce', {})
    pe = session.get('pe', {})

    _ce_prem_stored = session.get('ce_premium_collected') or 0
    _pe_prem_stored = session.get('pe_premium_collected') or 0
    if not _ce_prem_stored and not _pe_prem_stored and session.get('total_premium_collected', 0) > 0:
        _ce_prem_stored, _pe_prem_stored = _backfill_side_premiums(session)

    # BUG-C3 fix: use canonical P&L formula (includes perp + reverse)
    from .mmm_pnl_core import compute_current_total_pnl
    _net_pnl = round(compute_current_total_pnl(session), 6)

    return {
        'session_id': session.get('session_id'),
        'status': session.get('strategy_status', 'IDLE'),
        'mode': session.get('mode', 'fresh'),
        'created_at': session.get('created_at'),
        'entry_time': session.get('entry_time'),

        # CE summary
        'ce_strike': ce.get('active_strike', 0),
        'ce_original_lots': ce.get('original_lots', 0),
        'ce_active_lots': ce.get('active_lots', 0),
        'ce_total_lots': ce.get('total_lots', 0),
        'ce_frozen_lots': ce.get('frozen_total_lots', 0),

        # PE summary
        'pe_strike': pe.get('active_strike', 0),
        'pe_original_lots': pe.get('original_lots', 0),
        'pe_active_lots': pe.get('active_lots', 0),
        'pe_total_lots': pe.get('total_lots', 0),
        'pe_frozen_lots': pe.get('frozen_total_lots', 0),

        # Globals
        'last_aggressor': session.get('last_aggressor', 'NONE'),
        'adjustment_count': session.get('adjustment_count', 0),
        'reversal_count': session.get('reversal_count', 0),
        'shift_count': session.get('shift_count', 0),
        'close_at_5_count': session.get('close_at_5_count', 0),

        # P&L
        'total_premium_collected': session.get('total_premium_collected', 0),
        'ce_premium_collected': _ce_prem_stored,
        'pe_premium_collected': _pe_prem_stored,
        'realized_pnl': session.get('realized_pnl', 0),
        'unrealized_pnl': session.get('unrealized_pnl', 0),
        'total_fees': session.get('total_fees', 0),
        'net_pnl': _net_pnl,
        'peak_pnl': session.get('peak_pnl', 0),

        # Params (hot-reload visible)
        'adjustment_interval': session.get('params', {}).get('adjustment_interval', 300),
        'last_heartbeat': session.get('last_heartbeat'),
        'next_heartbeat': session.get('next_heartbeat'),

        # Expiry info
        'expiry': session.get('params', {}).get('expiry', ''),   # DDMMYYYY
        'expiry_time': session.get('expiry_time'),                # ISO UTC string
        'dte_category': session.get('params', {}).get('dte_category', ''),
        'session_deadline_utc': session.get('session_deadline_utc'),
        'session_window_hours': session.get('params', {}).get('session_window_hours', 0),

        # Pause context (if paused)
        '_paused_reason': session.get('_paused_reason', ''),

        # Health & regime (for card badges)
        '_health_grade': session.get('_health_grade', ''),
        '_gamma_regime': session.get('_gamma_regime', 'NORMAL'),
        '_gamma_zone': (session.get('_gamma_result') or {}).get('gamma_zone', 'SAFE'),
        '_data_confidence': session.get('_data_confidence'),
    }
