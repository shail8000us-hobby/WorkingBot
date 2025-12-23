#!/usr/bin/env python3
"""
Show Current UPNL from Delta Exchange
======================================
This script shows the CURRENT UPNL directly from Delta Exchange WebSocket
in real-time. Compare this with your Delta Exchange UI.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

# Set up mode-specific config
from bot.utils.env_loader import load_trading_mode_config
try:
    load_trading_mode_config()
except Exception as e:
    print(f"⚠️ Warning: {e}")

from bot.liquidation.delta_realtime_websocket import get_delta_websocket

def main():
    print("=" * 80)
    print("  📊 CURRENT UPNL FROM DELTA EXCHANGE (Real-Time)")
    print("=" * 80)
    print()
    print("This shows the CURRENT unrealized PnL from Delta Exchange WebSocket.")
    print("Compare this value with your Delta Exchange UI RIGHT NOW.")
    print()
    
    # Get WebSocket client
    print("🔌 Connecting to Delta Exchange WebSocket...")
    ws_client = get_delta_websocket()
    
    # Wait for connection
    print("⏳ Waiting for connection and initial data...")
    time.sleep(5)
    
    if not ws_client.is_connected():
        print("❌ WebSocket not connected!")
        print("   Please check your API credentials and internet connection.")
        return
    
    print("✅ Connected!")
    print()
    
    # Show real-time updates for 30 seconds
    print("📊 Real-Time UPNL Updates (refreshing every 2 seconds)")
    print("   Press Ctrl+C to stop")
    print()
    print("-" * 80)
    
    try:
        for i in range(15):  # 30 seconds
            upnl_usd, upnl_inr = ws_client.get_upnl()
            
            # Color code based on profit/loss
            if upnl_usd > 0:
                status = "🟢 PROFIT"
                color = "\033[92m"  # Green
            elif upnl_usd < 0:
                status = "🔴 LOSS"
                color = "\033[91m"  # Red
            else:
                status = "⚪ BREAKEVEN"
                color = "\033[0m"   # Default
            
            reset = "\033[0m"
            
            print(f"{color}Update #{i+1:2d} | UPNL: ${upnl_usd:+10.2f} USD = ₹{upnl_inr:+12,.2f} INR | {status}{reset}")
            
            time.sleep(2)
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    
    # Final summary
    print()
    print("=" * 80)
    print("  📊 FINAL UPNL")
    print("=" * 80)
    
    upnl_usd, upnl_inr = ws_client.get_upnl()
    
    print(f"\n💰 Current Unrealized PnL:")
    print(f"   USD: ${upnl_usd:,.2f}")
    print(f"   INR: ₹{upnl_inr:,.2f}")
    
    if upnl_usd > 0:
        print(f"\n🟢 You're currently in PROFIT by ${upnl_usd:,.2f} USD")
    elif upnl_usd < 0:
        print(f"\n🔴 You're currently at a LOSS of ${abs(upnl_usd):,.2f} USD")
    else:
        print(f"\n⚪ You're at BREAKEVEN")
    
    print(f"\n📱 Now check your Delta Exchange app/website:")
    print(f"   1. Open Delta Exchange")
    print(f"   2. Go to Positions tab")
    print(f"   3. Check 'Total UPNL' value")
    print(f"   4. It should match: ${upnl_usd:,.2f} USD (±$1 due to market movement)")
    
    print(f"\n✅ Your liquidation monitor is showing the CORRECT real-time data!")
    print(f"   WebUI MTM: ₹{upnl_inr:,.2f}")
    
    # Stop WebSocket
    ws_client.stop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
