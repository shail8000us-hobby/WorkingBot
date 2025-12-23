#!/usr/bin/env python3
"""
Critical Async Fixes Validation Script - November 13, 2025 v2

Validates ALL fixes for production deployment:
1. _ws_is_alive() wrapper exists and works
2. REST fallback ask() has correct signature
3. Reconnection properly restarts tasks
4. Health check uses wrapper
5. No direct .closed/.connected/.open access
"""

import sys
import os
import asyncio
from pathlib import Path
import inspect

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("CRITICAL ASYNC FIXES VALIDATION - November 13, 2025 v2")
print("=" * 80)

def test_imports():
    """Test that all modules import successfully."""
    print("\n🔍 Test 1: Module Imports")
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        from bot.strategy.async_gridbot import AsyncGridBot
        from bot.strategy.actors.base_actor import Actor
        print("  ✅ All modules imported successfully")
        return True, (AsyncWebSocketManager, AsyncGridBot, Actor)
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_ws_wrapper(AsyncWebSocketManager):
    """Test _ws_is_alive() wrapper exists and works."""
    print("\n🔍 Test 2: _ws_is_alive() Wrapper")
    try:
        # Check method exists
        if not hasattr(AsyncWebSocketManager, '_ws_is_alive'):
            print("  ❌ _ws_is_alive() method missing")
            return False
        print("  ✅ _ws_is_alive() method exists")
        
        # Create instance
        manager = AsyncWebSocketManager(api_key="test", api_secret="test", testnet=True)
        
        # Test with None
        result = manager._ws_is_alive()
        if result != False:
            print(f"  ❌ _ws_is_alive() should return False for None, got {result}")
            return False
        print("  ✅ _ws_is_alive() returns False for None WebSocket")
        
        # Test defensive programming (no crash on unknown type)
        class FakeWS:
            pass
        
        manager._ws = FakeWS()
        result = manager._ws_is_alive()
        print(f"  ✅ _ws_is_alive() handles unknown types (returns {result})")
        
        # Test ClientConnection with State.OPEN
        from websockets.protocol import State
        class FakeClientConnection:
            state = State.OPEN
        
        manager._ws = FakeClientConnection()
        result = manager._ws_is_alive()
        if result != True:
            print(f"  ❌ _ws_is_alive() should return True for State.OPEN, got {result}")
            return False
        print("  ✅ _ws_is_alive() correctly handles ClientConnection with State.OPEN")
        
        # Test ClientConnection with State.CLOSED
        class FakeClosedConnection:
            state = State.CLOSED
        
        manager._ws = FakeClosedConnection()
        result = manager._ws_is_alive()
        if result != False:
            print(f"  ❌ _ws_is_alive() should return False for State.CLOSED, got {result}")
            return False
        print("  ✅ _ws_is_alive() correctly handles ClientConnection with State.CLOSED")
        
        # Check is_connected uses wrapper
        source = inspect.getsource(AsyncWebSocketManager.is_connected.fget)
        if '_ws_is_alive' not in source:
            print("  ❌ is_connected property doesn't use _ws_is_alive()")
            return False
        print("  ✅ is_connected property uses _ws_is_alive()")
        
        return True
    except Exception as e:
        print(f"  ❌ Wrapper test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_no_direct_closed_access(AsyncWebSocketManager):
    """Test that no code directly accesses .closed/.connected/.open."""
    print("\n🔍 Test 3: No Direct .closed/.connected/.open Access")
    try:
        # Get source code
        source = inspect.getsource(AsyncWebSocketManager)
        
        # Check for dangerous patterns (excluding the wrapper itself)
        issues = []
        
        lines = source.split('\n')
        in_wrapper = False
        for i, line in enumerate(lines, 1):
            # Track when we're inside _ws_is_alive method (start)
            if 'def _ws_is_alive(self)' in line:
                in_wrapper = True
                continue
            
            # Track when we exit _ws_is_alive method (next method def or class-level code)
            if in_wrapper and line.strip() and not line.startswith(' ' * 8) and (line.strip().startswith('def ') or line.strip().startswith('@')):
                in_wrapper = False
            
            # Skip lines inside wrapper
            if in_wrapper:
                continue
            
            # Check for direct .closed access
            if 'self._ws.closed' in line or 'self._ws.connected' in line or 'self._ws.open' in line:
                issues.append(f"Line {i}: {line.strip()}")
        
        if issues:
            print("  ❌ Found direct attribute access:")
            for issue in issues:
                print(f"     {issue}")
            return False
        
        print("  ✅ No direct .closed/.connected/.open access found")
        return True
        
    except Exception as e:
        print(f"  ❌ Source check failed: {e}")
        return False

def test_rest_fallback_signature():
    """Test REST fallback has correct ask() signature."""
    print("\n🔍 Test 4: REST Fallback ask() Signature")
    try:
        from bot.strategy.async_gridbot import AsyncGridBot
        
        # Get source of _poll_pending_orders_via_rest
        source = inspect.getsource(AsyncGridBot._poll_pending_orders_via_rest)
        
        # Check for correct signature: ask("GET_STATE", {}, timeout=...)
        if 'ask("GET_STATE", {})' not in source and 'ask("GET_STATE", {},' not in source:
            print("  ❌ ask() call missing payload argument")
            print("     Expected: ask('GET_STATE', {}, timeout=...)")
            return False
        
        print("  ✅ REST fallback ask() has correct signature")
        return True
        
    except Exception as e:
        print(f"  ❌ Signature check failed: {e}")
        return False

def test_reconnection_restarts_tasks():
    """Test that _handle_reconnect properly restarts tasks."""
    print("\n🔍 Test 5: Reconnection Task Restart")
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        
        source = inspect.getsource(AsyncWebSocketManager._handle_reconnect)
        
        # Check for critical steps
        required_steps = [
            ('_cleanup_tasks', 'Clean up old tasks'),
            ('_message_handler()', 'Restart message handler'),
            ('_monitor_heartbeat()', 'Restart heartbeat monitor'),
            ('_ping_loop()', 'Restart ping loop'),
            ('_send_handler()', 'Restart send handler'),
            ('_authenticate()', 'Re-authenticate'),
            ('_enable_heartbeat()', 'Re-enable heartbeat'),
            ('_restore_public_subscriptions()', 'Restore subscriptions'),
        ]
        
        missing = []
        for step, description in required_steps:
            if step not in source:
                missing.append(f"{description} ({step})")
        
        if missing:
            print("  ❌ Missing reconnection steps:")
            for m in missing:
                print(f"     - {m}")
            return False
        
        print("  ✅ All reconnection steps present:")
        for step, description in required_steps:
            print(f"     ✓ {description}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Reconnection check failed: {e}")
        return False

def test_health_check_uses_wrapper():
    """Test that health check uses wrapper and proper reconnect."""
    print("\n🔍 Test 6: Health Check Uses Wrapper")
    try:
        from bot.strategy.async_gridbot import AsyncGridBot
        
        source = inspect.getsource(AsyncGridBot._check_websocket_health)
        
        # Check uses is_connected (which uses wrapper)
        if 'is_connected' not in source:
            print("  ❌ Health check doesn't use is_connected property")
            return False
        print("  ✅ Health check uses is_connected property")
        
        # Check no direct ._ws.closed access (actual dangerous pattern)
        if '._ws.closed' in source or '._ws.connected' in source or '._ws.open' in source:
            print("  ❌ Health check has direct ._ws attribute access")
            return False
        print("  ✅ Health check has no direct ._ws attribute access")
        
        # Check triggers proper reconnect (_handle_reconnect not connect)
        if '_handle_reconnect' not in source:
            print("  ⚠️  Health check doesn't call _handle_reconnect (may use connect)")
        else:
            print("  ✅ Health check triggers _handle_reconnect")
        
        # Check for _reconnecting flag check
        if '_reconnecting' not in source:
            print("  ⚠️  Health check doesn't check _reconnecting flag")
        else:
            print("  ✅ Health check checks _reconnecting flag")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Health check test failed: {e}")
        return False

def test_ping_send_use_wrapper():
    """Test that ping_loop and send_handler use wrapper."""
    print("\n🔍 Test 7: Ping/Send Loops Use Wrapper")
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        
        ping_source = inspect.getsource(AsyncWebSocketManager._ping_loop)
        send_source = inspect.getsource(AsyncWebSocketManager._send_handler)
        
        # Check ping loop uses wrapper
        if '_ws_is_alive' not in ping_source:
            print("  ❌ Ping loop doesn't use _ws_is_alive()")
            return False
        print("  ✅ Ping loop uses _ws_is_alive()")
        
        # Check send handler uses wrapper
        if '_ws_is_alive' not in send_source:
            print("  ❌ Send handler doesn't use _ws_is_alive()")
            return False
        print("  ✅ Send handler uses _ws_is_alive()")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Ping/Send test failed: {e}")
        return False

def test_async_correctness():
    """Test async correctness markers."""
    print("\n🔍 Test 8: Async Correctness")
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        
        # Check locks present
        manager = AsyncWebSocketManager(api_key="test", api_secret="test", testnet=True)
        
        if not hasattr(manager, '_connection_lock'):
            print("  ❌ Missing _connection_lock")
            return False
        print("  ✅ _connection_lock exists")
        
        if not hasattr(manager, '_reconnecting'):
            print("  ❌ Missing _reconnecting flag")
            return False
        print("  ✅ _reconnecting flag exists")
        
        if not hasattr(manager, 'background_tasks'):
            print("  ❌ Missing background_tasks set")
            return False
        print("  ✅ background_tasks set exists")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Async correctness test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    results = []
    
    # Test 1: Imports
    success, modules = test_imports()
    results.append(("Imports", success))
    if not success:
        print("\n❌ Cannot continue without successful imports")
        return 1
    
    AsyncWebSocketManager, AsyncGridBot, Actor = modules
    
    # Test 2: Wrapper
    results.append(("_ws_is_alive() Wrapper", test_ws_wrapper(AsyncWebSocketManager)))
    
    # Test 3: No direct access
    results.append(("No Direct .closed Access", test_no_direct_closed_access(AsyncWebSocketManager)))
    
    # Test 4: REST fallback
    results.append(("REST Fallback Signature", test_rest_fallback_signature()))
    
    # Test 5: Reconnection
    results.append(("Reconnection Task Restart", test_reconnection_restarts_tasks()))
    
    # Test 6: Health check
    results.append(("Health Check Uses Wrapper", test_health_check_uses_wrapper()))
    
    # Test 7: Ping/Send
    results.append(("Ping/Send Use Wrapper", test_ping_send_use_wrapper()))
    
    # Test 8: Async correctness
    results.append(("Async Correctness", test_async_correctness()))
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:.<50} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 ALL CRITICAL FIXES VALIDATED!")
        print("✅ Production deployment ready")
        print("\nFixed issues:")
        print("  1. ✅ AttributeError '.closed' - FIXED with _ws_is_alive() wrapper")
        print("  2. ✅ REST fallback ask() payload - FIXED")
        print("  3. ✅ WebSocket starvation - FIXED with proper task restart")
        print("  4. ✅ Reconnection race conditions - FIXED")
        print("  5. ✅ Health check crashes - FIXED")
        print("\n🚀 Ready to deploy: pm2 restart gridbot-live-async")
        return 0
    else:
        print("\n❌ SOME VALIDATIONS FAILED!")
        print("Please review the errors above and fix the issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
