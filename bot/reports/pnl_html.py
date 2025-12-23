#!/usr/bin/env python3
# Delta Exchange PnL Reporter — HTML + Email (robust, endpoint-fallbacks)
import os, sys, time, json, csv, hmac, hashlib, argparse, smtplib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from urllib.parse import urlencode
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

def now_ms() -> int:
    return int(time.time()*1000)

def parse_ts_ms(val: Any) -> int:
    if val is None: return 0
    if isinstance(val, (int, float)):
        x = int(val);  return x if x > 10_000_000_000 else x*1000
    s = str(val).strip()
    if s.isdigit(): return parse_ts_ms(int(s))
    try:
        s2 = s.replace("Z","+00:00")
        dt = datetime.fromisoformat(s2)
        return int(dt.timestamp()*1000)
    except Exception:
        return 0

def to_local(ms_any: Any, tz_name: Optional[str]) -> str:
    ms = parse_ts_ms(ms_any)
    try:
        dt = datetime.fromtimestamp(ms/1000, tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms_any)

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def write_json(path: str, data: Any) -> None:
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)

def csv_write(path: str, rows: List[Dict], cols: List[str]) -> None:
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); [w.writerow(r) for r in rows]

def rupee(v: float, fx: float) -> str:
    try: return f"₹{(v*fx):,.2f}"
    except Exception: return f"₹{v}"

# ---------------- Delta API ----------------
import requests
class DeltaAPI:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.key = api_key
        self.secret = api_secret.encode("utf-8")
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent":"gridbot-html-reporter","Content-Type":"application/json"})

    def _sign(self, method: str, ts: str, path: str, qs: str, payload: str) -> str:
        msg = (method + ts + path + qs + payload).encode("utf-8")
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _req(self, method: str, path: str, params: Optional[Dict]=None, payload: Optional[Dict]=None) -> Any:
        url = f"{self.base}{path}"
        qs_for_sig = ""
        data = ""
        if method == "GET" and params:
            qs_for_sig = "?" + urlencode(params, doseq=True)
        elif method != "GET":
            data = json.dumps(payload or {})
        for i in range(5):
            ts = str(int(time.time()))
            sig = self._sign(method, ts, path, qs_for_sig if method=="GET" else "", data)
            hdr = {"api-key": self.key, "timestamp": ts, "signature": sig}
            try:
                r = self.s.get(url, params=params, headers=hdr, timeout=(5,30)) if method=="GET" \
                    else self.s.post(url, data=data, headers=hdr, timeout=(5,30))
                r.raise_for_status()
                j = r.json()
                if isinstance(j, dict) and j.get("success") is False:
                    raise requests.HTTPError(j.get("error","delta: success=false"))
                return j
            except Exception:
                if i==4: raise
                time.sleep(0.5*(2**i))
        return {}

    # ---- Fills with endpoint fallback (/v2/orders/history/fills -> /v2/fills)
    def fills(self, start_ms: int, end_ms: int, page_size: int = 100) -> list:
        def fetch(path: str) -> list:
            all_f, after = [], None
            while True:
                params = {"start_time": start_ms, "end_time": end_ms, "page_size": page_size}
                if after: params["after"] = after
                j = self._req("GET", path, params)
                batch, meta = [], {}
                if isinstance(j, dict):
                    if isinstance(j.get("result"), list):
                        batch, meta = j["result"], j.get("meta", {})
                    elif isinstance(j.get("result"), dict) and "items" in j["result"]:
                        batch, meta = j["result"]["items"], j["result"].get("meta", j.get("meta", {}))
                    elif isinstance(j.get("items"), list):
                        batch, meta = j["items"], j.get("meta", {})
                elif isinstance(j, list):
                    batch = j
                if not batch: break
                all_f.extend(batch)
                after = (meta or {}).get("after")
                if not after: break
                time.sleep(0.1)
            return all_f
        try:
            f = fetch("/v2/orders/history/fills")
            if f: return f
        except Exception:
            pass
        try:
            return fetch("/v2/fills")
        except Exception:
            return []

    # ---- Positions with endpoint fallback (prefer margined)
    def positions(self) -> list:
        for path in ("/v2/positions/margined", "/v2/positions"):
            try:
                j = self._req("GET", path)
            except Exception:
                continue
            if isinstance(j, dict):
                if isinstance(j.get("result"), list): return j["result"]
                if isinstance(j.get("result"), dict) and "items" in j["result"]: return j["result"]["items"]
                if isinstance(j.get("items"), list): return j["items"]
            if isinstance(j, list): return j
        return []

    def balances(self) -> list:
        j = self._req("GET","/v2/wallet/balances")
        if isinstance(j, dict) and isinstance(j.get("result"), list): return j["result"]
        if isinstance(j, list): return j
        return []

    def tickers(self) -> list:
        j = self._req("GET","/v2/tickers")
        if isinstance(j, dict) and isinstance(j.get("result"), list): return j["result"]
        if isinstance(j, list): return j
        return []

