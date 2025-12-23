#!/usr/bin/env python3
"""
Test script to verify Delta Exchange testnet API keys
"""
import ccxt
import os
from dotenv import load_dotenv

# Load environment
load_dotenv("secrets/api_keys.env")
load_dotenv("grid_config.env", override=True)

# Get testnet credentials
api_key = os.getenv('DEMO_DELTA_API_KEY')
api_secret = os.getenv('DEMO_DELTA_API_SECRET')

print("=" * 80)
print("DELTA EXCHANGE TESTNET API KEY TEST")
print("=" * 80)
print()
print(f"API Key: {api_key[:10]}...{api_key[-5:]}")
print(f"API Secret: {api_secret[:10]}...***")
print(f"API URL: https://testnet-api.delta.exchange")
print()

# Initialize exchange
exchange = ccxt.delta({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'urls': {
        'api': {
            'public': 'https://testnet-api.delta.exchange',
            'private': 'https://testnet-api.delta.exchange'
        }
    }
})

print("Testing API connection...")
print()

try:
    # Test 1: Fetch balance (requires authentication)
    print("Test 1: Fetching balance...")
    balance = exchange.fetch_balance()
    print(f"✅ SUCCESS! Balance fetched")
    print(f"   Free balance: {balance.get('free', {})}")
    print()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    print()
    print("This means the API keys are INVALID or INCORRECT")
    print()
    print("Please:")
    print("1. Go to https://testnet.delta.exchange")
    print("2. Login to your testnet account")
    print("3. Go to Account Settings → API Management")
    print("4. Generate NEW API keys")
    print("5. Update secrets/api_keys.env")
    print()
    exit(1)

try:
    # Test 2: Fetch open positions
    print("Test 2: Fetching open positions...")
    positions = exchange.fetch_positions()
    print(f"✅ SUCCESS! Positions: {len(positions)}")
    for pos in positions:
        if pos.get('contracts', 0) != 0:
            print(f"   {pos['symbol']}: {pos['contracts']} contracts")
    print()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    print()

try:
    # Test 3: Fetch open orders
    print("Test 3: Fetching open orders...")
    orders = exchange.fetch_open_orders()
    print(f"✅ SUCCESS! Open orders: {len(orders)}")
    print()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    print()

try:
    # Test 4: Fetch markets to find BTC symbol
    print("Test 4: Finding BTC futures symbol...")
    markets = exchange.load_markets()
    btc_markets = [s for s in markets.keys() if 'BTC' in s and 'USD' in s]
    print(f"✅ SUCCESS! Found {len(btc_markets)} BTC markets:")
    for symbol in sorted(btc_markets)[:10]:
        market = markets[symbol]
        print(f"   {symbol} (ID: {market.get('id', 'N/A')})")
    print()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    print()

print("=" * 80)
print("API TEST COMPLETE")
print("=" * 80)
print()
print("If all tests passed, your API keys are VALID!")
print("If any test failed, please check your API keys.")

