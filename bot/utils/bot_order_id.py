#!/usr/bin/env python3
"""
Bot Order ID Generator
Centralized utility to generate clientOrderId with BOT- prefix for provenance tracking
"""

import time
import random
import string
from typing import Optional


def generate_bot_order_id(strategy: str = "grid", extra: Optional[str] = None) -> str:
    """
    Generate a Bot-tagged clientOrderId for provenance tracking.
    
    Format: BOT-<strategy>-<timestamp>-<random>[-<extra>]
    
    Args:
        strategy: Strategy name (grid, scalp, hedge, etc.)
        extra: Optional extra identifier
    
    Returns:
        Formatted clientOrderId string
    
    Examples:
        >>> generate_bot_order_id("grid")
        'BOT-grid-1729012345-a7f3'
        
        >>> generate_bot_order_id("grid", "tp")
        'BOT-grid-1729012345-a7f3-tp'
    """
    timestamp = int(time.time())
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    
    parts = ["BOT", strategy, str(timestamp), rand_suffix]
    
    if extra:
        parts.append(extra)
    
    return "-".join(parts)


def is_bot_order(client_order_id: Optional[str]) -> bool:
    """
    Check if clientOrderId indicates a bot-placed order.
    
    Args:
        client_order_id: The clientOrderId to check
    
    Returns:
        True if bot-placed, False otherwise
    """
    if not client_order_id:
        return False
    
    return client_order_id.startswith("BOT-")


def parse_bot_order_id(client_order_id: str) -> dict:
    """
    Parse a bot clientOrderId into components.
    
    Args:
        client_order_id: Bot-tagged clientOrderId
    
    Returns:
        Dict with: prefix, strategy, timestamp, random, extra
    
    Example:
        >>> parse_bot_order_id("BOT-grid-1729012345-a7f3-tp")
        {
            'prefix': 'BOT',
            'strategy': 'grid',
            'timestamp': 1729012345,
            'random': 'a7f3',
            'extra': 'tp'
        }
    """
    if not is_bot_order(client_order_id):
        return {}
    
    parts = client_order_id.split("-")
    
    result = {
        'prefix': parts[0] if len(parts) > 0 else None,
        'strategy': parts[1] if len(parts) > 1 else None,
        'timestamp': int(parts[2]) if len(parts) > 2 else None,
        'random': parts[3] if len(parts) > 3 else None,
        'extra': parts[4] if len(parts) > 4 else None
    }
    
    return result


if __name__ == "__main__":
    # Demo usage
    print("=== Bot Order ID Generator Demo ===\n")
    
    # Generate various IDs
    print("Basic grid order:")
    grid_id = generate_bot_order_id("grid")
    print(f"  {grid_id}")
    print(f"  Is bot order: {is_bot_order(grid_id)}")
    print(f"  Parsed: {parse_bot_order_id(grid_id)}\n")
    
    print("Grid order with TP marker:")
    tp_id = generate_bot_order_id("grid", "tp")
    print(f"  {tp_id}")
    print(f"  Parsed: {parse_bot_order_id(tp_id)}\n")
    
    print("Grid order with SL marker:")
    sl_id = generate_bot_order_id("grid", "sl")
    print(f"  {sl_id}")
    print(f"  Parsed: {parse_bot_order_id(sl_id)}\n")
    
    print("User order (no BOT- prefix):")
    user_id = "user-manual-123"
    print(f"  {user_id}")
    print(f"  Is bot order: {is_bot_order(user_id)}")
    print(f"  Parsed: {parse_bot_order_id(user_id)}\n")
