#!/usr/bin/env python3
"""
Clear Bot State Script - November 19, 2025

This script completely clears the bot's memory and state, giving it a clean slate.
Run this BEFORE restarting the bot to ensure no corrupted data persists.

Usage:
    python scripts/clear_bot_state.py
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def clear_bot_state():
    """Clear all bot state files and memory."""
    
    print("=" * 80)
    print("BOT STATE CLEANUP - CLEAN SLATE MODE")
    print("=" * 80)
    print()
    
    # List of state files to clear
    state_files = [
        "bot/state/position_state.json",
        "bot/state/order_state.json",
        "bot/state/recovery_state.json",
        "bot/state/saga_state.json",
        ".bot_state.json",
        ".position_state.json",
        ".order_state.json",
    ]
    
    # List of cache/temp files to clear
    cache_files = [
        "bot/cache/positions.cache",
        "bot/cache/orders.cache",
        ".cache",
        "__pycache__",
    ]
    
    cleared_count = 0
    
    # Clear state files
    print("🗑️  Clearing state files...")
    for state_file in state_files:
        file_path = project_root / state_file
        if file_path.exists():
            try:
                if file_path.is_file():
                    file_path.unlink()
                    print(f"   ✅ Deleted: {state_file}")
                    cleared_count += 1
                else:
                    print(f"   ⏭️  Skipped (not a file): {state_file}")
            except Exception as e:
                print(f"   ❌ Failed to delete {state_file}: {e}")
        else:
            print(f"   ⏭️  Not found: {state_file}")
    
    print()
    
    # Clear cache directories
    print("🗑️  Clearing cache directories...")
    for cache_dir in cache_files:
        dir_path = project_root / cache_dir
        if dir_path.exists():
            try:
                if dir_path.is_dir():
                    import shutil
                    shutil.rmtree(dir_path)
                    print(f"   ✅ Deleted directory: {cache_dir}")
                    cleared_count += 1
                elif dir_path.is_file():
                    dir_path.unlink()
                    print(f"   ✅ Deleted file: {cache_dir}")
                    cleared_count += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {cache_dir}: {e}")
        else:
            print(f"   ⏭️  Not found: {cache_dir}")
    
    print()
    
    # Clear Python bytecode
    print("🗑️  Clearing Python bytecode...")
    pycache_count = 0
    for pycache_dir in project_root.rglob("__pycache__"):
        try:
            import shutil
            shutil.rmtree(pycache_dir)
            pycache_count += 1
        except Exception as e:
            print(f"   ❌ Failed to delete {pycache_dir}: {e}")
    
    if pycache_count > 0:
        print(f"   ✅ Deleted {pycache_count} __pycache__ directories")
        cleared_count += pycache_count
    else:
        print(f"   ⏭️  No __pycache__ directories found")
    
    print()
    
    # Clear .pyc files
    print("🗑️  Clearing .pyc files...")
    pyc_count = 0
    for pyc_file in project_root.rglob("*.pyc"):
        try:
            pyc_file.unlink()
            pyc_count += 1
        except Exception as e:
            print(f"   ❌ Failed to delete {pyc_file}: {e}")
    
    if pyc_count > 0:
        print(f"   ✅ Deleted {pyc_count} .pyc files")
        cleared_count += pyc_count
    else:
        print(f"   ⏭️  No .pyc files found")
    
    print()
    print("=" * 80)
    print(f"✅ CLEANUP COMPLETE - {cleared_count} items cleared")
    print("=" * 80)
    print()
    print("📋 NEXT STEPS:")
    print("   1. Review the cleared items above")
    print("   2. Restart the bot: pm2 restart gridbot-live")
    print("   3. Bot will start with completely clean state")
    print("   4. All positions and orders will be fetched fresh from exchange")
    print()
    print("⚠️  NOTE: This does NOT delete:")
    print("   - Configuration files (config.yaml)")
    print("   - Log files")
    print("   - SQL database events")
    print("   - Exchange orders/positions (those remain on exchange)")
    print()

if __name__ == "__main__":
    try:
        clear_bot_state()
    except KeyboardInterrupt:
        print("\n\n❌ Cleanup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
