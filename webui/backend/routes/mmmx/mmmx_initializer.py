"""
MMMX Initializer — Entry Gates, Strike Scanning, and Tranche Deployment

Handles session entry validation, strike selection, and all-or-nothing CE+PE
deployment for both manual Tranche 1 and automatic Tranche 2–10.

Spec: MMMX_COMPLETE.md — Deployment Engine, Entry Gates, Eligibility Queue.

Key functions:
  check_entry_gates(params, live_data) → EntryVerdict
      Hard gates — ALL must pass before session transitions to RUNNING.
  scan_strikes(asset, expiry, otm_pct, chain, spot) → StrikeCandidates
      Selects nearest CE/PE strikes from live chain; no hardcoded step sizes.
  deploy_manual_tranche1(session, executor, audit, ...) → dict
      Operator-confirmed sell of Tr1 CE+PE; all-or-nothing with rollback.
  check_deploy_conditions(session, metrics) → DeployDecision
      Evaluates whipsaw-adjusted move/IV triggers each beat.
  populate_eligibility_queue(session, spot_move_pct, current_spot) → None
      Fills session['deployment_eligible_tranches'] on trigger fire.
  clear_queue_on_retrace(session, current_spot) → bool
      Clears queue if market has retraced > 0.5% against queue direction.
  enforce_frequency_gate(session) → bool
      Blocks deployment if max_deployments_per_day reached.
  enforce_fairness_gate(session, strike_quote, bs_price) → bool
      Blocks deployment if mid-price deviates too far from BS theoretical.
  execute_tranche_deploy(session, executor, audit, spot, iv_rank, chain, save_fn) → dict | None
      Full auto-deploy: gates → scan → CE sell → PE sell (rollback on PE fail) → save.

Key invariants:
  - tranches_deployed / tranches_remaining change ONLY on successful deployment.
  - ce_reserve_remaining / pe_reserve_remaining NOT touched by deployment.
  - last_deployment_spot and last_deployment_iv_rank MUST be updated after every deploy.
  - All-or-nothing: CE sold → PE fails → buy back CE immediately; no partial state.
  - Isolation: ZERO imports from routes.mmm.* in this file.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from .mmmx_constants import (
    LOT_SIZE_BTC,
    SMART_EXECUTE_REPRICE_ATTEMPTS,
    SessionStatus,
    TrncType,
    TRANCHE_COUNT,
    DEPLOYMENT_RETRACEMENT_THRESHOLD_PCT,
)
from .mmmx_engine import (
    recalc_hard_stop,
    check_fairness_gate,
    apply_whipsaw_to_deployment,
    compute_deployment_queue_size,
    check_deployment_retracement,
    compute_dte_days,
)
from .mmmx_state import make_tranche, transition_status
from .mmmx_websocket import emit_tranche_deployed, emit_deployment_queue
from .mmmx_activity import log_activity
from .mmmx_telegram import (
    alert_tranche_deployed,
    alert_deployment_queue,
    alert_queue_retrace,
)

log = logging.getLogger('mmmx_initializer')


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class EntryVerdict:
    """Result of check_entry_gates()."""
    ok:           bool
    failed_gates: List[str]  = field(default_factory=list)
    messages:     List[str]  = field(default_factory=list)


@dataclass
class StrikeCandidates:
    """Nearest CE/PE strikes found by scan_strikes()."""
    ce_strike:  float
    ce_symbol:  str
    ce_delta:   float
    ce_bid:     float
    ce_ask:     float
    pe_strike:  float
    pe_symbol:  str
    pe_delta:   float
    pe_bid:     float
    pe_ask:     float


@dataclass
class DeployDecision:
    """Result of check_deploy_conditions()."""
    should_deploy:    bool
    reason:           str
    adjusted_size:    int   = 0
    adjusted_move_pct: float = 2.0
    spot_move_pct:    float = 0.0


# ── check_entry_gates ──────────────────────────────────────────────────────────

def check_entry_gates(
    params: Dict[str, Any],
    live_data: Dict[str, Any],
) -> EntryVerdict:
    """
    Validate all hard entry gates before the first deployment.

    Gates (ALL must pass):
      1. DTE in [entry_dte_min, entry_dte_max] (default 20–45)
      2. IV rank >= entry_iv_rank_min (default 50)
      3. Margin utilisation < 80%
      4. Liquidity: bid depth >= 5 lots AND spread < 10%

    live_data keys expected:
      'dte': float               (days to expiry)
      'iv_rank': float           (0–100)
      'margin_utilisation': float (0–100 %)
      'bid_depth_lots': int       (CE + PE combined, or per-side dict)
      'spread_pct': float         (ask-bid)/mid × 100

    Returns:
        EntryVerdict(ok=True) if all pass.
        EntryVerdict(ok=False, failed_gates=[...], messages=[...]) if any fail.

    Spec: MMMX_COMPLETE.md — Entry Gates (G1, G2, G3, G4).
    """
    failed  = []
    msgs    = []

    dte_min     = int(params.get('entry_dte_min', 20))
    dte_max     = int(params.get('entry_dte_max', 45))
    iv_min      = float(params.get('entry_iv_rank_min', 50))

    dte              = float(live_data.get('dte', 0))
    iv_rank          = float(live_data.get('iv_rank', 0))
    margin_util      = float(live_data.get('margin_utilisation', 0))
    bid_depth_lots   = int(live_data.get('bid_depth_lots', 0))
    spread_pct       = float(live_data.get('spread_pct', 999.0))

    # Gate 1: DTE
    if not (dte_min <= dte <= dte_max):
        failed.append('DTE')
        msgs.append(
            f"DTE {dte:.1f} out of range [{dte_min}, {dte_max}]."
        )

    # Gate 2: IV rank
    if iv_rank < iv_min:
        failed.append('IV_RANK')
        msgs.append(
            f"IV rank {iv_rank:.1f} < required {iv_min}."
        )

    # Gate 3: Margin
    if margin_util >= 80.0:
        failed.append('MARGIN')
        msgs.append(
            f"Margin utilisation {margin_util:.1f}% >= 80% limit."
        )

    # Gate 4a: Bid depth
    if bid_depth_lots < 5:
        failed.append('BID_DEPTH')
        msgs.append(
            f"Bid depth {bid_depth_lots} lots < required 5."
        )

    # Gate 4b: Spread
    if spread_pct >= 10.0:
        failed.append('SPREAD')
        msgs.append(
            f"Spread {spread_pct:.1f}% >= 10% limit."
        )

    return EntryVerdict(ok=len(failed) == 0, failed_gates=failed, messages=msgs)


# ── scan_strikes ───────────────────────────────────────────────────────────────

def scan_strikes(
    asset: str,
    expiry: str,
    otm_pct: float,
    chain: List[Dict[str, Any]],
    spot: float,
) -> Optional[StrikeCandidates]:
    """
    Find nearest CE and PE strikes from the live options chain.

    Target strikes:
      CE target = spot × (1 + otm_pct / 100)   — OTM call
      PE target = spot × (1 - otm_pct / 100)   — OTM put

    Selects the chain entry whose strike is closest to each target.
    No hardcoded step sizes — works with irregular ladder spacing.

    Args:
        asset:   Underlying asset (e.g. 'BTC') — used for filtering if needed.
        expiry:  Expiry identifier (e.g. '280326') — used for filtering if needed.
        otm_pct: OTM distance in percent (e.g. 15.0 for 15% OTM).
        chain:   List of dicts: [{'strike', 'symbol', 'bid', 'ask', 'delta'}, ...]
        spot:    Current underlying price in USD.

    Returns:
        StrikeCandidates or None if chain is empty.

    Spec: MMMX_COMPLETE.md — scan_strikes.
    """
    if not chain or spot <= 0:
        return None

    ce_target = spot * (1 + otm_pct / 100.0)
    pe_target = spot * (1 - otm_pct / 100.0)

    # Split chain into calls and puts by inspecting symbol prefix or delta sign
    # CE: delta > 0 or symbol starts with 'C-'
    # PE: delta < 0 or symbol starts with 'P-'
    # Fall back to strike comparison if delta missing
    calls = []
    puts  = []

    for entry in chain:
        sym   = str(entry.get('symbol', ''))
        delta = entry.get('delta')
        if sym.upper().startswith('C-'):
            calls.append(entry)
        elif sym.upper().startswith('P-'):
            puts.append(entry)
        elif delta is not None:
            if float(delta) >= 0:
                calls.append(entry)
            else:
                puts.append(entry)
        else:
            # No way to distinguish — put in both buckets
            calls.append(entry)
            puts.append(entry)

    if not calls or not puts:
        # Try treating all as mixed (some providers don't prefix)
        calls = chain
        puts  = chain

    # Select CE: call strike closest to ce_target
    best_ce = min(calls, key=lambda e: abs(float(e.get('strike', 0)) - ce_target))
    # Select PE: put strike closest to pe_target
    best_pe = min(puts,  key=lambda e: abs(float(e.get('strike', 0)) - pe_target))

    ce_bid = float(best_ce.get('bid', 0.0))
    ce_ask = float(best_ce.get('ask', 0.0))
    pe_bid = float(best_pe.get('bid', 0.0))
    pe_ask = float(best_pe.get('ask', 0.0))

    return StrikeCandidates(
        ce_strike = float(best_ce.get('strike', 0.0)),
        ce_symbol = str(best_ce.get('symbol', '')),
        ce_delta  = float(best_ce.get('delta', 0.0)),
        ce_bid    = ce_bid,
        ce_ask    = ce_ask,
        pe_strike = float(best_pe.get('strike', 0.0)),
        pe_symbol = str(best_pe.get('symbol', '')),
        pe_delta  = float(best_pe.get('delta', 0.0)),
        pe_bid    = pe_bid,
        pe_ask    = pe_ask,
    )


# ── deploy_manual_tranche1 ────────────────────────────────────────────────────

async def deploy_manual_tranche1(
    session: Dict[str, Any],
    executor: Any,
    audit: Any,
    ce_symbol: str,
    pe_symbol: str,
    ce_lots: int,
    pe_lots: int,
    spot: float,
    iv_rank: float,
    ce_strike: float,
    ce_premium: float,
    ce_delta: float,
    pe_strike: float,
    pe_premium: float,
    pe_delta: float,
    entry_dvol: float = 0.0,
    save_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Sell Tranche 1 CE + PE via smart_execute — operator-confirmed manual deploy.

    All-or-nothing: if PE sell fails, CE is bought back immediately and the
    session state is NOT mutated (no tranche appended, counters unchanged).

    On success:
      - Tranche 1 appended to session['tranches']
      - hard_stop_usd initialised = hard_stop_multiplier × premium_collected
      - last_deployment_spot and last_deployment_iv_rank set
      - tranches_deployed += 1, tranches_remaining -= 1
      - deployments_last_24h updated
      - Session transitions GATES_PASSED → RUNNING
      - Telegram + audit + emit

    Returns:
        Deployed tranche dict on success, or {'success': False, 'reason': str}.

    Spec: MMMX_COMPLETE.md — deploy_manual_tranche1.
    """
    session_id = session.get('session_id', '')
    tranche_id = 1   # Tranche 1 is always the first manual deployment

    log.info(
        f"[Initializer][{session_id[:8]}] deploy_manual_tranche1: "
        f"CE {ce_symbol}×{ce_lots} | PE {pe_symbol}×{pe_lots} | spot={spot}"
    )

    # -- CE sell ─────────────────────────────────────────────────────────────────
    ce_result = await executor.smart_execute(
        symbol=ce_symbol,
        side='sell',
        size=ce_lots,
        reduce_only=False,
        max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
        session_id=session_id,
        tranche_id=tranche_id,
        action='DEPLOY_CE_TR1',
    )

    if not ce_result.success:
        log.error(
            f"[Initializer][{session_id[:8]}] Tr1 CE sell failed: {ce_result.reason}"
        )
        return {'success': False, 'reason': f"CE sell failed: {ce_result.reason}"}

    # -- PE sell ─────────────────────────────────────────────────────────────────
    pe_result = await executor.smart_execute(
        symbol=pe_symbol,
        side='sell',
        size=pe_lots,
        reduce_only=False,
        max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
        session_id=session_id,
        tranche_id=tranche_id,
        action='DEPLOY_PE_TR1',
    )

    if not pe_result.success:
        # Rollback CE: buy back immediately
        log.error(
            f"[Initializer][{session_id[:8]}] Tr1 PE sell failed: {pe_result.reason}. "
            "Rolling back CE."
        )
        await _rollback_ce(executor, ce_symbol, ce_lots, session_id, tranche_id)
        return {'success': False, 'reason': f"PE sell failed: {pe_result.reason}"}

    # -- Both legs filled — build tranche and update session ─────────────────────
    ce_fill_price = float(ce_result.avg_price or ce_premium)
    pe_fill_price = float(pe_result.avg_price or pe_premium)

    tranche = make_tranche(
        tranche_id=tranche_id,
        entry_spot=spot,
        entry_dvol=entry_dvol,
        entry_iv_rank=iv_rank,
        ce_symbol=ce_symbol,
        ce_strike=ce_strike,
        ce_lots=ce_lots,
        ce_premium=ce_fill_price,
        ce_delta=ce_delta,
        pe_symbol=pe_symbol,
        pe_strike=pe_strike,
        pe_lots=pe_lots,
        pe_premium=pe_fill_price,
        pe_delta=pe_delta,
        tranche_type=TrncType.DEPLOYMENT,
    )

    # Record fees
    total_fees = float(ce_result.fees_paid or 0.0) + float(pe_result.fees_paid or 0.0)
    tranche['ce']['fees_paid'] = float(ce_result.fees_paid or 0.0)
    tranche['pe']['fees_paid'] = float(pe_result.fees_paid or 0.0)

    _apply_deploy_state(session, tranche, spot, iv_rank, total_fees)

    # Transition GATES_PASSED → RUNNING (idempotent if already RUNNING)
    if session.get('status') == SessionStatus.GATES_PASSED:
        try:
            transition_status(session, SessionStatus.RUNNING, reason='manual_tr1_deploy')
        except ValueError as exc:
            log.warning(f"[Initializer] Status transition warning: {exc}")

    # G13: mid-beat persist
    if save_fn is not None:
        try:
            ok = save_fn(session)
            if not ok:
                log.error(
                    f"[Initializer][{session_id[:8]}] G13 persist failed after Tr1 deploy."
                )
        except Exception as exc:
            log.error(f"[Initializer] save_fn raised: {exc}")

    _emit_and_alert(session, tranche, spot)

    log.info(
        f"[Initializer][{session_id[:8]}] Tr1 deployed. "
        f"premium={tranche['premium_collected']:.4f} USD, "
        f"hard_stop={session['hard_stop_usd']:.4f}"
    )

    return tranche


