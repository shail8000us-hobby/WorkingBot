#!/usr/bin/env python3
"""
One-time permission fix for WebUI frontend build directory.
Run this once after building the frontend, or whenever you get permission errors.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FRONTEND_BUILD = PROJECT_ROOT / "webui" / "frontend" / "build"

def main():
    if not FRONTEND_BUILD.exists():
        print(f"❌ Frontend build directory not found: {FRONTEND_BUILD}")
        print("💡 Run: cd webui/frontend && npm run build")
        return 1
    
    print(f"🔧 Fixing permissions on: {FRONTEND_BUILD}")
    
    try:
        # Step 1: Clear extended attributes (macOS Documents folder protection)
        print("   1. Clearing macOS extended attributes...")
        xattr_result = subprocess.run(
            ["xattr", "-cr", str(FRONTEND_BUILD)],
            capture_output=True,
            text=True
        )
        if xattr_result.returncode == 0:
            print("      ✅ Extended attributes cleared")
        else:
            print(f"      ⚠️  xattr returned code {xattr_result.returncode}")
        
        # Step 2: Fix permissions
        print("   2. Setting directory permissions to 755...")
        result = subprocess.run(
            ["chmod", "-R", "755", str(FRONTEND_BUILD)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("      ✅ Permissions set to 755")
            print("")
            print("✅ All fixes applied successfully!")
            print(f"✅ WebUI should now be accessible at http://localhost:5555")
            print("")
            print("💡 If error reappears, macOS is re-adding protection.")
            print("   Solution: Move project outside ~/Documents folder")
            return 0
        else:
            print(f"⚠️  chmod returned code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return result.returncode
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
