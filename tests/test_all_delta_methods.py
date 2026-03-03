#!/usr/bin/env python3
"""
Test ALL Delta Exchange methods to fetch balance and UPNL
User will verify which method shows correct data matching their Delta Exchange UI
"""

import sys
sys.path.insert(0, '.')

import os
import json
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

# Setup LIVE mode
mode = os.getenv('TRADING_MODE', 'live').lower()
if mode == 'live':
    API_KEY = os.getenv('LIVE_DELTA_API_KEY', '')
    API_SECRET = os.getenv('LIVE_DELTA_API_SECRET', '')
    BASE_URL = 'https://api.india.delta.exchange'
else:
    API_KEY = os.getenv('DEMO_DELTA_API_KEY', '')
    API_SECRET = os.getenv('DEMO_DELTA_API_SECRET', '')
    BASE_URL = 'https://testnet-api.delta.exchange'

print("="*80)
print("🧪 TESTING ALL DELTA EXCHANGE DATA FETCH METHODS")
print("="*80)
print(f"Mode: {mode.upper()}")
print(f"API: {BASE_URL}")
print(f"Key: {API_KEY[:12]}...")
print("="*80)
print()

def make_request(method, path, params=None):
    """Make authenticated request to Delta Exchange"""
    timestamp = str(int(time.time()))
    query_string = ''
    if params:
        query_string = '?' + '&'.join(f"{k}={v}" for k, v in params.items())
    
    signature_data = method + timestamp + path + query_string
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        signature_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'api-key': API_KEY,
        'timestamp': timestamp,
        'signature': signature,
        'Content-Type': 'application/json'
    }
    
    url = BASE_URL + path
    if query_string:
        url += query_string
    
    response = requests.request(method, url, headers=headers)
    return response.json()

# ============================================================================
# METHOD 1: Wallet Balances API
# ============================================================================
print("\n" + "="*80)
print("METHOD 1: GET /v2/wallet/balances")
print("="*80)

wallet_data = make_request('GET', '/v2/wallet/balances')

if wallet_data.get('success'):
    wallet = wallet_data['result'][0]
    meta = wallet_data.get('meta', {})
    
    print("💰 WALLET DATA:")
    print(f"   Balance: ${wallet.get('balance', 0)}")
    print(f"   Available: ${wallet.get('available_balance', 0)}")
    print(f"   Blocked Margin: ${wallet.get('blocked_margin', 0)}")
    print(f"   Portfolio Margin: ${wallet.get('portfolio_margin', 0)}")
    print(f"   Order Margin: ${wallet.get('order_margin', 0)}")
    print(f"   Position Margin: ${wallet.get('position_margin', 0)}")
    print()
    print("📊 META DATA:")
    print(f"   Net Equity: ${meta.get('net_equity', 0)}")
    print()
    print("🧮 CALCULATED UPNL (net_equity - balance):")
    balance_val = float(wallet.get('balance', 0))
    net_equity = float(meta.get('net_equity', 0))
    calc_upnl = net_equity - balance_val
    print(f"   ${calc_upnl:.2f} USD")
    print(f"   ₹{calc_upnl * 85:,.2f} INR")
    print()
    print("₹ IN INR (×85):")
    print(f"   Balance: ₹{balance_val * 85:,.2f}")
    print(f"   Available: ₹{float(wallet.get('available_balance', 0)) * 85:,.2f}")
    print(f"   Blocked: ₹{float(wallet.get('blocked_margin', 0)) * 85:,.2f}")
else:
    print(f"❌ Failed: {wallet_data.get('error')}")

# ============================================================================
# METHOD 2: Positions API (All Positions)
# ============================================================================
print("\n" + "="*80)
print("METHOD 2: GET /v2/positions (No filters - ALL positions)")
print("="*80)

positions_data = make_request('GET', '/v2/positions', {})

