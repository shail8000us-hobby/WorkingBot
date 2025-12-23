#!/usr/bin/env python3
"""
Delta Exchange PnL Reporter (hardened)
- Endpoints:
    * fills  : /v2/orders/history/fills   (falls back to /v2/fills)
    * positions: /v2/positions           (falls back to /v2/positions/margined)
    * balances: /v2/wallet/balances
    * tickers : /v2/tickers
- Timestamps in **milliseconds** (ms) for API; accepts ISO/seconds/ms in inputs.
- Signature: method + timestamp + path + query(+? when present) + payload (JSON string) for GET/POST.
- Robust response handling (wrapped/unwrapped), nested fields, progress prints.
- Reports:
    * trade_history_<since>__<until>.csv
    * period_by_symbol_<since>__<until>.csv
    * period_summary_<since>__<until>.csv
    * open_positions_<now>.csv
    * snapshot_summary_<now>.csv
  Raw dumps under reports/raw/.
"""
import os, sys, time, json, csv, hmac, hashlib, argparse
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from urllib.parse import urlencode
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# -------- helpers --------
def now_ms() -> int:
    return int(time.time() * 1000)

def parse_ts_ms(val: Any) -> int:
    """Return milliseconds since epoch.
       Accepts ms/int, seconds, or ISO8601 (with or without 'Z')."""
    if val is None: return 0
    if isinstance(val, (int, float)):
        x = int(val)
        # heuristics: if it's clearly seconds, upgrade to ms
        return x if x > 10_000_000_000 else x * 1000
    s = str(val).strip()
    if s.isdigit():
        return parse_ts_ms(int(s))
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0

def to_local(ms_any: Any, tz: Optional[str]) -> str:
    ms = parse_ts_ms(ms_any)
    try:
        dt = datetime.fromtimestamp(ms/1000, tz=timezone.utc)
        if tz and ZoneInfo:
            dt = dt.astimezone(ZoneInfo(tz))
        else:
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms_any)

def range_tag(start_ms: int, end_ms: int) -> str:
    s = datetime.fromtimestamp(start_ms/1000, tz=timezone.utc).strftime('%Y%m%d_%H%M%S')
    e = datetime.fromtimestamp(end_ms/1000, tz=timezone.utc).strftime('%Y%m%d_%H%M%S')
    return f"{s}__{e}"

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def csv_write(path: str, rows: List[Dict], fieldnames: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# -------- Delta API (retry + correct signing) --------
import requests

class DeltaAPI:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.key = api_key
        self.secret = api_secret.encode("utf-8")
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "gridbot-pnl-reporter", "Content-Type": "application/json"})

    def _sign(self, method: str, ts: str, path: str, query: str, payload: str) -> str:
        msg = (method + ts + path + query + payload).encode("utf-8")
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _req(self, method: str, path: str, params: Optional[Dict]=None, payload: Optional[Dict]=None) -> Any:
        url = f"{self.base}{path}"
        qs_for_sig = ""
        data = ""
        if method == "GET":
            if params:
                # Note: Delta expects the **exact** query in the signature. urlencode keeps stable ordering if dict is ordered.
                qs_for_sig = "?" + urlencode(params, doseq=True)
        else:
            data = json.dumps(payload or {})
        for i in range(5):
            ts = str(int(time.time()))
            sig = self._sign(method, ts, path, qs_for_sig if method=="GET" else "", data)
            headers = {"api-key": self.key, "timestamp": ts, "signature": sig}
            try:
                if method == "GET":
                    r = self.s.get(url, params=params, headers=headers, timeout=(5, 30))
                else:
                    r = self.s.post(url, data=data, headers=headers, timeout=(5, 30))
                r.raise_for_status()
                j = r.json()
                # Some endpoints respond with bare lists/dicts (no success/result)
                if isinstance(j, dict) and j.get("success") is False:
                    raise requests.HTTPError(j.get("error", "delta: success=false"))
                return j
            except Exception:
                if i == 4: raise
                time.sleep(0.5 * (2**i))
        return {}

    # --- Endpoints ---
    def fills(self, start_ms: int, end_ms: int, page_size: int = 100) -> List[Dict]:
        """Primary: /v2/orders/history/fills; fallback: /v2/fills"""
        all_f: List[Dict] = []
        after = None
        def fetch(path: str) -> Optional[Dict]:
            params = {"start_time": start_ms, "end_time": end_ms, "page_size": page_size}
            if after: params["after"] = after
            return self._req("GET", path, params)
        path = "/v2/orders/history/fills"
        while True:
            try:
                j = fetch(path)
            except Exception:
                # fallback once to old path
                path = "/v2/fills"
                j = fetch(path)
            # Normalize results
            batch = []
            if isinstance(j, dict):
                if "result" in j and isinstance(j["result"], list):
                    batch = j["result"]
                    meta = j.get("meta", {})
                elif "result" in j and isinstance(j["result"], dict) and "items" in j["result"]:
                    batch = j["result"]["items"]
                    meta = j["result"].get("meta", j.get("meta", {}))
                elif "items" in j:
                    batch = j["items"]
                    meta = j.get("meta", {})
                else:
                    # unexpected dict shape
                    batch = []
                    meta = {}
            elif isinstance(j, list):
                batch = j
                meta = {}
            else:
                batch = []
                meta = {}

            if not batch:
                break
            all_f.extend(batch)
            after = (meta or {}).get("after")
            if not after:
                break
            time.sleep(0.1)
        return all_f

    def positions(self) -> List[Dict]:
        """Primary: /v2/positions; fallback: /v2/positions/margined"""
        try:
            j = self._req("GET", "/v2/positions")
        except Exception:
            j = self._req("GET", "/v2/positions/margined")
        if isinstance(j, dict) and "result" in j and isinstance(j["result"], list): return j["result"]
        if isinstance(j, list): return j
        return []

    def balances(self) -> List[Dict]:
        j = self._req("GET", "/v2/wallet/balances")
        if isinstance(j, dict) and "result" in j and isinstance(j["result"], list): return j["result"]
        if isinstance(j, list): return j
        return []

    def tickers(self) -> List[Dict]:
        j = self._req("GET", "/v2/tickers")
        if isinstance(j, dict) and "result" in j and isinstance(j["result"], list): return j["result"]
        if isinstance(j, list): return j
        return []

