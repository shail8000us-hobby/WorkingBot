"""
MMMX Executor — The ONLY module that calls exchange order APIs for MMMX.

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 4 Phase 2.

Key functions:
  smart_execute(...)             → ExecutionResult  (limit order + reprice loop)
  emergency_execute(...)         → ExecutionResult  (IOC path, no reprice)
  preflight_margin_check(...)    → str (MarginVerdict constant)
  compute_client_order_id(...)   → str

Order lifecycle (smart_execute):
  1. compute_client_order_id — sha256(session_id|tranche_id|side|action|minute_bucket)[:16]
  2. fetch_open_orders_by_client_id — dedup: if already exists, return it
  3. preflight_margin_check:
       SELL util >= 80% → MARGIN_BLOCKED
       BUY  util >= 95% → MARGIN_CRITICAL
  4. Mark position['_being_closed'] = True / _being_closed_at (180s TTL)
  5. Place limit at mid-price (or bid for use_bid_entry buys)
  6. Reprice loop (max_reprice_attempts × FILL_TIMEOUT_SECS each):
       - Filled → goto 8
       - midloop_margin_check:
           >= 95% → abort MARGIN_CRITICAL
           >= 85% → break loop → market fallback
       - Cancel + reprice (first half: mid, second half: bid/ask)
  7. Market fallback: emergency_execute (IOC)
  8. Record fill to audit log, clear _being_closed
  9. Return ExecutionResult

Isolation rule: ZERO imports from routes.mmm.* in this file.
All margin queries go through mmmx_margin_guardian (the designated bridge).
"""

import asyncio
import hashlib
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Ensure bot package root is on sys.path
_BOT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
if _BOT_ROOT not in sys.path:
    sys.path.insert(0, _BOT_ROOT)

from .mmmx_constants import (
    LOT_SIZE_BTC,
    SMART_EXECUTE_REPRICE_ATTEMPTS,
    FILL_TIMEOUT_SECS,
    BEING_CLOSED_TTL_SECS,
    FEE_RATE_MAKER,
    FEE_RATE_TAKER,
)

log = logging.getLogger('mmmx_executor')

# ── Execution constants ────────────────────────────────────────────────────────
FILL_CHECK_INTERVAL       = 3      # Poll fill status every 3 seconds
POST_ONLY_RETRIES         = 3      # Max attempts for initial post-only placement
POST_ONLY_RETRY_DELAY     = 1.5    # Seconds between post-only retries
INITIAL_PLACEMENT_RETRIES = 3      # Retries if initial placement fails

ORDER_STATES_FILLED = {'filled', 'closed', 'completed'}
ORDER_STATES_DEAD   = {'cancelled', 'canceled', 'rejected'}

# Margin thresholds for order gating
MARGIN_SELL_BLOCK_PCT      = 80.0  # Preflight: SELL blocked at >= 80%
MARGIN_BUY_BLOCK_PCT       = 95.0  # Preflight: BUY blocked at >= 95%
MARGIN_MIDLOOP_ABORT_PCT   = 95.0  # Mid-loop: abort immediately
MARGIN_MIDLOOP_FALLBACK_PCT = 85.0 # Mid-loop: fall through to market

EMERGENCY_MAX_ATTEMPTS = 2
EMERGENCY_FILL_WAIT    = 2.0       # Seconds after IOC placement before status check


# ── Margin verdicts ────────────────────────────────────────────────────────────
class MarginVerdict:
    OK              = 'OK'
    MARGIN_BLOCKED  = 'MARGIN_BLOCKED'   # SELL blocked (util >= 80%)
    MARGIN_CRITICAL = 'MARGIN_CRITICAL'  # BUY blocked (util >= 95%), or abort


# ── ExecutionResult ────────────────────────────────────────────────────────────
@dataclass
class ExecutionResult:
    """Return value from smart_execute and emergency_execute."""
    success:         bool
    filled_size:     int   = 0
    avg_price:       float = 0.0
    attempts:        int   = 0
    total_ms:        int   = 0
    reason:          str   = ''
    order_id:        str   = ''
    client_order_id: str   = ''
    fees_paid:       float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success':         self.success,
            'filled_size':     self.filled_size,
            'avg_price':       self.avg_price,
            'attempts':        self.attempts,
            'total_ms':        self.total_ms,
            'reason':          self.reason,
            'order_id':        self.order_id,
            'client_order_id': self.client_order_id,
            'fees_paid':       self.fees_paid,
        }


