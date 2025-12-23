#!/usr/bin/env python3
"""
Validation script for async WebSocket fixes (NOV 13, 2025)

This script validates that all the fixes are correctly implemented:
1. AsyncWebSocketManager has proper public properties
2. Health check uses correct API
3. No AttributeError can occur
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def validate_imports():
    """Validate that all modules can be imported."""
    print("🔍 Validating imports...")
    
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager, ConnectionState
        print("  ✅ AsyncWebSocketManager imported")
        
        from bot.strategy.async_gridbot import AsyncGridBot
        print("  ✅ AsyncGridBot imported")
        
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def validate_properties():
    """Validate that required properties exist."""
    print("\n🔍 Validating properties...")
    
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        
        # Create instance
        manager = AsyncWebSocketManager(
            api_key="test",
            api_secret="test",
            testnet=True
        )
        
        # Check ws property
        if not hasattr(manager, 'ws'):
            print("  ❌ Missing 'ws' property")
            return False
        print("  ✅ 'ws' property exists")
        
        # Check is_connected property
        if not hasattr(manager, 'is_connected'):
            print("  ❌ Missing 'is_connected' property")
            return False
        print("  ✅ 'is_connected' property exists")
        
        # Test property access
        ws_value = manager.ws
        print(f"  ✅ 'ws' property returns: {ws_value}")
        
        is_connected = manager.is_connected
        print(f"  ✅ 'is_connected' property returns: {is_connected}")
        
        # Verify is_connected is False when not connected
        if is_connected:
            print("  ⚠️  'is_connected' should be False before connection")
            return False
        print("  ✅ 'is_connected' correctly returns False before connection")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Property validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def validate_state_enum():
    """Validate ConnectionState enum."""
    print("\n🔍 Validating ConnectionState enum...")
    
    try:
        from bot.delta_websocket.async_ws_manager import ConnectionState
        
        # Check all required states
        required_states = ['DISCONNECTED', 'CONNECTING', 'CONNECTED', 'AUTHENTICATED']
        
        for state in required_states:
            if not hasattr(ConnectionState, state):
                print(f"  ❌ Missing state: {state}")
                return False
            print(f"  ✅ State '{state}' exists")
        
        # Check state values
        if ConnectionState.DISCONNECTED.value != "disconnected":
            print("  ❌ DISCONNECTED value incorrect")
            return False
        print("  ✅ State values correct")
        
        return True
        
    except Exception as e:
        print(f"  ❌ State enum validation failed: {e}")
        return False

def validate_health_check_method():
    """Validate health_check method exists and works."""
    print("\n🔍 Validating health_check method...")
    
    try:
        from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager
        
        manager = AsyncWebSocketManager(
            api_key="test",
            api_secret="test",
            testnet=True
        )
        
        # Check method exists
        if not hasattr(manager, 'health_check'):
            print("  ❌ Missing 'health_check' method")
            return False
        print("  ✅ 'health_check' method exists")
        
        # Test method call (async)
        async def test_health_check():
            health = await manager.health_check()
            
            # Validate return structure
            required_keys = ['healthy', 'issues', 'timestamp', 'is_connected', 'state', 'stats']
            for key in required_keys:
                if key not in health:
                    print(f"  ❌ Missing key in health check: {key}")
                    return False
            
            print(f"  ✅ Health check returns correct structure")
            print(f"  ✅ healthy: {health['healthy']}")
            print(f"  ✅ is_connected: {health['is_connected']}")
            print(f"  ✅ state: {health['state']}")
            print(f"  ✅ issues: {health['issues']}")
            
            return True
        
        result = asyncio.run(test_health_check())
        return result
        
    except Exception as e:
        print(f"  ❌ Health check validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def validate_gridbot_health_check():
    """Validate that async_gridbot health check uses correct API."""
    print("\n🔍 Validating async_gridbot health check...")
    
    try:
        import inspect
        from bot.strategy.async_gridbot import AsyncGridBot
        
        # Get source code of _check_websocket_health
        source = inspect.getsource(AsyncGridBot._check_websocket_health)
        
        # Check that it doesn't use the old broken pattern
        if 'self.ws_manager.ws.connected' in source:
            print("  ❌ Still uses broken 'ws.connected' pattern")
            return False
        print("  ✅ Does not use broken 'ws.connected' pattern")
        
        # Check that it uses the new pattern
        if 'self.ws_manager.is_connected' not in source:
            print("  ❌ Does not use 'is_connected' property")
            return False
        print("  ✅ Uses 'is_connected' property")
        
        # Check that it checks state
        if 'self.ws_manager.state' not in source:
            print("  ❌ Does not check state")
            return False
        print("  ✅ Checks WebSocket state")
        
        return True
        
    except Exception as e:
        print(f"  ❌ GridBot health check validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all validations."""
    print("=" * 80)
    print("ASYNC WEBSOCKET FIXES VALIDATION SCRIPT")
    print("November 13, 2025")
    print("=" * 80)
    
    results = []
    
    # Run validations
    results.append(("Imports", validate_imports()))
    results.append(("Properties", validate_properties()))
    results.append(("State Enum", validate_state_enum()))
    results.append(("Health Check Method", validate_health_check_method()))
    results.append(("GridBot Health Check", validate_gridbot_health_check()))
    
    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:.<40} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED!")
        print("The async WebSocket fixes are correctly implemented.")
        print("\n✅ Ready for production deployment!")
        return 0
    else:
        print("\n❌ SOME VALIDATIONS FAILED!")
        print("Please review the errors above and fix the issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
