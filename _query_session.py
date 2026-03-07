import sqlite3, json
conn = sqlite3.connect('webui/backend/data/mmm_sessions.db')
cur = conn.cursor()
cur.execute("SELECT session_id, data_json FROM mmm_sessions WHERE session_id='mmm04mar26-1'")
row = cur.fetchone()
if row:
    data = json.loads(row[1])
    params = data.get('params', {})
    print('=== wind-down / close params ===')
    for k,v in params.items():
        if any(x in k.lower() for x in ['wind','close_at','trailing','min_trigger','rebalance']):
            print(f'  {k}: {v}')
    print()
    print('=== wind-down session flags ===')
    for k,v in data.items():
        if any(x in k.lower() for x in ['wind','atm_wind','trend_wind','vol_wind','regime']):
            print(f'  {k}: {v}')
    print()
    wd_hist = data.get('_wind_down_history', [])
    print(f'=== _wind_down_history ({len(wd_hist)} entries) ===')
    for e in wd_hist:
        print(f'  {json.dumps(e)}')
    print()
    analytics = data.get('analytics', {})
    ace = analytics.get('auto_close_events', [])
    print(f'=== auto_close_events ({len(ace)} entries) ===')
    for e in ace:
        print(f'  {json.dumps(e)}')
    print()
    print('=== close_at_5_count:', data.get('close_at_5_count', 'N/A'))
    print('=== regime_log (last 5) ===')
    rl = data.get('_regime_log', [])
    for e in rl[-5:]:
        print(f'  {json.dumps(e)}')
else:
    print("Session mmm04mar26-1 not found")
conn.close()
