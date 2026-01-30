#!/usr/bin/env python3
"""Check if the frontend build contains the auto-loop debug logging."""
import os
import glob

build_dir = "/Users/ssr/Projects/WorkingBot/webui/frontend/build/static/js"

# Find all main-*.js files and check their modification time
main_files = glob.glob(os.path.join(build_dir, "main-*.js"))

for f in main_files:
    mtime = os.path.getmtime(f)
    import datetime
    dt = datetime.datetime.fromtimestamp(mtime)
    size = os.path.getsize(f)
    
    # Check if file contains AUTO-LOOP logging
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
        has_debug = "[AUTO-LOOP] executeAutoLoop called" in content or "AUTO-LOOP" in content
    
    print(f"{os.path.basename(f)}: {dt} | {size/1024:.1f}KB | Has debug: {has_debug}")

# Also check all chunk files for the debug logging
print("\n--- Checking all JS files for AUTO-LOOP ---")
all_js = glob.glob(os.path.join(build_dir, "*.js"))
found_in = []
for f in all_js:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
        if "[AUTO-LOOP]" in content:
            found_in.append(os.path.basename(f))

if found_in:
    print(f"Found [AUTO-LOOP] logging in: {found_in}")
else:
    print("No [AUTO-LOOP] logging found in any built JS files!")
