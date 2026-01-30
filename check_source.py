#!/usr/bin/env python3
"""Check if source has debug logging."""
source_file = '/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/options/OptionsPanel.js'
with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()
    
if "[AUTO-LOOP] executeAutoLoop called" in content:
    print("✅ Debug logging FOUND in source file")
    # Find the line
    for i, line in enumerate(content.split('\n'), 1):
        if "[AUTO-LOOP] executeAutoLoop called" in line:
            print(f"   Line {i}: {line.strip()}")
else:
    print("❌ Debug logging NOT FOUND in source file")
    # Check for any AUTO-LOOP mentions
    for i, line in enumerate(content.split('\n'), 1):
        if "AUTO-LOOP" in line:
            print(f"   Line {i}: {line.strip()[:100]}")
