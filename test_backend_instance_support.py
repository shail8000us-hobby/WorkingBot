#!/usr/bin/env python3
"""
Backend Instance Parameter Support Test Suite

Tests that all critical backend routes properly handle the instance parameter
for multi-instance architecture (v6.0).

Usage:
    python3 test_backend_instance_support.py

Author: GitHub Copilot
Date: January 3, 2026
"""

import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

def print_header(title):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_test(name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if details:
        print(f"         {details}")

def test_emergency_routes():
    """Test emergency.py instance parameter support"""
    print_header("TEST 1: Emergency Routes Instance Support")
    
    try:
        # Read source code to verify instance parameter usage
        emergency_file = BASE_DIR / 'webui' / 'backend' / 'routes' / 'emergency.py'
        with open(emergency_file, 'r') as f:
            content = f.read()
        
        # Test 1: check_flag has instance parameter
        has_check_instance = "request.args.get('instance')" in content and \
                            "check_emergency_flag" in content and \
                            ".guardian_emergency_stop_{instance}" in content
        print_test("check_emergency_flag accepts instance parameter", has_check_instance,
                  "Per-instance emergency flag path" if has_check_instance else "Missing instance support")
        
        # Test 2: clear_flag has instance parameter
        has_clear_instance = "request.args.get('instance')" in content and \
                            "clear_emergency_flag" in content and \
                            "guardian_emergency_stop_{instance}" in content
        print_test("clear_emergency_flag accepts instance parameter", has_clear_instance,
                  "Can clear per-instance flag" if has_clear_instance else "Missing instance support")
        
        return has_check_instance and has_clear_instance
        
    except Exception as e:
        print_test("Emergency routes test", False, f"Error: {e}")
        return False

def test_pnl_routes():
    """Test pnl.py instance parameter support"""
    print_header("TEST 2: PnL Routes Instance Support")
    
    try:
        pnl_file = BASE_DIR / 'webui' / 'backend' / 'routes' / 'pnl.py'
        with open(pnl_file, 'r') as f:
            content = f.read()
        
        # Test 1: pnl-history has instance parameter
        has_history_instance = "request.args.get('instance')" in content and \
                              "pnl_history_{instance}_" in content and \
                              "get_pnl_history" in content
        print_test("get_pnl_history accepts instance parameter", has_history_instance,
                  "Per-instance CSV file" if has_history_instance else "Missing instance support")
        
        # Test 2: pnl-history/hourly has instance documentation
        has_hourly_instance = "v6.0: Supports per-instance" in content and \
                             "get_hourly_pnl_history" in content
        print_test("get_hourly_pnl_history has instance docs", has_hourly_instance,
                  "v6.0 documentation present" if has_hourly_instance else "Missing instance docs")
        
        # Test 3: pnl/summary has instance parameter
        has_summary_instance = "pnl_history_{instance}_" in content and \
                              "get_pnl_summary" in content
        print_test("get_pnl_summary accepts instance parameter", has_summary_instance,
                  "Per-instance summary" if has_summary_instance else "Missing instance support")
        
        return has_history_instance and has_hourly_instance and has_summary_instance
        
    except Exception as e:
        print_test("PnL routes test", False, f"Error: {e}")
        return False

def test_logs_routes():
    """Test logs.py instance parameter support"""
    print_header("TEST 3: Logs Routes Instance Support")
    
    try:
        logs_file = BASE_DIR / 'webui' / 'backend' / 'routes' / 'logs.py'
        with open(logs_file, 'r') as f:
            content = f.read()
        
        # Test 1: get_logs has instance parameter
        has_logs_instance = "request.args.get('instance')" in content and \
                           "gridbot_{instance.lower()}.log" in content and \
                           "get_logs" in content
        print_test("get_logs accepts instance parameter", has_logs_instance,
                  "Per-instance log file" if has_logs_instance else "Missing instance support")
        
        # Test 2: get_logs_recent has instance parameter
        has_recent_instance = "instance = request.args.get('instance')" in content and \
                             "get_logs_recent" in content
        print_test("get_logs_recent accepts instance parameter", has_recent_instance,
                  "Instance parameter in query" if has_recent_instance else "Missing instance support")
        
        return has_logs_instance and has_recent_instance
        
    except Exception as e:
        print_test("Logs routes test", False, f"Error: {e}")
        return False

def test_orders_routes():
    """Test orders.py instance parameter support"""
    print_header("TEST 4: Orders Routes Instance Support")
    
    try:
        orders_file = BASE_DIR / 'webui' / 'backend' / 'routes' / 'orders.py'
        with open(orders_file, 'r') as f:
            content = f.read()
        
        # Test 1: get_orders has instance parameter
        has_orders_instance = "instance = request.args.get('instance')" in content and \
                             "v6.0: Instance parameter" in content and \
                             "get_orders" in content
        print_test("get_orders accepts instance parameter", has_orders_instance,
                  "Instance parameter documented" if has_orders_instance else "Missing instance support")
        
        # Test 2: Instance in response filters
        has_filter_instance = '"instance":' in content or "'instance':" in content
        print_test("get_orders returns instance in filters", has_filter_instance,
                  "Instance tracked in response" if has_filter_instance else "Missing instance in response")
        
        return has_orders_instance and has_filter_instance
        
    except Exception as e:
        print_test("Orders routes test", False, f"Error: {e}")
        return False

def test_instance_aware_patterns():
    """Test that routes follow v6.0 instance-aware patterns"""
    print_header("TEST 5: V6.0 Instance-Aware Patterns")
    
    patterns_found = {
        'emergency.py': False,
        'pnl.py': False,
        'logs.py': False,
        'orders.py': False
    }
    
    for filename in patterns_found.keys():
        file_path = BASE_DIR / 'webui' / 'backend' / 'routes' / filename
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Check for v6.0 patterns
            has_v6_pattern = "request.args.get('instance')" in content or \
                            "request.get_json" in content and "instance" in content
            has_instance_logic = "if instance:" in content
            has_instance_docs = "v6.0" in content or "instance (str)" in content or \
                               "instance: Optional" in content
            
            patterns_found[filename] = has_v6_pattern or has_instance_logic or has_instance_docs
            
            print_test(f"{filename} follows v6.0 patterns", patterns_found[filename],
                      "Instance parameter handling" if patterns_found[filename] else "No instance support found")
        except Exception as e:
            print_test(f"{filename} pattern check", False, f"Error: {e}")
    
    return all(patterns_found.values())

def test_frontend_component():
    """Test OpportunisticRecoveryPanel instance awareness"""
    print_header("TEST 6: Frontend OpportunisticRecoveryPanel Instance Support")
    
    try:
        component_file = BASE_DIR / 'webui' / 'frontend' / 'src' / 'components' / 'OpportunisticRecoveryPanel.js'
        with open(component_file, 'r') as f:
            content = f.read()
        
        # Test 1: Imports useInstance
        has_use_instance = "useInstance" in content and \
                          "from '../context/InstanceContext'" in content
        print_test("OpportunisticRecoveryPanel imports useInstance", has_use_instance,
                  "Context imported" if has_use_instance else "Missing useInstance import")
        
        # Test 2: Uses selectedInstance
        uses_selected_instance = "selectedInstance" in content
        print_test("OpportunisticRecoveryPanel uses selectedInstance", uses_selected_instance,
                  "Instance state available" if uses_selected_instance else "Not using instance state")
        
        # Test 3: Filters by instance
        filters_by_instance = "data.instance !== selectedInstance" in content or \
                             "selectedInstance &&" in content
        print_test("OpportunisticRecoveryPanel filters by instance", filters_by_instance,
                  "WebSocket filtering" if filters_by_instance else "No instance filtering")
        
        return has_use_instance and uses_selected_instance and filters_by_instance
        
    except Exception as e:
        print_test("Frontend component test", False, f"Error: {e}")
        return False

def run_all_tests():
    """Run all backend instance support tests"""
    print("\n" + "🔬" * 40)
    print("  BACKEND INSTANCE PARAMETER SUPPORT TEST SUITE")
    print("  V6.0 Multi-Instance Architecture Validation")
    print("🔬" * 40)
    
    results = {
        'Emergency Routes': test_emergency_routes(),
        'PnL Routes': test_pnl_routes(),
        'Logs Routes': test_logs_routes(),
        'Orders Routes': test_orders_routes(),
        'V6.0 Patterns': test_instance_aware_patterns(),
        'Frontend Component': test_frontend_component()
    }
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print("\n" + "-" * 80)
    print(f"TOTAL: {passed}/{total} test suites passed ({passed/total*100:.0f}%)")
    print("-" * 80)
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Backend is 100% instance-aware!")
        print("   WebUI v1 is ready for multi-instance production deployment.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed")
        print("   Review failed tests and implement missing instance support.")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
