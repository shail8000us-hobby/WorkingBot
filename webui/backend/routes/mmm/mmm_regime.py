"""
MMM Regime Engine — Regime-Aware Risk Controls

Three pre-adjustment regime controls that detect dangerous market conditions
BEFORE the adjustment engine fires:
  A. Volatility Regime Filter — IV spike + RV detection
  B. Portfolio Gamma Cap — dollar gamma limits
  C. Trend Detection Guard — directional move detection

This module does NO I/O — it receives data and returns decisions.
The monitor heartbeat calls it between safety checks and trigger evaluation.

Maps to MMM_REGIME_RISK_CONTROLS_DESIGN.md

Created: February 20, 2026
"""

import logging
import math
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from .mmm_constants import LOT_SIZE_BTC

log = logging.getLogger('mmm_regime')

# =============================================================================
# Constants
# =============================================================================

# Volatility Regime states
VOL_NORMAL = 'NORMAL'
VOL_ELEVATED = 'ELEVATED'
VOL_HIGH = 'HIGH'

# Gamma Regime states — canonical definition is in mmm_gamma.py (imported here)
from .mmm_gamma import GAMMA_NORMAL, GAMMA_SOFT, GAMMA_HARD, GAMMA_EMERGENCY

# Trend Regime states
TREND_NORMAL = 'NORMAL'
TREND_UP = 'TREND_UP'
TREND_DOWN = 'TREND_DOWN'

# Trend Tier levels (graduated response — IMP-2)
TREND_TIER_NONE = 0       # No trend detected
TREND_TIER_ALERT = 1      # Alert + lot reduction
TREND_TIER_GUARD = 2      # Block aggressor-side sells
TREND_TIER_BLOCK = 3      # Block ALL sells
TREND_TIER_WIND_DOWN = 4  # Auto-trigger wind-down

# Aggregate regime actions
ACTION_NORMAL = 'NORMAL'
ACTION_WARN = 'WARN'
ACTION_BLOCK_CE_SELLS = 'BLOCK_CE_SELLS'
ACTION_BLOCK_PE_SELLS = 'BLOCK_PE_SELLS'
ACTION_BLOCK_ALL_SELLS = 'BLOCK_ALL_SELLS'
ACTION_FORCE_REDUCE = 'FORCE_REDUCE'
ACTION_PAUSE = 'PAUSE'

# Ring buffer max sizes
MAX_IV_HISTORY = 60
MAX_SPOT_HISTORY = 60
MAX_GAMMA_HISTORY = 60


# =============================================================================
# Section A: Volatility Regime Filter
# =============================================================================

