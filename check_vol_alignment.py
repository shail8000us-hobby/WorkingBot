#!/usr/bin/env python3
import json
from datetime import datetime

with open('/tmp/vol_data.json') as f:
    data = json.load(f)

iv = data['data']['iv']
rv = data['data']['rv']

fmt = "%m-%d %H:%M"
iv_start_ts = iv[0]['timestamp']
rv_start_ts = rv[0]['timestamp']
iv_end_ts = iv[-1]['timestamp']
rv_end_ts = rv[-1]['timestamp']

iv_start = datetime.fromtimestamp(iv_start_ts/1000).strftime(fmt)
rv_start = datetime.fromtimestamp(rv_start_ts/1000).strftime(fmt)
iv_end = datetime.fromtimestamp(iv_end_ts/1000).strftime(fmt)
rv_end = datetime.fromtimestamp(rv_end_ts/1000).strftime(fmt)

print(f"IV: {len(iv)} points, {iv_start} to {iv_end}")
print(f"RV: {len(rv)} points, {rv_start} to {rv_end}")
print()

if iv_start_ts == rv_start_ts and iv_end_ts == rv_end_ts:
    print("✅ SUCCESS: IV and RV have IDENTICAL time spans!")
    print(f"   Start timestamp: {iv_start_ts} ({datetime.fromtimestamp(iv_start_ts/1000)})")
    print(f"   End timestamp: {iv_end_ts} ({datetime.fromtimestamp(iv_end_ts/1000)})")
else:
    start_diff_min = abs(iv_start_ts - rv_start_ts) / 60000
    end_diff_min = abs(iv_end_ts - rv_end_ts) / 60000
    print("❌ FAILED: Time spans differ")
    print(f"   Start difference: {start_diff_min:.1f} minutes")
    print(f"   End difference: {end_diff_min:.1f} minutes")
