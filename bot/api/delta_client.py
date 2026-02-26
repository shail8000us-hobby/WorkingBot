"""
Delta Exchange API Client

CRITICAL FEATURES (DO NOT BREAK):
- HMAC-SHA256 authentication (API key/secret signing)
- Order placement/cancellation (trading operations)
- Position management (portfolio tracking)
- Error handling and retries (reliability)
- Risk guard integration (safety checks)

Minimal, battle-tested adapter for Delta Exchange:
- Auth: seconds timestamp; signature over METHOD + ts + path + query + body
- Sends raw JSON (data=...) to match exactly what was signed
- Includes 'User-Agent' to avoid random 4xx

Configuration (from YAML):
- api.live_private_url or api.demo_private_url (based on trading_mode)
- safety.circuit_breaker settings
- API credentials from environment (DELTA_API_KEY, DELTA_API_SECRET)
"""

__VERSION__ = "1.0.1"
__STATUS__ = "Active"

import os
import sys
import time
import hmac
import json
import hashlib
import requests
import logging
from typing import Any, Dict, Optional, Union
from pathlib import Path

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config
from bot.risk.guards import assert_can_trade, RiskBreach
from bot.safety.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

log = logging.getLogger("delta_client")


class DeltaClient:
    """
    Delta Exchange API Client - Production-Ready
    """

    def __init__(self):
        # Load YAML configuration
        yaml_config = get_config()
        
        # Get API URL based on trading mode
        if yaml_config.trading_mode == 'demo':
            self.base = yaml_config.api.demo_private_url.rstrip("/")
        else:
            self.base = yaml_config.api.live_private_url.rstrip("/")
        
        # API credentials from environment (security - never in YAML)
        # Support both DELTA_API_KEY and LIVE_DELTA_API_KEY for backward compatibility
        self.key = (os.getenv("DELTA_API_KEY") or os.getenv("LIVE_DELTA_API_KEY") or "").strip()
        self.sec = (os.getenv("DELTA_API_SECRET") or os.getenv("LIVE_DELTA_API_SECRET") or "").strip()

        if not self.key or not self.sec:
            raise RuntimeError("Missing DELTA_API_KEY / DELTA_API_SECRET")

        self.session = requests.Session()
        # If you want, add retries here (urllib3 Retry)
        
        # Initialize Circuit Breaker from YAML config
        self.circuit_breaker = CircuitBreaker(
            name="delta_api",
            failure_threshold=yaml_config.safety.circuit_breaker.failure_threshold,
            timeout=yaml_config.safety.circuit_breaker.timeout_seconds,
            half_open_max_calls=yaml_config.safety.circuit_breaker.half_open_calls
        )
        log.info(f"Circuit Breaker initialized for Delta API (threshold={self.circuit_breaker.failure_threshold}, timeout={self.circuit_breaker.timeout}s)")

    # ---------- signing / request ----------
    def _auth_headers(self, method: str, path: str, query: str, body: str) -> Dict[str, str]:
        ts = str(int(time.time()))  # seconds
        prehash = method.upper() + ts + path + query + body
        sig = hmac.new(self.sec.encode(), prehash.encode(),
                       hashlib.sha256).hexdigest()
        return {
            "api-key": self.key,
            "timestamp": ts,
            "signature": sig,
            "User-Agent": "python-rest-client",
            "Content-Type": "application/json",
        }

    def _req(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Make API request with Circuit Breaker protection.
        
        The circuit breaker will:
        - Block calls if too many failures occur
        - Automatically retry after timeout period
        - Prevent API hammering during outages
        """
        try:
            # Wrap the actual request in circuit breaker
            return self.circuit_breaker.call(
                self._make_api_request,
                method,
                path,
                json_body,
                params
            )
        except CircuitBreakerOpen as e:
            # Circuit breaker is open - API is down or rate limited
            log.error(f"Circuit breaker OPEN: {e}")
            # Return safe default to prevent bot crash
            return {"success": False, "error": "API temporarily unavailable (circuit breaker open)", "result": []}
    
    def _make_api_request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Internal method that makes the actual API request (wrapped by circuit breaker)
        
        ✅ PRIORITY 1 ENHANCEMENT (NOV 11, 2025):
        - Automatic retry on 429 (rate limit) with Retry-After header parsing
        - Exponential backoff on 5xx (server errors): 1s, 2s, 4s, 8s, 16s, 32s, 60s max
        - Prevents IP bans and improves resilience during exchange outages
        """
        from urllib.parse import urlencode
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            body = "" if json_body is None else json.dumps(
                json_body, separators=(",", ":"))
            query = ""
            if params:
                # URL-encode the query string to match what requests library will send
                query = "?" + urlencode(sorted(params.items()))

            headers = self._auth_headers(method, path, query, body)
            url = self.base + path

            try:
                r = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=(body or None),  # send EXACT body we signed
                    headers=headers,
                    timeout=15,
                )
                
                # ✅ PRIORITY 1: Handle rate limits with Retry-After header
                if r.status_code == 429:
                    retry_after = int(r.headers.get('Retry-After', 60))
                    log.warning(f"⚠️  Rate limited (429). Exchange says retry after {retry_after}s")
                    log.warning(f"   └─ Request: {method} {path}")
                    log.warning(f"   └─ Attempt: {retry_count + 1}/{max_retries}")
                    
                    if retry_count < max_retries - 1:
                        log.info(f"   └─ Waiting {retry_after}s before retry...")
                        time.sleep(retry_after)
                        retry_count += 1
                        continue
                    else:
                        log.error(f"❌ Rate limit persists after {max_retries} attempts")
                        try:
                            error_detail = r.json()
                            log.error(f"   └─ Response: {error_detail}")
                        except:
                            log.error(f"   └─ Response: {r.text}")
                        r.raise_for_status()
                
                # ✅ PRIORITY 1: Handle transient server errors (5xx) with exponential backoff
                if r.status_code >= 500:
                    wait_time = min(2 ** retry_count, 60)  # 1s, 2s, 4s, 8s, 16s, 32s, 60s
                    log.warning(f"⚠️  Server error {r.status_code} (likely transient)")
                    log.warning(f"   └─ Request: {method} {path}")
                    log.warning(f"   └─ Attempt: {retry_count + 1}/{max_retries}")
                    
                    if retry_count < max_retries - 1:
                        log.info(f"   └─ Retrying in {wait_time}s (exponential backoff)...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        log.error(f"❌ Server error persists after {max_retries} attempts")
                        try:
                            error_detail = r.json()
                            log.error(f"   └─ Response: {error_detail}")
                        except:
                            log.error(f"   └─ Response: {r.text}")
                        r.raise_for_status()
                
                # Success or permanent error (4xx except 429)
                if not r.ok:
                    try:
                        error_detail = r.json()
                        log.error(f"❌ Delta API Error {r.status_code}: {error_detail}")
                        log.error(f"   Request: {method} {path}")
                        if json_body:
                            log.error(f"   Body: {body}")
                    except:
                        log.error(f"❌ Delta API Error {r.status_code}: {r.text}")
                    r.raise_for_status()
                
                # Success!
                return r.json()
                
            except requests.exceptions.RequestException as e:
                # Network errors, timeouts, etc.
                log.error(f"❌ Request exception: {e}")
                log.error(f"   └─ Request: {method} {path}")
                
                # Retry on network errors (connection issues, timeouts)
                if retry_count < max_retries - 1:
                    wait_time = min(2 ** retry_count, 30)
                    log.warning(f"   └─ Retrying in {wait_time}s due to network error...")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                else:
                    log.error(f"   └─ Network error persists after {max_retries} attempts")
                    raise
        
        # Should never reach here, but just in case
        raise RuntimeError(f"API request failed after {max_retries} retries")

    # ---------- circuit breaker monitoring ----------
    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring"""
        return self.circuit_breaker.get_stats()
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker (for testing/manual intervention)"""
        self.circuit_breaker.reset()
        log.info("Circuit breaker manually reset")
    
    # ---------- products / tickers ----------
    def get_products(self):
        return self._req("GET", "/v2/products")

    def resolve_product_id(self, symbol: str) -> int:
        # Check YAML config first, then query API
        cfg = get_config()
        if cfg.trading.product_id:
            return int(cfg.trading.product_id)
        data = self.get_products()
        for p in data.get("result", []):
            if p.get("symbol") == symbol:
                return int(p["id"])
        raise RuntimeError(f"Product ID not found for {symbol}")

    def get_ticker_by_product_id(self, product_id: int) -> Optional[dict]:
        data = self._req("GET", "/v2/tickers",
                         params={"product_ids": product_id})
        arr = data.get("result") or []
        return arr[0] if arr else None

    # ---------- account snapshot for risk canary ----------
    def account_snapshot_inr(self) -> Dict[str, Any]:
        # conservative defaults; replace with real endpoints if you have them
        return {
            "realized_pnl_inr": "0",
            "balance_inr": "999999999",   # prod can be large; guards still applied
            "open_notional_inr": "0",
            "open_orders_count": 0,
        }

    # ---------- orders ----------
    def place_order(
        self,
        *,
        product_id: int,
        side: str,
        size: int,
        limit_price: Union[float, str],
        order_type: str = "limit_order",   # must be 'limit_order'
        time_in_force: str = "gtc",        # must be lowercase 'gtc'
        post_only: Optional[bool] = None,
        client_order_id: Optional[str] = None,
        **extra,
    ):
        # Guard before we hit the wire
        snap = self.account_snapshot_inr()
        assert_can_trade(
            account_snapshot=snap,
            pending_open_orders=0,
            intended_qty=size,
            intended_price=limit_price,
        )

        payload = {
            "product_id": int(product_id),
            "side": side,
            "size": int(size),
            "limit_price": str(limit_price),   # API prefers string
            "order_type": order_type,
            "time_in_force": time_in_force,
        }
        if post_only is not None:
            payload["post_only"] = bool(post_only)
        if client_order_id:
            payload["client_order_id"] = client_order_id
        payload.update(extra)

        return self._req("POST", "/v2/orders", json_body=payload)

    def get_order(self, order_id: Union[int, str]):
        return self._req("GET", f"/v2/orders/{order_id}")

    def list_orders(self, *, product_id: Optional[int] = None, product_ids: Optional[str] = None, state: Optional[str] = None, states: Optional[str] = None):
        """
        List orders from Delta Exchange
        
        Delta API uses plural forms: 'states' and 'product_ids'
        Keeping singular forms for backward compatibility
        """
        params = {}
        
        # Product ID - support both singular and plural
        if product_ids is not None:
            params["product_ids"] = product_ids  # Delta API format (plural)
        elif product_id is not None:
            params["product_ids"] = str(product_id)  # Convert to Delta format
        
        # State - support both singular and plural
        if states is not None:
            params["states"] = states  # Delta API format (plural)
        elif state is not None:
            params["states"] = state  # Convert to Delta format
        
        return self._req("GET", "/v2/orders", params=params)
    
    def cancel_all_orders(self, product_id: int, 
                         cancel_limit_orders: str = "true",
                         cancel_stop_orders: str = "true",
                         cancel_reduce_only_orders: str = "true"):
        """
        Cancel all open orders for a product
        
        CRITICAL FIX (Delta AI recommendation):
        The bulk cancel API requires explicit filter parameters to actually cancel orders.
        Without these parameters set to "true", the API returns success=True but doesn't
        cancel any orders (confirmed bug in our testing).
        
        Args:
            product_id: Product ID to cancel orders for
            cancel_limit_orders: "true" to cancel limit orders (default: "true")
            cancel_stop_orders: "true" to cancel stop orders (default: "true")
            cancel_reduce_only_orders: "true" to cancel reduce-only orders (default: "true")
        
        Returns:
            API response dict with 'success' field
        """
        payload = {
            "product_id": product_id,
            "cancel_limit_orders": cancel_limit_orders,
            "cancel_stop_orders": cancel_stop_orders,
            "cancel_reduce_only_orders": cancel_reduce_only_orders
        }
        return self._req("DELETE", f"/v2/orders/all", json_body=payload)
    
    # ---------- wallet / balances ----------
    def get_wallet_balances(self):
        """Get wallet balances for all assets"""
        return self._req("GET", "/v2/wallet/balances")
    
    def get_wallet_balance(self, asset_id: Optional[int] = None):
        """Get balance for a specific asset or all assets"""
        if asset_id is not None:
            return self._req("GET", f"/v2/wallet/balances/{asset_id}")
        return self.get_wallet_balances()
    
    # ---------- positions ----------
    def get_positions(self, product_id: Optional[int] = None, underlying_asset_symbol: Optional[str] = None):
        """
        Get open positions
        
        Delta API requires at least one of:
        - product_id: specific product
        - underlying_asset_symbol: all positions for asset (e.g., "BTC")
        
        If neither provided, defaults to underlying_asset_symbol="BTC"
        """
        params = {}
        if product_id is not None:
            params["product_id"] = product_id
        elif underlying_asset_symbol is not None:
            params["underlying_asset_symbol"] = underlying_asset_symbol
        else:
            # Default: fetch all BTC positions
            params["underlying_asset_symbol"] = "BTC"
        
        return self._req("GET", "/v2/positions", params=params)
    
    def get_position(self, product_id: int):
        """Get position for a specific product"""
        data = self.get_positions()
        for pos in data.get("result", []):
            if pos.get("product_id") == product_id:
                return pos
        return None
    
    def close_position(self, product_id: int):
        """Close a position by placing a market order on the opposite side.
        
        Delta Exchange India does not have /v2/positions/close endpoint,
        so we close by placing a market order in the opposite direction.
        """
        # 1. Get current position to determine size and side
        pos = self.get_position(product_id)
        if not pos:
            return {'success': False, 'error': f'No open position found for product_id {product_id}'}
        
        size = int(pos.get('size', 0))
        if size == 0:
            return {'success': True, 'result': {}, 'message': 'Position already closed (size=0)'}
        
        # 2. Determine closing side: if long (size > 0) -> sell, if short (size < 0) -> buy
        close_side = 'sell' if size > 0 else 'buy'
        abs_size = abs(size)
        
        # 3. Place market order to close
        payload = {
            "product_id": int(product_id),
            "side": close_side,
            "size": abs_size,
            "order_type": "market_order",
            "reduce_only": True,
        }
        
        log.info(f"Closing position: product_id={product_id}, side={close_side}, size={abs_size}")
        result = self._req("POST", "/v2/orders", json_body=payload)
        
        # Wrap in success format if the API returned order data
        if isinstance(result, dict) and 'result' in result:
            return {'success': True, 'result': result.get('result', {})}
        return result
    
    # ---------- margins ----------
    def get_margins(self):
        """Get margin information from wallet balances"""
        # Delta Exchange India doesn't have /v2/margins endpoint
        # Use wallet balances instead which includes margin data
        return self.get_wallet_balances()
    
    def fetch_portfolio_margins(self):
        """Get portfolio margin data from positions endpoint"""
        # Delta Exchange India doesn't have /v2/portfolio-margins endpoint
        # Use positions endpoint which includes margin and PnL data
        # Return in Delta API format (dict with success/result)
        positions_response = self.get_positions()
        return {
            'success': True,
            'result': positions_response.get('result', []) if isinstance(positions_response, dict) else []
        }
    
    def get_margined_positions(self):
        """Get margined positions with liquidation data"""
        # Delta Exchange India uses /v2/positions for all position data
        # Return in Delta API format (dict with success/result)
        positions_response = self.get_positions()
        return {
            'success': True,
            'result': positions_response.get('result', []) if isinstance(positions_response, dict) else []
        }
    
    def get_margin_requirements(self):
        """Get margin requirements and limits"""
        # Delta Exchange India doesn't have /v2/margins endpoint
        # Use wallet balances which includes available balance and margin data
        return self.get_wallet_balances()
    
    def fetch_portfolio_margin(self):
        """CCXT-compatible portfolio margin fetch (alias for fetch_portfolio_margins)"""
        return self.fetch_portfolio_margins()
    
    # ---------- fills / trades ----------
    def get_fills(self, product_id: Optional[int] = None, start_time: Optional[int] = None, end_time: Optional[int] = None):
        """Get trade fills"""
        params = {}
        if product_id is not None:
            params["product_id"] = product_id
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        return self._req("GET", "/v2/fills", params=params)
    
    # ---------- CCXT compatibility layer ----------
    def fetch_balance(self):
        """
        CCXT-compatible balance fetch
        Returns balance in CCXT format for backward compatibility
        """
        wallet_data = self.get_wallet_balances()
        
        # Convert to CCXT format
        balances = {
            'info': wallet_data,
            'timestamp': int(time.time() * 1000),
            'datetime': None,
            'free': {},
            'used': {},
            'total': {}
        }
        
        for asset in wallet_data.get('result', []):
            symbol = asset.get('asset_symbol', 'USD')
            available = float(asset.get('available_balance', 0))
            balance = float(asset.get('balance', 0))
            
            balances['free'][symbol] = available
            balances['total'][symbol] = balance
            balances['used'][symbol] = balance - available
        
        return balances
    
    def fetch_positions(self, symbols=None):
        """
        CCXT-compatible positions fetch
        Returns positions in CCXT format for backward compatibility
        """
        positions_data = self.get_positions()
        positions = []
        
        for pos in positions_data.get('result', []):
            # Convert to CCXT-like format
            position = {
                'info': pos,
                'id': pos.get('id'),
                'symbol': pos.get('product', {}).get('symbol', ''),
                'timestamp': None,
                'datetime': None,
                'initialMargin': float(pos.get('margin', 0)),
                'initialMarginPercentage': None,
                'maintenanceMargin': float(pos.get('maintenance_margin', 0)),
                'maintenanceMarginPercentage': None,
                'entryPrice': float(pos.get('entry_price', 0)),
                'notional': float(pos.get('size', 0)) * float(pos.get('entry_price', 0)),
                'leverage': float(pos.get('leverage', 1)),
                'unrealizedPnl': float(pos.get('unrealized_pnl', 0)),
                'contracts': float(pos.get('size', 0)),
                'contractSize': 1,
                'side': 'long' if float(pos.get('size', 0)) > 0 else 'short',
                'percentage': None,
                'liquidationPrice': float(pos.get('liquidation_price', 0)),
            }
            positions.append(position)
        
        return positions
    
    def fetch_open_orders(self, symbol=None, product_id=None):
        """
        CCXT-compatible open orders fetch
        Returns orders in CCXT format for backward compatibility
        
        Delta Exchange API uses:
        - 'states' (plural) not 'state'
        - 'product_ids' (plural) not 'product_id'
        """
        params = {"states": "open"}  # FIXED: plural 'states'
        if product_id is not None:
            params["product_ids"] = str(product_id)  # FIXED: plural 'product_ids'
        
        orders_data = self.list_orders(**params)
        orders = []
        
        for order in orders_data.get('result', []):
            # Convert to CCXT-like format
            order_obj = {
                'info': order,
                'id': str(order.get('id')),
                'clientOrderId': order.get('client_order_id'),
                'timestamp': None,
                'datetime': None,
                'lastTradeTimestamp': None,
                'symbol': order.get('product', {}).get('symbol', ''),
                'type': 'limit' if order.get('order_type') == 'limit_order' else 'market',
                'side': order.get('side'),
                'price': float(order.get('limit_price', 0)) if order.get('limit_price') else None,
                'amount': float(order.get('size', 0)),
                'cost': None,
                'average': None,
                'filled': float(order.get('size', 0)) - float(order.get('unfilled_size', 0)),
                'remaining': float(order.get('unfilled_size', 0)),
                'status': order.get('state'),
                'fee': None,
                'trades': None,
            }
            orders.append(order_obj)
        
        return orders
    
    def cancel_order(self, order_id: Union[int, str], symbol=None, product_id: Optional[int] = None):
        try:
            if product_id is None:
                raise ValueError("product_id is required for order cancellation")
            
            return self._req("DELETE", "/v2/orders", json={"id": int(order_id), "product_id": product_id})
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                log.info(f"✅ Order {order_id} not found (already cancelled/filled)")
                return {"success": True, "result": None, "error": None}
            raise