# -------- Rates (USD-ish) --------
def build_usd_rates(tickers: List[Dict]) -> Dict[str, float]:
    rates = {"USD":1.0, "USDT":1.0}
    for t in tickers or []:
        sym = str(t.get("symbol", t.get("name", ""))).upper()
        mp  = t.get("mark_price") or t.get("spot_price") or t.get("price") or t.get("last_price")
        try: mp = float(mp)
        except Exception: mp = None
        if not mp: continue
        if "BTCUSD" in sym or "BTC/USDT" in sym or sym.startswith("BTCUSD"): rates["BTC"] = mp
        if "ETHUSD" in sym or "ETH/USDT" in sym or sym.startswith("ETHUSD"): rates["ETH"] = mp
    return rates

# -------- Normalizers --------
def norm_symbol(obj: Dict) -> str:
    return obj.get("product_symbol") or (obj.get("product") or {}).get("symbol") or obj.get("symbol") or "UNKNOWN"

def norm_commission(fill: Dict) -> float:
    # Some responses use commission; others paid_commission/fee fields
    for k in ("commission","paid_commission","fee","fees"):
        if k in fill and fill[k] is not None:
            try: return float(fill[k])
            except Exception: pass
    return 0.0

# -------- PnL calc (avg-cost; ms timestamps) --------
def realized_pnl_from_fills(fills: List[Dict]) -> Tuple[float, float, List[Dict]]:
    fills_sorted = sorted(fills, key=lambda f: parse_ts_ms(f.get("created_at") or f.get("timestamp")))
    per: Dict[str, Dict[str, Any]] = {}
    total_realized = 0.0
    total_comm = 0.0
    for f in fills_sorted:
        sym  = norm_symbol(f)
        side = f.get("side")
        try: size = float(f.get("size", 0) or 0)
        except Exception: size = 0.0
        try: price= float(f.get("price", 0) or 0)
        except Exception: price= 0.0
        comm = abs(norm_commission(f))
        total_comm += comm
        rec = per.setdefault(sym, {"qty":0.0,"avg":0.0,"realized":0.0,"commission":0.0,"trades":0,"buy_value":0.0,"sell_value":0.0})
        rec["trades"] += 1
        if side == "buy":
            if rec["qty"] < 0:
                cover = min(size, abs(rec["qty"]))
                rec["realized"] += (rec["avg"] - price) * cover
                rec["qty"] += cover; size -= cover
                if size > 0: rec["avg"]=price; rec["qty"]=size; size=0.0
            else:
                newq = rec["qty"] + size
                rec["avg"] = (rec["qty"]*rec["avg"] + size*price)/newq if newq else price
                rec["qty"] = newq; size=0.0
            rec["buy_value"] += (float(f.get("size",0) or 0)*price)
        else:
            if rec["qty"] > 0:
                close = min(size, rec["qty"])
                rec["realized"] += (price - rec["avg"]) * close
                rec["qty"] -= close; size -= close
                if size > 0: rec["avg"]=price; rec["qty"]=-size; size=0.0
            else:
                newq = abs(rec["qty"]) + size
                rec["avg"] = (abs(rec["qty"])*rec["avg"] + size*price)/newq if newq else price
                rec["qty"] = -newq; size=0.0
            rec["sell_value"] += (float(f.get("size",0) or 0)*price)
        rec["commission"] += comm
    rows: List[Dict] = []
    for sym, r in per.items():
        rows.append({
            "Product_Symbol": sym,
            "Trades": r["trades"],
            "Buy_Value": r["buy_value"],
            "Sell_Value": r["sell_value"],
            "Realized_PnL_native": round(r["realized"], 8),
            "Commission_Paid_native": round(r["commission"], 8),
            "Net_After_Fees_native": round(r["realized"] - r["commission"], 8),
            "Open_Qty_EndOfPeriod": r["qty"],
            "Avg_Cost_EndOfPeriod": r["avg"],
        })
        total_realized += r["realized"]
    return total_realized, total_comm, rows

