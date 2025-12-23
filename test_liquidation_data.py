#!/usr/bin/env python3
"""
Test script to verify Delta Exchange API data fetching
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

print("=" * 70)
print("🔍 Testing Delta Exchange API Data Fetching")
print("=" * 70)
print()

# Test 1: Check API credentials
print("1️⃣ Checking API Credentials...")
api_key = os.getenv('DELTA_API_KEY')
api_secret = os.getenv('DELTA_API_SECRET')

if api_key:
    print(f"   API Key: {api_key[:8]}... ✅ SET")
else:
    print(f"   API Key: ❌ NOT SET")
    
if api_secret:
    print(f"   API Secret: ✅ SET")
else:
    print(f"   API Secret: ❌ NOT SET")
    
if not api_key or not api_secret:
    print("\n   ❌ API credentials not found!")
    print("   Trying to load from env_loader...")
    from bot.utils.env_loader import load_trading_mode_config
    load_trading_mode_config()
    api_key = os.getenv('DELTA_API_KEY')
    api_secret = os.getenv('DELTA_API_SECRET')
    if api_key:
        print(f"   ✅ Loaded via env_loader: {api_key[:8]}...")
    
print()

# Test 2: Test DeltaClient
print("2️⃣ Testing DeltaClient...")
try:
    from bot.api.delta_client import DeltaClient
    client = DeltaClient()
    print(f"   ✅ DeltaClient initialized")
    print(f"   Base URL: {client.base}")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 3: Fetch wallet balances
print("3️⃣ Fetching Wallet Balances...")
try:
    response = client.get_wallet_balances()
    print(f"   Response: {response}")
    
    if response.get('success') and response.get('result'):
        wallets = response['result']
        for wallet in wallets:
            print(f"\n   Wallet: {wallet.get('asset_symbol', 'Unknown')}")
            print(f"   - Balance: {wallet.get('balance', 0)}")
            print(f"   - Available: {wallet.get('available_balance', 0)}")
            print(f"   - Order Margin: {wallet.get('order_margin', 0)}")
            print(f"   - Position Margin: {wallet.get('position_margin', 0)}")
            print(f"   - Maintenance Margin: {wallet.get('maintenance_margin', 0)}")
    else:
        print(f"   ❌ No wallet data: {response}")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 4: Fetch positions
print("4️⃣ Fetching Positions...")
try:
    response = client.fetch_positions()
    print(f"   Response type: {type(response)}")
    
    if isinstance(response, list):
        print(f"   ✅ Found {len(response)} positions")
        for pos in response:
            info = pos.get('info', {})
            print(f"\n   Position: {info.get('product_symbol', 'Unknown')}")
            print(f"   - Size: {info.get('size', 0)}")
            print(f"   - Entry Price: {pos.get('entryPrice', 0)}")
            print(f"   - Mark Price: {pos.get('markPrice', 0)}")
            print(f"   - Unrealized PnL: {pos.get('unrealizedPnl', 0)}")
            print(f"   - Initial Margin: {pos.get('initialMargin', 0)}")
    elif isinstance(response, dict):
        if response.get('success') and response.get('result'):
            positions = response['result']
            print(f"   ✅ Found {len(positions)} positions")
            for pos in positions:
                print(f"\n   Position: {pos.get('product_symbol', 'Unknown')}")
                print(f"   - Size: {pos.get('size', 0)}")
                print(f"   - Entry Price: {pos.get('entry_price', 0)}")
                print(f"   - Mark Price: {pos.get('mark_price', 0)}")
        else:
            print(f"   ❌ No position data: {response}")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

# Test 5: Test IntegratedLiquidationMonitor
print("5️⃣ Testing IntegratedLiquidationMonitor...")
try:
    from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
    from config_manager import ConfigManager
    
    config_manager = ConfigManager()
    config_data = config_manager.load_config_env()
    
    monitor = IntegratedLiquidationMonitor(config=config_data)
    print(f"   ✅ Monitor initialized")
    
    # Get status
    status = monitor.get_status()
    print(f"\n   Status:")
    print(f"   - Total Balance: {status.get('total_balance', 0)}")
    print(f"   - Available Balance: {status.get('available_balance', 0)}")
    print(f"   - Blocked Balance: {status.get('blocked_balance', 0)}")
    print(f"   - Margin Utilization: {status.get('margin_utilization', 0)}%")
    print(f"   - Liquidation Distance: {status.get('liquidation_distance', 0)}%")
    print(f"   - Total Unrealized PnL: ₹{status.get('total_unrealized_pnl', 0)}")
    print(f"   - Total Positions: {status.get('total_positions', 0)}")
    
    if 'error' in status:
        print(f"\n   ❌ Error in status: {status['error']}")
    
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()

print("=" * 70)
print("✅ Test Complete")
print("=" * 70)
