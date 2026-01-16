#!/usr/bin/env python3
"""Test SL/TP trigger logic manually"""

import sys
sys.path.insert(0, '.')

from webui.backend.options_strategy.sl_tp_manager import get_sl_tp_manager

# Test data
symbol = "P-BTC-95200-150126"
current_price = 0.65  # Current mid price
entry_price = 18.58   # Entry price
pnl_pct = 96.5        # P&L percentage
position_size = -14   # SHORT position (negative)

manager = get_sl_tp_manager()

# Get settings
settings = manager.get_sl_tp(symbol)
print(f"Settings for {symbol}:")
print(f"  TP Price: ${settings.get('take_profit_price')}")
print(f"  Auto Execute: {settings.get('auto_execute')}")
print()

# Check trigger
print(f"Position Data:")
print(f"  Symbol: {symbol}")
print(f"  Current Price: ${current_price}")
print(f"  Entry Price: ${entry_price}")
print(f"  Position Size: {position_size} ({'SHORT' if position_size < 0 else 'LONG'})")
print(f"  P&L: {pnl_pct:.1f}%")
print()

trigger = manager.check_triggers(
    symbol=symbol,
    current_price=current_price,
    entry_price=entry_price,
    pnl_pct=pnl_pct,
    position_size=position_size
)

print(f"Trigger Check:")
print(f"  TP Target: $2.0")
print(f"  Current: ${current_price}")
print(f"  Should Trigger (SHORT): {current_price} <= 2.0 = {current_price <= 2.0}")
print()

if trigger:
    print(f"✅ TRIGGER FIRED!")
    print(f"  Type: {trigger['type']}")
    print(f"  Reason: {trigger['reason']}")
else:
    print(f"❌ NO TRIGGER")
    print(f"  This is a bug - it should have triggered!")
