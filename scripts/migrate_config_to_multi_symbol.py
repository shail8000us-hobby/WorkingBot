#!/usr/bin/env python3
"""
Config Migration Script: v4.0 (single-symbol) → v5.0 (multi-symbol)
Migrates config.yaml from single BTCUSD bot to multi-symbol architecture
"""

import yaml
import sys
from pathlib import Path
from datetime import datetime

def migrate_config():
    """Migrate v4.0 single-symbol config to v5.0 multi-symbol"""
    
    config_file = Path("config.yaml")
    backup_file = Path("config.yaml.backup.v4.0")
    
    if not backup_file.exists():
        print("❌ Backup file not found: config.yaml.backup.v4.0")
        print("   Run: cp config.yaml config.yaml.backup.v4.0")
        sys.exit(1)
    
    # Load current config
    print("📂 Loading current config...")
    with open(config_file) as f:
        old_config = yaml.safe_load(f)
    
    # Extract symbol info
    try:
        symbol = old_config['bot']['symbol']  # 'BTCUSD'
        mode = old_config['bot']['mode']  # 'LONG'
        
        # Get product_id from api.live or api.demo
        trading_mode = old_config.get('trading_mode', 'live')
        if trading_mode == 'live':
            product_id = old_config['api']['live']['product_id']
        else:
            product_id = old_config['api']['demo']['product_id']
        
        print(f"\n📊 Current Configuration:")
        print(f"   Symbol: {symbol}")
        print(f"   Mode: {mode}")
        print(f"   Product ID: {product_id}")
        print(f"   Trading Mode: {trading_mode}")
        
    except KeyError as e:
        print(f"❌ Error extracting config: {e}")
        print("   Config might be in unexpected format")
        sys.exit(1)
    
    # Create new multi-symbol structure
    print("\n🔄 Creating multi-symbol structure...")
    
    new_config = {
        'version': '5.0',
        'trading_mode': old_config.get('trading_mode', 'live'),
        
        # Capital allocation (ADJUST THESE VALUES!)
        'capital_allocation': {
            'total_capital_usd': 10000,  # TODO: Update with actual capital
            'allocations': {
                'BTCUSD': {
                    'capital_usd': 7000,
                    'percentage': 70,
                    'max_position_value_usd': 5000
                },
                'ETHUSD': {
                    'capital_usd': 3000,
                    'percentage': 30,
                    'max_position_value_usd': 2000
                }
            }
        },
        
        # Multi-symbol configuration
        'symbols': {
            symbol: {
                'enabled': True,
                'product_id': product_id,
                'mode': mode,
                'capital': {
                    'allocated_usd': 7000,
                    'max_position_value_usd': 5000
                },
                'grid': old_config.get('grid', {}),
                'safety': {
                    'max_account_loss_inr': old_config.get('guardian', {}).get('max_account_loss_inr', 10000),
                    'min_liquidation_distance_pct': old_config.get('safety', {}).get('min_liquidation_distance_pct', 10.0)
                }
            },
            'ETHUSD': {
                'enabled': False,  # Disabled initially - enable after testing
                'product_id': 3136,  # Verified from Delta Exchange API
                'mode': 'LONG',
                'capital': {
                    'allocated_usd': 3000,
                    'max_position_value_usd': 2000
                },
                'grid': {
                    'geometry': {
                        'lower': 3200,  # TODO: Adjust based on current ETH price
                        'upper': 3800,
                        'step': 50,
                        'reference': 3500
                    },
                    'limits': {
                        'max_open_positions': 30,
                        'lot_size': 10,
                        'max_open_orders': 15,
                        'max_qty_per_order': 3
                    },
                    'behavior': {
                        'strict_grid': True,
                        'tick_size': 0.05,  # Verified from API
                        'rung_snap_mode': 'below'
                    }
                },
                'safety': {
                    'max_account_loss_inr': 5000,
                    'min_liquidation_distance_pct': 10.0
                }
            }
        }
    }
    
    # Copy all shared sections (everything except bot, grid, safety which are now in symbols)
    shared_sections = [
        'capital_protection', 'guardian', 'safety', 'startup',
        'shutdown', 'order_execution', 'heartbeat', 'api',
        'telegram', 'logging', 'webui'
    ]
    
    for section in shared_sections:
        if section in old_config:
            new_config[section] = old_config[section]
    
    # Write new config
    print("\n💾 Writing new config.yaml...")
    with open(config_file, 'w') as f:
        yaml.dump(new_config, f, default_flow_style=False, indent=2, sort_keys=False)
    
    print("✅ Config migrated to v5.0 multi-symbol format")
    print(f"\n📋 Summary:")
    print(f"   Backup saved to: {backup_file}")
    print(f"   BTCUSD: enabled={new_config['symbols']['BTCUSD']['enabled']}, product_id={new_config['symbols']['BTCUSD']['product_id']}")
    print(f"   ETHUSD: enabled={new_config['symbols']['ETHUSD']['enabled']}, product_id={new_config['symbols']['ETHUSD']['product_id']}")
    
    print(f"\n⚠️  IMPORTANT:")
    print(f"   1. Review capital_allocation section and update actual capital amounts")
    print(f"   2. Check ETH grid bounds (lower/upper/reference) based on current price")
    print(f"   3. Test config loading: python3 -c 'from config.loader import get_config; get_config()'")
    print(f"   4. Keep ETHUSD disabled until Phase 1 complete")
    
    return True

if __name__ == "__main__":
    print("=" * 80)
    print("Config Migration: v4.0 → v5.0 (Multi-Symbol)")
    print("=" * 80)
    print()
    
    try:
        success = migrate_config()
        if success:
            print("\n✅ Migration complete!")
            print("\nNext steps:")
            print("  1. Review new config.yaml")
            print("  2. Update capital allocation values")
            print("  3. Test config loading")
            print("  4. Proceed with Phase 1A config models update")
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n🔄 To restore:")
        print(f"   cp config.yaml.backup.v4.0 config.yaml")
        sys.exit(1)
