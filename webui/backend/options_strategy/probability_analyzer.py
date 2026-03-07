"""
Probability Analysis Module

Calculate probability-based risk metrics:
- Probability of Profit (PoP)
- Expected Value
- Value-at-Risk (VaR)
- Monte Carlo simulations

Created: January 23, 2026
Part of: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md Phase 2
"""

import numpy as np
from scipy.stats import norm, lognorm
from typing import Dict, List, Tuple
import math
from webui.backend.sealed import sealed


class ProbabilityAnalyzer:
    """
    Calculate probability-based risk metrics for options strategies
    """
    
    @staticmethod
    @sealed
    def probability_of_profit(
        positions: List[Dict],
        spot_price: float,
        volatility: float,
        time_to_expiry: float,
        risk_free_rate: float = 0.0,
        distribution: str = 'lognormal'
    ) -> Dict:
        """
        Calculate probability that strategy is profitable at expiry.

        SEALED — v1.0.0 — March 4, 2026
        Do not modify without UNSEAL command in AI_SEAL.md

        Returns: {
            'pop': float (0-1),
            'expected_value': float,
            'value_at_risk_95': float,
            'conditional_var_95': float,
            'profit_ranges': list
        }
        """
        if time_to_expiry <= 0:
            # At expiry, PoP is either 0 or 1
            current_pnl = ProbabilityAnalyzer._calculate_current_pnl(positions, spot_price)
            return {
                'pop': 1.0 if current_pnl > 0 else 0.0,
                'expected_value': current_pnl,
                'value_at_risk_95': current_pnl,
                'conditional_var_95': current_pnl,
                'profit_ranges': []
            }
        
        # Find breakeven points
        breakevens = ProbabilityAnalyzer._find_breakeven_points(positions, spot_price)
        
        # Calculate probability using lognormal distribution
        if distribution == 'lognormal':
            # Parameters for lognormal distribution
            mu = math.log(spot_price) + (risk_free_rate - 0.5 * volatility ** 2) * time_to_expiry
            sigma = volatility * math.sqrt(time_to_expiry)
            
            # Calculate PoP by integrating over profitable regions
            pop = 0.0
            for i in range(len(breakevens) - 1):
                lower = breakevens[i]
                upper = breakevens[i + 1]
                
                # Check if middle price is profitable
                mid_price = (lower + upper) / 2
                mid_pnl = ProbabilityAnalyzer._calculate_payoff_at_price(positions, mid_price, 0)
                
                if mid_pnl > 0:
                    # This range is profitable
                    prob_range = lognorm.cdf(upper, s=sigma, scale=math.exp(mu)) - \
                                lognorm.cdf(lower, s=sigma, scale=math.exp(mu))
                    pop += prob_range
        
        # Calculate expected value using numerical integration
        num_points = 1000
        price_range = np.linspace(spot_price * 0.5, spot_price * 1.5, num_points)
        payoffs = np.array([
            ProbabilityAnalyzer._calculate_payoff_at_price(positions, p, 0) 
            for p in price_range
        ])
        
        # Probability density for each price
        mu = math.log(spot_price) + (risk_free_rate - 0.5 * volatility ** 2) * time_to_expiry
        sigma = volatility * math.sqrt(time_to_expiry)
        pdf_values = lognorm.pdf(price_range, s=sigma, scale=math.exp(mu))
        
        # Expected value = integral of (payoff * probability)
        expected_value = np.trapz(payoffs * pdf_values, price_range)
        
        # Calculate VaR (Value at Risk) at 95% confidence
        # VaR is the loss exceeded with only 5% probability
        cumulative_prob = np.cumsum(pdf_values * np.gradient(price_range))
        cumulative_prob /= cumulative_prob[-1]  # Normalize
        
        var_95_idx = np.searchsorted(cumulative_prob, 0.05)
        var_95_price = price_range[var_95_idx]
        var_95 = ProbabilityAnalyzer._calculate_payoff_at_price(positions, var_95_price, 0)
        
        # Conditional VaR (CVaR) - expected loss given VaR is exceeded
        tail_payoffs = payoffs[:var_95_idx]
        tail_probs = pdf_values[:var_95_idx]
        if len(tail_payoffs) > 0 and np.sum(tail_probs) > 0:
            cvar_95 = np.average(tail_payoffs, weights=tail_probs)
        else:
            cvar_95 = var_95
        
        return {
            'pop': float(pop),
            'expected_value': float(expected_value),
            'value_at_risk_95': float(var_95),
            'conditional_var_95': float(cvar_95),
            'breakeven_points': breakevens,
            'profit_ranges': ProbabilityAnalyzer._identify_profit_ranges(positions, breakevens)
        }
    
    @staticmethod
    def monte_carlo_simulation(
        positions: List[Dict],
        spot_price: float,
        volatility: float,
        time_to_expiry: float,
        risk_free_rate: float = 0.0,
        num_simulations: int = 10000
    ) -> Dict:
        """
        Monte Carlo simulation for complex strategies
        
        Returns: {
            'final_prices': list,
            'final_pnls': list,
            'percentiles': dict,
            'histogram': dict,
            'pop': float
        }
        """
        if time_to_expiry <= 0:
            current_pnl = ProbabilityAnalyzer._calculate_current_pnl(positions, spot_price)
            return {
                'final_prices': [spot_price],
                'final_pnls': [current_pnl],
                'percentiles': {p: current_pnl for p in [5, 25, 50, 75, 95]},
                'histogram': {'bins': [current_pnl], 'frequencies': [1]},
                'pop': 1.0 if current_pnl > 0 else 0.0
            }
        
        # Generate random price paths using Geometric Brownian Motion
        np.random.seed(42)
        z = np.random.standard_normal(num_simulations)
        
        mu = (risk_free_rate - 0.5 * volatility ** 2) * time_to_expiry
        sigma = volatility * math.sqrt(time_to_expiry)
        final_prices = spot_price * np.exp(mu + sigma * z)
        
        # Calculate P&L for each simulation
        final_pnls = np.array([
            ProbabilityAnalyzer._calculate_payoff_at_price(positions, price, 0)
            for price in final_prices
        ])
        
        # Calculate percentiles
        percentiles = {
            'p5': float(np.percentile(final_pnls, 5)),
            'p25': float(np.percentile(final_pnls, 25)),
            'p50': float(np.percentile(final_pnls, 50)),
            'p75': float(np.percentile(final_pnls, 75)),
            'p95': float(np.percentile(final_pnls, 95))
        }
        
        # Create histogram
        hist, bins = np.histogram(final_pnls, bins=50)
        histogram = {
            'bins': bins.tolist(),
            'frequencies': hist.tolist()
        }
        
        # Calculate PoP
        pop = float(np.sum(final_pnls > 0) / num_simulations)
        
        return {
            'final_prices': final_prices.tolist()[:100],  # Return first 100 for visualization
            'final_pnls': final_pnls.tolist()[:100],
            'percentiles': percentiles,
            'histogram': histogram,
            'pop': pop,
            'mean_pnl': float(np.mean(final_pnls)),
            'std_pnl': float(np.std(final_pnls))
        }
    
    @staticmethod
    def _calculate_payoff_at_price(positions: List[Dict], price: float, time_to_expiry: float) -> float:
        """Calculate total P&L at a specific price and time"""
        total_pnl = 0.0
        
        for pos in positions:
            if 'strike' in pos:  # Options
                strike = pos['strike']
                is_call = pos.get('option_type', 'call').lower() == 'call'
                is_buy = pos.get('side', 'buy').lower() == 'buy'
                quantity = pos.get('quantity', pos.get('size', 1))
                entry_price = pos.get('entry_price', pos.get('premium', 0))
                
                # At expiry, use intrinsic value
                if time_to_expiry <= 0:
                    if is_call:
                        value = max(0, price - strike)
                    else:
                        value = max(0, strike - price)
                else:
                    # Would need pricing model for time > 0
                    # For now, use intrinsic value
                    if is_call:
                        value = max(0, price - strike)
                    else:
                        value = max(0, strike - price)
                
                # Contract multiplier (e.g., 0.001 for BTC/ETH)
                multiplier = 0.001
                
                if is_buy:
                    pnl = (value - entry_price) * quantity * multiplier
                else:
                    pnl = (entry_price - value) * quantity * multiplier
                
                total_pnl += pnl
            else:  # Futures
                # Simple linear P&L for futures
                entry = pos.get('entry_price', 0)
                size = pos.get('size', 0)
                pnl = (price - entry) * size
                total_pnl += pnl
        
        return total_pnl
    
    @staticmethod
    def _calculate_current_pnl(positions: List[Dict], spot_price: float) -> float:
        """Calculate current P&L"""
        return ProbabilityAnalyzer._calculate_payoff_at_price(positions, spot_price, 0)
    
    @staticmethod
    def _find_breakeven_points(positions: List[Dict], spot_price: float) -> List[float]:
        """Find prices where P&L = 0"""
        # Sample prices around current spot
        price_range = np.linspace(spot_price * 0.3, spot_price * 1.7, 1000)
        pnls = np.array([
            ProbabilityAnalyzer._calculate_payoff_at_price(positions, p, 0)
            for p in price_range
        ])
        
        # Find zero crossings
        breakevens = [spot_price * 0.3]  # Start with lower bound
        for i in range(len(pnls) - 1):
            if pnls[i] * pnls[i + 1] < 0:  # Sign change = zero crossing
                # Linear interpolation for more accurate breakeven
                be = price_range[i] + (price_range[i + 1] - price_range[i]) * \
                     (-pnls[i] / (pnls[i + 1] - pnls[i]))
                breakevens.append(be)
        
        breakevens.append(spot_price * 1.7)  # End with upper bound
        return breakevens
    
    @staticmethod
    def _identify_profit_ranges(positions: List[Dict], breakevens: List[float]) -> List[Dict]:
        """Identify price ranges where strategy is profitable"""
        profit_ranges = []
        
        for i in range(len(breakevens) - 1):
            lower = breakevens[i]
            upper = breakevens[i + 1]
            mid_price = (lower + upper) / 2
            mid_pnl = ProbabilityAnalyzer._calculate_payoff_at_price(positions, mid_price, 0)
            
            if mid_pnl > 0:
                profit_ranges.append({
                    'price_range': (lower, upper),
                    'profit': mid_pnl
                })
        
        return profit_ranges
