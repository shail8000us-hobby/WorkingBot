#!/usr/bin/env python3
"""Build the frontend and check for AUTO-LOOP debugging."""
import subprocess
import os
import glob

# Build the frontend
frontend_dir = "/Users/ssr/Projects/WorkingBot/webui/frontend"
build_dir = os.path.join(frontend_dir, "build/static/js")

print("=== BUILDING FRONTEND ===")
print("Clearing cache...")
cache_dir = os.path.join(frontend_dir, "node_modules/.cache")
if os.path.exists(cache_dir):
    import shutil
    shutil.rmtree(cache_dir)

print("Running npm build...")
result = subprocess.run(
    ["npm", "run", "build"],
    cwd=frontend_dir,
    capture_output=True,
    text=True
)

print(f"Build exit code: {result.returncode}")
if result.returncode == 0:
    print("✅ BUILD SUCCESSFUL")
else:
    print("❌ BUILD FAILED")
    print("STDERR:", result.stderr[-2000:] if result.stderr else "None")
    print("STDOUT:", result.stdout[-2000:] if result.stdout else "None")
    exit(1)

print("\n=== CHECKING FOR AUTO-LOOP DEBUG LOGGING ===")
all_js = glob.glob(os.path.join(build_dir, "*.js"))
found_in = []
for f in all_js:
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()
        if "[AUTO-LOOP]" in content:
            found_in.append(os.path.basename(f))

if found_in:
    print(f"✅ Found [AUTO-LOOP] logging in: {found_in}")
else:
    print("❌ No [AUTO-LOOP] logging found in any built JS files!")
    print("The production build may still be stripping console.log statements.")
