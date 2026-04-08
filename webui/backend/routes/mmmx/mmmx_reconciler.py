"""
MMMX Reconciler — Partial Fill Tracker & Exchange/DB Divergence Detector

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 2.

Functions:
  track_partial_fill(...)         — Record a partial fill residual in memory + audit log
  tick_partials(session) → list   — Retry all residuals; called at start of every heartbeat
  reconcile_with_exchange(session) → ReconciliationReport  (Phase 9 manual trigger)

In-memory residuals table:
  {order_id, symbol, side, tranche_id, requested, filled, remaining, last_attempt_at, session_id}

tick_partials retries each residual via smart_execute on the remaining lots.
A residual is cleared when filled == requested OR the position no longer exists on exchange.
If remainder implies large exposure (>= emergency_delta heuristic), escalates to emergency_execute.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger('mmmx_reconciler')


# ── Residual record ────────────────────────────────────────────────────────────

@dataclass
class PartialResidual:
    order_id:        str
    symbol:          str
    side:            str
    tranche_id:      Any
    requested:       int
    filled:          int
    session_id:      str
    last_attempt_at: float = field(default_factory=time.time)

    @property
    def remaining(self) -> int:
        return max(self.requested - self.filled, 0)


# ── Reconciliation report ─────────────────────────────────────────────────────

@dataclass
class ReconciliationReport:
    session_id:         str
    checked_at:         str
    exchange_positions: List[Dict] = field(default_factory=list)
    db_positions:       List[Dict] = field(default_factory=list)
    divergences:        List[Dict] = field(default_factory=list)
    ok:                 bool = True
    notes:              str  = ''


# ── In-memory residuals store ──────────────────────────────────────────────────

_residuals: Dict[str, PartialResidual] = {}   # keyed by order_id
_lock = threading.Lock()

# Lot threshold above which we escalate to emergency_execute in tick_partials.
# Rough proxy: if we still have >= this many lots unhedged, treat as urgent.
_EMERGENCY_LOTS_THRESHOLD = 20


# ── Public API ─────────────────────────────────────────────────────────────────

def track_partial_fill(
    order_id: str,
    symbol: str,
    side: str,
    tranche_id: Any,
    requested_lots: int,
    filled_lots: int,
    session_id: str,
) -> None:
    """
    Record (or update) a partial fill residual.

    If remaining == 0 the residual is cleared immediately.
    Persists to audit log for crash visibility.
    """
    remaining = requested_lots - filled_lots
    if remaining <= 0:
        with _lock:
            _residuals.pop(order_id, None)
        return

    residual = PartialResidual(
        order_id=order_id,
        symbol=symbol,
        side=side,
        tranche_id=tranche_id,
        requested=requested_lots,
        filled=filled_lots,
        session_id=session_id,
    )

    with _lock:
        _residuals[order_id] = residual

    _audit_event(session_id, 'PARTIAL_FILL_TRACKED', {
        'order_id':  order_id,
        'symbol':    symbol,
        'side':      side,
        'tranche_id': str(tranche_id),
        'requested': requested_lots,
        'filled':    filled_lots,
        'remaining': remaining,
    })

    log.warning(
        f"[MMMX][Reconciler] Partial fill tracked: {order_id} "
        f"{symbol} {filled_lots}/{requested_lots} lots — remaining={remaining}"
    )


async def tick_partials(session: Dict) -> List[Dict]:
    """
    Retry all pending partial fill residuals.

    Must be called at the start of every heartbeat cycle.

    For each residual:
      - remaining >= _EMERGENCY_LOTS_THRESHOLD → emergency_execute (IOC)
      - otherwise → smart_execute
      - On success: residual cleared
      - On failure: residual retained for next beat

    Returns:
        List of result dicts (one per residual attempted).
    """
    with _lock:
        pending = list(_residuals.values())

    if not pending:
        return []

    results: List[Dict] = []
    session_id = session.get('session_id', '')

    for residual in pending:
        remaining = residual.remaining
        if remaining <= 0:
            with _lock:
                _residuals.pop(residual.order_id, None)
            continue

        log.info(
            f"[MMMX][Reconciler] Retrying partial {residual.order_id}: "
            f"{residual.side.upper()} {remaining} remaining of {residual.requested} "
            f"{residual.symbol}"
        )

        try:
            from .mmmx_executor import get_executor
            executor = get_executor()

            use_emergency = remaining >= _EMERGENCY_LOTS_THRESHOLD

            if use_emergency:
                result = await executor.emergency_execute(
                    symbol=residual.symbol,
                    side=residual.side,
                    size=remaining,
                    session_id=session_id,
                    tranche_id=residual.tranche_id,
                    action='PARTIAL_RETRY',
                )
            else:
                result = await executor.smart_execute(
                    symbol=residual.symbol,
                    side=residual.side,
                    size=remaining,
                    session_id=session_id,
                    tranche_id=residual.tranche_id,
                    action='PARTIAL_RETRY',
                )

            residual.last_attempt_at = time.time()
            result_dict = result.to_dict()

            if result.success:
                with _lock:
                    _residuals.pop(residual.order_id, None)
                _audit_event(session_id, 'PARTIAL_FILL_CLEARED', {
                    'order_id':    residual.order_id,
                    'filled_size': result.filled_size,
                })
                log.info(
                    f"[MMMX][Reconciler] Residual {residual.order_id} cleared: "
                    f"{result.filled_size} lots filled"
                )
            else:
                log.warning(
                    f"[MMMX][Reconciler] Partial retry failed for {residual.order_id}: "
                    f"{result.reason}"
                )

            results.append({
                'order_id':  residual.order_id,
                'symbol':    residual.symbol,
                'remaining': remaining,
                'result':    result_dict,
            })

        except Exception as exc:
            log.exception(
                f"[MMMX][Reconciler] tick_partials error for {residual.order_id}: {exc}"
            )
            results.append({
                'order_id': residual.order_id,
                'symbol':   residual.symbol,
                'error':    str(exc),
            })

    return results


async def reconcile_with_exchange(session: Dict) -> ReconciliationReport:
    """
    Manual trigger (Phase 9): compare exchange positions against the DB session.

    Fetches the live position list from the exchange, compares against all
    ACTIVE positions in `session['tranches']`, and reports divergences.

    Returns:
        ReconciliationReport — ok=True if no divergences found.
    """
    session_id = session.get('session_id', '')
    report = ReconciliationReport(
        session_id=session_id,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )

    log.info(
        f"[MMMX][Reconciler] reconcile_with_exchange triggered for {session_id[:8]}"
    )

    try:
        from .mmmx_executor import get_executor
        rest = get_executor()._create_rest_client()

        # Fetch open positions from exchange
        try:
            positions_resp = await rest.get_positions()
            if isinstance(positions_resp, list):
                exchange_positions = positions_resp
            elif isinstance(positions_resp, dict):
                exchange_positions = positions_resp.get('result', [])
            else:
                exchange_positions = []
        except Exception as exc:
            report.ok    = False
            report.notes = f"Exchange position fetch failed: {exc}"
            log.error(f"[MMMX][Reconciler] {report.notes}")
            return report

        report.exchange_positions = exchange_positions

        # Build DB position list from session tranches
        db_positions: List[Dict] = []
        for t in session.get('tranches', []):
            for leg in ('ce', 'pe'):
                pos = t.get(leg, {})
                if pos.get('status') == 'ACTIVE':
                    db_positions.append({
                        'symbol':     pos.get('symbol'),
                        'lots':       pos.get('lots', 0),
                        'tranche_id': t.get('tranche_id'),
                        'leg':        leg,
                    })
        report.db_positions = db_positions

        # Build exchange symbol set (product.symbol varies by API response shape)
        exchange_symbols: set = set()
        for ep in exchange_positions:
            sym = (
                ep.get('symbol')
                or ep.get('product_symbol')
                or (ep.get('product') or {}).get('symbol')
                or ''
            )
            if sym:
                exchange_symbols.add(str(sym))

        # Divergence: DB position not found on exchange
        for dbp in db_positions:
            sym = dbp.get('symbol', '')
            if sym and sym not in exchange_symbols:
                report.divergences.append({
                    'type':      'DB_POSITION_NOT_ON_EXCHANGE',
                    'symbol':    sym,
                    'tranche_id': dbp.get('tranche_id'),
                    'leg':        dbp.get('leg'),
                })

        if report.divergences:
            report.ok    = False
            report.notes = f"{len(report.divergences)} divergence(s) found"
            log.warning(
                f"[MMMX][Reconciler] {report.notes} for session {session_id[:8]}"
            )
        else:
            report.notes = "No divergences detected"
            log.info(
                f"[MMMX][Reconciler] Clean reconciliation for {session_id[:8]}"
            )

    except Exception as exc:
        log.exception(
            f"[MMMX][Reconciler] reconcile_with_exchange crashed: {exc}"
        )
        report.ok    = False
        report.notes = f"Reconcile crashed: {exc}"

    return report


# ── Internal helpers ───────────────────────────────────────────────────────────

def _audit_event(session_id: str, category: str, data: Dict) -> None:
    """Append a reconciler event to the MMMX audit log (fire-and-forget)."""
    try:
        from .mmmx_audit_log import get_audit_log
        get_audit_log().enqueue_event(
            session_id=session_id,
            category=category,
            message=f'Reconciler: {category}',
            data=data,
        )
    except Exception as exc:
        log.debug(f"[MMMX][Reconciler] Audit event suppressed: {exc}")


def get_pending_residuals() -> List[Dict]:
    """Return a snapshot of all in-memory residuals (for monitoring/tests)."""
    with _lock:
        return [
            {
                'order_id':        r.order_id,
                'symbol':          r.symbol,
                'side':            r.side,
                'tranche_id':      str(r.tranche_id),
                'requested':       r.requested,
                'filled':          r.filled,
                'remaining':       r.remaining,
                'session_id':      r.session_id,
                'last_attempt_at': r.last_attempt_at,
            }
            for r in _residuals.values()
        ]


# ── Naked position watchdog (G37) ──────────────────────────────────────────────

async def check_naked_watchdog(session: Dict, executor) -> List[Dict]:
    """
    G37 Naked Position Timeout: escalate and retry-sell for naked positions.

    Called at the start of every heartbeat (before ATM shield evaluation).

    Per spec (G37):
      - time_naked > 30 min → force emergency sell retry, increment retries,
                               Telegram escalation.
      - time_naked > 2 hr   → send CRITICAL operator alert.

    Returns a list of action dicts (one per naked position checked).
    """
    from .mmmx_constants import NAKED_WATCHDOG_WARN_MINS, NAKED_WATCHDOG_CRITICAL_MINS
    from .mmmx_executor import get_executor as _get_executor

    naked_list = session.get('_naked_positions', [])
    if not naked_list:
        return []

    session_id = session.get('session_id', '')
    now = datetime.now(timezone.utc)
    actions: List[Dict] = []

    for naked in naked_list:
        tranche_id  = naked.get('tranche_id')
        side        = naked.get('side', '')
        naked_since = naked.get('naked_since', '')
        retries     = int(naked.get('retries', 0))
        symbol      = naked.get('symbol', '')
        lots        = int(naked.get('lots', 0))

        # Parse naked_since timestamp
        try:
            ts = datetime.fromisoformat(naked_since)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        elapsed_mins = (now - ts).total_seconds() / 60.0

        action: Dict = {
            'tranche_id':   tranche_id,
            'side':         side,
            'elapsed_mins': elapsed_mins,
            'action':       'none',
        }

        if elapsed_mins > NAKED_WATCHDOG_CRITICAL_MINS:
            # 2-hour escalation — operator manual intervention required
            log.critical(
                f"[Reconciler][G37] CRITICAL: Naked position Tr{tranche_id}/{side.upper()} "
                f"has been naked for {elapsed_mins:.1f} min (>{NAKED_WATCHDOG_CRITICAL_MINS} min). "
                "MANUAL INTERVENTION REQUIRED."
            )
            try:
                from .mmmx_telegram import alert_naked_position
                alert_naked_position(session_id, tranche_id, side, naked_since, retries)
            except Exception:
                pass
            action['action'] = 'critical_alert'

        elif elapsed_mins > NAKED_WATCHDOG_WARN_MINS:
            # 30-min escalation — fire emergency sell retry
            log.warning(
                f"[Reconciler][G37] Naked for {elapsed_mins:.1f} min. "
                f"Firing emergency sell retry for Tr{tranche_id}/{side.upper()} ({lots} lots)."
            )
            action['action'] = 'emergency_retry'

            if symbol and lots > 0:
                try:
                    exe = executor if executor is not None else _get_executor()
                    sell_result = await exe.emergency_execute(
                        symbol=symbol,
                        side='sell',
                        size=lots,
                        session_id=session_id,
                        tranche_id=tranche_id,
                        action=f'NAKED_RETRY_{side.upper()}',
                    )
                    naked['retries'] = retries + 1
                    action['sell_success'] = sell_result.success
                    action['retries']      = naked['retries']

                    if sell_result.success:
                        log.info(
                            f"[Reconciler][G37] Emergency sell filled for "
                            f"Tr{tranche_id}/{side.upper()}. Naked resolved."
                        )
                        # Remove from naked list — will be cleaned up by caller
                        naked['_resolved'] = True
                    else:
                        log.warning(
                            f"[Reconciler][G37] Emergency sell FAILED for "
                            f"Tr{tranche_id}/{side.upper()}: {sell_result.reason}"
                        )
                except Exception as exc:
                    log.exception(
                        f"[Reconciler][G37] Emergency sell raised: {exc}"
                    )

            try:
                from .mmmx_telegram import alert_naked_position
                alert_naked_position(
                    session_id, tranche_id, side, naked_since,
                    retries=naked.get('retries', retries)
                )
            except Exception:
                pass

        actions.append(action)

    # Remove resolved naked positions
    session['_naked_positions'] = [
        n for n in naked_list if not n.get('_resolved', False)
    ]

    return actions


def apply_recon_confirmation(session: Dict, operator_decision: Dict) -> None:
    """
    Apply an operator reconciliation decision to the session.

    operator_decision keys:
      divergence_id : str  — identifies the divergence (symbol + tranche_id + leg)
      action        : 'accept_db' | 'accept_exchange' | 'manual_close'
      notes         : str  — operator notes (optional)

    Actions:
      accept_db       — DB state is correct; mark divergence resolved in audit.
      accept_exchange — Force session state to match exchange (close the DB tranche leg).
      manual_close    — Mark as requiring manual close on exchange; add to _naked_positions.
    """
    divergence_id = operator_decision.get('divergence_id', '')
    action        = operator_decision.get('action', '')
    notes         = operator_decision.get('notes', '')
    session_id    = session.get('session_id', '')

    log.info(
        f"[MMMX][Reconciler] apply_recon_confirmation: "
        f"session={session_id[:8]} div_id={divergence_id!r} action={action!r}"
    )

    if action == 'accept_db':
        # Operator confirms DB is correct — log and mark resolved
        _audit_event(session_id, 'RECON_ACCEPT_DB', {
            'divergence_id': divergence_id,
            'notes':         notes,
        })
        log.info(
            f"[MMMX][Reconciler] Divergence {divergence_id!r} accepted (DB is authoritative)."
        )

    elif action == 'accept_exchange':
        # Force session state to match exchange: close the matching DB tranche leg
        _force_close_db_leg(session, divergence_id)
        _audit_event(session_id, 'RECON_ACCEPT_EXCHANGE', {
            'divergence_id': divergence_id,
            'notes':         notes,
        })
        log.warning(
            f"[MMMX][Reconciler] Divergence {divergence_id!r} resolved by "
            "forcing DB to match exchange (tranche leg closed in DB)."
        )

    elif action == 'manual_close':
        # Operator will close the position manually on exchange;
        # add to _naked_positions so the watchdog tracks it
        naked_positions = session.setdefault('_naked_positions', [])
        naked_positions.append({
            'divergence_id': divergence_id,
            'naked_since':   datetime.now(timezone.utc).isoformat(),
            'retries':       0,
            'source':        'recon_manual_close',
            'notes':         notes,
        })
        _audit_event(session_id, 'RECON_MANUAL_CLOSE', {
            'divergence_id': divergence_id,
            'notes':         notes,
        })
        log.warning(
            f"[MMMX][Reconciler] Divergence {divergence_id!r} flagged for manual close. "
            "Added to _naked_positions watchdog."
        )

    else:
        raise ValueError(
            f"Unknown action {action!r}. Must be one of: "
            "'accept_db', 'accept_exchange', 'manual_close'."
        )


def _force_close_db_leg(session: Dict, divergence_id: str) -> None:
    """
    Mark the tranche leg identified by divergence_id as CLOSED in the session dict.

    divergence_id format: "<symbol>:<tranche_id>:<leg>" or just tranche_id.
    Falls back to a best-effort symbol match if the full format is not present.
    """
    # Parse divergence_id — accept "symbol:tranche_id:leg" or just look for a match
    parts = str(divergence_id).split(':')
    target_symbol    = parts[0] if len(parts) >= 1 else ''
    target_tranche   = parts[1] if len(parts) >= 2 else ''
    target_leg       = parts[2] if len(parts) >= 3 else ''

    for t in session.get('tranches', []):
        t_id = str(t.get('tranche_id', ''))
        for leg in ('ce', 'pe'):
            pos = t.get(leg, {})
            if pos.get('status') != 'ACTIVE':
                continue
            sym = pos.get('symbol', '')

            # Match by symbol or tranche_id (lenient — operator confirmed the match)
            matched = (
                (target_symbol and sym == target_symbol)
                or (target_tranche and t_id == target_tranche)
            )
            if target_leg and matched:
                matched = matched and (leg == target_leg)

            if matched:
                pos['status'] = 'CLOSED'
                pos['closed_at'] = datetime.now(timezone.utc).isoformat()
                pos['close_reason'] = 'recon_accept_exchange'
                log.info(
                    f"[MMMX][Reconciler] Forced DB close: "
                    f"tranche={t_id} leg={leg} symbol={sym}"
                )
                return

    log.warning(
        f"[MMMX][Reconciler] _force_close_db_leg: no ACTIVE leg found "
        f"matching divergence_id={divergence_id!r}"
    )


def clear_all_residuals() -> None:
    """Hard reset — clears all in-memory residuals. For tests / emergency recovery."""
    with _lock:
        _residuals.clear()
