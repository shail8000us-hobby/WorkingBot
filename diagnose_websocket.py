#!/usr/bin/env python3
"""
WebSocket Diagnostic Tool
Connects to Delta Exchange WebSocket and logs ALL raw messages
"""

import os
import sys
import json
import time
import logging

# Setup logging to see EVERYTHING
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.utils.env_loader import load_env
from bot.delta_websocket.delta_ws import DeltaWebSocket

# Enable WebSocket trace for low-level debugging
from websocket import enableTrace
enableTrace(True)

def on_message_debug(data):
    """Log every single message received"""
    log.info(f"🔍 RAW MESSAGE: {json.dumps(data, indent=2)}")

def main():
    log.info("=" * 80)
    log.info("WebSocket Diagnostic Tool")
    log.info("=" * 80)
    
    # Load environment
    load_env()
    
    # Get credentials
    api_key = os.getenv("DELTA_API_KEY")
    api_secret = os.getenv("DELTA_API_SECRET")
    ws_url = os.getenv("DELTA_WEBSOCKET_URL")
    
    if not api_key or not api_secret:
        log.error("❌ Missing API credentials!")
        log.error("   Set DELTA_API_KEY and DELTA_API_SECRET in .env")
        return 1
    
    log.info(f"📡 WebSocket URL: {ws_url}")
    log.info(f"🔑 API Key: {api_key[:10]}...")
    log.info("")
    
    try:
        # Create WebSocket with debug callback
        log.info("🔌 Creating WebSocket client...")
        ws = DeltaWebSocket(
            api_key=api_key,
            api_secret=api_secret,
            on_message=on_message_debug
        )
        
        # Connect
        log.info("🔌 Connecting...")
        ws.connect()
        
        log.info("✅ Connected! Watching for messages...")
        log.info("   (Press Ctrl+C to stop)")
        log.info("")
        
        # Subscribe to ticker (public channel, no auth needed)
        log.info("📡 Subscribing to v2/ticker (BTCUSD)...")
        time.sleep(2)  # Wait for auth
        try:
            ws.subscribe('v2/ticker', ['BTCUSD'])
        except Exception as e:
            log.warning(f"⚠️ Subscription attempt failed: {e}")
            log.warning("   This is expected if not authenticated yet")
        
        # Keep running and log connection state every 10 seconds
        for i in range(60):  # Run for 10 minutes
            time.sleep(10)
            
            health = ws.get_health()
            log.info("")
            log.info(f"📊 Health Check #{i+1}:")
            log.info(f"   ├─ Status: {health['status']}")
            log.info(f"   ├─ Connected: {health['connected']}")
            log.info(f"   ├─ Authenticated: {health['authenticated']}")
            log.info(f"   ├─ Messages received: {health['metrics']['total_messages_received']}")
            
            last_msg_age = health['metrics']['last_message_age_seconds']
            if last_msg_age:
                log.info(f"   └─ Last message: {last_msg_age:.1f}s ago")
            else:
                log.info(f"   └─ Last message: Never")
            log.info("")
        
        log.info("⏱️  10 minutes elapsed, disconnecting...")
        ws.disconnect()
        
    except KeyboardInterrupt:
        log.info("")
        log.info("⏹️  Interrupted by user")
        ws.disconnect()
    except Exception as e:
        log.error(f"❌ Error: {e}")
        import traceback
        log.error(traceback.format_exc())
        return 1
    
    log.info("✅ Diagnostic complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
