#!/usr/bin/env python3
"""Manually restart monitor for a session"""
import sys
sys.path.append('/Users/ssr/Projects/WorkingBot')

from webui.backend.routes.mmm.mmm_storage import get_storage
from webui.backend.routes.mmm.mmm_monitor import start_session_monitor, get_all_monitors

# Get session
storage = get_storage()
session = storage.get_session('mmm_d8b725')

if not session:
    print("❌ Session not found")
    sys.exit(1)

print(f"Session: {session.get('session_id')}")
print(f"Status: {session.get('strategy_status')}")
print(f"Adjustment count: {session.get('adjustment_count', 0)}")

# Check existing monitors
monitors = get_all_monitors()
print(f"\nActive monitors: {len(monitors)}")
for sid, mon in monitors.items():
    print(f"  - {sid}: paused={mon.is_paused()}")

# Start monitor
print(f"\nStarting monitor for mmm_d8b725...")
try:
    monitor = start_session_monitor('mmm_d8b725', session)
    print(f"✅ Monitor started")
    print(f"   Paused: {monitor.is_paused()}")
    print(f"   Heartbeat interval: {monitor.session.get('params', {}).get('heartbeat_interval', 300)}s")
except Exception as e:
    print(f"❌ Failed to start monitor: {e}")
    import traceback
    traceback.print_exc()
