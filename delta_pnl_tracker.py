#!/usr/bin/env python3
"""
Delta Exchange PnL Tracker (robust)
- Works with https://api.india.delta.exchange
- Flexible timestamp parsing (ISO or micro/milli epoch)
- Retries + backoff, cursor pagination for fills
- Saves JSON + CSV into ./reports
- Uses DELTA_API_KEY / DELTA_API_SECRET from env (.env supported)
"""
import os, sys, time, json, csv, hmac, hashlib, argparse
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

# ---- optional dotenv ----
try:
    from dotenv import load_dotenv
    if os.path.exists(os.getenv("ENV_PATH", ".env")):
        load_dotenv(os.getenv("ENV_PATH", ".env"))
except Exception:
    pass

import requests
from urllib.parse import urlencode

def envs(k: str, d: str = "") -> str:
    v = os.getenv(k)
    return v if v not in (None, "") else d

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def parse_iso_or_epoch(v: Any) -> int:
    """
    Return milliseconds since epoch.
    Accepts: int/str microseconds, milliseconds, or ISO '...Z'
    """
    if v is None: return 0
    s = str(v).strip()
    if not s:
        return 0
    # epoch?
    if s.isdigit():
        n = int(s)
        # Heuristic: >= 1e15 → microseconds; >= 1e12 → milliseconds; else seconds
        if n >= 10**15:   # microseconds
            return n // 1000
        elif n >= 10**12: # milliseconds
            return n
        else:             # seconds
            return n * 1000
    # ISO timestamp
    try:
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0

def fmt_local(ms: int, tzname: Optional[str] = None) -> str:
    try:
        dt = datetime.fromtimestamp(ms/1000, tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms)

class DeltaAPI:
    def __init__(self, key: str, secret: str, base: str):
        self.key = key
        self.secret = secret.encode("utf-8")
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "gridbot-pnl-tracker", "Content-Type": "application/json"})

    def _sign(self, method: str, ts: str, path: str, qs: str, payload: str) -> str:
        msg = (method + ts + path + qs + payload).encode("utf-8")
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _req(self, method: str, path: str, params: Optional[Dict]=None) -> Any:
        url = f"{self.base}{path}"
        qs = ""
        if method == "GET" and params:
            items = sorted((k, str(v)) for k, v in params.items())
            params = dict(items)
            qs = "?" + urlencode(params)

        for i in range(5):
            ts = str(int(time.time()))
            sig = self._sign(method, ts, path, qs if method == "GET" else "", "")
            hdr = {"api-key": self.key, "timestamp": ts, "signature": sig}
            try:
                r = self.s.get(url, params=params, headers=hdr, timeout=(5, 30))
                r.raise_for_status()
                j = r.json()
                if isinstance(j, dict) and j.get("success") is False:
                    raise requests.HTTPError(j.get("error", "delta: success=false"))
                return j
            except Exception as e:
                if i == 4:
                    raise
                time.sleep(0.4 * (2**i))
        return {}

    def positions(self) -> List[Dict]:
        j = self._req("GET", "/v2/positions/margined")
        if isinstance(j, dict) and "result" in j:
            return j["result"]
        if isinstance(j, list):
            return j
        return []

    def balances(self) -> Dict[str, Any]:
        j = self._req("GET", "/v2/wallet/balances")
        return j if isinstance(j, dict) else {}

    def tickers(self) -> List[Dict]:
        j = self._req("GET", "/v2/tickers")
        if isinstance(j, dict) and "result" in j:
            return j["result"]
        if isinstance(j, list):
            return j
        return []

    def fills_window(self, start_ms: int, end_ms: int, page_size: int = 100) -> List[Dict]:
        """
        Try /v2/orders/history/fills (ms), fall back to /v2/fills (microseconds).
        """
        def fetch(path: str, use_microseconds: bool) -> List[Dict]:
            out, after = [], None
            while True:
                params = {
                    "start_time": int(start_ms*1000) if use_microseconds else int(start_ms),
                    "end_time":   int(end_ms*1000)   if use_microseconds else int(end_ms),
                    "page_size": page_size
                }
                if after: params["after"] = after
                j = self._req("GET", path, params)
                batch, meta = [], {}
                if isinstance(j, dict):
                    if isinstance(j.get("result"), list):
                        batch, meta = j["result"], j.get("meta", {})
                    elif isinstance(j.get("items"), list):
                        batch, meta = j["items"], j.get("meta", {})
                elif isinstance(j, list):
                    batch = j
                if not batch: break
                out.extend(batch)
                after = (meta or {}).get("after")
                if not after: break
            return out

        try:
            f = fetch("/v2/fills", use_microseconds=True)
            if f: return f
        except Exception:
            pass
        return fetch("/v2/fills", use_microseconds=True)