# ── check_deploy_conditions ───────────────────────────────────────────────────

def check_deploy_conditions(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
) -> DeployDecision:
    """
    Evaluate whether auto-deployment conditions are met this beat.

    Conditions (all must pass):
      (a) tranches_remaining > 0
      (b) whipsaw_score < COOLDOWN threshold (not currently in skip window)
      (c) Spot moved >= adjusted_move_pct from last_deployment_spot
          OR iv_rank increased >= tranche_deploy_iv_delta

    Applies whipsaw adjustment to thresholds before evaluation.

    Returns DeployDecision with should_deploy=True/False and diagnostic reason.

    Spec: MMMX_COMPLETE.md — check_deploy_conditions.
    """
    params              = session.get('params', {})
    base_move_pct       = float(params.get('tranche_deploy_move_pct', 2.0))
    iv_delta_threshold  = float(params.get('tranche_deploy_iv_delta', 10))
    base_lots           = int(params.get('total_budget_lots', 100)) // TRANCHE_COUNT

    tranches_remaining  = int(session.get('tranches_remaining', 0))
    last_spot           = session.get('last_deployment_spot')
    last_iv             = session.get('last_deployment_iv_rank')
    current_spot        = metrics.get('spot_price')
    current_iv          = metrics.get('iv_rank')

    # (a) Capacity check
    if tranches_remaining <= 0:
        return DeployDecision(
            should_deploy=False,
            reason='no_tranches_remaining',
            adjusted_size=0,
            adjusted_move_pct=base_move_pct,
        )

    # (b) Whipsaw cooldown check
    from . import mmmx_whipsaw as _ws
    if _ws.in_cooldown(session):
        return DeployDecision(
            should_deploy=False,
            reason='whipsaw_cooldown',
            adjusted_size=0,
            adjusted_move_pct=base_move_pct,
        )

    # Apply whipsaw adjustments to thresholds
    adjusted_move_pct, adjusted_size = _ws.apply_to_deployment(
        session, base_move_pct, base_lots
    )
    if adjusted_move_pct is None:
        return DeployDecision(
            should_deploy=False,
            reason='whipsaw_cooldown',
            adjusted_size=0,
            adjusted_move_pct=base_move_pct,
        )

    # (c) Trigger check: spot move OR IV delta
    spot_triggered = False
    iv_triggered   = False
    spot_move_pct  = 0.0

    if last_spot and current_spot and current_spot > 0 and last_spot > 0:
        spot_move_pct = abs(current_spot - last_spot) / last_spot * 100.0
        spot_triggered = spot_move_pct >= adjusted_move_pct

    if last_iv is not None and current_iv is not None:
        iv_increase = float(current_iv) - float(last_iv)
        iv_triggered = iv_increase >= iv_delta_threshold

    if not (spot_triggered or iv_triggered):
        return DeployDecision(
            should_deploy=False,
            reason=(
                f"trigger not met: spot_move={spot_move_pct:.2f}%<{adjusted_move_pct}%, "
                f"iv_delta not sufficient"
            ),
            adjusted_size=adjusted_size,
            adjusted_move_pct=adjusted_move_pct,
            spot_move_pct=spot_move_pct,
        )

    trigger_reason = 'spot_move' if spot_triggered else 'iv_delta'
    return DeployDecision(
        should_deploy=True,
        reason=trigger_reason,
        adjusted_size=adjusted_size,
        adjusted_move_pct=adjusted_move_pct,
        spot_move_pct=spot_move_pct,
    )


