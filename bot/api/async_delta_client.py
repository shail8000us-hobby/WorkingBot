"""
Async REST API client for Delta Exchange.
Uses httpx for async HTTP calls with retry logic and circuit breaker.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

import httpx
from loguru import logger as log

# Suppress httpx INFO logs (too verbose)
logging.getLogger("httpx").setLevel(logging.WARNING)


# Custom Exception Classes
class DeltaAPIError(Exception):
    """Base Delta API error."""
    pass


class DeltaAuthenticationError(DeltaAPIError):
    """Authentication failed."""
    pass


class DeltaRateLimitError(DeltaAPIError):
    """Rate limit exceeded."""
    pass


class DeltaCircuitBreakerError(DeltaAPIError):
    """Circuit breaker is open."""
    pass


@dataclass
class RateLimitTracker:
    """Track Delta Exchange rate limits per their specifications."""
    
    def __init__(self):
        self.window_duration = 300  # 5 minutes in seconds
        self.max_units = 10000  # 10,000 units per 5-minute window
        self.current_window_start = time.time()
        self.current_units_used = 0
        self.request_weights = {
            'POST /orders': 5,
            'DELETE /orders': 5,
            'GET /orders': 3,
            'GET /positions': 3,
            'GET /products': 3,
            'default': 3
        }
    
    def get_request_weight(self, method: str, endpoint: str) -> int:
        """Get weight for a specific request."""
        key = f"{method} {endpoint.split('?')[0]}"  # Remove query params
        return self.request_weights.get(key, self.request_weights['default'])
    
    def can_make_request(self, method: str, endpoint: str) -> bool:
        """Check if request can be made without exceeding rate limits."""
        self._reset_window_if_needed()
        weight = self.get_request_weight(method, endpoint)
        return (self.current_units_used + weight) <= self.max_units
    
    def record_request(self, method: str, endpoint: str) -> None:
        """Record a request and update usage."""
        self._reset_window_if_needed()
        weight = self.get_request_weight(method, endpoint)
        self.current_units_used += weight
        log.debug(f"Rate limit: Used {weight} units, total: {self.current_units_used}/{self.max_units}")
    
    def _reset_window_if_needed(self) -> None:
        """Reset window if 5 minutes have passed."""
        current_time = time.time()
        if current_time - self.current_window_start >= self.window_duration:
            self.current_window_start = current_time
            self.current_units_used = 0
            log.debug("Rate limit window reset")
    
    def get_reset_time(self) -> float:
        """Get time until rate limit window resets."""
        return self.window_duration - (time.time() - self.current_window_start)

@dataclass
class ClientMetrics:
    """HTTP client metrics."""
    
    requests_made: int = 0
    requests_failed: int = 0
    total_response_time: float = 0.0
    circuit_breaker_opens: int = 0
    rate_limit_hits: int = 0


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for API calls."""
    
    failures: int = 0
    last_failure: float = 0
    is_open: bool = False
    reset_after: float = 60.0  # Reset circuit after 60 seconds
    failure_threshold: int = 5  # Open circuit after 5 failures


