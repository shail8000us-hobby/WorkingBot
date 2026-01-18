#!/usr/bin/env python3
"""
Test Delta Price WebSocket Connection

Quick script to verify the WebSocket service is correctly receiving
price updates from Delta Exchange.

Usage:
    python test_delta_websocket.py

Expected Output:
    [DeltaWS] Connection established
    [DeltaWS] Subscribed to .DEXBTUSD and .DEETHUSD
    [DeltaWS] BTC price update: $95,174.50
    [DeltaWS] ETH price update: $3,312.44
    ...
"""

import sys
import time
import logging
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

def test_websocket():
    """Test WebSocket connection and price updates"""
    from webui.backend.services.delta_price_websocket import DeltaPriceWebSocket
    
    print("=" * 60)
    print("Delta Price WebSocket Test")
    print("=" * 60)
    print()
    
    # Track received prices
    received_prices = {'BTC': [], 'ETH': []}
    
    def on_price_update(symbol, price):
        """Callback for price updates"""
        received_prices[symbol].append(price)
        print(f"✅ {symbol} Price: ${price:,.2f}")
    
    # Create WebSocket instance
    print("📡 Creating WebSocket instance...")
    ws = DeltaPriceWebSocket(on_price_update=on_price_update)
    
    # Start connection
    print("🔌 Connecting to wss://socket.india.delta.exchange...")
    ws.start()
    
    # Wait for connection
    print("⏳ Waiting for connection (5 seconds)...")
    time.sleep(5)
    
    # Check connection status
    if ws.is_connected():
        print("✅ WebSocket connected successfully!")
    else:
        print("❌ WebSocket failed to connect")
        ws.stop()
        return
    
    # Wait for price updates
    print()
    print("📊 Waiting for price updates (30 seconds)...")
    print("   Press Ctrl+C to stop early")
    print()
    
    try:
        for i in range(30):
            time.sleep(1)
            
            # Show status every 5 seconds
            if i > 0 and i % 5 == 0:
                status = ws.get_status()
                print(f"⏱️  {i}s elapsed - Connected: {status['connected']}, "
                      f"BTC updates: {len(received_prices['BTC'])}, "
                      f"ETH updates: {len(received_prices['ETH'])}")
    
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    # Final summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    status = ws.get_status()
    prices = ws.get_all_prices()
    
    print(f"Connection Status: {'✅ Connected' if status['connected'] else '❌ Disconnected'}")
    print(f"Running: {'✅ Yes' if status['running'] else '❌ No'}")
    print(f"Reconnect Attempts: {status['reconnect_attempts']}")
    print()
    
    print("Latest Prices:")
    print(f"  BTC: ${prices['BTC']:,.2f}" if prices['BTC'] > 0 else "  BTC: No data")
    print(f"  ETH: ${prices['ETH']:,.2f}" if prices['ETH'] > 0 else "  ETH: No data")
    print()
    
    print("Updates Received:")
    print(f"  BTC: {len(received_prices['BTC'])} updates")
    print(f"  ETH: {len(received_prices['ETH'])} updates")
    print()
    
    if received_prices['BTC']:
        print(f"BTC Price Range: ${min(received_prices['BTC']):,.2f} - ${max(received_prices['BTC']):,.2f}")
    if received_prices['ETH']:
        print(f"ETH Price Range: ${min(received_prices['ETH']):,.2f} - ${max(received_prices['ETH']):,.2f}")
    
    # Stop WebSocket
    print()
    print("🛑 Stopping WebSocket...")
    ws.stop()
    
    # Verdict
    print()
    if len(received_prices['BTC']) > 0 and len(received_prices['ETH']) > 0:
        print("✅ TEST PASSED - WebSocket is working correctly!")
    elif status['connected']:
        print("⚠️  TEST PARTIAL - Connected but no price updates received")
        print("   This might indicate a field name mismatch issue")
    else:
        print("❌ TEST FAILED - Could not connect to WebSocket")
    
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_websocket()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
