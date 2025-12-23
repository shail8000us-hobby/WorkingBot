#!/usr/bin/env python3
"""
Test Delta Exchange Real-Time WebSocket
==========================================
This script tests the comprehensive Delta Exchange WebSocket client
that fetches UPNL, Balance, and Maintenance Margin in real-time.

Run this to verify your liquidation monitor is getting correct data.
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
    print(f"✅ Trading mode loaded: {os.getenv('TRADING_MODE', 'unknown')}")
except Exception as e:
    print(f"⚠️ Warning: {e}")

# Import WebSocket client
from bot.liquidation.delta_realtime_websocket import get_delta_websocket

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_section(title):
    """Print formatted section"""
    print(f"\n{title}")
    print("-" * 80)

def format_currency(value, currency="USD"):
    """Format currency value"""
    if currency == "USD":
        return f"${value:,.2f}"
    elif currency == "INR":
        return f"₹{value:,.2f}"
    return f"{value:,.2f}"

def main():
    """Main test function"""
    print_header("🧪 Delta Exchange Real-Time WebSocket Test")
    
    print("\n📋 Test Configuration:")
    print(f"   API Key: {os.getenv('DELTA_API_KEY', 'NOT SET')[:10]}...")
    print(f"   WebSocket URL: {os.getenv('DELTA_WEBSOCKET_URL', 'wss://socket.india.delta.exchange')}")
    print(f"   Trading Mode: {os.getenv('TRADING_MODE', 'live')}")
    
    # Create WebSocket client (singleton)
    print("\n🚀 Starting WebSocket client...")
    ws_client = get_delta_websocket()
    
    # Add alert callback
    def alert_handler(message, data):
        print(f"\n🚨 ALERT: {message}")
        print(f"   Liquidation Risk: {data.get('liquidation_risk', False)}")
        print(f"   Under Liquidation: {data.get('under_liquidation', False)}")
        print(f"   Margin Shortfall: {format_currency(data.get('margin_shortfall', 0))}")
    
    ws_client.add_alert_callback(alert_handler)
    
    # Wait for connection and authentication
    print("⏳ Waiting for WebSocket connection and authentication...")
    max_wait = 10  # seconds
    waited = 0
    while waited < max_wait:
        if ws_client.is_connected():
            print("✅ WebSocket connected and authenticated!")
            break
        time.sleep(1)
        waited += 1
        print(f"   Waiting... ({waited}s/{max_wait}s)")
    
    if not ws_client.is_connected():
        print("❌ WebSocket failed to connect within timeout!")
        print("\n🔍 Troubleshooting:")
        print("   1. Check your API credentials in secrets/api_keys.env")
        print("   2. Verify your internet connection")
        print("   3. Check Delta Exchange API status")
        sys.exit(1)
    
    # Run test for 60 seconds, displaying data every 5 seconds
    test_duration = 60
    update_interval = 5
    iterations = test_duration // update_interval
    
    print(f"\n📊 Monitoring real-time data for {test_duration} seconds...")
    print(f"   Update interval: {update_interval} seconds")
    
    for i in range(iterations):
        time.sleep(update_interval)
        
        print_header(f"Update #{i+1} / {iterations}")
        
        # Get full status
        status = ws_client.get_full_status()
        
        # Connection status
        print_section("🔌 Connection Status")
        print(f"   Connected: {'✅ Yes' if status['connected'] else '❌ No'}")
        print(f"   Authenticated: {'✅ Yes' if status['authenticated'] else '❌ No'}")
        print(f"   Messages Received: {status['message_count']}")
        print(f"   Reconnection Attempts: {status['reconnect_count']}")
        print(f"   Last Update: {status['last_update'] or 'Never'}")
        
        # Balance data
        if status['balance']:
            print_section("💰 Balance (from 'margins' channel)")
            balance = status['balance']
            print(f"   Asset: {balance['asset_symbol']}")
            print(f"   Wallet Balance: {format_currency(balance['balance'])}")
            print(f"   Available Balance: {format_currency(balance['available_balance'])}")
            print(f"   Blocked Margin: {format_currency(balance['blocked_margin'])}")
            print(f"   Portfolio Margin: {format_currency(balance['portfolio_margin'])}")
            print(f"   Order Margin: {format_currency(balance['order_margin'])}")
            print(f"   Position Margin: {format_currency(balance['position_margin'])}")
        else:
            print_section("💰 Balance")
            print("   ⚠️ No balance data received yet")
        
        # UPNL data
        if status['upnl']:
            print_section("📊 Unrealized PnL (from 'portfolio_margins' channel)")
            upnl = status['upnl']
            print(f"   UPNL (USD): {format_currency(upnl['usd'], 'USD')}")
            print(f"   UPNL (INR): {format_currency(upnl['inr'], 'INR')}")
            
            # Color-coded status
            if upnl['usd'] > 0:
                print(f"   Status: 🟢 Profit")
            elif upnl['usd'] < 0:
                print(f"   Status: 🔴 Loss")
            else:
                print(f"   Status: ⚪ Neutral")
        else:
            print_section("📊 Unrealized PnL")
            print("   ⚠️ No UPNL data received yet")
        
        # Maintenance Margin
        if status['maintenance_margin']:
            print_section("🛡️ Maintenance Margin (from 'portfolio_margins' channel)")
            mm = status['maintenance_margin']
            print(f"   MM (with unrealized cashflows): {format_currency(mm['with_ucf'])}")
            print(f"   MM (without unrealized cashflows): {format_currency(mm['without_ucf'])}")
        else:
            print_section("🛡️ Maintenance Margin")
            print("   ⚠️ No maintenance margin data received yet")
        
        # Liquidation Risk
        if status['liquidation_risk']:
            print_section("⚠️ Liquidation Risk (from 'portfolio_margins' channel)")
            risk = status['liquidation_risk']
            
            if risk['liquidation_risk'] or risk['under_liquidation']:
                print(f"   🚨 LIQUIDATION RISK DETECTED!")
            else:
                print(f"   ✅ No liquidation risk")
            
            print(f"   Liquidation Risk: {'⚠️ YES' if risk['liquidation_risk'] else '✅ NO'}")
            print(f"   Under Liquidation: {'🚨 YES' if risk['under_liquidation'] else '✅ NO'}")
            print(f"   Margin Shortfall: {format_currency(risk['margin_shortfall'])}")
            print(f"   Risk Margin: {format_currency(risk['risk_margin'])}")
        
        # Portfolio margin details
        if status['portfolio_margin']:
            print_section("📈 Portfolio Margin Details")
            pm = status['portfolio_margin']
            print(f"   Index Symbol: {pm['index_symbol']}")
            print(f"   Positions UPL: {format_currency(pm['positions_upl'])} USD")
            print(f"   Blocked Margin: {format_currency(pm['blocked_margin'])}")
    
    # Final summary
    print_header("✅ Test Complete")
    
    final_status = ws_client.get_full_status()
    
    print("\n📊 Final Summary:")
    print(f"   Total Messages: {final_status['message_count']}")
    print(f"   Reconnections: {final_status['reconnect_count']}")
    
    if final_status['upnl']:
        upnl_usd = final_status['upnl']['usd']
        upnl_inr = final_status['upnl']['inr']
        print(f"\n💰 Final UPNL:")
        print(f"   USD: {format_currency(upnl_usd, 'USD')}")
        print(f"   INR: {format_currency(upnl_inr, 'INR')}")
    
    if final_status['balance']:
        balance = final_status['balance']['balance']
        available = final_status['balance']['available_balance']
        print(f"\n💵 Final Balance:")
        print(f"   Total: {format_currency(balance)}")
        print(f"   Available: {format_currency(available)}")
    
    print("\n✅ WebSocket test completed successfully!")
    print("\n📝 Next Steps:")
    print("   1. Verify the UPNL matches Delta Exchange UI")
    print("   2. Check balance and margin data accuracy")
    print("   3. Start your liquidation monitor with this WebSocket")
    
    # Stop WebSocket
    print("\n⏹️ Stopping WebSocket...")
    ws_client.stop()
    print("👋 Goodbye!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
