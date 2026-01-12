"""
Options Trading Helper Functions
Created: January 4, 2026
Purpose: Utility functions for options trading module

⚠️ COMPLETE SEPARATION FROM GRID BOT
This module is completely independent of grid bot logic.
"""

from datetime import datetime
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def calculate_unrealized_pnl(position: Dict, mid_price: float) -> float:
    """
    Calculate unrealized PnL for options position using mid price (bid+ask)/2.
    
    Args:
        position: Position dict with size, entry_price
        mid_price: Mid price calculated as (bid+ask)/2
        
    Returns:
        float: Unrealized PnL in USD
    """
    # Convert to float (API may return strings)
    size = float(position.get('size', 0))
    entry_price = float(position.get('entry_price', 0))
    mid_price = float(mid_price)
    contract_value = 0.001  # BTC contracts = 0.001 BTC each
    
    pnl = (mid_price - entry_price) * size * contract_value
    return pnl


def calculate_pnl_percentage(position: Dict, mid_price: float) -> float:
    """
    Calculate PnL percentage using mid price.
    
    Args:
        position: Position dict with entry_price
        mid_price: Mid price calculated as (bid+ask)/2
        
    Returns:
        float: PnL percentage
    """
    # Convert to float (API may return strings)
    entry_price = float(position.get('entry_price', 0))
    mid_price = float(mid_price)
    
    if entry_price == 0:
        return 0.0
    
    pnl_pct = ((mid_price - entry_price) / entry_price) * 100
    return pnl_pct


def check_expiry_warning(settlement_time: str) -> Dict:
    """
    Check if option is expiring soon.
    
    Args:
        settlement_time: ISO format timestamp (e.g., "2025-01-31T12:00:00Z")
        
    Returns:
        dict: {
            'is_expiring_soon': bool,
            'hours_until_expiry': float,
            'warning_level': str  # 'critical', 'warning', 'normal', 'expired'
        }
    """
    try:
        expiry = datetime.fromisoformat(settlement_time.replace('Z', '+00:00'))
        now = datetime.now(expiry.tzinfo)
        
        time_until_expiry = expiry - now
        hours_until_expiry = time_until_expiry.total_seconds() / 3600
        
        # Determine warning level
        if hours_until_expiry < 0:
            warning_level = 'expired'
        elif hours_until_expiry < 1:
            warning_level = 'critical'  # < 1 hour
        elif hours_until_expiry < 24:
            warning_level = 'warning'   # < 24 hours
        else:
            warning_level = 'normal'
        
        return {
            'is_expiring_soon': hours_until_expiry < 24 and hours_until_expiry > 0,
            'hours_until_expiry': hours_until_expiry,
            'warning_level': warning_level
        }
        
    except Exception as e:
        logger.error(f"Error checking expiry: {e}")
        return {
            'is_expiring_soon': False,
            'hours_until_expiry': 999,
            'warning_level': 'normal'
        }


def check_liquidity(ticker: Dict) -> Dict:
    """
    Check if option has sufficient liquidity.
    
    Args:
        ticker: Ticker dict with quotes and mark_price
        
    Returns:
        dict: {
            'is_liquid': bool,
            'spread_pct': float,
            'spread': float,
            'reason': str
        }
    """
    try:
        quotes = ticker.get('quotes', {})
        best_bid = float(quotes.get('best_bid', 0))
        best_ask = float(quotes.get('best_ask', 0))
        mark_price = float(ticker.get('mark_price', 0))
        
        if mark_price == 0:
            return {
                'is_liquid': False,
                'spread_pct': 999,
                'spread': 0,
                'reason': 'No mark price'
            }
        
        spread = best_ask - best_bid
        spread_pct = (spread / mark_price) * 100
        
        # Consider liquid if spread < 10%
        is_liquid = spread_pct < 10.0
        
        return {
            'is_liquid': is_liquid,
            'spread_pct': spread_pct,
            'spread': spread,
            'reason': f'Spread {spread_pct:.1f}%' if not is_liquid else 'OK'
        }
        
    except Exception as e:
        logger.error(f"Error checking liquidity: {e}")
        return {
            'is_liquid': False,
            'spread_pct': 999,
            'spread': 0,
            'reason': str(e)
        }


def determine_close_side(position_size: float) -> str:
    """
    Determine which side to use to close position.
    
    Args:
        position_size: Current position size (positive = long, negative = short)
        
    Returns:
        str: 'sell' for long positions, 'buy' for short positions
    """
    return 'sell' if position_size > 0 else 'buy'


def enrich_position_data(position: Dict, ticker: Dict) -> Dict:
    """
    Enrich position with real-time ticker data.
    
    Args:
        position: Position dict from API
        ticker: Ticker dict from API
        
    Returns:
        dict: Enriched position with mark price, PnL, Greeks, bid/ask, etc.
    """
    # Convert to float (API may return strings)
    mark_price = float(ticker.get('mark_price', 0))
    size = float(position.get('size', 0))
    spread_pct = float(ticker.get('spread_pct', 0))
    
    # Extract bid/ask from quotes
    quotes = ticker.get('quotes', {})
    if not quotes and 'raw' in ticker:
        quotes = ticker.get('raw', {}).get('quotes', {})
    
    best_bid = float(quotes.get('best_bid', 0))
    best_ask = float(quotes.get('best_ask', 0))
    
    # Calculate mid price (bid+ask)/2 for PnL calculation
    mid_price = (best_bid + best_ask) / 2.0 if (best_bid > 0 and best_ask > 0) else mark_price
    
    # Cashflow in USD = total premium paid/received
    # Formula: |contracts| * entry_price / 1000
    cashflow_usd = abs(size) * float(position.get('entry_price', 0)) / 1000.0
    
    enriched = position.copy()
    enriched.update({
        'mark_price': mark_price,
        'mid_price': mid_price,  # Add mid price for display
        'best_bid': best_bid,
        'best_ask': best_ask,
        'size': size,
        'entry_price': float(position.get('entry_price', 0)),
        'unrealized_pnl': calculate_unrealized_pnl(position, mid_price),
        'pnl_percentage': calculate_pnl_percentage(position, mid_price),
        'spread_pct': spread_pct,
        'is_liquid': spread_pct < 10.0 if spread_pct > 0 else True,
        'greeks': ticker.get('greeks', {}),
        'cashflow': cashflow_usd,  # Cashflow in USD
    })
    
    # Add expiry warning if settlement time exists
    if 'settlement_time' in position:
        enriched['expiry_warning'] = check_expiry_warning(position['settlement_time'])
    
    return enriched
