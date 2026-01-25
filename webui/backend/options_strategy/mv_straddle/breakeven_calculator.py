"""
Breakeven Calculator for MV Straddle
Calculates breakeven points, profit zones, and P&L at various prices
"""
import logging
from typing import Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class BreakevenCalculator:
    """Calculate breakeven and P&L for straddle strategies"""
    
    def calculate_pnl_curve(
        self,
        legs: List[Dict],
        price_range: Tuple[float, float] = None,
        num_points: int = 100
    ) -> Dict:
        """
        Calculate P&L curve across price range
        
        Args:
            legs: List of strategy legs
            price_range: (min_price, max_price) or None for auto
            num_points: Number of points to calculate
        
        Returns:
            {
                "prices": [95000, 96000, ...],
                "pnl": [-500, -400, ...],
                "breakeven_points": [92000, 108000],
                "max_profit_price": 100000 or None,
                "max_loss_price": 100000
            }
        """
        try:
            if len(legs) != 2:
                return {"error": "Straddle must have exactly 2 legs"}
            
            # Extract straddle parameters
            strike = legs[0]["strike"]
            call_premium = legs[0]["current_price"] if legs[0]["option_type"] == "call" else legs[1]["current_price"]
            put_premium = legs[1]["current_price"] if legs[1]["option_type"] == "put" else legs[0]["current_price"]
            
            # Get quantity and direction
            quantity = abs(legs[0]["quantity"])
            direction = legs[0]["side"]  # "buy" or "sell"
            
            # Total premium
            total_premium = (call_premium + put_premium) * quantity
            
            # Determine price range
            if price_range is None:
                # Auto range: ±30% from strike
                min_price = strike * 0.7
                max_price = strike * 1.3
            else:
                min_price, max_price = price_range
            
            # Generate price points
            prices = np.linspace(min_price, max_price, num_points)
            pnl_values = []
            
            # Calculate P&L at each price
            for price in prices:
                pnl = self._calculate_pnl_at_price(
                    price=float(price),
                    strike=strike,
                    total_premium=total_premium,
                    direction=direction,
                    quantity=quantity
                )
                pnl_values.append(pnl)
            
            # Find breakeven points
            breakeven_points = self._find_breakeven_points(prices, pnl_values)
            
            # Find max profit/loss prices
            max_pnl_idx = np.argmax(pnl_values)
            min_pnl_idx = np.argmin(pnl_values)
            
            max_profit_price = float(prices[max_pnl_idx]) if direction == "sell" else None
            max_loss_price = float(prices[min_pnl_idx]) if direction == "buy" else float(prices[max_pnl_idx])
            
            return {
                "prices": [float(p) for p in prices],
                "pnl": [float(p) for p in pnl_values],
                "breakeven_points": breakeven_points,
                "max_profit_price": max_profit_price,
                "max_loss_price": max_loss_price,
                "total_premium": total_premium,
                "strike": strike
            }
            
        except Exception as e:
            logger.error(f"Error calculating P&L curve: {e}")
            return {"error": str(e)}
    
    def _calculate_pnl_at_price(
        self,
        price: float,
        strike: float,
        total_premium: float,
        direction: str,
        quantity: int
    ) -> float:
        """
        Calculate P&L at a specific price at expiry
        
        For Long Straddle (buy both):
        - P&L = max(price - strike, 0) + max(strike - price, 0) - total_premium
        - Simplified: P&L = abs(price - strike) - total_premium
        
        For Short Straddle (sell both):
        - P&L = total_premium - max(price - strike, 0) - max(strike - price, 0)
        - Simplified: P&L = total_premium - abs(price - strike)
        """
        intrinsic_value = abs(price - strike) * quantity
        
        if direction == "buy":
            # Long straddle: profit from large moves
            pnl = intrinsic_value - total_premium
        else:
            # Short straddle: profit from small moves
            pnl = total_premium - intrinsic_value
        
        return pnl
    
    def _find_breakeven_points(self, prices: np.ndarray, pnl_values: List[float]) -> List[float]:
        """
        Find prices where P&L crosses zero
        
        Returns:
            List of breakeven prices [lower, upper]
        """
        breakeven_points = []
        
        # Find sign changes in P&L
        for i in range(len(pnl_values) - 1):
            if (pnl_values[i] <= 0 and pnl_values[i + 1] > 0) or \
               (pnl_values[i] >= 0 and pnl_values[i + 1] < 0):
                # Interpolate to find exact breakeven price
                price1, price2 = prices[i], prices[i + 1]
                pnl1, pnl2 = pnl_values[i], pnl_values[i + 1]
                
                # Linear interpolation
                breakeven_price = price1 + (0 - pnl1) * (price2 - price1) / (pnl2 - pnl1)
                breakeven_points.append(float(breakeven_price))
        
        # Sort breakeven points
        breakeven_points.sort()
        
        return breakeven_points
    
    def calculate_breakeven_simple(
        self,
        strike: float,
        total_premium: float,
        direction: str
    ) -> Dict:
        """
        Simple breakeven calculation without full curve
        
        For Long Straddle:
        - Lower breakeven = strike - total_premium
        - Upper breakeven = strike + total_premium
        
        For Short Straddle:
        - Same formula (where P&L becomes zero)
        
        Args:
            strike: Strike price
            total_premium: Total premium paid/received
            direction: "buy" or "sell"
        
        Returns:
            {
                'breakeven_lower': float,
                'breakeven_upper': float,
                'breakeven_range': float (width of profit zone)
            }
        """
        breakeven_lower = strike - total_premium
        breakeven_upper = strike + total_premium
        breakeven_range = breakeven_upper - breakeven_lower
        
        return {
            'breakeven_lower': round(breakeven_lower, 2),
            'breakeven_upper': round(breakeven_upper, 2),
            'breakeven_range': round(breakeven_range, 2),
            'breakeven_points': [breakeven_lower, breakeven_upper]
        }
    
    def calculate_max_profit_loss(
        self,
        total_premium: float,
        direction: str
    ) -> Dict:
        """
        Calculate theoretical max profit and loss
        
        For Long Straddle:
        - Max loss: total premium paid (at strike)
        - Max profit: unlimited
        
        For Short Straddle:
        - Max profit: total premium received (at strike)
        - Max loss: unlimited
        
        Args:
            total_premium: Total premium paid/received
            direction: "buy" or "sell"
        
        Returns:
            {
                'max_profit': float or 'Unlimited',
                'max_loss': float or 'Unlimited',
                'risk_reward_ratio': str
            }
        """
        if direction == "buy":
            max_profit = "Unlimited"
            max_loss = total_premium
            risk_reward = "Unlimited upside / Limited downside"
        else:
            max_profit = total_premium
            max_loss = "Unlimited"
            risk_reward = "Limited upside / Unlimited downside"
        
        return {
            'max_profit': max_profit,
            'max_loss': max_loss,
            'risk_reward_ratio': risk_reward
        }
