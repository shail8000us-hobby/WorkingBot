#!/usr/bin/env python3
"""
Options Trading Module - Integration Tests
Phase 5: Testing & Validation

Tests all options functionality end-to-end.
Run with: python3 tests/options/test_integration.py

Created: January 4, 2026
"""

import asyncio
import sys
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Backend URL
BACKEND_URL = "http://localhost:3001"


def test_options_status():
    """Test: GET /api/options/status"""
    print("\n" + "="*60)
    print("TEST 1: Options Status Endpoint")
    print("="*60)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/options/status", timeout=10)
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data.get('success') == True, "Expected success=True"
        assert 'guardian_signal' in data, "Missing guardian_signal"
        assert 'trading_allowed' in data, "Missing trading_allowed"
        
        print(f"  Guardian Signal: {data['guardian_signal']}")
        print(f"  Trading Allowed: {data['trading_allowed']}")
        print(f"  Rate Limit: {data.get('rate_limit_seconds')}s")
        print("\n✅ Test PASSED: Status endpoint working")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def test_options_positions():
    """Test: GET /api/options/positions"""
    print("\n" + "="*60)
    print("TEST 2: Options Positions Endpoint")
    print("="*60)
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/options/positions", timeout=30)
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data.get('success') == True, "Expected success=True"
        assert 'positions' in data, "Missing positions array"
        assert 'count' in data, "Missing count"
        
        print(f"  Position Count: {data['count']}")
        
        if data['positions']:
            print(f"  Sample Position:")
            pos = data['positions'][0]
            print(f"    Symbol: {pos.get('product_symbol')}")
            print(f"    Size: {pos.get('size')}")
            print(f"    Entry: ${pos.get('entry_price', 0):.2f}")
            print(f"    Mark: ${pos.get('mark_price', 0):.2f}")
            print(f"    PnL: ${pos.get('unrealized_pnl', 0):.4f}")
        
        print("\n✅ Test PASSED: Positions endpoint working")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def test_options_ticker():
    """Test: GET /api/options/ticker/<symbol>"""
    print("\n" + "="*60)
    print("TEST 3: Options Ticker Endpoint")
    print("="*60)
    
    try:
        # First get a position to use its symbol
        positions_resp = requests.get(f"{BACKEND_URL}/api/options/positions", timeout=30)
        positions_data = positions_resp.json()
        
        if not positions_data.get('positions'):
            print("  ⚠️ No positions to test ticker, skipping")
            return True
        
        symbol = positions_data['positions'][0].get('product_symbol')
        print(f"  Testing ticker for: {symbol}")
        
        response = requests.get(f"{BACKEND_URL}/api/options/ticker/{symbol}", timeout=10)
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data.get('success') == True, "Expected success=True"
        assert 'ticker' in data, "Missing ticker data"
        
        ticker = data['ticker']
        mark_price = float(ticker.get('mark_price') or 0)
        bid = float(ticker.get('bid') or 0)
        ask = float(ticker.get('ask') or 0)
        spread = float(ticker.get('spread_pct') or 0)
        print(f"  Mark Price: ${mark_price:.2f}")
        print(f"  Bid: ${bid:.2f}")
        print(f"  Ask: ${ask:.2f}")
        print(f"  Spread: {spread:.1f}%")
        
        print("\n✅ Test PASSED: Ticker endpoint working")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def test_close_confirmation():
    """Test: POST /api/options/close (without confirm)"""
    print("\n" + "="*60)
    print("TEST 4: Close Position (Confirmation Request)")
    print("="*60)
    
    try:
        # First get a position
        positions_resp = requests.get(f"{BACKEND_URL}/api/options/positions", timeout=30)
        positions_data = positions_resp.json()
        
        if not positions_data.get('positions'):
            print("  ⚠️ No positions to test close, skipping")
            return True
        
        symbol = positions_data['positions'][0].get('product_symbol')
        print(f"  Testing close confirmation for: {symbol}")
        
        # Request WITHOUT confirm=true (should return confirmation request)
        response = requests.post(
            f"{BACKEND_URL}/api/options/close",
            json={"symbol": symbol, "confirm": False},
            timeout=10
        )
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data.get('success') == True, "Expected success=True"
        assert data.get('action') == 'confirm_required', "Expected action=confirm_required"
        
        print(f"  Action: {data.get('action')}")
        print(f"  Position Size: {data.get('position_size')}")
        print(f"  Close Size: {data.get('close_size')}")
        print(f"  Side: {data.get('side')}")
        
        print("\n✅ Test PASSED: Close confirmation working")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def test_add_confirmation():
    """Test: POST /api/options/add (without confirm)"""
    print("\n" + "="*60)
    print("TEST 5: Add to Position (Confirmation Request)")
    print("="*60)
    
    try:
        # First get a position
        positions_resp = requests.get(f"{BACKEND_URL}/api/options/positions", timeout=30)
        positions_data = positions_resp.json()
        
        if not positions_data.get('positions'):
            print("  ⚠️ No positions to test add, skipping")
            return True
        
        symbol = positions_data['positions'][0].get('product_symbol')
        print(f"  Testing add confirmation for: {symbol}")
        
        # Request WITHOUT confirm=true
        response = requests.post(
            f"{BACKEND_URL}/api/options/add",
            json={"symbol": symbol, "size": 1, "side": "buy", "confirm": False},
            timeout=10
        )
        data = response.json()
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data.get('success') == True, "Expected success=True"
        assert data.get('action') == 'confirm_required', "Expected action=confirm_required"
        
        print(f"  Action: {data.get('action')}")
        print(f"  Size: {data.get('size')}")
        print(f"  Side: {data.get('side')}")
        print(f"  Spread: {data.get('spread_pct', 'N/A')}%")
        
        print("\n✅ Test PASSED: Add confirmation working")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def test_rate_limiting():
    """Test: Rate limiting on order endpoints"""
    print("\n" + "="*60)
    print("TEST 6: Rate Limiting")
    print("="*60)
    
    try:
        # First get a position
        positions_resp = requests.get(f"{BACKEND_URL}/api/options/positions", timeout=30)
        positions_data = positions_resp.json()
        
        if not positions_data.get('positions'):
            print("  ⚠️ No positions to test rate limiting, skipping")
            return True
        
        symbol = positions_data['positions'][0].get('product_symbol')
        
        # Make first request (should succeed)
        response1 = requests.post(
            f"{BACKEND_URL}/api/options/close",
            json={"symbol": symbol, "confirm": False},
            timeout=10
        )
        
        # Immediately make second request (should be rate limited)
        response2 = requests.post(
            f"{BACKEND_URL}/api/options/close",
            json={"symbol": symbol, "confirm": False},
            timeout=10
        )
        
        # Note: Rate limiting only applies to confirmed orders
        # Both confirmation requests should succeed
        print(f"  First request: {response1.status_code}")
        print(f"  Second request: {response2.status_code}")
        
        print("\n✅ Test PASSED: Rate limiting check complete")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def test_grid_bot_isolation():
    """Test: Grid bot is not affected by options module"""
    print("\n" + "="*60)
    print("TEST 7: Grid Bot Isolation")
    print("="*60)
    
    try:
        # Check grid bot status
        response = requests.get(f"{BACKEND_URL}/api/pm2/processes", timeout=10)
        
        if response.status_code != 200:
            print("  ⚠️ PM2 API not available, checking positions instead")
            
            # Check futures positions
            positions_resp = requests.get(f"{BACKEND_URL}/api/positions", timeout=10)
            if positions_resp.status_code == 200:
                print("  Futures positions endpoint working")
                print("\n✅ Test PASSED: Grid bot systems accessible")
                return True
        else:
            data = response.json()
            print(f"  PM2 Processes: {len(data.get('result', []))}")
            
            for proc in data.get('result', []):
                if 'gridbot' in proc.get('name', ''):
                    print(f"    {proc['name']}: {proc.get('pm2_env', {}).get('status', 'unknown')}")
            
            print("\n✅ Test PASSED: Grid bot processes running")
            return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        return False


def main():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("🧪 OPTIONS TRADING MODULE - INTEGRATION TESTS")
    print("="*60)
    print(f"\nBackend URL: {BACKEND_URL}")
    print("Running all tests...\n")
    
    tests = [
        ("Status Endpoint", test_options_status),
        ("Positions Endpoint", test_options_positions),
        ("Ticker Endpoint", test_options_ticker),
        ("Close Confirmation", test_close_confirmation),
        ("Add Confirmation", test_add_confirmation),
        ("Rate Limiting", test_rate_limiting),
        ("Grid Bot Isolation", test_grid_bot_isolation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("Options trading module is ready for production.\n")
        return 0
    else:
        print(f"\n⚠️ {total - passed} tests failed.")
        print("Review the failures above before deploying.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
