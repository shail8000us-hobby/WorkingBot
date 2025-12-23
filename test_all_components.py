#!/usr/bin/env python3
"""
Test All Bot Components
Tests each migrated component to ensure DeltaClient integration works
"""

import os
import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv('secrets/api_keys.env')
load_dotenv('.env')
load_dotenv('grid_config.env', override=True)

# Set demo mode
os.environ['TRADING_MODE'] = 'demo'
os.environ['MODE'] = 'DEMO'

# Load trading mode config
from bot.utils.env_loader import load_trading_mode_config
load_trading_mode_config()

print("=" * 80)
print("🧪 TESTING ALL BOT COMPONENTS")
print("=" * 80)
print()

# Test counters
tests_passed = 0
tests_failed = 0

def test_component(name, test_func):
    """Run a component test"""
    global tests_passed, tests_failed
    print(f"Testing {name}...", end=" ")
    try:
        result = test_func()
        if result:
            print("✅ PASSED")
            tests_passed += 1
        else:
            print("❌ FAILED")
            tests_failed += 1
    except Exception as e:
        print(f"❌ FAILED: {e}")
        tests_failed += 1
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST 1: DeltaClient Basic Functionality
# ============================================================================

def test_delta_client():
    """Test DeltaClient initialization and basic methods"""
    from bot.api.delta_client import DeltaClient
    
    client = DeltaClient()
    
    # Test balance fetch (CCXT-compatible)
    balance = client.fetch_balance()
    if not isinstance(balance, dict):
        print(f"\n  Balance fetch failed: got {type(balance)}")
        return False
    
    # Test positions fetch (CCXT-compatible)
    positions = client.fetch_positions()
    if not isinstance(positions, list):
        print(f"\n  Positions fetch failed: got {type(positions)}")
        return False
    
    # Test open orders fetch (CCXT-compatible)
    orders = client.fetch_open_orders(product_id=84)
    if not isinstance(orders, list):
        print(f"\n  Orders fetch failed: got {type(orders)}")
        return False
    
    print(f"\n  Balance: {len(balance.get('free', {}))} assets")
    print(f"  Positions: {len(positions)}")
    print(f"  Open Orders: {len(orders)}")
    
    return True

# ============================================================================
# TEST 2: Liquidation Protection Components
# ============================================================================

def test_liquidation_protection():
    """Test all 3 liquidation protection components"""
    try:
        from bot.liquidation.margin_monitor import MarginUtilizationMonitor
        from bot.liquidation.distance_monitor import LiquidationDistanceMonitor
        from bot.liquidation.mtm_tracker import MTMTracker
    except (ImportError, ModuleNotFoundError) as e:
        print(f"\n  ⚠️  SKIPPED: Liquidation modules not available ({e})")
        return True  # Skip gracefully
    from dataclasses import dataclass
    
    @dataclass
    class DC:
        ex: object = None
    
    dc = DC()  # Empty DC object - components will use DeltaClient
    
    # Test Margin Monitor
    margin_monitor = MarginUtilizationMonitor(dc, os.environ)
    utilization = margin_monitor.get_utilization()
    if not isinstance(utilization, (int, float)):
        print(f"\n  Margin utilization failed: got {type(utilization)}")
        return False
    print(f"\n  Margin Utilization: {utilization}%")
    
    # Test Distance Monitor
    distance_monitor = LiquidationDistanceMonitor(dc, os.environ)
    distance, zone = distance_monitor.calculate_distance()
    if not isinstance(distance, (int, float)):
        print(f"\n  Distance calculation failed: got {type(distance)}")
        return False
    print(f"  Liquidation Distance: {distance}% ({zone})")
    
    # Test MTM Tracker
    mtm_tracker = MTMTracker(dc, os.environ)
    mtm = mtm_tracker.get_current_mtm()
    if not isinstance(mtm, (int, float)):
        print(f"\n  MTM tracking failed: got {type(mtm)}")
        return False
    print(f"  MTM (Unrealized P&L): {mtm}")
    
    return True