def _update_vol_regime(session: Dict, iv_data: Dict, spot_price: float) -> str:
    """
    Update volatility regime based on IV change rate and realized volatility.

    Args:
        session: MMM session dict (mutated in place)
        iv_data: {'ce_iv': float, 'pe_iv': float} from ticker
        spot_price: Current BTC spot price

    Returns:
        Current vol regime: NORMAL / ELEVATED / HIGH
    """
    params = session.get('params', {})
    if not params.get('vol_regime_enabled', True):
        session['_vol_regime'] = VOL_NORMAL
        return VOL_NORMAL

    now = datetime.now(timezone.utc).isoformat()

    # ── Collect IV data ──
    ce_iv = iv_data.get('ce_iv', 0)
    pe_iv = iv_data.get('pe_iv', 0)

    # Use max(CE_iv, PE_iv) as conservative estimate (Section A.7)
    if ce_iv > 0 and pe_iv > 0:
        iv_avg = max(ce_iv, pe_iv)
    elif ce_iv > 0:
        iv_avg = ce_iv
    elif pe_iv > 0:
        iv_avg = pe_iv
    else:
        iv_avg = 0

    # ── Update ring buffers (L-5 fix: use deque to avoid manual slicing) ──
    # Convert from list (JSON-deserialized) to deque with maxlen for automatic eviction.
    # We store back as list so JSON serialization in _save_session() never sees a deque.
    raw_iv = session.get('_vol_iv_history')
    if isinstance(raw_iv, deque):
        iv_history = raw_iv
    else:
        iv_history = deque(raw_iv or [], maxlen=MAX_IV_HISTORY)

    raw_spot = session.get('_vol_spot_history')
    if isinstance(raw_spot, deque):
        spot_history = raw_spot
    else:
        spot_history = deque(raw_spot or [], maxlen=MAX_SPOT_HISTORY)

    if iv_avg > 0:
        iv_history.append((now, iv_avg))  # deque auto-evicts oldest when full
    session['_vol_iv_history'] = list(iv_history)  # Back to list for JSON safety

    # M-14 fix: use last valid spot price as fallback when current is <= 0
    last_valid_spot = session.get('_vol_last_valid_spot', 0)
    effective_spot = spot_price if spot_price > 0 else last_valid_spot
    if effective_spot > 0:
        spot_history.append((now, effective_spot))
        session['_vol_last_valid_spot'] = effective_spot
    session['_vol_spot_history'] = list(spot_history)  # Back to list for JSON safety

    # ── Compute IV Change Rate (Section A.2.1) ──
    # L-5 fix: type-check params to handle None from corrupt sessions
    lookback = int(params.get('vol_lookback_beats') or 5)
    iv_spike_threshold = float(params.get('vol_iv_spike_pct') or 30)
    iv_change_pct = 0.0
    have_iv = False

    # M-12 fix: explicit index calculation with bounds guard
    iv_past_idx = len(iv_history) - lookback - 1
    if iv_past_idx >= 0 and iv_avg > 0:
        iv_past = iv_history[iv_past_idx][1]
        if iv_past > 0:
            iv_change_pct = ((iv_avg - iv_past) / iv_past) * 100
            have_iv = True

    # ── Compute Realized Volatility (Section A.2.2) ──
    rv_window = int(params.get('vol_rv_window') or 20)
    rv_threshold = float(params.get('vol_rv_threshold') or 80)
    rv_annualized = 0.0
    have_rv = False

    if len(spot_history) >= rv_window:
        recent = list(spot_history)[-rv_window:]
        log_returns = []
        time_diffs = []
        for i in range(1, len(recent)):
            s_prev = recent[i - 1][1]
            s_curr = recent[i][1]
            if s_prev > 0 and s_curr > 0:
                log_returns.append(math.log(s_curr / s_prev))
                # Estimate time diff between beats (default ~60s for adaptive)
                try:
                    t1 = datetime.fromisoformat(recent[i - 1][0])
                    t2 = datetime.fromisoformat(recent[i][0])
                    time_diffs.append((t2 - t1).total_seconds())
                except (ValueError, TypeError):
                    time_diffs.append(60)

        if len(log_returns) >= 2:
            n = len(log_returns)
            variance = sum(r ** 2 for r in log_returns) / (n - 1)
            avg_dt = max(sum(time_diffs) / len(time_diffs) if time_diffs else 60, 1)  # M-13 fix: floor at 1s
            # Annualize: sqrt(seconds_per_year / avg_dt)
            # Crypto: 365 * 86400 = 31,536,000 seconds/year
            if avg_dt > 0:
                annualize_factor = math.sqrt(31_536_000 / avg_dt)
                rv_annualized = math.sqrt(variance) * annualize_factor * 100
                have_rv = True

    # ── Composite Regime Score (Section A.2.3) ──
    if have_iv and have_rv:
        w1, w2 = 0.6, 0.4
    elif have_iv:
        w1, w2 = 1.0, 0.0
    elif have_rv:
        w1, w2 = 0.0, 1.0
    else:
        # Insufficient data (Section A.7) — stay NORMAL
        session['_vol_regime'] = VOL_NORMAL
        session['_vol_iv_change_pct'] = 0.0
        session['_vol_rv_annualized'] = 0.0
        session['_vol_regime_score'] = 0.0
        return VOL_NORMAL

    iv_term = (abs(iv_change_pct) / iv_spike_threshold) if iv_spike_threshold > 0 else 0
    rv_term = (rv_annualized / rv_threshold) if rv_threshold > 0 else 0
    r_score = w1 * iv_term + w2 * rv_term

    # ── Determine state ──
    if r_score > 1.0:
        new_regime = VOL_HIGH
    elif r_score >= 0.7:
        new_regime = VOL_ELEVATED
    else:
        new_regime = VOL_NORMAL

    # ── Cooldown logic (Section A.7) ──
    current_regime = session.get('_vol_regime', VOL_NORMAL)
    cooldown_beats = params.get('vol_regime_cooldown_beats', 10)

    if current_regime in (VOL_ELEVATED, VOL_HIGH) and new_regime == VOL_NORMAL:
        # Must stay below threshold for N beats before resetting
        beats_below = session.get('_vol_regime_beats_below', 0) + 1
        session['_vol_regime_beats_below'] = beats_below
        if beats_below < cooldown_beats:
            new_regime = current_regime  # Stay in current elevated state
        else:
            session['_vol_regime_beats_below'] = 0  # Reset counter
    else:
        session['_vol_regime_beats_below'] = 0

    # ── Update state ──
    if new_regime != current_regime:
        session['_vol_regime_since'] = now
        log.info(
            f"Vol regime transition: {current_regime} → {new_regime} "
            f"(score={r_score:.2f}, IV_change={iv_change_pct:+.1f}%, RV={rv_annualized:.1f}%)"
        )

    session['_vol_regime'] = new_regime
    session['_vol_iv_change_pct'] = round(iv_change_pct, 2)
    session['_vol_rv_annualized'] = round(rv_annualized, 2)
    session['_vol_regime_score'] = round(r_score, 3)

    if new_regime == VOL_NORMAL and session.get('_vol_wind_down_triggered'):
        session['_vol_wind_down_triggered'] = False
        log.info("Vol regime reset to NORMAL — clearing _vol_wind_down_triggered")

    return new_regime

# =============================================================================
# Section B: Portfolio Gamma Cap — now in mmm_gamma.py
# =============================================================================
# _update_gamma_cap and compute_projected_gamma have been extracted to
# mmm_gamma.py for clear separation of concerns.  Imported here so that
# MMMRegimeEngine (below) and any existing callers continue to work.

from .mmm_gamma import _update_gamma_cap, compute_projected_gamma


# =============================================================================
# Section C: Trend Detection Guard
# =============================================================================

def _check_acceleration(session: Dict, spot_price: float, params: Dict) -> Tuple[bool, float]:
    """
    Check if BTC moved fast enough in a short window to bypass EMA confirmation.

    Uses the existing _vol_spot_history ring buffer (timestamp, spot) tuples.

    Returns:
        (is_fast_move: bool, acceleration_move_pct: float)
    """
    window_s = params.get('trend_acceleration_window_s', 600)
    accel_threshold = params.get('trend_acceleration_pct', 0.5)

    raw_spot = session.get('_vol_spot_history')
    if not raw_spot or len(raw_spot) < 2:
        return False, 0.0

    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - window_s

    # Walk backward to find the oldest price within the window
    oldest_price = None
    for ts_str, price in raw_spot:
        try:
            ts = datetime.fromisoformat(ts_str).timestamp()
        except (ValueError, TypeError):
            continue
        if ts >= cutoff and price > 0:
            oldest_price = price
            break  # First one in buffer that's within window

    if oldest_price is None or oldest_price <= 0:
        return False, 0.0

    accel_move_pct = ((spot_price - oldest_price) / oldest_price) * 100
    is_fast = abs(accel_move_pct) >= accel_threshold

    return is_fast, round(accel_move_pct, 3)


