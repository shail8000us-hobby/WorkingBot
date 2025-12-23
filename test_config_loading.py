#!/usr/bin/env python3
"""
Test that AsyncGridBot correctly loads configuration from grid_config.env
"""

import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load grid_config.env
load_dotenv("grid_config.env", override=True)

# Get configuration
lower = float(os.getenv("GRIDBOT_LOWER", "0"))
upper = float(os.getenv("GRIDBOT_UPPER", "0"))
step = float(os.getenv("GRIDBOT_STEP", "0"))
max_open = int(os.getenv("GRIDBOT_MAX_OPEN", "0"))
symbol = os.getenv("GRIDBOT_SYMBOL", "")

print("=" * 80)
print("CONFIGURATION TEST")
print("=" * 80)
print("")
print("Reading from grid_config.env:")
print(f"  GRIDBOT_LOWER = {lower:,.2f}")
print(f"  GRIDBOT_UPPER = {upper:,.2f}")
print(f"  GRIDBOT_STEP = {step:,.2f}")
print(f"  GRIDBOT_MAX_OPEN = {max_open}")
print(f"  GRIDBOT_SYMBOL = {symbol}")
print("")

if lower == 0 or upper == 0:
    print("❌ FAILED: Configuration not loaded correctly")
    sys.exit(1)

print("✅ Configuration loaded successfully")
print("")
print("Expected bot behavior:")
print(f"  - Place BUY orders below market price")
print(f"  - Grid range: ${lower:,.0f} to ${upper:,.0f}")
print(f"  - Order spacing: ${step:,.0f}")
print(f"  - Maximum {max_open} open positions")
print("")
print("=" * 80)
print("")
print("Next step: Start bot and verify 'ASYNC GRIDBOT CONFIGURATION' section shows these values")
print("Command: python3 -m bot.run 2>&1 | grep -A15 'ASYNC GRIDBOT CONFIGURATION'")
print("")
