"""
MMMX ATM Shield — Per-Position OTM Protection

Spec: MMMX_COMPLETE.md Section 6 (ATM Shield + G37 + G38 + G39).

Key functions:
  evaluate(session, spot) -> List[ShieldCandidate]
      Find all ACTIVE positions whose OTM buffer < atm_protect_threshold.
  sort_by_priority(candidates) -> List[ShieldCandidate]  (G38 — worst loss first)
  execute_shield(session, candidate, executor, audit, spot, save_fn) -> ShieldResult
      6-step shield: calculate loss → buyback → sell new → create recovery tranche.
  allocate_reserve(session, loss_usd, ce_premium, pe_premium) -> RecoveryAllocation (G39)
  create_recovery_tranche(session, parent, ...) -> Optional[dict]
      Sibling naming: "2A" / "2B" / "2C" (max = atm_shield_max_shifts).
  evaluate_and_fire(session, spot, executor, audit, save_fn) -> List[ShieldResult]
      Main entry point from monitor. Orchestrates G38 multi-shield and G39 cascade.

Key invariants:
  - emit_safety() is a regular def — call directly, NEVER await.
  - Isolation: ZERO imports from routes.mmm.* in this file.
  - tranches_deployed / tranches_remaining are NOT changed by recovery tranche creation.
  - G13: mid-beat persist after create_recovery_tranche via save_fn callback.
  - Shield fires even when session is PAUSED (naked watchdog path).
  - Buyback fails → abort shield, no naked state. Next beat re-evaluates.
  - New-sell fails all 11 attempts → session PAUSED, _naked_positions populated.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .mmmx_constants import (
    LOT_SIZE_BTC,
    SHIELD_BUYBACK_REPRICE_ATTEMPTS,
    SHIELD_SELL_REPRICE_ATTEMPTS,
    SessionStatus,
    TrncStatus,
    TrncType,
)
from .mmmx_engine import compute_realized_pnl, compute_recovery_lots
from . import mmmx_engine as _engine   # Accessed via module attr so patches are transparent
from .mmmx_state import make_tranche
from .mmmx_websocket import emit_safety
from .mmmx_activity import log_activity
from .mmmx_telegram import (
    alert_atm_shield,
    alert_atm_shield_aborted,
    alert_naked_position,
)

log = logging.getLogger('mmmx_atm_shield')


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class ShieldCandidate:
    """A position (leg) that has triggered the ATM shield threshold."""
    tranche_id: Any           # int (deployment) or str e.g. "2A" (recovery)
    side: str                 # 'ce' | 'pe'
    position: Dict            # leg dict from tranche (reference — mutations reflected)
    tranche: Dict             # full tranche dict (reference)
    otm_pct: float            # current OTM% (< threshold)
    unrealized_loss_usd: float  # positive = losing money on the short


@dataclass
class RecoveryAllocation:
    """Reserve allocation result per G39 (partial or zero cascade)."""
    ce_requested: int
    pe_requested: int
    ce_allocated: int
    pe_allocated: int

    @property
    def partial(self) -> bool:
        return (
            self.ce_allocated < self.ce_requested or
            self.pe_allocated < self.pe_requested
        )

    @property
    def exhausted(self) -> bool:
        return self.ce_allocated == 0 and self.pe_allocated == 0


@dataclass
class ShieldResult:
    """Result of a single shield execution."""
    success: bool
    tranche_id: Any
    side: str
    old_strike: float = 0.0
    new_strike: float = 0.0
    recovery_tranche_id: Any = None   # None if no recovery created
    naked: bool = False               # True if new-sell failed → session PAUSED
    reason: str = ''
    ce_allocated: int = 0
    pe_allocated: int = 0


# ── OTM calculation helpers ───────────────────────────────────────────────────

def _compute_otm_pct(side: str, strike: float, spot: float) -> Optional[float]:
    """
    Compute OTM buffer %.

    CE: (strike - spot) / spot × 100
    PE: (spot - strike) / spot × 100

    Returns None if inputs invalid (non-positive).
    """
    if spot <= 0 or strike <= 0:
        return None
    if side == 'ce':
        return (strike - spot) / spot * 100.0
    else:
        return (spot - strike) / spot * 100.0


def _compute_unrealized_loss(position: Dict) -> float:
    """
    Estimate unrealized loss for a SHORT position.

    loss = max(0, (current_premium - entry_premium) × lots × LOT_SIZE_BTC)
    Returns 0.0 if current_premium is None.
    """
    entry   = position.get('entry_premium', 0.0) or 0.0
    current = position.get('current_premium')
    lots    = position.get('lots', 0) or 0
    if current is None:
        return 0.0
    return max(0.0, (current - entry) * lots * LOT_SIZE_BTC)


# ── evaluate ──────────────────────────────────────────────────────────────────

def evaluate(session: Dict, spot: float) -> List[ShieldCandidate]:
    """
    Find all ACTIVE positions (all tranches) whose OTM buffer < atm_protect_threshold.

    Iterates ALL tranches (deployment + recovery). Checks both CE and PE legs.
    Returns a list of ShieldCandidate — may be empty.
    """
    if not spot or spot <= 0:
        return []

    threshold = session.get('params', {}).get('atm_protect_threshold', 5.0)
    candidates: List[ShieldCandidate] = []

    for tranche in session.get('tranches', []):
        if tranche.get('status') == TrncStatus.CLOSED:
            continue

        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if leg.get('status') != TrncStatus.ACTIVE:
                continue

            strike = leg.get('strike')
            if not strike:
                continue

            otm_pct = _compute_otm_pct(side, float(strike), float(spot))
            if otm_pct is None:
                continue

            if otm_pct < threshold:
                loss = _compute_unrealized_loss(leg)
                candidates.append(ShieldCandidate(
                    tranche_id=tranche['tranche_id'],
                    side=side,
                    position=leg,
                    tranche=tranche,
                    otm_pct=otm_pct,
                    unrealized_loss_usd=loss,
                ))

    return candidates


# ── sort_by_priority (G38) ────────────────────────────────────────────────────

def sort_by_priority(candidates: List[ShieldCandidate]) -> List[ShieldCandidate]:
    """
    Sort shield candidates by priority (G38 — worst loss first).

    Primary:    largest unrealized_loss_usd (descending).
    Tiebreaker: oldest tranche first — numeric IDs sort before string IDs;
                within strings, sort by (numeric prefix ASC, suffix ASC).

    Returns a new sorted list; input is not mutated.
    """
    def _sort_key(c: ShieldCandidate):
        tid = c.tranche_id
        if isinstance(tid, int):
            sort_tid = (tid, '')
        else:
            s = str(tid)
            digits = ''.join(ch for ch in s if ch.isdigit())
            suffix = ''.join(ch for ch in s if not ch.isdigit())
            sort_tid = (int(digits) if digits else 0, suffix)
        return (-c.unrealized_loss_usd, sort_tid)

    return sorted(candidates, key=_sort_key)


# ── multi_shield_margin_precheck (G38) ────────────────────────────────────────

def multi_shield_margin_precheck(candidates: List[ShieldCandidate]) -> bool:
    """
    Pre-execution margin gate for multi-shield beats (G38).

    Phase 5: Returns True (pass-through). Full live-margin pre-check is implemented
    in Phase 7 once MMMXExecutor.preflight_margin_check is fully wired to live data.
    Per-order margin checks still fire inside smart_execute and emergency_execute.
    """
    return True


# ── allocate_reserve (G39) ────────────────────────────────────────────────────

def allocate_reserve(
    session: Dict,
    loss_usd: float,
    ce_premium: float,
    pe_premium: float,
) -> RecoveryAllocation:
    """
    Compute reserve allocation for one shield recovery (G39 cascade).

    ce_recovery_needed = ceil(loss × 0.30 / (ce_premium × LOT_SIZE_BTC))
    pe_recovery_needed = ceil(loss × 0.70 / (pe_premium × LOT_SIZE_BTC))

    Each side independently capped to its remaining reserve.
    Returns a RecoveryAllocation (may be partial or fully-exhausted).
    """
    ce_needed, pe_needed = compute_recovery_lots(loss_usd, ce_premium, pe_premium)

    ce_avail = max(0, session.get('ce_reserve_remaining', 0))
    pe_avail = max(0, session.get('pe_reserve_remaining', 0))

    ce_alloc = min(ce_needed, ce_avail)
    pe_alloc = min(pe_needed, pe_avail)

    return RecoveryAllocation(
        ce_requested=ce_needed,
        pe_requested=pe_needed,
        ce_allocated=ce_alloc,
        pe_allocated=pe_alloc,
    )


# ── sibling ID helper ──────────────────────────────────────────────────────────

def _next_recovery_id(session: Dict, parent_id: Any, max_shifts: int) -> Optional[str]:
    """
    Return the next unused sibling ID for a parent tranche, or None if limit hit.

    parent_id=2, existing=[]    → "2A"
    parent_id=2, existing=["2A"] → "2B"
    parent_id=2, existing=["2A","2B","2C"], max_shifts=3 → None
    """
    suffixes = 'ABCDEFGHIJ'[:max_shifts]
    parent_str = str(parent_id)
    existing = {
        str(t['tranche_id'])
        for t in session.get('tranches', [])
        if t.get('type') == TrncType.RECOVERY
        and str(t.get('parent_tranche_id')) == parent_str
    }
    for suffix in suffixes:
        cid = f"{parent_str}{suffix}"
        if cid not in existing:
            return cid
    return None


# ── create_recovery_tranche ────────────────────────────────────────────────────

def create_recovery_tranche(
    session: Dict,
    parent_tranche: Dict,
    ce_lots: int,
    pe_lots: int,
    spot: float,
    ce_symbol: str,
    pe_symbol: str,
    ce_strike: float,
    pe_strike: float,
    ce_premium: float,
    pe_premium: float,
    ce_delta: float,
    pe_delta: float,
    shield_event: int,
) -> Optional[Dict]:
    """
    Create a sibling recovery tranche (2A / 2B / 2C) and append to session['tranches'].

    Sibling naming: parent_id + suffix letter (A/B/C up to atm_shield_max_shifts).

    Invariants:
      - tranches_deployed and tranches_remaining are NOT modified.
      - Returns None if max_shifts exhausted (caller should alert and skip recovery).
      - Caller is responsible for decrementing reserves and updating total_premium_collected.
    """
    max_shifts = session.get('params', {}).get('atm_shield_max_shifts', 3)
    parent_id = parent_tranche['tranche_id']

    new_id = _next_recovery_id(session, parent_id, max_shifts)
    if new_id is None:
        log.error(
            f"[ATM Shield] Max shifts exhausted for tranche {parent_id} "
            f"(atm_shield_max_shifts={max_shifts}). No recovery tranche created."
        )
        return None

    # Inherit metadata from parent where available
    dvol    = parent_tranche.get('entry_dvol', 0.0) or 0.0
    iv_rank = parent_tranche.get('entry_iv_rank', 0.0) or 0.0

    tranche = make_tranche(
        tranche_id=new_id,
        entry_spot=spot,
        entry_dvol=dvol,
        entry_iv_rank=iv_rank,
        ce_symbol=ce_symbol,
        ce_strike=ce_strike,
        ce_lots=ce_lots,
        ce_premium=ce_premium,
        ce_delta=ce_delta,
        pe_symbol=pe_symbol,
        pe_strike=pe_strike,
        pe_lots=pe_lots,
        pe_premium=pe_premium,
        pe_delta=pe_delta,
        tranche_type=TrncType.RECOVERY,
        parent_tranche_id=parent_id,
        shield_event=shield_event,
    )

    session['tranches'].append(tranche)
    log.info(
        f"[ATM Shield] Recovery tranche {new_id} created "
        f"(parent={parent_id}, CE={ce_lots} lots, PE={pe_lots} lots)."
    )
    return tranche


# ── Symbol helpers ─────────────────────────────────────────────────────────────

def _build_new_symbol(old_symbol: str, new_strike: float) -> str:
    """
    Build a new option symbol by replacing the strike in the existing symbol's format.

    Format: {C|P}-BTC-{strike}-{expiry_ddmmyy}
    Example: 'C-BTC-90000-280326', strike=95000 → 'C-BTC-95000-280326'

    Falls back to old_symbol on parse failure.
    """
    parts = old_symbol.split('-')
    if len(parts) >= 4:
        return f"{parts[0]}-{parts[1]}-{int(round(new_strike))}-{parts[3]}"
    return old_symbol


def _compute_new_strike(side: str, spot: float, otm_distance_pct: float) -> float:
    """
    Compute the target strike at the original OTM distance from current spot.

    CE: spot × (1 + otm_distance_pct / 100)
    PE: spot × (1 - otm_distance_pct / 100)
    """
    if side == 'ce':
        return spot * (1.0 + otm_distance_pct / 100.0)
    else:
        return spot * (1.0 - otm_distance_pct / 100.0)


# ── Retry sell (10 limit + 1 market) ─────────────────────────────────────────

async def _run_retry_sell(
    executor,
    symbol: str,
    size: int,
    session_id: str,
    tranche_id: Any,
    side: str,
) -> Any:  # ExecutionResult
    """
    Shield sell retry: 10 limit reprice attempts + market fallback.

    Spec: MMMX_COMPLETE.md Section 6 "Shield Sell Retry Mechanism".
    Delegates to executor.smart_execute with SHIELD_SELL_REPRICE_ATTEMPTS.
    The executor's internal market fallback fires after the limit loop exhausts.
    """
    return await executor.smart_execute(
        symbol=symbol,
        side='sell',
        size=size,
        reduce_only=False,
        max_reprice_attempts=SHIELD_SELL_REPRICE_ATTEMPTS,
        session_id=session_id,
        tranche_id=tranche_id,
        action=f'SHIELD_SELL_{side.upper()}',
    )


# ── execute_shield ────────────────────────────────────────────────────────────

async def execute_shield(
    session: Dict,
    candidate: ShieldCandidate,
    executor,
    audit,
    spot: float,
    save_fn: Optional[Callable] = None,
) -> ShieldResult:
    """
    Execute the 6-step ATM shield sequence for a single candidate.

    Step 1: Calculate loss (current_premium vs entry_premium)
    Step 2: Buyback old position (10 reprice + 1 market via smart_execute)
            → Abort on failure; no naked state; next beat re-evaluates.
    Step 3: Sell new position at fresh OTM strike (10 reprice + 1 market)
            → On failure: session PAUSED, _naked_positions populated, Telegram CRITICAL.
    Step 4-5: Allocate reserve (G39 — partial or zero cascade)
    Step 6: Update state — reserves, premium collected, hard stop, baselines, counters.
            G13: mid-beat persist after recovery tranche via save_fn.

    Returns ShieldResult.
    """
    tranche    = candidate.tranche
    tranche_id = candidate.tranche_id
    side       = candidate.side
    position   = candidate.position   # reference into session['tranches'][...]['ce'|'pe']
    session_id = session.get('session_id', '')

    old_strike  = float(position.get('strike', 0.0))
    old_symbol  = position.get('symbol', '')
    old_premium = float(position.get('entry_premium', 0.0))
    lots        = int(position.get('lots', 0))

    # ── Step 1: Calculate loss ─────────────────────────────────────────────────
    current_premium = position.get('current_premium')
    if current_premium is None:
        current_premium = old_premium
    current_premium = float(current_premium)

    loss_usd = max(0.0, (current_premium - old_premium) * lots * LOT_SIZE_BTC)
    log.info(
        f"[ATM Shield] Tr{tranche_id}/{side.upper()}: "
        f"OTM={candidate.otm_pct:.2f}%, strike={old_strike}, loss=${loss_usd:.2f}"
    )

    # ── Step 2: Buyback old position ───────────────────────────────────────────
    buyback_result = await executor.smart_execute(
        symbol=old_symbol,
        side='buy',
        size=lots,
        reduce_only=True,
        max_reprice_attempts=SHIELD_BUYBACK_REPRICE_ATTEMPTS,
        use_bid_entry=True,
        session_id=session_id,
        tranche_id=tranche_id,
        action=f'SHIELD_BUY_{side.upper()}',
        position=position,
    )

    if not buyback_result.success:
        # Abort shield — do NOT create naked state. Delta-gate catches next beat.
        reason = f"buyback failed: {buyback_result.reason}"
        log.error(f"[ATM Shield] Tr{tranche_id}/{side.upper()} ABORTED — {reason}")
        try:
            alert_atm_shield_aborted(session_id, side, reason)
        except Exception:
            pass
        return ShieldResult(
            success=False,
            tranche_id=tranche_id,
            side=side,
            old_strike=old_strike,
            reason=reason,
        )

    # Record buyback fill
    buyback_price  = float(buyback_result.avg_price or current_premium)
    realized_loss  = max(0.0, (buyback_price - old_premium) * lots * LOT_SIZE_BTC)
    shield_event_n = len(position.get('shield_history', [])) + 1

    position.setdefault('shield_history', []).append({
        'event':         shield_event_n,
        'old_strike':    old_strike,
        'buyback_price': buyback_price,
        'loss_usd':      realized_loss,
        'fired_at':      datetime.now(timezone.utc).isoformat(),
    })
    position['realized_pnl'] = (
        float(position.get('realized_pnl', 0.0)) +
        compute_realized_pnl(old_premium, buyback_price, lots)
    )
    position['fees_paid']    = float(position.get('fees_paid', 0.0)) + buyback_result.fees_paid
    position['shift_count']  = int(position.get('shift_count', 0)) + 1
    position['_being_closed'] = False  # smart_execute set this; clear after fill

    # ── Step 3: Sell new position at fresh strike ──────────────────────────────
    otm_distance_pct = session.get('params', {}).get('otm_distance_pct', 15.0)
    new_strike       = _compute_new_strike(side, spot, otm_distance_pct)
    new_symbol       = _build_new_symbol(old_symbol, new_strike)

    sell_result = await _run_retry_sell(
        executor=executor,
        symbol=new_symbol,
        size=lots,
        session_id=session_id,
        tranche_id=tranche_id,
        side=side,
    )

    if not sell_result.success:
        # ── Sell failed — naked position; session PAUSED ───────────────────────
        now_iso = datetime.now(timezone.utc).isoformat()
        naked_entry = {
            'tranche_id':  tranche_id,
            'side':        side,
            'naked_since': now_iso,
            'retries':     0,
            'symbol':      new_symbol,
            'lots':        lots,
        }
        session.setdefault('_naked_positions', []).append(naked_entry)

        if session.get('status') == SessionStatus.RUNNING:
            session['status'] = SessionStatus.PAUSED

        log.critical(
            f"[ATM Shield] NAKED POSITION: Tr{tranche_id}/{side.upper()} "
            "— new sell failed all 11 attempts. Session PAUSED."
        )
        try:
            alert_naked_position(session_id, tranche_id, side, now_iso, retries=0)
        except Exception:
            pass
        try:
            emit_safety(
                session_id=session_id,
                safety_type='naked_position',
                level='critical',
                message=f"NAKED: Tr{tranche_id}/{side.upper()} — new sell failed.",
            )
        except Exception:
            pass

        return ShieldResult(
            success=False,
            tranche_id=tranche_id,
            side=side,
            old_strike=old_strike,
            new_strike=new_strike,
            naked=True,
            reason='new_sell_failed_all_attempts',
        )

    # Sell succeeded — update position to new strike
    new_sell_price = float(sell_result.avg_price or 0.0)

    position['symbol']          = new_symbol
    position['strike']          = new_strike
    position['entry_premium']   = new_sell_price
    position['current_premium'] = new_sell_price
    position['entry_delta']     = 0.0   # Phase 6+ will populate from live quotes
    position['current_delta']   = 0.0
    position['unrealized_pnl']  = 0.0
    position['fees_paid']       = float(position.get('fees_paid', 0.0)) + sell_result.fees_paid
    # status remains ACTIVE — position is live at new strike

    # ── Steps 4-5: Allocate reserve (G39) ─────────────────────────────────────
    other_side = 'pe' if side == 'ce' else 'ce'
    other_leg  = tranche.get(other_side, {})
    other_prem = float(
        other_leg.get('current_premium') or other_leg.get('entry_premium') or 0.01
    )
    other_prem = max(0.01, other_prem)

    ce_prem_for_recovery = new_sell_price if side == 'ce' else other_prem
    pe_prem_for_recovery = new_sell_price if side == 'pe' else other_prem
    ce_prem_for_recovery = max(0.01, ce_prem_for_recovery)
    pe_prem_for_recovery = max(0.01, pe_prem_for_recovery)

    allocation = allocate_reserve(
        session, realized_loss, ce_prem_for_recovery, pe_prem_for_recovery
    )

    recovery_tranche = None
    recovery_id      = None

    if not allocation.exhausted:
        # ── Step 6a: Create recovery tranche ──────────────────────────────────
        if side == 'ce':
            ce_rec_strike = new_strike
            pe_rec_strike = float(tranche.get('pe', {}).get('strike', new_strike))
            ce_rec_sym    = new_symbol
            pe_rec_sym    = _build_new_symbol(
                tranche.get('pe', {}).get('symbol', new_symbol), pe_rec_strike
            )
        else:
            pe_rec_strike = new_strike
            ce_rec_strike = float(tranche.get('ce', {}).get('strike', new_strike))
            pe_rec_sym    = new_symbol
            ce_rec_sym    = _build_new_symbol(
                tranche.get('ce', {}).get('symbol', new_symbol), ce_rec_strike
            )

        recovery_tranche = create_recovery_tranche(
            session=session,
            parent_tranche=tranche,
            ce_lots=allocation.ce_allocated,
            pe_lots=allocation.pe_allocated,
            spot=spot,
            ce_symbol=ce_rec_sym,
            pe_symbol=pe_rec_sym,
            ce_strike=ce_rec_strike,
            pe_strike=pe_rec_strike,
            ce_premium=ce_prem_for_recovery,
            pe_premium=pe_prem_for_recovery,
            ce_delta=0.0,
            pe_delta=0.0,
            shield_event=shield_event_n,
        )

        if recovery_tranche:
            recovery_id = recovery_tranche['tranche_id']

            # Decrement reserves (per-side, independent)
            session['ce_reserve_remaining'] = max(
                0, session.get('ce_reserve_remaining', 0) - allocation.ce_allocated
            )
            session['pe_reserve_remaining'] = max(
                0, session.get('pe_reserve_remaining', 0) - allocation.pe_allocated
            )

            # Recovery premiums contribute to total_premium_collected
            session['total_premium_collected'] = (
                float(session.get('total_premium_collected', 0.0)) +
                recovery_tranche['premium_collected']
            )

            # Hard stop scales with collected premium
            session['hard_stop_usd'] = _engine.recalc_hard_stop(session)

            # G13: mid-beat persist — crash safety after recovery tranche creation
            if save_fn is not None:
                try:
                    ok = save_fn(session)
                    if not ok:
                        log.error(
                            f"[ATM Shield] G13 mid-beat persist FAILED after "
                            f"recovery tranche {recovery_id}. Stale monitor?"
                        )
                except Exception as exc:
                    log.error(f"[ATM Shield] G13 save_fn raised: {exc}")

            if allocation.partial:
                _alert_partial_reserve(session_id, tranche_id, allocation)
        else:
            # Max shifts exhausted — alert, no recovery created
            _alert_max_shifts(session_id, tranche_id)
    else:
        # Both reserves exhausted — reposition without recovery (Q11, G39)
        log.warning(
            f"[ATM Shield] Reserve exhausted. "
            f"Tr{tranche_id}/{side.upper()} repositioned WITHOUT recovery."
        )
        _alert_reserve_exhausted(session_id, tranche_id)

    # ── Step 6b: Update deployment reference baselines ─────────────────────────
    # Mandatory per spec: prevents stale move-reference after reposition.
    session['last_deployment_spot']    = spot
    session['last_deployment_iv_rank'] = session.get('last_deployment_iv_rank')  # Phase 6 supplies live IV

    # ── Step 6c: Counters and event history ───────────────────────────────────
    session['shield_fire_count'] = int(session.get('shield_fire_count', 0)) + 1
    session.setdefault('shield_event_history', []).append({
        'tranche_id':    tranche_id,
        'side':          side,
        'old_strike':    old_strike,
        'new_strike':    new_strike,
        'loss_usd':      realized_loss,
        'recovery_id':   recovery_id,
        'ce_allocated':  allocation.ce_allocated,
        'pe_allocated':  allocation.pe_allocated,
        'spot':          spot,
        'fired_at':      datetime.now(timezone.utc).isoformat(),
    })

    # Emit WS event and Telegram
    try:
        emit_safety(
            session_id=session_id,
            safety_type='atm_shield_fired',
            level='warning',
            message=(
                f"Shield: Tr{tranche_id}/{side.upper()} "
                f"{old_strike:.0f} → {new_strike:.0f}. "
                f"Recovery: {recovery_id or 'none'}."
            ),
        )
    except Exception:
        pass
    try:
        alert_atm_shield(session_id, side, old_strike, new_strike)
    except Exception:
        pass
    try:
        log_activity(
            event_type='atm_shield_fired',
            message=(
                f"Tr{tranche_id}/{side.upper()}: {old_strike:.0f} → {new_strike:.0f}. "
                f"Loss=${realized_loss:.2f}. Recovery={recovery_id or 'none'}. "
                f"CE reserve={session.get('ce_reserve_remaining')}, "
                f"PE reserve={session.get('pe_reserve_remaining')}."
            ),
            session_id=session_id,
            level='warning',
            data={
                'tranche_id':   tranche_id,
                'side':         side,
                'old_strike':   old_strike,
                'new_strike':   new_strike,
                'loss_usd':     realized_loss,
                'recovery_id':  recovery_id,
                'ce_allocated': allocation.ce_allocated,
                'pe_allocated': allocation.pe_allocated,
            },
        )
    except Exception:
        pass

    return ShieldResult(
        success=True,
        tranche_id=tranche_id,
        side=side,
        old_strike=old_strike,
        new_strike=new_strike,
        recovery_tranche_id=recovery_id,
        naked=False,
        reason='',
        ce_allocated=allocation.ce_allocated,
        pe_allocated=allocation.pe_allocated,
    )


# ── evaluate_and_fire (main entry point) ──────────────────────────────────────

async def evaluate_and_fire(
    session: Dict,
    spot: Optional[float],
    executor,
    audit,
    save_fn: Optional[Callable] = None,
) -> List[ShieldResult]:
    """
    Main ATM Shield entry point called by mmmx_monitor._heartbeat.

    Orchestration:
      1. evaluate() — find all candidates
      2. sort_by_priority() — G38: worst loss first
      3. multi_shield_margin_precheck() — G38: margin gate
      4. Execute shields sequentially (G39: reserve cascade)
         — pause after naked detection (no point shielding if PAUSED from naked)

    Shield fires even when session is PAUSED (naked watchdog path handles re-sell).
    If spot is None or <= 0, returns [] immediately (no OTM calculation possible).
    """
    if not spot or spot <= 0:
        return []

    status = session.get('status', '')
    if status not in (SessionStatus.RUNNING, SessionStatus.PAUSED):
        return []

    candidates = evaluate(session, spot)
    if not candidates:
        return []

    sorted_candidates = sort_by_priority(candidates)

    if not multi_shield_margin_precheck(sorted_candidates):
        log.warning(
            f"[ATM Shield] Multi-shield margin pre-check failed. "
            f"Deferring {len(sorted_candidates)} shields to next beat."
        )
        return []

    results: List[ShieldResult] = []
    for candidate in sorted_candidates:
        result = await execute_shield(
            session=session,
            candidate=candidate,
            executor=executor,
            audit=audit,
            spot=spot,
            save_fn=save_fn,
        )
        results.append(result)

        # If session just became PAUSED (naked), stop processing remaining shields.
        # They will be re-evaluated next beat once the naked is resolved.
        if session.get('status') == SessionStatus.PAUSED and result.naked:
            remaining = len(sorted_candidates) - len(results)
            if remaining > 0:
                log.warning(
                    f"[ATM Shield] Session PAUSED (naked). "
                    f"Deferring {remaining} remaining shield(s) to next beat."
                )
            break

    return results


# ── Telegram alert helpers ─────────────────────────────────────────────────────

def _alert_partial_reserve(
    session_id: str, tranche_id: Any, alloc: RecoveryAllocation
) -> None:
    try:
        from .mmmx_telegram import send_alert
        send_alert(
            f"⚠️ Reserve partially depleted for Tr{tranche_id}. "
            f"CE: {alloc.ce_allocated}/{alloc.ce_requested} lots. "
            f"PE: {alloc.pe_allocated}/{alloc.pe_requested} lots.",
            alert_type=f'reserve_partial_{tranche_id}',
            session_id=session_id,
            dedup_ttl=60,
        )
    except Exception:
        pass


def _alert_reserve_exhausted(session_id: str, tranche_id: Any) -> None:
    try:
        from .mmmx_telegram import send_alert
        send_alert(
            f"🚨 Reserve exhausted. Tr{tranche_id} repositioned WITHOUT recovery. "
            "Operator action required.",
            alert_type=f'reserve_exhausted_{tranche_id}',
            session_id=session_id,
            dedup_ttl=60,
        )
    except Exception:
        pass


def _alert_max_shifts(session_id: str, tranche_id: Any) -> None:
    try:
        from .mmmx_telegram import send_alert
        send_alert(
            f"⚠️ Max ATM shield shifts exhausted for Tr{tranche_id}. "
            "Raise atm_shield_max_shifts or apply delta-gate manually.",
            alert_type=f'max_shifts_{tranche_id}',
            session_id=session_id,
            dedup_ttl=120,
        )
    except Exception:
        pass
