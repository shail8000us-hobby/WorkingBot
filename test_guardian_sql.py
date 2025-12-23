#!/usr/bin/env python3
"""
Test Guardian SQL Signal System

Verifies:
1. EventStore has Guardian event types
2. Guardian can write signals to database
3. Signals can be queried from database
4. Latest signal retrieval works correctly
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.strategy.modules.event_store import EventStore, Event, EventType

def test_event_types():
    """Test 1: Verify Guardian event types exist"""
    print("=" * 70)
    print("TEST 1: Guardian Event Types")
    print("=" * 70)
    
    required_types = [
        'GUARDIAN_SIGNAL_GO',
        'GUARDIAN_SIGNAL_STOP',
        'GUARDIAN_CONFIG_CHANGED',
        'GUARDIAN_VOLATILITY_CHECK',
        'GUARDIAN_RISK_CHECK',
        'GUARDIAN_POSITION_CHECK',
        'GUARDIAN_LIQUIDATION_CHECK',
        'GUARDIAN_HEALTH_CHECK'
    ]
    
    for type_name in required_types:
        if hasattr(EventType, type_name):
            print(f"✅ {type_name}: {getattr(EventType, type_name).value}")
        else:
            print(f"❌ {type_name}: NOT FOUND")
            return False
    
    print("\n✅ All Guardian event types found!\n")
    return True


def test_database_write():
    """Test 2: Write Guardian signals to database"""
    print("=" * 70)
    print("TEST 2: Write Signals to Database")
    print("=" * 70)
    
    # Use test database
    db_path = 'test_guardian.db'
    event_store = EventStore(db_path)
    
    # Create test GO signal
    go_event = Event(
        event_id="test-go-001",
        event_type=EventType.GUARDIAN_SIGNAL_GO,
        timestamp=time.time(),
        correlation_id="test-correlation-go",
        aggregate_id="guardian",
        data={
            'signal': 'GO',
            'reason': 'All safety checks passed',
            'timestamp': time.time(),
            'details': {
                'iv': 28.5,
                'rv': 22.3,
                'spread': 85,
                'pnl_inr': -500,
                'position_size': 125
            }
        },
        metadata={
            'guardian_version': '1.0.0',
            'config_version': 'test123',
            'source': 'test_script'
        }
    )
    
    event_store.append_event(go_event)
    print(f"✅ GO signal written: {go_event.event_id}")
    
    # Create test STOP signal
    time.sleep(1)  # Wait 1 second
    
    stop_event = Event(
        event_id="test-stop-002",
        event_type=EventType.GUARDIAN_SIGNAL_STOP,
        timestamp=time.time(),
        correlation_id="test-correlation-stop",
        aggregate_id="guardian",
        data={
            'signal': 'STOP',
            'reason': 'High volatility detected',
            'timestamp': time.time(),
            'details': {
                'iv': 45.8,
                'rv': 38.2,
                'spread': 120
            }
        },
        metadata={
            'guardian_version': '1.0.0',
            'config_version': 'test123',
            'source': 'test_script'
        }
    )
    
    event_store.append_event(stop_event)
    print(f"✅ STOP signal written: {stop_event.event_id}")
    
    # Create config change event
    config_event = Event(
        event_id="test-config-003",
        event_type=EventType.GUARDIAN_CONFIG_CHANGED,
        timestamp=time.time(),
        correlation_id="test-correlation-config",
        aggregate_id="guardian",
        data={
            'old_config_version': 'test123',
            'new_config_version': 'test456',
            'max_iv': 35.0,
            'max_rv': 30.0
        },
        metadata={
            'source': 'test_script',
            'reason': 'webui_parameter_update'
        }
    )
    
    event_store.append_event(config_event)
    print(f"✅ Config change written: {config_event.event_id}")
    
    print("\n✅ All test events written to database!\n")
    return event_store


def test_query_signals(event_store):
    """Test 3: Query signals from database"""
    print("=" * 70)
    print("TEST 3: Query Signals from Database")
    print("=" * 70)
    
    # Query all Guardian signals (GO + STOP)
    signals = event_store.get_events_by_type(
        [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
        limit=10
    )
    
    print(f"Found {len(signals)} Guardian signals:")
    for signal in signals:
        print(f"  - {signal.event_type.value}: {signal.data['signal']} - {signal.data['reason']}")
        print(f"    Time: {signal.timestamp}")
        print(f"    Event ID: {signal.event_id}")
        print()
    
    print("✅ Query successful!\n")
    return signals


def test_latest_signal(event_store):
    """Test 4: Get latest signal (what trading bot will do)"""
    print("=" * 70)
    print("TEST 4: Get Latest Signal (Trading Bot Simulation)")
    print("=" * 70)
    
    # This is how trading bot will query
    latest_signals = event_store.get_events_by_type(
        [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
        limit=1
    )
    
    if not latest_signals:
        print("❌ No signal found!")
        return False
    
    latest = latest_signals[0]
    signal_age = time.time() - latest.timestamp
    
    print(f"Latest Signal:")
    print(f"  Event Type: {latest.event_type.value}")
    print(f"  Signal: {latest.data['signal']}")
    print(f"  Reason: {latest.data['reason']}")
    print(f"  Age: {signal_age:.2f} seconds")
    print(f"  Config Version: {latest.metadata.get('config_version')}")
    print(f"  Guardian Version: {latest.metadata.get('guardian_version')}")
    
    # Simulate trading bot decision
    if signal_age > 30:
        print(f"\n⚠️  Signal is STALE ({signal_age:.0f}s old) - Trading bot would HALT")
    else:
        if latest.data['signal'] == 'GO':
            print(f"\n🟢 Trading bot would EXECUTE STRATEGY")
        else:
            print(f"\n🔴 Trading bot would PAUSE (reason: {latest.data['reason']})")
    
    print("\n✅ Latest signal query successful!\n")
    return True


def test_config_changes(event_store):
    """Test 5: Query config change history"""
    print("=" * 70)
    print("TEST 5: Config Change History")
    print("=" * 70)
    
    config_changes = event_store.get_events_by_type(
        EventType.GUARDIAN_CONFIG_CHANGED,
        limit=10
    )
    
    print(f"Found {len(config_changes)} config changes:")
    for change in config_changes:
        print(f"  - Old: {change.data.get('old_config_version')} → New: {change.data.get('new_config_version')}")
        print(f"    Reason: {change.metadata.get('reason')}")
        print(f"    Time: {change.timestamp}")
        print()
    
    print("✅ Config change query successful!\n")
    return True


def cleanup_test_db():
    """Remove test database"""
    import os
    try:
        if os.path.exists('test_guardian.db'):
            os.remove('test_guardian.db')
        if os.path.exists('test_guardian.db-wal'):
            os.remove('test_guardian.db-wal')
        if os.path.exists('test_guardian.db-shm'):
            os.remove('test_guardian.db-shm')
        print("✅ Test database cleaned up\n")
    except Exception as e:
        print(f"⚠️  Could not clean up test database: {e}\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("🧪 GUARDIAN SQL SIGNAL SYSTEM TEST")
    print("=" * 70)
    print()
    
    try:
        # Test 1: Event types
        if not test_event_types():
            print("❌ Test 1 FAILED - Event types missing")
            return 1
        
        # Test 2: Database write
        event_store = test_database_write()
        
        # Test 3: Query signals
        signals = test_query_signals(event_store)
        
        # Test 4: Latest signal
        if not test_latest_signal(event_store):
            print("❌ Test 4 FAILED - Latest signal retrieval failed")
            return 1
        
        # Test 5: Config changes
        test_config_changes(event_store)
        
        # All tests passed!
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Guardian SQL Signal System is working correctly!")
        print("Next steps:")
        print("  1. Install watchdog: pip install watchdog")
        print("  2. Start Guardian bot to test live signal generation")
        print("  3. Check database: sqlite3 gridbot_events.db")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        cleanup_test_db()


if __name__ == '__main__':
    sys.exit(main())