# ---------------- PnL from fills ----------------
def norm_sym(d: Dict) -> str:
    return d.get("product_symbol") or (d.get("product") or {}).get("symbol") or d.get("symbol") or "UNKNOWN"

def norm_comm(d: Dict) -> float:
    for k in ("commission","paid_commission","fee","fees"):
        if k in d and d[k] is not None:
            try: return float(d[k])
            except Exception: pass
    return 0.0

def realized_pnl_from_fills(fills: List[Dict]) -> Tuple[float, float, List[Dict]]:
    fills_sorted = sorted(fills, key=lambda f: parse_ts_ms(f.get("created_at") or f.get("timestamp")))
    per: Dict[str, Dict[str, Any]] = {}
    total_realized = total_comm = 0.0
    for f in fills_sorted:
        sym  = norm_sym(f)
        side = f.get("side")
        size = float(f.get("size",0) or 0)
        price= float(f.get("price",0) or 0)
        comm = abs(norm_comm(f)); total_comm += comm
        rec = per.setdefault(sym, {"qty":0.0,"avg":0.0,"realized":0.0,"commission":0.0,"trades":0,"buy_val":0.0,"sell_val":0.0})
        rec["trades"] += 1
        if side == "buy":
            if rec["qty"] < 0:
                cover = min(size, abs(rec["qty"]))
                rec["realized"] += (rec["avg"] - price) * cover
                rec["qty"] += cover; size -= cover
                if size>0: rec["avg"]=price; rec["qty"]=size; size=0.0
            else:
                newq = rec["qty"] + size
                rec["avg"] = (rec["qty"]*rec["avg"] + size*price)/newq if newq else price
                rec["qty"] = newq; size=0.0
            rec["buy_val"] += (float(f.get("size",0) or 0)*price)
        else:
            if rec["qty"] > 0:
                close = min(size, rec["qty"])
                rec["realized"] += (price - rec["avg"]) * close
                rec["qty"] -= close; size -= close
                if size>0: rec["avg"]=price; rec["qty"]=-size; size=0.0
            else:
                newq = abs(rec["qty"]) + size
                rec["avg"] = (abs(rec["qty"])*rec["avg"] + size*price)/newq if newq else price
                rec["qty"] = -newq; size=0.0
            rec["sell_val"] += (float(f.get("size",0) or 0)*price)
        rec["commission"] += comm
    rows=[]
    for sym, r in per.items():
        rows.append({
            "symbol": sym,
            "trades": r["trades"],
            "buy_value": r["buy_val"],
            "sell_value": r["sell_val"],
            "realized": round(r["realized"],8),
            "commission": round(r["commission"],8),
            "net_after_fees": round(r["realized"]-r["commission"],8),
            "open_qty_eop": r["qty"],
            "avg_cost_eop": r["avg"],
        })
        total_realized += r["realized"]
    return total_realized, total_comm, rows

