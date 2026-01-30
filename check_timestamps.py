#!/usr/bin/env python3
"""Check source and build file timestamps."""
import os
import datetime

source_file = '/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/options/OptionsPanel.js'
source_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(source_file))

build_dir = "/Users/ssr/Projects/WorkingBot/webui/frontend/build/static/js"
build_files = [f for f in os.listdir(build_dir) if f.startswith('main-') and f.endswith('.js') and not f.endswith('.gz')]

print(f"SOURCE FILE: {source_mtime}")
print()
print("BUILD FILES:")
for f in sorted(build_files):
    path = os.path.join(build_dir, f)
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    print(f"  {f}: {mtime}")

# Check if source is newer than build
for f in build_files:
    path = os.path.join(build_dir, f)
    build_mtime = os.path.getmtime(path)
    source_mtime_ts = os.path.getmtime(source_file)
    if source_mtime_ts > build_mtime:
        print(f"\n⚠️ SOURCE IS NEWER THAN BUILD! Need to rebuild.")
    else:
        print(f"\n✅ Build is newer than source ({f})")
