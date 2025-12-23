"""
Integrity Verification System for Production-Locked Files

This module verifies that production-locked trading files have not been
tampered with or modified without proper approval. It runs on bot startup
to ensure code integrity before any trading operations begin.

Usage:
    from bot.verify_integrity import verify_locked_files
    
    if not verify_locked_files():
        sys.exit(1)  # Abort startup
"""

import hashlib
import json
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

log = logging.getLogger("runner")


class IntegrityVerificationError(Exception):
    """Raised when integrity verification fails"""
    pass


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate SHA256 hash of a file
    
    Args:
        file_path: Path to file
        
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, 'rb') as f:
            # Read file in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        raise IntegrityVerificationError(f"Failed to hash {file_path}: {e}")


def load_registry() -> Optional[Dict]:
    """
    Load the locked files registry
    
    Returns:
        Registry dict or None if not found
    """
    registry_path = Path(".locked_files_registry.json")
    
    if not registry_path.exists():
        return None
    
    try:
        with open(registry_path) as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to load registry: {e}")
        return None


def verify_file_integrity(file_path: str, expected_hash: str) -> Tuple[bool, Optional[str]]:
    """
    Verify integrity of a single file
    
    Args:
        file_path: Path to file
        expected_hash: Expected SHA256 hash
        
    Returns:
        (is_valid, actual_hash or None)
    """
    path = Path(file_path)
    
    if not path.exists():
        return False, None
    
    try:
        actual_hash = calculate_sha256(path)
        is_valid = actual_hash == expected_hash
        return is_valid, actual_hash
    except Exception as e:
        log.error(f"Error verifying {file_path}: {e}")
        return False, None


def verify_locked_files(strict_mode: bool = True) -> bool:
    """
    Verify integrity of all production-locked files
    
    Args:
        strict_mode: If True, fail on any integrity violation.
                    If False, only warn but allow startup.
    
    Returns:
        True if all files valid, False otherwise
    """
    # Load registry
    registry = load_registry()
    
    if registry is None:
        log.warning("⚠️  No locked files registry found (.locked_files_registry.json)")
        log.warning("⚠️  Skipping integrity verification")
        return True
    
    # Check if protection is enabled
    if not registry.get("protection_enabled", True):
        log.info("ℹ️  File protection is disabled in registry")
        return True
    
    # Check if integrity checking is enabled
    if not registry.get("integrity_check_on_startup", True):
        log.info("ℹ️  Integrity check on startup is disabled")
        return True
    
    log.info("🔐 Verifying production-locked files...")
    
    locked_files = registry.get("locked_files", [])
    
    if not locked_files:
        log.info("ℹ️  No locked files defined in registry")
        return True
    
    # Track results
    verified = []
    failed = []
    missing = []
    no_checksum = []
    
    # Verify each file
    for file_info in locked_files:
        path = file_info.get("path")
        expected_hash = file_info.get("sha256")
        description = file_info.get("description", "")
        
        if not path:
            continue
        
        # Skip if no checksum defined
        if not expected_hash or expected_hash == "TO_BE_GENERATED":
            no_checksum.append(path)
            log.warning(f"⚠️  {path}: No checksum defined (skipping)")
            continue
        
        # Verify file
        is_valid, actual_hash = verify_file_integrity(path, expected_hash)
        
        if actual_hash is None:
            # File not found
            missing.append(path)
            log.error(f"❌ {path}: FILE NOT FOUND!")
        elif is_valid:
            # File verified
            verified.append(path)
            log.info(f"✅ {path}: OK")
        else:
            # Integrity violation
            failed.append({
                'path': path,
                'expected': expected_hash,
                'actual': actual_hash,
                'description': description
            })
            log.error(f"❌ {path}: INTEGRITY CHECK FAILED!")
            log.error(f"   Expected: {expected_hash[:16]}...")
            log.error(f"   Actual:   {actual_hash[:16]}...")
    
    # Print summary
    print("")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("           INTEGRITY VERIFICATION SUMMARY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"✅ Verified:       {len(verified)}")
    print(f"❌ Failed:         {len(failed)}")
    print(f"❓ Missing:        {len(missing)}")
    print(f"⚠️  No Checksum:    {len(no_checksum)}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    
    # If any failures, show detailed information
    if failed or missing:
        print("")
        print("🚨 CRITICAL: Production-locked files have been modified!")
        print("")
        
        if failed:
            print("Files with integrity violations:")
            for file in failed:
                print(f"  • {file['path']}")
                print(f"    Description: {file['description']}")
                print(f"    Expected: {file['expected'][:32]}...")
                print(f"    Actual:   {file['actual'][:32]}...")
            print("")
        
        if missing:
            print("Missing files:")
            for path in missing:
                print(f"  • {path}")
            print("")
        
        print("🛑 BOT STARTUP ABORTED")
        print("")
        print("Options to resolve:")
        print("  1. Restore files from backup:")
        print(f"     cp backups/golden_master/* bot/")
        print("")
        print("  2. Revert to last known good version:")
        print("     git checkout 🔒v1.0.0-stable")
        print("")
        print("  3. If changes were intentional:")
        print("     a. Review changes carefully")
        print("     b. Test in dry-run mode")
        print("     c. Regenerate checksums:")
        print("        shasum -a 256 bot/strategy/gridbot.py > .checksums/gridbot.sha256")
        print("        shasum -a 256 bot/strategy/modules/*.py > .checksums/modules.sha256")
        print("     d. Update .locked_files_registry.json with new hashes")
        print("")
        
        if strict_mode:
            return False
        else:
            log.warning("⚠️  Running in non-strict mode - allowing startup despite failures")
            return True
    
    # All files verified
    log.info("✅ All production-locked files verified successfully")
    return True


def generate_checksums(registry_path: str = ".locked_files_registry.json") -> bool:
    """
    Generate checksums for all locked files and update registry
    
    This should be run after intentional modifications to update the
    expected checksums.
    
    Args:
        registry_path: Path to registry file
        
    Returns:
        True if successful
    """
    registry = load_registry()
    
    if registry is None:
        log.error("Registry not found")
        return False
    
    locked_files = registry.get("locked_files", [])
    
    print("🔄 Generating checksums for locked files...")
    print("")
    
    updated = 0
    for file_info in locked_files:
        path = file_info.get("path")
        if not path:
            continue
        
        file_path = Path(path)
        if not file_path.exists():
            log.error(f"❌ {path}: File not found")
            continue
        
        try:
            new_hash = calculate_sha256(file_path)
            file_info["sha256"] = new_hash
            print(f"✅ {path}")
            print(f"   SHA256: {new_hash}")
            updated += 1
        except Exception as e:
            log.error(f"❌ {path}: {e}")
    
    # Save updated registry
    try:
        with open(registry_path, 'w') as f:
            json.dump(registry, f, indent=2)
        
        print("")
        print(f"✅ Updated {updated} checksums in {registry_path}")
        return True
    except Exception as e:
        log.error(f"Failed to save registry: {e}")
        return False


if __name__ == "__main__":
    """
    Run integrity verification from command line
    
    Usage:
        python -m bot.verify_integrity              # Verify files
        python -m bot.verify_integrity --generate   # Generate new checksums
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify integrity of production-locked files")
    parser.add_argument("--generate", action="store_true", 
                       help="Generate new checksums (use after approved modifications)")
    parser.add_argument("--non-strict", action="store_true",
                       help="Allow startup even if verification fails (not recommended)")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    if args.generate:
        success = generate_checksums()
        sys.exit(0 if success else 1)
    else:
        success = verify_locked_files(strict_mode=not args.non_strict)
        sys.exit(0 if success else 1)

