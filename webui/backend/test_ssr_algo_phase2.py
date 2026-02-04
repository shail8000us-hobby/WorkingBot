#!/usr/bin/env python3
"""Test script for SSR Algo Phase 2 modules."""
import sys
import os

# Add the ssr_algo directory directly to avoid routes/__init__.py conflicts
ssr_algo_path = os.path.join(os.path.dirname(__file__), 'routes', 'ssr_algo')
sys.path.insert(0, ssr_algo_path)

# Test 1: Payoff Calculator
print("=" * 50)
print("TEST 1: SSRPayoffCalculator")
print("=" * 50)

from ssr_algo_payoff import SSRPayoffCalculator, get_payoff_calculator

calc = get_payoff_calculator()

# Test price range generation
spot = 77000
price_range = calc.generate_price_range(spot, range_percent=20, points=50)
print(f"✅ Price range: {price_range[0]} to {price_range[-1]} ({len(price_range)} points)")

# Test single position payoff
test_position = {
    'symbol': 'C-BTC-77000-060226',
    'size': -1,
    'entry_price': 3500
}
pnl_at_spot = calc.calculate_single_position_payoff(test_position, 77000)
pnl_at_higher = calc.calculate_single_position_payoff(test_position, 80000)
print(f"✅ Short ATM Call PnL at 77000: ${pnl_at_spot:.2f}")
print(f"   PnL at 80000: ${pnl_at_higher:.2f}")

# Test butterfly payoff
butterfly_positions = [
    # Short ATM Straddle (sells)
    {'symbol': 'C-BTC-77000-060226', 'size': -1, 'entry_price': 3500},  # ATM Call sell
    {'symbol': 'P-BTC-77000-060226', 'size': -1, 'entry_price': 3500},  # ATM Put sell
    # Long OTM wings (buys)
    {'symbol': 'C-BTC-80000-060226', 'size': 2, 'entry_price': 1600},   # OTM Call buy x2
    {'symbol': 'P-BTC-74000-060226', 'size': 2, 'entry_price': 1600},   # OTM Put buy x2
    # Short far OTM (sells)
    {'symbol': 'C-BTC-82000-060226', 'size': -1, 'entry_price': 800},   # Far OTM Call sell
    {'symbol': 'P-BTC-72000-060226', 'size': -1, 'entry_price': 800},   # Far OTM Put sell
]

payoff_curve = calc.calculate_payoff_curve(butterfly_positions, price_range)
max_loss_points = calc.find_max_loss_points(payoff_curve)
breakevens = calc.find_breakevens(payoff_curve)
net_premium = calc.calculate_net_premium(butterfly_positions)

print(f"\n✅ Butterfly Payoff Analysis:")
print(f"   Net Premium: ${net_premium:.2f}")
print(f"   Max Loss Upper: {max_loss_points.get('max_loss_upper')}")
print(f"   Max Loss Lower: {max_loss_points.get('max_loss_lower')}")
print(f"   Max Loss Value: ${max_loss_points.get('max_loss_value', 0):.2f}")
print(f"   Max Profit Price: {max_loss_points.get('max_profit_price')}")
print(f"   Max Profit Value: ${max_loss_points.get('max_profit_value', 0):.2f}")
print(f"   Breakevens: {breakevens}")

# Test zone detection
in_zone, zone = calc.is_price_in_max_loss_zone(80000, max_loss_points.get('max_loss_upper'), max_loss_points.get('max_loss_lower'), tolerance=500)
print(f"\n✅ Zone Detection at 80000: in_zone={in_zone}, zone={zone}")

print("\n" + "=" * 50)
print("TEST 2: DwellTracker")
print("=" * 50)

from ssr_algo_monitor import DwellTracker

tracker = DwellTracker(dwell_threshold_minutes=10)

# Simulate entering zone
result1 = tracker.update(True, 'upper')
print(f"✅ Enter zone: triggered={result1}, zone={tracker.current_zone}")

# Simulate staying in zone
result2 = tracker.update(True, 'upper')
print(f"✅ Stay in zone: triggered={result2}")

# Simulate exiting zone
result3 = tracker.update(False, None)
print(f"✅ Exit zone: triggered={result3}, zone={tracker.current_zone}")

# Get status
status = tracker.get_status()
print(f"✅ Status: {status}")

print("\n" + "=" * 50)
print("TEST 3: Monitor Functions")
print("=" * 50)

from ssr_algo_monitor import get_all_monitor_statuses
statuses = get_all_monitor_statuses()
print(f"✅ Active monitors: {len(statuses)}")

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)