if positions_data.get('success'):
    positions = positions_data.get('result', [])
    print(f"📊 Found {len(positions)} positions\n")
    
    total_upnl = 0
    for i, pos in enumerate(positions, 1):
        symbol = pos.get('product_symbol', 'Unknown')
        size = float(pos.get('size', 0))
        entry = float(pos.get('entry_price', 0))
        mark = float(pos.get('mark_price', 0))
        upnl = float(pos.get('unrealized_pnl', 0))
        
        print(f"Position {i}: {symbol}")
        print(f"   Size: {size}")
        print(f"   Entry: ${entry:.2f}")
        print(f"   Mark: ${mark:.2f}")
        print(f"   UPNL: ${upnl:.2f}")
        print()
        
        total_upnl += upnl
    
    print(f"📊 TOTAL UPNL (Sum of positions):")
    print(f"   ${total_upnl:.2f} USD")
    print(f"   ₹{total_upnl * 85:,.2f} INR")
else:
    print(f"❌ Failed: {positions_data.get('error')}")

# ============================================================================
# METHOD 3: Positions API with BTC filter
# ============================================================================
print("\n" + "="*80)
print("METHOD 3: GET /v2/positions?underlying_asset_symbol=BTC")
print("="*80)

positions_btc = make_request('GET', '/v2/positions', {'underlying_asset_symbol': 'BTC'})

if positions_btc.get('success'):
    positions = positions_btc.get('result', [])
    print(f"📊 Found {len(positions)} BTC positions\n")
    
    total_upnl = 0
    for i, pos in enumerate(positions, 1):
        symbol = pos.get('product_symbol', 'Unknown')
        upnl = float(pos.get('unrealized_pnl', 0))
        print(f"   {symbol}: ${upnl:.2f}")
        total_upnl += upnl
    
    print(f"\n📊 TOTAL UPNL:")
    print(f"   ${total_upnl:.2f} USD")
    print(f"   ₹{total_upnl * 85:,.2f} INR")
else:
    print(f"❌ Failed: {positions_btc.get('error')}")

# ============================================================================
# METHOD 4: WebSocket portfolio_margins (positions_upl)
# ============================================================================
print("\n" + "="*80)
print("METHOD 4: WebSocket portfolio_margins channel → positions_upl")
print("="*80)

try:
    from bot.liquidation.delta_realtime_websocket import get_realtime_websocket
    ws = get_realtime_websocket()
    
    print("Waiting 5 seconds for WebSocket data...")
    time.sleep(5)
    
    upnl_usd, upnl_inr = ws.get_upnl()
    balance_usd, balance_inr = ws.get_balance()
    
    print(f"💰 UPNL (positions_upl):")
    print(f"   ${upnl_usd:.2f} USD")
    print(f"   ₹{upnl_inr:,.2f} INR")
    print()
    print(f"💵 Balance:")
    print(f"   ${balance_usd:.2f} USD")
    print(f"   ₹{balance_inr:,.2f} INR")
except Exception as e:
    print(f"❌ WebSocket test failed: {e}")

# ============================================================================
# METHOD 5: Try positions_margined endpoint (if exists)
# ============================================================================
print("\n" + "="*80)
print("METHOD 5: GET /v2/positions_margined (if exists)")
print("="*80)

try:
    margined_data = make_request('GET', '/v2/positions_margined', {})
    if margined_data.get('success'):
        print(json.dumps(margined_data, indent=2))
    else:
        print(f"⚠️ Endpoint doesn't exist or returned error: {margined_data.get('error')}")
except Exception as e:
    print(f"⚠️ Endpoint doesn't exist: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("📋 SUMMARY - VERIFY AGAINST YOUR DELTA EXCHANGE UI")
print("="*80)
print()
print("Your Delta Exchange UI shows:")
print("   Position 1 (C-BTC-129000): +$9.57")
print("   Position 2 (P-BTC-92000): +$50.57")
print("   Position 3 (BTCUSD): +$17.67")
print("   Σ Total UPNL: +$77.82 USD")
print()
print("Which method above matches this +$77.82 value?")
print()
print("OPTIONS:")
print("   A) Method 1 - Calculated UPNL (net_equity - balance)")
print("   B) Method 2 - Sum of position unrealized_pnl")
print("   C) Method 3 - BTC positions unrealized_pnl")
print("   D) Method 4 - WebSocket positions_upl")
print("   E) Method 5 - Other endpoint")
print()
print("👉 Tell me which method shows +$77.82 and I'll implement that one!")
print("="*80)

