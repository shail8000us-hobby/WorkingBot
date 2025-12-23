#!/usr/bin/env python3
"""
Checksum Update Utility
=======================
Automatically regenerates checksums for production-locked files.
Use this after making approved changes to avoid integrity check failures.

Usage:
    python3 update_checksums.py
    python3 update_checksums.py --verify-only
"""

import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime

REGISTRY_FILE = ".locked_files_registry.json"

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return None

def load_registry():
    """Load the locked files registry"""
    try:
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Registry file not found: {REGISTRY_FILE}")
        sys.exit(1)

def save_registry(registry):
    """Save the updated registry"""
    registry['last_updated'] = datetime.now().strftime("%Y-%m-%d")
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)
    print(f"✅ Registry updated: {REGISTRY_FILE}")

def verify_checksums(registry):
    """Verify all checksums and report mismatches"""
    print("\n" + "="*60)
    print("INTEGRITY VERIFICATION")
    print("="*60)
    
    mismatches = []
    verified = 0
    
    for file_entry in registry.get('locked_files', []):
        file_path = file_entry['path']
        expected_hash = file_entry.get('sha256')
        
        if not expected_hash:
            continue
            
        actual_hash = calculate_sha256(file_path)
        
        if actual_hash is None:
            print(f"⚠️  {file_path}: FILE NOT FOUND")
            continue
            
        if actual_hash == expected_hash:
            print(f"✅ {file_path}: OK")
            verified += 1
        else:
            print(f"❌ {file_path}: MISMATCH")
            print(f"   Expected: {expected_hash}")
            print(f"   Actual:   {actual_hash}")
            mismatches.append((file_path, expected_hash, actual_hash))
    
    print("="*60)
    print(f"Verified: {verified}")
    print(f"Mismatches: {len(mismatches)}")
    print("="*60)
    
    return mismatches

def update_checksums(registry, auto_approve=False):
    """Update all checksums in the registry"""
    print("\n" + "="*60)
    print("CHECKSUM UPDATE")
    print("="*60)
    
    updated = 0
    
    for file_entry in registry.get('locked_files', []):
        file_path = file_entry['path']
        old_hash = file_entry.get('sha256')
        
        if not old_hash:
            continue
            
        new_hash = calculate_sha256(file_path)
        
        if new_hash is None:
            print(f"⚠️  {file_path}: FILE NOT FOUND (skipped)")
            continue
            
        if new_hash != old_hash:
            if not auto_approve:
                print(f"\n📝 {file_path}:")
                print(f"   Old: {old_hash}")
                print(f"   New: {new_hash}")
                response = input("   Update checksum? (y/N): ").strip().lower()
                if response != 'y':
                    print("   ⏭️  Skipped")
                    continue
            
            file_entry['sha256'] = new_hash
            file_entry['last_modified'] = datetime.now().strftime("%Y-%m-%d")
            print(f"✅ {file_path}: Updated")
            updated += 1
        else:
            print(f"✅ {file_path}: No change")
    
    print("="*60)
    print(f"Updated: {updated} files")
    print("="*60)
    
    return updated

def main():
    """Main entry point"""
    verify_only = '--verify-only' in sys.argv
    auto_approve = '--auto' in sys.argv
    
    print("🔒 Production File Checksum Utility")
    print("="*60)
    
    registry = load_registry()
    
    # Always verify first
    mismatches = verify_checksums(registry)
    
    if verify_only:
        sys.exit(0 if not mismatches else 1)
    
    if not mismatches:
        print("\n✅ All checksums match. No updates needed.")
        return
    
    print(f"\n⚠️  Found {len(mismatches)} file(s) with checksum mismatches.")
    
    if not auto_approve:
        response = input("\nUpdate all checksums? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Aborted by user")
            sys.exit(1)
    
    updated = update_checksums(registry, auto_approve=auto_approve)
    
    if updated > 0:
        save_registry(registry)
        print("\n✅ Checksums updated successfully!")
        print("⚠️  IMPORTANT: Test your bot in --dry-run mode before production!")
    else:
        print("\n✅ No updates applied.")

if __name__ == '__main__':
    main()
