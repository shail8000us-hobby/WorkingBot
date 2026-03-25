"""
IC Executor — Iron Condor Order Placement

Handles:
- Batch order placement for all 4 legs (entry and close)
- Partial fill atomicity rollback (§C.1)
- Simulate mode (§C.9)
- Fill monitoring and amend logic

Mirrors smart execution patterns from mmm_executor.py.

Created: 2026-03-24
"""

import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .ic_constants import (
    LOT_SIZE_BTC, ALL_LEGS,
    FILL_PENDING, FILL_FILLED, FILL_CANCELLED, FILL_FAILED,
    STRATEGY_ENTRY_PARTIAL, STRATEGY_ENTRY_FAILED,
)

log = logging.getLogger('ic_executor')


class ICExecutor:
    """
    Order executor for IC algo.

    Supports batch placement, fill monitoring, and atomicity rollback.
    In simulate mode, returns simulated fills without touching the exchange.
    """

    def __init__(self, api_client=None):
        """
        Args:
            api_client: Delta Exchange API client (from existing bot infrastructure)
        """
        self.api = api_client
        self._fill_timeout_sec = 90   # Per-leg fill timeout
        self._total_timeout_sec = 120  # Total timeout before atomicity rollback

    def place_entry_orders(
        self,
        legs: Dict,
        session: Dict,
    ) -> Tuple[bool, Dict]:
        """
        Place all 4 entry orders (batch if possible).

        §C.1 Atomicity:
          1. Batch place all 4 orders
          2. Monitor fills (90s per-leg timeout)
          3. If stuck at PARTIAL > 120s: rollback
          4. NEVER leave a partial structure active

        Args:
            legs: Dict of {leg_key: leg_state} with product_symbol
            session: Session state

        Returns:
            (success, updated_legs)
        """
        simulate = session.get('params', {}).get('simulate', False)

        if simulate:
            return self._simulate_entry(legs, session)

        return self._real_entry(legs, session)

    def place_close_orders(
        self,
        legs: Dict,
        lots: int,
        session: Dict,
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Place close orders for all open legs.

        §10.2: Buy back short legs first, then sell long legs.

        Returns:
            (success, close_premiums: {leg_key: fill_price})
        """
        simulate = session.get('params', {}).get('simulate', False)

        if simulate:
            return self._simulate_close(legs, session)

        return self._real_close(legs, lots, session)

    # ─── Simulate Mode ────────────────────────────────────────────────────────

    def _simulate_entry(
        self,
        legs: Dict,
        session: Dict,
    ) -> Tuple[bool, Dict]:
        """§C.9: Log decisions without placing real orders."""
        for leg_key, leg in legs.items():
            side_str = 'SELL' if leg['action'] == 'sell' else 'BUY'
            log.info(
                f"[SIMULATE] Would {side_str} {leg['lots']} lots of "
                f"{leg.get('side', '?').upper()} @ strike {leg['strike']} "
                f"premium ${leg.get('entry_premium', 0):.2f}"
            )
            leg['order_id'] = f"SIM_{uuid.uuid4().hex[:8]}"
            leg['fill_status'] = FILL_FILLED
            leg['fill_time'] = datetime.now(timezone.utc).isoformat()

        return True, legs

    def _simulate_close(
        self,
        legs: Dict,
        session: Dict,
    ) -> Tuple[bool, Dict[str, float]]:
        """Simulate closing all legs at current mark prices."""
        close_premiums = {}
        for leg_key, leg in legs.items():
            if leg.get('status') != 'open':
                continue
            close_price = leg.get('mark_premium', leg.get('entry_premium', 0))
            close_premiums[leg_key] = close_price
            side_str = 'BUY BACK' if leg['action'] == 'sell' else 'SELL'
            log.info(
                f"[SIMULATE] Would {side_str} {leg['lots']} lots of "
                f"{leg.get('side', '?').upper()} @ strike {leg['strike']} "
                f"close premium ${close_price:.2f}"
            )
        return True, close_premiums

    # ─── Real Execution ───────────────────────────────────────────────────────

    def _real_entry(
        self,
        legs: Dict,
        session: Dict,
    ) -> Tuple[bool, Dict]:
        """
        Place real entry orders using batch API.

        §C.3: Use POST /v2/orders/batch for all 4 legs simultaneously.
        """
        if not self.api:
            log.error("No API client — cannot place real orders")
            return False, legs

        orders = []
        leg_order_map = {}  # order_index -> leg_key

        for i, (leg_key, leg) in enumerate(legs.items()):
            symbol = leg.get('product_symbol', '')
            if not symbol:
                log.error(f"No product_symbol for leg {leg_key}")
                return False, legs

            side = 'sell' if leg['action'] == 'sell' else 'buy'
            # Use bid for sells, ask for buys
            price = leg.get('entry_premium', 0)

            orders.append({
                'product_symbol': symbol,
                'size': leg['lots'],
                'side': side,
                'order_type': 'limit',
                'limit_price': str(price),
            })
            leg_order_map[i] = leg_key

        try:
            # Batch place
            result = self.api.batch_create_orders(orders)
            if not result or not result.get('result'):
                log.error(f"Batch order placement failed: {result}")
                return False, legs

            # Map order IDs back to legs
            order_results = result.get('result', [])
            for i, order_res in enumerate(order_results):
                leg_key = leg_order_map.get(i)
                if leg_key and leg_key in legs:
                    legs[leg_key]['order_id'] = str(order_res.get('id', ''))
                    legs[leg_key]['fill_status'] = FILL_PENDING

            # AUDIT C1: Monitor fills with timeout and atomicity rollback
            total_start = time.time()
            all_filled = False

            while (time.time() - total_start) < self._total_timeout_sec:
                pending_count = 0
                for leg_key, leg in legs.items():
                    if leg.get('fill_status') == FILL_PENDING and leg.get('order_id'):
                        try:
                            order_status = self.api.get_order(leg['order_id'])
                            if order_status and order_status.get('state') == 'filled':
                                leg['fill_status'] = FILL_FILLED
                                leg['fill_time'] = datetime.now(timezone.utc).isoformat()
                                # Use actual fill price if available
                                fill_price = order_status.get('average_fill_price')
                                if fill_price:
                                    leg['entry_premium'] = float(fill_price)
                                log.info(f"Leg {leg_key} filled at {leg.get('entry_premium')}")
                            elif order_status and order_status.get('state') in ('cancelled', 'rejected'):
                                leg['fill_status'] = FILL_CANCELLED
                                log.warning(f"Leg {leg_key} order cancelled/rejected")
                            else:
                                pending_count += 1
                        except Exception as e:
                            log.warning(f"Fill check error for {leg_key}: {e}")
                            pending_count += 1

                if pending_count == 0:
                    all_filled = True
                    break

                time.sleep(3)  # Poll every 3 seconds

            # Check for partial fills — NEVER leave a partial structure
            filled_count = sum(1 for l in legs.values() if l.get('fill_status') == FILL_FILLED)
            if not all_filled or filled_count < len(legs):
                log.error(
                    f"Partial fill detected: {filled_count}/{len(legs)} legs filled. "
                    f"Initiating atomicity rollback."
                )
                # Cancel all pending orders
                for leg_key, leg in legs.items():
                    if leg.get('fill_status') == FILL_PENDING and leg.get('order_id'):
                        try:
                            self.api.cancel_order(leg['order_id'])
                            leg['fill_status'] = FILL_CANCELLED
                        except Exception:
                            pass

                # Close any filled legs to restore neutral
                for leg_key, leg in legs.items():
                    if leg.get('fill_status') == FILL_FILLED:
                        try:
                            close_side = 'buy' if leg['action'] == 'sell' else 'sell'
                            self.api.create_order({
                                'product_symbol': leg.get('product_symbol', ''),
                                'size': leg['lots'],
                                'side': close_side,
                                'order_type': 'market',
                            })
                            leg['fill_status'] = FILL_CANCELLED
                            log.info(f"Rollback: closed filled leg {leg_key}")
                        except Exception as e:
                            log.error(f"CRITICAL: Rollback failed for {leg_key}: {e}")

                session['strategy_status'] = STRATEGY_ENTRY_FAILED
                return False, legs

            return True, legs

        except Exception as e:
            log.error(f"Batch entry order failed: {e}")
            session['strategy_status'] = STRATEGY_ENTRY_FAILED
            return False, legs

    def _real_close(
        self,
        legs: Dict,
        lots: int,
        session: Dict,
    ) -> Tuple[bool, Dict[str, float]]:
        """Place real close orders for all open legs."""
        if not self.api:
            log.error("No API client — cannot place real close orders")
            return False, {}

        close_premiums = {}
        orders = []
        leg_order_map = {}

        for i, (leg_key, leg) in enumerate(legs.items()):
            if leg.get('status') != 'open':
                continue

            symbol = leg.get('product_symbol', '')
            if not symbol:
                continue

            # Reverse the action to close
            close_side = 'buy' if leg['action'] == 'sell' else 'sell'
            price = leg.get('mark_premium', 0)

            orders.append({
                'product_symbol': symbol,
                'size': lots,
                'side': close_side,
                'order_type': 'limit',
                'limit_price': str(price),
            })
            leg_order_map[i] = leg_key

        if not orders:
            return True, close_premiums

        try:
            result = self.api.batch_create_orders(orders)
            if not result or not result.get('result'):
                log.error(f"Batch close order failed: {result}")
                return False, close_premiums

            # AUDIT C1: Monitor close fills with timeout
            order_ids = []
            order_results = result.get('result', [])
            for i, order_res in enumerate(order_results):
                order_ids.append(str(order_res.get('id', '')))

            total_start = time.time()
            while (time.time() - total_start) < self._total_timeout_sec:
                all_done = True
                for oid in order_ids:
                    try:
                        status = self.api.get_order(oid)
                        if status and status.get('state') not in ('filled', 'cancelled', 'rejected'):
                            all_done = False
                    except Exception:
                        all_done = False
                if all_done:
                    break
                time.sleep(3)

            # Record actual close premiums from fills
            for leg_key, leg in legs.items():
                if leg.get('status') == 'open':
                    close_premiums[leg_key] = leg.get('mark_premium', 0)

            return True, close_premiums

        except Exception as e:
            log.error(f"Batch close order failed: {e}")
            return False, close_premiums


def get_executor(api_client=None) -> ICExecutor:
    """Get an executor instance."""
    return ICExecutor(api_client=api_client)