# ---------------- HTML builder ----------------
def build_html(start_ms:int, end_ms:int, tz:str, fx_inr:float,
               fills:List[Dict], positions:List[Dict], balances:List[Dict],
               per_rows:List[Dict], realized:float, fees:float) -> str:
    vol_by_sym: Dict[str,float] = {}
    daily_count: Dict[str,int] = {}
    for f in fills:
        s = norm_sym(f)
        vol_by_sym[s] = vol_by_sym.get(s,0.0) + float(f.get("size",0) or 0)*float(f.get("price",0) or 0)
        dkey = datetime.fromtimestamp(parse_ts_ms(f.get("created_at") or f.get("timestamp"))/1000, tz=timezone.utc).date().isoformat()
        daily_count[dkey] = daily_count.get(dkey,0) + 1
    sym_labels = list(vol_by_sym.keys())
    sym_vols   = [vol_by_sym[k] for k in sym_labels]
    day_labels = sorted(daily_count.keys())
    day_counts = [daily_count[d] for d in day_labels]

    pos_rows=[]
    for p in positions:
        if float(p.get("size",0) or 0) == 0: continue
        pos_rows.append({
            "symbol": p.get("product_symbol") or (p.get("product") or {}).get("symbol") or "N/A",
            "size": p.get("size",0),
            "entry": float(p.get("entry_price",0) or 0),
            "mark":  float(p.get("mark_price",0) or 0),
            "unreal": float(p.get("unrealized_pnl",0) or 0),
            "realized": float(p.get("realized_pnl",0) or 0),
        })
    bal_rows=[{
        "asset": b.get("asset_symbol") or b.get("asset","?"),
        "avail": b.get("available_balance",0),
        "total": b.get("balance",0),
        "blocked": b.get("blocked_margin",0),
    } for b in balances]

    total_trades = len(fills)
    net_after_fees = realized - fees

    html = f"""<!doctype html><html><head>
<meta charset="utf-8"><title>Delta PnL Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{{font-family:Inter,system-ui,Segoe UI,Roboto,Arial,sans-serif;background:#0b1020;color:#e6e6ea;margin:0}}
.container{{max-width:1200px;margin:0 auto;padding:24px}}
.card{{background:#121734;border:1px solid #1f2a4a;border-radius:14px;padding:18px;margin:12px 0;box-shadow:0 6px 24px rgba(0,0,0,.25)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}
.h1{{font-size:22px;margin:8px 0 2px}}
.h2{{font-size:18px;margin:4px 0 12px;color:#9fb0ff}}
.kpi{{font-size:26px;font-weight:700}}
.pos{{color:#50fa7b}} .neg{{color:#ff5555}} .muted{{color:#9ca3af}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px 8px;border-bottom:1px solid #1f2a4a;font-size:14px}}
th{{text-align:left;color:#9fb0ff}}
canvas{{max-height:380px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;background:#1f2a4a;color:#9fb0ff;font-size:12px}}
</style></head><body><div class="container">
<div class="card"><div class="h1">Delta Exchange PnL Report</div>
<div class="muted">Period: {to_local(start_ms,tz)} → {to_local(end_ms,tz)} · Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div></div>

<div class="grid">
  <div class="card"><div class="h2">Realized PnL (period)</div>
    <div class="kpi {'pos' if realized>=0 else 'neg'}">{rupee(realized, fx_inr)}</div></div>
  <div class="card"><div class="h2">Net After Fees (period)</div>
    <div class="kpi {'pos' if net_after_fees>=0 else 'neg'}">{rupee(net_after_fees, fx_inr)}</div>
    <div class="muted"><span class="badge">Fees</span> {rupee(fees, fx_inr)}</div></div>
  <div class="card"><div class="h2">Total Trades</div><div class="kpi">{total_trades:,}</div></div>
</div>

<div class="grid">
  <div class="card"><div class="h2">Volume by Symbol</div><canvas id="volChart"></canvas></div>
  <div class="card"><div class="h2">Daily Trades</div><canvas id="dailyChart"></canvas></div>
</div>

<div class="card"><div class="h2">Per-Symbol PnL (period)</div>
<table><thead><tr>
<th>Symbol</th><th>Trades</th><th>Buy Value</th><th>Sell Value</th>
<th>Realized</th><th>Fees</th><th>Net</th><th>Open Qty</th><th>Avg Cost</th>
</tr></thead><tbody>"""
    for r in per_rows:
        html += f"<tr><td>{r['symbol']}</td><td>{r['trades']}</td><td>{rupee(r['buy_value'],fx_inr)}</td><td>{rupee(r['sell_value'],fx_inr)}</td><td class=\"{'pos' if r['realized']>=0 else 'neg'}\">{rupee(r['realized'],fx_inr)}</td><td>{rupee(r['commission'],fx_inr)}</td><td class=\"{'pos' if r['net_after_fees']>=0 else 'neg'}\">{rupee(r['net_after_fees'],fx_inr)}</td><td>{r['open_qty_eop']}</td><td>{r['avg_cost_eop']:.4f}</td></tr>"
    html += "</tbody></table></div>"

    html += """<div class="card"><div class="h2">Open Positions (snapshot)</div>
<table><thead><tr><th>Symbol</th><th>Size</th><th>Entry</th><th>Mark</th><th>Unrealized</th><th>Realized</th></tr></thead><tbody>"""
    for p in pos_rows:
        html += f"<tr><td>{p['symbol']}</td><td>{p['size']}</td><td>{rupee(p['entry'],fx_inr)}</td><td>{rupee(p['mark'],fx_inr)}</td><td class=\"{'pos' if p['unreal']>=0 else 'neg'}\">{rupee(p['unreal'],fx_inr)}</td><td class=\"{'pos' if p['realized']>=0 else 'neg'}\">{rupee(p['realized'],fx_inr)}</td></tr>"
    html += "</tbody></table></div>"

    html += """<div class="card"><div class="h2">Balances (snapshot)</div>
<table><thead><tr><th>Asset</th><th>Available</th><th>Total</th><th>Blocked</th></tr></thead><tbody>"""
    for b in bal_rows:
        html += f"<tr><td>{b['asset']}</td><td>{b['avail']}</td><td>{b['total']}</td><td>{b['blocked']}</td></tr>"
    html += "</tbody></table></div>"

    html += f"""
<script>
new Chart(document.getElementById('volChart').getContext('2d'), {{
  type: 'doughnut',
  data: {{ labels: {json.dumps(sym_labels)}, datasets:[{{ data: {json.dumps(sym_vols)} }}] }},
  options: {{ plugins:{{legend:{{position:'bottom'}}}}, responsive:true, maintainAspectRatio:false }}
}});
new Chart(document.getElementById('dailyChart').getContext('2d'), {{
  type: 'line',
  data: {{ labels: {json.dumps(day_labels)}, datasets:[{{ label:'Trades', data:{json.dumps(day_counts)} }}] }},
  options: {{ responsive:true, maintainAspectRatio:false, scales:{{y:{{beginAtZero:true}}}} }}
}});
</script>
</div></body></html>"""
    return html

