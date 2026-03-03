"""
Test Kelly Criterion with Simulated Trades
"""

import requests
import random
import time

BASE_URL = "http://localhost:5555"

print("🧪 KELLY CRITERION TEST")
print("=" * 60)

# Step 1: Check health
print("\n1️⃣ Checking Kelly health...")
resp = requests.get(f"{BASE_URL}/api/kelly/health")
print(f"   Status: {resp.json()['status']}")
print(f"   Total trades: {resp.json()['total_trades']}")

# Step 2: Check sizing with no data (should be LOW confidence)
print("\n2️⃣ Checking initial sizing (no trades yet)...")
resp = requests.get(f"{BASE_URL}/api/kelly/sizing/iron_condor?account_balance=100000")
data = resp.json()
print(f"   Confidence: {data['confidence']}")
print(f"   Recommended size: ${data['position_size_usd']:,.0f} ({data['kelly_percent']*100:.1f}%)")

# Step 3: Simulate 30 trades with 55% win rate
print("\n3️⃣ Simulating 30 iron condor trades (55% win rate)...")
wins = 0
losses = 0

for i in range(30):
    is_win = random.random() < 0.55  # 55% win rate
    pnl = random.uniform(200, 400) if is_win else -random.uniform(100, 250)
    
    resp = requests.post(f"{BASE_URL}/api/kelly/record-trade", json={
        "strategy": "iron_condor",
        "pnl": round(pnl, 2)
    })
    
    if is_win:
        wins += 1
    else:
        losses += 1
    
    print(f"   Trade {i+1}/30: {'WIN' if is_win else 'LOSS'} ${pnl:+7.2f} (W/L: {wins}/{losses})")
    time.sleep(0.1)

# Step 4: Check updated sizing
print("\n4️⃣ Checking Kelly sizing after 30 trades...")
resp = requests.get(f"{BASE_URL}/api/kelly/sizing/iron_condor?account_balance=100000")
data = resp.json()

print(f"\n{'='*60}")
print("🎯 KELLY RECOMMENDATION")
print(f"{'='*60}")
print(f"Strategy:        {data['strategy']}")
print(f"Confidence:      {data['confidence']}")
print(f"Kelly Percent:   {data['kelly_percent']*100:.2f}%")
print(f"Position Size:   ${data['position_size_usd']:,.0f}")
print(f"\nAccount Balance: ${data['account_balance']:,.0f}")
print(f"{'='*60}")

if 'stats' in data:
    stats = data['stats']
    print(f"\n📊 STATISTICS")
    print(f"{'='*60}")
    print(f"Total Trades:    {stats.get('total_trades', 0)}")
    print(f"Win Rate:        {stats.get('win_rate', 0)*100:.1f}%")
    print(f"Avg Win:         ${stats.get('avg_win_usd', 0):,.0f}")
    print(f"Avg Loss:        ${stats.get('avg_loss_usd', 0):,.0f}")
    print(f"Win/Loss Ratio:  {stats.get('win_loss_ratio', 0):.2f}x")
    print(f"Expectancy:      ${stats.get('expectancy', 0):,.0f} per trade")
    print(f"{'='*60}")

print(f"\n💡 RECOMMENDATION")
print(f"{'='*60}")
print(data['recommendation'])
print(f"{'='*60}")

# Step 5: Calculate max contracts
print("\n5️⃣ Calculate max contracts (premium = $1.20)...")
resp = requests.post(f"{BASE_URL}/api/kelly/calculate-max-contracts", json={
    "strategy": "iron_condor",
    "account_balance": 100000,
    "premium_per_contract": 1.20
})
data = resp.json()

print(f"   Kelly size: ${data['kelly_size_usd']:,.0f}")
print(f"   Premium: ${data['premium_per_contract']}")
print(f"   Max contracts: {data['max_contracts']}")
print(f"   Recommendation: {data['recommendation']}")

print("\n✅ Test complete! Kelly Criterion is working.")
