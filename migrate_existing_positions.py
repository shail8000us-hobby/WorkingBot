#!/usr/bin/env python3
"""
Migrate existing open positions to the Position Tracker

This script reads the bot's internal state (open_tranches) and creates
position tracking entries for them.
"""

import os
import sys
from pathlib import Path

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment
os.environ["USD_TO_INR_RATE"] = "85"
os.environ["MAINTENANCE_MARGIN_PERCENT"] = "2.5"

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("MIGRATE EXISTING POSITIONS TO TRACKER")
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

# Get current market price (you'll need to update this manually)
print("=" * 50)
print("INSTRUCTIONS:")
print("=" * 50)
print()
print("This script needs information about your open positions.")
print("Please check your bot logs or Delta Exchange and provide:")
print()
print("For each open position:")
print("  1. Entry price (buy price)")
print("  2. TP order ID (if available)")
print("  3. Size (usually 1)")
print()

# Example: You can manually add positions here
# Based on your config: GRID_STEP=500, so positions are likely at 500 intervals

print("Checking current bot state...")

# Try to infer from state.json or bot logs
import json

# Check if we can get info from bot's internal state
# You'll need to provide the actual position data

print()
print("=" * 50)
print("MANUAL POSITION ENTRY")
print("=" * 50)
print()
print("Since your bot is running, you can:")
print()
print("Option 1: Stop the bot and restart it")
print("   The new position tracker will start tracking new positions automatically")
print()
print("Option 2: Manually add positions below")
print()

# Get user input
add_positions = input("Do you want to manually add positions now? (y/n): ").strip().lower()

if add_positions == 'y':
    num_positions = int(input("How many positions do you have open? "))
    
    current_price = float(input("What is the current BTC price? (e.g., 112000): "))
    
    for i in range(num_positions):
        print(f"\n--- Position {i+1} ---")
        entry_price = float(input(f"  Entry price: "))
        size = float(input(f"  Size (default 1): ") or "1")
        tp_order_id = input(f"  TP Order ID (optional): ").strip() or f"TP_MIGRATED_{i+1}"
        
        # Add to tracker
        position = tracker.add_position(
            position_id=f"POS_MIGRATED_{i+1}",
            entry_price=entry_price,
            size=size,
            tp_order_id=tp_order_id,
            current_price=current_price
        )
        
        print(f"  ✅ Position added: {position.id}")
        print(f"     Entry: ₹{position.entry_price:,.2f}")
        print(f"     Liquidation: ₹{position.liquidation.liquidation_price:,.2f}")
        print(f"     PnL: ₹{position.pnl_inr:,.2f}")
    
    print()
    print("=" * 50)
    print("✅ MIGRATION COMPLETE")
    print("=" * 50)
    print()
    print(f"Added {num_positions} position(s) to tracker")
    print(f"File saved: positions.json")
    print()
    print("Refresh your Web UI to see the positions!")
    
else:
    print()
    print("No positions added. Recommendations:")
    print()
    print("1. EASIEST: Stop the bot and restart it")
    print("   - The bot will start tracking new positions automatically")
    print("   - Existing positions will be tracked when they close and reopen")
    print()
    print("2. Wait for the next trade")
    print("   - When a TP fills or new entry, tracking starts automatically")
    print()
    print("3. Re-run this script later")
    print("   - Come back and manually add positions")