# ---------------- Email ----------------
def send_email(html_path: str, recipient: str) -> bool:
    server = envs("SMTP_SERVER","smtp.gmail.com")
    port   = int(envs("SMTP_PORT","587"))
    user   = envs("SENDER_EMAIL","")
    pwd    = envs("SENDER_PASSWORD","")
    if not (user and pwd and recipient):
        print("WARN: Email not sent (missing SMTP creds or recipient).")
        return False
    msg = MIMEMultipart()
    msg["From"], msg["To"] = user, recipient
    msg["Subject"] = f"Delta PnL Report – {os.path.basename(html_path)}"
    with open(html_path,"r",encoding="utf-8") as f:
        msg.attach(MIMEText(f.read(),"html"))
    with open(html_path,"rb") as f:
        part = MIMEBase("application","octet-stream")
        part.set_payload(f.read()); encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(html_path)}"')
        msg.attach(part)
    s = smtplib.SMTP(server, port); s.starttls(); s.login(user, pwd); s.sendmail(user,[recipient],msg.as_string()); s.quit()
    print(f"[ok] Email sent to {recipient}")
    return True

# ---------------- Orchestrator ----------------
def compute_window(args) -> Tuple[int,int]:
    if args.today:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp()*1000), now_ms()
    if args.since or args.until:
        def parse_any(x: Optional[str]) -> Optional[int]:
            if not x: return None
            if x.strip().isdigit(): return parse_ts_ms(int(x))
            return parse_ts_ms(x)
        s = parse_any(args.since) or (now_ms() - int(args.days*86400*1000))
        e = parse_any(args.until) or now_ms()
        return s, e
    end = now_ms()
    return end - int(args.days*86400*1000), end

