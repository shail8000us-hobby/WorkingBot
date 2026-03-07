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
from webui.backend.sealed import sealed

logger = logging.getLogger(__name__)


@sealed
def get_contract_multiplier(symbol: str) -> float:
    """
    Return the USD contract multiplier for a given product symbol.
    Delta Exchange India specs (verified):
      BTC options/futures: 0.001 BTC per contract
      ETH options/futures: 0.001 ETH per contract
      All others default to 0.001 (override when new assets are listed)

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md
    """
    if not symbol:
        return 0.001
    parts = symbol.split('-')
    underlying = parts[1].upper() if len(parts) >= 2 else symbol.upper()
    return {
        'BTC': 0.001,
        'ETH': 0.001,
    }.get(underlying, 0.001)


@sealed
def calculate_unrealized_pnl(position: Dict, mid_price: float) -> float:
    """
    Calculate unrealized PnL for options position using mid price (bid+ask)/2.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

    For SHORT (size < 0): profit when price drops (mid < entry)
    For LONG (size > 0): profit when price rises (mid > entry)

    Args:
        position: Position dict with size, entry_price, product_symbol
        mid_price: Mid price calculated as (bid+ask)/2

    Returns:
        float: Unrealized PnL in USD (positive = profit, negative = loss)
    """
    # Convert to float (API may return strings)
    size = float(position.get('size', 0))
    entry_price = float(position.get('entry_price', 0))
    mid_price = float(mid_price)
    # BUG-1/BUG-2 FIX: use symbol-aware multiplier instead of hardcoded 0.001
    contract_value = get_contract_multiplier(position.get('product_symbol', ''))

    # For SHORT: size is negative, so (mid - entry) * negative_size = positive when mid < entry (profit)
    # For LONG: size is positive, so (mid - entry) * positive_size = positive when mid > entry (profit)
    pnl = (mid_price - entry_price) * size * contract_value
    return pnl


@sealed
def calculate_pnl_percentage(position: Dict, mid_price: float) -> float:
    """
    Calculate PnL percentage using mid price.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

    Returns positive percentage for profit, negative for loss.
    - For SHORT positions: profit when mid_price < entry_price
    - For LONG positions: profit when mid_price > entry_price
    
    Args:
        position: Position dict with entry_price, size
        mid_price: Mid price calculated as (bid+ask)/2
        
    Returns:
        float: PnL percentage (positive = profit, negative = loss)
    """
    # Convert to float (API may return strings)
    entry_price = float(position.get('entry_price', 0))
    mid_price = float(mid_price)
    size = float(position.get('size', 0))
    
    if entry_price == 0:
        return 0.0
    
    # Price change percentage
    price_change_pct = ((mid_price - entry_price) / entry_price) * 100
    
    # For SHORT positions (size < 0): invert sign so profit shows as positive
    # If mid_price dropped 50% (price_change = -50%), short profit = +50%
    if size < 0:
        return -price_change_pct
    else:
        return price_change_pct


@sealed
def check_expiry_warning(settlement_time: str) -> Dict:
    """
    Check if option is expiring soon.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

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


@sealed
def check_liquidity(ticker: Dict) -> Dict:
    """
    Check if option has sufficient liquidity.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

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


@sealed
def determine_close_side(position_size: float) -> str:
    """
    Determine which side to use to close position.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

    Args:
        position_size: Current position size (positive = long, negative = short)

    Returns:
        str: 'sell' for long positions, 'buy' for short positions
    """
    return 'sell' if position_size > 0 else 'buy'


@sealed
def enrich_position_data(position: Dict, ticker: Dict) -> Dict:
    """
    Enrich position with real-time ticker data.

    SEALED — v1.0.0 — March 4, 2026
    Do not modify without UNSEAL command in AI_SEAL.md

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
    # BUG-1 FIX: use symbol-aware multiplier instead of hardcoded /1000
    symbol = position.get('product_symbol', '')
    contract_multiplier = get_contract_multiplier(symbol)
    cashflow_usd = abs(size) * float(position.get('entry_price', 0)) * contract_multiplier
    
    enriched = position.copy()
    enriched.update({
        'mark_price': mark_price,
        'mid_price': mid_price,  # Add mid price for display
        'best_bid': best_bid,
        'best_ask': best_ask,
        'size': size,
        'entry_price': float(position.get('entry_price', 0)),
        'unrealized_pnl': calculate_unrealized_pnl(position, mid_price),
        # pnl_percentage = option price % change (can be extreme for small premiums, capped ±200% in UI)
        'pnl_percentage': calculate_pnl_percentage(position, mid_price),
        # BUG-19 FIX: add return_on_cashflow = PnL / cash outlay, more meaningful for risk tracking
        # For shorts (cashflow_usd = premium received): shows return vs premium collected
        'return_on_cashflow': (calculate_unrealized_pnl(position, mid_price) / cashflow_usd * 100)
            if cashflow_usd != 0 else 0.0,
        'spread_pct': spread_pct,
        'is_liquid': spread_pct < 10.0 if spread_pct > 0 else True,
        'greeks': ticker.get('greeks', {}),
        'cashflow': cashflow_usd,  # Cashflow in USD
    })
    
    # BUG-27 FIX: settlement_time is a product field, not a position field in the Delta Exchange API.
    # If not present on the position, derive it from the symbol's DDMMYY expiry code.
    settlement_time = position.get('settlement_time') or ticker.get('settlement_time')
    if not settlement_time:
        # Parse from symbol: C-BTC-95000-310125 → day=31, month=01, year=2025
        parts = symbol.split('-')
        if len(parts) >= 4:
            expiry = parts[3]  # DDMMYY
            try:
                day = int(expiry[0:2])
                month = int(expiry[2:4])
                year = 2000 + int(expiry[4:6])
                # 09:30 IST = 04:00 UTC
                settlement_time = f"{year:04d}-{month:02d}-{day:02d}T04:00:00Z"
            except (ValueError, IndexError):
                pass
    if settlement_time:
        enriched['expiry_warning'] = check_expiry_warning(settlement_time)
    
    return enriched
