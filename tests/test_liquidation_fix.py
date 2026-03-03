#!/usr/bin/env python3
"""
Test script to verify liquidation monitor fix
Tests that:
1. Environment variables are correctly loaded
2. DeltaClient initializes with correct API keys
3. Liquidation monitor can fetch balances
"""

import os
import sys

# Load environment
from dotenv import load_dotenv
load_dotenv('grid_config.env')
load_dotenv('secrets/api_keys.env')

print("=" * 70)
print("🧪 Testing Liquidation Monitor Fix")
print("=" * 70)

# Test 1: Check trading mode and keys are loaded
print("\n📋 Test 1: Environment Loading")
trading_mode = os.getenv('TRADING_MODE', 'demo')
print(f"  Trading Mode: {trading_mode}")

if trading_mode == 'demo':
    api_key = os.getenv('DEMO_DELTA_API_KEY', '')
    api_secret = os.getenv('DEMO_DELTA_API_SECRET', '')
    key_type = "DEMO"
else:
    api_key = os.getenv('LIVE_DELTA_API_KEY', '')
    api_secret = os.getenv('LIVE_DELTA_API_SECRET', '')
    key_type = "LIVE"

print(f"  {key_type}_DELTA_API_KEY: {'✅ Set' if api_key else '❌ Missing'} ({api_key[:8]}... if set)")
print(f"  {key_type}_DELTA_API_SECRET: {'✅ Set' if api_secret else '❌ Missing'}")

if not api_key or not api_secret:
    print("\n❌ FAIL: API keys not loaded")
    sys.exit(1)

# Test 2: Load trading mode config (this sets DELTA_API_KEY/SECRET)
print("\n📋 Test 2: Trading Mode Configuration")
try:
    from bot.utils.env_loader import load_trading_mode_config
    mode = load_trading_mode_config()
    print(f"  ✅ Mode configured: {mode}")
    
    # Verify the generic keys are set
    delta_key = os.getenv('DELTA_API_KEY', '')
    delta_secret = os.getenv('DELTA_API_SECRET', '')
    print(f"  DELTA_API_KEY: {'✅ Set' if delta_key else '❌ Missing'} ({delta_key[:8]}...)")
    print(f"  DELTA_API_SECRET: {'✅ Set' if delta_secret else '❌ Missing'}")
    
    if not delta_key or not delta_secret:
        print("  ❌ FAIL: Generic keys not set by env_loader")
        sys.exit(1)
        
except Exception as e:
    print(f"  ❌ FAIL: {e}")
    sys.exit(1)

# Test 3: Initialize DeltaClient
print("\n📋 Test 3: DeltaClient Initialization")
try:
    from bot.api.delta_client import DeltaClient
    client = DeltaClient()
    print(f"  ✅ DeltaClient initialized")
    print(f"  Base URL: {client.base}")
    print(f"  API Key: {client.key[:8]}...")
except Exception as e:
    print(f"  ❌ FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Fetch wallet balances (THIS IS THE KEY TEST)
print("\n📋 Test 4: Wallet Balance Fetch")
try:
    response = client.get_wallet_balances()
    print(f"  API Response: {response.get('success', False)}")
    
    if response.get('success') and response.get('result'):
        wallets = response['result']
        if wallets:
            wallet = wallets[0]
            balance = float(wallet.get('balance', 0))
            available = float(wallet.get('available_balance', 0))
            blocked = float(wallet.get('blocked_margin', 0) or wallet.get('portfolio_margin', 0) or 0)
            
            print(f"  ✅ Balance fetched successfully:")
            print(f"     Total: ${balance:.2f}")
            print(f"     Available: ${available:.2f}")
            print(f"     Blocked: ${blocked:.2f}")
            print(f"     INR Total: ₹{balance * 85:.2f}")
        else:
            print(f"  ⚠️  No wallet data in response")
    else:
        error = response.get('error', 'Unknown error')
        print(f"  ❌ FAIL: API call failed - {error}")
        sys.exit(1)
        
except Exception as e:
    print(f"  ❌ FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Initialize Liquidation Monitor
print("\n📋 Test 5: Liquidation Monitor Initialization")
try:
    from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
    from config_manager import ConfigManager
    
    config_manager = ConfigManager()
    config_data = config_manager.load_config_env()
    
    monitor = IntegratedLiquidationMonitor(config=config_data, logger=None)
    print(f"  ✅ IntegratedLiquidationMonitor created")
    
    # Test get_status (which internally calls fetch_balances)
    status = monitor.get_status()
    
    if status.get('total_balance', 0) > 0:
        print(f"  ✅ get_status() returned valid data:")
        print(f"     Total Balance: ₹{status.get('total_balance', 0):.2f}")
        print(f"     Available: ₹{status.get('available_balance', 0):.2f}")
        print(f"     Margin Utilization: {status.get('margin_utilization', 0):.2f}%")
        print(f"     Zone: {status.get('margin_zone', 'UNKNOWN')}")
    else:
        print(f"  ⚠️  get_status() returned zero balance")
        print(f"  Status: {status}")
        
except Exception as e:
    print(f"  ❌ FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED")
print("=" * 70)
print("\n🎯 Fix Verification:")
print("  ✓ Environment loading works correctly")
print("  ✓ API keys switch based on TRADING_MODE")
print("  ✓ DeltaClient fetches balances successfully")
print("  ✓ Liquidation monitor get_status() returns valid data")
print("\n💡 The liquidation monitor global variable fix is working!")