def _compute_trend_tier(
    abs_move_pct: float,
    ema_slope_confirms: bool,
    is_fast_move: bool,
    params: Dict,
) -> int:
    """
    Compute the trend tier (0–4) based on % move from anchor.

    Tier 1 requires EMA confirmation OR fast-move bypass.
    Tiers 2–4 fire on absolute % move alone (no EMA needed).

    Returns:
        Tier level: 0 (none), 1 (alert), 2 (guard), 3 (block), 4 (wind-down)
    """
    tier4_pct = params.get('trend_tier4_pct', 2.0)
    tier3_pct = params.get('trend_tier3_pct', 1.5)
    tier2_pct = params.get('trend_tier2_pct', 1.0)
    tier1_pct = params.get('trend_tier1_pct', 0.5)

    if abs_move_pct >= tier4_pct:
        return TREND_TIER_WIND_DOWN
    elif abs_move_pct >= tier3_pct:
        return TREND_TIER_BLOCK
    elif abs_move_pct >= tier2_pct:
        return TREND_TIER_GUARD
    elif abs_move_pct >= tier1_pct and (ema_slope_confirms or is_fast_move):
        return TREND_TIER_ALERT
    else:
        return TREND_TIER_NONE


def _update_trend_guard(session: Dict, spot_price: float) -> str:
    """
    Update trend detection guard based on spot price movement.

    Uses a TIERED response system (IMP-2):
      Tier 0: NORMAL — no intervention
      Tier 1: ALERT — log warning, reduce hedge lot size by configurable %
      Tier 2: GUARD — block sells on the aggressor side (CE in rally)
      Tier 3: BLOCK — block ALL new option sells (both CE and PE)
      Tier 4: WIND_DOWN — auto-trigger wind-down mode

    EMA slope confirmation required only for Tier 1 entry.
    Tiers 2–4 fire on absolute % move from anchor alone.
    Fast acceleration bypass: if BTC moves trend_acceleration_pct within
    trend_acceleration_window_s, bypasses EMA requirement for Tier 1.

    Tier reset: simple binary — when retracement + calm beats condition is met,
    reset straight to Tier 0 / NORMAL.

    Args:
        session: MMM session dict (mutated in place)
        spot_price: Current BTC spot price

    Returns:
        Current trend regime: NORMAL / TREND_UP / TREND_DOWN
    """
    params = session.get('params', {})
    if not params.get('trend_enabled', True):
        session['_trend_regime'] = TREND_NORMAL
        session['_trend_tier'] = TREND_TIER_NONE
        session['_trend_direction'] = 'none'
        return TREND_NORMAL

    if spot_price <= 0:
        return session.get('_trend_regime', TREND_NORMAL)

    now = datetime.now(timezone.utc).isoformat()

    # ── Initialize anchor if needed ──
    anchor = session.get('_trend_anchor_spot', 0)
    if anchor <= 0:
        session['_trend_anchor_spot'] = spot_price
        session['_trend_high'] = spot_price
        session['_trend_low'] = spot_price
        session['_trend_ema'] = spot_price
        session['_trend_ema_prev'] = spot_price
        session['_trend_regime'] = TREND_NORMAL
        session['_trend_tier'] = TREND_TIER_NONE
        session['_trend_direction'] = 'none'
        return TREND_NORMAL

    # ── Update high/low tracking ──
    trend_high = session.get('_trend_high', spot_price)
    trend_low = session.get('_trend_low', spot_price)

    if spot_price > trend_high:
        trend_high = spot_price
    if spot_price < trend_low:
        trend_low = spot_price

    session['_trend_high'] = trend_high
    session['_trend_low'] = trend_low

    # ── Signal 1: Percentage move from anchor ──
    move_pct = ((spot_price - anchor) / anchor) * 100
    abs_move = abs(move_pct)

    # ── Signal 2: Max excursion without retracement ──
    retrace_threshold_pct = params.get('trend_retrace_pct', 30)

    # Check retracement from high (for rally scenario)
    retrace_from_high = 0
    if trend_high > trend_low and trend_high > 0:
        retrace_from_high = ((trend_high - spot_price) / (trend_high - trend_low)) * 100 if (trend_high - trend_low) > 0 else 0

    # Check retracement from low (for drop scenario)
    retrace_from_low = 0
    if trend_high > trend_low and trend_high > 0:
        retrace_from_low = ((spot_price - trend_low) / (trend_high - trend_low)) * 100 if (trend_high - trend_low) > 0 else 0

    # ── Signal 3: EMA Slope ──
    ema_period = params.get('trend_ema_period', 10)
    ema_prev = session.get('_trend_ema', spot_price)
    ema_slope_threshold = params.get('trend_ema_slope_threshold', 25)

    # EMA calculation: α = 2/(period+1)
    alpha = 2.0 / (ema_period + 1)
    ema_now = alpha * spot_price + (1 - alpha) * ema_prev

    # Slope: normalized rate of EMA change
    ema_slope = 0
    if spot_price > 0:
        ema_slope = ((ema_now - ema_prev) / spot_price) * 10000

    session['_trend_ema_prev'] = ema_prev
    session['_trend_ema'] = ema_now
    session['_trend_ema_slope'] = round(ema_slope, 2)
    session['_trend_move_pct'] = round(move_pct, 3)

    # ── Acceleration check (rate-of-change bypass) ──
    is_fast_move, accel_move_pct = _check_acceleration(session, spot_price, params)
    session['_trend_acceleration_move_pct'] = accel_move_pct

    # ── Determine direction ──
    direction = 'none'
    if move_pct > 0:
        direction = 'up'
        ema_confirms = ema_slope > 0
    elif move_pct < 0:
        direction = 'down'
        ema_confirms = ema_slope < 0
    else:
        ema_confirms = False

    # ── Determine new regime and tier ──
    current_regime = session.get('_trend_regime', TREND_NORMAL)
    current_tier = session.get('_trend_tier', TREND_TIER_NONE)

    raw_tier = _compute_trend_tier(abs_move, ema_confirms, is_fast_move, params)

    # ── Tier only ESCALATES within a trend, never de-escalates ──
    # (de-escalation only happens via full reset)
    if current_regime != TREND_NORMAL:
        new_tier = max(raw_tier, current_tier)
    else:
        new_tier = raw_tier

    # ── Map tier + direction to regime ──
    if new_tier >= TREND_TIER_ALERT:
        if direction == 'up':
            new_regime = TREND_UP
        elif direction == 'down':
            new_regime = TREND_DOWN
        else:
            new_regime = current_regime  # Keep current if direction unclear
    else:
        new_regime = TREND_NORMAL

    # ── Reset conditions (simple binary reset) ──
    if current_regime in (TREND_UP, TREND_DOWN):
        # Check if spot retraced past anchor → immediate reset
        if current_regime == TREND_UP and move_pct <= 0:
            # Price dropped below anchor — trend clearly over
            new_regime = TREND_NORMAL
            new_tier = TREND_TIER_NONE
            session['_trend_anchor_spot'] = spot_price
            session['_trend_high'] = spot_price
            session['_trend_low'] = spot_price
            session['_trend_calm_beats'] = 0
            session['_trend_t4_beats'] = 0
        elif current_regime == TREND_DOWN and move_pct >= 0:
            # Price rose above anchor — trend clearly over
            new_regime = TREND_NORMAL
            new_tier = TREND_TIER_NONE
            session['_trend_anchor_spot'] = spot_price
            session['_trend_high'] = spot_price
            session['_trend_low'] = spot_price
            session['_trend_calm_beats'] = 0
            session['_trend_t4_beats'] = 0
        else:
            # Check gradual retracement + calm beats
            if current_regime == TREND_UP:
                has_retrace = retrace_from_high >= retrace_threshold_pct
            else:
                has_retrace = retrace_from_low >= retrace_threshold_pct

            ema_calmed = abs(ema_slope) < ema_slope_threshold

            if has_retrace and ema_calmed:
                calm_beats = session.get('_trend_calm_beats', 0) + 1
                session['_trend_calm_beats'] = calm_beats
                if calm_beats >= params.get('trend_reset_beats', 5):
                    new_regime = TREND_NORMAL
                    new_tier = TREND_TIER_NONE
                    session['_trend_anchor_spot'] = spot_price
                    session['_trend_high'] = spot_price
                    session['_trend_low'] = spot_price
                    session['_trend_calm_beats'] = 0
                    session['_trend_plateau_beats'] = 0
                    session['_trend_t4_beats'] = 0
            else:
                session['_trend_calm_beats'] = 0
                # Plateau reset: market moved up/down, plateaued near the new level,
                # and never retraced enough (< retrace_threshold_pct) to trigger the
                # standard calm+retracement path.  When the raw computed tier (based on
                # current price vs anchor) has fallen below the locked tier AND the EMA
                # has gone flat, count consecutive calm beats.  After
                # trend_plateau_reset_beats beats we advance the anchor to the current
                # price and exit the trend lock.  This prevents a stale anchor from
                # keeping T3/T4 locked indefinitely after the market stabilises.
                if raw_tier < current_tier and ema_calmed:
                    plateau_beats = session.get('_trend_plateau_beats', 0) + 1
                    session['_trend_plateau_beats'] = plateau_beats
                    if plateau_beats >= params.get('trend_plateau_reset_beats', 5):
                        new_regime = TREND_NORMAL
                        new_tier = TREND_TIER_NONE
                        session['_trend_anchor_spot'] = spot_price
                        session['_trend_high'] = spot_price
                        session['_trend_low'] = spot_price
                        session['_trend_calm_beats'] = 0
                        session['_trend_plateau_beats'] = 0
                        session['_trend_t4_beats'] = 0
                else:
                    session['_trend_plateau_beats'] = 0

                # ── T4 Timeout: anchor slide when stuck at WIND_DOWN with flat EMA ──
                # The plateau counter above checks raw_tier < current_tier, which is
                # always False at T4 plateau: the anchor is frozen at session start, so
                # abs_move stays ≥ tier4_pct and raw_tier stays 4 indefinitely.
                # This dedicated counter fires purely on: current_tier is T4 AND EMA
                # has been flat for trend_t4_timeout_beats consecutive beats.
                # After timeout: slide anchor to current price, reset to NORMAL.
                # The downstream code (line ~719) then clears _trend_wind_down_triggered.
                if current_tier >= TREND_TIER_WIND_DOWN and ema_calmed:
                    t4_beats = session.get('_trend_t4_beats', 0) + 1
                    session['_trend_t4_beats'] = t4_beats
                    timeout_beats = params.get('trend_t4_timeout_beats', 20)
                    if t4_beats >= timeout_beats:
                        log.info(
                            f"T4 TIMEOUT: {t4_beats} calm beats at Tier 4 — "
                            f"sliding anchor ${anchor:.0f} → ${spot_price:.0f}, "
                            f"resetting to NORMAL (EMA slope={ema_slope:+.1f})"
                        )
                        new_regime = TREND_NORMAL
                        new_tier = TREND_TIER_NONE
                        session['_trend_anchor_spot'] = spot_price
                        session['_trend_high'] = spot_price
                        session['_trend_low'] = spot_price
                        session['_trend_calm_beats'] = 0
                        session['_trend_plateau_beats'] = 0
                        session['_trend_t4_beats'] = 0
                else:
                    session['_trend_t4_beats'] = 0

            # Check for trend reversal (was up, now strongly down or vice versa)
            tier1_pct = params.get('trend_tier1_pct', 0.5)
            if current_regime == TREND_UP and move_pct <= -tier1_pct and ema_slope < -ema_slope_threshold:
                new_regime = TREND_DOWN
                new_tier = _compute_trend_tier(abs_move, True, is_fast_move, params)
                session['_trend_anchor_spot'] = spot_price
                session['_trend_high'] = spot_price
                session['_trend_low'] = spot_price
                session['_trend_calm_beats'] = 0
            elif current_regime == TREND_DOWN and move_pct >= tier1_pct and ema_slope > ema_slope_threshold:
                new_regime = TREND_UP
                new_tier = _compute_trend_tier(abs_move, True, is_fast_move, params)
                session['_trend_anchor_spot'] = spot_price
                session['_trend_high'] = spot_price
                session['_trend_low'] = spot_price
                session['_trend_calm_beats'] = 0

    # ── Log tier transitions ──
    if new_tier != current_tier or new_regime != current_regime:
        session['_trend_since'] = now
        tier_names = {
            TREND_TIER_NONE: 'NONE',
            TREND_TIER_ALERT: 'T1:ALERT',
            TREND_TIER_GUARD: 'T2:GUARD',
            TREND_TIER_BLOCK: 'T3:BLOCK',
            TREND_TIER_WIND_DOWN: 'T4:WIND_DOWN',
        }
        old_tier_name = tier_names.get(current_tier, str(current_tier))
        new_tier_name = tier_names.get(new_tier, str(new_tier))

        if new_tier > current_tier:
            log.warning(
                f"Trend ESCALATION: {current_regime}(tier={old_tier_name}) → "
                f"{new_regime}(tier={new_tier_name}) "
                f"(move={move_pct:+.2f}%, EMA_slope={ema_slope:+.1f}, "
                f"accel={accel_move_pct:+.2f}%, anchor=${anchor:.0f}, spot=${spot_price:.0f})"
            )
        elif new_tier < current_tier:
            log.info(
                f"Trend RESET: {current_regime}(tier={old_tier_name}) → "
                f"{new_regime}(tier={new_tier_name}) "
                f"(move={move_pct:+.2f}%, retracement sufficient, anchor reset to ${spot_price:.0f})"
            )
        else:
            log.info(
                f"Trend regime transition: {current_regime} → {new_regime} "
                f"(tier={new_tier_name}, move={move_pct:+.2f}%, "
                f"EMA_slope={ema_slope:+.1f}, anchor=${anchor:.0f}, spot=${spot_price:.0f})"
            )

    # ── Auto-trigger wind-down at Tier 4 ──
    if new_tier >= TREND_TIER_WIND_DOWN:
        if not session.get('_trend_wind_down_triggered'):
            session['_trend_wind_down_triggered'] = True
            log.warning(
                f"TREND TIER 4: Auto-triggering wind-down mode "
                f"(move={move_pct:+.2f}% from anchor=${anchor:.0f})"
            )

    # ── Store all state ──
    session['_trend_regime'] = new_regime
    session['_trend_tier'] = new_tier
    session['_trend_direction'] = direction if new_tier > TREND_TIER_NONE else 'none'

    # Clear regime wind-down flag when trend resets fully to NORMAL.
    # Without this, a Tier 4 wind-down trigger would be sticky forever,
    # keeping wind-down active even after the market calmed down.
    if new_tier == TREND_TIER_NONE and session.get('_trend_wind_down_triggered'):
        session['_trend_wind_down_triggered'] = False
        log.info("Trend reset to NORMAL — clearing _trend_wind_down_triggered")

    return new_regime