# ── populate_eligibility_queue ────────────────────────────────────────────────

def populate_eligibility_queue(
    session: Dict[str, Any],
    spot_move_pct: float,
    current_spot: Optional[float] = None,
    last_deployment_spot: Optional[float] = None,
) -> None:
    """
    Fill session['deployment_eligible_tranches'] based on the size of the spot move.

    num_eligible = floor(spot_move_pct / adjusted_move_pct), capped at tranches_remaining.
    Appends the next N sequential tranche IDs.

    Records:
      deployment_queue_triggered_spot = current_spot
      deployment_queue_triggered_at   = now (ISO UTC)
      deployment_queue_direction      = 'UP' or 'DOWN'

    Only appends IDs not already in the queue.

    Spec: MMMX_COMPLETE.md — Deployment Eligibility Queue.
    """
    params             = session.get('params', {})
    base_move_pct      = float(params.get('tranche_deploy_move_pct', 2.0))
    base_lots          = int(params.get('total_budget_lots', 100)) // TRANCHE_COUNT
    tranches_deployed  = int(session.get('tranches_deployed', 0))
    tranches_remaining = int(session.get('tranches_remaining', 0))

    from . import mmmx_whipsaw as _ws
    adjusted_move_pct, _ = _ws.apply_to_deployment(session, base_move_pct, base_lots)
    if adjusted_move_pct is None:
        adjusted_move_pct = base_move_pct  # COOLDOWN; queue will be empty anyway

    num_eligible = compute_deployment_queue_size(
        spot_move_pct, adjusted_move_pct, tranches_remaining
    )

    existing_queue = session.get('deployment_eligible_tranches', [])

    # Build list of next sequential tranche IDs (1-indexed deployment IDs)
    next_id = tranches_deployed + 1
    for i in range(num_eligible):
        tid = next_id + i
        if tid <= TRANCHE_COUNT and tid not in existing_queue:
            existing_queue.append(tid)

    # Cap to tranches_remaining
    session['deployment_eligible_tranches'] = existing_queue[:tranches_remaining]

    # Record trigger context for retrace detection
    now = datetime.now(timezone.utc).isoformat()
    session['deployment_queue_triggered_at'] = now

    if current_spot is not None:
        session['deployment_queue_triggered_spot'] = current_spot

        # Determine direction relative to last deployment spot
        ref_spot = last_deployment_spot or session.get('last_deployment_spot')
        if ref_spot and ref_spot > 0:
            direction = 'UP' if current_spot >= ref_spot else 'DOWN'
        else:
            direction = 'UP'
        session['deployment_queue_direction'] = direction

    queue_size = len(session['deployment_eligible_tranches'])
    log.info(
        f"[Initializer] Eligibility queue populated: {queue_size} tranches "
        f"({spot_move_pct:.2f}% move, adjusted_threshold={adjusted_move_pct:.2f}%)"
    )

    if queue_size > 0:
        session_id = session.get('session_id', '')
        try:
            alert_deployment_queue(session_id, queue_size, spot_move_pct)
        except Exception:
            pass
        try:
            emit_deployment_queue(session_id, {
                'queue': list(session['deployment_eligible_tranches']),
                'triggered_spot': current_spot,
                'direction': session.get('deployment_queue_direction'),
                'spot_move_pct': spot_move_pct,
            })
        except Exception:
            pass


