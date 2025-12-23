#!/usr/bin/env python3
"""
Test Liquidation Monitor Data Accuracy
========================================
This script compares data from multiple sources:
1. Delta Exchange WebSocket (real-time)
2. Delta Exchange REST API (on-demand)
3. Integrated Liquidation Monitor

Use this to debug data discrepancies in the liquidation monitor.
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

# Import components
from bot.liquidation.delta_realtime_websocket import get_delta_websocket
from bot.api.delta_client import DeltaClient

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_comparison(label, ws_value, rest_value, unit="USD"):
    """Print side-by-side comparison"""
    if unit == "USD":
        ws_str = f"${ws_value:,.2f}"
        rest_str = f"${rest_value:,.2f}"
    elif unit == "INR":
        ws_str = f"₹{ws_value:,.2f}"
        rest_str = f"₹{rest_value:,.2f}"
    else:
        ws_str = f"{ws_value}"
        rest_str = f"{rest_value}"
    
    # Calculate difference
    try:
        diff = ws_value - rest_value
        diff_pct = (diff / rest_value * 100) if rest_value != 0 else 0
        
        # Color code based on difference
        if abs(diff) < 0.01:
            status = "✅"
        elif abs(diff_pct) < 1:
            status = "⚠️"
        else:
            status = "❌"
        
        print(f"   {label:<25} | WebSocket: {ws_str:>15} | REST API: {rest_str:>15} | Diff: {diff:>+10.2f} ({diff_pct:>+6.2f}%) {status}")
    except:
        print(f"   {label:<25} | WebSocket: {ws_str:>15} | REST API: {rest_str:>15}")

def main():
    """Main test function"""
    print_header("🔍 Liquidation Monitor Data Accuracy Test")
    
    print("\n📋 This test compares data from:")
    print("   1. Delta Exchange WebSocket (real-time)")
    print("   2. Delta Exchange REST API (on-demand)")
    print("   3. Shows you exactly what your liquidation monitor sees")
    
    # Initialize clients
    print("\n🚀 Initializing clients...")
    
    # WebSocket client
    print("   Starting WebSocket...")
    ws_client = get_delta_websocket()
    
    # REST API client
    print("   Initializing REST API client...")
    rest_client = DeltaClient()
    
    # Wait for WebSocket connection
    print("\n⏳ Waiting for WebSocket connection...")
    max_wait = 15
    waited = 0
    while waited < max_wait:
        if ws_client.is_connected():
            print("✅ WebSocket connected!")
            break
        time.sleep(1)
        waited += 1
    
    if not ws_client.is_connected():
        print("❌ WebSocket connection timeout!")
        print("   Continuing with REST API only...")
    
    # Give WebSocket time to receive initial data
    if ws_client.is_connected():
        print("\n⏳ Waiting for initial WebSocket data...")
        time.sleep(5)
    
    # Run comparison
    print_header("📊 DATA COMPARISON")
    
    # Get data from WebSocket
    ws_status = ws_client.get_full_status()
    ws_upnl_usd = ws_status['upnl']['usd']
    ws_upnl_inr = ws_status['upnl']['inr']
    ws_balance = ws_status['balance']
    ws_mm = ws_status['maintenance_margin']
    
    # Get data from REST API
    print("\n📡 Fetching data from REST API...")
    
    # Get positions for UPNL calculation
    positions_response = rest_client.fetch_positions()
    rest_upnl_usd = 0
    
    if isinstance(positions_response, dict) and positions_response.get('success'):
        positions = positions_response.get('result', [])
    elif isinstance(positions_response, list):
        positions = positions_response
    else:
        positions = []
    
    print(f"   Found {len(positions)} positions")
    
    # Calculate UPNL from positions
    for pos in positions:
        info = pos.get('info', {})
        size = float(info.get('size', 0))
        if size != 0:
            # Get unrealized PnL
            upnl = float(info.get('unrealized_pnl', 0))
            if upnl == 0:
                upnl = float(info.get('unrealized_funding_pnl', 0))
            rest_upnl_usd += upnl
            
            symbol = info.get('product_symbol', 'UNKNOWN')
            print(f"      {symbol}: Size={size}, UPNL=${upnl:.2f}")
    
    rest_upnl_inr = rest_upnl_usd * 85
    
    # Get balance data
    wallet_response = rest_client.get_wallet_balances()
    rest_balance = 0
    rest_available = 0
    rest_blocked = 0
    
    if wallet_response.get('success') and wallet_response.get('result'):
        wallet = wallet_response['result'][0]
        rest_balance = float(wallet.get('balance', 0))
        rest_available = float(wallet.get('available_balance', 0))
        rest_blocked = float(wallet.get('blocked_margin', 0))
        if rest_blocked == 0:
            rest_blocked = float(wallet.get('portfolio_margin', 0))
    
    print("\n" + "-" * 80)
    print("   Metric                    | WebSocket (Real-time)  | REST API (On-demand)   | Difference")
    print("-" * 80)
    
    # Compare UPNL
    print_comparison("UPNL (USD)", ws_upnl_usd, rest_upnl_usd, "USD")
    print_comparison("UPNL (INR)", ws_upnl_inr, rest_upnl_inr, "INR")
    
    # Compare Balance
    if ws_balance:
        print_comparison("Wallet Balance", ws_balance['balance'], rest_balance, "USD")
        print_comparison("Available Balance", ws_balance['available_balance'], rest_available, "USD")
        print_comparison("Blocked Margin", ws_balance['blocked_margin'], rest_blocked, "USD")
    
    # Print maintenance margin from WebSocket
    if ws_mm:
        print(f"\n   Maintenance Margin (WebSocket only):")
        print(f"      With UCF: ${ws_mm['with_ucf']:,.2f}")
        print(f"      Without UCF: ${ws_mm['without_ucf']:,.2f}")
    
    # Test Integrated Liquidation Monitor
    print_header("🛡️ Integrated Liquidation Monitor Test")
    
    try:
        from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
        from config_manager import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config_env()
        
        print("   Initializing monitor...")
        monitor = IntegratedLiquidationMonitor(config)
        
        print("   Fetching status...")
        status = monitor.get_status()
        
        print(f"\n   Monitor Status:")
        print(f"      Total Balance: ₹{status.get('total_balance', 0):,.2f}")
        print(f"      Available Balance: ₹{status.get('available_balance', 0):,.2f}")
        print(f"      Blocked Balance: ₹{status.get('blocked_balance', 0):,.2f}")
        print(f"      Total UPNL (INR): ₹{status.get('total_unrealized_pnl', 0):,.2f}")
        print(f"      Total UPNL (USD): ${status.get('total_unrealized_pnl_usd', 0):,.2f}")
        print(f"      Margin Utilization: {status.get('margin_utilization', 0):.2f}%")
        print(f"      Margin Zone: {status.get('margin_zone', 'UNKNOWN')}")
        print(f"      Liquidation Distance: {status.get('liquidation_distance', 0):.2f}%")
        print(f"      Distance Zone: {status.get('distance_zone', 'UNKNOWN')}")
        
        # Compare with WebSocket
        print(f"\n   Comparison with WebSocket:")
        monitor_upnl_inr = status.get('total_unrealized_pnl', 0)
        diff = monitor_upnl_inr - ws_upnl_inr
        diff_pct = (diff / ws_upnl_inr * 100) if ws_upnl_inr != 0 else 0
        
        print(f"      Monitor UPNL: ₹{monitor_upnl_inr:,.2f}")
        print(f"      WebSocket UPNL: ₹{ws_upnl_inr:,.2f}")
        print(f"      Difference: ₹{diff:,.2f} ({diff_pct:+.2f}%)")
        
        if abs(diff) < 100:
            print(f"      ✅ Data matches!")
        else:
            print(f"      ⚠️ Data mismatch detected!")
        
    except Exception as e:
        print(f"   ❌ Error testing monitor: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print_header("📝 Summary")
    
    print("\n✅ Data Source Recommendations:")
    print("   1. WebSocket (Real-time): Most accurate for UPNL and maintenance margin")
    print("   2. REST API (On-demand): Good for one-time queries")
    print("   3. Monitor should use WebSocket for real-time data")
    
    print("\n🔍 Data Quality Check:")
    upnl_diff = abs(ws_upnl_usd - rest_upnl_usd)
    if upnl_diff < 0.01:
        print("   ✅ WebSocket and REST API data match perfectly")
    elif upnl_diff < 1:
        print("   ⚠️ Minor difference between WebSocket and REST API (< $1)")
    else:
        print(f"   ❌ Significant difference: ${upnl_diff:.2f}")
        print("      This may indicate:")
        print("      - WebSocket hasn't received updates yet")
        print("      - Market movements between API calls")
        print("      - API data inconsistency")
    
    print("\n📊 Your Current UPNL (from WebSocket):")
    print(f"   ${ws_upnl_usd:,.2f} USD")
    print(f"   ₹{ws_upnl_inr:,.2f} INR")
    
    if ws_upnl_usd > 0:
        print("   🟢 You're in profit!")
    elif ws_upnl_usd < 0:
        print("   🔴 You have unrealized losses")
    else:
        print("   ⚪ Breakeven")
    
    print("\n✅ Test complete!")
    
    # Cleanup
    print("\n⏹️ Stopping WebSocket...")
    ws_client.stop()
    print("👋 Done!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
