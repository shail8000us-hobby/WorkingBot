#!/usr/bin/env python3
"""WebUI startup wrapper that fixes permissions before starting"""

import os
import sys
import subprocess
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_BUILD = PROJECT_ROOT / "webui" / "frontend" / "build"

# Fix permissions on frontend build directory
if FRONTEND_BUILD.exists():
    try:
        subprocess.run(["chmod", "-R", "755", str(FRONTEND_BUILD)], 
                      stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass  # Ignore permission errors during chmod

# Change to project root
os.chdir(PROJECT_ROOT)

# Add project root to Python path
sys.path.insert(0, str(PROJECT_ROOT))

# Import and run the WebUI main function
if __name__ == "__main__":
    from webui.backend.app import main
    main()
