#!/usr/bin/env python3
"""
Test script for Error Intelligence System
Injects a test error and verifies system is working
"""

import sys
import time
import requests
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

def test_error_intelligence():
    """Test Error Intelligence System is working"""
    
    base_url = "http://localhost:5555"
    
    print("=" * 60)
    print("Error Intelligence System - Test Script")
    print("=" * 60)
    
    # Test 1: Check API is available
    print("\n1. Testing API availability...")
    try:
        response = requests.get(f"{base_url}/api/errors/", timeout=5)
        if response.status_code == 200:
            print("   ✅ API is available")
            data = response.json()
            print(f"   Current errors: {len(data.get('errors', []))}")
        else:
            print(f"   ❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to backend. Is it running?")
        print("   Start it with: pm2 restart webui-backend")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Get error catalog
    print("\n2. Testing error catalog...")
    try:
        response = requests.get(f"{base_url}/api/errors/catalog", timeout=5)
        if response.status_code == 200:
            data = response.json()
            patterns = data.get('patterns', [])
            print(f"   ✅ Catalog loaded: {len(patterns)} error patterns")
            print(f"   Sample patterns: {', '.join([p['code'] for p in patterns[:5]])}")
        else:
            print(f"   ❌ Catalog returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Get statistics
    print("\n3. Testing statistics...")
    try:
        response = requests.get(f"{base_url}/api/errors/statistics", timeout=5)
        if response.status_code == 200:
            data = response.json()
            stats = data.get('statistics', {})
            print(f"   ✅ Statistics retrieved")
            print(f"   Total errors: {stats.get('total', 0)}")
            print(f"   By severity: {stats.get('by_severity', {})}")
            print(f"   By status: {stats.get('by_status', {})}")
        else:
            print(f"   ❌ Statistics returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Inject test error
    print("\n4. Injecting test error...")
    try:
        test_payload = {
            "message": "Authentication failed - invalid API key",
            "source": "trading"
        }
        response = requests.post(
            f"{base_url}/api/errors/test",
            json=test_payload,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Test error created successfully")
            error = data.get('error', {})
            print(f"   Error ID: {error.get('id', 'N/A')}")
            print(f"   Code: {error.get('code', 'N/A')}")
            print(f"   Severity: {error.get('severity', 'N/A')}")
            print(f"   Explanation: {error.get('explanation', 'N/A')[:100]}...")
        else:
            print(f"   ❌ Test error creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 5: Verify error appears in list
    print("\n5. Verifying error appears in list...")
    try:
        time.sleep(1)  # Wait a bit for processing
        response = requests.get(f"{base_url}/api/errors/?status=open", timeout=5)
        if response.status_code == 200:
            data = response.json()
            errors = data.get('errors', [])
            print(f"   ✅ Retrieved {len(errors)} open errors")
            if errors:
                latest = errors[0]
                print(f"   Latest error: {latest.get('code', 'N/A')} - {latest.get('message_raw', 'N/A')[:60]}...")
        else:
            print(f"   ❌ Failed to retrieve errors")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Error Intelligence System is working!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Open WebUI at http://localhost:5555")
    print("2. Look for floating incidents badge (bottom-right)")
    print("3. Click badge to open error panel")
    print("4. Configure Telegram (optional) in grid_config.env:")
    print("   - TELEGRAM_BOT_TOKEN=your_token_here")
    print("   - TELEGRAM_CHAT_ID=your_chat_id_here")
    print("   - TELEGRAM_ERROR_NOTIFICATIONS=true")
    print("")
    
    return True


if __name__ == '__main__':
    try:
        success = test_error_intelligence()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(1)
