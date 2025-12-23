#!/usr/bin/env python3
"""Verify MTM calculation is using new primary method"""
import os, sys, time
from dotenv import load_dotenv
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

# Suppress most logs
import logging
logging.basicConfig(level=logging.WARNING)

from bot.utils.env_loader import load_trading_mode_config
load_trading_mode_config()

from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor

print('\n' + '='*80)
print('  🔍 VERIFYING MTM CALCULATION METHOD')
print('='*80)
print()

# Create monitor
config = {}
logger = logging.getLogger('verify')
logger.setLevel(logging.DEBUG)

monitor = IntegratedLiquidationMonitor(config, logger)

print('Step 1: Fetch balances (triggers MTM calculation)')
print('-' * 80)
balance = monitor.fetch_balances()

print()
print('Step 2: Check cached UPNL')
print('-' * 80)
cached_upnl = getattr(monitor, '_cached_upnl_usd', 0)
print(f'Cached UPNL (USD): ${cached_upnl:+,.2f}')
print(f'Cached UPNL (INR): ₹{cached_upnl * 85:+,.2f}')

print()
print('Step 3: Get full status (used by WebUI)')
print('-' * 80)
status = monitor.get_status()
mtm_inr = status.get('total_unrealized_pnl', 0)
mtm_usd = status.get('total_unrealized_pnl_usd', 0)

print(f'Status MTM (USD): ${mtm_usd:+,.2f}')
print(f'Status MTM (INR): ₹{mtm_inr:+,.2f}')

print()
print('='*80)
print('  📊 COMPARISON')
print('='*80)
print(f'WebUI shows:     ₹4,482 (from screenshot)')
print(f'Backend returns: ₹{mtm_inr:+,.2f}')
print()

if abs(mtm_inr - 4482) < 100:
    print('⚠️  Backend is returning the old value!')
    print('   The WebUI backend needs to be restarted to use new code.')
else:
    print('✅ Backend is using new calculation!')

print()
print('💡 To apply new code:')
print('   1. Stop the WebUI backend')
print('   2. Restart it')
print('   3. Refresh the browser')
print('='*80)
print()

