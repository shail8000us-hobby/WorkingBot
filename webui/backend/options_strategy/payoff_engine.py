"""
Payoff Engine - Single Source of Truth for Options Payoff Calculations
========================================================================
Created: January 23, 2026 (Day 2 - Phase 1)
Purpose: Consolidate all payoff calculation logic in one place

Features:
- Black-Scholes option pricing
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Payoff calculation for single and multi-leg strategies
- Probability of Profit (PoP) calculation
- Price distribution generation
- API endpoint for frontend consumption

Standards:
- Risk-free rate: 0% (crypto standard)
- Dividend yield: 0% (crypto has no dividends)
- Contract multiplier: 0.001 for BTC, 0.01 for ETH
- European options only (no early exercise)
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

log = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS - Delta Exchange India Specifications
# ============================================================================

class ContractMultiplier:
    """Contract multipliers for different assets"""
    BTC = 0.001
    ETH = 0.01   # 1 lot = 0.01 ETH
    
    @classmethod
    def get(cls, symbol: str) -> float:
        """Get multiplier for a symbol"""
        symbol_upper = symbol.upper()
        if 'BTC' in symbol_upper:
            return cls.BTC
        elif 'ETH' in symbol_upper:
            return cls.ETH
        return 0.001  # Default


RISK_FREE_RATE = 0.0  # 0% for crypto (not 5% like stocks)
DIVIDEND_YIELD = 0.0  # Crypto has no dividends
MIN_VOLATILITY = 0.05  # 5% minimum IV
MAX_VOLATILITY = 5.0   # 500% maximum IV


class OptionType(str, Enum):
    """Option types"""
    CALL = "call"
    PUT = "put"


class PositionSide(str, Enum):
    """Position side"""
    BUY = "buy"
    SELL = "sell"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class OptionLeg:
    """Single option leg in a strategy"""
    option_type: str  # 'call' or 'put'
    strike: float
    quantity: int
    side: str  # 'buy' or 'sell'
    premium: float  # Entry price (premium paid/received)
    iv: Optional[float] = None  # Implied volatility
    symbol: Optional[str] = None
    expiry_date: Optional[str] = None


@dataclass
class Greeks:
    """Option Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


@dataclass
class PayoffPoint:
    """Single point on payoff curve"""
    price: float
    pnl_expiry: float
    pnl_current: float
    probability: float = 0.0


# ============================================================================
# STATISTICAL FUNCTIONS
# ============================================================================

def normal_cdf(x: float) -> float:
    """
    Cumulative distribution function for standard normal distribution
    Using Abramowitz and Stegun approximation
    """
    if x == 0:
        return 0.5
    
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    
    sign = 1 if x >= 0 else -1
    abs_x = abs(x)
    t = 1.0 / (1.0 + p * abs_x)
    
    y = 1.0 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * math.exp(-abs_x * abs_x / 2)
    
    return 0.5 * (1 + sign * y)


def normal_pdf(x: float) -> float:
    """Probability density function for standard normal distribution"""
    return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x)


# ============================================================================
# BLACK-SCHOLES MODEL
# ============================================================================

