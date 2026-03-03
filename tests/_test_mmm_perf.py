import sqlite3, time

t0 = time.time()
conn = sqlite3.connect('/Users/ssr/Projects/WorkingBot/data/mmm_sessions.db')
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
t1 = time.time()

rows = conn.execute('SELECT count(*) as c FROM mmm_sessions').fetchone()
t2 = time.time()
print(f'connect: {t1-t0:.3f}s, count: {t2-t1:.3f}s, sessions={rows["c"]}')

t3 = time.time()
r = conn.execute("""
    SELECT session_id, status, 
           json_extract(data_json, '$.mode') AS mode,
           json_extract(data_json, '$.realized_pnl') AS pnl
    FROM mmm_sessions ORDER BY created_at DESC
""").fetchall()
t4 = time.time()
print(f'summary query: {t4-t3:.3f}s, rows={len(r)}')

sizes = conn.execute('SELECT sum(length(data_json)) as total FROM mmm_sessions').fetchone()
total = sizes['total'] or 0
print(f'total data_json size: {total/1024/1024:.1f}MB')

conn.close()