# ── Client order ID ────────────────────────────────────────────────────────────
def compute_client_order_id(
    session_id: str,
    tranche_id: Any,
    side: str,
    action: str,
) -> str:
    """
    Deterministic, idempotent client_order_id.

    sha256(session_id|tranche_id|side|action|minute_bucket)[:16]

    minute_bucket = UTC epoch seconds rounded down to the whole minute.
    Idempotent within one minute — deduplicates retries that occur within
    the same minute window for the same intent.
    """
    minute_bucket = int(time.time() // 60) * 60
    raw = f"{session_id}|{tranche_id}|{side}|{action}|{minute_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Activity log helper (fire-and-forget) ──────────────────────────────────────
def _log_activity(
    event_type: str,
    message: str,
    session_id: str = None,
    level: str = 'info',
    data: dict = None,
) -> None:
    try:
        from .mmmx_activity import log_activity
        log_activity(event_type, message, session_id=session_id, level=level, data=data)
    except Exception as exc:
        log.debug(f"Activity log suppressed: {exc}")


# ── MMMXExecutor ───────────────────────────────────────────────────────────────
class MMMXExecutor:
    """
    Smart execution engine for MMMX.

    This is the ONLY class that places orders on the exchange for MMMX.
    Completely separate from MMM's executor — zero shared code or imports.

    CRITICAL: httpx.AsyncClient binds to the event loop where first used.
    A fresh AsyncDeltaClient is created per async call to avoid
    'Future attached to a different loop' errors.
    """

    # ── REST client factory ────────────────────────────────────────────────────

    def _create_rest_client(self):
        """
        Create a FRESH AsyncDeltaClient bound to the CURRENT event loop.
        Must NOT be cached across asyncio.run() calls or threads.
        """
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials
        creds = get_api_credentials()
        return AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=bool(creds.get('testnet', False)),
        )

    # ── Margin checks ──────────────────────────────────────────────────────────

    async def preflight_margin_check(
        self,
        side: str,
        session_id: str = None,
    ) -> str:
        """
        Check margin before placing an order.

        Returns a MarginVerdict constant:
          OK              — safe to proceed
          MARGIN_BLOCKED  — SELL blocked: util >= 80%
          MARGIN_CRITICAL — BUY blocked: util >= 95%
        """
        try:
            from .mmmx_margin_guardian import get_margin_guardian
            util = await get_margin_guardian().current_utilization()
        except Exception as exc:
            log.warning(f"[MMMX] Preflight margin check failed ({exc}) — defaulting OK")
            return MarginVerdict.OK

        side_lower = side.lower()
        if side_lower == 'sell' and util >= MARGIN_SELL_BLOCK_PCT:
            log.warning(
                f"[MMMX] Preflight SELL blocked: util={util:.1f}% >= {MARGIN_SELL_BLOCK_PCT}%"
            )
            _log_activity(
                'margin_blocked',
                f"SELL blocked: margin util={util:.1f}%",
                session_id=session_id, level='warning',
                data={'util_pct': util, 'threshold': MARGIN_SELL_BLOCK_PCT},
            )
            return MarginVerdict.MARGIN_BLOCKED

        if side_lower == 'buy' and util >= MARGIN_BUY_BLOCK_PCT:
            log.warning(
                f"[MMMX] Preflight BUY blocked: util={util:.1f}% >= {MARGIN_BUY_BLOCK_PCT}%"
            )
            _log_activity(
                'margin_critical',
                f"BUY blocked: margin CRITICAL util={util:.1f}%",
                session_id=session_id, level='error',
                data={'util_pct': util, 'threshold': MARGIN_BUY_BLOCK_PCT},
            )
            return MarginVerdict.MARGIN_CRITICAL

        return MarginVerdict.OK

    async def _midloop_margin_check(self) -> str:
        """
        Check margin inside the reprice loop.

        Returns:
          MARGIN_CRITICAL — abort immediately, cancel order
          MARGIN_BLOCKED  — fall through to market (emergency_execute)
          OK              — continue normal reprice
        """
        try:
            from .mmmx_margin_guardian import get_margin_guardian
            util = await get_margin_guardian().current_utilization()
        except Exception:
            return MarginVerdict.OK

        if util >= MARGIN_MIDLOOP_ABORT_PCT:
            return MarginVerdict.MARGIN_CRITICAL
        if util >= MARGIN_MIDLOOP_FALLBACK_PCT:
            return MarginVerdict.MARGIN_BLOCKED
        return MarginVerdict.OK

    # ── Quote helpers ──────────────────────────────────────────────────────────

    async def _fetch_quotes(self, symbol: str, rest_client) -> Optional[Dict]:
        """Fetch fresh bid/ask from L2 orderbook, falling back to ticker."""
        result = {
            'best_bid':  0.0,
            'best_ask':  0.0,
            'bid_size':  0,
            'ask_size':  0,
            'tick_size': 0.01,
            'fresh':     False,
        }

        try:
            orderbook = await rest_client.get_orderbook(symbol)
            if orderbook:
                buys  = orderbook.get('buy', [])
                sells = orderbook.get('sell', [])
                if buys and sells:
                    result['best_bid'] = float(buys[0].get('price', 0))
                    result['best_ask'] = float(sells[0].get('price', 0))
                    result['bid_size'] = float(buys[0].get('size', 0))
                    result['ask_size'] = float(sells[0].get('size', 0))
                    result['fresh'] = True
                    log.debug(
                        f"[MMMX] L2 {symbol}: bid={result['best_bid']:.2f} "
                        f"ask={result['best_ask']:.2f}"
                    )
        except Exception as exc:
            log.warning(f"[MMMX] L2 orderbook failed for {symbol}: {exc}")

        # Ticker fallback
        if not result['fresh'] or result['best_bid'] == 0:
            try:
                resp = await rest_client._request_with_retry('GET', f'/v2/tickers/{symbol}')
                ticker = resp.get('result', resp)
                quotes = ticker.get('quotes', {})
                result['best_bid']  = float(quotes.get('best_bid') or 0)
                result['best_ask']  = float(quotes.get('best_ask') or 0)
                result['tick_size'] = float(ticker.get('tick_size') or 0.01)
                result['fresh'] = True
            except Exception as exc:
                log.warning(f"[MMMX] Ticker fallback failed for {symbol}: {exc}")

        return result if result['fresh'] else None

    def _calc_mid(self, quotes: Dict) -> float:
        """Calculate mid-price rounded to tick size."""
        bid  = quotes.get('best_bid', 0)
        ask  = quotes.get('best_ask', 0)
        tick = quotes.get('tick_size', 0.01)
        if bid <= 0 or ask <= 0:
            return 0.0
        mid = (bid + ask) / 2.0
        if tick > 0:
            mid = round(mid / tick) * tick
        return round(mid, 2)

    # ── Order placement helpers ────────────────────────────────────────────────

    async def _place_limit_order(
        self,
        symbol: str,
        side: str,
        size: int,
        price: float,
        reduce_only: bool,
        rest_client,
        client_order_id: str = None,
    ) -> Optional[Dict]:
        """Place a post-only GTC limit order. Retries on post-only rejection."""
        for attempt in range(1, POST_ONLY_RETRIES + 1):
            try:
                response = await rest_client.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=price,
                    size=int(size),
                    order_type='limit_order',
                    time_in_force='gtc',
                    post_only=True,
                    reduce_only=reduce_only,
                    client_order_id=client_order_id,
                )
                result = response.get('result', response)
                if result and result.get('id'):
                    return result

                err_str = str(result.get('error', result))
                if 'post_only' in err_str.lower() or 'would_cross' in err_str.lower():
                    log.warning(
                        f"[MMMX] Post-only rejected (attempt {attempt}): {err_str}"
                    )
                    if attempt < POST_ONLY_RETRIES:
                        await asyncio.sleep(POST_ONLY_RETRY_DELAY)
                        continue
                return result

            except Exception as exc:
                log.warning(f"[MMMX] Place limit attempt {attempt} failed: {exc}")
                if attempt < POST_ONLY_RETRIES:
                    await asyncio.sleep(POST_ONLY_RETRY_DELAY)
        return None

    async def _cancel_order(
        self,
        order_id: str,
        product_id: Any,
        rest_client,
    ) -> bool:
        """Cancel an open order. Returns True on success."""
        try:
            await rest_client.cancel_order(
                order_id=order_id,
                product_id=product_id,
            )
            return True
        except Exception as exc:
            log.warning(f"[MMMX] Cancel order {order_id} failed: {exc}")
            return False

    async def _get_order_status(
        self,
        order_id: str,
        product_id: Any,
        rest_client,
    ) -> Optional[Dict]:
        """Fetch order status dict. Returns None on error."""
        try:
            resp = await rest_client.get_order(
                order_id=order_id,
                product_id=product_id,
            )
            if isinstance(resp, dict):
                return resp.get('result', resp)
            return resp
        except Exception as exc:
            log.warning(f"[MMMX] Get order status {order_id} failed: {exc}")
            return None

    async def _wait_for_fill(
        self,
        order_id: str,
        product_id: Any,
        timeout: float,
        rest_client,
    ):
        """
        Poll order status every FILL_CHECK_INTERVAL seconds until filled,
        dead, or timeout.

        Returns:
            (filled: bool, order_data: dict | None)
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            await asyncio.sleep(FILL_CHECK_INTERVAL)
            data = await self._get_order_status(order_id, product_id, rest_client)
            if data is None:
                continue
            state = str(data.get('state', '')).lower()
            if state in ORDER_STATES_FILLED:
                return True, data
            if state in ORDER_STATES_DEAD:
                data['_dead'] = True
                return False, data
        return False, None

    async def _fetch_open_orders_by_client_id(
        self,
        symbol: str,
        client_order_id: str,
        rest_client,
    ) -> Optional[Dict]:
        """Return an open order matching client_order_id, or None."""
        try:
            open_orders = await rest_client.get_open_orders_by_symbol(symbol)
            return next(
                (
                    o for o in open_orders
                    if str(o.get('client_order_id', '')) == str(client_order_id)
                ),
                None,
            )
        except Exception as exc:
            log.debug(f"[MMMX] Dedup open-order fetch failed: {exc}")
            return None

    # ── Audit log helper ───────────────────────────────────────────────────────

    def _audit_trade(
        self,
        session_id: str,
        action: str,
        symbol: str,
        lots: int,
        price: float,
        tranche_id: Any,
        order_id: str,
        client_order_id: str,
        fees_paid: float,
    ) -> None:
        try:
            from .mmmx_audit_log import get_audit_log
            get_audit_log().enqueue_trade(
                session_id=session_id or '',
                action=action,
                symbol=symbol,
                lots=lots,
                price=price,
                tranche_id=tranche_id,
                side='ce' if symbol.upper().startswith('C-') else 'pe',
                order_id=order_id,
                client_order_id=client_order_id,
                fees_paid=fees_paid,
            )
        except Exception as exc:
            log.debug(f"[MMMX] Audit trade log suppressed: {exc}")

    def _emit_order_event(self, event_fn: str, **kwargs) -> None:
        """
        Best-effort order lifecycle emitter bridge.

        Keeps execution path non-blocking if websocket layer is unavailable.
        """
        try:
            from . import mmmx_websocket as ws
            fn = getattr(ws, event_fn, None)
            if callable(fn):
                fn(**kwargs)
        except Exception as exc:
            log.debug(f"[MMMX] {event_fn} suppressed: {exc}")

    # ── smart_execute ──────────────────────────────────────────────────────────

    async def smart_execute(
        self,
        symbol: str,
        side: str,
        size: int,
        reduce_only: bool = False,
        max_reprice_attempts: int = None,
        use_bid_entry: bool = False,
        session_id: str = None,
        tranche_id: Any = None,
        action: str = 'TRADE',
        position: Dict = None,
    ) -> ExecutionResult:
        """
        Place a limit order with a reprice loop and market fallback.

        Args:
            symbol:               Options symbol (e.g. 'C-BTC-100000-280326')
            side:                 'buy' | 'sell'
            size:                 Number of lots
            reduce_only:          Only reduce an existing position
            max_reprice_attempts: Override SMART_EXECUTE_REPRICE_ATTEMPTS
            use_bid_entry:        BUY orders start at best_bid (cheaper, maker)
            session_id:           For activity/audit logging
            tranche_id:           For audit trail
            action:               Short label for client_order_id and audit log
            position:             Optional position dict — will be marked
                                  _being_closed=True with a 180s TTL

        Returns:
            ExecutionResult
        """
        t0 = time.time()
        _max = (
            max_reprice_attempts
            if max_reprice_attempts is not None
            else SMART_EXECUTE_REPRICE_ATTEMPTS
        )
        _aggressive_from = (_max // 2) + 1
        mode = 'limit'

        coid = compute_client_order_id(session_id or '', tranche_id or '', side, action)

        log.info(f"[MMMX] smart_execute: {side.upper()} {size} {symbol} coid={coid}")
        _log_activity(
            'order_placing',
            f"{side.upper()} {size} {symbol}",
            session_id=session_id, level='info',
            data={'symbol': symbol, 'side': side, 'size': size, 'coid': coid},
        )

        self._emit_order_event(
            'emit_order_intent',
            session_id=session_id or '',
            symbol=symbol,
            side=side,
            requested_size=size,
            mode=mode,
            attempt=1,
            client_order_id=coid,
            tranche_id=tranche_id,
            action=action,
            extra={
                'reduce_only': bool(reduce_only),
                'max_reprice_attempts': _max,
                'use_bid_entry': bool(use_bid_entry),
            },
        )

        rest = self._create_rest_client()

        # Step 2: Dedup — find existing open order with same client_order_id
        existing = await self._fetch_open_orders_by_client_id(symbol, coid, rest)
        if existing and existing.get('id'):
            log.info(
                f"[MMMX] Dedup: found existing order {existing['id']} for coid={coid}"
            )
            _log_activity(
                'order_placed',
                f"Dedup: found existing order {existing['id']} — skipping new POST",
                session_id=session_id, level='info',
                data={'order_id': existing['id'], 'coid': coid},
            )
            self._emit_order_event(
                'emit_order_ack',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=0,
                client_order_id=coid,
                order_id=str(existing['id']),
                tranche_id=tranche_id,
                action=action,
                price=float(existing.get('limit_price') or 0),
                extra={'deduped': True, 'state': str(existing.get('state', 'open'))},
            )
            return ExecutionResult(
                success=True,
                filled_size=0,
                avg_price=float(existing.get('limit_price') or 0),
                attempts=0,
                total_ms=int((time.time() - t0) * 1000),
                reason='DEDUPED_EXISTING_ORDER',
                order_id=str(existing['id']),
                client_order_id=coid,
            )

        # Step 3: Preflight margin check
        verdict = await self.preflight_margin_check(side, session_id)
        if verdict == MarginVerdict.MARGIN_BLOCKED:
            self._emit_order_event(
                'emit_order_failed',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=0,
                client_order_id=coid,
                reason_code='MARGIN_BLOCKED',
                reason='Preflight margin policy blocked order',
                tranche_id=tranche_id,
                action=action,
            )
            return ExecutionResult(
                success=False,
                total_ms=int((time.time() - t0) * 1000),
                reason='MARGIN_BLOCKED',
                client_order_id=coid,
            )
        if verdict == MarginVerdict.MARGIN_CRITICAL:
            self._emit_order_event(
                'emit_order_failed',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=0,
                client_order_id=coid,
                reason_code='MARGIN_CRITICAL',
                reason='Preflight margin policy entered critical zone',
                tranche_id=tranche_id,
                action=action,
            )
            return ExecutionResult(
                success=False,
                total_ms=int((time.time() - t0) * 1000),
                reason='MARGIN_CRITICAL',
                client_order_id=coid,
            )

        # Step 4: Mark position as being closed (180s TTL)
        if position is not None:
            position['_being_closed']    = True
            position['_being_closed_at'] = datetime.now(timezone.utc).isoformat()

        # Step 5: Fetch quotes and place initial order
        quotes = await self._fetch_quotes(symbol, rest)
        if not quotes:
            _log_activity(
                'order_failed',
                f"Cannot fetch quotes for {symbol}",
                session_id=session_id, level='error',
            )
            self._emit_order_event(
                'emit_order_failed',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=1,
                client_order_id=coid,
                reason_code='NO_QUOTES',
                reason='Unable to fetch executable quotes',
                tranche_id=tranche_id,
                action=action,
            )
            return ExecutionResult(
                success=False, reason='NO_QUOTES',
                total_ms=int((time.time() - t0) * 1000),
                client_order_id=coid,
            )

        if use_bid_entry and side.lower() == 'buy':
            price = float(quotes.get('best_bid') or 0) or self._calc_mid(quotes)
        else:
            price = self._calc_mid(quotes)

        if price <= 0:
            self._emit_order_event(
                'emit_order_failed',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=1,
                client_order_id=coid,
                reason_code='INVALID_PRICE',
                reason='Calculated limit price is not tradable',
                tranche_id=tranche_id,
                action=action,
            )
            return ExecutionResult(
                success=False, reason='INVALID_PRICE',
                total_ms=int((time.time() - t0) * 1000),
                client_order_id=coid,
            )

        order_result = await self._place_limit_order(
            symbol, side, size, price, reduce_only, rest, client_order_id=coid,
        )
        if not order_result or not order_result.get('id'):
            err = (
                str(order_result.get('error', 'placement failed'))
                if order_result
                else 'placement failed'
            )
            self._emit_order_event(
                'emit_order_failed',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=1,
                client_order_id=coid,
                reason_code='PLACE_FAILED',
                reason=err,
                tranche_id=tranche_id,
                action=action,
            )
            return ExecutionResult(
                success=False, reason=f'PLACE_FAILED:{err}',
                total_ms=int((time.time() - t0) * 1000),
                client_order_id=coid,
            )

        order_id   = str(order_result['id'])
        product_id = order_result.get('product_id')

        self._emit_order_event(
            'emit_order_ack',
            session_id=session_id or '',
            symbol=symbol,
            side=side,
            requested_size=size,
            mode=mode,
            attempt=1,
            client_order_id=coid,
            order_id=order_id,
            tranche_id=tranche_id,
            action=action,
            price=price,
        )

        log.info(f"[MMMX] Order {order_id} placed @ ${price:.2f}")
        _log_activity(
            'order_placed',
            f"{side.upper()} {size} {symbol} @ ${price:.2f}",
            session_id=session_id, level='info',
            data={'order_id': order_id, 'price': price},
        )

        # Step 6: Reprice loop
        attempts     = 0
        go_emergency = False

        while attempts < _max:
            attempts += 1

            filled, fill_data = await self._wait_for_fill(
                order_id, product_id, FILL_TIMEOUT_SECS, rest,
            )

            if filled:
                # Brief delay for exchange to finalize fill data
                await asyncio.sleep(0.5)
                final = await self._get_order_status(order_id, product_id, rest) or fill_data

                raw_fill = final.get('average_fill_price')
                raw_unf  = final.get('unfilled_size')

                try:
                    fill_price = float(raw_fill) if raw_fill else 0.0
                except (ValueError, TypeError):
                    fill_price = 0.0

                if fill_price <= 0:
                    log.error(
                        f"[MMMX] Order {order_id} filled but avg_fill_price={raw_fill!r}"
                    )
                    self._emit_order_event(
                        'emit_order_failed',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempts,
                        client_order_id=coid,
                        reason_code='INVALID_FILL_PRICE',
                        reason=f'Exchange returned invalid fill price: {raw_fill!r}',
                        tranche_id=tranche_id,
                        action=action,
                        order_id=order_id,
                    )
                    return ExecutionResult(
                        success=False, reason='INVALID_FILL_PRICE',
                        order_id=order_id, client_order_id=coid,
                        attempts=attempts,
                        total_ms=int((time.time() - t0) * 1000),
                    )

                filled_size = size
                if raw_unf is not None:
                    try:
                        filled_size = size - int(raw_unf)
                    except (ValueError, TypeError):
                        pass
                filled_size = max(filled_size, 0)
                residual_size = max(size - filled_size, 0)

                fees = fill_price * filled_size * LOT_SIZE_BTC * FEE_RATE_MAKER

                if residual_size > 0:
                    self._emit_order_event(
                        'emit_order_partial',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempts,
                        client_order_id=coid,
                        order_id=order_id,
                        filled_size=filled_size,
                        residual_size=residual_size,
                        tranche_id=tranche_id,
                        action=action,
                        avg_price=fill_price,
                    )

                self._emit_order_event(
                    'emit_order_filled',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempts,
                    client_order_id=coid,
                    order_id=order_id,
                    filled_size=filled_size,
                    residual_size=residual_size,
                    avg_price=fill_price,
                    tranche_id=tranche_id,
                    action=action,
                    fees_paid=round(fees, 6),
                )

                # Clear _being_closed
                if position is not None:
                    position.pop('_being_closed', None)
                    position.pop('_being_closed_at', None)

                action_tag = 'BUY' if side.lower() == 'buy' else 'SELL'
                self._audit_trade(
                    session_id, action_tag, symbol, filled_size,
                    fill_price, tranche_id, order_id, coid, round(fees, 6),
                )

                total_ms = int((time.time() - t0) * 1000)
                log.info(
                    f"[MMMX] FILLED {order_id} @ ${fill_price:.2f} "
                    f"({filled_size}/{size} lots) in {total_ms}ms"
                )
                _log_activity(
                    'order_filled',
                    f"{side.upper()} {symbol} FILLED @ ${fill_price:.2f}",
                    session_id=session_id, level='info',
                    data={'order_id': order_id, 'fill_price': fill_price,
                          'filled_size': filled_size},
                )
                return ExecutionResult(
                    success=True,
                    filled_size=filled_size,
                    avg_price=fill_price,
                    attempts=attempts,
                    total_ms=total_ms,
                    order_id=order_id,
                    client_order_id=coid,
                    fees_paid=round(fees, 6),
                )

            # Order dead (cancelled/rejected)
            if fill_data and fill_data.get('_dead'):
                partial_filled = 0
                try:
                    raw_unfilled = fill_data.get('unfilled_size')
                    if raw_unfilled is not None:
                        partial_filled = max(size - int(raw_unfilled), 0)
                except (ValueError, TypeError):
                    partial_filled = 0

                if partial_filled > 0:
                    self._emit_order_event(
                        'emit_order_partial',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempts,
                        client_order_id=coid,
                        order_id=order_id,
                        filled_size=partial_filled,
                        residual_size=max(size - partial_filled, 0),
                        tranche_id=tranche_id,
                        action=action,
                        avg_price=float(fill_data.get('average_fill_price') or 0.0),
                    )

                self._emit_order_event(
                    'emit_order_failed',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempts,
                    client_order_id=coid,
                    reason_code='ORDER_DEAD',
                    reason='Order became cancelled/rejected before full fill',
                    tranche_id=tranche_id,
                    action=action,
                    order_id=order_id,
                    filled_size=partial_filled,
                    residual_size=max(size - partial_filled, 0),
                )
                return ExecutionResult(
                    success=False, reason='ORDER_DEAD',
                    order_id=order_id, client_order_id=coid,
                    attempts=attempts,
                    total_ms=int((time.time() - t0) * 1000),
                )

            # Mid-loop margin check
            midverdict = await self._midloop_margin_check()
            if midverdict == MarginVerdict.MARGIN_CRITICAL:
                await self._cancel_order(order_id, product_id, rest)
                log.warning(f"[MMMX] Aborting {order_id}: MARGIN_CRITICAL mid-loop")
                self._emit_order_event(
                    'emit_order_failed',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempts,
                    client_order_id=coid,
                    reason_code='MARGIN_CRITICAL',
                    reason='Mid-loop margin check entered critical zone',
                    tranche_id=tranche_id,
                    action=action,
                    order_id=order_id,
                )
                return ExecutionResult(
                    success=False, reason='MARGIN_CRITICAL',
                    order_id=order_id, client_order_id=coid,
                    attempts=attempts,
                    total_ms=int((time.time() - t0) * 1000),
                )
            if midverdict == MarginVerdict.MARGIN_BLOCKED:
                # Fall through to market
                await self._cancel_order(order_id, product_id, rest)
                self._emit_order_event(
                    'emit_order_retry',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempts,
                    client_order_id=coid,
                    reason_code='MARGIN_FALLBACK',
                    reason='Mid-loop margin check triggered emergency fallback',
                    tranche_id=tranche_id,
                    action=action,
                    order_id=order_id,
                )
                go_emergency = True
                break

            # Reprice: cancel + replace with fresh quotes
            log.info(
                f"[MMMX] Order {order_id} not filled after {FILL_TIMEOUT_SECS}s "
                f"— repricing ({attempts}/{_max})"
            )
            _log_activity(
                'order_repricing',
                f"Repricing {order_id} attempt {attempts}/{_max}",
                session_id=session_id, level='warning',
                data={'attempt': attempts, 'order_id': order_id},
            )
            self._emit_order_event(
                'emit_order_retry',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=attempts,
                client_order_id=coid,
                reason_code='TIMEOUT_REPRICE',
                reason=f'No fill after {FILL_TIMEOUT_SECS}s; repricing order',
                tranche_id=tranche_id,
                action=action,
                order_id=order_id,
            )

            new_quotes = await self._fetch_quotes(symbol, rest)
            if not new_quotes:
                continue

            new_price = self._calc_mid(new_quotes)

            # Second half of attempts: aggressive pricing
            if attempts >= _aggressive_from:
                if side.lower() == 'sell':
                    bid = float(new_quotes.get('best_bid') or 0)
                    if bid > 0:
                        new_price = bid
                else:
                    ask = float(new_quotes.get('best_ask') or 0)
                    if ask > 0:
                        new_price = ask

            if new_price <= 0:
                continue

            await self._cancel_order(order_id, product_id, rest)
            new_order = await self._place_limit_order(
                symbol, side, size, new_price, reduce_only, rest,
                client_order_id=coid,
            )
            if new_order and new_order.get('id'):
                order_id   = str(new_order['id'])
                product_id = new_order.get('product_id')
                price      = new_price
                self._emit_order_event(
                    'emit_order_ack',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=min(attempts + 1, _max),
                    client_order_id=coid,
                    order_id=order_id,
                    tranche_id=tranche_id,
                    action=action,
                    price=price,
                    extra={'repriced': True},
                )

        # Step 7: Market fallback (exhausted reprices, or margin fallback triggered)
        log.warning(f"[MMMX] Falling back to emergency_execute for {symbol}")
        _log_activity(
            'order_repricing',
            f"Falling back to emergency IOC for {symbol} after {attempts} attempts",
            session_id=session_id, level='warning',
            data={'symbol': symbol, 'attempts': attempts},
        )
        self._emit_order_event(
            'emit_order_retry',
            session_id=session_id or '',
            symbol=symbol,
            side=side,
            requested_size=size,
            mode=mode,
            attempt=max(attempts, 1),
            client_order_id=coid,
            reason_code='FALLBACK_EMERGENCY',
            reason='Limit path exhausted; escalating to emergency IOC path',
            tranche_id=tranche_id,
            action=action,
            order_id=order_id,
            extra={'go_emergency': bool(go_emergency or attempts >= _max)},
        )

        emerg = await self.emergency_execute(
            symbol=symbol,
            side=side,
            size=size,
            session_id=session_id,
            tranche_id=tranche_id,
            action=action,
            position=position,
            origin_client_order_id=coid,
        )
        emerg.attempts += attempts
        return emerg

    # ── emergency_execute ──────────────────────────────────────────────────────

    async def emergency_execute(
        self,
        symbol: str,
        side: str,
        size: int,
        session_id: str = None,
        tranche_id: Any = None,
        action: str = 'EMERGENCY',
        position: Dict = None,
        max_slippage_pct: float = 5.0,
        origin_client_order_id: str = None,
    ) -> ExecutionResult:
        """
        IOC order execution — no reprice loop, immediate fill or cancel.

        Used for:
          - Margin-breach fallback from smart_execute
          - Direct emergency calls (hard stop, flash crash)

        Args:
            symbol:           Options symbol
            side:             'buy' | 'sell'
            size:             Lots
            session_id:       For audit logging
            tranche_id:       For audit trail
            action:           Short label for audit log
            position:         Optional position dict (cleared on fill)
            max_slippage_pct: Maximum slippage from best bid/ask (%)

        Returns:
            ExecutionResult
        """
        t0   = time.time()
        mode = 'emergency'
        coid = compute_client_order_id(
            session_id or '', tranche_id or '', side, f'{action}_EMRG'
        )

        log.critical(
            f"[MMMX] EMERGENCY EXECUTE: {side.upper()} {size} {symbol}"
        )
        _log_activity(
            'emergency_order',
            f"EMERGENCY {side.upper()} {size} {symbol}",
            session_id=session_id, level='error',
            data={'symbol': symbol, 'side': side, 'size': size},
        )

        self._emit_order_event(
            'emit_order_intent',
            session_id=session_id or '',
            symbol=symbol,
            side=side,
            requested_size=size,
            mode=mode,
            attempt=1,
            client_order_id=coid,
            tranche_id=tranche_id,
            action=action,
            extra={
                'max_slippage_pct': float(max_slippage_pct),
                'origin_client_order_id': origin_client_order_id or '',
            },
        )

        rest = self._create_rest_client()
        terminal_failure_emitted = False

        for attempt in range(1, EMERGENCY_MAX_ATTEMPTS + 1):
            try:
                quotes = await self._fetch_quotes(symbol, rest)
                if not quotes or (
                    quotes.get('best_bid', 0) <= 0 or quotes.get('best_ask', 0) <= 0
                ):
                    log.error(
                        f"[MMMX] Emergency attempt {attempt}: no valid quotes for {symbol}"
                    )
                    if attempt < EMERGENCY_MAX_ATTEMPTS:
                        self._emit_order_event(
                            'emit_order_retry',
                            session_id=session_id or '',
                            symbol=symbol,
                            side=side,
                            requested_size=size,
                            mode=mode,
                            attempt=attempt,
                            client_order_id=coid,
                            reason_code='NO_QUOTES_RETRY',
                            reason='Emergency path has no valid quote; retrying',
                            tranche_id=tranche_id,
                            action=action,
                            extra={'origin_client_order_id': origin_client_order_id or ''},
                        )
                        await asyncio.sleep(1)
                        continue
                    self._emit_order_event(
                        'emit_order_failed',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempt,
                        client_order_id=coid,
                        reason_code='NO_QUOTES_EMERGENCY',
                        reason='Emergency path exhausted with no valid quotes',
                        tranche_id=tranche_id,
                        action=action,
                        extra={'origin_client_order_id': origin_client_order_id or ''},
                    )
                    return ExecutionResult(
                        success=False, reason='NO_QUOTES_EMERGENCY',
                        client_order_id=coid, attempts=attempt,
                        total_ms=int((time.time() - t0) * 1000),
                    )

                bid  = float(quotes.get('best_bid', 0))
                ask  = float(quotes.get('best_ask', 0))
                tick = float(quotes.get('tick_size', 0.01))

                if side.lower() == 'buy':
                    slippage = ask * (max_slippage_pct / 100.0)
                    aggressive_price = ask + slippage
                else:
                    slippage = bid * (max_slippage_pct / 100.0)
                    aggressive_price = max(bid - slippage, tick)

                if tick > 0:
                    aggressive_price = round(aggressive_price / tick) * tick
                aggressive_price = round(aggressive_price, 2)

                log.info(
                    f"[MMMX] Emergency attempt {attempt}: {side.upper()} {size} "
                    f"{symbol} @ ${aggressive_price:.2f} (IOC, {max_slippage_pct}% slip)"
                )

                response = await rest.place_order_by_symbol(
                    symbol=symbol,
                    side=side,
                    price=aggressive_price,
                    size=int(size),
                    order_type='limit_order',
                    time_in_force='ioc',
                    post_only=False,
                    reduce_only=True,
                    client_order_id=coid,
                )
                result   = response.get('result', response)
                order_id = str(result.get('id', ''))

                if not order_id:
                    log.error(f"[MMMX] Emergency placement failed: {response}")
                    if attempt < EMERGENCY_MAX_ATTEMPTS:
                        self._emit_order_event(
                            'emit_order_retry',
                            session_id=session_id or '',
                            symbol=symbol,
                            side=side,
                            requested_size=size,
                            mode=mode,
                            attempt=attempt,
                            client_order_id=coid,
                            reason_code='EMERGENCY_PLACE_RETRY',
                            reason='Emergency placement failed; widening slippage and retrying',
                            tranche_id=tranche_id,
                            action=action,
                            extra={
                                'max_slippage_pct': float(max_slippage_pct),
                                'origin_client_order_id': origin_client_order_id or '',
                            },
                        )
                        await asyncio.sleep(1)
                        max_slippage_pct = min(max_slippage_pct * 2, 20.0)
                        continue
                    self._emit_order_event(
                        'emit_order_failed',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempt,
                        client_order_id=coid,
                        reason_code='EMERGENCY_PLACE_FAILED',
                        reason='Emergency placement failed after max attempts',
                        tranche_id=tranche_id,
                        action=action,
                        extra={'origin_client_order_id': origin_client_order_id or ''},
                    )
                    return ExecutionResult(
                        success=False, reason='EMERGENCY_PLACE_FAILED',
                        client_order_id=coid, attempts=attempt,
                        total_ms=int((time.time() - t0) * 1000),
                    )

                self._emit_order_event(
                    'emit_order_ack',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempt,
                    client_order_id=coid,
                    order_id=order_id,
                    tranche_id=tranche_id,
                    action=action,
                    price=aggressive_price,
                    extra={'origin_client_order_id': origin_client_order_id or ''},
                )

                await asyncio.sleep(EMERGENCY_FILL_WAIT)

                product_id = result.get('product_id')
                order_data = (
                    await self._get_order_status(order_id, product_id, rest) or result
                )
                state = str(order_data.get('state', '')).lower()

                if state in ORDER_STATES_FILLED:
                    raw_fill = order_data.get('average_fill_price')
                    try:
                        fill_price = float(raw_fill) if raw_fill else aggressive_price
                    except (ValueError, TypeError):
                        fill_price = aggressive_price

                    raw_unf     = order_data.get('unfilled_size')
                    filled_size = size
                    if raw_unf is not None:
                        try:
                            filled_size = size - int(raw_unf)
                        except (ValueError, TypeError):
                            pass
                    filled_size = max(filled_size, 0)
                    residual_size = max(size - filled_size, 0)

                    fees = fill_price * filled_size * LOT_SIZE_BTC * FEE_RATE_TAKER

                    if residual_size > 0:
                        self._emit_order_event(
                            'emit_order_partial',
                            session_id=session_id or '',
                            symbol=symbol,
                            side=side,
                            requested_size=size,
                            mode=mode,
                            attempt=attempt,
                            client_order_id=coid,
                            order_id=order_id,
                            filled_size=filled_size,
                            residual_size=residual_size,
                            tranche_id=tranche_id,
                            action=action,
                            avg_price=fill_price,
                            extra={'origin_client_order_id': origin_client_order_id or ''},
                        )

                    self._emit_order_event(
                        'emit_order_filled',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempt,
                        client_order_id=coid,
                        order_id=order_id,
                        filled_size=filled_size,
                        residual_size=residual_size,
                        avg_price=fill_price,
                        tranche_id=tranche_id,
                        action=action,
                        fees_paid=round(fees, 6),
                        extra={'origin_client_order_id': origin_client_order_id or ''},
                    )

                    if position is not None:
                        position.pop('_being_closed', None)
                        position.pop('_being_closed_at', None)

                    action_tag = 'BUY' if side.lower() == 'buy' else 'SELL'
                    self._audit_trade(
                        session_id, action_tag, symbol, filled_size,
                        fill_price, tranche_id, order_id, coid, round(fees, 6),
                    )

                    total_ms = int((time.time() - t0) * 1000)
                    log.info(
                        f"[MMMX] Emergency FILLED {order_id} @ ${fill_price:.2f} "
                        f"({filled_size}/{size} lots) in {total_ms}ms"
                    )
                    _log_activity(
                        'order_filled',
                        f"EMERGENCY FILLED {symbol} @ ${fill_price:.2f}",
                        session_id=session_id, level='error',
                        data={'order_id': order_id, 'fill_price': fill_price,
                              'filled_size': filled_size},
                    )
                    return ExecutionResult(
                        success=True,
                        filled_size=filled_size,
                        avg_price=fill_price,
                        attempts=attempt,
                        total_ms=total_ms,
                        order_id=order_id,
                        client_order_id=coid,
                        fees_paid=round(fees, 6),
                    )

                # IOC cancelled or unknown state
                log.warning(
                    f"[MMMX] Emergency IOC state={state!r} ({attempt}/{EMERGENCY_MAX_ATTEMPTS})"
                )
                if attempt < EMERGENCY_MAX_ATTEMPTS:
                    self._emit_order_event(
                        'emit_order_retry',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempt,
                        client_order_id=coid,
                        reason_code='IOC_NOT_FILLED_RETRY',
                        reason=f'IOC returned state={state!r}; retrying with wider slippage',
                        tranche_id=tranche_id,
                        action=action,
                        order_id=order_id,
                        extra={
                            'max_slippage_pct': float(max_slippage_pct),
                            'origin_client_order_id': origin_client_order_id or '',
                        },
                    )
                    max_slippage_pct = min(max_slippage_pct * 2, 20.0)
                    continue

                self._emit_order_event(
                    'emit_order_failed',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempt,
                    client_order_id=coid,
                    reason_code='IOC_NOT_FILLED',
                    reason=f'IOC terminal state={state!r} after max attempts',
                    tranche_id=tranche_id,
                    action=action,
                    order_id=order_id,
                    extra={'origin_client_order_id': origin_client_order_id or ''},
                )
                terminal_failure_emitted = True

            except Exception as exc:
                log.exception(f"[MMMX] Emergency attempt {attempt} crashed: {exc}")
                if attempt < EMERGENCY_MAX_ATTEMPTS:
                    self._emit_order_event(
                        'emit_order_retry',
                        session_id=session_id or '',
                        symbol=symbol,
                        side=side,
                        requested_size=size,
                        mode=mode,
                        attempt=attempt,
                        client_order_id=coid,
                        reason_code='EMERGENCY_EXCEPTION_RETRY',
                        reason=f'Emergency attempt raised exception: {exc}',
                        tranche_id=tranche_id,
                        action=action,
                        extra={'origin_client_order_id': origin_client_order_id or ''},
                    )
                    await asyncio.sleep(1)
                    continue

                self._emit_order_event(
                    'emit_order_failed',
                    session_id=session_id or '',
                    symbol=symbol,
                    side=side,
                    requested_size=size,
                    mode=mode,
                    attempt=attempt,
                    client_order_id=coid,
                    reason_code='EMERGENCY_EXCEPTION',
                    reason=f'Emergency path failed with exception: {exc}',
                    tranche_id=tranche_id,
                    action=action,
                    extra={'origin_client_order_id': origin_client_order_id or ''},
                )
                terminal_failure_emitted = True

        if not terminal_failure_emitted:
            self._emit_order_event(
                'emit_order_failed',
                session_id=session_id or '',
                symbol=symbol,
                side=side,
                requested_size=size,
                mode=mode,
                attempt=EMERGENCY_MAX_ATTEMPTS,
                client_order_id=coid,
                reason_code='EMERGENCY_NOT_FILLED',
                reason='Emergency path exhausted with no full fill',
                tranche_id=tranche_id,
                action=action,
                extra={'origin_client_order_id': origin_client_order_id or ''},
            )

        return ExecutionResult(
            success=False, reason='EMERGENCY_NOT_FILLED',
            client_order_id=coid, attempts=EMERGENCY_MAX_ATTEMPTS,
            total_ms=int((time.time() - t0) * 1000),
        )


# ── Singleton ──────────────────────────────────────────────────────────────────
_instance: Optional[MMMXExecutor] = None
_init_lock = threading.Lock()


def get_executor() -> MMMXExecutor:
    """Return the process-wide executor singleton."""
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = MMMXExecutor()
    return _instance
