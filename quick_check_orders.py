#!/usr/bin/env python3
"""
Quick check of current orders on Delta Exchange
"""
import requests
import time
import hmac
import hashlib
import os
import yaml

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

api_key = os.getenv('DELTA_API_KEY')
api_secret = os.getenv('DELTA_API_SECRET')

if not api_key or not api_secret:
    print("❌ API credentials not found in environment")
    print("Set DELTA_API_KEY and DELTA_API_SECRET")
    exit(1)

# API endpoints
base_url = config['exchange']['live']['private_url']
product_id = config['exchange']['live']['product_id']

def create_signature(method, endpoint, timestamp, payload=""):
    """Create HMAC signature for Delta Exchange"""
    message = method + timestamp + endpoint + payload
    signature = hmac.new(
        api_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def get_open_orders():
    """Fetch open orders"""
    endpoint = f"/v2/orders"
    method = "GET"
    timestamp = str(int(time.time()))
    
    headers = {
        'api-key': api_key,
        'timestamp': timestamp,
        'signature': create_signature(method, endpoint, timestamp),
        'User-Agent': 'rest-client',
        'Content-Type': 'application/json'
    }
    
    params = {'product_id': product_id, 'state': 'open'}
    
    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching orders: {e}")
        return None

# Get orders
print("=" * 80)
print("🔍 CHECKING CURRENT ORDERS")
print("=" * 80)
print(f"Product ID: {product_id}")
print(f"Exchange: {base_url}")
print()

result = get_open_orders()

if result and 'result' in result:
    orders = result['result']
    
    if not orders:
        print("✅ No open orders found")
    else:
        print(f"📊 Found {len(orders)} open order(s):\n")
        
        buy_orders = [o for o in orders if o['side'] == 'buy']
        sell_orders = [o for o in orders if o['side'] == 'sell']
        
        print(f"📈 BUY Orders: {len(buy_orders)}")
        for order in buy_orders:
            print(f"   ID: {order['id']} | Price: ${float(order['limit_price']):,.0f} | Size: {order['size']} | Status: {order['state']}")
        
        print(f"\n📉 SELL Orders: {len(sell_orders)}")
        for order in sell_orders:
            print(f"   ID: {order['id']} | Price: ${float(order['limit_price']):,.0f} | Size: {order['size']} | Status: {order['state']}")
        
        print(f"\n💰 Total value:")
        buy_value = sum(float(o['limit_price']) * float(o['size']) for o in buy_orders)
        sell_value = sum(float(o['limit_price']) * float(o['size']) for o in sell_orders)
        print(f"   BUY: ${buy_value:,.2f}")
        print(f"   SELL: ${sell_value:,.2f}")