# ── clear_queue_on_retrace ────────────────────────────────────────────────────

def clear_queue_on_retrace(
    session: Dict[str, Any],
    current_spot: float,
) -> bool:
    """
    Clear deployment_eligible_tranches if the market has retraced against the
    queued move direction by >= DEPLOYMENT_RETRACEMENT_THRESHOLD_PCT (0.5%).

    Returns True if queue was cleared, False otherwise.

    Spec: MMMX_COMPLETE.md — Deployment Queue: retracement check.
    """
    queue = session.get('deployment_eligible_tranches', [])
    if not queue:
        return False

    triggered_spot = session.get('deployment_queue_triggered_spot')
    direction      = session.get('deployment_queue_direction')

    if not triggered_spot:
        return False

    should_clear, retrace_pct = check_deployment_retracement(
        current_spot=current_spot,
        queue_triggered_spot=float(triggered_spot),
        queue_direction=direction or 'UP',
        retracement_threshold_pct=DEPLOYMENT_RETRACEMENT_THRESHOLD_PCT,
    )

    if should_clear:
        cleared_count = len(queue)
        session['deployment_eligible_tranches'] = []
        log.warning(
            f"[Initializer] Queue cleared: {cleared_count} tranches removed. "
            f"Retrace {retrace_pct:.2f}% against {direction} queue."
        )
        session_id = session.get('session_id', '')
        try:
            alert_queue_retrace(session_id, retrace_pct, cleared_count)
        except Exception:
            pass
        return True

    return False


