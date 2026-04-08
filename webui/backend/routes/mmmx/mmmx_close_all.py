"""
MMMX Close-All — Production-Hardened Emergency Close

Spec: MMMX_COMPLETE.md Hard Stop Execution Rule + Q44, Q47, G36.

Key function:
  async def close_all(session, reason, executor, audit) -> CloseAllReport

Execution strategy:
  SHORT legs (tranche ce/pe, status=ACTIVE):
    → emergency_execute (MARKET, buy-to-close) — must fill; log CRITICAL on failure.
  LONG legs (hedge ce/pe, status=ACTIVE):
    → smart_execute (LIMIT at bid, sell) — best-effort; mark ORPHANED if fails (Q44, Q47).

Recovery tranches ARE full citizens — closed in the same loop as deployment tranches (Q33).

Isolation rule: ZERO imports from routes.mmm.* in this file.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .mmmx_constants import TrncStatus, HedgeStatus, SessionStatus
from .mmmx_state import transition_status
from .mmmx_websocket import emit_safety
from .mmmx_telegram import alert_hard_stop, alert_dte_close, alert_session_complete
from .mmmx_activity import log_activity

log = logging.getLogger('mmmx_close_all')


# ── CloseAllReport ─────────────────────────────────────────────────────────────

@dataclass
class CloseAllReport:
    """
    Summary of a close_all execution.

    shorts_failed > 0 → logged CRITICAL but session still transitions to COMPLETE.
    hedges_failed  > 0 → logged WARNING; hedge is marked ORPHANED (non-fatal per Q47).
    """
    reason:            str
    shorts_attempted:  int               = 0
    shorts_filled:     int               = 0
    shorts_failed:     int               = 0
    hedges_attempted:  int               = 0
    hedges_filled:     int               = 0
    hedges_failed:     int               = 0
    total_fees_paid:   float             = 0.0
    close_errors:      List[Dict]        = field(default_factory=list)
    completed_at:      str               = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'reason':            self.reason,
            'shorts_attempted':  self.shorts_attempted,
            'shorts_filled':     self.shorts_filled,
            'shorts_failed':     self.shorts_failed,
            'hedges_attempted':  self.hedges_attempted,
            'hedges_filled':     self.hedges_filled,
            'hedges_failed':     self.hedges_failed,
            'total_fees_paid':   self.total_fees_paid,
            'close_errors':      self.close_errors,
            'completed_at':      self.completed_at,
        }


# ── close_all ─────────────────────────────────────────────────────────────────

async def close_all(
    session: dict,
    reason: str,
    executor,
    audit,
) -> CloseAllReport:
    """
    Close every active leg in the session.

    SHORT legs (tranche ce/pe): emergency_execute (MARKET). Fatal-ish — log CRITICAL on fail.
    LONG legs (hedge ce/pe):    smart_execute (LIMIT at bid). Non-fatal — mark ORPHANED on fail.

    After all legs attempted:
      - Transitions session to COMPLETE.
      - emit_safety() (sync — NOT awaited).
      - Telegram alerts.
      - Audit log entry with full report.

    Returns CloseAllReport.
    """
    session_id = session.get('session_id', 'unknown')
    report = CloseAllReport(reason=reason)

    log.critical(
        f"[MMMX][{session_id[:8]}] close_all initiated: reason={reason}"
    )

    # ── 1. Close SHORT legs (deployment + recovery tranches) ───────────────────
    for tranche in session.get('tranches', []):
        tranche_id = tranche.get('tranche_id')
        tranche_type = tranche.get('type', 'deployment')

        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg or leg.get('status') != TrncStatus.ACTIVE:
                continue

            symbol = leg.get('symbol', '')
            lots = leg.get('lots', 0)

            if lots <= 0 or not symbol:
                continue

            report.shorts_attempted += 1
            log.info(
                f"[MMMX][{session_id[:8]}] Emergency close SHORT: "
                f"tranche={tranche_id}({tranche_type})/{side} symbol={symbol} lots={lots}"
            )

            try:
                result = await executor.emergency_execute(
                    symbol=symbol,
                    side='buy',     # buy-to-close the short
                    size=lots,
                    session_id=session_id,
                    tranche_id=tranche_id,
                    action='EMERGENCY_CLOSE',
                    position=leg,
                )

                # Fee accounting — verbatim from ExecutionResult
                if result.success and result.fees_paid:
                    session['fees_tracking']['total_fees_paid'] += result.fees_paid
                    session['fees_tracking']['last_fee_charge'] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    report.total_fees_paid += result.fees_paid

                # Audit record regardless of success
                try:
                    audit.enqueue_trade(
                        session_id=session_id,
                        action='BUY',
                        symbol=symbol,
                        lots=result.filled_size if result.success else lots,
                        price=result.avg_price,
                        order_id=result.order_id,
                        client_order_id=result.client_order_id,
                        fees_paid=result.fees_paid,
                        tranche_id=tranche_id,
                        side=side,
                        extra={
                            'close_reason': reason,
                            'success':      result.success,
                            'tranche_type': tranche_type,
                        },
                    )
                except Exception as exc:
                    log.error(f"[MMMX][{session_id[:8]}] audit.enqueue_trade failed: {exc}")

                if result.success:
                    leg['status'] = TrncStatus.CLOSED
                    leg['_being_closed'] = False
                    report.shorts_filled += 1
                    log.info(
                        f"[MMMX][{session_id[:8]}] SHORT closed OK: "
                        f"tranche={tranche_id}/{side} avg_price={result.avg_price:.4f}"
                    )
                else:
                    report.shorts_failed += 1
                    report.close_errors.append({
                        'tranche_id': str(tranche_id),
                        'side':       side,
                        'error':      result.reason,
                    })
                    log.critical(
                        f"[MMMX][{session_id[:8]}] SHORT close FAILED: "
                        f"tranche={tranche_id}/{side}: {result.reason}"
                    )

            except Exception as exc:
                report.shorts_failed += 1
                report.close_errors.append({
                    'tranche_id': str(tranche_id),
                    'side':       side,
                    'error':      str(exc),
                })
                log.critical(
                    f"[MMMX][{session_id[:8]}] emergency_execute exception "
                    f"tranche={tranche_id}/{side}: {exc}"
                )
                try:
                    audit.enqueue_event(
                        session_id=session_id,
                        category='CLOSE_ERROR',
                        message=f"Emergency close exception: {exc}",
                        data={
                            'tranche_id': str(tranche_id),
                            'side':       side,
                            'symbol':     symbol,
                        },
                    )
                except Exception:
                    pass

    # ── 2. Close LONG legs (hedges) — LIMIT at bid, non-fatal (Q44, Q47) ──────
    for hedge in session.get('hedges', []):
        if hedge.get('status') != HedgeStatus.ACTIVE:
            continue

        hedge_id = hedge.get('hedge_id', 'unknown')

        for side in ('ce', 'pe'):
            leg = hedge.get(side, {})
            if not leg or leg.get('status') != HedgeStatus.ACTIVE:
                continue

            symbol = leg.get('symbol', '')
            lots = leg.get('lots', 0)

            if lots <= 0 or not symbol:
                continue

            report.hedges_attempted += 1
            log.info(
                f"[MMMX][{session_id[:8]}] Limit-sell LONG hedge: "
                f"hedge={hedge_id}/{side} symbol={symbol} lots={lots}"
            )

            try:
                result = await executor.smart_execute(
                    symbol=symbol,
                    side='sell',        # sell-to-close the long
                    size=lots,
                    session_id=session_id,
                    tranche_id=hedge_id,
                    action='HEDGE_CLOSE',
                    position=leg,
                    use_bid_entry=True,
                )

                # Fee accounting — verbatim from ExecutionResult
                if result.success and result.fees_paid:
                    session['fees_tracking']['total_fees_paid'] += result.fees_paid
                    session['fees_tracking']['last_fee_charge'] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    report.total_fees_paid += result.fees_paid

                # Audit record regardless of success
                try:
                    audit.enqueue_trade(
                        session_id=session_id,
                        action='SELL',
                        symbol=symbol,
                        lots=result.filled_size if result.success else lots,
                        price=result.avg_price,
                        order_id=result.order_id,
                        client_order_id=result.client_order_id,
                        fees_paid=result.fees_paid,
                        tranche_id=hedge_id,
                        side=side,
                        extra={
                            'close_reason': reason,
                            'success':      result.success,
                            'hedge_close':  True,
                        },
                    )
                except Exception as exc:
                    log.error(f"[MMMX][{session_id[:8]}] audit.enqueue_trade (hedge) failed: {exc}")

                if result.success:
                    leg['status'] = HedgeStatus.CLOSED
                    leg['_being_closed'] = False
                    report.hedges_filled += 1
                    log.info(
                        f"[MMMX][{session_id[:8]}] LONG hedge closed OK: "
                        f"hedge={hedge_id}/{side} avg_price={result.avg_price:.4f}"
                    )
                else:
                    # Non-fatal — hedge orphaned, not CRITICAL (Q47)
                    leg['status'] = HedgeStatus.ORPHANED
                    leg['_being_closed'] = False
                    report.hedges_failed += 1
                    report.close_errors.append({
                        'tranche_id': str(hedge_id),
                        'side':       side,
                        'error':      f"hedge_orphaned: {result.reason}",
                    })
                    log.warning(
                        f"[MMMX][{session_id[:8]}] LONG hedge limit-sell did not fill: "
                        f"hedge={hedge_id}/{side} — marking ORPHANED (will expire worthless, per Q47)"
                    )

            except Exception as exc:
                leg['status'] = HedgeStatus.ORPHANED
                report.hedges_failed += 1
                report.close_errors.append({
                    'tranche_id': str(hedge_id),
                    'side':       side,
                    'error':      f"hedge_exception: {exc}",
                })
                log.warning(
                    f"[MMMX][{session_id[:8]}] hedge smart_execute exception "
                    f"hedge={hedge_id}/{side}: {exc} — marking ORPHANED"
                )
                try:
                    audit.enqueue_event(
                        session_id=session_id,
                        category='HEDGE_ORPHANED',
                        message=f"Hedge smart_execute exception: {exc}",
                        data={
                            'hedge_id': str(hedge_id),
                            'side':     side,
                            'symbol':   symbol,
                        },
                    )
                except Exception:
                    pass

    # ── 3. Finalize ────────────────────────────────────────────────────────────
    report.completed_at = datetime.now(timezone.utc).isoformat()

    # Transition session to COMPLETE (best-effort — may already be terminal)
    try:
        transition_status(session, SessionStatus.COMPLETE, reason=reason)
    except ValueError as exc:
        log.error(
            f"[MMMX][{session_id[:8]}] transition_status to COMPLETE failed: {exc} "
            "(session may already be terminal)"
        )

    session['_last_beat_at'] = datetime.now(timezone.utc).isoformat()

    # emit_safety — regular def, NEVER awaited
    try:
        emit_safety(
            session_id=session_id,
            safety_type=reason.lower(),
            level='critical',
            message=(
                f"Session COMPLETE via {reason}. "
                f"shorts={report.shorts_filled}/{report.shorts_attempted} filled, "
                f"hedges={report.hedges_filled}/{report.hedges_attempted} filled "
                f"({report.hedges_failed} orphaned), "
                f"errors={len(report.close_errors)}"
            ),
            details=report.to_dict(),
        )
    except Exception as exc:
        log.error(f"[MMMX][{session_id[:8]}] emit_safety in close_all failed: {exc}")

    # Telegram alerts
    try:
        if reason == 'HARD_STOP':
            alert_hard_stop(
                session_id=session_id,
                total_pnl=session.get('portfolio_pnl', 0.0),
                hard_stop_usd=session.get('hard_stop_usd', 0.0),
            )
        elif reason == 'DTE_CLOSE':
            alert_dte_close(
                session_id=session_id,
                dte=0.0,
            )
        alert_session_complete(
            session_id=session_id,
            reason=reason,
            final_pnl=session.get('portfolio_pnl', 0.0),
        )
    except Exception as exc:
        log.error(f"[MMMX][{session_id[:8]}] Telegram in close_all failed: {exc}")

    # Audit event with full report
    try:
        audit.enqueue_event(
            session_id=session_id,
            category='CLOSE_ALL',
            message=(
                f"close_all complete: {reason} — "
                f"{report.shorts_filled}/{report.shorts_attempted} shorts, "
                f"{report.hedges_filled}/{report.hedges_attempted} hedges"
            ),
            data=report.to_dict(),
        )
    except Exception as exc:
        log.error(f"[MMMX][{session_id[:8]}] audit enqueue_event in close_all failed: {exc}")

    # Activity log
    try:
        log_activity(
            event_type='session_complete',
            message=(
                f"Session completed via {reason}. "
                f"shorts_filled={report.shorts_filled}, errors={len(report.close_errors)}"
            ),
            session_id=session_id,
            level='critical' if report.close_errors else 'info',
            data=report.to_dict(),
        )
    except Exception:
        pass

    log.info(
        f"[MMMX][{session_id[:8]}] close_all done: "
        f"shorts={report.shorts_filled}/{report.shorts_attempted}, "
        f"hedges={report.hedges_filled}/{report.hedges_attempted}, "
        f"fees_paid={report.total_fees_paid:.4f}, "
        f"errors={len(report.close_errors)}"
    )

    return report
