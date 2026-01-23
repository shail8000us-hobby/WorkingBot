"""
Complete Greeks Calculator

First-order and second-order Greeks for comprehensive risk management

Created: January 23, 2026
Part of: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md Phase 1
"""

import math
from scipy.stats import norm
from typing import Dict, List, Optional


class GreeksCalculator:
    """
    Complete Greeks calculation for risk management
    """
    
    @staticmethod
    def calculate_all_greeks(
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        option_type: str
    ) -> Dict[str, float]:
        """
        Calculate all Greeks at once for efficiency
        
        Returns first and second-order Greeks
        """
        if time_to_expiry <= 0:
            return GreeksCalculator._expiry_greeks(spot, strike, option_type)
        
        if volatility <= 0 or spot <= 0 or strike <= 0:
            return GreeksCalculator._zero_greeks()
        
        sqrt_t = math.sqrt(time_to_expiry)
        d1 = (math.log(spot / strike) + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t
        
        pdf_d1 = norm.pdf(d1)
        cdf_d1 = norm.cdf(d1)
        cdf_d2 = norm.cdf(d2)
        
        discount_factor = math.exp(-dividend_yield * time_to_expiry)
        
        # First-order Greeks
        if option_type.lower() == 'call':
            delta = discount_factor * cdf_d1
            rho = strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * cdf_d2 / 100
        else:
            delta = -discount_factor * norm.cdf(-d1)
            rho = -strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
        
        gamma = (pdf_d1 * discount_factor) / (spot * volatility * sqrt_t)
        vega = spot * discount_factor * pdf_d1 * sqrt_t / 100
        
        # Theta (per day)
        theta_part1 = -(spot * pdf_d1 * volatility * discount_factor) / (2 * sqrt_t)
        if option_type.lower() == 'call':
            theta_part2 = dividend_yield * spot * cdf_d1 * discount_factor
            theta_part3 = -risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * cdf_d2
        else:
            theta_part2 = -dividend_yield * spot * norm.cdf(-d1) * discount_factor
            theta_part3 = risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
        theta = (theta_part1 + theta_part2 + theta_part3) / 365
        
        # Second-order Greeks
        vanna = (vega / spot) * (1 - d1 / (volatility * sqrt_t))
        charm = -discount_factor * pdf_d1 * (
            2 * (risk_free_rate - dividend_yield) * time_to_expiry - d2 * volatility * sqrt_t
        ) / (2 * time_to_expiry * volatility * sqrt_t) / 365
        
        vomma = (vega * d1 * d2) / volatility
        
        return {
            # First-order
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho,
            # Second-order
            'vanna': vanna,
            'charm': charm,
            'vomma': vomma,
            # Useful metrics
            'lambda': delta * spot / (spot * delta),  # Leverage
            'delta_decay_per_day': charm
        }
    
    @staticmethod
    def calculate_portfolio_greeks(positions: List[Dict]) -> Dict[str, float]:
        """
        Aggregate Greeks across all positions
        
        Returns portfolio-level Greeks with dollar-denominated versions
        """
        portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'vanna': 0.0,
            'charm': 0.0,
            'vomma': 0.0,
            'dollar_delta': 0.0,
            'dollar_gamma': 0.0,
            'dollar_theta': 0.0,
            'dollar_vega': 0.0
        }
        
        for pos in positions:
            if 'greeks' not in pos:
                continue
            
            greeks = pos['greeks']
            quantity = pos.get('quantity', pos.get('size', 1))
            multiplier = pos.get('multiplier', 0.001)  # BTC/ETH default
            spot_price = pos.get('spot_price', 0)
            
            # Aggregate standard Greeks
            for greek in ['delta', 'gamma', 'theta', 'vega', 'rho', 'vanna', 'charm', 'vomma']:
                if greek in greeks:
                    portfolio_greeks[greek] += greeks[greek] * quantity
            
            # Calculate dollar Greeks
            portfolio_greeks['dollar_delta'] += greeks.get('delta', 0) * quantity * spot_price * multiplier
            portfolio_greeks['dollar_gamma'] += greeks.get('gamma', 0) * quantity * spot_price ** 2 * multiplier / 100
            portfolio_greeks['dollar_theta'] += greeks.get('theta', 0) * quantity * multiplier
            portfolio_greeks['dollar_vega'] += greeks.get('vega', 0) * quantity * multiplier
        
        return portfolio_greeks
    
    @staticmethod
    def _expiry_greeks(spot: float, strike: float, option_type: str) -> Dict[str, float]:
        """Greeks at expiry"""
        if option_type.lower() == 'call':
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0
        
        return {
            'delta': delta,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'vanna': 0.0,
            'charm': 0.0,
            'vomma': 0.0,
            'lambda': 0.0,
            'delta_decay_per_day': 0.0
        }
    
    @staticmethod
    def _zero_greeks() -> Dict[str, float]:
        """Return zero Greeks for invalid inputs"""
        return {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'vanna': 0.0,
            'charm': 0.0,
            'vomma': 0.0,
            'lambda': 0.0,
            'delta_decay_per_day': 0.0
        }