# ── enforce_frequency_gate ────────────────────────────────────────────────────

def enforce_frequency_gate(session: Dict[str, Any]) -> bool:
    """
    Check if a new deployment is allowed under the rolling 24-hour frequency limit.

    Returns True if allowed (count < max_deployments_per_day).
    Returns False if the limit would be exceeded.

    Uses deployments_last_24h (list of ISO timestamps) — rolling window, not calendar day.

    Spec: MMMX_COMPLETE.md — enforce_frequency_gate (Q30, A5).
    """
    params         = session.get('params', {})
    max_per_day    = int(params.get('max_deployments_per_day', 2))
    cutoff         = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_iso     = cutoff.isoformat()

    deployments    = session.get('deployments_last_24h', [])
    recent_count   = sum(1 for ts in deployments if ts >= cutoff_iso)

    if recent_count >= max_per_day:
        log.info(
            f"[Initializer] Frequency gate BLOCKED: "
            f"{recent_count} deployments in last 24h >= limit {max_per_day}."
        )
        return False

    return True


# ── enforce_fairness_gate ─────────────────────────────────────────────────────

def enforce_fairness_gate(
    session: Dict[str, Any],
    strike_quote: float,
    bs_price: float,
) -> bool:
    """
    Check if the market quote is within fairness_threshold_pct of the BS fair value.

    Returns True if the order should proceed (price is fair or gate is disabled).
    Returns False if the deviation exceeds the threshold.

    When bs_price <= 0 (IV data unavailable), the gate always passes.

    Spec: MMMX_COMPLETE.md — enforce_fairness_gate (G3).
    """
    params = session.get('params', {})
    if not params.get('fairness_gate_enabled', True):
        return True

    threshold = float(params.get('fairness_threshold_pct', 10.0))
    passes, deviation_pct = check_fairness_gate(strike_quote, bs_price, threshold)

    if not passes:
        log.info(
            f"[Initializer] Fairness gate BLOCKED: "
            f"quote={strike_quote:.2f}, bs={bs_price:.2f}, "
            f"deviation={deviation_pct:.2f}% > {threshold}%"
        )

    return passes