# -------- Reports --------
def report_trade_history(fills: List[Dict], outdir: str, start_ms: int, end_ms: int, tz: Optional[str]) -> str:
    ts = range_tag(start_ms, end_ms)
    fp = os.path.join(outdir, f"trade_history_{ts}.csv")
    rows: List[Dict] = []
    total_comm = total_buy = total_sell = 0.0
    for f in fills:
        size = float(f.get("size", 0) or 0)
        price= float(f.get("price", 0) or 0)
        comm = abs(norm_commission(f))
        val  = size * price
        total_comm += comm
        if f.get("side") == "buy": total_buy += val
        else: total_sell += val
        ts_local = to_local(f.get("created_at") or f.get("timestamp"), tz)
        rows.append({
            "Timestamp": ts_local,
            "Product_Symbol": norm_symbol(f),
            "Side": f.get("side"),
            "Size": size,
            "Price": price,
            "Total_Value": val,
            "Commission": comm,
            "Role": f.get("role") or f.get("liquidity"),
            "Fill_Type": f.get("fill_type", "normal"),
            "Order_ID": f.get("order_id") or f.get("order",{}).get("id"),
            "Settling_Asset": f.get("settling_asset_symbol") or (f.get("product") or {}).get("settling_asset_symbol"),
        })
    rows.append({
        "Timestamp":"--- SUMMARY ---","Product_Symbol":"", "Side":"", "Size":"", "Price":"",
        "Total_Value": f"Buy: {total_buy:.8f} | Sell: {total_sell:.8f}",
        "Commission": f"{total_comm:.8f}", "Role":"", "Fill_Type":"", "Order_ID":"", "Settling_Asset":""
    })
    csv_write(fp, rows, list(rows[0].keys()))
    return fp

