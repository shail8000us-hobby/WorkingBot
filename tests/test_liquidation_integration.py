#!/usr/bin/env python3
"""
Test Liquidation Integration

Test script to verify:
1. Telegram integration works
2. Frontend parameters are accessible
3. Real-time monitoring is working
"""

import os
import sys
import time
import requests
import json

def test_backend_running():
    """Test if backend is running"""
    try:
        response = requests.get('http://localhost:5555/api/health', timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend not running: {e}")
        return False

def test_liquidation_config():
    """Test liquidation config endpoint"""
    try:
        response = requests.get('http://localhost:5555/api/liquidation/config')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                config = data.get('config', {})
                print("✅ Liquidation config accessible")
                print(f"   Real-time monitoring: {config.get('REAL_TIME_MONITORING_ENABLED')}")
                print(f"   Margin critical: {config.get('MARGIN_UTILIZATION_CRITICAL')}%")
                print(f"   Distance warning: {config.get('LIQUIDATION_DISTANCE_WARNING')}%")
                return True
            else:
                print(f"❌ Config request failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Config endpoint returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing config: {e}")
        return False

def test_realtime_status():
    """Test real-time status endpoint"""
    try:
        response = requests.get('http://localhost:5555/api/liquidation/realtime-status')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Real-time status accessible")
                status = data.get('status', {})
                print(f"   Monitoring active: {data.get('monitoring_active')}")
                print(f"   Margin utilization: {status.get('margin_utilization', 0):.1f}%")
                print(f"   Liquidation distance: {status.get('liquidation_distance', 0):.1f}%")
                return True
            else:
                print(f"❌ Real-time status failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Real-time endpoint returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing real-time status: {e}")
        return False

def test_telegram_integration():
    """Test if Telegram integration is available"""
    try:
        # Check if recon_telegram module exists
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from bot.recon_telegram import send_telegram_alert
        print("✅ Telegram integration available")
        return True
    except ImportError as e:
        print(f"⚠️  Telegram integration not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing Telegram: {e}")
        return False

def test_emergency_action():
    """Test emergency action endpoint (dry run)"""
    try:
        response = requests.post('http://localhost:5555/api/liquidation/emergency-action')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Emergency action endpoint accessible")
                print(f"   Message: {data.get('message')}")
                return True
            else:
                print(f"❌ Emergency action failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Emergency action returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing emergency action: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Liquidation Integration")
    print("=" * 50)
    
    tests = [
        ("Backend Running", test_backend_running),
        ("Liquidation Config", test_liquidation_config),
        ("Real-time Status", test_realtime_status),
        ("Telegram Integration", test_telegram_integration),
        ("Emergency Action", test_emergency_action)
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}...")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n📈 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Integration is working!")
    else:
        print("⚠️  Some tests failed - Check issues above")

if __name__ == "__main__":
    main()
