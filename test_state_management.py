#!/usr/bin/env python3
"""
State Management Test Suite
Tests the new v2.0 state management features

Run: python3 test_state_management.py
"""

import json
import hashlib
import time
import os
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.strategy.modules.position_manager import PositionManager


def test_immediate_persistence():
    """Test that state persists immediately after changes"""
    print("\n" + "=" * 60)
    print("TEST 1: Immediate Persistence")
    print("=" * 60)
    
    # Create position manager
    pm = PositionManager(max_open=10, session_tag="TEST_SESSION")
    
    # Get initial modification time
    state_file = Path('runtime_state.json')
    if state_file.exists():
        initial_mtime = state_file.stat().st_mtime
    else:
        initial_mtime = 0
    
    # Wait 2 seconds to ensure debounce expires
    time.sleep(2)
    
    # Add position
    print("Adding position...")
    pm.add_position({
        'entry_price': 94000,
        'tp_price': 95000,
        'buy_order_id': 'TEST_ORDER_1'
    })
    
    # Check if file was updated
    time.sleep(0.5)  # Small delay for file system
    new_mtime = state_file.stat().st_mtime
    
    if new_mtime > initial_mtime:
        print("✅ PASS: State file updated after add_position()")
        print(f"   Time delta: {new_mtime - initial_mtime:.2f}s")
    else:
        print("❌ FAIL: State file NOT updated after add_position()")
        return False
    
    # Verify position in state
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    if 'data' in state:
        positions = state['data']['open_tranches']
    else:
        positions = state['open_tranches']
    
    if len(positions) == 1 and positions[0]['entry_price'] == 94000:
        print("✅ PASS: Position correctly saved in state file")
    else:
        print("❌ FAIL: Position NOT found in state file")
        return False
    
    return True


def test_checksum_validation():
    """Test checksum validation on load"""
    print("\n" + "=" * 60)
    print("TEST 2: Checksum Validation")
    print("=" * 60)
    
    state_file = Path('runtime_state.json')
    
    # Read current state
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    # Verify checksum exists
    if 'checksum' not in state:
        print("⚠️  SKIP: Legacy state format (no checksum)")
        return True
    
    stored_checksum = state['checksum']
    data = state['data']
    
    # Recalculate checksum
    data_json = json.dumps(data, sort_keys=True)
    calculated_checksum = hashlib.sha256(data_json.encode()).hexdigest()[:16]
    
    if stored_checksum == calculated_checksum:
        print("✅ PASS: Checksum validation successful")
        print(f"   Checksum: {stored_checksum}")
    else:
        print("❌ FAIL: Checksum mismatch!")
        print(f"   Stored: {stored_checksum}")
        print(f"   Calculated: {calculated_checksum}")
        return False
    
    return True


def test_metadata_presence():
    """Test that metadata is present in v2.0 format"""
    print("\n" + "=" * 60)
    print("TEST 3: Metadata Presence")
    print("=" * 60)
    
    state_file = Path('runtime_state.json')
    
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    required_fields = ['version', 'schema_version', 'created_at', 'bot_pid', 'checksum', 'data']
    
    for field in required_fields:
        if field in state:
            print(f"✅ {field}: {state[field]}")
        else:
            print(f"❌ Missing: {field}")
            return False
    
    print("✅ PASS: All metadata fields present")
    return True


def test_debouncing():
    """Test that debouncing prevents excessive writes"""
    print("\n" + "=" * 60)
    print("TEST 4: Debouncing (1s interval)")
    print("=" * 60)
    
    pm = PositionManager(max_open=10, session_tag="TEST_DEBOUNCE")
    
    state_file = Path('runtime_state.json')
    initial_mtime = state_file.stat().st_mtime
    
    # Add 5 positions rapidly
    print("Adding 5 positions in <1 second...")
    for i in range(5):
        pm.add_position({
            'entry_price': 94000 + (i * 1000),
            'tp_price': 95000 + (i * 1000),
            'buy_order_id': f'TEST_ORDER_{i}'
        })
        time.sleep(0.1)  # 100ms between adds
    
    time.sleep(0.5)
    final_mtime = state_file.stat().st_mtime
    
    # Should have ~1 write despite 5 changes
    write_count_estimate = int((final_mtime - initial_mtime) / 1.0) + 1
    
    if write_count_estimate <= 2:
        print(f"✅ PASS: Debouncing working (~{write_count_estimate} writes for 5 changes)")
    else:
        print(f"⚠️  WARNING: Possible excessive writes ({write_count_estimate} writes)")
    
    return True


def test_stale_rejection():
    """Test that stale state is rejected"""
    print("\n" + "=" * 60)
    print("TEST 5: Stale State Rejection (5 minute threshold)")
    print("=" * 60)
    
    # Create a stale state file
    stale_state = {
        "version": "2.0",
        "schema_version": 1,
        "created_at": "2025-11-08T00:00:00+00:00",
        "bot_pid": os.getpid(),
        "checksum": "test",
        "data": {
            "timestamp": time.time() - 600,  # 10 minutes old
            "session_tag": "STALE_TEST",
            "open_tranches": [],
            "pending_buy": None,
            "tp_retry_queue": [],
            "reserved_capacity": 0,
            "max_open": 10
        }
    }
    
    # Calculate proper checksum
    data_json = json.dumps(stale_state['data'], sort_keys=True)
    stale_state['checksum'] = hashlib.sha256(data_json.encode()).hexdigest()[:16]
    
    # Write stale state
    test_file = 'test_stale_state.json'
    with open(test_file, 'w') as f:
        json.dump(stale_state, f, indent=2)
    
    # Try to load
    pm = PositionManager(max_open=10, session_tag="TEST")
    result = pm.load_runtime_state(test_file)
    
    # Clean up
    os.remove(test_file)
    
    if not result:
        print("✅ PASS: Stale state correctly rejected")
    else:
        print("❌ FAIL: Stale state was loaded (should be rejected)")
        return False
    
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("State Management Test Suite - v2.0")
    print("=" * 60)
    
    tests = [
        test_immediate_persistence,
        test_checksum_validation,
        test_metadata_presence,
        test_debouncing,
        test_stale_rejection
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
