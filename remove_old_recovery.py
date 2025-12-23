#!/usr/bin/env python3
"""
Script to remove OLD recovery system from async_gridbot.py
"""

import re

# Read the file
with open('bot/strategy/async_gridbot.py', 'r') as f:
    content = f.read()

# Remove recovery flags
content = re.sub(
    r"        # Opportunistic Recovery Mode\n        self\._opportunistic_recovery_active = False\n        self\._recovery_orders = \{\}.*?\n        \n",
    "",
    content,
    flags=re.DOTALL
)

# Remove recovery methods (lines ~941-1328)
# Find the section starting with "_check_startup_opportunistic_recovery"
# and ending before "async def start"
pattern = r"    async def _check_startup_opportunistic_recovery\(self\).*?(?=    # Volatility halt handling REMOVED)"
content = re.sub(pattern, "", content, flags=re.DOTALL)

# Remove recovery checks in _process_fill
content = re.sub(
    r"            # CRITICAL FIX NOV 19: Check if recovery mode is active.*?\n            if self\._opportunistic_recovery_active:.*?return\n",
    "",
    content,
    flags=re.DOTALL
)

# Remove recovery checks in _check_and_place_entry_order
content = re.sub(
    r"                # CRITICAL: Skip normal grid operations during recovery\n                if self\._opportunistic_recovery_active:.*?return\n                \n",
    "",
    content,
    flags=re.DOTALL
)

# Remove recovery status in logging
content = re.sub(
    r"                        elif self\._opportunistic_recovery_active:\n                            trading_status = \" \| 🔄 RECOVERY MODE\"\n",
    "",
    content
)

# Remove recovery check in start() method
content = re.sub(
    r"        # Check opportunistic recovery status.*?log\.info\(\"=\" \* 98\)\n        log\.info\(\"\"\)\n        \n",
    "",
    content,
    flags=re.DOTALL
)

# Write back
with open('bot/strategy/async_gridbot.py', 'w') as f:
    f.write(content)

print("✅ OLD recovery system removed successfully!")
print("✅ File saved: bot/strategy/async_gridbot.py")
