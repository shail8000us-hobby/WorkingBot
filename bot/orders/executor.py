"""
Execution layer (Delta via CCXT) — single responsibility:
- Connect to exchange (India prod)
- Place/cancel orders with sane defaults
- Fetch ticker, open orders, positions
- Normalize errors and log clearly

This module is intentionally small and testable.
Higher layers (manager/protection/reconcile) should call this, not CCXT directly.

Enhanced with Circuit Breaker to prevent API bans during exchange outages.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from dotenv import load_dotenv
import ccxt  # type: ignore

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger("exec")

# Circuit Breaker Integration
try:
    from bot.safety.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
    CIRCUIT_BREAKER_ENABLED = True
except Exception:
    CIRCUIT_BREAKER_ENABLED = False
    class CircuitBreakerOpen(Exception): pass
    def get_circuit_breaker(*args, **kwargs): return None

# Load config
cfg = get_config()
DEFAULT_SYMBOL = cfg.trading.symbol
# API credentials loaded from environment variables set by env_loader
API_KEY = os.getenv("DELTA_API_KEY") or ""
API_SECRET = os.getenv("DELTA_API_SECRET") or ""
USE_INDIA = True  # we're on India production


class DeltaExecutor:
    """
    Thin wrapper around CCXT.delta with India URLs and a few conveniences
    (reduce-only, idempotent client IDs, retries).

    Safe to construct once and reuse.
    
    Enhanced with Circuit Breaker to prevent API bans during exchange outages.
    """

    def __init__(self) -> None:
        self.ex = ccxt.delta({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True,
        })
        if USE_INDIA:
            self.ex.urls["api"] = {
                "public":  "https://api.india.delta.exchange",
                "private": "https://api.india.delta.exchange",
            }
        
        # Initialize circuit breakers for different API operations
        self.circuit_breakers = {}
        if CIRCUIT_BREAKER_ENABLED:
            self.circuit_breakers['fetch'] = get_circuit_breaker(
                name="delta_fetch",
                failure_threshold=3,
                timeout=60
            )
            self.circuit_breakers['order'] = get_circuit_breaker(
                name="delta_order",
                failure_threshold=3,
                timeout=30
            )
            log.info("Circuit breakers initialized for API protection")
        
        # Basic connectivity sanity
        try:
            # This will raise if keys/permissions/IP are invalid
            _ = self.ex.fetch_balance()
            log.info("Executor: authenticated with Delta India (CCXT ok)")
        except Exception as e:
            # We allow construction to succeed, but warn loudly;
            # callers will still get exceptions on private calls.
            log.warning("Executor: auth check failed: %s", e)

    # ---------- Market data ----------
    def fetch_ticker(self, symbol: str = DEFAULT_SYMBOL) -> Dict[str, Any]:
        if CIRCUIT_BREAKER_ENABLED and 'fetch' in self.circuit_breakers:
            try:
                return self.circuit_breakers['fetch'].call(self.ex.fetch_ticker, symbol)
            except CircuitBreakerOpen as e:
                log.warning(f"Circuit breaker blocked fetch_ticker: {e}")
                raise
        return self.ex.fetch_ticker(symbol)

    # ---------- Orders ----------
    def create_order(
        self,
        side: str,
        amount: float,
        order_type: str = "market",
        symbol: str = DEFAULT_SYMBOL,
        price: Optional[float] = None,
        reduce_only: bool = False,
        client_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Place an order. order_type in {"market","limit"}.
        - reduce_only -> passes {'reduceOnly': True} to CCXT
        - client_id   -> passes {'clientOrderId': "..."} (idempotency hint)
        """
        if order_type not in ("market", "limit"):
            raise ValueError("order_type must be 'market' or 'limit'")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if amount <= 0:
            raise ValueError("amount must be > 0")
        if order_type == "limit" and price is None:
            raise ValueError("price required for limit orders")

        p = dict(params or {})
        if reduce_only:
            # CCXT unified param name
            p["reduceOnly"] = True
        if client_id:
            p["clientOrderId"] = client_id

        try:
            if order_type == "market":
                order = self.ex.create_order(symbol, "market", side, amount, None, p)
            else:
                order = self.ex.create_order(symbol, "limit", side, amount, float(price), p)
            log.info(
                "EXEC: placed %s %s %s %s @ %s (reduce_only=%s cid=%s)",
                symbol, order_type, side, amount, price, reduce_only, client_id,
            )
            
            # Register order with confirmation guard (for BUY orders only)
            if side == "buy" and client_id and not reduce_only:
                try:
                    from bot.safety.order_confirmation_guard import get_confirmation_guard
                    guard = get_confirmation_guard()
                    guard.register_order(client_id, {
                        'exchange_id': order.get('id'),
                        'symbol': symbol,
                        'side': side,
                        'price': price if price else order.get('price'),
                        'amount': amount
                    })
                except Exception as guard_error:
                    log.warning(f"Failed to register order with confirmation guard: {guard_error}")
            
            return order
        except Exception as e:
            log.error("EXEC: create_order failed: %s", e)
            raise

    def cancel_order(self, order_id: str, symbol: str = DEFAULT_SYMBOL) -> Dict[str, Any]:
        try:
            res = self.ex.cancel_order(order_id, symbol)
            log.info("EXEC: canceled order %s (%s)", order_id, symbol)
            return res
        except Exception as e:
            error_msg = str(e).lower()
            # Testnet often returns 500 errors for orders that don't exist or are already cancelled
            if '500' in error_msg or 'internal server error' in error_msg:
                log.warning("EXEC: cancel_order got 500 error (testnet issue), order %s may already be cancelled", order_id)
                # Return empty dict to indicate "handled" - don't crash the bot
                return {}
            log.error("EXEC: cancel_order failed: %s", e)
            raise

    def cancel_all_orders(self, symbol: str = DEFAULT_SYMBOL) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            open_orders = self.fetch_open_orders(symbol)
            for o in open_orders:
                try:
                    results.append(self.cancel_order(o["id"], symbol))
                except Exception as e:
                    log.warning("EXEC: cancel failed for %s: %s", o.get("id"), e)
            return results
        except Exception as e:
            log.error("EXEC: cancel_all_orders failed to list: %s", e)
            raise

    # ---------- Queries ----------
    def fetch_open_orders(self, symbol: str = DEFAULT_SYMBOL) -> List[Dict[str, Any]]:
        try:
            return self.ex.fetch_open_orders(symbol)
        except Exception as e:
            log.error("EXEC: fetch_open_orders failed: %s", e)
            raise

    def fetch_order(self, order_id: str, symbol: str = DEFAULT_SYMBOL) -> Dict[str, Any]:
        try:
            return self.ex.fetch_order(order_id, symbol)
        except Exception as e:
            log.error("EXEC: fetch_order failed: %s", e)
            raise

    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if CIRCUIT_BREAKER_ENABLED and 'fetch' in self.circuit_breakers:
                try:
                    if symbol:
                        # Some CCXT builds require full fetch then filter
                        ps = self.circuit_breakers['fetch'].call(self.ex.fetch_positions)
                        return [p for p in ps if p.get("symbol") == symbol]
                    return self.circuit_breakers['fetch'].call(self.ex.fetch_positions)
                except CircuitBreakerOpen as e:
                    log.warning(f"Circuit breaker blocked fetch_positions: {e}")
                    raise
            else:
                if symbol:
                    ps = self.ex.fetch_positions()
                    return [p for p in ps if p.get("symbol") == symbol]
                return self.ex.fetch_positions()
        except Exception as e:
            log.error("EXEC: fetch_positions failed: %s", e)
            raise

    def current_position_size(self, symbol: str = DEFAULT_SYMBOL) -> float:
        """
        Returns signed contracts if available, else 0.
        """
        try:
            ps = self.fetch_positions(symbol)
            for p in ps:
                if p.get("symbol") == symbol:
                    # CCXT standardized fields vary; try contracts/size/amount
                    sz = p.get("contracts") or p.get("size") or p.get("amount") or 0
                    try:
                        return float(sz)
                    except Exception:
                        return 0.0
        except Exception:
            pass
        return 0.0

    # ---------- Utilities ----------
    @staticmethod
    def epoch_ms() -> int:
        return int(time.time() * 1000)