# =============================================================================
# Section D: Aggregate Regime Computation
# =============================================================================

def _compute_regime_action(session: Dict) -> str:
    """
    Combine all three regime controls into a single action flag.

    Priority (Section D.2):
      1. Safety hard stops (handled before this — max_loss, margin_critical)
      2. Gamma emergency → FORCE_REDUCE
      3. Vol HIGH + Trend → BLOCK_ALL_SELLS
      4. Gamma hard (vol=NORMAL) → directional block via per-side gamma (Tier B)
         or DTE relax tiebreaker (Tier C); fallback BLOCK_ALL_SELLS.
         Vol ELEVATED + Gamma HARD → BLOCK_ALL_SELLS (compound risk, no exemption).
      5. Vol ELEVATED or Trend alone → directional or block sells
      6. Gamma soft → WARN

    Most conservative action wins (Section D.3).

    Returns:
        NORMAL | WARN | BLOCK_CE_SELLS | BLOCK_PE_SELLS |
        BLOCK_ALL_SELLS | FORCE_REDUCE | PAUSE
    """
    vol_regime = session.get('_vol_regime', VOL_NORMAL)
    gamma_regime = session.get('_gamma_regime', GAMMA_NORMAL)
    trend_regime = session.get('_trend_regime', TREND_NORMAL)

    params = session.get('params', {})
    vol_action_cfg = params.get('vol_regime_action', 'block_sells')
    trend_action_cfg = params.get('trend_action', 'block_sells')

    # Priority 2: Gamma emergency
    if gamma_regime == GAMMA_EMERGENCY:
        return ACTION_FORCE_REDUCE

    # Priority 3: Vol HIGH + any Trend → block all
    if vol_regime == VOL_HIGH and trend_regime != TREND_NORMAL:
        return ACTION_BLOCK_ALL_SELLS

    # Priority 3b: Vol HIGH alone
    if vol_regime == VOL_HIGH:
        if vol_action_cfg == 'wind_down':
            # Vol HIGH with wind_down action → mark for wind-down + block all sells
            session['_vol_wind_down_triggered'] = True
        elif vol_action_cfg == 'pause':
            # Vol HIGH with pause action → pause the session entirely
            return ACTION_PAUSE
        return ACTION_BLOCK_ALL_SELLS

    # Priority 4: Gamma hard — block the DANGER (aggressor) side only.
    # Vol is NORMAL or NORMAL here — HIGH was returned early in P3/P3b.
    # CRITICAL: Vol ELEVATED must still block ALL sells — it compounds with
    # gamma risk and is not safe to relax.  Only when vol is NORMAL can we
    # apply the per-side gamma and DTE-relax exemptions (Tier B/C).
    #
    # Three-step resolution when vol=NORMAL (most reliable first):
    #
    #   Step 1 — Tier B (per-side gamma): The side closer to ATM has higher
    #     dollar gamma.  If one side contributes ≥ ratio × the other, it is
    #     the danger side.  Block only it; allow the low-gamma side to hedge.
    #
    #   Step 1 — Anchor direction: the session price anchor tracks net
    #     directional movement.  When spot > anchor → market moved UP → calls
    #     (CE) are going ITM → CE is the aggressor → block CE sells.  When
    #     spot < anchor → puts (PE) are going ITM → block PE sells.  A small
    #     dead-band (gamma_directional_min_pct) prevents flip-flopping when
    #     spot oscillates near the anchor.  This is the primary economic signal
    #     — it is independent of lot-count asymmetry that can distort per-side
    #     gamma totals.
    #
    #   Step 2 — Per-side gamma imbalance: when anchor direction is ambiguous
    #     (spot inside dead-band), fall back to dollar gamma per side.  One
    #     side having significantly more gamma exposure indicates it carries
    #     more risk.  NOTE: confounded by lot-count asymmetry — use only as
    #     tiebreaker.
    #
    #   Step 3 — Tier C (DTE relax): When per-side gamma is balanced and we
    #     are inside the DTE relax window with dollar_gamma below the relaxed
    #     hedge limit, use trend direction as a tiebreaker.  Near expiry the
    #     algo must hedge even when gamma is structurally elevated.
    #
    #   Step 4 — Conservative fallback: block all sells.
    if gamma_regime == GAMMA_HARD:
        # Vol ELEVATED + Gamma HARD = compound risk → no exemption allowed.
        # Leave this to Priority 5's vol=ELEVATED handler by falling through,
        # but since Priority 5 comes after and vol=ELEVATED always returns
        # BLOCK_ALL_SELLS there, short-circuit now for clarity and safety.
        if vol_regime == VOL_ELEVATED:
            return ACTION_BLOCK_ALL_SELLS

        ce_dgamma = session.get('_ce_dollar_gamma', 0.0)
        pe_dgamma = session.get('_pe_dollar_gamma', 0.0)
        ratio = params.get('gamma_side_imbalance_ratio', 1.5)

        # Step 1: Anchor-relative direction — primary economic signal.
        # spot > anchor by >= dead-band → market moved UP → CE (calls) is aggressor.
        # spot < anchor by >= dead-band → market moved DOWN → PE (puts) is aggressor.
        # Dead-band prevents flip-flopping when spot oscillates near anchor.
        _anchor = session.get('_trend_anchor_spot', 0.0)
        _spot = session.get('_regime_spot_price', 0.0)
        _min_dir_pct = params.get('gamma_directional_min_pct', 0.10)
        if _anchor > 0 and _spot > 0:
            _move_pct = (_spot - _anchor) / _anchor * 100.0
            if _move_pct >= _min_dir_pct:
                return ACTION_BLOCK_CE_SELLS   # Market up → CE is aggressor
            elif _move_pct <= -_min_dir_pct:
                return ACTION_BLOCK_PE_SELLS   # Market down → PE is aggressor

        # Step 2: Per-side gamma imbalance — tiebreaker when direction is ambiguous.
        if ce_dgamma > 0 and pe_dgamma > 0:
            if pe_dgamma >= ce_dgamma * ratio:
                return ACTION_BLOCK_PE_SELLS   # PE exposure dominates
            if ce_dgamma >= pe_dgamma * ratio:
                return ACTION_BLOCK_CE_SELLS   # CE exposure dominates
        elif pe_dgamma > 0 and ce_dgamma == 0:
            return ACTION_BLOCK_PE_SELLS       # Only PE positions active
        elif ce_dgamma > 0 and pe_dgamma == 0:
            return ACTION_BLOCK_CE_SELLS       # Only CE positions active

        # Step 3: DTE relax tiebreaker — balanced gamma near expiry
        if session.get('_gamma_dte_relax_active', False):
            dollar_gamma = session.get('_portfolio_dollar_gamma', 0.0)
            hedge_limit = session.get('_gamma_hard_limit_hedge_effective',
                                      session.get('_gamma_hard_limit_effective', 5000.0))
            if dollar_gamma < hedge_limit:
                trend_now = session.get('_trend_regime', TREND_NORMAL)
                if trend_now == TREND_DOWN:
                    return ACTION_BLOCK_PE_SELLS
                if trend_now == TREND_UP:
                    return ACTION_BLOCK_CE_SELLS

        # Step 4: Conservative fallback
        return ACTION_BLOCK_ALL_SELLS

    # Priority 5: Trend detection — tiered response (IMP-2)
    # + Vol ELEVATED compounds with trend
    trend_tier = session.get('_trend_tier', TREND_TIER_NONE)

    if trend_regime == TREND_UP and vol_regime == VOL_ELEVATED:
        return ACTION_BLOCK_ALL_SELLS
    if trend_regime == TREND_DOWN and vol_regime == VOL_ELEVATED:
        return ACTION_BLOCK_ALL_SELLS

    if vol_regime == VOL_ELEVATED:
        return ACTION_BLOCK_ALL_SELLS

    # ── ATM Shield override: relax trend tiers when shield has capacity ──
    # Shield catches ATM risk proactively, so trend guard's defensive blocks
    # become unnecessary at T1/T2 and can be narrowed at T3/T4.
    shield_on = params.get('atm_shield_enabled', False)
    if shield_on and trend_tier >= TREND_TIER_ALERT:
        trend_dir = session.get('_trend_direction', 'none')
        if trend_dir in ('up', 'down'):
            endangered = 'ce' if trend_dir == 'up' else 'pe'
            count = session.get(f'_atm_shield_count_{endangered}', 0)
            max_fires = params.get('atm_shield_max_per_session', 3)
            if count < max_fires:
                if trend_tier <= TREND_TIER_GUARD:  # T1 or T2
                    return ACTION_NORMAL
                else:  # T3 or T4
                    if trend_dir == 'up':
                        return ACTION_BLOCK_CE_SELLS
                    else:
                        return ACTION_BLOCK_PE_SELLS
        # Shield exhausted or no clear direction → fall through to original

    # Tier 4: wind-down + block all sells
    if trend_tier >= TREND_TIER_WIND_DOWN:
        session['_trend_wind_down_triggered'] = True
        return ACTION_BLOCK_ALL_SELLS

    # Tier 3: block dangerous side; allow safe-side if trend_boost_enabled
    if trend_tier >= TREND_TIER_BLOCK:
        if params.get('trend_boost_enabled', False):
            # Trend Boost: only block the dangerous side, allow safe-side sells
            if trend_regime == TREND_UP:
                return ACTION_BLOCK_CE_SELLS
            if trend_regime == TREND_DOWN:
                return ACTION_BLOCK_PE_SELLS
        return ACTION_BLOCK_ALL_SELLS

    # Tier 2: block aggressor-side sells only
    if trend_tier >= TREND_TIER_GUARD:
        if trend_regime == TREND_UP:
            if trend_action_cfg == 'wind_down':
                session['_trend_wind_down_triggered'] = True
            elif trend_action_cfg == 'pause':
                return ACTION_PAUSE
            return ACTION_BLOCK_CE_SELLS
        if trend_regime == TREND_DOWN:
            if trend_action_cfg == 'wind_down':
                session['_trend_wind_down_triggered'] = True
            elif trend_action_cfg == 'pause':
                return ACTION_PAUSE
            return ACTION_BLOCK_PE_SELLS

    # Tier 1: warn only (lot reduction handled in engine)
    if trend_tier >= TREND_TIER_ALERT:
        return ACTION_WARN

    # Priority 6: Gamma soft → warn only
    if gamma_regime == GAMMA_SOFT:
        return ACTION_WARN

    return ACTION_NORMAL


