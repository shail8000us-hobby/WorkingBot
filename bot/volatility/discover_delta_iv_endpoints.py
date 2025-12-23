#!/usr/bin/env python3
"""
Delta Exchange Historical IV Data Explorer

Try various potential API endpoints to discover if historical IV data exists.
"""

import requests
import json
from datetime import datetime, timedelta

API_BASE = "https://api.india.delta.exchange"

# Potential endpoints to try
ENDPOINTS_TO_TEST = [
    # Historical IV endpoints (guesses based on common API patterns)
    "/v2/history/iv",
    "/v2/history/implied_volatility",
    "/v2/history/option_iv",
    "/v2/history/volatility",
    "/v2/volatility/historical",
    "/v2/iv/history",
    
    # Volatility index
    "/v2/tickers/BTCVOL",
    "/v2/indices/volatility",
    "/v2/volatility_index",
    
    # Option greeks history (includes IV)
    "/v2/history/greeks",
    "/v2/history/option_greeks",
    "/v2/options/history/greeks",
    
    # Historical option data
    "/v2/history/options",
    "/v2/history/option_tickers",
    "/v2/options/history",
    
    # Volatility surface
    "/v2/volatility/surface",
    "/v2/iv/surface",
    "/v2/options/surface",
]

def test_endpoint(endpoint, params=None):
    """Test if an endpoint exists and returns data"""
    url = f"{API_BASE}{endpoint}"
    
    try:
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ {endpoint} - SUCCESS (HTTP 200)")
            try:
                data = response.json()
                print(f"   Response preview: {json.dumps(data, indent=2)[:200]}...")
                return True
            except:
                print(f"   Response not JSON: {response.text[:200]}...")
                return False
        elif response.status_code == 404:
            print(f"❌ {endpoint} - Not Found (HTTP 404)")
            return False
        elif response.status_code == 401:
            print(f"🔒 {endpoint} - Requires Auth (HTTP 401)")
            return False
        elif response.status_code == 403:
            print(f"🔒 {endpoint} - Forbidden (HTTP 403)")
            return False
        else:
            print(f"⚠️  {endpoint} - HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️  {endpoint} - Timeout")
        return False
    except Exception as e:
        print(f"❌ {endpoint} - Error: {e}")
        return False

def main():
    print("=" * 70)
    print("🔍 Delta Exchange Historical IV Data Endpoint Discovery")
    print("=" * 70)
    print()
    
    # Test parameters
    end_time = int(datetime.now().timestamp())
    start_time = int((datetime.now() - timedelta(days=7)).timestamp())
    
    test_params = {
        'symbol': 'BTCUSD',
        'start': start_time,
        'end': end_time,
        'resolution': '1d'
    }
    
    print("Testing endpoints with parameters:")
    print(f"  Symbol: BTCUSD")
    print(f"  Start: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d')}")
    print(f"  End: {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d')}")
    print()
    
    successful_endpoints = []
    
    # Test each endpoint
    for endpoint in ENDPOINTS_TO_TEST:
        if test_endpoint(endpoint, test_params):
            successful_endpoints.append(endpoint)
        print()
    
    # Summary
    print("=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    if successful_endpoints:
        print(f"\n✅ Found {len(successful_endpoints)} working endpoint(s):")
        for ep in successful_endpoints:
            print(f"   - {ep}")
    else:
        print("\n❌ No historical IV endpoints found")
        print("\nNext steps:")
        print("1. Contact Delta Exchange support with the request document")
        print("2. Check their official API documentation")
        print("3. Ask in their developer community")
    
    print()

if __name__ == "__main__":
    main()
