#!/usr/bin/env python3
"""Quick test: verify JSON→SQLite migration works with real session data."""
import sys, os
sys.path.insert(0, '/Users/ssr/Projects/WorkingBot')

import shutil, tempfile, json

tmpdir = tempfile.mkdtemp()
src = '/Users/ssr/Projects/WorkingBot/webui/backend/data/mmm_sessions.json'
dst = os.path.join(tmpdir, 'mmm_sessions.json')
shutil.copy2(src, dst)

import webui.backend.routes.mmm.mmm_storage as ms
ms.LEGACY_JSON_FILE = dst
ms.DB_FILE = os.path.join(tmpdir, 'mmm_sessions.db')
ms._storage_instance = None

storage = ms.MMMStorage(ms.DB_FILE)

sessions = storage.list_sessions()
print(f'Sessions migrated: {len(sessions)}')
for s in sessions:
    sid = s.get('session_id', '?')
    status = s.get('strategy_status', '?')
    interval = s.get('params', {}).get('adjustment_interval', '?')
    hb = s.get('_heartbeat_counter', 0)
    print(f'  {sid}  status={status}  interval={interval}  heartbeats={hb}')

print(f'JSON exists: {os.path.exists(dst)}')
print(f'JSON.migrated exists: {os.path.exists(dst + ".migrated")}')

active = storage.get_active_session_ids()
print(f'Active IDs: {active}')

first_sid = sessions[0]['session_id']
storage.update_session(first_sid, {'params': {'adjustment_interval': 999}})
updated = storage.get_session(first_sid)
print(f'After update: {first_sid} interval={updated["params"]["adjustment_interval"]}')

# Verify other sessions untouched
for s in sessions[1:]:
    check = storage.get_session(s['session_id'])
    orig_int = s['params']['adjustment_interval']
    new_int = check['params']['adjustment_interval']
    assert orig_int == new_int, f"FAIL: {s['session_id']} interval changed from {orig_int} to {new_int}"
    print(f'  {s["session_id"]} interval unchanged: {new_int} ✓')

print(f'Session count: {storage.get_session_count()}')

# Test delete
storage.delete_session(first_sid)
assert storage.get_session(first_sid) is None
print(f'Delete test passed ✓')

shutil.rmtree(tmpdir)
print('ALL MIGRATION TESTS PASSED ✓')
