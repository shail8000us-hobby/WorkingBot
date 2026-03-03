#!/usr/bin/env python3
"""Test UPNL fetching from Delta Exchange"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

from bot.utils.env_loader import load_trading_mode_config
try:
    load_trading_mode_config()
except:
    pass

from bot.api.delta_client import DeltaClient

client = DeltaClient()

print("=" * 70)
print("Testing UPNL Fetching")
print("=" * 70)

# Method 1: Get positions via CCXT wrapper
print("\n1. Fetching positions via fetch_positions()...")
positions = client.fetch_positions()

total_upnl_usd = 0
for pos in positions:
    info = pos.get('info', {})
    size = float(info.get('size', 0))
    if size != 0:
        # Try to get UPNL from different fields
        upnl = float(info.get('unrealized_pnl', 0))
        if upnl == 0:
            upnl = float(info.get('unrealized_funding_pnl', 0))
        
        total_upnl_usd += upnl
        print(f"\nPosition: {info.get('product_symbol')}")
        print(f"  Size: {size}")
        print(f"  Entry Price: {info.get('entry_price')}")
        print(f"  Mark Price: {info.get('mark_price')}")
        print(f"  Unrealized PnL: ${upnl}")
        print(f"  Raw info keys: {list(info.keys())}")

print(f"\n✅ Total UPNL: ${total_upnl_usd:.2f}")
print(f"✅ Total UPNL in INR: ₹{total_upnl_usd * 85:.2f}")

print("\n" + "=" * 70)
