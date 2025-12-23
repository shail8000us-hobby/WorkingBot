#!/usr/bin/env python3
import os, sys, time, json, hmac, hashlib, requests, websocket
from dotenv import load_dotenv
load_dotenv('.env.reports')
API_KEY=os.getenv('DELTA_API_KEY'); API_SECRET=os.getenv('DELTA_API_SECRET')
WS_URL=os.getenv('DELTA_WS_URL','wss://socket.india.delta.exchange')
TG_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN'); TG_CHAT=os.getenv('TELEGRAM_CHAT_ID')
def tgsend(txt):
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
                          json={'chat_id': TG_CHAT, 'text': txt, 'disable_web_page_preview': True}, timeout=10).raise_for_status()
        except Exception as e: print('[telepush] failed:', e, file=sys.stderr)
def sig(m): return hmac.new(API_SECRET.encode(), m.encode(), hashlib.sha256).hexdigest()
def on_open(ws):
    ts=str(int(time.time()))
    ws.send(json.dumps({"type":"auth","payload":{"api-key":API_KEY,"timestamp":ts,"signature":sig('GET'+ts+'/live')}}))
def on_message(ws, m):
    try: d=json.loads(m)
    except: return
    if d.get('type')=='success' and str(d.get('message','')).lower().startswith('authenticated'):
        ws.send(json.dumps({"type":"subscribe","payload":{"channels":[
            {"name":"orders","symbols":["all"]},{"name":"v2/user_trades","symbols":["all"]}]}}))
        tgsend("✅ Delta WS authenticated; subscribed to orders & trades"); return
    if d.get('type')=='orders':
        sy=d.get('symbol') or d.get('product_symbol') or 'N/A'
        side=d.get('side','?').upper(); state=d.get('state','?')
        lp=d.get('limit_price') or d.get('average_fill_price'); sz=d.get('size'); uf=d.get('unfilled_size')
        tgsend(f"🧾 Order • {sy} • {side} • state={state} • size={sz} unfilled={uf} • price={lp}")
    if d.get('type')=='v2/user_trades':
        sy=d.get('sy','N/A'); side=d.get('S','?').upper(); sz=d.get('s'); px=d.get('p'); role=d.get('r')
        tgsend(f"💱 Fill • {sy} • {side} {sz} @ {px} • {role}")
def on_error(ws, e): print('[ws error]', e, file=sys.stderr); tgsend(f"⚠️ WS error: {e}")
def on_close(ws, code, msg): print('[ws closed]', code, msg); tgsend("🔌 WS closed")
if not API_KEY or not API_SECRET: print('Missing DELTA_API_KEY/DELTA_API_SECRET'); sys.exit(1)
websocket.enableTrace(False)
websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message,
                       on_error=on_error, on_close=on_close).run_forever(ping_interval=30, ping_timeout=10)