def main():
    ap = argparse.ArgumentParser(description="Delta HTML PnL Reporter")
    ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument("--since", type=str, default=None)
    ap.add_argument("--until", type=str, default=None)
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--tz", type=str, default="Asia/Kolkata")
    ap.add_argument("--outdir", type=str, default="reports")
    ap.add_argument("--email", type=str, default=None)
    ap.add_argument("--fx-usd-inr", type=float, default=float(envs("FX_USD_INR","1.0")))
    args = ap.parse_args()

    ensure_dir(args.outdir); ensure_dir(os.path.join(args.outdir,"raw"))
    API_KEY=envs("DELTA_API_KEY"); API_SECRET=envs("DELTA_API_SECRET"); BASE=envs("DELTA_BASE_URL","https://api.india.delta.exchange")
    if not (API_KEY and API_SECRET):
        print("ERROR: set DELTA_API_KEY / DELTA_API_SECRET in .env"); sys.exit(2)

    s_ms, e_ms = compute_window(args)
    print(f"[range] {to_local(s_ms,args.tz)} → {to_local(e_ms,args.tz)}")
    api = DeltaAPI(API_KEY, API_SECRET, BASE)

    print("[fetch] positions…"); positions = api.positions()
    print("[fetch] fills…");     fills     = api.fills(s_ms, e_ms)
    print("[fetch] balances…");  balances  = api.balances()
    print("[fetch] tickers…");   tickers   = api.tickers()

    tag = datetime.fromtimestamp(s_ms/1000, tz=timezone.utc).strftime('%Y%m%d_%H%M%S') + "__" + \
          datetime.fromtimestamp(e_ms/1000, tz=timezone.utc).strftime('%Y%m%d_%H%M%S')
    write_json(os.path.join(args.outdir,"raw",f"positions_{tag}.json"), positions)
    write_json(os.path.join(args.outdir,"raw",f"fills_{tag}.json"), fills)
    write_json(os.path.join(args.outdir,"raw",f"balances_{tag}.json"), balances)
    write_json(os.path.join(args.outdir,"raw",f"tickers_{tag}.json"), tickers)

    realized, fees, per_rows = realized_pnl_from_fills(fills)
    csv_write(os.path.join(args.outdir,f"period_by_symbol_{tag}.csv"), per_rows,
              ["symbol","trades","buy_value","sell_value","realized","commission","net_after_fees","open_qty_eop","avg_cost_eop"])
    th_rows=[{
        "timestamp_local": to_local(f.get("created_at") or f.get("timestamp"), args.tz),
        "symbol": norm_sym(f), "side": f.get("side"),
        "size": f.get("size"), "price": f.get("price"),
        "commission": norm_comm(f),
        "order_id": f.get("order_id") or (f.get("order") or {}).get("id"),
    } for f in fills]
    csv_write(os.path.join(args.outdir,f"trade_history_{tag}.csv"), th_rows,
              ["timestamp_local","symbol","side","size","price","commission","order_id"])

    fx = args.fx_usd_inr  # display multiplier to show INR-like numbers
    html = build_html(s_ms, e_ms, args.tz, fx, fills, positions, balances, per_rows, realized, fees)
    out_html = os.path.join(args.outdir, f"pnl_report_{tag}.html")
    with open(out_html,"w",encoding="utf-8") as f: f.write(html)
    print("[ok] HTML:", out_html)

    if args.email:
        send_email(out_html, args.email)

if __name__ == "__main__":
    main()