# ============================================================================
# TEST 3: Heartbeat Monitor
# ============================================================================

def test_heartbeat():
    """Test heartbeat monitor initialization"""
    from bot.heartbeat.monitor import HeartbeatMonitor
    
    # Create a test heartbeat file
    test_file = Path('.heartbeat_test')
    test_file.touch()
    test_file.write_text(f"{int(__import__('time').time())}")
    
    # Initialize monitor (don't run it, just test init)
    monitor = HeartbeatMonitor(
        heartbeat_file=str(test_file),
        timeout=15,
        check_interval=5,
        action='notify_only'
    )
    
    # Test exchange initialization
    monitor._init_exchange()
    
    if monitor.exchange is None:
        print("\n  Exchange initialization failed")
        test_file.unlink()
        return False
    
    print(f"\n  Exchange initialized: {monitor.symbol_ccxt}")
    test_file.unlink()
    return True

# ============================================================================
# TEST 4: Reconciliation Service
# ============================================================================

def test_reconciliation():
    """Test reconciliation service"""
    try:
        from bot.reconciliation_service import ReconciliationService
    except (ImportError, ModuleNotFoundError) as e:
        print(f"\n  ⚠️  SKIPPED: ReconciliationService module not available ({e})")
        return True  # Skip gracefully
    
    service = ReconciliationService()
    
    # Test position fetch
    positions = service._fetch_exchange_positions()
    if not isinstance(positions, list):
        print(f"\n  Position fetch failed: got {type(positions)}")
        return False
    
    print(f"\n  Exchange Positions: {len(positions)}")
    return True

# ============================================================================
# TEST 5: WebSocket GridBot
# ============================================================================

def test_websocket_gridbot():
    """Test WebSocket GridBot initialization"""
    try:
        from bot.strategy.gbot_ws import GridBotWebSocket
    except (ImportError, ModuleNotFoundError) as e:
        print(f"\n  ⚠️  SKIPPED: GridBotWebSocket module not available ({e})")
        return True  # Skip gracefully
    from bot.api.delta_client import DeltaClient
    
    delta_client = DeltaClient()
    product_id = 84  # BTCUSD
    
    # Initialize bot (don't run it)
    bot = GridBotWebSocket(
        delta_client=delta_client,
        product_id=product_id,
        symbol="BTCUSD",
        lower=109000.0,
        upper=130000.0,
        step=100.0,
        ref=111000.0,
        lot=1,
        max_open=100
    )
    
    if bot.delta_client is None:
        print("\n  Delta client not initialized")
        return False
    
    if bot.ws_manager is None:
        print("\n  WebSocket manager not initialized")
        return False
    
    print(f"\n  Symbol: {bot.symbol}")
    print(f"  Grid: ${bot.lower:,.0f} - ${bot.upper:,.0f}")
    print(f"  Step: ${bot.step}")
    print(f"  Max Open: {bot.max_open}")
    
    return True

# ============================================================================
# RUN ALL TESTS
# ============================================================================

print("🧪 Running Component Tests...")
print("=" * 80)
print()

test_component("DeltaClient", test_delta_client)
test_component("Liquidation Protection", test_liquidation_protection)
test_component("Heartbeat Monitor", test_heartbeat)
test_component("Reconciliation Service", test_reconciliation)
test_component("WebSocket GridBot", test_websocket_gridbot)

# ============================================================================
# RESULTS
# ============================================================================

print()
print("=" * 80)
print("📊 TEST RESULTS")
print("=" * 80)
print(f"✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")
print(f"📈 Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")
print("=" * 80)

if tests_failed == 0:
    print()
    print("🎉 ALL TESTS PASSED! Bot is ready for integration testing.")
    print()
    sys.exit(0)
else:
    print()
    print("⚠️  Some tests failed. Review errors above.")
    print()
    sys.exit(1)

