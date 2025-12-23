#!/usr/bin/env python3
"""
Clear Drawdown Protective Mode

Clears the protective mode flag and forces the equity tracker to reload.
Use when protective mode is stuck active despite low drawdown.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.capital.equity_tracker import get_equity_tracker, reload_equity_tracker

def main():
    print("🔧 Clearing Protective Mode...")
    print()
    
    # Get base directory
    base_dir = Path(__file__).parent
    
    # Check flag file
    flag_file = base_dir / '.drawdown_protective_mode'
    if flag_file.exists():
        print(f"   Found flag file: {flag_file}")
        flag_file.unlink()
        print("   ✅ Deleted flag file")
    else:
        print("   ℹ️  No flag file found")
    
    # Reload tracker to clear in-memory state
    print()
    print("   Reloading equity tracker...")
    reload_equity_tracker()
    
    # Get fresh tracker instance
    tracker = get_equity_tracker(base_dir)
    
    # Get current stats
    stats = tracker.get_stats()
    
    print()
    print("📊 Current Status:")
    print(f"   Drawdown: {stats['current_drawdown_pct']:.2f}%")
    print(f"   Limit: {stats['max_drawdown_pct']}%")
    print(f"   Protective Mode: {'ACTIVE ⚠️' if stats['protective_mode'] else 'INACTIVE ✅'}")
    print()
    
    if stats['protective_mode']:
        print("❌ Protective mode still active!")
        print("   This means the tracker is reading from snapshot data.")
        print("   Try restarting the WebUI backend:")
        print("   launchctl restart com.gridbot.webui")
    else:
        print("✅ Protective mode successfully cleared!")
        print("   Refresh your WebUI to see the update.")

if __name__ == '__main__':
    main()
