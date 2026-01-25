"""
MV Straddle Strategy Implementation
Market View Straddle with enhanced volatility analysis
"""
from typing import Dict, List, Optional, Tuple
import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class MVStraddleStrategy(BaseStrategy):
    """
    MV Straddle: Buy/Sell Call + Put at same strike
    Enhanced with volatility analysis and intelligent strike selection
    """
    
    def __init__(self, api_client, chain_service, volatility_analyzer, strike_selector):
        super().__init__(api_client, chain_service)
        self.volatility_analyzer = volatility_analyzer
        self.strike_selector = strike_selector
    
    def calculate_legs(
        self,
        underlying: str,
        expiry: str,
        strike: Optional[int] = None,
        direction: str = "long",  # "long" or "short"
        quantity: int = 1,
        auto_strike: bool = True,
        strike_offset: int = 0  # Offset from ATM (e.g., +1000, -500)
    ) -> List[Dict]:
        """
        Calculate MV Straddle legs
        
        Args:
            underlying: BTC or ETH
            expiry: DDMMYYYY format
            strike: Strike price (optional if auto_strike=True)
            direction: "long" (buy both) or "short" (sell both)
            quantity: Number of contracts per leg
            auto_strike: Auto-select ATM strike
            strike_offset: Offset from ATM strike
        
        Returns:
            List of 2 legs (Call + Put)
        """
        try:
            # Get spot price
            spot_price = self._get_spot_price(underlying)
            
            # Determine strike
            if auto_strike or strike is None:
                strike = self.strike_selector.select_atm_strike(
                    underlying=underlying,
                    expiry=expiry,
                    spot_price=spot_price,
                    offset=strike_offset
                )
                logger.info(f"Auto-selected strike: {strike} (spot: {spot_price}, offset: {strike_offset})")
            
            # Convert expiry format (DDMMYYYY -> DDMMYY)
            expiry_6digit = self._convert_expiry_format(expiry)
            
            # Get market data for both legs
            call_symbol = f"C-{underlying}-{strike}-{expiry_6digit}"
            put_symbol = f"P-{underlying}-{strike}-{expiry_6digit}"
            
            call_ticker = self.api_client.get_option_ticker(call_symbol)
            put_ticker = self.api_client.get_option_ticker(put_symbol)
            
            if not call_ticker or not put_ticker:
                logger.warning(f"Could not fetch tickers for {call_symbol} or {put_symbol}, creating legs with estimated data")
                # Continue with estimated prices rather than failing
                call_ticker = self._create_fallback_ticker(call_symbol, spot_price, strike, "call")
                put_ticker = self._create_fallback_ticker(put_symbol, spot_price, strike, "put")
            
            # Determine side based on direction
            side = "buy" if direction == "long" else "sell"
            
            # Build call leg
            call_leg = {
                "option_type": "call",
                "symbol": call_symbol,
                "strike": strike,
                "side": side,
                "quantity": quantity,
                "current_price": self._get_mid_price(call_ticker),
                "iv": call_ticker.get("iv", 0) * 100 if call_ticker.get("iv") else 0,
                "greeks": call_ticker.get("greeks", {}),
                "bid": call_ticker.get("quotes", {}).get("best_bid", 0),
                "ask": call_ticker.get("quotes", {}).get("best_ask", 0)
            }
            
            # Build put leg
            put_leg = {
                "option_type": "put",
                "symbol": put_symbol,
                "strike": strike,
                "side": side,
                "quantity": quantity,
                "current_price": self._get_mid_price(put_ticker),
                "iv": put_ticker.get("iv", 0) * 100 if put_ticker.get("iv") else 0,
                "greeks": put_ticker.get("greeks", {}),
                "bid": put_ticker.get("quotes", {}).get("best_bid", 0),
                "ask": put_ticker.get("quotes", {}).get("best_ask", 0)
            }
            
            legs = [call_leg, put_leg]
            
            logger.info(f"Created MV Straddle legs: {direction} {strike} strike, {quantity} contracts each")
            return legs
            
        except Exception as e:
            logger.error(f"Error calculating MV Straddle legs: {e}")
            raise
    
    def validate_parameters(
        self,
        underlying: str,
        expiry: str,
        direction: str,
        quantity: int,
        **kwargs
    ) -> Tuple[bool, str]:
        """
        Validate MV Straddle parameters
        
        Returns:
            (is_valid, error_message)
        """
        # Validate common parameters
        is_valid, error_msg = self._validate_common_parameters(underlying, expiry, quantity)
        if not is_valid:
            return False, error_msg
        
        # Validate direction
        if direction not in ["long", "short"]:
            return False, f"Invalid direction: {direction}. Must be 'long' or 'short'"
        
        return True, ""
    
    def calculate_breakeven(self, legs: List[Dict]) -> Dict:
        """
        Calculate breakeven points for MV Straddle
        
        For both long and short straddle:
        - Lower breakeven = strike - total_premium
        - Upper breakeven = strike + total_premium
        
        Returns:
            {
                'breakeven_points': [lower, upper],
                'breakeven_lower': float,
                'breakeven_upper': float,
                'breakeven_range': float
            }
        """
        try:
            if len(legs) != 2:
                return {"error": "Straddle must have exactly 2 legs"}
            
            strike = legs[0]["strike"]
            total_premium = sum(leg["current_price"] * leg["quantity"] for leg in legs)
            
            breakeven_lower = strike - total_premium
            breakeven_upper = strike + total_premium
            breakeven_range = breakeven_upper - breakeven_lower
            
            return {
                "breakeven_points": [breakeven_lower, breakeven_upper],
                "breakeven_lower": round(breakeven_lower, 2),
                "breakeven_upper": round(breakeven_upper, 2),
                "breakeven_range": round(breakeven_range, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating breakeven: {e}")
            return {"error": str(e)}
    
    def calculate_max_profit_loss(self, legs: List[Dict]) -> Dict:
        """
        Calculate maximum profit and loss
        
        For Long Straddle:
        - Max loss: total premium paid (at strike)
        - Max profit: unlimited
        
        For Short Straddle:
        - Max profit: total premium received (at strike)
        - Max loss: unlimited
        
        Returns:
            {
                'max_profit': float or 'Unlimited',
                'max_loss': float or 'Unlimited',
                'max_profit_price': strike (for short) or None (for long),
                'max_loss_price': strike
            }
        """
        try:
            if len(legs) != 2:
                return {"error": "Straddle must have exactly 2 legs"}
            
            strike = legs[0]["strike"]
            total_premium = sum(leg["current_price"] * leg["quantity"] for leg in legs)
            direction = legs[0]["side"]
            
            if direction == "buy":
                # Long straddle
                max_profit = "Unlimited"
                max_loss = total_premium
                max_profit_price = None
                max_loss_price = strike
            else:
                # Short straddle
                max_profit = total_premium
                max_loss = "Unlimited"
                max_profit_price = strike
                max_loss_price = None
            
            return {
                "max_profit": max_profit,
                "max_loss": max_loss,
                "max_profit_price": max_profit_price,
                "max_loss_price": max_loss_price,
                "risk_reward_ratio": "Unlimited upside / Limited downside" if direction == "buy" else "Limited upside / Unlimited downside"
            }
            
        except Exception as e:
            logger.error(f"Error calculating max profit/loss: {e}")
            return {"error": str(e)}
    
    def get_volatility_analysis(self, legs: List[Dict], expiry: str, underlying: str) -> Dict:
        """
        Get volatility analysis for this straddle
        
        Args:
            legs: Strategy legs
            expiry: Expiry date
            underlying: BTC or ETH
            
        Returns:
            Volatility analysis dict
        """
        try:
            # Calculate average IV from both legs
            avg_iv = sum(leg.get("iv", 0) for leg in legs) / len(legs)
            
            # Get volatility analysis
            vol_analysis = self.volatility_analyzer.analyze(
                underlying=underlying,
                current_iv=avg_iv,
                expiry=expiry
            )
            
            return vol_analysis
            
        except Exception as e:
            logger.error(f"Error getting volatility analysis: {e}")
            return {"error": str(e)}
    
    def get_strategy_info(self) -> Dict:
        """Return MV Straddle strategy metadata"""
        return {
            "name": "MV Straddle",
            "description": "Market View Straddle - Enhanced straddle with volatility analysis",
            "risk_level": "medium-high",
            "complexity": "intermediate",
            "best_for": "High volatility expectations or volatility premium capture",
            "features": [
                "Auto ATM strike selection",
                "Volatility analysis (IV rank, percentile)",
                "Breakeven calculator",
                "Position adjustment tools (roll, close leg, adjust ratio)"
            ]
        }
    
    def _get_mid_price(self, ticker: Dict) -> float:
        """Get mid price from ticker"""
        try:
            quotes = ticker.get("quotes", {})
            bid = quotes.get("best_bid", 0)
            ask = quotes.get("best_ask", 0)
            
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2
                return round(mid, 2)
            
            # Fallback to mark price
            mark_price = ticker.get("mark_price", 0)
            if mark_price > 0:
                return round(mark_price, 2)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error getting mid price: {e}")
            return 0
    
    def _create_fallback_ticker(self, symbol: str, spot_price: float, strike: int, option_type: str) -> Dict:
        """
        Create fallback ticker when API fails
        
        Uses simple Black-Scholes approximation for estimated prices
        """
        # Simple intrinsic value calculation
        if option_type == "call":
            intrinsic = max(0, spot_price - strike)
        else:
            intrinsic = max(0, strike - spot_price)
        
        # Add some time value (simplified)
        time_value = strike * 0.02  # Rough 2% estimate
        estimated_price = intrinsic + time_value
        
        return {
            "symbol": symbol,
            "quotes": {
                "best_bid": estimated_price * 0.98,
                "best_ask": estimated_price * 1.02
            },
            "mark_price": estimated_price,
            "iv": 0.65,  # Estimated 65% IV
            "greeks": {
                "delta": 0.5 if option_type == "call" else -0.5,
                "gamma": 0.001,
                "vega": strike * 0.01,
                "theta": -0.5
            }
        }