# ── execute_tranche_deploy ────────────────────────────────────────────────────

async def execute_tranche_deploy(
    session: Dict[str, Any],
    executor: Any,
    audit: Any,
    spot: float,
    iv_rank: float,
    chain: List[Dict[str, Any]],
    save_fn: Optional[Callable] = None,
) -> Optional[Dict[str, Any]]:
    """
    Auto-deploy the next tranche from the deployment_eligible_tranches queue.

    Full pre-flight:
      1. Pop tranche ID from queue (if queue empty → return None)
      2. enforce_frequency_gate → reject if exceeded
      3. scan_strikes → find CE/PE strikes from chain
      4. enforce_fairness_gate for CE and PE (if IV available)
      5. CE sell via smart_execute
      6. PE sell via smart_execute — on failure: rollback CE; push tranche_id back
      7. Update session state (tranche, counters, hard stop, baselines)
      8. G13 mid-beat persist via save_fn
      9. Telegram + audit + emit

    Returns deployed tranche dict, or None if deployment was skipped/failed.

    Spec: MMMX_COMPLETE.md — execute_tranche_deploy.
    """
    session_id = session.get('session_id', '')

    # Step 1: Pop from queue
    queue = session.get('deployment_eligible_tranches', [])
    if not queue:
        return None

    tranche_id = queue.pop(0)
    session['deployment_eligible_tranches'] = queue

    # Step 2: Frequency gate
    if not enforce_frequency_gate(session):
        # Put tranche_id back — it will try again next beat (or operator clears queue)
        session['deployment_eligible_tranches'] = [tranche_id] + queue
        log.info(
            f"[Initializer][{session_id[:8]}] "
            f"Tr{tranche_id} deployment blocked by frequency gate."
        )
        return None

    # Step 3: Scan strikes
    params       = session.get('params', {})
    otm_pct      = float(params.get('otm_distance_pct', 15.0))
    expiry       = str(session.get('expiry_ddmmyy', ''))
    base_lots    = int(params.get('total_budget_lots', 100)) // TRANCHE_COUNT

    strikes = scan_strikes(
        asset=str(session.get('symbol_base', 'BTC')),
        expiry=expiry,
        otm_pct=otm_pct,
        chain=chain,
        spot=spot,
    )

    if strikes is None:
        log.error(
            f"[Initializer][{session_id[:8]}] "
            f"scan_strikes returned None for Tr{tranche_id}. Empty chain?"
        )
        session['deployment_eligible_tranches'] = [tranche_id] + queue
        return None

    # Determine lot size (with whipsaw adjustment)
    from . import mmmx_whipsaw as _ws
    base_move = float(params.get('tranche_deploy_move_pct', 2.0))
    _, adjusted_size = _ws.apply_to_deployment(session, base_move, base_lots)
    if adjusted_size is None:
        # COOLDOWN — shouldn't reach here but guard anyway
        session['deployment_eligible_tranches'] = [tranche_id] + queue
        return None
    lots = max(1, adjusted_size)

    # Step 4: Fairness gate (best-effort — skip if IV unavailable)
    ce_mid = (strikes.ce_bid + strikes.ce_ask) / 2.0 if strikes.ce_ask > 0 else 0.0
    pe_mid = (strikes.pe_bid + strikes.pe_ask) / 2.0 if strikes.pe_ask > 0 else 0.0

    if ce_mid > 0:
        bs_ce = _compute_bs_price(session, spot, strikes.ce_strike, iv_rank, 'call')
        if not enforce_fairness_gate(session, ce_mid, bs_ce):
            log.info(
                f"[Initializer][{session_id[:8]}] Tr{tranche_id} CE fairness gate blocked."
            )
            session['deployment_eligible_tranches'] = [tranche_id] + queue
            return None

    if pe_mid > 0:
        bs_pe = _compute_bs_price(session, spot, strikes.pe_strike, iv_rank, 'put')
        if not enforce_fairness_gate(session, pe_mid, bs_pe):
            log.info(
                f"[Initializer][{session_id[:8]}] Tr{tranche_id} PE fairness gate blocked."
            )
            session['deployment_eligible_tranches'] = [tranche_id] + queue
            return None

    # Step 5: CE sell
    ce_result = await executor.smart_execute(
        symbol=strikes.ce_symbol,
        side='sell',
        size=lots,
        reduce_only=False,
        max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
        session_id=session_id,
        tranche_id=tranche_id,
        action=f'DEPLOY_CE_TR{tranche_id}',
    )

    if not ce_result.success:
        log.error(
            f"[Initializer][{session_id[:8]}] Tr{tranche_id} CE sell failed: "
            f"{ce_result.reason}. Deferring."
        )
        session['deployment_eligible_tranches'] = [tranche_id] + queue
        return None

    # Step 6: PE sell — rollback CE on failure
    pe_result = await executor.smart_execute(
        symbol=strikes.pe_symbol,
        side='sell',
        size=lots,
        reduce_only=False,
        max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
        session_id=session_id,
        tranche_id=tranche_id,
        action=f'DEPLOY_PE_TR{tranche_id}',
    )

    if not pe_result.success:
        log.error(
            f"[Initializer][{session_id[:8]}] Tr{tranche_id} PE sell failed: "
            f"{pe_result.reason}. Rolling back CE."
        )
        await _rollback_ce(executor, strikes.ce_symbol, lots, session_id, tranche_id)
        # Tranche ID NOT returned to queue — failed deployment is dropped
        return None

    # Step 7: Both fills — update session
    ce_fill = float(ce_result.avg_price or ce_mid or strikes.ce_bid)
    pe_fill = float(pe_result.avg_price or pe_mid or strikes.pe_bid)
    entry_dvol = float(session.get('_last_dvol', 0.0))

    tranche = make_tranche(
        tranche_id=tranche_id,
        entry_spot=spot,
        entry_dvol=entry_dvol,
        entry_iv_rank=iv_rank,
        ce_symbol=strikes.ce_symbol,
        ce_strike=strikes.ce_strike,
        ce_lots=lots,
        ce_premium=ce_fill,
        ce_delta=strikes.ce_delta,
        pe_symbol=strikes.pe_symbol,
        pe_strike=strikes.pe_strike,
        pe_lots=lots,
        pe_premium=pe_fill,
        pe_delta=strikes.pe_delta,
        tranche_type=TrncType.DEPLOYMENT,
    )

    total_fees = float(ce_result.fees_paid or 0.0) + float(pe_result.fees_paid or 0.0)
    tranche['ce']['fees_paid'] = float(ce_result.fees_paid or 0.0)
    tranche['pe']['fees_paid'] = float(pe_result.fees_paid or 0.0)

    _apply_deploy_state(session, tranche, spot, iv_rank, total_fees)

    # Step 8: G13 mid-beat persist
    if save_fn is not None:
        try:
            ok = save_fn(session)
            if not ok:
                log.error(
                    f"[Initializer][{session_id[:8]}] G13 persist failed after Tr{tranche_id}."
                )
        except Exception as exc:
            log.error(f"[Initializer] save_fn raised: {exc}")

    # Step 9: Signals
    _emit_and_alert(session, tranche, spot)

    log.info(
        f"[Initializer][{session_id[:8]}] Tr{tranche_id} auto-deployed. "
        f"premium={tranche['premium_collected']:.4f}, "
        f"tranches_deployed={session.get('tranches_deployed')}"
    )

    return tranche