def report_period_summary(fills: List[Dict], outdir: str, start_ms: int, end_ms: int, tz: Optional[str], rates: Dict[str,float]) -> Tuple[str, str]:
    ts = range_tag(start_ms, end_ms)
    fp_sum = os.path.join(outdir, f"period_summary_{ts}.csv")
    fp_sym = os.path.join(outdir, f"period_by_symbol_{ts}.csv")

    realized_native, comm_native, rows_sym = realized_pnl_from_fills(fills)

    # very conservative USD estimate: assume USD/USDT settlement
    realized_usd = realized_native
    comm_usd = comm_native

    rows_conv = []
    for r in rows_sym:
        row = dict(r)
        row["Realized_PnL_USD"] = round(r["Realized_PnL_native"], 8)
        row["Commission_Paid_USD"] = round(r["Commission_Paid_native"], 8)
        row["Net_After_Fees_USD"] = round(r["Net_After_Fees_native"], 8)
        rows_conv.append(row)

    csv_write(fp_sym, rows_conv, [
        "Product_Symbol","Trades","Buy_Value","Sell_Value",
        "Realized_PnL_native","Commission_Paid_native","Net_After_Fees_native",
        "Realized_PnL_USD","Commission_Paid_USD","Net_After_Fees_USD",
        "Open_Qty_EndOfPeriod","Avg_Cost_EndOfPeriod"
    ])

    sum_rows = [
        {"Metric":"=== PERIOD WINDOW ===","Value":"","Unit":""},
        {"Metric":"Start (local)","Value": to_local(start_ms, tz),"Unit":""},
        {"Metric":"End (local)","Value":   to_local(end_ms, tz),"Unit":""},
        {"Metric":"Realized PnL (native)","Value": f"{realized_native:.8f}","Unit":"mixed"},
        {"Metric":"Commission Paid (native)","Value": f"{comm_native:.8f}","Unit":"mixed"},
        {"Metric":"Net After Fees (native)","Value": f"{(realized_native - comm_native):.8f}","Unit":"mixed"},
        {"Metric":"Realized PnL (USD est.)","Value": f"{realized_usd:.8f}","Unit":"USD"},
        {"Metric":"Commission Paid (USD est.)","Value": f"{comm_usd:.8f}","Unit":"USD"},
        {"Metric":"Net After Fees (USD est.)","Value": f"{(realized_usd - comm_usd):.8f}","Unit":"USD"},
        {"Metric":"Trades","Value": sum(r["Trades"] for r in rows_sym),"Unit":"count"},
    ]
    csv_write(fp_sum, sum_rows, ["Metric","Value","Unit"])
    return fp_sum, fp_sym

def report_snapshot(positions: List[Dict], balances: List[Dict], outdir: str, tz: Optional[str]) -> Tuple[str, str]:
    now_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fp_pos = os.path.join(outdir, f"open_positions_{now_tag}.csv")
    fp_snap= os.path.join(outdir, f"snapshot_summary_{now_tag}.csv")

    rows: List[Dict] = []
    tot_real = tot_unreal = tot_block = tot_fund = 0.0
    for p in positions:
        realized = float(p.get("realized_pnl", 0) or 0)
        unreal   = float(p.get("unrealized_pnl", 0) or 0)
        blocked  = float(p.get("commission", p.get("commission_blocked", 0)) or 0)
        fund     = float(p.get("realized_funding", 0) or 0)
        rows.append({
            "Product_Symbol": p.get("product_symbol") or (p.get("product") or {}).get("symbol"),
            "Product_ID": p.get("product_id") or (p.get("product") or {}).get("id"),
            "Position_Size": p.get("size"),
            "Entry_Price": p.get("entry_price"),
            "Mark_Price": p.get("mark_price", ""),
            "Unrealized_PnL_native": unreal,
            "Realized_PnL_native": realized,
            "Realized_Funding_native": fund,
            "Commission_Blocked_native": blocked,
            "Margin": p.get("margin"),
            "Liq_Price": p.get("liquidation_price"),
            "Bankruptcy_Price": p.get("bankruptcy_price"),
            "ADL_Level": p.get("adl_level"),
            "Created_At": p.get("created_at"),
            "Updated_At": p.get("updated_at"),
        })
        tot_real += realized; tot_unreal += unreal; tot_block += blocked; tot_fund += fund
    rows.append({
        "Product_Symbol":"--- SUMMARY ---","Product_ID":"","Position_Size":"","Entry_Price":"","Mark_Price":"",
        "Unrealized_PnL_native": f"{tot_unreal:.8f}",
        "Realized_PnL_native": f"{tot_real:.8f}",
        "Realized_Funding_native": f"{tot_fund:.8f}",
        "Commission_Blocked_native": f"{tot_block:.8f}",
        "Margin":"","Liq_Price":"","Bankruptcy_Price":"","ADL_Level":"","Created_At":"","Updated_At":"",
    })
    csv_write(fp_pos, rows, list(rows[0].keys()))

    bal_map = {b.get("asset_symbol") or b.get("asset"): b for b in (balances or [])}
    snap_rows = [{"Metric":"=== ACCOUNT SNAPSHOT ===","Value":"","Unit":""}]
    for asset, b in bal_map.items():
        snap_rows += [
            {"Metric":f"{asset} Available","Value": b.get("available_balance"),"Unit":asset},
            {"Metric":f"{asset} Total","Value": b.get("balance"),"Unit":asset},
            {"Metric":f"{asset} Blocked Margin","Value": b.get("blocked_margin"),"Unit":asset},
        ]
    csv_write(fp_snap, snap_rows, ["Metric","Value","Unit"])
    return fp_pos, fp_snap

