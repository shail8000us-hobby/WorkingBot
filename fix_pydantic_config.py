#!/usr/bin/env python3
"""
Quick fix for Pydantic config validation error.
Converts numeric/bool values to strings in config.yaml
"""

import yaml
import sys
from pathlib import Path

CONFIG_PATH = Path("/Users/ssr/Projects/WorkingBot/config.yaml")
BACKUP_PATH = Path("/Users/ssr/Projects/WorkingBot/config.yaml.backup_before_pydantic_fix")

def convert_to_strings(obj):
    """Recursively convert all int/float/bool values to strings"""
    if isinstance(obj, dict):
        return {k: convert_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_strings(item) for item in obj]
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, bool):
        return str(obj).lower()  # "true" or "false"
    else:
        return obj

def main():
    print("🔧 Fixing Pydantic config validation error...")
    print("")
    
    # Check if config exists
    if not CONFIG_PATH.exists():
        print(f"❌ Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    
    # Backup
    print(f"📦 Creating backup: {BACKUP_PATH}")
    with open(CONFIG_PATH) as f:
        original_content = f.read()
    with open(BACKUP_PATH, 'w') as f:
        f.write(original_content)
    
    # Load config
    print(f"📖 Loading config: {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    
    # Convert symbols section (the problematic one)
    if 'symbols' in config:
        if 'BTCUSD' in config['symbols']:
            print("🔄 Converting numeric/bool values to strings in symbols.BTCUSD...")
            config['symbols']['BTCUSD'] = convert_to_strings(config['symbols']['BTCUSD'])
        if 'ETHUSD' in config['symbols']:
            print("🔄 Converting numeric/bool values to strings in symbols.ETHUSD...")
            config['symbols']['ETHUSD'] = convert_to_strings(config['symbols']['ETHUSD'])
    
    # Save
    print(f"💾 Saving fixed config: {CONFIG_PATH}")
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print("")
    print("✅ Config fixed successfully!")
    print("")
    print("Changed values like:")
    print("  lower: 90000        → lower: '90000'")
    print("  strict_grid: True   → strict_grid: 'true'")
    print("")
    print("Next steps:")
    print("  1. Restart backend: launchctl kickstart -k gui/$(id -u)/com.gridbot.webui")
    print("  2. Wait 5 seconds")
    print("  3. Test: curl http://localhost:5555/")
    print("  4. Open browser: http://localhost:5555")
    print("")
    print("If you need to revert:")
    print(f"  cp {BACKUP_PATH} {CONFIG_PATH}")
    print("")

if __name__ == '__main__':
    main()
