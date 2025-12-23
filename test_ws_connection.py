#!/usr/bin/env python3
"""
Test Delta Exchange WebSocket Connection Health

Tests:
1. WebSocket connection establishment
2. Price updates reception  
3. Connection health monitoring
4. Starvation detection
5. Reconnection capability

Run: python test_ws_connection.py
"""

import sys
import os
import time
import logging
from datetime import datetime

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

from delta_websocket.ws_manager import WebSocketManager
from dotenv import load_dotenv

# Load API credentials
load_dotenv('secrets/api_keys.env')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

class WebSocketTester:
    """Test WebSocket connection and health"""
    
    def __init__(self):
        self.ws_manager = None
        self.price_updates = []
        self.last_update_time = None
        self.update_count = 0
        self.connection_established = False
        
    def on_price_update(self, data):
        """Callback for price updates"""
        now = time.time()
        self.last_update_time = now
        self.update_count += 1
        
        if 'close' in data or 'price' in data:
            price = data.get('close') or data.get('price')
            symbol = data.get('symbol', 'UNKNOWN')
            
            self.price_updates.append({
                'timestamp': now,
                'symbol': symbol,
                'price': price
            })
            
            if self.update_count <= 5 or self.update_count % 10 == 0:
                print(f"  📊 Update #{self.update_count}: {symbol} @ ${price}")
    
    def on_connection_status(self, connected: bool):
        """Callback for connection status changes"""
        if connected:
            self.connection_established = True
            print(f"✅ WebSocket CONNECTED at {datetime.now()}")
        else:
            print(f"⚠️  WebSocket DISCONNECTED at {datetime.now()}")
    
    def test_connection(self, duration: int = 30):
        """Test WebSocket connection for specified duration"""
        print("\n" + "="*80)
        print("TEST 1: WebSocket Connection & Price Updates")
        print("="*80)
        
        try:
            # Initialize WebSocket manager
            print(f"\n🔌 Initializing WebSocket manager...")
            api_key = os.getenv('LIVE_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
            api_secret = os.getenv('LIVE_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')
            self.ws_manager = WebSocketManager(api_key, api_secret, symbol="BTCUSD")
            
            # Register callbacks
            print(f"📝 Registering callbacks...")
            self.ws_manager.on_price_update(self.on_price_update)
            
            # Start connection
            print(f"🚀 Starting WebSocket connection...")
            self.ws_manager.connect()
            
            # Wait for connection
            print(f"⏳ Waiting for connection (max 10s)...")
            for i in range(10):
                time.sleep(1)
                if self.connection_established:
                    break
            
            if not self.connection_established:
                print(f"❌ Failed to establish connection within 10s")
                return False
            
            # Monitor for specified duration
            print(f"\n📡 Monitoring price updates for {duration} seconds...")
            print(f"   (Showing first 5 and every 10th update)")
            
            start_time = time.time()
            initial_count = self.update_count
            
            while time.time() - start_time < duration:
                time.sleep(1)
                
                # Check for starvation
                if self.last_update_time:
                    age = time.time() - self.last_update_time
                    if age > 30:
                        print(f"\n⚠️  WARNING: No updates for {age:.1f}s (STARVATION)")
            
            elapsed = time.time() - start_time
            updates_received = self.update_count - initial_count
            
            print(f"\n📊 Results after {elapsed:.1f}s:")
            print(f"   - Total updates: {updates_received}")
            print(f"   - Updates/sec: {updates_received/elapsed:.2f}")
            
            if updates_received > 0:
                print(f"✅ WebSocket is receiving data successfully")
                return True
            else:
                print(f"❌ No updates received - WebSocket may be broken")
                return False
                
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_starvation_detection(self):
        """Test starvation detection by monitoring no-update period"""
        print("\n" + "="*80)
        print("TEST 2: Starvation Detection")
        print("="*80)
        
        if not self.ws_manager or not self.connection_established:
            print(f"⚠️  Skipping - no active connection from previous test")
            return None
        
        print(f"\n⏱️  Monitoring for 60 seconds to detect any starvation...")
        print(f"   (Starvation = no updates for >30s)")
        
        starvation_detected = False
        max_gap = 0
        
        for i in range(60):
            time.sleep(1)
            
            if self.last_update_time:
                gap = time.time() - self.last_update_time
                max_gap = max(max_gap, gap)
                
                if gap > 30 and not starvation_detected:
                    print(f"\n🚨 STARVATION DETECTED: No updates for {gap:.1f}s")
                    starvation_detected = True
                
                if i % 10 == 0:
                    print(f"   {i}s: Last update {gap:.1f}s ago (max gap: {max_gap:.1f}s)")
        
        print(f"\n📊 Starvation Test Results:")
        print(f"   - Max gap between updates: {max_gap:.1f}s")
        
        if starvation_detected:
            print(f"❌ STARVATION OCCURRED - WebSocket is unreliable")
            return False
        elif max_gap > 10:
            print(f"⚠️  Large gaps detected but below threshold")
            return True
        else:
            print(f"✅ No starvation - WebSocket is healthy")
            return True
    
    def test_manual_disconnect_reconnect(self):
        """Test manual disconnect and reconnection"""
        print("\n" + "="*80)
        print("TEST 3: Manual Disconnect & Reconnection")
        print("="*80)
        
        if not self.ws_manager:
            print(f"⚠️  Skipping - no WebSocket manager")
            return None
        
        try:
            print(f"🔌 Forcing disconnect...")
            self.ws_manager.disconnect()
            time.sleep(2)
            
            print(f"🔄 Reconnecting...")
            self.connection_established = False
            self.ws_manager.connect()
            
            # Wait for reconnection
            print(f"⏳ Waiting for reconnection (max 15s)...")
            for i in range(15):
                time.sleep(1)
                if self.connection_established:
                    print(f"✅ Reconnected in {i+1}s")
                    break
            
            if not self.connection_established:
                print(f"❌ Failed to reconnect within 15s")
                return False
            
            # Verify data flow after reconnection
            print(f"\n📡 Verifying data flow after reconnection...")
            old_count = self.update_count
            time.sleep(10)
            new_count = self.update_count
            
            if new_count > old_count:
                print(f"✅ Received {new_count - old_count} updates after reconnection")
                return True
            else:
                print(f"❌ No updates after reconnection")
                return False
                
        except Exception as e:
            print(f"❌ EXCEPTION: {type(e).__name__}: {e}")
            return False
    
    def cleanup(self):
        """Cleanup WebSocket connection"""
        if self.ws_manager:
            print(f"\n🧹 Cleaning up...")
            self.ws_manager.disconnect()
            time.sleep(1)


def main():
    """Run all WebSocket tests"""
    print("\n" + "="*80)
    print("DELTA EXCHANGE WEBSOCKET CONNECTION TEST")
    print("="*80)
    print("Testing WebSocket connection, health, and reconnection")
    
    tester = WebSocketTester()
    results = {}
    
    try:
        # Test 1: Basic connection and updates
        results['connection'] = tester.test_connection(duration=30)
        
        # Test 2: Starvation detection
        results['starvation'] = tester.test_starvation_detection()
        
        # Test 3: Reconnection
        results['reconnection'] = tester.test_manual_disconnect_reconnect()
        
    finally:
        tester.cleanup()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"{status} - {test_name}")
    
    # Overall assessment
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    
    print(f"\n📊 Overall: {passed} passed, {failed} failed")
    
    if results.get('connection') is False:
        print("\n⚠️  CRITICAL: WebSocket connection is broken!")
        print("   - Check network connectivity")
        print("   - Verify API credentials")
        print("   - Check Delta Exchange service status")
    elif results.get('starvation') is False:
        print("\n⚠️  WARNING: WebSocket experiences starvation!")
        print("   - REST API fallback is ESSENTIAL")
        print("   - Consider implementing automatic reconnection")
    else:
        print("\n🎉 WebSocket is working correctly!")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
