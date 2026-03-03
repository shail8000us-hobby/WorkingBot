#!/usr/bin/env python3
"""
Test script for reconciliation system
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from bot.reconciliation import get_reconciliation_engine, get_data_sources_manager
from bot.api.delta_client import DeltaClient

def test_reconciliation():
    """Test reconciliation system"""
    print("\n" + "="*60)
    print("🧪 Testing Reconciliation System")
    print("="*60 + "\n")
    
    # Test 1: Initialize data sources manager
    print("📊 Test 1: Initialize Data Sources Manager")
    try:
        data_manager = get_data_sources_manager(
            base_dir=str(BASE_DIR),
            delta_client_factory=lambda: DeltaClient()
        )
        print("✅ Data sources manager initialized")
        print(f"   Base dir: {data_manager.base_dir}")
        print(f"   Orders file: {data_manager.orders_file}")
        print(f"   Orders file exists: {data_manager.orders_file.exists()}")
    except Exception as e:
        print(f"❌ Failed to initialize data sources manager: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Load bot orders
    print("\n📊 Test 2: Load Bot Orders")
    try:
        bot_orders = data_manager.get_bot_orders(force_refresh=True)
        print(f"✅ Loaded {len(bot_orders)} bot orders")
        if bot_orders:
            print(f"   Sample order: {bot_orders[0].get('order_id')} - {bot_orders[0].get('side')} @ {bot_orders[0].get('price')}")
    except Exception as e:
        print(f"❌ Failed to load bot orders: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Load exchange orders
    print("\n📊 Test 3: Load Exchange Orders")
    try:
        exchange_orders = data_manager.get_exchange_orders(force_refresh=True)
        print(f"✅ Loaded {len(exchange_orders)} exchange orders")
        if exchange_orders:
            sample = exchange_orders[0]
            print(f"   Sample order: {sample.get('id')} - {sample.get('side')} @ {sample.get('price', sample.get('limit_price'))}")
    except Exception as e:
        print(f"❌ Failed to load exchange orders: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Run full reconciliation
    print("\n📊 Test 4: Run Full Reconciliation")
    try:
        engine = get_reconciliation_engine(
            base_dir=str(BASE_DIR),
            delta_client_factory=lambda: DeltaClient()
        )
        print("✅ Reconciliation engine initialized")
        
        result = engine.reconcile(force_refresh=True)
        print(f"✅ Reconciliation completed")
        print(f"   Status: {result.get('status')}")
        
        if result.get('status') == 'success':
            summary = result.get('summary', {})
            print(f"\n📊 Summary:")
            print(f"   Total orders: {summary.get('total_orders', 0)}")
            print(f"   Bot orders: {summary.get('bot_orders', 0)}")
            print(f"   Manual orders: {summary.get('manual_orders', 0)}")
            print(f"   Unknown orders: {summary.get('unknown_orders', 0)}")
            print(f"   Matched orders: {summary.get('matched_orders', 0)}")
            print(f"   Mismatched orders: {summary.get('mismatched_orders', 0)}")
            print(f"   Exchange only: {summary.get('exchange_only_orders', 0)}")
            print(f"   Bot only: {summary.get('bot_only_orders', 0)}")
            
            records = result.get('records', [])
            print(f"\n📊 Records: {len(records)} total")
            
            # Show sample records
            if records:
                print("\n📋 Sample Records:")
                for i, record in enumerate(records[:3]):
                    print(f"\n   Record {i+1}:")
                    print(f"      Order ID: {record.get('order_id')}")
                    print(f"      Client ID: {record.get('client_order_id')}")
                    print(f"      Side: {record.get('side')}")
                    print(f"      Price: {record.get('price')}")
                    print(f"      Size: {record.get('size')}")
                    print(f"      Provenance: {record.get('provenance')}")
                    print(f"      Source: {record.get('source')}")
                    print(f"      Discrepancy: {record.get('discrepancy')}")
        else:
            print(f"❌ Reconciliation failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Failed to run reconciliation: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("✅ Test completed")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_reconciliation()
