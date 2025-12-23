#!/usr/bin/env python3
"""Test Delta Exchange balance fetch - verify real vs fake data"""

import requests
import os
import json

# Load secrets
api_key = None
api_secret = None

with open('secrets/api_keys.env', 'r') as f:
    for line in f:
        if line.startswith('LIVE_DELTA_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
        elif line.startswith('LIVE_DELTA_API_SECRET='):
            api_secret = line.split('=', 1)[1].strip()

if not api_key or not api_secret:
    print("❌ Failed to load API keys from secrets/api_keys.env")
    exit(1)

print(f"🔑 API Key: {api_key[:12]}...")
print(f"🌐 Endpoint: https://api.india.delta.exchange/v2/wallet/balances")
print()

# Create signature
import time
import hmac
import hashlib

method = 'GET'
endpoint = '/v2/wallet/balances'
timestamp = str(int(time.time()))
payload = ''

signature_data = method + timestamp + endpoint + payload
signature = hmac.new(
    api_secret.encode('utf-8'),
    signature_data.encode('utf-8'),
    hashlib.sha256
).hexdigest()

headers = {
    'api-key': api_key,
    'timestamp': timestamp,
    'signature': signature,
    'Content-Type': 'application/json'
}

# Make request
print("📡 Calling Delta Exchange API...")
response = requests.get(
    'https://api.india.delta.exchange/v2/wallet/balances',
    headers=headers
)

print(f"📊 Response Status: {response.status_code}")
print()

if response.status_code == 200:
    data = response.json()
    
    if data.get('success'):
        print("✅ API CALL SUCCESSFUL - THIS IS REAL DATA!")
        print()
        
        result = data.get('result', [])
        if result:
            wallet = result[0]
            
            print("💰 RAW DATA FROM DELTA EXCHANGE (USD):")
            print(f"   Balance: ${wallet.get('balance', 0)}")
            print(f"   Available: ${wallet.get('available_balance', 0)}")
            print(f"   Blocked Margin: ${wallet.get('blocked_margin', 0)}")
            print(f"   Portfolio Margin: ${wallet.get('portfolio_margin', 0)}")
            print(f"   Order Margin: ${wallet.get('order_margin', 0)}")
            print(f"   Position Margin: ${wallet.get('position_margin', 0)}")
            print()
            
            meta = data.get('meta', {})
            net_equity = float(meta.get('net_equity', 0))
            balance = float(wallet.get('balance', 0))
            upnl = net_equity - balance
            
            print("📊 CALCULATED VALUES:")
            print(f"   Net Equity: ${net_equity:.2f}")
            print(f"   Unrealized PnL: ${upnl:.2f}")
            print()
            
            print("₹ CONVERTED TO INR (×85):")
            print(f"   Total Balance: ₹{balance * 85:,.2f}")
            print(f"   Available: ₹{float(wallet.get('available_balance', 0)) * 85:,.2f}")
            print(f"   Blocked Margin: ₹{float(wallet.get('blocked_margin', 0)) * 85:,.2f}")
            print(f"   Portfolio Margin: ₹{float(wallet.get('portfolio_margin', 0)) * 85:,.2f}")
            print(f"   Unrealized PnL: ₹{upnl * 85:,.2f}")
            print()
            
            print("🎯 WHAT YOU SEE IN YOUR UI:")
            print(f"   Total Balance: ₹{balance * 85:,.0f}")
            print(f"   Available: ₹{float(wallet.get('available_balance', 0)) * 85:,.0f}")
            print(f"   Blocked: ₹{float(wallet.get('blocked_margin', 0)) * 85:,.0f}")
            print(f"   MTM: ₹{upnl * 85:,.0f}")
            print()
            
            # Check if it matches UI
            ui_balance = 102303
            ui_available = 90055
            ui_mtm = -5545
            
            calculated_balance = int(balance * 85)
            calculated_available = int(float(wallet.get('available_balance', 0)) * 85)
            calculated_mtm = int(upnl * 85)
            
            print("🔍 VERIFICATION:")
            if abs(calculated_balance - ui_balance) < 10:
                print(f"   ✅ Balance matches UI: ₹{ui_balance:,} ≈ ₹{calculated_balance:,}")
            else:
                print(f"   ❌ Balance mismatch: UI shows ₹{ui_balance:,}, API shows ₹{calculated_balance:,}")
                
            if abs(calculated_available - ui_available) < 10:
                print(f"   ✅ Available matches UI: ₹{ui_available:,} ≈ ₹{calculated_available:,}")
            else:
                print(f"   ❌ Available mismatch: UI shows ₹{ui_available:,}, API shows ₹{calculated_available:,}")
                
            if abs(calculated_mtm - ui_mtm) < 100:
                print(f"   ✅ MTM matches UI: ₹{ui_mtm:,} ≈ ₹{calculated_mtm:,}")
            else:
                print(f"   ❌ MTM mismatch: UI shows ₹{ui_mtm:,}, API shows ₹{calculated_mtm:,}")
            
            print()
            print("🎉 CONCLUSION: Data is REAL from Delta Exchange API!")
        else:
            print("❌ No wallet data in response")
    else:
        print(f"❌ API returned error: {data.get('error', 'Unknown')}")
else:
    print(f"❌ HTTP Error: {response.status_code}")
    print(response.text)

