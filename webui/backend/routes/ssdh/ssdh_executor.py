"""
SSDH Executor — Order Placement and Fill Verification

Places and verifies all SSDH orders on Delta Exchange.
The ONLY file that touches the exchange API for order placement.

CRITICAL: This module uses asyncio. The monitor calls it from a real OS thread
(created via eventlet.patcher.original). Never call async functions from Flask
request greenlets — that will cause "Cannot run event loop while another loop
is running."

Key rules:
- Create a FRESH AsyncDeltaClient per asyncio.run() context (httpx binds to loop)
- Use paid_commission for fee extraction (NOT commission — always "0" for fills)
- client_order_id format: ssdh_{session8}_{sides}_{ts8} — max 32 chars

Created: March 21, 2026
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

log = logging.getLogger('ssdh_executor')

# =============================================================================
# Constants
# =============================================================================

FILL_CHECK_INTERVAL  = 3     # Poll every 3s
FILL_TIMEOUT         = 60    # Reprice after 60s without fill
MAX_REPRICE_ATTEMPTS = 4     # 4 × 60s = 4-minute max per leg

ORDER_STATES_FILLED = {'filled', 'closed', 'completed'}
ORDER_STATES_DEAD   = {'cancelled', 'canceled', 'rejected'}

# Aggressive close pricing buffers
SHORT_CLOSE_BUFFER = 1.05   # buy back shorts at ask × 1.05
LONG_CLOSE_BUFFER  = 0.97   # sell back longs at bid × 0.97


# =============================================================================
# Client factory
# =============================================================================

def _create_rest_client():
    """
    Create a FRESH AsyncDeltaClient bound to the CURRENT event loop.
    httpx.AsyncClient binds its transport to the loop where it's first used.
    Must create fresh per asyncio.run() call.
    """
    from bot.api.async_delta_client import AsyncDeltaClient
    from config.loader import get_api_credentials

    creds = get_api_credentials()
    return AsyncDeltaClient(
        api_key=creds.get('api_key', ''),
        api_secret=creds.get('api_secret', ''),
        testnet=creds.get('testnet', False) or False,
    )


# =============================================================================
# client_order_id
# =============================================================================

def _generate_client_order_id(session_id: str, side: str, leg_type: str) -> str:
    """
    Generates: ssdh_{session8}_{side1}{type1}_{ts8}
    Example: ssdh_a1b2c3d4_cs_17109600  (c=CE, s=short)
    Max 32 chars — enforced by assertion.
    side: 'c' (CE) or 'p' (PE)
    leg_type: 's' (short/core) or 'l' (long/hedge)
    """
    sess_tag = ''.join(c for c in (session_id or 'x').replace('ssdh', '').replace('-', ''))[:8]
    ts_tag   = str(int(time.time()))[-8:]
    coid     = f"ssdh_{sess_tag}_{side[0].lower()}{leg_type[0].lower()}_{ts_tag}"[:32]
    assert len(coid) <= 32, f"client_order_id too long: {coid}"
    return coid


# =============================================================================
# Fee extraction
# =============================================================================

def _extract_fees(order_response: dict) -> float:
    """
    Returns actual fee from order response.

    Delta Exchange API quirk:
    - commission: always string "0" for filled orders (reserved amount)
    - paid_commission: actual USDT fee charged (string like "0.04140325")
    Always cast with float(). Use paid_commission, fall back to commission.
    """
    od = order_response or {}
    return float(od.get('paid_commission', 0) or od.get('commission', 0) or 0)


# =============================================================================
# Executor class
# =============================================================================

class SSDHExecutor:

    # =========================================================================
    # Fetch quotes
    # =========================================================================

    async def _fetch_quotes(self, symbol: str, client) -> Optional[dict]:
        """Fetch best_bid, best_ask, tick_size for a symbol."""
        try:
            ticker = await client.get_ticker(symbol)
            if not ticker:
                return None
            best_bid = float(ticker.get('best_bid', 0) or 0)
            best_ask = float(ticker.get('best_ask', 0) or 0)
            if best_bid <= 0 or best_ask <= 0:
                return None
            return {
                'best_bid':  best_bid,
                'best_ask':  best_ask,
                'mid':       (best_bid + best_ask) / 2,
                'tick_size': float(ticker.get('tick_size', 0.01) or 0.01),
                'mark_price':float(ticker.get('mark_price', 0) or 0),
            }
        except Exception as e:
            log.warning("_fetch_quotes %s: %s", symbol, e)
            return None

    def _round_to_tick(self, price: float, tick: float) -> float:
        if tick <= 0:
            return round(price, 2)
        return round(round(price / tick) * tick, 10)

    # =========================================================================
    # Place limit order
    # =========================================================================

    async def _place_limit_order(
        self, symbol: str, side: str, size: int, price: float,
        client, client_order_id: str
    ) -> Optional[dict]:
        try:
            result = await client.place_order(
                symbol=symbol,
                side=side,
                size=size,
                order_type='limit_order',
                price=price,
                client_order_id=client_order_id,
            )
            return result
        except Exception as e:
            log.warning("_place_limit_order %s %s: %s", side, symbol, e)
            return None

    async def _place_market_order(
        self, symbol: str, side: str, size: int, client, client_order_id: str
    ) -> Optional[dict]:
        try:
            result = await client.place_order(
                symbol=symbol,
                side=side,
                size=size,
                order_type='market_order',
                client_order_id=client_order_id,
            )
            return result
        except Exception as e:
            log.warning("_place_market_order %s %s: %s", side, symbol, e)
            return None

    # =========================================================================
    # Poll for fill
    # =========================================================================

    async def _poll_for_fill(self, order_id: str, client) -> Optional[dict]:
        """
        Polls order status every FILL_CHECK_INTERVAL seconds.
        Returns order dict if filled, None if dead/unknown.
        Returns False on timeout (caller should reprice).
        """
        deadline = time.monotonic() + FILL_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(FILL_CHECK_INTERVAL)
            try:
                order = await client.get_order(order_id)
                if not order:
                    continue
                state = str(order.get('state', '') or order.get('status', '')).lower()
                if state in ORDER_STATES_FILLED:
                    return order
                if state in ORDER_STATES_DEAD:
                    return None
            except Exception as e:
                log.warning("_poll_for_fill %s: %s", order_id, e)
        return False   # timeout sentinel

    # =========================================================================
    # Core sell / buy with reprice loop
    # =========================================================================

    async def _execute_with_reprice(
        self, symbol: str, order_side: str, lots: int,
        start_price: float, client_order_id: str,
        session_id: str, params: dict, client,
    ) -> dict:
        """
        Place limit order. Poll for fill. On timeout: cancel + reprice. Repeat.
        Returns executor result dict.
        """
        from .ssdh_activity import log_activity

        max_attempts = int(params.get('max_retries_on_fill', MAX_REPRICE_ATTEMPTS))
        price = start_price
        last_order_id = None

        for attempt in range(1, max_attempts + 1):
            log_activity('order_placing',
                f"{order_side.upper()} {lots}× {symbol} @ {price:.2f} (attempt {attempt})",
                session_id=session_id, severity='progress')

            order = await self._place_limit_order(symbol, order_side, lots, price, client, client_order_id)
            if not order or not order.get('id'):
                log_activity('order_failed', f"{symbol}: placement failed attempt {attempt}",
                    session_id=session_id, severity='error')
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                continue

            last_order_id = str(order['id'])
            log_activity('order_placed', f"{symbol} order {last_order_id} @ {price:.2f}",
                session_id=session_id, severity='info')

            fill_result = await self._poll_for_fill(last_order_id, client)

            if fill_result is None:   # dead order
                log_activity('order_cancelled', f"{symbol}: order {last_order_id} dead/rejected",
                    session_id=session_id, severity='warning')
                continue

            if fill_result is not False:  # filled
                fill_price = float(
                    fill_result.get('average_fill_price') or
                    fill_result.get('fill_price') or price
                )
                fees = _extract_fees(fill_result)
                log_activity('order_filled',
                    f"{symbol} filled @ {fill_price:.2f}, fees={fees:.6f}",
                    session_id=session_id, severity='success')
                return {
                    'success':          True,
                    'order_id':         last_order_id,
                    'client_order_id':  client_order_id,
                    'fill_price':       fill_price,
                    'lots':             lots,
                    'fees':             fees,
                    'fill_confirmed_at':datetime.now(timezone.utc).isoformat(),
                }

            # Timeout — cancel and reprice
            log_activity('order_repricing',
                f"{symbol}: no fill after {FILL_TIMEOUT}s, repricing (attempt {attempt})",
                session_id=session_id, severity='warning')
            try:
                await client.cancel_order(last_order_id)
            except Exception:
                pass

            # Fetch fresh quote for next attempt
            quotes = await self._fetch_quotes(symbol, client)
            if quotes:
                tick = quotes['tick_size']
                if order_side == 'sell':
                    price = self._round_to_tick(quotes['best_bid'], tick)
                else:
                    price = self._round_to_tick(quotes['best_ask'], tick)

        return {
            'success': False,
            'error':   f"{symbol}: all {max_attempts} attempts exhausted",
            'order_id': last_order_id,
            'client_order_id': client_order_id,
        }

    # =========================================================================
    # sell_option
    # =========================================================================

    async def sell_option(
        self,
        session_id: str,
        symbol: str,
        strike: float,
        lots: int,
        client_order_id: str,
        session_params: dict,
    ) -> dict:
        """
        Places SELL limit order at bid price (maker).
        Polls for fill, reprices on timeout.
        Returns executor result dict.
        """
        client = _create_rest_client()
        try:
            quotes = await self._fetch_quotes(symbol, client)
            if not quotes:
                return {'success': False, 'error': f'{symbol}: no quotes for sell', 'client_order_id': client_order_id}
            tick  = quotes['tick_size']
            price = self._round_to_tick(quotes['best_bid'], tick)
            if price <= 0:
                price = self._round_to_tick(quotes['mid'], tick)
            return await self._execute_with_reprice(
                symbol, 'sell', lots, price, client_order_id, session_id, session_params, client
            )
        finally:
            try:
                await client.close()
            except Exception:
                pass

    # =========================================================================
    # buy_option
    # =========================================================================

    async def buy_option(
        self,
        session_id: str,
        symbol: str,
        strike: float,
        lots: int,
        client_order_id: str,
        session_params: dict,
    ) -> dict:
        """
        Places BUY limit order at ask price (taker — for hedge legs).
        Polls for fill, reprices on timeout.
        """
        client = _create_rest_client()
        try:
            quotes = await self._fetch_quotes(symbol, client)
            if not quotes:
                return {'success': False, 'error': f'{symbol}: no quotes for buy', 'client_order_id': client_order_id}
            tick  = quotes['tick_size']
            price = self._round_to_tick(quotes['best_ask'], tick)
            if price <= 0:
                price = self._round_to_tick(quotes['mid'], tick)
            return await self._execute_with_reprice(
                symbol, 'buy', lots, price, client_order_id, session_id, session_params, client
            )
        finally:
            try:
                await client.close()
            except Exception:
                pass

    # =========================================================================
    # close_position
    # =========================================================================

    async def close_position(
        self,
        position: dict,
        session_id: str,
        reason: str,
        symbol: str,
        aggressive: bool = True,
        session_params: dict = None,
    ) -> dict:
        """
        Closes a position by placing the opposite order.
        - short position → buy back at ask × SHORT_CLOSE_BUFFER (1.05)
        - long position  → sell back at bid × LONG_CLOSE_BUFFER (0.97)

        If aggressive=True and still not filled after one timeout → escalate to emergency.
        """
        from .ssdh_state import DIR_SHORT

        params = session_params or {}
        direction = position['direction']
        lots      = position['lots']

        close_side = 'buy' if direction == DIR_SHORT else 'sell'

        client = _create_rest_client()
        try:
            quotes = await self._fetch_quotes(symbol, client)
            if not quotes:
                if aggressive:
                    return await self._emergency_execute_internal(position, session_id, symbol, client)
                return {'success': False, 'error': f'{symbol}: no quotes for close'}

            tick = quotes['tick_size']
            if direction == DIR_SHORT:
                price = self._round_to_tick(quotes['best_ask'] * SHORT_CLOSE_BUFFER, tick)
            else:
                price = self._round_to_tick(quotes['best_bid'] * LONG_CLOSE_BUFFER, tick)
            price = max(price, quotes['tick_size'])

            coid = _generate_client_order_id(session_id, position['side'], 'close')
            result = await self._execute_with_reprice(
                symbol, close_side, lots, price, coid, session_id, params, client
            )

            if not result['success'] and aggressive:
                log.warning("close_position: escalating %s to emergency", position['pos_id'])
                return await self._emergency_execute_internal(position, session_id, symbol, client)

            return result
        finally:
            try:
                await client.close()
            except Exception:
                pass

    # =========================================================================
    # emergency_execute
    # =========================================================================

    async def emergency_execute(self, position: dict, session_id: str, symbol: str) -> dict:
        """
        Market order. No price limit. No repricing.
        Used for: kill switch, failed escalated close, structure break.
        Retries once on failure.
        """
        client = _create_rest_client()
        try:
            return await self._emergency_execute_internal(position, session_id, symbol, client)
        finally:
            try:
                await client.close()
            except Exception:
                pass

    async def _emergency_execute_internal(
        self, position: dict, session_id: str, symbol: str, client
    ) -> dict:
        from .ssdh_state import DIR_SHORT
        from .ssdh_activity import log_activity

        direction  = position['direction']
        lots       = position['lots']
        close_side = 'buy' if direction == DIR_SHORT else 'sell'
        coid       = _generate_client_order_id(session_id, position['side'], 'emg')

        for attempt in range(1, 3):
            log_activity('order_placing',
                f"EMERGENCY {close_side.upper()} {lots}× {symbol} (attempt {attempt})",
                session_id=session_id, severity='error')
            order = await self._place_market_order(symbol, close_side, lots, client, coid)
            if order and order.get('id'):
                order_id = str(order['id'])
                # Brief wait for market fill confirmation
                await asyncio.sleep(5)
                try:
                    filled = await client.get_order(order_id)
                except Exception:
                    filled = order

                fill_price = float(
                    (filled or order).get('average_fill_price') or
                    (filled or order).get('fill_price') or 0
                )
                fees = _extract_fees(filled or order)
                return {
                    'success':          True,
                    'order_id':         order_id,
                    'client_order_id':  coid,
                    'fill_price':       fill_price,
                    'lots':             lots,
                    'fees':             fees,
                    'fill_confirmed_at':datetime.now(timezone.utc).isoformat(),
                }
            await asyncio.sleep(2)

        return {'success': False, 'error': f'{symbol}: emergency execute failed after 2 attempts'}
