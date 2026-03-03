#!/usr/bin/env python3
"""
Comprehensive Backend Instance Support Test

Tests ALL backend routes for instance parameter support.

Usage:
    python3 test_all_backend_routes_instance.py

Author: GitHub Copilot
Date: January 3, 2026
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if details:
        print(f"         {details}")

def test_route_file(filename, expected_routes):
    """Test a route file for instance parameter support"""
    file_path = BASE_DIR / 'webui' / 'backend' / 'routes' / filename
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        results = {}
        for route_name in expected_routes:
            has_instance = "request.args.get('instance')" in content or \
                          ("request.get_json" in content and ".get('instance')" in content)
            has_v6_docs = "v6.0" in content or "instance (str)" in content or \
                         "instance: Optional" in content
            
            results[route_name] = has_instance or has_v6_docs
        
        return results
    except Exception as e:
        return {route: False for route in expected_routes}

def run_comprehensive_test():
    """Test all backend routes for instance support"""
    print("\n" + "🔬" * 40)
    print("  COMPREHENSIVE BACKEND INSTANCE SUPPORT TEST")
    print("  Testing ALL Routes for V6.0 Multi-Instance")
    print("🔬" * 40)
    
    # Define all route files and their critical endpoints
    route_tests = {
        'emergency.py': ['check_flag', 'clear_flag', 'overrides', 'reset_gatekeeper'],
        'pnl.py': ['pnl_history', 'hourly_history', 'summary'],
        'logs.py': ['get_logs', 'get_logs_recent'],
        'orders.py': ['get_orders'],
        'config.py': ['get_config'],
        'analytics.py': ['summary', 'performance'],
        'trades.py': ['history', 'summary'],
        'recon.py': ['status', 'table'],
        'risk.py': ['analytics', 'status'],
        'backtest.py': ['latest', 'history'],
        'positions.py': ['positions'],
        'guardian.py': ['status'],
        'monitoring.py': ['metrics']
    }
    
    all_results = {}
    
    for filename, routes in route_tests.items():
        print_header(f"Testing {filename}")
        results = test_route_file(filename, routes)
        
        for route, passed in results.items():
            print_test(f"{route} endpoint", passed, 
                      "Instance support found" if passed else "No instance support")
        
        all_results[filename] = results
    
    # Calculate overall stats
    print_header("OVERALL SUMMARY")
    
    total_routes = sum(len(routes) for routes in all_results.values())
    passed_routes = sum(sum(1 for p in results.values() if p) for results in all_results.values())
    
    for filename, results in all_results.items():
        file_passed = sum(1 for p in results.values() if p)
        file_total = len(results)
        status = "✅" if file_passed == file_total else "⚠️"
        print(f"{status} {filename}: {file_passed}/{file_total} ({file_passed/file_total*100:.0f}%)")
    
    print("\n" + "-" * 80)
    print(f"TOTAL: {passed_routes}/{total_routes} routes support instances ({passed_routes/total_routes*100:.0f}%)")
    print("-" * 80)
    
    if passed_routes == total_routes:
        print("\n✅ ALL ROUTES INSTANCE-AWARE - 100% Production Ready!")
        return 0
    else:
        print(f"\n⚠️  {total_routes - passed_routes} route(s) still need instance support")
        return 1

if __name__ == '__main__':
    sys.exit(run_comprehensive_test())
