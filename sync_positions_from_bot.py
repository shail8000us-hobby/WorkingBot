#!/usr/bin/env python3
"""
Sync existing bot positions to Position Tracker

This script connects to the running bot's internal state
and creates position tracking entries.
"""

import os
import sys
import json
import ccxt
from pathlib import Path
from datetime import datetime

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv('grid_config.env')
load_dotenv('secrets/api_keys.env')

# Set defaults
os.environ.setdefault("USD_TO_INR_RATE", "85")
os.environ.setdefault("MAINTENANCE_MARGIN_PERCENT", "2.5")

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("SYNC BOT POSITIONS TO TRACKER")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()

try:
    from bot.position_tracker import PositionTracker
    print("✅ Position Tracker imported")
except Exception as e:
    print(f"❌ Failed to import Position Tracker: {e}")
    sys.exit(1)

# Initialize tracker
tracker = PositionTracker(storage_file="positions.json")
print(f"✅ Position Tracker initialized")
print()

# Initialize Delta Exchange client
try:
    api_key = os.getenv('DELTA_API_KEY', '')
    api_secret = os.getenv('DELTA_API_SECRET', '')
    
    if not api_key or not api_secret:
        print("❌ API credentials not found")
        print("   Please check secrets/api_keys.env")
        sys.exit(1)
    
    exchange = ccxt.delta({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    
    print("✅ Connected to Delta Exchange")
    print()
except Exception as e:
    print(f"❌ Failed to connect to Delta Exchange: {e}")
    sys.exit(1)

# Get current market price
symbol = os.getenv('GRIDBOT_SYMBOL', 'BTC/USD:USD')

# Try different symbol formats for Delta
symbol_variants = [symbol, 'BTCUSD', 'BTC/USDT']

current_price = None
for sym in symbol_variants:
    try:
        ticker = exchange.fetch_ticker(sym)
        current_price = ticker['last']
        print(f"Current {sym} price: ₹{current_price:,.2f}")
        symbol = sym  # Use working symbol
        break
    except Exception:
        continue

if not current_price:
    # Fallback: get from recent log
    print("⚠️  Could not fetch current price from exchange")
    try:
        import re
        with open('bot/logs/bot.log', 'r') as f:
            lines = f.readlines()[-50:]
            for line in reversed(lines):
                match = re.search(r'BTC/USD:USD: ([\d.]+)', line)
                if match:
                    current_price = float(match.group(1))
                    print(f"Using price from logs: ₹{current_price:,.2f}")
                    break
    except Exception as e:
        print(f"Could not read from logs: {e}")
    
    if not current_price:
        print("❌ Could not determine current price")
        print("Please ensure bot is running or check logs")
        sys.exit(1)

print()

# Fetch open orders
try:
    print("Fetching open orders from Delta Exchange...")
    orders = exchange.fetch_open_orders(symbol)
    print(f"Found {len(orders)} open orders")
    print()
    
    # Separate into BUY and SELL orders
    buy_orders = [o for o in orders if o['side'] == 'buy']
    sell_orders = [o for o in orders if o['side'] == 'sell']
    
    print(f"  BUY orders: {len(buy_orders)}")
    print(f"  SELL orders (TP): {len(sell_orders)}")
    print()
    
    if not sell_orders:
        print("No SELL orders found (no open positions with TP)")
        print("This means no positions are currently open.")
        sys.exit(0)
    
    # Each SELL order represents a position with TP
    print("Creating position tracker entries...")
    print()
    
    step = float(os.getenv('GRIDBOT_STEP', '500'))
    
    for i, tp_order in enumerate(sell_orders, 1):
        tp_price = float(tp_order['price'])
        tp_id = tp_order['id']
        size = float(tp_order['amount'])
        
        # Calculate entry price (TP - STEP)
        entry_price = tp_price - step
        
        print(f"Position {i}:")
        print(f"  Entry: ₹{entry_price:,.2f}")
        print(f"  TP: ₹{tp_price:,.2f}")
        print(f"  TP Order ID: {tp_id}")
        print(f"  Size: {size}")
        
        # Add to tracker
        try:
            position = tracker.add_position(
                position_id=f"POS_{tp_id}",
                entry_price=entry_price,
                size=size,
                tp_order_id=tp_id,
                current_price=current_price
            )
            
            print(f"  ✅ Added to tracker")
            print(f"     Liquidation: ₹{position.liquidation.liquidation_price:,.2f}")
            print(f"     Distance: {position.liquidation.distance_to_liq_percent:.2f}%")
            print(f"     PnL: ₹{position.pnl_inr:,.2f}")
            print(f"     Risk: {position.liquidation.risk_level.upper()}")
            print()
        except Exception as e:
            print(f"  ⚠️  Failed to add: {e}")
            print()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ SYNC COMPLETE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"Synced {len(sell_orders)} position(s) to tracker")
    print(f"File saved: positions.json")
    print()
    
    # Show summary
    summary = tracker.get_summary()
    print("Summary:")
    print(f"  Total Positions: {summary['total_positions']}")
    print(f"  Total PnL: ${summary['total_pnl_usd']:.2f} / ₹{summary['total_pnl_inr']:.2f}")
    print(f"  Risk Level: {summary['risk_percent']:.1f}%")
    print(f"  Overall Liquidation Risk: {summary['overall_liq_risk'].upper()}")
    print()
    print("🎉 Refresh your Web UI to see the positions!")
    print()
    
except Exception as e:
    print(f"❌ Error fetching orders: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