class AsyncDeltaClient:
    """
    Async REST API client for Delta Exchange.
    
    Features:
    - Connection pooling with limits
    - Automatic retry with exponential backoff
    - Circuit breaker pattern
    - Timeout handling
    - Delta Exchange authentication
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.india.delta.exchange",
        testnet: bool = False,
        max_connections: int = 10,
        timeout: float = 10.0
    ):
        """
        Initialize async Delta client.
        
        Args:
            api_key: Delta Exchange API key
            api_secret: Delta Exchange API secret
            base_url: Base URL for API (default: India exchange)
            testnet: Whether to use testnet
            max_connections: Maximum concurrent connections
            timeout: Default timeout in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url if not testnet else "https://cdn-ind.testnet.deltaex.org"
        self.timeout = timeout
        
        # HTTP client with connection pooling
        limits = httpx.Limits(max_connections=max_connections, max_keepalive_connections=5)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            limits=limits,
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "python-rest-client",  # Required by Delta Exchange
                "Content-Type": "application/json"
            }
        )
        
        # Circuit breaker, metrics, and rate limiting
        self._circuit_breaker = CircuitBreakerState()
        self._metrics = ClientMetrics()
        self._rate_limiter = RateLimitTracker()
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
    
    def _generate_signature(self, method: str, path: str, query_or_payload: str = "") -> Dict[str, str]:
        """
        Generate Delta Exchange authentication signature.
        
        Delta Exchange signature format:
        - For GET/DELETE with params: METHOD + TIMESTAMP + PATH + ?QUERY_STRING  (Note: '?' prefix required!)
        - For POST/PUT with body: METHOD + TIMESTAMP + PATH + JSON_BODY
        
        CRITICAL: For GET/DELETE, query_or_payload MUST include the '?' prefix
        Example: "?product_id=27&state=open" NOT "product_id=27&state=open"
        
        Args:
            method: HTTP method (uppercase)
            path: API path (e.g., "/v2/orders")
            query_or_payload: Query string WITH '?' prefix for GET/DELETE, or JSON body for POST/PUT
            
        Returns:
            Dict with authentication headers
        """
        timestamp = str(int(time.time()))  # Delta API uses SECONDS not milliseconds
        signature_data = method.upper() + timestamp + path + query_or_payload
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "api-key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "User-Agent": "python-rest-client",  # Required by Delta Exchange
            "Content-Type": "application/json"
        }
    
    def _check_circuit_breaker(self):
        """
        Check if circuit breaker is open.
        
        Raises:
            DeltaCircuitBreakerError: If circuit is open
        """
        if self._circuit_breaker.is_open:
            # Check if we should reset
            if time.time() - self._circuit_breaker.last_failure > self._circuit_breaker.reset_after:
                log.info("Circuit breaker reset after cooldown")
                self._circuit_breaker.is_open = False
                self._circuit_breaker.failures = 0
            else:
                raise DeltaCircuitBreakerError(f"Circuit breaker open - API calls blocked for {self._circuit_breaker.reset_after}s")
    
    def _record_failure(self):
        """Record API failure for circuit breaker."""
        # Only advance the failure counter when the breaker is NOT already open.
        # Updating last_failure while open resets the cooldown timer, causing
        # the breaker to stay permanently open under sustained blocked traffic.
        if not self._circuit_breaker.is_open:
            self._circuit_breaker.failures += 1
            self._circuit_breaker.last_failure = time.time()

            if self._circuit_breaker.failures >= self._circuit_breaker.failure_threshold:
                log.error(f"Circuit breaker opened after {self._circuit_breaker.failures} failures")
                self._circuit_breaker.is_open = True
                self._metrics.circuit_breaker_opens += 1
    
    def _record_success(self):
        """Record API success - reset failure count."""
        self._circuit_breaker.failures = 0
    
    async def _request_with_retry(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        max_retries: int = 3,
        backoff_base: int = 1
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method
            path: API path
            params: Query parameters
            data: Request body
            max_retries: Maximum retry attempts
            backoff_base: Base for exponential backoff
            
        Returns:
            Response data
            
        Raises:
            httpx.HTTPStatusError: For 4xx errors (no retry)
            Exception: For other errors after retries exhausted
        """
        # Check circuit breaker
        self._check_circuit_breaker()
        
        # Check rate limits (Delta Exchange: 10,000 units per 5min window)
        if not self._rate_limiter.can_make_request(method, path):
            reset_time = self._rate_limiter.get_reset_time()
            self._metrics.rate_limit_hits += 1
            log.warning(f"Rate limit exceeded. Reset in {reset_time:.1f}s")
            raise DeltaRateLimitError(f"Rate limit exceeded. Reset in {reset_time:.1f}s")
        
        # Record request for rate limiting
        self._rate_limiter.record_request(method, path)
        
        # Track metrics
        start_time = time.time()
        self._metrics.requests_made += 1
        
        # Retry loop
        for attempt in range(max_retries):
            try:
                # Prepare request with proper signature
                headers = {}
                
                if data:
                    # POST/PUT with JSON body
                    # CRITICAL: Use compact JSON format (no spaces) and raw string payload
                    payload = json.dumps(data, separators=(',', ':'))
                    headers = self._generate_signature(method, path, payload)
                    
                    response = await self._client.request(
                        method=method,
                        url=path,
                        content=payload.encode('utf-8'),  # Send as bytes for exact signature match
                        headers=headers
                    )
                    
                elif method in ["GET", "DELETE"] and params:
                    # GET/DELETE with query parameters
                    # CRITICAL FIX: Build the EXACT query string that will be sent in the request
                    # httpx doesn't sort params, so we must sign the unsorted query string
                    query_string = urlencode(list(params.items()))  # Convert dict_items to list, preserve order
                    query_with_prefix = f"?{query_string}"
                    
                    # Generate signature with '?' prefix and UNSORTED params
                    headers = self._generate_signature(method, path, query_with_prefix)
                    
                    # Make request - httpx will build the URL from base_url + path + params
                    # IMPORTANT: Pass params in same order used for signature
                    response = await self._client.request(
                        method=method,
                        url=path,  # Just the path, httpx will add base_url
                        params=params,  # Original order matches signature
                        headers=headers
                    )
                    
                else:
                    # Simple request without params or data
                    headers = self._generate_signature(method, path, "")
                    
                    response = await self._client.request(
                        method=method,
                        url=path,
                        headers=headers
                    )
                
                # Check for rate limit
                if response.status_code == 429:
                    self._metrics.rate_limit_hits += 1
                    retry_after = int(response.headers.get("Retry-After", 60))
                    log.warning(f"Rate limited - waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                
                # Check for auth errors (no retry)
                if response.status_code == 401:
                    self._metrics.requests_failed += 1
                    self._metrics.total_response_time += time.time() - start_time
                    raise DeltaAuthenticationError("Authentication failed - check API credentials")
                
                # Check for client errors (no retry for most, but some are retryable)
                if 400 <= response.status_code < 500:
                    # Parse error response for Delta Exchange specific errors
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error', {}).get('code', '')
                        error_message = error_data.get('error', {}).get('message', str(error_data))
                        
                        # Delta Exchange specific retryable errors
                        retryable_errors = {
                            'insufficient_margin',  # May resolve if positions close
                            'order_size_exceed_available',  # May resolve with smaller size
                        }
                        
                        # Permanent errors (no retry)
                        permanent_errors = {
                            'invalid_contract',
                            'immediate_liquidation', 
                            'risk_limits_breached',
                            'ip_blocked_for_api_key'
                        }
                        
                        if error_code in retryable_errors and attempt < max_retries - 1:
                            wait_time = backoff_base * (2 ** attempt)
                            log.warning(f"Retryable error {error_code}: {error_message} - retry {attempt + 1}/{max_retries} after {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        elif error_code in permanent_errors:
                            log.error(f"Permanent error {error_code}: {error_message}")
                            raise DeltaAPIError(f"{error_code}: {error_message}")
                        else:
                            log.error(f"Client error {response.status_code}: {error_message}")
                            response.raise_for_status()
                    except (json.JSONDecodeError, KeyError):
                        # Fallback if error parsing fails
                        response.raise_for_status()
                
                # Check for server errors (retry)
                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        wait_time = backoff_base * (2 ** attempt)
                        log.warning(f"Server error {response.status_code} - retry {attempt + 1}/{max_retries} after {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    response.raise_for_status()
                
                # Success
                self._record_success()
                self._metrics.total_response_time += time.time() - start_time
                return response.json()
            
            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    wait_time = backoff_base * (2 ** attempt)
                    log.warning(f"Request timeout - retry {attempt + 1}/{max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                self._record_failure()
                self._metrics.requests_failed += 1
                self._metrics.total_response_time += time.time() - start_time
                raise Exception(f"Request timeout after {max_retries} attempts") from e
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    # Client error - don't retry
                    self._record_failure()
                    self._metrics.requests_failed += 1
                    self._metrics.total_response_time += time.time() - start_time
                    raise
                if attempt < max_retries - 1:
                    wait_time = backoff_base * (2 ** attempt)
                    log.warning(f"HTTP error {e.response.status_code} - retry {attempt + 1}/{max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                self._record_failure()
                self._metrics.requests_failed += 1
                self._metrics.total_response_time += time.time() - start_time
                raise
            
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = backoff_base * (2 ** attempt)
                    log.warning(f"Request error: {e} - retry {attempt + 1}/{max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                self._record_failure()
                self._metrics.requests_failed += 1
                self._metrics.total_response_time += time.time() - start_time
                raise
        
        # Should never reach here
        self._record_failure()
        self._metrics.requests_failed += 1
        self._metrics.total_response_time += time.time() - start_time
        raise Exception(f"Request failed after {max_retries} attempts")
    
    async def place_order(
        self,
        product_id: int,
        side: str,
        price: float = None,  # Optional for market orders
        size: int = None,
        order_type: str = "limit_order",
        time_in_force: str = "gtc",
        post_only: bool = True,
        reduce_only: bool = False,
        client_order_id: str = None
    ) -> Dict[str, Any]:
        """
        Place order on Delta Exchange.
        
        Args:
            product_id: Delta Exchange product ID (integer, not symbol)
            side: Order side ("buy" or "sell")
            price: Order price (None for market orders)
            size: Order size (number of contracts)
            order_type: Order type ("limit_order" or "market_order")
            time_in_force: Time in force ("gtc", "ioc", "fok")
            post_only: Whether order is post-only (maker only)
            reduce_only: Whether order is reduce-only
            client_order_id: Optional client order ID for tracking
            
        Returns:
            Order response with order_id
        """
        # CRITICAL: Delta Exchange expects boolean values as STRINGS, not actual booleans
        # Build base order data
        data = {
            "product_id": product_id,
            "side": side,
            "order_type": order_type,
            "size": size
        }
        
        # CRITICAL: Market orders have different requirements than limit orders
        if order_type == "market_order":
            # Market orders: NO limit_price, NO post_only, NO time_in_force
            # Only include reduce_only if it's True
            if reduce_only:
                data["reduce_only"] = "true"
        else:
            # Limit orders: Include all standard fields
            if price is not None:
                data["limit_price"] = str(price)
            data["time_in_force"] = time_in_force
            data["post_only"] = "true" if post_only else "false"
            data["reduce_only"] = "true" if reduce_only else "false"
        
        # Add client_order_id if provided (works for both market and limit)
        if client_order_id:
            data["client_order_id"] = client_order_id
        
        # DEBUG: Log the exact request data
        log.info(f"🔍 Placing order with data: {data}")
        
        response = await self._request_with_retry(
            method="POST",
            path="/v2/orders",
            data=data
        )
        
        order_id = response.get('result', {}).get('id')
        price_str = f"@ {price}" if price else "MARKET"
        log.info(f"Order placed: {side} {size} {price_str} (product_id={product_id}) -> {order_id}")
        return response
    
    async def cancel_order(self, order_id: str, product_id: int) -> Dict[str, Any]:
        """
        Cancel order by ID.
        
        Args:
            order_id: Order ID to cancel
            product_id: Product ID for the order
            
        Returns:
            Cancellation response
        """
        response = await self._request_with_retry(
            method="DELETE",
            path="/v2/orders",
            data={"id": int(order_id), "product_id": product_id}
        )
        
        log.info(f"Order cancelled: {order_id}")
        return response
    
    async def edit_order(self, order_id: str, product_id: int, new_price: str) -> Dict[str, Any]:
        """
        Edit order price without cancelling.
        
        Args:
            order_id: Order ID to edit
            product_id: Product ID for the order
            new_price: New limit price as string
            
        Returns:
            Updated order details
        """
        response = await self._request_with_retry(
            method="PUT",
            path="/v2/orders",
            data={
                "id": int(order_id),
                "product_id": product_id,
                "limit_price": new_price
            }
        )
        
        log.info(f"Order edited: {order_id} → ${new_price}")
        return response.get('result', response)
    
    async def get_open_orders(self, product_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get open orders.
        
        Args:
            product_id: Optional product ID filter
            
        Returns:
            List of open orders
        """
        params = {}
        if product_id is not None:
            params["product_id"] = product_id
        
        response = await self._request_with_retry(
            method="GET",
            path="/v2/orders",
            params=params
        )
        
        return response.get("result", [])
    
    async def get_positions(self, product_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get open positions.
        
        Args:
            product_id: Optional product ID filter
            
        Returns:
            List of positions
        """
        params = {}
        if product_id is not None:
            params["product_id"] = product_id
        
        response = await self._request_with_retry(
            method="GET",
            path="/v2/positions",
            params=params
        )
        
        return response.get("result", [])
    
    async def get_positions_for_underlying(self, underlying_asset: str) -> List[Dict[str, Any]]:
        """
        Get all positions for an underlying asset (includes futures + options).
        
        Args:
            underlying_asset: Underlying asset symbol (e.g., "BTC", "ETH")
            
        Returns:
            List of positions (futures + options)
        """
        params = {"underlying_asset_symbol": underlying_asset}
        
        response = await self._request_with_retry(
            method="GET",
            path="/v2/positions",
            params=params
        )
        
        return response.get("result", [])

    async def get_positions_margined(self) -> List[Dict[str, Any]]:
        """
        Get ALL open positions across all products (no filter required).

        Uses /v2/positions/margined which returns all positions that have
        margin allocated. This is the correct endpoint for account-level
        position overview.

        Returns:
            List of position dicts with keys: product_symbol, size, margin,
            entry_price, mark_price, unrealized_pnl, product_id, product, etc.
        """
        response = await self._request_with_retry(
            method="GET",
            path="/v2/positions/margined"
        )
        
        return response.get("result", [])
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get ticker data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            
        Returns:
            Ticker data
        """
        response = await self._request_with_retry(
            method="GET",
            path=f"/v2/tickers/{symbol}"
        )
        
        return response.get("result", {})
    
    async def get_all_tickers(self) -> List[Dict[str, Any]]:
        """
        Get ticker data for all products (includes mark prices).
        
        Returns:
            List of ticker data for all products
        """
        response = await self._request_with_retry(
            method="GET",
            path="/v2/tickers"
        )
        
        return response.get("result", [])
    
    async def get_orderbook(self, symbol: str, depth: int = 10) -> Dict[str, Any]:
        """
        Get orderbook snapshot.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            depth: Orderbook depth (default: 10)
            
        Returns:
            Orderbook data with bids/asks
        """
        response = await self._request_with_retry(
            method="GET",
            path=f"/v2/l2orderbook/{symbol}"
        )
        
        return response.get("result", {})
    
    async def get_wallet_balances(self) -> List[Dict[str, Any]]:
        """
        Get wallet balances for all assets.
        
        Returns:
            List of wallet balances by asset
        """
        response = await self._request_with_retry(
            method="GET",
            path="/v2/wallet/balances"
        )
        
        return response.get("result", [])

    async def get_wallet_balances_full(self) -> Dict[str, Any]:
        """
        Get wallet balances with full response including meta (net_equity, etc.).
        
        Returns:
            Full API response dict with 'result' (wallets list) and 'meta' (net_equity etc.)
        """
        response = await self._request_with_retry(
            method="GET",
            path="/v2/wallet/balances"
        )
        return response
    
    async def get_product(self, symbol: str) -> Dict[str, Any]:
        """
        Get product details by symbol using direct endpoint.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            
        Returns:
            Product details including product_id
        """
        response = await self._request_with_retry(
            method="GET",
            path=f"/v2/products/{symbol}"
        )
        
        return response.get("result", {})
    
    async def get_product_id(self, symbol: str) -> int:
        """
        Get product ID from symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            
        Returns:
            Product ID (integer)
        """
        product = await self.get_product(symbol)
        return product.get("id")
    
    async def place_order_by_symbol(
        self,
        symbol: str,
        side: str,
        price: float = None,
        size: int = None,
        order_type: str = "limit_order",
        time_in_force: str = "gtc",
        post_only: bool = True,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Place order using symbol instead of product_id.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD" or "C-BTC-100000-280126")
            side: Order side ("buy" or "sell")
            price: Order price (required for limit orders, ignored for market)
            size: Order size (number of contracts)
            order_type: Order type ("limit_order" or "market_order")
            time_in_force: Time in force ("gtc", "ioc", "fok") - limit orders only
            post_only: Whether order is post-only (maker only) - limit orders only
            reduce_only: Whether order is reduce-only
            
        Returns:
            Order response with order_id
        """
        # CRITICAL: Delta Exchange expects boolean values as STRINGS, not actual booleans
        # Build base order data
        data = {
            "product_symbol": symbol,
            "side": side,
            "order_type": order_type,
            "size": size
        }
        
        # CRITICAL: Market orders have different requirements than limit orders
        if order_type == "market_order":
            # Market orders: NO limit_price, NO post_only, NO time_in_force
            # Only include reduce_only if it's True
            if reduce_only:
                data["reduce_only"] = "true"
        else:
            # Limit orders: Include all standard fields
            if price is not None:
                data["limit_price"] = str(price)
            data["time_in_force"] = time_in_force
            data["post_only"] = "true" if post_only else "false"
            data["reduce_only"] = "true" if reduce_only else "false"
        
        # DEBUG: Log the exact request data
        log.info(f"🔍 Placing order by symbol: {data}")
        
        response = await self._request_with_retry(
            method="POST",
            path="/v2/orders",
            data=data
        )
        
        log.info(f"Order placed: {side} {size} @ {price or 'MARKET'} ({symbol}) -> {response.get('result', {}).get('id')}")
        return response
    
    async def get_open_orders_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get open orders for a specific symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            
        Returns:
            List of open orders for the symbol
        """
        # Get product_id first, then filter
        product = await self.get_product(symbol)
        product_id = product.get("id")
        
        if product_id:
            return await self.get_open_orders(product_id)
        else:
            return []
    
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order details by ID.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            Order details
        """
        response = await self._request_with_retry(
            method="GET",
            path=f"/v2/orders/{order_id}"
        )
        
        return response.get("result", {})
    
    async def list_orders(
        self,
        symbol: Optional[str] = None,
        states: str = "open,pending",
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List orders with filtering.
        
        Args:
            symbol: Optional symbol filter
            states: Comma-separated states (open,pending,closed,cancelled)
                    Note: 'closed' means filled/completed orders
            page_size: Number of orders per page
            
        Returns:
            List of orders
        """
        params = {
            "states": states,
            "page_size": page_size
        }
        
        if symbol:
            # Get product_id for symbol
            product = await self.get_product(symbol)
            if product_id := product.get("id"):
                params["product_ids"] = str(product_id)
        
        response = await self._request_with_retry(
            method="GET",
            path="/v2/orders",
            params=params
        )
        
        return response.get("result", [])
    
    async def get_fills(
        self,
        product_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get trade fills (filled orders).
        
        Args:
            product_id: Optional product ID filter
            start_time: Optional start timestamp (microseconds)
            end_time: Optional end timestamp (microseconds)
            page_size: Number of fills per page
            
        Returns:
            List of fill records
        """
        params = {"page_size": page_size}
        
        if product_id is not None:
            params["product_id"] = product_id
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time
        
        response = await self._request_with_retry(
            method="GET",
            path="/v2/fills",
            params=params
        )
        
        return response.get("result", [])
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel all orders for a symbol or all symbols.
        
        Args:
            symbol: Optional symbol to cancel orders for
            
        Returns:
            Cancellation response
        """
        # For DELETE with body, need to handle data properly
        if symbol:
            data = {"product_symbol": symbol}
        else:
            data = None
        
        response = await self._request_with_retry(
            method="DELETE",
            path="/v2/orders/all",
            data=data
        )
        
        log.info(f"All orders cancelled for {symbol or 'all symbols'}")
        return response
    
    async def get_products(self) -> List[Dict[str, Any]]:
        """
        Get all products from Delta Exchange
        
        **Added for 0DTE System** - Fetch option chain data
        
        Returns:
            List of product dictionaries with details like:
            - symbol, product_type, underlying_asset
            - strike_price, settlement_time
            - contract_unit_currency, etc.
        """
        try:
            response = await self._request_with_retry(
                method="GET",
                path="/v2/products"
            )
            
            if response.get('success'):
                products = response.get('result', [])
                log.debug(f"Fetched {len(products)} products from Delta Exchange")
                return products
            else:
                log.error(f"Failed to fetch products: {response.get('error')}")
                return []
                
        except Exception as e:
            log.error(f"Exception fetching products: {e}")
            return []
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get client metrics.
        
        Returns:
            Dict with performance and health metrics
        """
        total_requests = self._metrics.requests_made
        avg_response_time = (
            self._metrics.total_response_time / total_requests 
            if total_requests > 0 else 0
        )
        
        return {
            "requests_made": self._metrics.requests_made,
            "requests_failed": self._metrics.requests_failed,
            "success_rate": (
                (total_requests - self._metrics.requests_failed) / total_requests
                if total_requests > 0 else 1.0
            ),
            "average_response_time": avg_response_time,
            "circuit_breaker": {
                "is_open": self._circuit_breaker.is_open,
                "failures": self._circuit_breaker.failures,
                "opens": self._metrics.circuit_breaker_opens
            },
            "rate_limit_hits": self._metrics.rate_limit_hits
        }
