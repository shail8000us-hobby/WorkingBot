#!/usr/bin/env python3
"""
State File Migration Script
Converts legacy state files to v2.0 format with metadata and checksums

Usage:
    python3 migrate_state_to_v2.py
"""

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


def migrate_state_file(input_file: str, output_file: str = None):
    """
    Migrate legacy state file to v2.0 format
    
    Args:
        input_file: Path to legacy state file
        output_file: Path for output (defaults to same file)
    """
    if output_file is None:
        output_file = input_file
    
    print(f"📂 Reading legacy state: {input_file}")
    
    # Read legacy state
    with open(input_file, 'r') as f:
        legacy_state = json.load(f)
    
    # Check if already v2.0 format
    if 'version' in legacy_state and 'data' in legacy_state:
        print("✅ Already v2.0 format, skipping")
        return
    
    print(f"🔄 Converting to v2.0 format...")
    
    # Build v2.0 state
    data = {
        'timestamp': legacy_state.get('timestamp', 0),
        'session_tag': legacy_state.get('session_tag', f'MIGRATED_{int(datetime.now().timestamp())}'),
        'open_tranches': legacy_state.get('open_tranches', []),
        'pending_buy': legacy_state.get('pending_buy') or legacy_state.get('pending_buy_order'),
        'tp_retry_queue': legacy_state.get('tp_retry_queue', []),
        'reserved_capacity': legacy_state.get('reserved_capacity', 0),
        'max_open': legacy_state.get('max_open', 10)
    }
    
    # Calculate checksum
    data_json = json.dumps(data, sort_keys=True)
    checksum = hashlib.sha256(data_json.encode()).hexdigest()[:16]
    
    # Wrap with metadata
    state_v2 = {
        'version': '2.0',
        'schema_version': 1,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'bot_pid': os.getpid(),
        'checksum': checksum,
        'data': data
    }
    
    # Backup original
    backup_file = f"{input_file}.backup_pre_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"💾 Backing up original: {backup_file}")
    with open(backup_file, 'w') as f:
        json.dump(legacy_state, f, indent=2)
    
    # Write migrated state
    temp_file = f"{output_file}.tmp"
    with open(temp_file, 'w') as f:
        json.dump(state_v2, f, indent=2)
    
    # Atomic rename
    os.replace(temp_file, output_file)
    
    print(f"✅ Migration complete!")
    print(f"   Version: 2.0")
    print(f"   Checksum: {checksum}")
    print(f"   Positions: {len(data['open_tranches'])}")
    print(f"   Pending: {data['pending_buy'] is not None}")
    print(f"   Output: {output_file}")


def main():
    """Migrate all state files in workspace"""
    workspace = Path.cwd()
    
    print("=" * 60)
    print("State File Migration to v2.0")
    print("=" * 60)
    
    # Find state files
    state_files = [
        workspace / 'runtime_state.json',
        workspace / 'bot' / 'state' / 'state.json',
    ]
    
    migrated = 0
    skipped = 0
    
    for state_file in state_files:
        if state_file.exists():
            print(f"\n📄 Found: {state_file}")
            try:
                migrate_state_file(str(state_file))
                migrated += 1
            except Exception as e:
                print(f"❌ Failed to migrate {state_file}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⏭️  Skipped (not found): {state_file}")
            skipped += 1
    
    print("\n" + "=" * 60)
    print(f"Migration Summary:")
    print(f"  ✅ Migrated: {migrated}")
    print(f"  ⏭️  Skipped: {skipped}")
    print("=" * 60)


if __name__ == '__main__':
    main()
