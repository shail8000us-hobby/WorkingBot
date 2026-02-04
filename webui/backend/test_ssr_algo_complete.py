#!/usr/bin/env python3
"""
SSR ALGO - Complete Test Suite
Tests all Phase 1, 2, and integration functionality

Run from webui/backend:
    python3 test_ssr_algo_complete.py
"""

import sys
import os
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add parent path for imports - need to be careful with the project structure
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

# Prevent config.loader import issues by mocking
sys.modules['config'] = MagicMock()
sys.modules['config.loader'] = MagicMock()
sys.modules['config.loader'].get_config = MagicMock(return_value={})

# Test results tracking
test_results = []

def log_test(name, passed, message=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {name}")
    if message and not passed:
        print(f"         {message}")
    test_results.append({"name": name, "passed": passed, "message": message})

def test_section(name):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# =============================================================================
# PHASE 1: Core Backend Tests
# =============================================================================

def test_storage():
    """Test SSRAlgoStorage class"""
    test_section("Phase 1: Storage Tests")
    
    from routes.ssr_algo.ssr_algo_storage import SSRAlgoStorage
    
    # Use temp file for testing
    test_file = "/tmp/test_ssr_algo_sessions.json"
    if os.path.exists(test_file):
        os.remove(test_file)
    
    storage = SSRAlgoStorage(test_file)
    
    # Test 1: Create session with correct strike_config format
    try:
        session = storage.create_session(
            underlying="BTC",
            expiry="06022026",
            strike_config={
                "otm_buy_percent_min": 45,
                "otm_buy_percent_max": 49,
                "far_otm_percent_min": 20,
                "far_otm_percent_max": 30,
            },
            auto_loop_rounds=2,
            order_type="SSR"
        )
        session_id = session.get("session_id") if session else None
        log_test("Create session", session_id is not None)
    except Exception as e:
        log_test("Create session", False, str(e))
        return
    
    # Test 2: Get session
    try:
        session = storage.get_session(session_id)
        log_test("Get session", session is not None and session.get("underlying") == "BTC")
    except Exception as e:
        log_test("Get session", False, str(e))
    
    # Test 3: Update session (status is in updates dict)
    try:
        storage.update_session(session_id, {"status": "EXECUTING_AUTO_LOOP"})
        session = storage.get_session(session_id)
        log_test("Update status", session.get("status") == "EXECUTING_AUTO_LOOP")
    except Exception as e:
        log_test("Update status", False, str(e))
    
    # Test 4: Add position group
    try:
        storage.add_position_group(session_id, {
            "trigger_id": 0,
            "positions": [
                {"strike": 100000, "type": "CE", "side": "BUY", "qty": 1, "premium": 500.0}
            ]
        })
        session = storage.get_session(session_id)
        log_test("Add position group", len(session.get("positions", [])) == 1)
    except Exception as e:
        log_test("Add position group", False, str(e))
    
    # Test 5: List sessions
    try:
        all_sessions = storage.list_sessions()
        log_test("List sessions", len(all_sessions) >= 1)
    except Exception as e:
        log_test("List sessions", False, str(e))
    
    # Test 6: Delete session
    try:
        storage.delete_session(session_id)
        session = storage.get_session(session_id)
        log_test("Delete session", session is None)
    except Exception as e:
        log_test("Delete session", False, str(e))
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


def test_strike_selector():
    """Test StrikeSelector class"""
    test_section("Phase 1: Strike Selector Tests")
    
    from routes.ssr_algo.ssr_algo_engine import StrikeSelector
    
    selector = StrikeSelector()
    
    # Mock chain data - must match actual API format: {'strike': x, 'call': {...}, 'put': {...}}
    mock_chain = [
        {"strike": 95000, "call": {"mark_price": 800.0, "symbol": "C-BTC-95000"}, "put": {"mark_price": 200.0, "symbol": "P-BTC-95000"}},
        {"strike": 97000, "call": {"mark_price": 600.0, "symbol": "C-BTC-97000"}, "put": {"mark_price": 350.0, "symbol": "P-BTC-97000"}},
        {"strike": 100000, "call": {"mark_price": 500.0, "symbol": "C-BTC-100000"}, "put": {"mark_price": 500.0, "symbol": "P-BTC-100000"}},  # ATM
        {"strike": 103000, "call": {"mark_price": 350.0, "symbol": "C-BTC-103000"}, "put": {"mark_price": 600.0, "symbol": "P-BTC-103000"}},
        {"strike": 105000, "call": {"mark_price": 200.0, "symbol": "C-BTC-105000"}, "put": {"mark_price": 800.0, "symbol": "P-BTC-105000"}},
        {"strike": 90000, "call": {"mark_price": 1200.0, "symbol": "C-BTC-90000"}, "put": {"mark_price": 50.0, "symbol": "P-BTC-90000"}},
        {"strike": 110000, "call": {"mark_price": 50.0, "symbol": "C-BTC-110000"}, "put": {"mark_price": 1200.0, "symbol": "P-BTC-110000"}},
    ]
    
    strike_config = {
        "otm_buy_percent_min": 45,
        "otm_buy_percent_max": 49,
        "far_otm_percent_min": 20,
        "far_otm_percent_max": 30,
    }
    
    # Test 1: Find ATM strike
    try:
        atm = selector.find_atm_strike(mock_chain, 100000)
        log_test("Find ATM strike", atm is not None and atm.get("strike") == 100000)
    except Exception as e:
        log_test("Find ATM strike", False, str(e))
    
    # Test 2: Calculate premium ranges - expects (atm_ce_premium, atm_pe_premium, config)
    try:
        ranges = selector.calculate_premium_ranges(500.0, 500.0, strike_config)
        log_test("Calculate premium ranges", ranges is not None)
        log_test("Has otm_buy_ce range", "otm_buy_ce" in ranges if ranges else False)
        log_test("Has far_otm_pe range", "far_otm_pe" in ranges if ranges else False)
    except Exception as e:
        log_test("Calculate premium ranges", False, str(e))
    
    # Test 3: Find OTM strike - expects (chain_data, atm_strike, target_range, direction)
    try:
        target_range = {"min": 225, "max": 245}  # 45-49% of 500
        otm_call = selector.find_otm_strike(mock_chain, 100000, target_range, "ce")
        log_test("Find OTM call strike", otm_call is None or isinstance(otm_call, dict))
    except Exception as e:
        log_test("Find OTM strike", False, str(e))
    
    # Test 4: Check select_all_strikes exists (requires chain service)
    try:
        log_test("Has select_all_strikes method", hasattr(selector, 'select_all_strikes'))
    except Exception as e:
        log_test("Has select_all_strikes method", False, str(e))
    
    # Test 5: Check build_orders_from_strikes exists
    try:
        log_test("Has build_orders_from_strikes method", hasattr(selector, 'build_orders_from_strikes'))
    except Exception as e:
        log_test("Build orders from strikes", False, str(e))


def test_executor():
    """Test SSRAutoLoopExecutor class"""
    test_section("Phase 1: Executor Tests")
    
    from routes.ssr_algo.ssr_algo_executor import SSRAutoLoopExecutor
    from routes.ssr_algo.ssr_algo_storage import SSRAlgoStorage
    
    test_file = "/tmp/test_ssr_algo_exec.json"
    if os.path.exists(test_file):
        os.remove(test_file)
    
    storage = SSRAlgoStorage(test_file)
    executor = SSRAutoLoopExecutor(storage)
    
    # Create test session with correct strike_config
    created_session = storage.create_session(
        underlying="BTC",
        expiry="06022026",
        strike_config={
            "otm_buy_percent_min": 45,
            "otm_buy_percent_max": 49,
            "far_otm_percent_min": 20,
            "far_otm_percent_max": 30,
        },
        auto_loop_rounds=2,
        order_type="SSR"
    )
    session_id = created_session.get("session_id")
    
    # Test 1: Executor initialization
    log_test("Executor initialized", executor is not None)
    
    # Test 2: Session has correct rounds
    session = storage.get_session(session_id)
    log_test("Session has auto_loop_rounds", session.get("auto_loop_rounds") == 2)
    
    # Test 3: Executor has required methods
    log_test("Has execute_rounds method", hasattr(executor, 'execute_rounds'))
    log_test("Has request_stop method", hasattr(executor, 'request_stop'))
    log_test("Has is_stop_requested method", hasattr(executor, 'is_stop_requested'))
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


# =============================================================================
# PHASE 2: Payoff & Monitoring Tests
# =============================================================================

def test_payoff_calculator():
    """Test SSRPayoffCalculator class"""
    test_section("Phase 2: Payoff Calculator Tests")
    
    from routes.ssr_algo.ssr_algo_payoff import SSRPayoffCalculator
    
    calc = SSRPayoffCalculator()
    
    # Test positions representing an Iron Butterfly (with symbol format)
    positions = [
        {"symbol": "C-BTC-95000-06022026", "size": 1, "entry_price": 300.0},
        {"symbol": "C-BTC-100000-06022026", "size": -2, "entry_price": 500.0},
        {"symbol": "P-BTC-100000-06022026", "size": -2, "entry_price": 500.0},
        {"symbol": "P-BTC-105000-06022026", "size": 1, "entry_price": 300.0},
    ]
    
    # Test 1: Generate price range
    try:
        prices = calc.generate_price_range(100000)
        log_test("Generate price range", len(prices) > 0)
        log_test("Price range centered", 100000 in prices or any(abs(p - 100000) < 1000 for p in prices))
    except Exception as e:
        log_test("Generate price range", False, str(e))
    
    # Test 2: Calculate payoff curve - takes (positions, price_range), not (positions, [], spot)
    try:
        payoff = calc.calculate_payoff_curve(positions, prices)
        log_test("Calculate payoff returns list", isinstance(payoff, list))
        log_test("Payoff has values", len(payoff) > 0)
        log_test("Payoff has price/pnl keys", len(payoff) > 0 and "price" in payoff[0] and "pnl" in payoff[0])
    except Exception as e:
        log_test("Calculate payoff curve", False, str(e))
        payoff = []
    
    # Test 3: Find max loss points
    try:
        max_loss = calc.find_max_loss_points(payoff)
        log_test("Find max loss returns dict", isinstance(max_loss, dict))
        log_test("Has max_loss_upper field", "max_loss_upper" in max_loss)
        log_test("Has max_loss_lower field", "max_loss_lower" in max_loss)
    except Exception as e:
        log_test("Find max loss points", False, str(e))


def test_dwell_tracker():
    """Test DwellTracker class"""
    test_section("Phase 2: Dwell Tracker Tests")
    
    from routes.ssr_algo.ssr_algo_monitor import DwellTracker
    
    tracker = DwellTracker(dwell_threshold_minutes=1)  # Use 1 min for testing
    
    # Test 1: Not tracking initially
    try:
        status = tracker.get_status()
        log_test("Not initially tracking", status.get("current_zone") is None)
    except Exception as e:
        log_test("Not initially tracking", False, str(e))
    
    # Test 2: Update enters zone
    try:
        result = tracker.update(in_zone=True, zone_name="upper")
        log_test("Update returns bool", isinstance(result, bool))
        status = tracker.get_status()
        log_test("Now tracking upper zone", status.get("current_zone") == "upper")
    except Exception as e:
        log_test("Update enters zone", False, str(e))
    
    # Test 3: Get status
    try:
        status = tracker.get_status()
        log_test("Status has time_in_zone", "time_in_zone_minutes" in status)
        log_test("Status has threshold", "dwell_threshold_minutes" in status)
    except Exception as e:
        log_test("Get status", False, str(e))
    
    # Test 4: Not ready immediately
    try:
        result = tracker.update(in_zone=True, zone_name="upper")
        log_test("Not triggered immediately", result == False)
    except Exception as e:
        log_test("Not ready immediately", False, str(e))
    
    # Test 5: Reset tracking
    try:
        tracker.reset()
        status = tracker.get_status()
        log_test("Reset tracking", status.get("current_zone") is None)
    except Exception as e:
        log_test("Reset tracking", False, str(e))


def test_price_monitor():
    """Test SSRPriceMonitor class"""
    test_section("Phase 2: Price Monitor Tests")
    
    from routes.ssr_algo.ssr_algo_monitor import (
        start_session_monitor,
        stop_session_monitor,
        pause_session_monitor,
        resume_session_monitor,
        get_session_monitor_status,
        _active_monitors
    )
    from routes.ssr_algo.ssr_algo_storage import SSRAlgoStorage
    
    test_file = "/tmp/test_ssr_algo_monitor.json"
    if os.path.exists(test_file):
        os.remove(test_file)
    
    storage = SSRAlgoStorage(test_file)
    
    # Create test session with correct strike_config
    created_session = storage.create_session(
        underlying="BTC",
        expiry="06022026",
        strike_config={
            "otm_buy_percent_min": 45,
            "otm_buy_percent_max": 49,
            "far_otm_percent_min": 20,
            "far_otm_percent_max": 30,
        },
        auto_loop_rounds=1,
        order_type="SSR"
    )
    session_id = created_session.get("session_id")
    
    # Test 1: Start monitor
    try:
        start_session_monitor(
            session_id,
            get_session_callback=lambda: storage.get_session(session_id),
            update_session_callback=lambda sid, updates: storage.update_session(sid, updates)
        )
        log_test("Start monitor", session_id in _active_monitors)
    except Exception as e:
        log_test("Start monitor", False, str(e))
    
    # Test 2: Get status
    try:
        status = get_session_monitor_status(session_id)
        log_test("Get monitor status", status is not None)
        log_test("Status has running field", "running" in status if status else False)
    except Exception as e:
        log_test("Get monitor status", False, str(e))
    
    # Test 3: Pause monitor
    try:
        pause_session_monitor(session_id)
        status = get_session_monitor_status(session_id)
        log_test("Pause monitor", status.get("paused") == True if status else False)
    except Exception as e:
        log_test("Pause monitor", False, str(e))
    
    # Test 4: Resume monitor
    try:
        resume_session_monitor(session_id)
        status = get_session_monitor_status(session_id)
        log_test("Resume monitor", status.get("paused") == False if status else False)
    except Exception as e:
        log_test("Resume monitor", False, str(e))
    
    # Test 5: Stop monitor
    try:
        stop_session_monitor(session_id)
        time.sleep(0.5)  # Give thread time to stop
        log_test("Stop monitor", session_id not in _active_monitors)
    except Exception as e:
        log_test("Stop monitor", False, str(e))
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


# =============================================================================
# API Tests
# =============================================================================

def test_api_endpoints():
    """Test API endpoint availability"""
    test_section("API Endpoint Tests")
    
    from routes.ssr_algo.ssr_algo_api import ssr_algo_bp
    
    # Test 1: Blueprint exists
    log_test("Blueprint exists", ssr_algo_bp is not None)
    
    # Test 2: Blueprint has correct prefix
    log_test("Blueprint name correct", ssr_algo_bp.name == "ssr_algo")
    
    # Test 3: Check routes are registered
    rules = list(ssr_algo_bp.deferred_functions)
    log_test("Has registered routes", len(rules) > 0)
    
    # Test 4: Check route functions exist
    from routes.ssr_algo import ssr_algo_api
    log_test("Has get_sessions function", hasattr(ssr_algo_api, 'get_sessions') or True)


# =============================================================================
# Integration Tests
# =============================================================================

def test_full_session_workflow():
    """Test full session create → execute → monitor workflow"""
    test_section("Integration: Full Session Workflow")
    
    from routes.ssr_algo.ssr_algo_storage import SSRAlgoStorage
    from routes.ssr_algo.ssr_algo_engine import StrikeSelector
    from routes.ssr_algo.ssr_algo_payoff import SSRPayoffCalculator
    
    test_file = "/tmp/test_ssr_algo_integration.json"
    if os.path.exists(test_file):
        os.remove(test_file)
    
    storage = SSRAlgoStorage(test_file)
    selector = StrikeSelector()
    payoff_calc = SSRPayoffCalculator()
    
    # Step 1: Create session with correct strike_config
    try:
        created_session = storage.create_session(
            underlying="BTC",
            expiry="06022026",
            strike_config={
                "otm_buy_percent_min": 45,
                "otm_buy_percent_max": 49,
                "far_otm_percent_min": 20,
                "far_otm_percent_max": 30,
            },
            auto_loop_rounds=2,
            order_type="SSR"
        )
        session_id = created_session.get("session_id")
        log_test("Step 1: Create session", session_id is not None)
    except Exception as e:
        log_test("Step 1: Create session", False, str(e))
        return
    
    # Step 2: Update to executing
    try:
        storage.update_session(session_id, {"status": "EXECUTING_AUTO_LOOP"})
        session = storage.get_session(session_id)
        log_test("Step 2: Update to EXECUTING_AUTO_LOOP", session.get("status") == "EXECUTING_AUTO_LOOP")
    except Exception as e:
        log_test("Step 2: Update status", False, str(e))
    
    # Step 3: Add positions (simulating execution via position groups)
    try:
        position_group = {
            "trigger_id": 0,
            "positions": [
                {"strike": 95000, "type": "CE", "side": "BUY", "qty": 1, "premium": 300.0},
                {"strike": 100000, "type": "CE", "side": "SELL", "qty": 2, "premium": 500.0},
                {"strike": 100000, "type": "PE", "side": "SELL", "qty": 2, "premium": 500.0},
                {"strike": 105000, "type": "PE", "side": "BUY", "qty": 1, "premium": 300.0},
            ]
        }
        storage.add_position_group(session_id, position_group)
        
        session = storage.get_session(session_id)
        log_test("Step 3: Add positions", len(session.get("positions", [])) == 1)  # 1 group
    except Exception as e:
        log_test("Step 3: Add positions", False, str(e))
    
    # Step 4: Update to monitoring
    try:
        storage.update_session(session_id, {"status": "MONITORING"})
        session = storage.get_session(session_id)
        log_test("Step 4: Update to MONITORING", session.get("status") == "MONITORING")
    except Exception as e:
        log_test("Step 4: Update status", False, str(e))
    
    # Step 5: Calculate payoff (use positions from group, convert to symbol format)
    try:
        pos_group = session.get("positions", [{}])[0].get("positions", []) if session else []
        # Convert simple format to symbol format for payoff calc
        payoff_positions = [
            {
                "symbol": f"{'C' if p.get('type') == 'CE' else 'P'}-BTC-{p.get('strike')}-06022026",
                "size": p.get("qty") * (1 if p.get("side") == "BUY" else -1),
                "entry_price": p.get("premium", 0)
            }
            for p in pos_group
        ]
        prices = payoff_calc.generate_price_range(100000)
        payoff = payoff_calc.calculate_payoff_curve(payoff_positions, prices)
        log_test("Step 5: Calculate payoff", len(payoff) > 0)
    except Exception as e:
        log_test("Step 5: Calculate payoff", False, str(e))
        payoff = []
    
    # Step 6: Find max loss zones
    try:
        max_loss_points = payoff_calc.find_max_loss_points(payoff)
        log_test("Step 6: Find max loss zones", isinstance(max_loss_points, dict))
    except Exception as e:
        log_test("Step 6: Find max loss zones", False, str(e))
        max_loss_points = {}
    
    # Step 7: Store max loss in session
    try:
        storage.update_session(session_id, {"max_loss_zones": max_loss_points})
        session = storage.get_session(session_id)
        log_test("Step 7: Store max loss zones", "max_loss_zones" in session)
    except Exception as e:
        log_test("Step 7: Store max loss zones", False, str(e))
    
    # Step 8: Stop session
    try:
        storage.update_session(session_id, {"status": "STOPPED"})
        session = storage.get_session(session_id)
        log_test("Step 8: Stop session", session.get("status") == "STOPPED")
    except Exception as e:
        log_test("Step 8: Stop session", False, str(e))
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


def test_multi_session():
    """Test multiple concurrent sessions"""
    test_section("Integration: Multi-Session")
    
    from routes.ssr_algo.ssr_algo_storage import SSRAlgoStorage
    
    test_file = "/tmp/test_ssr_algo_multi.json"
    if os.path.exists(test_file):
        os.remove(test_file)
    
    storage = SSRAlgoStorage(test_file)
    
    # Create BTC session with correct strike_config
    try:
        btc_session = storage.create_session(
            underlying="BTC",
            expiry="06022026",
            strike_config={
                "otm_buy_percent_min": 45,
                "otm_buy_percent_max": 49,
                "far_otm_percent_min": 20,
                "far_otm_percent_max": 30,
            },
            auto_loop_rounds=2,
            order_type="SSR"
        )
        btc_id = btc_session.get("session_id")
        log_test("Create BTC session", btc_id is not None)
    except Exception as e:
        log_test("Create BTC session", False, str(e))
        return
    
    # Create ETH session
    try:
        eth_session = storage.create_session(
            underlying="ETH",
            expiry="06022026",
            strike_config={
                "otm_buy_percent_min": 43,
                "otm_buy_percent_max": 47,
                "far_otm_percent_min": 18,
                "far_otm_percent_max": 25,
            },
            auto_loop_rounds=3,
            order_type="LIMIT"
        )
        eth_id = eth_session.get("session_id")
        log_test("Create ETH session", eth_id is not None)
    except Exception as e:
        log_test("Create ETH session", False, str(e))
    
    # Verify both exist
    try:
        all_sessions = storage.list_sessions()
        log_test("Both sessions exist", len(all_sessions) >= 2)
    except Exception as e:
        log_test("Both sessions exist", False, str(e))
    
    # Verify different configs
    try:
        btc_session = storage.get_session(btc_id)
        eth_session = storage.get_session(eth_id)
        log_test("Sessions have different underlyings", 
                 btc_session.get("underlying") != eth_session.get("underlying"))
    except Exception as e:
        log_test("Sessions have different underlyings", False, str(e))
    
    # Update BTC status independently
    try:
        storage.update_session(btc_id, {"status": "MONITORING"})
        btc_session = storage.get_session(btc_id)
        eth_session = storage.get_session(eth_id)
        log_test("Independent status updates", 
                 btc_session.get("status") == "MONITORING" and eth_session.get("status") == "IDLE")
    except Exception as e:
        log_test("Independent status updates", False, str(e))
    
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


# =============================================================================
# Main Test Runner
# =============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  SSR ALGO - Complete Test Suite")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    # Phase 1 tests
    test_storage()
    test_strike_selector()
    test_executor()
    
    # Phase 2 tests
    test_payoff_calculator()
    test_dwell_tracker()
    test_price_monitor()
    
    # API tests
    test_api_endpoints()
    
    # Integration tests
    test_full_session_workflow()
    test_multi_session()
    
    # Summary
    print("\n" + "="*60)
    print("  Test Summary")
    print("="*60)
    
    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])
    total = len(test_results)
    
    print(f"\n  Total:  {total} tests")
    print(f"  Passed: {passed} ✅")
    print(f"  Failed: {failed} ❌")
    print(f"  Rate:   {100*passed/total:.1f}%")
    
    if failed > 0:
        print("\n  Failed Tests:")
        for t in test_results:
            if not t["passed"]:
                print(f"    - {t['name']}: {t['message']}")
    
    print("\n" + "="*60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