def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str,
    risk_free_rate: float = RISK_FREE_RATE,
    dividend_yield: float = DIVIDEND_YIELD
) -> float:
    """
    Calculate Black-Scholes option price
    
    Args:
        spot: Current spot price
        strike: Strike price
        time_to_expiry: Time to expiry in years
        volatility: Implied volatility (e.g., 0.8 for 80%)
        option_type: 'call' or 'put'
        risk_free_rate: Risk-free interest rate (default 0% for crypto)
        dividend_yield: Dividend yield (default 0% for crypto)
    
    Returns:
        Option price
    """
    if time_to_expiry <= 0:
        # At expiry, intrinsic value only
        if option_type.lower() == 'call':
            return max(0, spot - strike)
        else:
            return max(0, strike - spot)
    
    # Clamp volatility to reasonable range
    volatility = max(MIN_VOLATILITY, min(MAX_VOLATILITY, volatility))
    
    # Calculate d1 and d2
    d1 = (math.log(spot / strike) + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
    d2 = d1 - volatility * math.sqrt(time_to_expiry)
    
    if option_type.lower() == 'call':
        price = spot * math.exp(-dividend_yield * time_to_expiry) * normal_cdf(d1) - strike * math.exp(-risk_free_rate * time_to_expiry) * normal_cdf(d2)
    else:
        price = strike * math.exp(-risk_free_rate * time_to_expiry) * normal_cdf(-d2) - spot * math.exp(-dividend_yield * time_to_expiry) * normal_cdf(-d1)
    
    return max(0, price)


def calculate_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str,
    risk_free_rate: float = RISK_FREE_RATE,
    dividend_yield: float = DIVIDEND_YIELD
) -> Greeks:
    """
    Calculate all Greeks for an option
    
    Returns:
        Greeks object with delta, gamma, theta, vega, rho
    """
    if time_to_expiry <= 0:
        # At expiry, no Greeks (or infinity)
        return Greeks(delta=0, gamma=0, theta=0, vega=0, rho=0)
    
    # Clamp volatility
    volatility = max(MIN_VOLATILITY, min(MAX_VOLATILITY, volatility))
    
    # Calculate d1 and d2
    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (math.log(spot / strike) + (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    
    # Delta
    if option_type.lower() == 'call':
        delta = math.exp(-dividend_yield * time_to_expiry) * normal_cdf(d1)
    else:
        delta = math.exp(-dividend_yield * time_to_expiry) * (normal_cdf(d1) - 1)
    
    # Gamma (same for call and put)
    gamma = (math.exp(-dividend_yield * time_to_expiry) * normal_pdf(d1)) / (spot * volatility * sqrt_t)
    
    # Theta
    term1 = -(spot * normal_pdf(d1) * volatility * math.exp(-dividend_yield * time_to_expiry)) / (2 * sqrt_t)
    if option_type.lower() == 'call':
        term2 = risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * normal_cdf(d2)
        term3 = -dividend_yield * spot * math.exp(-dividend_yield * time_to_expiry) * normal_cdf(d1)
        theta = (term1 + term2 + term3) / 365  # Convert to daily theta
    else:
        term2 = -risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * normal_cdf(-d2)
        term3 = dividend_yield * spot * math.exp(-dividend_yield * time_to_expiry) * normal_cdf(-d1)
        theta = (term1 + term2 + term3) / 365  # Convert to daily theta
    
    # Vega (same for call and put)
    vega = (spot * math.exp(-dividend_yield * time_to_expiry) * normal_pdf(d1) * sqrt_t) / 100  # Per 1% change in IV
    
    # Rho
    if option_type.lower() == 'call':
        rho = (strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * normal_cdf(d2)) / 100  # Per 1% change in rate
    else:
        rho = -(strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * normal_cdf(-d2)) / 100
    
    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


# ============================================================================
# PROBABILITY CALCULATIONS
# ============================================================================

def calculate_probability_of_profit(
    spot: float,
    strike: float,
    entry_price: float,
    time_to_expiry: float,
    volatility: float,
    option_type: str,
    side: str
) -> float:
    """
    Calculate Probability of Profit (PoP) for a single option position
    
    Args:
        spot: Current spot price
        strike: Strike price
        entry_price: Premium paid/received
        time_to_expiry: Time to expiry in years
        volatility: Implied volatility
        option_type: 'call' or 'put'
        side: 'buy' or 'sell'
    
    Returns:
        Probability (0-1) that position will be profitable at expiry
    """
    if time_to_expiry <= 0:
        return 0.0
    
    # Clamp volatility
    volatility = max(MIN_VOLATILITY, min(MAX_VOLATILITY, volatility))
    
    # Calculate breakeven price
    if option_type.lower() == 'call':
        if side.lower() == 'buy':
            breakeven = strike + entry_price
        else:  # sell
            breakeven = strike + entry_price
    else:  # put
        if side.lower() == 'buy':
            breakeven = strike - entry_price
        else:  # sell
            breakeven = strike - entry_price
    
    # Calculate d2 (probability ITM in risk-neutral measure)
    sqrt_t = math.sqrt(time_to_expiry)
    d2 = (math.log(spot / breakeven) + (RISK_FREE_RATE - DIVIDEND_YIELD - 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
    
    # Probability depends on option type and side
    if option_type.lower() == 'call':
        if side.lower() == 'buy':
            prob = normal_cdf(d2)  # Prob price > breakeven
        else:  # sell
            prob = normal_cdf(-d2)  # Prob price < breakeven
    else:  # put
        if side.lower() == 'buy':
            prob = normal_cdf(-d2)  # Prob price < breakeven
        else:  # sell
            prob = normal_cdf(d2)  # Prob price > breakeven
    
    return prob


def calculate_price_distribution(
    spot: float,
    volatility: float,
    time_to_expiry: float,
    num_points: int = 100,
    price_range_pct: float = 0.25
) -> List[Dict]:
    """
    Calculate lognormal price distribution at expiry
    
    Returns list of {price, probability} dicts
    """
    if time_to_expiry <= 0:
        return [{'price': spot, 'probability': 100.0}]
    
    # Clamp volatility
    volatility = max(MIN_VOLATILITY, min(MAX_VOLATILITY, volatility))
    
    # Calculate price range
    min_price = spot * (1 - price_range_pct)
    max_price = spot * (1 + price_range_pct)
    price_step = (max_price - min_price) / num_points
    
    distribution = []
    
    # Parameters for lognormal distribution
    mu = math.log(spot) + (RISK_FREE_RATE - DIVIDEND_YIELD - 0.5 * volatility ** 2) * time_to_expiry
    sigma = volatility * math.sqrt(time_to_expiry)
    
    # Calculate probability density at each price
    for i in range(num_points + 1):
        price = min_price + i * price_step
        if price <= 0:
            continue
        
        # Lognormal PDF
        z = (math.log(price) - mu) / sigma
        pdf = (1 / (price * sigma * math.sqrt(2 * math.pi))) * math.exp(-0.5 * z * z)
        
        # Convert to percentage (normalize to 0-100%)
        probability_pct = pdf * 100 * price_step  # Approximate integral
        
        distribution.append({
            'price': price,
            'probability': probability_pct
        })
    
    # Normalize to sum to 100%
    total_prob = sum(p['probability'] for p in distribution)
    if total_prob > 0:
        for p in distribution:
            p['probability'] = (p['probability'] / total_prob) * 100
    
    return distribution


# ============================================================================
# PAYOFF CALCULATIONS
# ============================================================================

def calculate_single_leg_payoff(
    leg: OptionLeg,
    price_points: List[float],
    spot: float,
    current_time_to_expiry: float,
    expiry_time_to_expiry: float = 0.0
) -> List[PayoffPoint]:
    """
    Calculate payoff for a single option leg at various price points
    
    Args:
        leg: Option leg details
        price_points: List of price points to calculate payoff at
        spot: Current spot price
        current_time_to_expiry: Time to expiry for current P&L calculation
        expiry_time_to_expiry: Time to expiry at expiry (usually 0)
    
    Returns:
        List of PayoffPoint objects
    """
    payoff_points = []
    contract_multiplier = ContractMultiplier.get(leg.symbol or 'BTC')
    
    for price in price_points:
        # Payoff at expiry (intrinsic value only)
        if leg.option_type.lower() == 'call':
            intrinsic = max(0, price - leg.strike)
        else:
            intrinsic = max(0, leg.strike - price)
        
        # Sign: buy = +1, sell = -1
        sign = 1 if leg.side.lower() == 'buy' else -1
        
        # P&L at expiry = (intrinsic - premium) * sign * quantity * multiplier
        pnl_expiry = (intrinsic - leg.premium) * sign * leg.quantity * contract_multiplier
        
        # Current P&L (if not at expiry, includes time value)
        if current_time_to_expiry > 0 and leg.iv:
            current_price = black_scholes_price(
                price, leg.strike, current_time_to_expiry, leg.iv, leg.option_type
            )
            pnl_current = (current_price - leg.premium) * sign * leg.quantity * contract_multiplier
        else:
            pnl_current = pnl_expiry
        
        payoff_points.append(PayoffPoint(
            price=price,
            pnl_expiry=pnl_expiry,
            pnl_current=pnl_current
        ))
    
    return payoff_points


def calculate_strategy_payoff(
    legs: List[OptionLeg],
    spot: float,
    price_range_pct: float = 0.25,
    num_points: int = 200,
    current_time_to_expiry: Optional[float] = None
) -> Dict:
    """
    Calculate payoff for multi-leg strategy
    
    Args:
        legs: List of option legs
        spot: Current spot price
        price_range_pct: Price range as percentage of spot (e.g., 0.25 = ±25%)
        num_points: Number of points to calculate
        current_time_to_expiry: Time to expiry for current P&L (None = use leg's time)
    
    Returns:
        Dict with payoff data, statistics, and breakeven points
    """
    if not legs:
        return {
            'error': 'No legs provided',
            'price_points': [],
            'payoff_values_expiry': [],
            'payoff_values_current': []
        }
    
    # Generate price points
    min_price = spot * (1 - price_range_pct)
    max_price = spot * (1 + price_range_pct)
    price_step = (max_price - min_price) / num_points
    price_points = [min_price + i * price_step for i in range(num_points + 1)]
    
    # Calculate payoff for each leg
    payoff_expiry = [0.0] * len(price_points)
    payoff_current = [0.0] * len(price_points)
    
    for leg in legs:
        # Use current_time_to_expiry if provided, otherwise estimate from leg
        if current_time_to_expiry is None:
            # Estimate from leg (simplified - should be passed properly)
            leg_tte = 0.1  # Default 0.1 years (about 36 days)
        else:
            leg_tte = current_time_to_expiry
        
        leg_payoff = calculate_single_leg_payoff(
            leg, price_points, spot, leg_tte, expiry_time_to_expiry=0.0
        )
        
        for i, point in enumerate(leg_payoff):
            payoff_expiry[i] += point.pnl_expiry
            payoff_current[i] += point.pnl_current
    
    # Find max profit/loss
    max_profit = max(payoff_expiry)
    max_loss = min(payoff_expiry)
    
    # Find breakeven points
    breakeven_points = []
    for i in range(1, len(payoff_expiry)):
        prev = payoff_expiry[i - 1]
        curr = payoff_expiry[i]
        if (prev <= 0 and curr >= 0) or (prev >= 0 and curr <= 0):
            # Linear interpolation for more precise breakeven
            if curr != prev:
                price_be = price_points[i - 1] + (0 - prev) * (price_points[i] - price_points[i - 1]) / (curr - prev)
                breakeven_points.append(price_be)
    
    return {
        'price_points': price_points,
        'payoff_values_expiry': payoff_expiry,
        'payoff_values_current': payoff_current,
        'max_profit': max_profit if abs(max_profit) < 1e6 else None,  # Cap unrealistic values
        'max_loss': max_loss if abs(max_loss) < 1e6 else None,
        'breakeven_points': breakeven_points,
        'current_price': spot
    }


# ============================================================================
# API INTERFACE FUNCTIONS
# ============================================================================

def calculate_payoff_api(
    legs: List[Dict],
    spot: float,
    price_range_pct: float = 0.25,
    num_points: int = 200,
    current_time_to_expiry: Optional[float] = None
) -> Dict:
    """
    API-friendly wrapper for payoff calculation
    
    Args:
        legs: List of leg dicts with keys: option_type, strike, quantity, side, premium, iv, symbol
        spot: Current spot price
        price_range_pct: Price range percentage
        num_points: Number of calculation points
        current_time_to_expiry: Time to expiry in years
    
    Returns:
        Payoff calculation results
    """
    try:
        # Convert dicts to OptionLeg objects
        option_legs = []
        for leg_dict in legs:
            option_legs.append(OptionLeg(
                option_type=leg_dict.get('option_type', 'call'),
                strike=float(leg_dict.get('strike', 0)),
                quantity=int(leg_dict.get('quantity', 1)),
                side=leg_dict.get('side', 'buy'),
                premium=float(leg_dict.get('premium', 0)),
                iv=float(leg_dict.get('iv', 0.8)) if leg_dict.get('iv') else None,
                symbol=leg_dict.get('symbol', 'BTC'),
                expiry_date=leg_dict.get('expiry_date')
            ))
        
        # Calculate payoff
        result = calculate_strategy_payoff(
            option_legs, spot, price_range_pct, num_points, current_time_to_expiry
        )
        
        result['success'] = True
        return result
        
    except Exception as e:
        log.error(f"Error calculating payoff: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# TESTING
# ============================================================================

if __name__ == '__main__':
    # Test with a simple call spread
    print("Testing Payoff Engine...")
    
    legs = [
        {
            'option_type': 'call',
            'strike': 100000,
            'quantity': 1,
            'side': 'buy',
            'premium': 2000,
            'iv': 0.8,
            'symbol': 'BTC'
        },
        {
            'option_type': 'call',
            'strike': 105000,
            'quantity': 1,
            'side': 'sell',
            'premium': 1000,
            'iv': 0.75,
            'symbol': 'BTC'
        }
    ]
    
    result = calculate_payoff_api(legs, spot=102000, num_points=50)
    
    if result.get('success'):
        print(f"✅ Payoff calculation successful!")
        print(f"Max Profit: ${result['max_profit']:.2f}")
        print(f"Max Loss: ${result['max_loss']:.2f}")
        print(f"Breakeven: {result['breakeven_points']}")
    else:
        print(f"❌ Error: {result.get('error')}")