# ── Private helpers ────────────────────────────────────────────────────────────

def _apply_deploy_state(
    session: Dict[str, Any],
    tranche: Dict[str, Any],
    spot: float,
    iv_rank: float,
    total_fees: float,
) -> None:
    """
    Mutate session after a successful CE+PE deployment.
    Called by both deploy_manual_tranche1 and execute_tranche_deploy.
    """
    # Append tranche
    session.setdefault('tranches', []).append(tranche)

    # Increment counters (deployment tranches only)
    session['tranches_deployed']  = int(session.get('tranches_deployed', 0)) + 1
    session['tranches_remaining'] = max(0, int(session.get('tranches_remaining', 0)) - 1)

    # Accumulate premium and lots
    lots = int(tranche['ce'].get('lots', 0))
    session['total_deployed_lots']   = int(session.get('total_deployed_lots', 0)) + lots * 2
    session['total_premium_collected'] = (
        float(session.get('total_premium_collected', 0.0)) + tranche['premium_collected']
    )

    # Hard stop scales with collected premium
    session['hard_stop_usd'] = recalc_hard_stop(session)

    # Mandatory baselines for next trigger evaluation
    session['last_deployment_spot']    = spot
    session['last_deployment_iv_rank'] = iv_rank

    # Rolling 24h frequency tracker
    now_iso = datetime.now(timezone.utc).isoformat()
    deployments_list = session.setdefault('deployments_last_24h', [])
    deployments_list.append(now_iso)
    # Trim old entries outside 24h window
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    session['deployments_last_24h'] = [ts for ts in deployments_list if ts >= cutoff]

    # Update fee tracking
    ft = session.setdefault('fees_tracking', {})
    ft['total_fees_paid'] = float(ft.get('total_fees_paid', 0.0)) + total_fees
    ft['last_fee_charge'] = now_iso


