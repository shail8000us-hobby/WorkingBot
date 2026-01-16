#!/usr/bin/env python3
"""
Match Delta Exchange Analytics EXACTLY.

Key insight: Delta's "47 trades" likely = unique symbols traded, not fill count.
Delta's "Realized PnL" = cashflow only (not including settlements).

We need to:
1. Count unique symbols as "trades"
2. Sum cashflow (not settlement) for "Realized PnL"
"""

import sys
import os

project_root = '/Users/ssr/Projects/WorkingBot'
sys.path.insert(0, project_root)
os.chdir(project_root)

import requests
import hashlib
import hmac
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from collections import defaultdict

# Load credentials
secrets_file = Path(project_root) / 'secrets' / 'api_keys.env'
if secrets_file.exists():
    load_dotenv(secrets_file, override=True)

api_key = os.getenv('LIVE_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
api_secret = os.getenv('LIVE_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')
base_url = 'https://api.india.delta.exchange'

def make_request(method, path):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path
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
    
    url = base_url + path
    response = requests.get(url, headers=headers)
    return response.json()

def is_option(symbol):
    if not symbol:
        return False
    return symbol.startswith('C-') or symbol.startswith('P-')

print("=" * 70)
print("DELTA EXCHANGE ANALYTICS EXACT MATCH")
print("=" * 70)

# Try LAST 2 DAYS only (since you mentioned 2 days ago with different numbers)
now = datetime.now()
cutoff_2d = now - timedelta(days=2)
cutoff_7d = now - timedelta(days=7)

print(f"2D cutoff: {cutoff_2d}")
print(f"7D cutoff: {cutoff_7d}")

# Fetch options transactions 
all_tx_2d = []
all_tx_7d = []
page = 1
done_7d = False

while not done_7d and page <= 500:
    result = make_request('GET', f'/v2/wallet/transactions?page_num={page}&page_size=100')
    
    if 'result' not in result or not result['result']:
        break
    
    transactions = result['result']
    
    for tx in transactions:
        created = tx.get('created_at', '')
        symbol = tx.get('meta_data', {}).get('product_symbol', '')
        tx_type = tx.get('transaction_type', '')
        
        # Only cashflow (realized trades)
        if tx_type != 'cashflow':
            continue
        
        # Only options
        if not is_option(symbol):
            continue
        
        if created:
            try:
                tx_time = datetime.fromisoformat(created.replace('Z', '+00:00')).replace(tzinfo=None)
                
                if tx_time < cutoff_7d:
                    done_7d = True
                    break
                
                all_tx_7d.append(tx)
                
                if tx_time >= cutoff_2d:
                    all_tx_2d.append(tx)
            except:
                pass
    
    if len(transactions) < 100:
        break
    
    page += 1
    if page % 20 == 0:
        print(f"Page {page}: {len(all_tx_7d)} cashflow tx...")

print(f"\n2D cashflow transactions: {len(all_tx_2d)}")
print(f"7D cashflow transactions: {len(all_tx_7d)}")

def analyze_trades(transactions, label):
    """Analyze trades - group by unique symbol"""
    by_symbol = defaultdict(lambda: {'pnl': 0, 'fills': 0, 'win': False})
    
    for tx in transactions:
        symbol = tx.get('meta_data', {}).get('product_symbol', 'unknown')
        amount = float(tx.get('amount', 0) or 0)
        by_symbol[symbol]['pnl'] += amount
        by_symbol[symbol]['fills'] += 1
    
    # Count wins/losses by symbol
    total_pnl = 0
    wins = 0
    losses = 0
    
    for symbol, data in by_symbol.items():
        data['win'] = data['pnl'] > 0
        total_pnl += data['pnl']
        if data['pnl'] > 0:
            wins += 1
        elif data['pnl'] < 0:
            losses += 1
    
    num_trades = len(by_symbol)
    win_rate = (wins / num_trades * 100) if num_trades > 0 else 0
    
    print(f"\n{label}")
    print("=" * 70)
    print(f"Unique Symbols (='trades'):  {num_trades}")
    print(f"Total Fills:                 {len(transactions)}")
    print(f"Wins:                        {wins}")
    print(f"Losses:                      {losses}")
    print(f"Win Rate:                    {win_rate:.1f}%")
    print(f"Total Cashflow PnL:          ${total_pnl:.2f} | Rs.{total_pnl*83:,.0f}")
    
    # Show top 5 winners and losers
    sorted_symbols = sorted(by_symbol.items(), key=lambda x: x[1]['pnl'], reverse=True)
    print(f"\nTop 5 Winners:")
    for symbol, data in sorted_symbols[:5]:
        print(f"  {symbol:35} | ${data['pnl']:8.2f} ({data['fills']} fills)")
    print(f"\nTop 5 Losers:")
    for symbol, data in sorted_symbols[-5:]:
        print(f"  {symbol:35} | ${data['pnl']:8.2f} ({data['fills']} fills)")
    
    return num_trades, total_pnl, win_rate

# Analyze both periods
trades_2d, pnl_2d, wr_2d = analyze_trades(all_tx_2d, "LAST 2 DAYS")
trades_7d, pnl_7d, wr_7d = analyze_trades(all_tx_7d, "LAST 7 DAYS")

print("\n" + "=" * 70)
print("COMPARISON WITH DELTA SCREENSHOT")
print("=" * 70)
print(f"Delta shows:     47 trades, Rs.8,880 PnL, 89.36% win rate")
print(f"")
print(f"Our 2D:          {trades_2d} trades, Rs.{pnl_2d*83:,.0f} PnL, {wr_2d:.1f}% win rate")
print(f"Our 7D:          {trades_7d} trades, Rs.{pnl_7d*83:,.0f} PnL, {wr_7d:.1f}% win rate")

# Maybe "7D" in Delta is actually calendar week or different timezone?
# Let's try exact 7 calendar days at start of day IST
ist_offset = 5.5  # hours ahead of UTC
now_ist = now + timedelta(hours=ist_offset)
start_of_today_ist = datetime(now_ist.year, now_ist.month, now_ist.day) - timedelta(hours=ist_offset)
cutoff_7d_ist = start_of_today_ist - timedelta(days=6)  # 7 day window including today

print(f"\nIST adjusted 7D cutoff: {cutoff_7d_ist}")
