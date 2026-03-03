#!/usr/bin/env python3
"""
Test WebUI Backend Liquidation Data
=====================================
This script tests if the WebUI backend is serving correct liquidation data
"""

import os
import sys
import requests
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

def test_backend_api():
    """Test the WebUI backend API endpoint"""
    print("=" * 80)
    print("  Testing WebUI Backend Liquidation API")
    print("=" * 80)
    
    # Test endpoint
    url = "http://localhost:5000/api/liquidation/status"
    
    print(f"\n📡 Fetching data from: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('success'):
            print("\n✅ API Response Successful")
            
            # MTM Data
            mtm = data.get('mtm', {})
            print(f"\n📊 Mark-to-Market (MTM):")
            print(f"   Current MTM (INR): ₹{mtm.get('current_mtm_inr', 0):,.2f}")
            print(f"   Trend: {mtm.get('trend', 'UNKNOWN')}")
            print(f"   Alert Level: {mtm.get('alert_level', 'UNKNOWN')}")
            print(f"   Message: {mtm.get('message', 'N/A')}")
            
            # Margin Data
            margin = data.get('margin', {})
            print(f"\n💰 Margin:")
            print(f"   Utilization: {margin.get('utilization', 0):.2f}%")
            print(f"   Zone: {margin.get('zone', 'UNKNOWN')}")
            print(f"   Total Balance: ₹{margin.get('total_balance', 0):,.2f}")
            print(f"   Available Balance: ₹{margin.get('available_balance', 0):,.2f}")
            print(f"   Blocked Balance: ₹{margin.get('blocked_balance', 0):,.2f}")
            print(f"   Unrealized PnL: ₹{margin.get('unrealized_pnl', 0):,.2f}")
            print(f"   Message: {margin.get('message', 'N/A')}")
            
            # Distance Data
            distance = data.get('distance', {})
            print(f"\n📏 Liquidation Distance:")
            print(f"   Distance: {distance.get('distance', 0):.2f}%")
            print(f"   Zone: {distance.get('zone', 'UNKNOWN')}")
            print(f"   Maintenance Margin: ₹{distance.get('maintenance_margin', 0):,.2f}")
            print(f"   Message: {distance.get('message', 'N/A')}")
            
            # Data Source
            print(f"\n🔍 Data Source: {data.get('data_source', 'unknown')}")
            
            # Check if data is correct
            mtm_value = mtm.get('current_mtm_inr', 0)
            if mtm_value > 0:
                print(f"\n✅ MTM is POSITIVE: ₹{mtm_value:,.2f}")
            elif mtm_value < 0:
                print(f"\n⚠️ MTM is NEGATIVE: ₹{mtm_value:,.2f}")
            else:
                print(f"\n❌ MTM is ZERO - This might be wrong!")
            
        else:
            print(f"\n❌ API Error: {data.get('error', 'Unknown error')}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection Error: WebUI backend is not running!")
        print("\n💡 Start the WebUI backend:")
        print("   cd webui")
        print("   ./start.sh")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_direct_monitor():
    """Test the integrated monitor directly"""
    print("\n" + "=" * 80)
    print("  Testing Integrated Liquidation Monitor Directly")
    print("=" * 80)
    
    try:
        from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
        from config_manager import ConfigManager
        
        print("\n🔧 Initializing monitor...")
        config_manager = ConfigManager()
        config = config_manager.load_config_env()
        
        monitor = IntegratedLiquidationMonitor(config)
        
        print("\n📊 Fetching status...")
        status = monitor.get_status()
        
        print(f"\n✅ Monitor Status:")
        print(f"   Total Balance: ₹{status.get('total_balance', 0):,.2f}")
        print(f"   Available Balance: ₹{status.get('available_balance', 0):,.2f}")
        print(f"   Blocked Balance: ₹{status.get('blocked_balance', 0):,.2f}")
        print(f"   Total UPNL (INR): ₹{status.get('total_unrealized_pnl', 0):,.2f}")
        print(f"   Total UPNL (USD): ${status.get('total_unrealized_pnl_usd', 0):,.2f}")
        print(f"   Margin Utilization: {status.get('margin_utilization', 0):.2f}%")
        print(f"   Margin Zone: {status.get('margin_zone', 'UNKNOWN')}")
        print(f"   Liquidation Distance: {status.get('liquidation_distance', 0):.2f}%")
        print(f"   Data Source: {status.get('data_source', 'unknown')}")
        
        # Check WebSocket status
        if monitor.delta_websocket:
            ws_connected = monitor.delta_websocket.is_connected()
            print(f"\n🔌 WebSocket Status: {'✅ Connected' if ws_connected else '❌ Not Connected'}")
            
            if ws_connected:
                upnl_usd, upnl_inr = monitor.delta_websocket.get_upnl()
                print(f"   WebSocket UPNL: ${upnl_usd:.2f} USD = ₹{upnl_inr:,.2f} INR")
        else:
            print(f"\n⚠️ WebSocket not initialized")
        
    except Exception as e:
        print(f"\n❌ Error testing monitor: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🧪 WebUI Backend Liquidation Data Test\n")
    
    # Test direct monitor first
    test_direct_monitor()
    
    # Then test backend API
    test_backend_api()
    
    print("\n" + "=" * 80)
    print("  Test Complete")
    print("=" * 80)
    print("\n💡 If MTM is still wrong:")
    print("   1. Check the logs above for WebSocket connection status")
    print("   2. Restart the WebUI backend")
    print("   3. Hard refresh your browser (Ctrl+Shift+R)")
