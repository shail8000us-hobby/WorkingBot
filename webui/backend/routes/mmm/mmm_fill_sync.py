"""
MMM Fill Sync — Ground-truth P&L reconciliation via exchange fills.

Every heartbeat this module fetches recent fills from Delta Exchange and
reconciles them against session positions. It is the universal backstop:
no matter how a position was closed (algo close, manual buyback, expiry,
external algo, crash-recovery) the fill sync catches it and books the
realized P&L at the ACTUAL exchange fill price.

Design principles:
  - Exchange fills are authoritative. Session state is a best-effort view.
  - Never double-book: positions track _fill_confirmed and _estimated_pnl_booked.
  - Non-blocking: all errors are logged and swallowed; heartbeat continues.
  - Additive: existing close paths still book P&L immediately (best-effort).
    Fill sync corrects the amount when the actual fill price is known.

Cursor:
  session['_fill_sync_cursor_us'] stores the microsecond UTC timestamp of
  the last fill we processed. Each sync advances this cursor forward so we
  never reprocess old fills.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

log = logging.getLogger(__name__)

LOT_SIZE_BTC = 0.001
# How many seconds before session start to look back on first sync
_FIRST_SYNC_LOOKBACK_SEC = 3600  # 1 hour


class FillSyncer:
    """
    Reconciles exchange fills with session position state.

    Instantiated once per MMMMonitor and reused across heartbeats.
    Thread-safe: only called from the heartbeat coroutine (single writer).
    """

    def __init__(self, monitor):
        # Weak reference to parent monitor — gives access to initializer,
        # session_id, and logging context without creating a retain cycle.
        self._monitor = monitor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync(self, rest_client, session: Dict, expiry: str) -> int:
        """
        Fetch recent fills and reconcile with session positions.

        Returns the number of positions updated (closed or P&L corrected).
        Swallows all exceptions so a fill sync failure never crashes the
        heartbeat.
        """
        try:
            return await self._sync_inner(rest_client, session, expiry)
        except Exception as e:
            sid = session.get('session_id', '?')
            log.warning(f"[{sid}] FillSync: unhandled error (non-critical): {e}",
                        exc_info=True)
            return 0

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    async def _sync_inner(self, rest_client, session: Dict, expiry: str) -> int:
        sid = session.get('session_id', '?')

        session_symbols = self._get_session_symbols(session, expiry)
        if not session_symbols:
            return 0

        # ── Determine time window ────────────────────────────────────────
        now_us = int(time.time() * 1_000_000)
        cursor_us = session.get('_fill_sync_cursor_us', 0)

        if not cursor_us:
            # First run: look back to session start (or 1 hour, whichever is later)
            # BUG-3 FIX: session uses 'entry_time' (not 'started_at') as the
            # authoritative start timestamp; fall back to 'created_at'.
            started_at = (
                session.get('entry_time', '')
                or session.get('started_at', '')
                or session.get('created_at', '')
            )
            if started_at:
                try:
                    dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    cursor_us = int(dt.timestamp() * 1_000_000)
                except Exception:
                    pass
            if not cursor_us:
                cursor_us = now_us - _FIRST_SYNC_LOOKBACK_SEC * 1_000_000

        if now_us <= cursor_us:
            return 0  # Clock skew / nothing to fetch

        # ── Fetch fills from exchange ────────────────────────────────────
        try:
            resp = await rest_client._request_with_retry(
                method='GET',
                path='/v2/fills',
                params={
                    'start_time': cursor_us,
                    'end_time': now_us,
                    'page_size': 100,
                },
            )
        except Exception as e:
            log.warning(f"[{sid}] FillSync: /v2/fills request failed: {e}")
            return 0

        fills = resp.get('result', [])
        if not isinstance(fills, list):
            return 0

        # ── Filter to session symbols only ───────────────────────────────
        relevant = []
        newest_fill_us = cursor_us
        for fill in fills:
            sym = (fill.get('product', {}).get('symbol', '')
                   or fill.get('product_symbol', ''))
            if sym not in session_symbols:
                continue
            # Parse fill timestamp → microseconds
            created_raw = fill.get('created_at', '')
            fill_us = _parse_ts_us(created_raw)
            if fill_us > newest_fill_us:
                newest_fill_us = fill_us
            relevant.append((fill, sym, fill_us))

        # Advance cursor past the newest fill we saw — intentionally unconditional.
        # Retrying unmatched fills next heartbeat would produce the same result:
        # fills with no matching session position can never be processed by this
        # module (that's Bug-B / reconciliation territory). Advancing prevents
        # endlessly re-fetching old fills on every heartbeat.
        if newest_fill_us > cursor_us:
            session['_fill_sync_cursor_us'] = newest_fill_us + 1

        if not relevant:
            return 0

        # ── Reconcile each fill ──────────────────────────────────────────
        updated = 0
        for fill, sym, fill_us in relevant:
            side_raw = (fill.get('side', '') or '').lower()
            # Only BUY fills are closes for our SHORT positions
            if side_raw != 'buy':
                continue

            fill_price = float(fill.get('price', 0) or 0)
            fill_size = abs(float(fill.get('size', 0) or 0))
            fill_id = str(fill.get('id', ''))
            order_id = str(fill.get('order_id', ''))
            commission = float(fill.get('commission', 0) or 0)
            fill_type = (fill.get('fill_type', '') or '').lower()

            if fill_price <= 0 or fill_size <= 0:
                continue

            n = self._process_close_fill(
                session=session,
                symbol=sym,
                fill_price=fill_price,
                fill_size=fill_size,
                fill_id=fill_id,
                order_id=order_id,
                commission=commission,
                fill_type=fill_type,
                expiry=expiry,
            )
            updated += n

        if updated:
            log.info(f"[{sid}] FillSync: updated {updated} position(s) from exchange fills")

        return updated

    def _process_close_fill(
        self,
        session: Dict,
        symbol: str,
        fill_price: float,
        fill_size: float,
        fill_id: str,
        order_id: str,
        commission: float,
        fill_type: str,
        expiry: str,
    ) -> int:
        """
        Match a single BUY fill to a session position and reconcile P&L.

        Matching: STRICT order_id only.
        Every close path (close_at_5, wind_down, manual_reduce, shift_recycle)
        stores close_order_id on the position when placing the buy order.
        FillSyncer matches fill.order_id == position.close_order_id.

        This is the only reliable match — the position record is the bridge
        between the SELL (entry) and BUY (close) orders, carrying entry_premium,
        lots, strike, type, and close_order_id.

        Fills with no matching close_order_id are logged and skipped.
        Those represent external closes (manual buyback, expiry) which are
        audit-reconciler territory, not fill-sync territory.

        Returns number of positions updated.
        """
        from .mmm_state import recompute_side_lots
        from .mmm_activity import log_activity

        if not order_id:
            return 0

        sid = session.get('session_id', '?')
        now_iso = datetime.now(timezone.utc).isoformat()

        # ── Find position by close_order_id (O(n) scan, n is small) ─────
        matched_pos = None
        matched_side_key = None
        matched_side = None

        for side_key in ('ce', 'pe'):
            side = session.get(side_key, {})
            for pos in side.get('positions', []):
                if pos.get('_fill_confirmed'):
                    continue
                close_oid = pos.get('close_order_id', '') or ''
                if close_oid and close_oid == order_id:
                    matched_pos = pos
                    matched_side_key = side_key
                    matched_side = side
                    break
            if matched_pos:
                break

        if not matched_pos:
            # No position owns this order — could be external close, expiry,
            # or manual buyback. Log at debug level (not warning — this is
            # expected for fills outside our close paths).
            log.debug(
                f"[{sid}] FillSync: no position with close_order_id={order_id} "
                f"for {symbol} — skipping (external close or expiry)"
            )
            return 0

        pos = matched_pos
        pos_strike = float(pos.get('strike', 0) or 0)
        pos_lots = int(pos.get('lots', 0) or 0)
        status = pos.get('status', '')

        # Guard: skip positions with no valid entry premium —
        # computing P&L at entry=0 would book a phantom loss.
        entry = float(pos.get('entry_premium', 0) or 0)
        if entry <= 0:
            log.warning(
                f"[{sid}] FillSync: skipping {matched_side_key.upper()} @ "
                f"{pos_strike:.0f} — entry_premium=0, cannot compute P&L"
            )
            return 0

        # Use fill_size (actual lots exchanged), capped at pos_lots,
        # so a partial fill never over-books P&L.
        lots_closed = min(fill_size, float(pos_lots)) if pos_lots > 0 else fill_size

        # ── P&L reconciliation ──────────────────────────────────────
        actual_pnl = (entry - fill_price) * lots_closed * LOT_SIZE_BTC

        # How much P&L was already booked for this position?
        estimated_booked = float(pos.get('_estimated_pnl_booked', 0) or 0)
        pnl_correction = actual_pnl - estimated_booked

        # Apply correction to session totals (both positive and negative —
        # negative = overstated estimate / maker rebate).
        # FILL-SYNC-ROUND-FIX: only touch realized_pnl when there is an actual
        # correction.  The previous unconditional round(realized + 0.0, 8) call
        # silently truncated the last few ULP digits of realized_pnl on every
        # fill confirmation even when nothing changed, causing a slow ratchet
        # divergence from pnl_adjustment (which was guarded and never touched).
        pos_type = pos.get('type', '')
        attr_key = 'pnl_initial' if pos_type == 'original' else 'pnl_adjustment'
        if abs(pnl_correction) > 1e-9:
            session['realized_pnl'] = round(
                session.get('realized_pnl', 0) + pnl_correction, 8)
            session[attr_key] = round(
                session.get(attr_key, 0.0) + pnl_correction, 8)

        # Commission correction (both directions — negative = rebate).
        estimated_comm = float(pos.get('_estimated_commission_booked', 0) or 0)
        comm_correction = commission - estimated_comm
        if abs(comm_correction) > 1e-9:
            session['total_fees'] = round(
                session.get('total_fees', 0) + comm_correction, 8)

        # ── Update position ─────────────────────────────────────────
        if status != 'closed':
            pos['status'] = 'closed'
            pos['closed_at'] = now_iso
            if not pos.get('close_reason'):
                pos['close_reason'] = f'fill_sync:{fill_type or "buyback"}'

        pos['close_fill_price'] = round(fill_price, 6)
        pos['close_fill_id'] = fill_id
        pos['_fill_confirmed'] = True
        # Record final booked amounts for audit trail
        pos['_actual_pnl_booked'] = round(actual_pnl, 8)
        pos['_pnl_correction_applied'] = round(pnl_correction, 8)

        recompute_side_lots(matched_side)

        log_level = 'info'
        correction_note = ''
        if abs(pnl_correction) > 0.0001:
            correction_note = (f', correction from estimate: '
                               f'{pnl_correction:+.6f} USD')
            log_level = 'warning'

        log.log(
            logging.INFO if log_level == 'info' else logging.WARNING,
            f"[{sid}] FillSync ✅ {matched_side_key.upper()} {pos_lots} lots "
            f"@ {pos_strike:.0f} confirmed closed at {fill_price:.4f} "
            f"(P&L: {actual_pnl:+.6f} USD{correction_note}) "
            f"[order_id={order_id}]"
        )
        log_activity(
            'fill_sync_confirmed',
            f'✅ Fill confirmed: {matched_side_key.upper()} {pos_lots} lots '
            f'@ {pos_strike:.0f} closed at {fill_price:.4f} '
            f'(P&L: {actual_pnl:+.4f} USD{correction_note})',
            sid, log_level,
            {
                'side': matched_side_key,
                'strike': pos_strike,
                'lots': pos_lots,
                'fill_price': round(fill_price, 6),
                'fill_id': fill_id,
                'order_id': order_id,
                'pos_type': pos_type,
                'actual_pnl': round(actual_pnl, 8),
                'pnl_correction': round(pnl_correction, 8),
                'commission_correction': round(comm_correction, 8),
            }
        )
        return 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_session_symbols(self, session: Dict, expiry: str) -> set:
        """All symbols this session has ever managed."""
        symbols = set()
        for side_key in ('ce', 'pe'):
            side = session.get(side_key, {})
            opt = 'call' if side_key == 'ce' else 'put'

            sym = side.get('symbol', '')
            if sym:
                symbols.add(sym)

            active_strike = side.get('active_strike', 0)
            if active_strike:
                symbols.add(self._monitor.initializer.build_symbol(
                    opt, 'BTC', int(active_strike), expiry))

            for pos in side.get('positions', []):
                s = pos.get('strike', 0)
                if s:
                    symbols.add(self._monitor.initializer.build_symbol(
                        opt, 'BTC', int(s), expiry))

        return symbols


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _parse_ts_us(ts_raw) -> int:
    """Parse a timestamp into microseconds since epoch. Returns 0 on failure."""
    if not ts_raw:
        return 0
    if isinstance(ts_raw, (int, float)):
        # Already microseconds or seconds — normalise
        v = int(ts_raw)
        if v < 1e13:          # seconds range (< year 2286 as microseconds)
            v *= 1_000_000
        return v
    try:
        dt = datetime.fromisoformat(str(ts_raw).replace('Z', '+00:00'))
        return int(dt.timestamp() * 1_000_000)
    except Exception:
        return 0
