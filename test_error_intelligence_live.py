#!/usr/bin/env python3
"""
Quick Test Script for Error Intelligence Live System
Tests both the log parser and the API endpoint
"""

import sys
import json
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

def test_log_parser():
    """Test the log parser module"""
    print("=" * 80)
    print("TEST 1: Log Parser Module")
    print("=" * 80)
    
    try:
        from webui.backend.log_parser import get_parser
        
        parser = get_parser(BASE_DIR)
        result = parser.get_latest_errors(max_errors=10, severity_filter='All')
        
        print(f"✅ Parser initialized successfully")
        print(f"📄 Log file: {result['log_file']}")
        print(f"📊 Log exists: {result['log_exists']}")
        print(f"🔢 Total errors found: {result['total_count']}")
        print(f"")
        print(f"📈 Severity Breakdown:")
        for severity, count in result['severity_counts'].items():
            icon = '🔴' if severity == 'Critical' else '⚠️' if severity == 'Warning' else 'ℹ️'
            print(f"  {icon} {severity}: {count}")
        print(f"")
        print(f"📦 Category Breakdown:")
        for category, count in result['category_counts'].items():
            print(f"  • {category}: {count}")
        
        if result['errors']:
            print(f"")
            print(f"📝 Sample Errors (first 3):")
            for i, error in enumerate(result['errors'][:3], 1):
                print(f"")
                print(f"  {i}. [{error['severity']}] {error['category']}")
                print(f"     Message: {error['message'][:120]}...")
                print(f"     Action: {error['suggested_action'][:100]}...")
                print(f"     Time: {error['timestamp']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoint():
    """Test the Flask API endpoint (requires running backend)"""
    print("")
    print("=" * 80)
    print("TEST 2: Flask API Endpoint")
    print("=" * 80)
    
    try:
        import requests
        
        # Test the endpoint
        url = "http://localhost:5555/api/errors/live"
        params = {
            'severity': 'All',
            'limit': 5,
            'lines': 500
        }
        
        print(f"🌐 Testing endpoint: {url}")
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint responded successfully")
            print(f"📊 Status: HTTP {response.status_code}")
            print(f"🔢 Total errors: {data.get('total_count', 0)}")
            print(f"📈 Severity counts: {json.dumps(data.get('severity_counts', {}), indent=2)}")
            
            if data.get('errors'):
                print(f"")
                print(f"📝 Sample Error:")
                error = data['errors'][0]
                print(f"  • Severity: {error['severity']}")
                print(f"  • Category: {error['category']}")
                print(f"  • Message: {error['message'][:100]}...")
                print(f"  • Suggested Action: {error['suggested_action'][:100]}...")
            
            return True
        else:
            print(f"❌ Endpoint returned HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"⚠️  Backend not running on port 5555")
        print(f"   To test endpoint, start backend: cd webui/backend && python3 app.py")
        return None
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_frontend_integration():
    """Check if frontend component exists"""
    print("")
    print("=" * 80)
    print("TEST 3: Frontend Integration")
    print("=" * 80)
    
    try:
        component_file = BASE_DIR / "webui" / "frontend" / "src" / "components" / "ErrorIntelligenceLive.js"
        app_file = BASE_DIR / "webui" / "frontend" / "src" / "App.js"
        
        if component_file.exists():
            print(f"✅ Component file exists: {component_file.name}")
            with open(component_file, 'r') as f:
                content = f.read()
                if 'ErrorIntelligenceLive' in content:
                    print(f"✅ Component properly defined")
                if 'formatTimeAgo' in content:
                    print(f"✅ Native time formatting implemented (no date-fns dependency)")
        else:
            print(f"❌ Component file not found")
            return False
        
        if app_file.exists():
            with open(app_file, 'r') as f:
                content = f.read()
                if 'ErrorIntelligenceLive' in content:
                    print(f"✅ Component imported in App.js")
                    print(f"✅ Component integrated into WebUI")
                else:
                    print(f"❌ Component not integrated in App.js")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("")
    print("🚀 ERROR INTELLIGENCE LIVE - SYSTEM TEST")
    print("")
    
    results = []
    
    # Test 1: Log Parser
    results.append(('Log Parser', test_log_parser()))
    
    # Test 2: API Endpoint
    results.append(('API Endpoint', test_api_endpoint()))
    
    # Test 3: Frontend Integration
    results.append(('Frontend Integration', test_frontend_integration()))
    
    # Summary
    print("")
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, result in results:
        if result is True:
            print(f"✅ {test_name}: PASSED")
        elif result is False:
            print(f"❌ {test_name}: FAILED")
        elif result is None:
            print(f"⚠️  {test_name}: SKIPPED (backend not running)")
    
    print("")
    print("=" * 80)
    
    # Overall status
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    print(f"📊 Results: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("")
        print("🎉 ALL TESTS PASSED!")
        print("")
        print("Next Steps:")
        print("1. Start backend: cd webui/backend && python3 app.py")
        print("2. Start frontend: cd webui/frontend && npm start")
        print("3. Open browser: http://localhost:3000")
        print("4. Scroll down to see 'Live Error Monitor' panel")
        return 0
    else:
        print("")
        print("⚠️  SOME TESTS FAILED - Review errors above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