def compute_report(api: DeltaAPI, start_ms: int, end_ms: int) -> Dict[str, Any]:
    pos = api.positions()
    bal = api.balances()
    fills = api.fills_window(start_ms, end_ms)
    # normalize fills timestamps to ms
    norm_fills = []
    for f in (fills or []):
        ts = parse_iso_or_epoch(f.get("created_at"))
        sym = f.get("product_symbol") or ((f.get("product") or {}).get("symbol")) or "UNKNOWN"
        role = f.get("role") or ""
        commission = float(f.get("commission") or 0.0)
        size = float(f.get("size") or 0.0)
        price = float(f.get("price") or 0.0)
        side = f.get("side") or ""
        norm_fills.append({
            "id": f.get("id") or f.get("fill_id") or f.get("trade_id"),
            "created_at_ms": ts,
            "created_at": fmt_local(ts),
            "product_symbol": sym,
            "side": side,
            "size": size,
            "price": price,
            "commission": commission,
            "role": role,
            "order_id": f.get("order_id"),
            "fill_type": f.get("fill_type") or "",
        })
    norm_fills.sort(key=lambda x: x["created_at_ms"])

    # position metrics
    total_realized = 0.0
    total_unrealized = 0.0
    total_blocked_commission = 0.0
    position_rows = []
    for p in (pos or []):
        size = float(p.get("size") or 0.0)
        if size == 0:
            continue
        entry = float(p.get("entry_price") or 0.0)
        mark  = float(p.get("mark_price")  or 0.0)
        realized = float(p.get("realized_pnl") or 0.0)
        unreal   = float(p.get("unrealized_pnl") or 0.0)
        comm     = float(p.get("commission") or 0.0)
        total_realized += realized
        total_unrealized += unreal
        total_blocked_commission += abs(comm)
        position_rows.append({
            "product_symbol": p.get("product_symbol") or ((p.get("product") or {}).get("symbol")) or "UNKNOWN",
            "size": size, "entry_price": entry, "mark_price": mark,
            "realized_pnl": realized, "unrealized_pnl": unreal,
            "liquidation_price": p.get("liquidation_price"),
            "margin": p.get("margin"),
        })

    # commissions paid in fills
    total_trade_commission = sum(abs(float(f["commission"])) for f in norm_fills)
    net_equity = None
    try:
        net_equity = float((bal.get("meta") or {}).get("net_equity") or 0.0)
    except Exception:
        net_equity = None

    total_pnl = total_realized + total_unrealized
    report = {
        "generated_at": fmt_local(int(time.time()*1000)),
        "window": {
            "start_ms": start_ms, "end_ms": end_ms,
            "start_local": fmt_local(start_ms), "end_local": fmt_local(end_ms),
        },
        "summary": {
            "net_equity": net_equity,
            "total_realized_pnl": total_realized,
            "total_unrealized_pnl": total_unrealized,
            "total_pnl": total_pnl,
            "trade_commission_paid": total_trade_commission,
            "position_commission_blocked": total_blocked_commission,
            "fills_count": len(norm_fills),
            "open_positions": len(position_rows),
        },
        "positions": position_rows,
        "fills": norm_fills,
        "balances_raw": bal,
    }
    return report

def save_json_csv(report: Dict[str, Any], outdir: str) -> Tuple[str, str]:
    ensure_dir(outdir)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fp_json = os.path.join(outdir, f"pnl_report_{ts}.json")
    fp_csv  = os.path.join(outdir, f"pnl_summary_{ts}.csv")

    with open(fp_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # CSV summary + top positions + last 50 fills
    with open(fp_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        s = report["summary"]
        w.writerow(["Metric", "Value"])
        for k in ("net_equity","total_realized_pnl","total_unrealized_pnl","total_pnl",
                  "trade_commission_paid","position_commission_blocked","fills_count","open_positions"):
            w.writerow([k, s.get(k)])

        w.writerow([])
        w.writerow(["Open Positions"])
        w.writerow(["symbol","size","entry","mark","realized","unrealized"])
        for p in report["positions"]:
            w.writerow([p["product_symbol"], p["size"], p["entry_price"], p["mark_price"], p["realized_pnl"], p["unrealized_pnl"]])

        w.writerow([])
        w.writerow(["Recent Fills (last 50)"])
        w.writerow(["time","symbol","side","size","price","commission","role","type","order_id"])
        for frow in report["fills"][-50:]:
            w.writerow([frow["created_at"], frow["product_symbol"], frow["side"], frow["size"],
                        frow["price"], frow["commission"], frow["role"], frow["fill_type"], frow["order_id"]])

    return fp_json, fp_csv

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Delta PnL Tracker (robust)")
    ap.add_argument("--since", type=str, default=None, help="Start time ISO (YYYY-MM-DDTHH:MM[:SS]Z) or epoch seconds")
    ap.add_argument("--until", type=str, default=None, help="End time ISO or epoch seconds")
    ap.add_argument("--hours", type=float, default=1.0, help="Lookback hours if since/until not set")
    ap.add_argument("--outdir", type=str, default="reports", help="Output directory")
    return ap.parse_args()

def main():
    args = parse_args()
    key = envs("DELTA_API_KEY")
    sec = envs("DELTA_API_SECRET")
    base = envs("DELTA_BASE_URL", "https://api.india.delta.exchange")
    if not (key and sec):
        print("ERROR: set DELTA_API_KEY / DELTA_API_SECRET in environment (.env)", file=sys.stderr)
        sys.exit(2)

    if args.since or args.until:
        start_ms = parse_iso_or_epoch(args.since) if args.since else int(time.time()*1000 - args.hours*3600*1000)
        end_ms   = parse_iso_or_epoch(args.until) if args.until else int(time.time()*1000)
    else:
        end_ms = int(time.time()*1000)
        start_ms = end_ms - int(args.hours*3600*1000)

    api = DeltaAPI(key, sec, base)
    rep = compute_report(api, start_ms, end_ms)
    fpj, fpc = save_json_csv(rep, args.outdir)
    print(f"[ok] JSON: {fpj}")
    print(f"[ok] CSV : {fpc}")
    # brief console summary
    s = rep["summary"]
    print(f"[sum] realized={s['total_realized_pnl']:.8f}  unrealized={s['total_unrealized_pnl']:.8f}  "
          f"total={s['total_pnl']:.8f}  fills={s['fills_count']}  positions={s['open_positions']}")

if __name__ == "__main__":
    main()
