#!/usr/bin/env python3
"""Update session with actual fill data from exchange."""
import json

f = '/Users/ssr/Projects/WorkingBot/webui/backend/data/mmm_sessions.json'
with open(f) as fp:
    data = json.load(fp)

s = data['sessions']['mmm_f1db0f']

# Orders actually FILLED on exchange:
# 1178865108: C-BTC-71000-160226, state=closed, size=1, avg_fill=89.5
# 1178865113: P-BTC-67000-160226, state=closed, size=1, avg_fill=104.8

s['ce']['entry_fill_price'] = 89.5
s['ce']['original_premium'] = 89.5
s['ce']['entry_order_id'] = '1178865108'
s['ce']['trigger_snapshot'] = {'71000': 89.5}

s['pe']['entry_fill_price'] = 104.8
s['pe']['original_premium'] = 104.8
s['pe']['entry_order_id'] = '1178865113'
s['pe']['trigger_snapshot'] = {'67000': 104.8}

s['actual_total_premium'] = 194.3
s['total_premium_collected'] = 194.3
s['initial_total_premium'] = 194.3
s['strategy_status'] = 'IDLE'
s['mmm_order_ids'] = ['1178865108', '1178865113']
s['entry_mode'] = 'fresh'
s['last_error'] = None
s['error_count'] = 0

with open(f, 'w') as fp:
    json.dump(data, fp, indent=2)

print(f"Updated mmm_f1db0f: CE@$89.50, PE@$104.80, total=$194.30")
print("Session file saved")