def _emit_and_alert(
    session: Dict[str, Any],
    tranche: Dict[str, Any],
    spot: float,
) -> None:
    """Fire WebSocket event, Telegram alert, and audit log after successful deploy."""
    session_id = session.get('session_id', '')
    tranche_id = tranche['tranche_id']
    total_lots = int(session.get('total_deployed_lots', 0))

    try:
        alert_tranche_deployed(session_id, tranche_id, total_lots)
    except Exception:
        pass

    try:
        emit_tranche_deployed(
            session_id=session_id,
            tranche_id=tranche_id,
            tranche_type=tranche.get('type', TrncType.DEPLOYMENT),
            ce_symbol=tranche['ce']['symbol'],
            pe_symbol=tranche['pe']['symbol'],
            lots=tranche['ce']['lots'],
            premium_collected=tranche['premium_collected'],
        )
    except Exception:
        pass


def _compute_bs_price(
    session: Dict[str, Any],
    spot: float,
    strike: float,
    iv_rank: float,
    option_type: str,
) -> float:
    """
    Estimate Black-Scholes fair price. Returns 0.0 when IV is unavailable.

    iv_rank (0–100) is converted to approximate raw IV (annualised decimal)
    as a rough proxy. For Phase 6, this is best-effort — the fairness gate
    passes when bs_price=0 (IV unavailable).
    """
    from .mmmx_engine import black_scholes_fair_value, compute_dte_days

    if iv_rank <= 0 or spot <= 0 or strike <= 0:
        return 0.0

    dte_days = compute_dte_days(session.get('expiry_datetime'))
    if dte_days <= 0:
        return 0.0

    # Very rough IV proxy: iv_rank/100 × historical_vol_proxy (assume 0.80 baseline)
    # In Phase 7 a proper IV feed replaces this
    iv = iv_rank / 100.0 * 0.80
    time_to_expiry_years = dte_days / 365.0

    return black_scholes_fair_value(
        spot=spot,
        strike=strike,
        time_to_expiry_years=time_to_expiry_years,
        iv=iv,
        option_type=option_type,
    )


async def _rollback_ce(
    executor: Any,
    ce_symbol: str,
    ce_lots: int,
    session_id: str,
    tranche_id: Any,
) -> None:
    """Buy back CE after PE failure (all-or-nothing rollback)."""
    try:
        rollback = await executor.smart_execute(
            symbol=ce_symbol,
            side='buy',
            size=ce_lots,
            reduce_only=True,
            max_reprice_attempts=SMART_EXECUTE_REPRICE_ATTEMPTS,
            use_bid_entry=True,
            session_id=session_id,
            tranche_id=tranche_id,
            action=f'ROLLBACK_CE_TR{tranche_id}',
        )
        if rollback.success:
            log.info(
                f"[Initializer][{session_id[:8]}] CE rollback successful for Tr{tranche_id}."
            )
        else:
            log.error(
                f"[Initializer][{session_id[:8]}] CE ROLLBACK FAILED for Tr{tranche_id}: "
                f"{rollback.reason}. Naked CE position!"
            )
    except Exception as exc:
        log.error(
            f"[Initializer][{session_id[:8]}] CE rollback exception for Tr{tranche_id}: {exc}"
        )
