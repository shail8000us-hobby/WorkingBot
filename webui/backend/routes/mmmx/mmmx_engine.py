"""
MMMX Engine — Pure Math Module

All P&L, delta, fee, and risk calculations live here.
No I/O, no side effects, fully deterministic given inputs.
Spec: MMMX_COMPLETE.md Section 4 (P&L formulas) + Section 2 (capital model).

Rules:
  - LOT_SIZE_BTC is ALWAYS imported from mmmx_constants — never hardcoded.
  - All functions are pure (no session mutation).
  - PnLIncompleteError is raised when required quotes are missing;
    the monitor catches this, sets _pnl_calculation_incomplete=True, and skips triggers.
"""

import math
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .mmmx_constants import LOT_SIZE_BTC, FEE_RATE_MAKER, FEE_RATE_TAKER

log = logging.getLogger('mmmx_engine')


class PnLIncompleteError(Exception):
    """
    Raised when live quotes are missing and P&L cannot be fully computed.
    Monitor catches this and sets session['_pnl_calculation_incomplete'] = True.
    """
    pass


# ── Position P&L ──────────────────────────────────────────────────────────────

def compute_position_pnl(
    entry_premium: float,
    current_premium: float,
    lots: int,
    position_type: str = 'SHORT',
) -> float:
    """
    Compute gross unrealized P&L for a single leg.

    SHORT (sold option):
      unrealized_pnl = (entry_premium - current_premium) × lots × LOT_SIZE_BTC
      Positive when current < entry (premium decayed — theta at work).

    LONG (bought hedge):
      unrealized_pnl = (current_premium - entry_premium) × lots × LOT_SIZE_BTC
      Positive when current > entry.

    Spec: MMMX_COMPLETE.md Section 4 (P&L formulas).
    """
    if current_premium is None:
        raise PnLIncompleteError(
            f"current_premium is None — cannot compute P&L for this leg"
        )
    if position_type == 'SHORT':
        return (entry_premium - current_premium) * lots * LOT_SIZE_BTC
    else:  # LONG (hedge)
        return (current_premium - entry_premium) * lots * LOT_SIZE_BTC


def compute_realized_pnl(
    entry_premium: float,
    exit_premium: float,
    lots: int,
    position_type: str = 'SHORT',
) -> float:
    """
    Compute realized P&L after a position is closed.

    SHORT: (entry - exit) × lots × LOT_SIZE_BTC
    LONG:  (exit - entry) × lots × LOT_SIZE_BTC
    """
    if position_type == 'SHORT':
        return (entry_premium - exit_premium) * lots * LOT_SIZE_BTC
    else:
        return (exit_premium - entry_premium) * lots * LOT_SIZE_BTC


# ── Fee calculation ────────────────────────────────────────────────────────────

def compute_fee(price: float, lots: int, is_taker: bool = True) -> float:
    """
    Compute exchange fee for a single order.

    fee = price × lots × LOT_SIZE_BTC × rate
    is_taker=True: 0.05% (market orders, aggressive limit fills)
    is_taker=False: 0.02% (maker limit orders)
    """
    rate = FEE_RATE_TAKER if is_taker else FEE_RATE_MAKER
    return price * lots * LOT_SIZE_BTC * rate


# ── Portfolio-level P&L ────────────────────────────────────────────────────────

def compute_portfolio_pnl(session: Dict[str, Any]) -> float:
    """
    Compute total portfolio P&L (unrealized + realized) across all tranches and hedges.

    Raises PnLIncompleteError if any active position is missing current_premium.
    Caller must catch and set session['_pnl_calculation_incomplete'] = True.

    Formula per MMMX_COMPLETE.md:
      total_pnl = sum(tranche unrealized/realized pnl) + sum(hedge unrealized/realized pnl) - fees
    """
    incomplete_legs = []
    total_pnl = 0.0

    for tranche in session.get('tranches', []):
        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg:
                continue
            status = leg.get('status', 'ACTIVE')
            lots = leg.get('lots', 0)
            entry = leg.get('entry_premium', 0.0)
            realized = leg.get('realized_pnl', 0.0)
            fees = leg.get('fees_paid', 0.0)

            if status == 'CLOSED':
                total_pnl += realized - fees
            else:
                current = leg.get('current_premium')
                if current is None:
                    incomplete_legs.append(f"Tr{tranche['tranche_id']}/{side}")
                else:
                    total_pnl += compute_position_pnl(entry, current, lots, 'SHORT') - fees

    for hedge in session.get('hedges', []):
        if hedge.get('status') == 'CLOSED':
            for side in ('ce', 'pe'):
                leg = hedge.get(side, {})
                total_pnl += leg.get('realized_pnl', 0.0) - leg.get('fees_paid', 0.0)
        else:
            for side in ('ce', 'pe'):
                leg = hedge.get(side, {})
                if not leg:
                    continue
                entry = leg.get('entry_premium', 0.0)
                current = leg.get('current_premium')
                lots = leg.get('lots', 0)
                fees = leg.get('fees_paid', 0.0)
                if current is None:
                    incomplete_legs.append(f"Hedge {hedge.get('hedge_id')}/{side}")
                else:
                    total_pnl += compute_position_pnl(entry, current, lots, 'LONG') - fees

    if incomplete_legs:
        raise PnLIncompleteError(
            f"Missing current_premium for: {', '.join(incomplete_legs)}"
        )

    return round(total_pnl, 4)


