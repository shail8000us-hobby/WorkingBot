#!/usr/bin/env python3
"""
Fetch Raw Data from Delta Exchange
====================================
This script fetches and displays RAW data directly from Delta Exchange API
with zero processing or calculations. Use this as the source of truth.

Shows exactly what Delta Exchange returns for:
- Positions (with UPNL)
- Wallet Balance
- Maintenance Margin
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv('secrets/api_keys.env')
load_dotenv('grid_config.env')

# Set up mode-specific config
from bot.utils.env_loader import load_trading_mode_config
try:
    load_trading_mode_config()
    print(f"✅ Mode: {os.getenv('TRADING_MODE', 'unknown')}")
except Exception as e:
    print(f"⚠️ Warning: {e}")

from bot.api.delta_client import DeltaClient

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_json(data, indent=2):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=indent, default=str))

def main():
    """Main function"""
    print_header("🔍 Delta Exchange RAW Data Viewer")
    
    print("\n📝 This script shows EXACTLY what Delta Exchange returns")
    print("   No calculations, no processing, just raw API responses")
    
    # Initialize client
    print("\n🚀 Initializing Delta Exchange API client...")
    client = DeltaClient()
    
    # ========================================
    # 1. Fetch Positions
    # ========================================
    print_header("📊 1. POSITIONS (GET /v2/positions)")
    
    try:
        positions = client.fetch_positions()
        
        if isinstance(positions, dict) and positions.get('success'):
            pos_list = positions.get('result', [])
        elif isinstance(positions, list):
            pos_list = positions
        else:
            pos_list = []
        
        print(f"\n✅ Found {len(pos_list)} positions\n")
        
        total_upnl = 0
        
        for i, pos in enumerate(pos_list, 1):
            info = pos.get('info', {})
            size = float(info.get('size', 0))
            
            if size == 0:
                continue  # Skip closed positions
            
            print(f"Position #{i}:")
            print(f"   Symbol: {info.get('product_symbol', 'UNKNOWN')}")
            print(f"   Product ID: {info.get('product_id', 'N/A')}")
            print(f"   Size: {size}")
            print(f"   Side: {pos.get('side', 'N/A')}")
            print(f"   Entry Price: {pos.get('entryPrice', 0)}")
            print(f"   Mark Price: {pos.get('markPrice', 0)}")
            print(f"   Liquidation Price: {pos.get('liquidationPrice', 'N/A')}")
            
            # UPNL from different fields
            upnl_1 = float(pos.get('unrealizedPnl', 0))
            upnl_2 = float(info.get('unrealized_pnl', 0))
            upnl_3 = float(info.get('unrealized_funding_pnl', 0))
            
            print(f"   UPNL Fields:")
            print(f"      pos.unrealizedPnl: ${upnl_1:.2f}")
            print(f"      info.unrealized_pnl: ${upnl_2:.2f}")
            print(f"      info.unrealized_funding_pnl: ${upnl_3:.2f}")
            
            # Use the first non-zero value
            upnl = upnl_1 or upnl_2 or upnl_3
            total_upnl += upnl
            
            print(f"   → Using UPNL: ${upnl:.2f} USD = ₹{upnl * 85:,.2f} INR")
            print()
        
        print(f"📊 TOTAL UPNL (Sum of all positions):")
        print(f"   ${total_upnl:.2f} USD")
        print(f"   ₹{total_upnl * 85:,.2f} INR")
        
        # Show raw JSON for first position (for debugging)
        if pos_list:
            print(f"\n🔍 Raw JSON for Position #1:")
            print_json(pos_list[0])
    
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================
    # 2. Fetch Wallet Balances
    # ========================================
    print_header("💰 2. WALLET BALANCE (GET /v2/wallet/balances)")
    
    try:
        wallet_response = client.get_wallet_balances()
        
        if wallet_response.get('success'):
            wallets = wallet_response.get('result', [])
            meta = wallet_response.get('meta', {})
            
            print(f"\n✅ Found {len(wallets)} wallet(s)\n")
            
            for i, wallet in enumerate(wallets, 1):
                print(f"Wallet #{i}:")
                print(f"   Asset: {wallet.get('asset_symbol', 'N/A')}")
                print(f"   Asset ID: {wallet.get('asset_id', 'N/A')}")
                print(f"   Balance: ${wallet.get('balance', 0):.2f}")
                print(f"   Available Balance: ${wallet.get('available_balance', 0):.2f}")
                print(f"   Order Margin: ${wallet.get('order_margin', 0):.2f}")
                print(f"   Position Margin: ${wallet.get('position_margin', 0):.2f}")
                print(f"   Blocked Margin: ${wallet.get('blocked_margin', 0):.2f}")
                print(f"   Portfolio Margin: ${wallet.get('portfolio_margin', 0):.2f}")
                print(f"   Commission Blocked: ${wallet.get('commission_blocked', 0):.2f}")
                print()
            
            # Meta information
            if meta:
                print(f"📊 Meta Information:")
                print(f"   Net Equity: ${meta.get('net_equity', 0):.2f}")
                print(f"   ROE: {meta.get('roepercent', 0):.4f}%")
                print()
                print(f"🔍 Raw Meta JSON:")
                print_json(meta)
            
            # Show raw JSON for first wallet
            if wallets:
                print(f"\n🔍 Raw JSON for Wallet #1:")
                print_json(wallets[0])
        
        else:
            print(f"❌ API returned error: {wallet_response}")
    
    except Exception as e:
        print(f"❌ Error fetching wallet: {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================
    # 3. Calculate UPNL from Net Equity
    # ========================================
    print_header("📈 3. UPNL CALCULATION (from net_equity)")
    
    try:
        wallet_response = client.get_wallet_balances()
        if wallet_response.get('success') and wallet_response.get('result'):
            wallet = wallet_response['result'][0]
            meta = wallet_response.get('meta', {})
            
            balance = float(wallet.get('balance', 0))
            net_equity = float(meta.get('net_equity', 0))
            
            # UPNL = net_equity - balance
            upnl_from_equity = net_equity - balance
            
            print(f"\nFormula: UPNL = net_equity - balance")
            print(f"   Net Equity: ${net_equity:.2f}")
            print(f"   Balance: ${balance:.2f}")
            print(f"   → UPNL: ${upnl_from_equity:.2f} USD")
            print(f"   → UPNL: ₹{upnl_from_equity * 85:,.2f} INR")
    
    except Exception as e:
        print(f"❌ Error calculating UPNL: {e}")
    
    # ========================================
    # 4. Summary
    # ========================================
    print_header("📝 SUMMARY - What Delta Exchange Shows")
    
    try:
        # Get positions UPNL
        positions = client.fetch_positions()
        if isinstance(positions, dict) and positions.get('success'):
            pos_list = positions.get('result', [])
        elif isinstance(positions, list):
            pos_list = positions
        else:
            pos_list = []
        
        total_upnl_positions = 0
        for pos in pos_list:
            info = pos.get('info', {})
            size = float(info.get('size', 0))
            if size != 0:
                upnl = float(info.get('unrealized_pnl', 0) or pos.get('unrealizedPnl', 0))
                total_upnl_positions += upnl
        
        # Get wallet UPNL
        wallet_response = client.get_wallet_balances()
        if wallet_response.get('success') and wallet_response.get('result'):
            wallet = wallet_response['result'][0]
            meta = wallet_response.get('meta', {})
            balance = float(wallet.get('balance', 0))
            net_equity = float(meta.get('net_equity', 0))
            total_upnl_wallet = net_equity - balance
            blocked_margin = float(wallet.get('blocked_margin', 0) or wallet.get('portfolio_margin', 0))
        else:
            total_upnl_wallet = 0
            balance = 0
            blocked_margin = 0
        
        print(f"\n💰 Balance:")
        print(f"   ${balance:,.2f} USD = ₹{balance * 85:,.2f} INR")
        
        print(f"\n📊 UPNL (Method 1 - Sum of Positions):")
        print(f"   ${total_upnl_positions:,.2f} USD")
        print(f"   ₹{total_upnl_positions * 85:,.2f} INR")
        
        print(f"\n📊 UPNL (Method 2 - Net Equity - Balance):")
        print(f"   ${total_upnl_wallet:,.2f} USD")
        print(f"   ₹{total_upnl_wallet * 85:,.2f} INR")
        
        print(f"\n🛡️ Blocked Margin:")
        print(f"   ${blocked_margin:,.2f} USD")
        print(f"   ₹{blocked_margin * 85:,.2f} INR")
        
        # Recommendation
        print(f"\n✅ RECOMMENDED UPNL (Method 2):")
        print(f"   ${total_upnl_wallet:,.2f} USD")
        print(f"   ₹{total_upnl_wallet * 85:,.2f} INR")
        print(f"\n   This is what your liquidation monitor should show!")
        
        # Comparison with screenshots
        print(f"\n📸 Compare with your Delta Exchange UI:")
        print(f"   1. Check 'Total UPNL' value")
        print(f"   2. It should match: ${total_upnl_wallet:.2f} USD")
        print(f"   3. If it doesn't match, there may be pending trades")
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
    
    print_header("✅ Complete")
    print("\n💡 Next Steps:")
    print("   1. Compare the UPNL values above with your Delta Exchange UI")
    print("   2. If they match, your API credentials are correct")
    print("   3. Run test_delta_websocket.py to verify WebSocket data")
    print("   4. Run test_liquidation_data_accuracy.py to verify monitor")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