# =============================================================================
# Public API — MMMRegimeEngine
# =============================================================================

class MMMRegimeEngine:
    """
    Stateless regime engine. All state lives in the session dict.
    Called by the monitor heartbeat every cycle.
    """

    def update_vol_regime(
        self, session: Dict, iv_data: Dict, spot_price: float,
    ) -> str:
        """Update volatility regime. Returns regime string."""
        try:
            return _update_vol_regime(session, iv_data, spot_price)
        except Exception as e:
            log.error(f"[RegimeEngine] vol_regime calculation failed: {e}", exc_info=True)
            # H-11 fix: return CURRENT regime, not NORMAL — don't downgrade safety
            return session.get('_vol_regime', VOL_NORMAL)

    def update_gamma_cap(
        self,
        session: Dict,
        gamma_data: Dict,
        spot_price: float,
        minutes_to_expiry: Optional[float] = None,
    ) -> str:
        """Update gamma cap regime. Returns regime string."""
        try:
            return _update_gamma_cap(session, gamma_data, spot_price, minutes_to_expiry)
        except Exception as e:
            log.error(f"[RegimeEngine] gamma_cap calculation failed: {e}", exc_info=True)
            return session.get('_gamma_regime', GAMMA_NORMAL)

    def update_trend_guard(
        self, session: Dict, spot_price: float,
    ) -> str:
        """Update trend detection guard. Returns regime string."""
        try:
            return _update_trend_guard(session, spot_price)
        except Exception as e:
            log.error(f"[RegimeEngine] trend_guard calculation failed: {e}", exc_info=True)
            return session.get('_trend_regime', TREND_NORMAL)

    def compute_regime_action(self, session: Dict) -> str:
        """Compute aggregate regime action from all three controls."""
        action = _compute_regime_action(session)
        session['_regime_action'] = action
        return action

    def get_regime_status(self, session: Dict) -> Dict[str, Any]:
        """
        Return full regime status for WebSocket/API.

        Includes all three control states, current action, and metrics.
        """
        return {
            'vol_regime': session.get('_vol_regime', VOL_NORMAL),
            'gamma_regime': session.get('_gamma_regime', GAMMA_NORMAL),
            'trend_regime': session.get('_trend_regime', TREND_NORMAL),
            'trend_tier': session.get('_trend_tier', TREND_TIER_NONE),
            'trend_direction': session.get('_trend_direction', 'none'),
            'regime_action': session.get('_regime_action', ACTION_NORMAL),
            'trend_boost_active': session.get('_trend_boost_active', False),
            'trend_boost_mult': session.get('_trend_boost_mult', 1.0),
            'details': {
                'iv_change_pct': session.get('_vol_iv_change_pct', 0),
                'rv_annualized': session.get('_vol_rv_annualized', 0),
                'vol_regime_score': session.get('_vol_regime_score', 0),
                'dollar_gamma': session.get('_portfolio_dollar_gamma', 0),
                'ce_dollar_gamma': session.get('_ce_dollar_gamma', 0),
                'pe_dollar_gamma': session.get('_pe_dollar_gamma', 0),
                'gamma_soft_limit': session.get('_gamma_soft_limit_effective', 0),
                'gamma_hard_limit': session.get('_gamma_hard_limit_effective', 0),
                'gamma_hard_limit_hedge': session.get('_gamma_hard_limit_hedge_effective', 0),
                'gamma_dte_relax_active': session.get('_gamma_dte_relax_active', False),
                'delta_rescue_count': session.get('_delta_rescue_count', 0),
                'spot_move_pct': session.get('_trend_move_pct', 0),
                'ema_slope': session.get('_trend_ema_slope', 0),
                'trend_anchor': session.get('_trend_anchor_spot', 0),
                'trend_tier': session.get('_trend_tier', TREND_TIER_NONE),
                'trend_direction': session.get('_trend_direction', 'none'),
                'trend_acceleration_move_pct': session.get('_trend_acceleration_move_pct', 0),
            },
        }

    def should_block_sell(
        self, session: Dict, sell_side: str,
    ) -> Tuple[bool, str]:
        """
        Check if a specific sell should be blocked by regime controls.

        This is the check used by the adjustment engine before executing
        any sell order.

        Args:
            session: MMM session dict
            sell_side: 'ce' or 'pe' — the side being sold

        Returns:
            (blocked: bool, reason: str)
        """
        action = session.get('_regime_action', ACTION_NORMAL)

        if action == ACTION_FORCE_REDUCE:
            return True, 'Gamma emergency — force reducing positions'

        if action == ACTION_PAUSE:
            return True, 'Regime pause — session paused by vol/trend controls'

        if action == ACTION_BLOCK_ALL_SELLS:
            vol = session.get('_vol_regime', VOL_NORMAL)
            gamma = session.get('_gamma_regime', GAMMA_NORMAL)
            reasons = []
            if vol in (VOL_HIGH, VOL_ELEVATED):
                reasons.append(f'Vol regime {vol}')
            if gamma == GAMMA_HARD:
                reasons.append(f'Gamma {gamma}')
            trend = session.get('_trend_regime', TREND_NORMAL)
            if trend != TREND_NORMAL:
                reasons.append(f'Trend {trend}')
            return True, ' + '.join(reasons) if reasons else 'Regime block'

        if action == ACTION_BLOCK_CE_SELLS and sell_side.lower() == 'ce':
            gamma = session.get('_gamma_regime', GAMMA_NORMAL)
            if gamma == GAMMA_HARD:
                ce_dg = session.get('_ce_dollar_gamma', 0.0)
                pe_dg = session.get('_pe_dollar_gamma', 0.0)
                return True, (
                    f'CE sells blocked — Gamma HARD, CE is aggressor side '
                    f'(CE $Γ={ce_dg:.0f} vs PE $Γ={pe_dg:.0f})'
                )
            tier = session.get('_trend_tier', 0)
            return True, f'CE sells blocked — Trend UP Tier {tier} (spot +{session.get("_trend_move_pct", 0):.1f}%)'

        if action == ACTION_BLOCK_PE_SELLS and sell_side.lower() == 'pe':
            gamma = session.get('_gamma_regime', GAMMA_NORMAL)
            if gamma == GAMMA_HARD:
                ce_dg = session.get('_ce_dollar_gamma', 0.0)
                pe_dg = session.get('_pe_dollar_gamma', 0.0)
                return True, (
                    f'PE sells blocked — Gamma HARD, PE is aggressor side '
                    f'(PE $Γ={pe_dg:.0f} vs CE $Γ={ce_dg:.0f})'
                )
            tier = session.get('_trend_tier', 0)
            return True, f'PE sells blocked — Trend DOWN Tier {tier} (spot {session.get("_trend_move_pct", 0):.1f}%)'

        return False, ''

    def check_projected_gamma(
        self,
        session: Dict,
        new_strike_gamma: float,
        new_lots: int,
        spot_price: float,
    ) -> Tuple[bool, float]:
        """
        Pre-trade gamma projection check (Section B.4.1).

        Returns:
            (blocked: bool, projected_dollar_gamma: float)

        When gamma_incremental_limit > 0 and current dollar gamma already
        exceeds hard_limit, the check switches from "total projected vs hard_limit"
        to "incremental added by this trade vs gamma_incremental_limit". This
        prevents the "once breached, always blocked" freeze where elevated baseline
        gamma (e.g. near-ATM 0DTE positions) permanently disables all adjustments.
        """
        params = session.get('params', {})
        if not params.get('gamma_cap_enabled', True):
            return False, 0

        projected = compute_projected_gamma(
            session, new_strike_gamma, new_lots, spot_price,
        )
        hard_limit = session.get('_gamma_hard_limit_effective',
                                  params.get('gamma_hard_limit', 5000.0))

        if projected <= hard_limit:
            return False, projected

        # projected > hard_limit — would breach or extend an existing breach.
        # If gamma_incremental_limit is configured, allow the trade when the
        # INCREMENTAL dollar gamma added by this specific trade is within budget,
        # even though the total portfolio gamma already exceeds hard_limit.
        incremental_limit = params.get('gamma_incremental_limit', 0.0)
        if incremental_limit > 0:
            current_dollar_gamma = session.get('_portfolio_dollar_gamma', 0.0)
            if current_dollar_gamma >= hard_limit:
                # Already in breach — baseline gamma exceeds limit due to
                # existing positions (e.g. near-ATM 0DTE). Evaluate only the
                # marginal cost of this trade, not the full portfolio total.
                incremental = projected - current_dollar_gamma
                if incremental <= incremental_limit:
                    log.info(
                        f"Gamma already breached (${current_dollar_gamma:.0f} > "
                        f"${hard_limit:.0f}) but incremental $Γ={incremental:.0f} "
                        f"≤ budget ${incremental_limit:.0f} — allowing trade "
                        f"(new_lots={new_lots})"
                    )
                    return False, projected

        session['_gamma_blocked_count'] = session.get('_gamma_blocked_count', 0) + 1
        log.warning(
            f"Gamma projection blocked: projected $Γ={projected:.2f} > "
            f"hard limit ${hard_limit:.0f} "
            f"(new_lots={new_lots}, blocked_count={session['_gamma_blocked_count']})"
        )
        return True, projected
