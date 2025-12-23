#!/usr/bin/env python3
"""
Ghost Order Cleanup Script
==========================

This script identifies and cancels "ghost" orders on Delta Exchange.

Ghost orders are duplicate BUY orders at the same price level that were
created due to Delta 500 errors preventing proper cancellation.

The script will:
1. Fetch ALL open orders from Delta Exchange
2. Identify bot's orders (GBOT_ prefix)
3. Group by price level
4. Keep ONLY the NEWEST order at each price level
5. Cancel all older duplicate orders
6. Keep ALL SELL/TP orders (never cancel these!)

Usage:
    python3 scripts/cleanup_ghost_orders.py [--dry-run] [--auto]
    
Options:
    --dry-run    Show what would be done without actually canceling
    --auto       Auto-confirm without prompting (use with caution!)
"""

import os
import sys
import time
import ccxt
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime

# Load environment
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load API keys only
load_dotenv(os.path.join(project_root, "secrets/api_keys.env"))
load_dotenv(os.path.join(project_root, "secrets", "api_keys.env"))

# Configuration
SYMBOL = "BTCUSD"
GBOT_PREFIX = "GBOT_"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

def get_exchange():
    """Initialize Delta Exchange connection"""
    api_key = os.getenv("DELTA_API_KEY_DEMO" if DEMO_MODE else "DELTA_API_KEY_LIVE")
    api_secret = os.getenv("DELTA_API_SECRET_DEMO" if DEMO_MODE else "DELTA_API_SECRET_LIVE")
    
    if not api_key or not api_secret:
        print("❌ API credentials not found in environment!")
        sys.exit(1)
    
    exchange = ccxt.delta({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    
    if DEMO_MODE:
        exchange.set_sandbox_mode(True)
    
    return exchange

def get_client_id(order):
    """Extract client_order_id from order"""
    try:
        info = order.get("info", {})
        return info.get("client_order_id") or order.get("clientOrderId") or ""
    except:
        return ""

def analyze_orders(exchange):
    """Fetch and analyze all open orders"""
    print("\n" + "="*80)
    print("🔍 FETCHING OPEN ORDERS FROM DELTA EXCHANGE")
    print("="*80)
    
    try:
        orders = exchange.fetch_open_orders(SYMBOL)
        print(f"✅ Found {len(orders)} total open orders\n")
    except Exception as e:
        print(f"❌ Failed to fetch orders: {e}")
        sys.exit(1)
    
    # Categorize orders
    buy_orders = defaultdict(list)  # price -> [orders]
    sell_orders = []
    manual_orders = []
    
    for order in orders:
        cid = get_client_id(order)
        side = str(order.get("side", "")).lower()
        price = float(order.get("price", 0))
        order_id = order.get("id")
        timestamp = order.get("timestamp", 0)
        
        is_bot_order = cid.startswith(GBOT_PREFIX)
        
        if is_bot_order:
            if side == "buy":
                buy_orders[price].append({
                    "id": order_id,
                    "client_id": cid,
                    "price": price,
                    "timestamp": timestamp,
                    "time_str": datetime.fromtimestamp(timestamp/1000).strftime("%H:%M:%S")
                })
            else:  # sell/TP
                sell_orders.append({
                    "id": order_id,
                    "client_id": cid,
                    "price": price,
                    "timestamp": timestamp,
                    "time_str": datetime.fromtimestamp(timestamp/1000).strftime("%H:%M:%S")
                })
        else:
            manual_orders.append({
                "id": order_id,
                "side": side,
                "price": price
            })
    
    # Identify ghost orders (duplicates at same price)
    ghost_orders = []
    normal_buy_orders = []
    
    for price, orders_at_price in buy_orders.items():
        if len(orders_at_price) > 1:
            # Sort by timestamp (newest first)
            sorted_orders = sorted(orders_at_price, key=lambda x: x["timestamp"], reverse=True)
            # Keep newest, mark rest as ghosts
            normal_buy_orders.append(sorted_orders[0])
            ghost_orders.extend(sorted_orders[1:])
        else:
            normal_buy_orders.append(orders_at_price[0])
    
    return {
        "total": len(orders),
        "normal_buys": normal_buy_orders,
        "sell_tp": sell_orders,
        "ghost_buys": ghost_orders,
        "manual": manual_orders
    }

def print_analysis(analysis):
    """Print analysis results"""
    print("\n" + "="*80)
    print("📊 ORDER ANALYSIS RESULTS")
    print("="*80)
    
    print(f"\n┌─────────────────────────────────────────────────────────────────┐")
    print(f"│ Total Orders:        {analysis['total']:>3}                                      │")
    print(f"│ ✅ Normal BUY:        {len(analysis['normal_buys']):>3} (keep these)                            │")
    print(f"│ 🎯 SELL/TP:           {len(analysis['sell_tp']):>3} (keep these)                            │")
    print(f"│ 🚨 Ghost BUY:         {len(analysis['ghost_buys']):>3} (DELETE these - duplicates!)           │")
    print(f"│ 📝 Manual:            {len(analysis['manual']):>3} (ignore these)                          │")
    print(f"└─────────────────────────────────────────────────────────────────┘")
    
    if analysis['ghost_buys']:
        print("\n" + "="*80)
        print("⚠️  GHOST ORDERS TO BE CANCELLED:")
        print("="*80)
        print(f"\n{'Price':<12} {'Time Placed':<12} {'Order ID':<15} {'Client ID':<30}")
        print("-"*80)
        for order in analysis['ghost_buys']:
            print(f"{order['price']:<12.1f} {order['time_str']:<12} {order['id']:<15} {order['client_id']:<30}")
    
    print("\n" + "="*80)
    print("✅ ORDERS TO KEEP:")
    print("="*80)
    print(f"\nNormal BUY orders: {len(analysis['normal_buys'])}")
    print(f"SELL/TP orders: {len(analysis['sell_tp'])}")

def cancel_ghost_orders(exchange, ghost_orders, dry_run=False):
    """Cancel ghost orders"""
    if not ghost_orders:
        print("\n✅ No ghost orders to cancel!")
        return
    
    print(f"\n{'='*80}")
    if dry_run:
        print("🔍 DRY RUN - NO ORDERS WILL BE CANCELLED")
    else:
        print("🗑️  CANCELLING GHOST ORDERS")
    print(f"{'='*80}\n")
    
    cancelled = 0
    failed = 0
    
    for i, order in enumerate(ghost_orders, 1):
        print(f"[{i}/{len(ghost_orders)}] Cancelling {order['id']} @ {order['price']:.1f}...", end=" ")
        
        if dry_run:
            print("SKIPPED (dry run)")
            continue
        
        try:
            exchange.cancel_order(order['id'], SYMBOL)
            print("✅ CANCELLED")
            cancelled += 1
            time.sleep(0.5)  # Rate limit protection
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed += 1
    
    print(f"\n{'='*80}")
    print("📊 CLEANUP SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Cancelled: {cancelled}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {len(ghost_orders)}")
    print(f"{'='*80}\n")

def main():
    """Main cleanup function"""
    import argparse
    parser = argparse.ArgumentParser(description="Clean up ghost orders on Delta Exchange")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually canceling")
    parser.add_argument("--auto", action="store_true", help="Auto-confirm without prompting")
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🧹 GHOST ORDER CLEANUP SCRIPT")
    print("="*80)
    print(f"Mode: {'DEMO (testnet)' if DEMO_MODE else 'LIVE (REAL MONEY!)'}")
    print(f"Symbol: {SYMBOL}")
    print(f"Dry Run: {args.dry_run}")
    print("="*80)
    
    # Initialize exchange
    exchange = get_exchange()
    
    # Analyze orders
    analysis = analyze_orders(exchange)
    
    # Print analysis
    print_analysis(analysis)
    
    # Confirm before cancelling
    if not analysis['ghost_buys']:
        print("\n✨ No ghost orders found! Your exchange is clean.")
        return
    
    if not args.auto and not args.dry_run:
        print(f"\n⚠️  WARNING: About to cancel {len(analysis['ghost_buys'])} ghost orders!")
        response = input("\nProceed with cancellation? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("❌ Cancelled by user")
            return
    
    # Cancel ghost orders
    cancel_ghost_orders(exchange, analysis['ghost_buys'], dry_run=args.dry_run)
    
    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    main()