# -------- Orchestrator --------
def compute_window(args) -> Tuple[int,int,str]:
    tz = args.tz
    if args.today:
        z = ZoneInfo(tz) if tz and ZoneInfo else datetime.now().astimezone().tzinfo
        now = datetime.now(tz=z)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start.timestamp() * 1000)
        end_ms   = int(now.timestamp() * 1000)
        return start_ms, end_ms, tz
    if args.since or args.until:
        def parse_any(x: Optional[str]) -> Optional[int]:
            if not x: return None
            if x.strip().isdigit(): return parse_ts_ms(int(x))
            return parse_ts_ms(x)
        start_ms = parse_any(args.since) or (now_ms() - int(args.days*24*3600*1000))
        end_ms   = parse_any(args.until) or now_ms()
        return start_ms, end_ms, tz
    end_ms = now_ms()
    start_ms = end_ms - int(args.days*24*3600*1000)
    return start_ms, end_ms, tz

def generate_all(args):
    ensure_dir(args.outdir); ensure_dir(os.path.join(args.outdir, "raw"))

    API_KEY = envs("DELTA_API_KEY", "")
    API_SECRET = envs("DELTA_API_SECRET", "")
    BASE_URL = envs("DELTA_BASE_URL", "https://api.india.delta.exchange")
    if not API_KEY or not API_SECRET:
        print("ERROR: set DELTA_API_KEY / DELTA_API_SECRET in .env"); sys.exit(2)

    start_ms, end_ms, tz = compute_window(args)
    print(f"[range] {to_local(start_ms, tz)} → {to_local(end_ms, tz)}")

    api = DeltaAPI(API_KEY, API_SECRET, BASE_URL)

    print("Fetching positions...")
    positions = api.positions()
    print(f"Found {len(positions)} positions")

    print("Fetching fills...")
    fills = api.fills(start_ms, end_ms)
    print(f"Found {len(fills)} fills")

    print("Fetching balances...")
    balances = api.balances()
    print(f"Found {len(balances)} balances")

    print("Fetching tickers...")
    tickers = api.tickers()
    print(f"Found {len(tickers)} tickers")
    rates = build_usd_rates(tickers)
    print(f"Rates: {rates}")

    # raw dumps
    stamp = range_tag(start_ms, end_ms)
    write_json(os.path.join(args.outdir, "raw", f"positions_{stamp}.json"), positions)
    write_json(os.path.join(args.outdir, "raw", f"fills_{stamp}.json"), fills)
    write_json(os.path.join(args.outdir, "raw", f"balances_{stamp}.json"), balances)
    write_json(os.path.join(args.outdir, "raw", f"tickers_{stamp}.json"), tickers)

    # reports
    fp_hist = report_trade_history(fills, args.outdir, start_ms, end_ms, tz)
    fp_sum, fp_sym = report_period_summary(fills, args.outdir, start_ms, end_ms, tz, rates)
    fp_pos, fp_snap = report_snapshot(positions, balances, args.outdir, tz)

    print("\n[SUCCESS] Generated reports:")
    for p in [fp_hist, fp_sym, fp_sum, fp_pos, fp_snap]:
        print(f" - {p}")

def main():
    ap = argparse.ArgumentParser(description="Delta Exchange PnL Reporter (hardened)")
    ap.add_argument("--days", type=float, default=1.0, help="Lookback window in days (fractional OK).")
    ap.add_argument("--since", type=str, default=None, help="Start time ISO (YYYY-MM-DDTHH:MM[:SS][Z]) or epoch seconds/ms.")
    ap.add_argument("--until", type=str, default=None, help="End time ISO or epoch seconds/ms.")
    ap.add_argument("--today", action="store_true", help="Use midnight→now in given --tz.")
    ap.add_argument("--tz", type=str, default="Asia/Kolkata", help="Timezone for local display.")
    ap.add_argument("--outdir", type=str, default="reports", help="Output directory.")
    args = ap.parse_args()
    generate_all(args)

if __name__ == "__main__":
    main()
