"""
Native MV Straddle Implementation for Delta Exchange India
Handles MV Straddle as a single native product (contract_type: move_options)

MV Straddle is a Delta Exchange India exclusive product that combines
ATM Call + Put premium into ONE tradeable instrument.

Symbol format: MV-{UNDERLYING}-{STRIKE}-{EXPIRY}
Example: MV-BTC-89400-250126

Contract type: move_options

Created: January 25, 2026
"""
import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MVStraddleNative:
    """
    Native MV Straddle handler for Delta Exchange
    
    MV Straddle is a single tradeable product that combines ATM Call + Put premium.
    This is NOT a synthetic strategy - it's a native Delta Exchange product.
    """
    
    def __init__(self, api_client):
        self.api_client = api_client
        self._products_cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes
        
        # Use requests session for API calls
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        self.api_base = "https://api.india.delta.exchange"
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if not self._cache_timestamp:
            return False
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl
    
    def get_available_mv_straddles(
        self, 
        underlying: str = "BTC",
        state: str = "live"
    ) -> List[Dict]:
        """
        Get all available MV Straddle products
        
        Args:
            underlying: BTC or ETH
            state: live, upcoming, expired
        
        Returns:
            List of MV Straddle products sorted by expiry (nearest first)
        """
        try:
            # Check cache
            cache_key = f"{underlying}_{state}"
            if self._is_cache_valid() and cache_key in self._products_cache:
                logger.debug(f"Returning cached MV Straddles for {underlying}")
                return self._products_cache[cache_key]
            
            # Fetch from API
            logger.info(f"Fetching MV Straddle products for {underlying} (state: {state})")
            
            # Use requests directly
            url = f"{self.api_base}/v2/products"
            response = self.session.get(url, params={'contract_types': 'move_options'}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                logger.error("Empty response from /v2/products")
                return []
            
            products = data.get("result", [])
            
            # Filter by underlying and state
            mv_straddles = [
                p for p in products
                if (p.get("underlying_asset", {}).get("symbol") == underlying and
                    p.get("state") == state)
            ]
            
            # Sort by settlement time (nearest first)
            mv_straddles.sort(key=lambda x: x.get("settlement_time", ""))
            
            # Update cache
            self._products_cache[cache_key] = mv_straddles
            self._cache_timestamp = datetime.now()
            
            logger.info(f"Found {len(mv_straddles)} MV Straddles for {underlying}")
            return mv_straddles
            
        except Exception as e:
            logger.error(f"Error fetching MV Straddles: {e}", exc_info=True)
            return []
    
    def get_mv_straddle_by_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Get specific MV Straddle product by symbol
        
        Args:
            symbol: MV Straddle symbol (e.g., MV-BTC-89400-250126)
        
        Returns:
            Product dict or None
        """
        try:
            url = f"{self.api_base}/v2/products"
            response = self.session.get(url, params={'contract_types': 'move_options'}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            products = data.get("result", [])
            
            for product in products:
                if product.get("symbol") == symbol:
                    return product
            
            logger.warning(f"MV Straddle product not found: {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching MV Straddle {symbol}: {e}")
            return None
    
    def get_expirations(self, underlying: str = "BTC") -> List[Dict]:
        """
        Get available expiration dates for MV Straddle
        
        Args:
            underlying: BTC or ETH
        
        Returns:
            List of dicts with expiry info:
            [
                {
                    "expiry": "250126",  # DDMMYY format
                    "expiry_date": "2026-01-25",  # ISO format
                    "settlement_time": "2026-01-25T12:00:00Z",
                    "days_to_expiry": 0,
                    "label": "25 Jan 2026 (Today)"
                }
            ]
        """
        try:
            products = self.get_available_mv_straddles(underlying)
            
            # Extract unique expirations
            expirations_map = {}
            
            for product in products:
                symbol = product.get("symbol", "")
                settlement_time = product.get("settlement_time", "")
                
                # Parse expiry from symbol: MV-BTC-89400-250126
                parts = symbol.split("-")
                if len(parts) == 4:
                    expiry_code = parts[3]  # 250126
                    
                    if expiry_code not in expirations_map:
                        # Parse settlement time
                        try:
                            settlement_dt = datetime.fromisoformat(settlement_time.replace('Z', '+00:00'))
                            expiry_date = settlement_dt.strftime('%Y-%m-%d')
                            days_to_expiry = (settlement_dt.date() - datetime.now().date()).days
                            
                            # Create label
                            if days_to_expiry == 0:
                                label = f"{settlement_dt.strftime('%d %b %Y')} (Today)"
                            elif days_to_expiry == 1:
                                label = f"{settlement_dt.strftime('%d %b %Y')} (Tomorrow)"
                            else:
                                label = f"{settlement_dt.strftime('%d %b %Y')} ({days_to_expiry} days)"
                            
                            expirations_map[expiry_code] = {
                                "expiry": expiry_code,
                                "expiry_date": expiry_date,
                                "settlement_time": settlement_time,
                                "days_to_expiry": days_to_expiry,
                                "label": label
                            }
                        except Exception as e:
                            logger.warning(f"Failed to parse settlement time {settlement_time}: {e}")
            
            # Sort by settlement time
            expirations = sorted(expirations_map.values(), key=lambda x: x["settlement_time"])
            
            logger.info(f"Found {len(expirations)} expiration dates for {underlying}")
            return expirations
            
        except Exception as e:
            logger.error(f"Error getting expirations: {e}")
            return []
    
    def get_strikes_for_expiry(self, underlying: str, expiry: str) -> List[Dict]:
        """
        Get available strikes for specific expiry
        
        Args:
            underlying: BTC or ETH
            expiry: DDMMYY format (e.g., 250126)
        
        Returns:
            List of dicts with strike info:
            [
                {
                    "strike": 89400,
                    "symbol": "MV-BTC-89400-250126",
                    "product_id": 118230,
                    "is_atm": true,
                    "distance_from_spot": -668.4
                }
            ]
        """
        try:
            products = self.get_available_mv_straddles(underlying)
            
            # Get current spot price
            spot_price = self._get_spot_price(underlying)
            
            strikes = []
            
            for product in products:
                symbol = product.get("symbol", "")
                
                # Check if this product matches the expiry
                if symbol.endswith(f"-{expiry}"):
                    strike = int(float(product.get("strike_price", 0)))
                    
                    distance = spot_price - strike if spot_price > 0 else 0
                    is_atm = abs(distance) < 1000  # Within 1000 of spot
                    
                    strikes.append({
                        "strike": strike,
                        "symbol": symbol,
                        "product_id": product.get("id"),
                        "is_atm": is_atm,
                        "distance_from_spot": distance
                    })
            
            # Sort by strike price
            strikes.sort(key=lambda x: x["strike"])
            
            logger.info(f"Found {len(strikes)} strikes for {underlying} {expiry}")
            return strikes
            
        except Exception as e:
            logger.error(f"Error getting strikes: {e}")
            return []
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get ticker data for MV Straddle
        
        Args:
            symbol: MV Straddle symbol (e.g., MV-BTC-89400-250126)
        
        Returns:
            Ticker data with mark_price, greeks, quotes, etc.
        """
        try:
            url = f"{self.api_base}/v2/tickers/{symbol}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("result")
            
            if ticker:
                logger.debug(f"Got ticker for {symbol}: mark_price={ticker.get('mark_price')}")
            else:
                logger.warning(f"No ticker data for {symbol}")
            
            return ticker
            
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        size: int,
        order_type: str = "limit_order",
        limit_price: Optional[float] = None
    ) -> Dict:
        """
        Place MV Straddle order
        
        Args:
            symbol: MV Straddle symbol
            side: "buy" or "sell"
            size: Number of contracts
            order_type: "limit_order" or "market_order"
            limit_price: Limit price (required for limit orders)
        
        Returns:
            {
                "success": True/False,
                "order": {...},
                "error": "..."
            }
        """
        try:
            # Get product details
            product = self.get_mv_straddle_by_symbol(symbol)
            if not product:
                return {"success": False, "error": f"Product not found: {symbol}"}
            
            product_id = product.get("id")
            
            # Build order request
            order_data = {
                "product_id": product_id,
                "product_symbol": symbol,
                "size": size,
                "side": side,
                "order_type": order_type
            }
            
            # Add limit price if limit order
            if order_type == "limit_order":
                if not limit_price:
                    return {"success": False, "error": "Limit price required for limit orders"}
                order_data["limit_price"] = str(limit_price)
            
            # Place order via API client (authenticated)
            logger.info(f"Placing MV Straddle order: {side} {size} {symbol} (product_id={product_id}) @ {limit_price}")
            
            # Use api_client's place_order method - expects product_id (int), not symbol
            # MAKER-ONLY: For limit orders, use post_only=True to ensure order only adds liquidity
            # Market orders don't use post_only parameter
            use_post_only = (order_type == "limit_order")
            order = await self.api_client.place_order(
                product_id=product_id,
                size=size,
                side=side,
                order_type=order_type,
                price=limit_price if order_type == "limit_order" else None,
                post_only=use_post_only
            )
            
            if order:
                logger.info(f"✅ Order placed successfully: {order.get('id', order)}")
                return {
                    "success": True,
                    "order": order
                }
            else:
                logger.error(f"❌ Order failed: No response from API")
                return {
                    "success": False,
                    "error": "No response from API"
                }
                
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def calculate_pnl(
        self,
        entry_price: float,
        current_price: float,
        size: int,
        side: str,
        contract_value: float = 0.001
    ) -> Dict:
        """
        Calculate P&L for MV Straddle position
        
        Args:
            entry_price: Entry price
            current_price: Current mark price
            size: Position size
            side: "buy" or "sell"
            contract_value: Contract value (default 0.001 BTC)
        
        Returns:
            {
                "pnl": 0.255,  # in BTC
                "pnl_usd": 22500.0,
                "pnl_pct": 3.79,
                "unrealized_pnl": 0.255
            }
        """
        try:
            if side == "buy":
                pnl = (current_price - entry_price) * size * contract_value
            else:  # sell
                pnl = (entry_price - current_price) * size * contract_value
            
            pnl_pct = (pnl / (entry_price * size * contract_value)) * 100 if entry_price > 0 else 0
            
            # Estimate USD value (approximate)
            pnl_usd = pnl * 88000  # Rough BTC price
            
            return {
                "pnl": round(pnl, 8),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_pct": round(pnl_pct, 2),
                "unrealized_pnl": round(pnl, 8)
            }
            
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}")
            return {
                "pnl": 0,
                "pnl_usd": 0,
                "pnl_pct": 0,
                "unrealized_pnl": 0
            }
    
    def _get_spot_price(self, underlying: str) -> float:
        """Get current spot price for underlying"""
        try:
            symbol = f"{underlying}USD"
            url = f"{self.api_base}/v2/tickers/{symbol}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            result = data.get("result", {})
            spot = float(result.get("mark_price") or result.get("close") or 0)
            
            return spot
            
        except Exception as e:
            logger.error(f"Error getting spot price for {underlying}: {e}")
            return 0.0
    
    def get_atm_strike(self, underlying: str, expiry: str) -> Optional[int]:
        """
        Get ATM (At-The-Money) strike for given expiry
        
        Args:
            underlying: BTC or ETH
            expiry: DDMMYY format
        
        Returns:
            ATM strike price or None
        """
        try:
            strikes = self.get_strikes_for_expiry(underlying, expiry)
            
            if not strikes:
                return None
            
            # Find strike marked as ATM
            atm_strikes = [s for s in strikes if s.get("is_atm")]
            
            if atm_strikes:
                # Return the one closest to spot
                atm_strikes.sort(key=lambda x: abs(x.get("distance_from_spot", 0)))
                return atm_strikes[0]["strike"]
            
            # Fallback: Find closest strike to spot
            spot_price = self._get_spot_price(underlying)
            if spot_price > 0:
                strikes.sort(key=lambda x: abs(spot_price - x["strike"]))
                return strikes[0]["strike"]
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting ATM strike: {e}")
            return None
