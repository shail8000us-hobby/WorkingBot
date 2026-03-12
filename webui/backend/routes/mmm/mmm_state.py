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
    'shift_threshold': 50.0,            # min premium to sell at current strike
    'shift_target_premium': 100.0,      # target premium for new strike on shift
    'close_at_threshold': 5.0,          # close positions at this premium or below
    'close_at_use_bid': True,           # use bid price (not mark) for close_at_5 checks — more accurate for illiquid options
    'premium_buffer_pct': 0.05,         # 5% extra lots for slippage
    'max_lots_per_side': 100,           # maximum total lots per CE or PE
    # Split Ledger Phase 1
    'max_total_exposure': 0,            # absolute ceiling on active+frozen lots per side. 0 = auto (2× max_lots_per_side)
    # Split Ledger Phase 2: Shift-Time Recycle
    'shift_recycle_enabled': False,         # proactive cleanup at shift time. Start disabled.
    'shift_recycle_premium_floor': 60.0,    # only close frozen positions with premium < this. 0 = dynamic mode
    'shift_recycle_max_pct': 1.0,           # max fraction of frozen lots to close per shift (0.0-1.0)
    'shift_recycle_floor_ratio': 0.40,      # when premium_floor<=0, floor = new_strike_premium × this ratio
    'max_adjustments': 500,             # maximum adjustment events
    'max_loss_amount': 5000.0,          # hard stop P&L threshold
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
    'shift_cooldown_sec': 120,             # minimum seconds between consecutive strike shifts

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
    'atm_shield_enabled': False,
    'atm_shield_proximity_pct': 0.5,
    'atm_shield_target_otm_pct': 1.0,
    'atm_shield_loss_split_aggressor': 0.3,
    'atm_shield_max_per_session': 3,
    'atm_shield_cooldown_mins': 10,
}

# Which parameters can be changed while algo is running
HOT_RELOAD_PARAMS = {
    'adjustment_interval', 'min_trigger_move', 'shift_threshold',
    'shift_threshold_pct', 'shift_target_premium', 'shift_match_opposite_lots',
    'shift_cooldown_sec',
    'close_at_threshold',
    'premium_buffer_pct', 'max_lots_per_side',
    # Split Ledger
    'max_total_exposure',
    'shift_recycle_enabled', 'shift_recycle_premium_floor', 'shift_recycle_max_pct',
    'shift_recycle_floor_ratio',
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
    'trend_enabled', 'trend_tier1_pct', 'trend_tier2_pct',
    'trend_tier3_pct', 'trend_tier4_pct', 'trend_tier1_lot_reduction',
    'trend_move_pct', 'trend_retrace_pct',
    'trend_ema_period', 'trend_ema_slope_threshold', 'trend_action',
    'trend_reset_beats', 'trend_acceleration_window_s', 'trend_acceleration_pct',
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
        'total_fees': 0.0,
        'strategy_status': 'IDLE',  # IDLE → RUNNING → PAUSED/BOTH_SIDES_UP → STOPPED

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
        'expiry_time': None,  # populated below

        # Parameters
        'params': merged_params,

        # Heartbeat history for P&L chart
        'pnl_history': [],  # [{timestamp, total_pnl, realized, unrealized, ce_premium, pe_premium}]

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
            session['expiry_time'] = datetime(y_full, m, d, 15, 30, 0, tzinfo=timezone.utc).isoformat()
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


def get_session_summary(session: Dict) -> Dict:
    """
    Get a compact summary of the session for WebUI display.

    Returns:
        Summary dictionary with key metrics
    """
    ce = session.get('ce', {})
    pe = session.get('pe', {})

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
        'realized_pnl': session.get('realized_pnl', 0),
        'unrealized_pnl': session.get('unrealized_pnl', 0),
        'total_fees': session.get('total_fees', 0),
        'net_pnl': session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0) - session.get('total_fees', 0),
        'peak_pnl': session.get('peak_pnl', 0),

        # Params (hot-reload visible)
        'adjustment_interval': session.get('params', {}).get('adjustment_interval', 300),
        'last_heartbeat': session.get('last_heartbeat'),
        'next_heartbeat': session.get('next_heartbeat'),

        # Expiry info
        'expiry': session.get('params', {}).get('expiry', ''),   # DDMMYYYY
        'expiry_time': session.get('expiry_time'),                # ISO UTC string
    }
