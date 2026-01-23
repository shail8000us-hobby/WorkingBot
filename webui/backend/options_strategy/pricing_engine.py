"""
Options Pricing Engine

Industry-standard option pricing with multiple models:
- Black-Scholes-Merton (with dividends)
- Binomial Tree (for American options)
- Monte Carlo (for complex strategies)

Created: January 23, 2026
Part of: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md Phase 1
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Optional
import math


class OptionPricingEngine:
    """
    Industry-standard option pricing with multiple models
    """
    
    @staticmethod
    def black_scholes_merton(
        spot: float,
        strike: float,
        time_to_expiry: float,  # in years
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        option_type: str
    ) -> Dict[str, float]:
        """
        Enhanced Black-Scholes with dividends and complete Greeks
        
        Returns: {
            'price': float,
            'delta': float,
            'gamma': float,
            'theta': float,
            'vega': float,
            'rho': float
        }
        """
        if time_to_expiry <= 0:
            # At expiry: return intrinsic value only
            intrinsic = max(0, spot - strike) if option_type == 'call' else max(0, strike - spot)
            return {
                'price': intrinsic,
                'delta': 1.0 if (option_type == 'call' and spot > strike) else 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
        
        if volatility <= 0 or spot <= 0 or strike <= 0:
            # Return intrinsic value for invalid inputs
            intrinsic = max(0, spot - strike) if option_type == 'call' else max(0, strike - spot)
            return {
                'price': intrinsic,
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
        
        sqrt_t = math.sqrt(time_to_expiry)
        d1 = (math.log(spot / strike) + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t
        
        # Calculate price
        if option_type == 'call':
            price = spot * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1) - \
                    strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
            delta = math.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
            rho = strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
        else:  # put
            price = strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - \
                    spot * math.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)
            delta = -math.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)
            rho = -strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
        
        # Calculate Greeks
        pdf_d1 = norm.pdf(d1)
        gamma = (pdf_d1 * math.exp(-dividend_yield * time_to_expiry)) / (spot * volatility * sqrt_t)
        vega = spot * math.exp(-dividend_yield * time_to_expiry) * pdf_d1 * sqrt_t / 100
        
        # Theta (per day)
        theta_part1 = -(spot * pdf_d1 * volatility * math.exp(-dividend_yield * time_to_expiry)) / (2 * sqrt_t)
        if option_type == 'call':
            theta_part2 = dividend_yield * spot * norm.cdf(d1) * math.exp(-dividend_yield * time_to_expiry)
            theta_part3 = -risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        else:
            theta_part2 = -dividend_yield * spot * norm.cdf(-d1) * math.exp(-dividend_yield * time_to_expiry)
            theta_part3 = risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
        
        theta = (theta_part1 + theta_part2 + theta_part3) / 365  # per day
        
        return {
            'price': price,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }
    
    @staticmethod
    def binomial_tree(
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        option_type: str,
        steps: int = 100,
        american: bool = True
    ) -> Dict[str, float]:
        """
        Cox-Ross-Rubinstein binomial tree for American options
        
        Handles early exercise premium
        """
        if time_to_expiry <= 0:
            intrinsic = max(0, spot - strike) if option_type == 'call' else max(0, strike - spot)
            return {'price': intrinsic, 'delta': 0.0}
        
        dt = time_to_expiry / steps
        u = math.exp(volatility * math.sqrt(dt))
        d = 1 / u
        p = (math.exp((risk_free_rate - dividend_yield) * dt) - d) / (u - d)
        discount = math.exp(-risk_free_rate * dt)
        
        # Initialize asset prices at maturity
        asset_prices = np.zeros(steps + 1)
        option_values = np.zeros(steps + 1)
        
        for i in range(steps + 1):
            asset_prices[i] = spot * (u ** (steps - i)) * (d ** i)
            if option_type == 'call':
                option_values[i] = max(0, asset_prices[i] - strike)
            else:
                option_values[i] = max(0, strike - asset_prices[i])
        
        # Backward induction
        for step in range(steps - 1, -1, -1):
            for i in range(step + 1):
                asset_price = spot * (u ** (step - i)) * (d ** i)
                option_values[i] = discount * (p * option_values[i] + (1 - p) * option_values[i + 1])
                
                if american:
                    # Check early exercise
                    if option_type == 'call':
                        intrinsic = max(0, asset_price - strike)
                    else:
                        intrinsic = max(0, strike - asset_price)
                    option_values[i] = max(option_values[i], intrinsic)
        
        # Calculate delta (from first two nodes)
        if steps > 0:
            up_price = spot * u
            down_price = spot * d
            delta = (option_values[0] - option_values[1]) / (up_price - down_price)
        else:
            delta = 0.0
        
        return {
            'price': option_values[0],
            'delta': delta
        }
    
    @staticmethod
    def monte_carlo(
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        option_type: str,
        num_simulations: int = 10000
    ) -> Dict[str, float]:
        """
        Monte Carlo simulation for option pricing
        
        Useful for exotic options and validation
        """
        if time_to_expiry <= 0:
            intrinsic = max(0, spot - strike) if option_type == 'call' else max(0, strike - spot)
            return {
                'price': intrinsic,
                'std_error': 0.0,
                'paths': []
            }
        
        # Generate random price paths
        np.random.seed(42)  # For reproducibility
        z = np.random.standard_normal(num_simulations)
        
        # Geometric Brownian Motion
        drift = (risk_free_rate - dividend_yield - 0.5 * volatility ** 2) * time_to_expiry
        diffusion = volatility * math.sqrt(time_to_expiry) * z
        final_prices = spot * np.exp(drift + diffusion)
        
        # Calculate payoffs
        if option_type == 'call':
            payoffs = np.maximum(final_prices - strike, 0)
        else:
            payoffs = np.maximum(strike - final_prices, 0)
        
        # Discount to present value
        option_price = math.exp(-risk_free_rate * time_to_expiry) * np.mean(payoffs)
        std_error = math.exp(-risk_free_rate * time_to_expiry) * np.std(payoffs) / math.sqrt(num_simulations)
        
        return {
            'price': option_price,
            'std_error': std_error,
            'final_prices': final_prices.tolist()[:100],  # Return first 100 for visualization
            'payoffs': payoffs.tolist()[:100]
        }
