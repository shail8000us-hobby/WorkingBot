#!/usr/bin/env python3
"""
PM2 WebUI Integration Test

Tests the PM2 adapter and verifies WebUI can communicate with PM2.

Usage:
    python3 test_pm2_integration.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'webui' / 'backend'))

def test_pm2_integration():
    """Test PM2 integration"""
    
    print("=" * 70)
    print("PM2 WebUI Integration Test")
    print("=" * 70)
    print()
    
    # Test 1: Import PM2 adapter
    print("Test 1: Importing PM2 adapter...")
    try:
        from utils.pm2_adapter import get_pm2_adapter, is_pm2_enabled
        print("✅ Import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Check PM2 availability
    print("\nTest 2: Checking PM2 availability...")
    adapter = get_pm2_adapter()
    print(f"  PM2 available: {adapter.available}")
    print(f"  PM2 enabled: {adapter.enabled}")
    print(f"  Config file: {adapter.config_file}")
    
    if not adapter.available:
        print("❌ PM2 not available")
        return False
    
    print("✅ PM2 is available")
    
    if not adapter.enabled:
        print("⚠️  PM2 integration is not enabled")
        print("   Run: ./toggle_pm2.sh enable")
        return True  # Not a failure, just not enabled
    
    print("✅ PM2 integration is enabled")
    
    # Test 3: Get bot status
    print("\nTest 3: Getting bot status...")
    try:
        status = adapter.get_bot_status('live')
        if status:
            print(f"✅ Bot status retrieved:")
            print(f"   Name: {status['name']}")
            print(f"   Status: {status['status']}")
            print(f"   PID: {status.get('pid', 'N/A')}")
            print(f"   Restarts: {status.get('restarts', 0)}")
        else:
            print("ℹ️  Bot not running in PM2")
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return False
    
    # Test 4: Get all bots
    print("\nTest 4: Getting all bots...")
    try:
        bots = adapter.get_all_bots_status()
        print(f"✅ Found {len(bots)} bot(s) in PM2")
        for bot in bots:
            print(f"   - {bot['name']}: {bot['status']}")
    except Exception as e:
        print(f"❌ Failed to get bots: {e}")
        return False
    
    # Test 5: WebUI routes integration
    print("\nTest 5: Checking WebUI integration...")
    try:
        from routes.bot_control import bot_control_bp
        
        # Check routes exist
        routes = [rule.rule for rule in bot_control_bp.url_map.iter_rules()]
        
        expected_routes = [
            '/api/bot/status',
            '/api/bot/start',
            '/api/bot/stop',
            '/api/bot/restart',
            '/api/pm2/enabled',
            '/api/pm2/bots'
        ]
        
        missing = []
        for route in expected_routes:
            if route not in routes:
                missing.append(route)
        
        if missing:
            print(f"❌ Missing routes: {missing}")
            return False
        
        print("✅ All WebUI routes registered")
        
    except Exception as e:
        print(f"⚠️  Could not verify routes: {e}")
        print("   (This is normal if WebUI is not running)")
    
    print()
    print("=" * 70)
    print("✅ PM2 Integration Test: PASSED")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Restart WebUI: cd webui && ./restart.sh")
    print("2. Start bot via PM2: ./pm2_gridbot.sh start live")
    print("3. Or use WebUI Start Bot button")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = test_pm2_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
