#!/usr/bin/env python3
"""
WebSocket Test Script
Quick test to verify WebSocket connection works
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger("test")

# Load environment
load_dotenv("secrets/api_keys.env")
load_dotenv("grid_config.env")

# Import WebSocket manager
from bot.websocket import WebSocketManager

def main():
    """
    Test WebSocket connection
    """
    log.info("=" * 80)
    log.info("🧪 WEBSOCKET CONNECTION TEST")
    log.info("=" * 80)
    
    # Get API credentials
    api_key = os.getenv("DELTA_API_KEY")
    api_secret = os.getenv("DELTA_API_SECRET")
    
    if not api_key or not api_secret:
        log.error("❌ API credentials not found!")
        log.error("   Please set DELTA_API_KEY and DELTA_API_SECRET in secrets/api_keys.env")
        sys.exit(1)
    
    log.info(f"✅ API Key: {api_key[:10]}...")
    log.info(f"✅ API Secret: {api_secret[:10]}...")
    
    # Create WebSocket manager
    log.info("\n📡 Creating WebSocket Manager...")
    ws_manager = WebSocketManager(
        api_key=api_key,
        api_secret=api_secret,
        symbol="BTCUSD",
        testnet=True
    )
    
    # Register callbacks
    def on_fill(data):
        log.info(f"🎯 FILL: {data}")
    
    def on_price(data):
        price = data.get('close', 0)
        log.info(f"💹 PRICE UPDATE: {price}")
    
    def on_position(data):
        log.info(f"📊 POSITION: {data}")
    
    ws_manager.on_fill(on_fill)
    ws_manager.on_price_update(on_price)
    ws_manager.on_position_update(on_position)
    
    # Connect
    log.info("\n🔌 Connecting to WebSocket...")
    try:
        ws_manager.connect()
        log.info("✅ WebSocket connected!")
    except Exception as e:
        log.error(f"❌ Connection failed: {e}")
        sys.exit(1)
    
    # Monitor for 30 seconds
    log.info("\n⏱️  Monitoring for 30 seconds...")
    log.info("   (You should see real-time price updates)")
    log.info("")
    
    try:
        for i in range(30):
            time.sleep(1)
            
            # Check connection
            if not ws_manager.is_connected():
                log.warning("⚠️  WebSocket disconnected!")
                break
            
            # Show price every 5 seconds
            if i % 5 == 0:
                price = ws_manager.get_last_price()
                if price:
                    log.info(f"   Current price: {price}")
    
    except KeyboardInterrupt:
        log.info("\n⚠️  Interrupted by user")
    
    # Disconnect
    log.info("\n🔌 Disconnecting...")
    ws_manager.disconnect()
    
    log.info("\n" + "=" * 80)
    log.info("✅ TEST COMPLETE!")
    log.info("=" * 80)

if __name__ == "__main__":
    main()