# ── Portfolio delta ────────────────────────────────────────────────────────────

def compute_portfolio_delta(session: Dict[str, Any]) -> float:
    """
    Compute signed portfolio delta (short weighted average).

    delta = weighted_sum(|delta| × lots) for ACTIVE shorts / total_active_lots
    Sign: positive = net long delta (CE exposure), negative = net short delta (PE exposure).

    Returns 0.0 if no active positions.
    """
    total_lots = 0
    weighted_delta = 0.0

    for tranche in session.get('tranches', []):
        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg or leg.get('status') != 'ACTIVE':
                continue
            lots = leg.get('lots', 0)
            delta = leg.get('current_delta') or leg.get('entry_delta', 0.0)
            sign = 1.0 if side == 'ce' else -1.0
            weighted_delta += sign * abs(delta) * lots
            total_lots += lots

    if total_lots == 0:
        return 0.0

    return round(weighted_delta / total_lots, 4)


# ── Lot imbalance ──────────────────────────────────────────────────────────────

def compute_lot_imbalance(session: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute CE vs PE lot imbalance across active deployment tranches.

    Returns:
      {
        'total_ce_lots': int,
        'total_pe_lots': int,
        'imbalance_pct': float,  # abs(ce - pe) / max(ce, pe) × 100
      }
    """
    ce_lots = 0
    pe_lots = 0

    for tranche in session.get('tranches', []):
        if tranche.get('type') != 'deployment':
            continue
        ce_leg = tranche.get('ce', {})
        pe_leg = tranche.get('pe', {})
        if ce_leg.get('status') == 'ACTIVE':
            ce_lots += ce_leg.get('lots', 0)
        if pe_leg.get('status') == 'ACTIVE':
            pe_lots += pe_leg.get('lots', 0)

    max_lots = max(ce_lots, pe_lots, 1)
    imbalance_pct = abs(ce_lots - pe_lots) / max_lots * 100.0

    return {
        'total_ce_lots': ce_lots,
        'total_pe_lots': pe_lots,
        'imbalance_pct': round(imbalance_pct, 2),
    }


# ── DTE calculation ────────────────────────────────────────────────────────────

def compute_dte_days(expiry_datetime_iso: Optional[str]) -> float:
    """
    Compute days to expiry from an ISO UTC datetime string.

    Returns -1.0 if expiry_datetime_iso is None (session not yet configured).
    Uses fractional days (e.g. 6.75 means 6h 18m remaining).
    """
    if not expiry_datetime_iso:
        return -1.0
    try:
        expiry = datetime.fromisoformat(expiry_datetime_iso)
        now = datetime.now(timezone.utc)
        if expiry.tzinfo is None:
            # Should not happen — expiry_datetime must have tz. Log and assume UTC.
            log.warning("expiry_datetime has no timezone — assuming UTC")
            expiry = expiry.replace(tzinfo=timezone.utc)
        delta = expiry - now
        return max(0.0, delta.total_seconds() / 86400.0)
    except Exception as exc:
        log.error(f"compute_dte_days failed: {exc}")
        return -1.0


# ── Hard stop recalculation ────────────────────────────────────────────────────

def recalc_hard_stop(session: Dict[str, Any]) -> float:
    """
    Recalculate hard_stop_usd from current total_premium_collected.

    hard_stop_usd = hard_stop_multiplier × total_premium_collected

    Called every beat so hard stop scales up as more premium is collected.
    Returns the new hard_stop_usd value (does NOT mutate session — caller updates).

    Spec: MMMX_COMPLETE.md Section 3 (Hard Stop).
    """
    multiplier = session.get('params', {}).get('hard_stop_multiplier', 2.0)
    premium = session.get('total_premium_collected', 0.0)
    return round(multiplier * premium, 4)


# ── Black-Scholes fair value ───────────────────────────────────────────────────

def black_scholes_fair_value(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    iv: float,
    risk_free_rate: float = 0.05,
    option_type: str = 'call',
) -> float:
    """
    Black-Scholes European option price.

    Args:
        spot: Current underlying price (USD).
        strike: Option strike price (USD).
        time_to_expiry_years: Time to expiry in years (DTE / 365).
        iv: Implied volatility (annualized, e.g. 0.80 for 80%).
        risk_free_rate: Annualized risk-free rate (default 5%).
        option_type: 'call' or 'put'.

    Returns:
        Fair value in USD per BTC (multiply by lots × LOT_SIZE_BTC for USD position value).

    Used by fairness gate (G3) to reject orders where exchange mid-price
    deviates more than fairness_threshold_pct from BS theoretical price.
    """
    if time_to_expiry_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return 0.0

    sqrt_t = math.sqrt(time_to_expiry_years)
    log_sk = math.log(spot / strike)

    d1 = (log_sk + (risk_free_rate + 0.5 * iv ** 2) * time_to_expiry_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    nd1 = _norm_cdf(d1)
    nd2 = _norm_cdf(d2)

    if option_type.lower() == 'call':
        price = spot * nd1 - strike * math.exp(-risk_free_rate * time_to_expiry_years) * nd2
    else:  # put
        price = (
            strike * math.exp(-risk_free_rate * time_to_expiry_years) * (1 - nd2)
            - spot * (1 - nd1)
        )

    return max(0.0, round(price, 4))


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erfc for accuracy."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


# ── Fairness gate check ────────────────────────────────────────────────────────

def check_fairness_gate(
    mid_price: float,
    bs_fair_value: float,
    threshold_pct: float,
) -> Tuple[bool, float]:
    """
    Check if mid_price is within threshold_pct of BS fair value.

    Returns:
        (passes, deviation_pct)
        passes=True means the price is fair (order should proceed).

    Spec: MMMX_COMPLETE.md (G3 — Fairness Gate).
    """
    if bs_fair_value <= 0:
        # Cannot compute — let the order through (don't block on bad IV data)
        return True, 0.0
    deviation_pct = abs(mid_price - bs_fair_value) / bs_fair_value * 100.0
    passes = deviation_pct <= threshold_pct
    return passes, round(deviation_pct, 2)


# ── Whipsaw-adjusted deployment params ────────────────────────────────────────

def apply_whipsaw_to_deployment(
    whipsaw_score: int,
    base_move_pct: float,
    base_lots: int,
    caution_score: int = 2,
    restrict_score: int = 3,
    cooldown_score: int = 4,
) -> Dict[str, Any]:
    """
    Compute whipsaw-adjusted deployment thresholds.

    Spec: MMMX_COMPLETE.md Section 2 (Whipsaw Guard).

    Returns:
        {
          'skip': bool,             # True if COOLDOWN — no deployment
          'move_pct': float,        # Adjusted move threshold
          'lots': int,              # Adjusted lot size (5 in RESTRICT, else base)
          'level': str,             # 'NORMAL'|'CAUTION'|'RESTRICT'|'COOLDOWN'
        }
    """
    if whipsaw_score >= cooldown_score:
        return {'skip': True, 'move_pct': base_move_pct, 'lots': 0, 'level': 'COOLDOWN'}
    elif whipsaw_score >= restrict_score:
        return {
            'skip': False,
            'move_pct': round(base_move_pct * 2.0, 4),
            'lots': max(5, base_lots // 2),
            'level': 'RESTRICT',
        }
    elif whipsaw_score >= caution_score:
        return {
            'skip': False,
            'move_pct': round(base_move_pct * 1.5, 4),
            'lots': base_lots,
            'level': 'CAUTION',
        }
    else:
        return {
            'skip': False,
            'move_pct': base_move_pct,
            'lots': base_lots,
            'level': 'NORMAL',
        }


# ── Deployment queue logic ─────────────────────────────────────────────────────

def compute_deployment_queue_size(
    spot_move_pct: float,
    adjusted_move_pct: float,
    tranches_remaining: int,
) -> int:
    """
    Compute how many tranches should be queued for a given spot move.

    num_eligible = floor(spot_move_pct / adjusted_move_pct)
    Capped by tranches_remaining and a maximum of 5 at a time (safety cap).

    Spec: MMMX_COMPLETE.md Section 2 (Deployment Eligibility Queue).
    """
    if adjusted_move_pct <= 0 or spot_move_pct <= 0:
        return 0
    eligible = math.floor(spot_move_pct / adjusted_move_pct)
    return min(eligible, tranches_remaining, 5)


def check_deployment_retracement(
    current_spot: float,
    queue_triggered_spot: float,
    queue_direction: str,
    retracement_threshold_pct: float = 0.5,
) -> Tuple[bool, float]:
    """
    Check whether the market has retraced against the queued move direction.

    Returns:
        (should_clear_queue, retracement_pct)

    Spec: MMMX_COMPLETE.md Section 2 (Deployment Queue — retracement check).
    """
    if not queue_triggered_spot or not queue_direction:
        return False, 0.0

    if queue_direction == 'UP':
        retracement = max(
            0.0,
            (queue_triggered_spot - current_spot) / queue_triggered_spot * 100.0
        )
    else:  # DOWN
        retracement = max(
            0.0,
            (current_spot - queue_triggered_spot) / queue_triggered_spot * 100.0
        )

    should_clear = retracement > retracement_threshold_pct
    return should_clear, round(retracement, 3)


# ── Hedge premium / max loss ───────────────────────────────────────────────────

def compute_hedge_cost(
    ce_premium: float,
    pe_premium: float,
    lots: int,
) -> float:
    """
    Compute total hedge cost (what we pay to buy the protective options).

    hedge_premium_paid = (ce_premium + pe_premium) × lots × LOT_SIZE_BTC
    """
    return round((ce_premium + pe_premium) * lots * LOT_SIZE_BTC, 4)


def compute_spread_max_loss(
    sold_strike: float,
    hedge_strike: float,
    lots: int,
) -> float:
    """
    Maximum loss if the spread is fully hit (both legs ITM at expiry).

    max_loss = abs(sold_strike - hedge_strike) × lots × LOT_SIZE_BTC
    This is the theoretical worst-case cap from the spread structure.
    """
    return round(abs(sold_strike - hedge_strike) * lots * LOT_SIZE_BTC, 4)


# ── Recovery lot calculation ───────────────────────────────────────────────────

def compute_recovery_lots(
    loss_usd: float,
    ce_premium: float,
    pe_premium: float,
) -> Tuple[int, int]:
    """
    Calculate CE and PE recovery lots to offset an ATM shield loss.

    ce_recovery = ceil(loss × 0.30 / (ce_premium × LOT_SIZE_BTC))
    pe_recovery = ceil(loss × 0.70 / (pe_premium × LOT_SIZE_BTC))

    Spec: MMMX_COMPLETE.md Section 6 (ATM Shield — Step 4).
    """
    if ce_premium <= 0 or pe_premium <= 0:
        return 0, 0

    ce_lots = math.ceil(loss_usd * 0.30 / (ce_premium * LOT_SIZE_BTC))
    pe_lots = math.ceil(loss_usd * 0.70 / (pe_premium * LOT_SIZE_BTC))

    return max(0, ce_lots), max(0, pe_lots)


# ── Danger-side classifier ─────────────────────────────────────────────────────

def classify_danger_side(tranche: Dict[str, Any]) -> str:
    """
    Return which leg is currently the 'danger' side (has unrealized loss).

    Returns: 'ce' | 'pe' | 'both' | 'none'

    Logic: A SHORT leg has unrealized loss when current_premium > entry_premium
    (the option has gained value against us).

    Pure function — for logging/reporting only.
    close_all closes ALL ACTIVE legs regardless of this value.
    """
    ce_leg = tranche.get('ce', {})
    pe_leg = tranche.get('pe', {})

    ce_losing = False
    pe_losing = False

    ce_entry = ce_leg.get('entry_premium')
    ce_current = ce_leg.get('current_premium')
    if ce_entry is not None and ce_current is not None:
        # SHORT: losing when current > entry (option gained value against us)
        ce_losing = ce_current > ce_entry

    pe_entry = pe_leg.get('entry_premium')
    pe_current = pe_leg.get('current_premium')
    if pe_entry is not None and pe_current is not None:
        pe_losing = pe_current > pe_entry

    if ce_losing and pe_losing:
        return 'both'
    elif ce_losing:
        return 'ce'
    elif pe_losing:
        return 'pe'
    else:
        return 'none'
