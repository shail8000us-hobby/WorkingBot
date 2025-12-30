#!/usr/bin/env python3
"""
WebUI Integration Verification - Delta Exchange India Improvements
===================================================================

This script verifies that all Delta Exchange India improvements are properly
integrated with the WebUI and accessible to users.

Date: December 28, 2025
"""

import json
import requests
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
WEBUI_URL = "http://localhost:5555"


def check_guardian_health_file():
    """Verify Guardian health file includes liquidation metrics"""
    print("\n" + "=" * 80)
    print("TEST 1: Guardian Health File")
    print("=" * 80)
    
    health_file = BASE_DIR / '.guardian_health'
    
    if not health_file.exists():
        print("❌ FAIL: .guardian_health file not found")
        return False
    
    with open(health_file, 'r') as f:
        health_data = json.load(f)
    
    # Check required fields
    required_fields = {
        'guardian_version': str,
        'signal': str,
        'positions': dict,
        'liquidation': dict
    }
    
    passed = True
    for field, expected_type in required_fields.items():
        if field not in health_data:
            print(f"❌ FAIL: Missing field '{field}'")
            passed = False
        elif not isinstance(health_data[field], expected_type):
            print(f"❌ FAIL: Field '{field}' has wrong type (expected {expected_type})")
            passed = False
        else:
            print(f"✅ PASS: Field '{field}' present and correct type")
    
    # Check liquidation metrics specifically
    print("\n📊 Liquidation Metrics:")
    liquidation = health_data.get('liquidation', {})
    required_liq_fields = ['distance', 'critical', 'warning', 'details_count', 'bankruptcy_distance']
    
    for field in required_liq_fields:
        if field in liquidation:
            print(f"   ✅ {field}: {liquidation[field]}")
        else:
            print(f"   ❌ Missing: {field}")
            passed = False
    
    if passed:
        print("\n✅ TEST 1 PASSED: Guardian health file properly formatted")
    else:
        print("\n❌ TEST 1 FAILED: Guardian health file missing required fields")
    
    return passed


def check_api_liquidation_metrics():
    """Verify /api/positions/liquidation-metrics endpoint"""
    print("\n" + "=" * 80)
    print("TEST 2: API - Liquidation Metrics Endpoint")
    print("=" * 80)
    
    url = f"{WEBUI_URL}/api/positions/liquidation-metrics"
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            print(f"❌ FAIL: HTTP status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ FAIL: API returned success=false")
            print(f"Response: {json.dumps(data, indent=2)}")
            return False
        
        # Check required response fields
        required_fields = [
            'liquidation_distance',
            'liquidation_critical',
            'liquidation_warning',
            'bankruptcy_distance',
            'positions_count',
            'risk_zone'
        ]
        
        passed = True
        for field in required_fields:
            if field in data:
                print(f"✅ {field}: {data[field]}")
            else:
                print(f"❌ Missing: {field}")
                passed = False
        
        if passed:
            print("\n✅ TEST 2 PASSED: API endpoint returns all required fields")
        else:
            print("\n❌ TEST 2 FAILED: API endpoint missing required fields")
        
        return passed
        
    except requests.exceptions.RequestException as e:
        print(f"❌ FAIL: Could not connect to WebUI: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ FAIL: Invalid JSON response: {e}")
        return False


def check_api_monitor_cycle():
    """Verify /api/positions/monitor-cycle endpoint"""
    print("\n" + "=" * 80)
    print("TEST 3: API - Monitor Cycle Endpoint")
    print("=" * 80)
    
    url = f"{WEBUI_URL}/api/positions/monitor-cycle"
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            print(f"❌ FAIL: HTTP status {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ FAIL: API returned success=false")
            return False
        
        # Check required response fields
        required_fields = [
            'signal',
            'liquidation_distance',
            'liquidation_critical',
            'liquidation_warning',
            'bankruptcy_distance',
            'positions_count',
            'current_price'
        ]
        
        passed = True
        for field in required_fields:
            if field in data:
                print(f"✅ {field}: {data[field]}")
            else:
                print(f"❌ Missing: {field}")
                passed = False
        
        if passed:
            print("\n✅ TEST 3 PASSED: Monitor cycle endpoint returns all required fields")
        else:
            print("\n❌ TEST 3 FAILED: Monitor cycle endpoint missing required fields")
        
        return passed
        
    except requests.exceptions.RequestException as e:
        print(f"❌ FAIL: Could not connect to WebUI: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ FAIL: Invalid JSON response: {e}")
        return False


def main():
    """Run all integration tests"""
    print("\n" + "=" * 80)
    print("🔍 WebUI Integration Verification")
    print("Delta Exchange India Improvements")
    print("=" * 80)
    
    tests = [
        ("Guardian Health File", check_guardian_health_file),
        ("Liquidation Metrics API", check_api_liquidation_metrics),
        ("Monitor Cycle API", check_api_monitor_cycle),
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Delta Exchange India improvements are properly integrated with WebUI")
        print("✅ Users can access liquidation metrics via API endpoints")
        print("✅ Guardian is writing metrics to health file")
        sys.exit(0)
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("\nPlease check:")
        print("  1. Guardian bot is running: pm2 status guardian-live")
        print("  2. WebUI backend is running: launchctl list | grep gridbot.webui")
        print("  3. No errors in logs: pm2 logs guardian-live")
        sys.exit(1)


if __name__ == '__main__':
    main()
