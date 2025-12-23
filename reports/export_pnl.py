#!/usr/bin/env python
import csv
import datetime as dt
import json
import pathlib
from collections import defaultdict, deque

AUDIT_DIR = pathlib.Path("bot/audit")
JSONL = AUDIT_DIR / "orders.jsonl"
ORDERS_CSV = AUDIT_DIR / "orders.csv"
PNL_TRADES_CSV = AUDIT_DIR / "pnl_trades.csv"
PNL_DAILY_CSV = AUDIT_DIR / "pnl_daily.csv"
XLSX_PATH = AUDIT_DIR / "pnl_report.xlsx"


def parse_ts(s):
    # Accept "YYYY-mm-dd HH:MM:SS,ms" or iso-like; fall back to raw
    for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s, fmt)
        except Exception:
            pass
    try:
        return dt.datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None


def load_events():
    events = []
    if not JSONL.exists():
        return events
    with JSONL.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        events.append(item)
                continue
            if isinstance(payload, dict):
                events.append(payload)
    # Normalize a few fields
    for e in events:
        e["ts_dt"] = parse_ts(e.get("ts", "")) or dt.datetime.min
        # coerce numerics if present
        for k in ("price", "qty"):
            v = e.get(k)
            try:
                if v is None:
                    continue
                e[k] = float(v)
            except Exception:
                e[k] = None
    events.sort(key=lambda x: x.get("ts_dt", dt.datetime.min))
    return events


def write_orders_csv(events):
    if not events:
        return
    # flatten keys
    fields = set()
    for e in events:
        fields.update(e.keys())
    fields = [c for c in sorted(fields) if c not in {"ts_dt"}]
    with ORDERS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in events:
            row = {k: ("" if e.get(k) is None else e.get(k)) for k in fields}
            w.writerow(row)


def fifo_pnl(events):
    """
    Simple FIFO matcher:
    - Takes events where category=='filled' and side in {'buy','sell'}
    - Matches SELLs to prior BUY inventory.
    - PnL in quote currency: (sell_px - buy_px) * qty
    Assumes no fees; extend later if needed.
    """
    buys = deque()
    trades = []  # closed pairs
    for e in events:
        if e.get("category") != "filled":
            continue
        side = (e.get("side") or "").lower()
        px, qty, ts = e.get("price"), e.get("qty"), e.get("ts_dt")
        if px is None or qty is None:
            continue
        if side == "buy":
            buys.append({"ts": ts, "price": px, "qty": qty})
        elif side == "sell":
            remaining = qty
            while remaining > 1e-12 and buys:
                lot = buys[0]
                take = min(lot["qty"], remaining)
                pnl = (px - lot["price"]) * take
                trades.append(
                    {
                        "buy_ts": lot["ts"],
                        "buy_px": lot["price"],
                        "sell_ts": ts,
                        "sell_px": px,
                        "qty": take,
                        "pnl": pnl,
                    }
                )
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] <= 1e-12:
                    buys.popleft()
            # If sells > inventory, we ignore the short remainder (could add short logic later)
    return trades


def write_pnl_trades_csv(trades):
    if not trades:
        return
    with PNL_TRADES_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["buy_ts", "buy_px", "sell_ts", "sell_px", "qty", "pnl"])
        for t in trades:
            w.writerow(
                [
                    t["buy_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                    f"{t['buy_px']:.2f}",
                    t["sell_ts"].strftime("%Y-%m-%d %H:%M:%S"),
                    f"{t['sell_px']:.2f}",
                    f"{t['qty']:.6f}",
                    f"{t['pnl']:.2f}",
                ]
            )


def write_daily(trades):
    by_day = defaultdict(lambda: {"closed_qty": 0.0, "realized_pnl": 0.0, "trades": 0})
    for t in trades:
        day = t["sell_ts"].date().isoformat()
        by_day[day]["closed_qty"] += t["qty"]
        by_day[day]["realized_pnl"] += t["pnl"]
        by_day[day]["trades"] += 1
    rows = sorted(by_day.items(), key=lambda kv: kv[0])
    with PNL_DAILY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "closed_qty", "realized_pnl", "trades"])
        for d, agg in rows:
            w.writerow([d, f"{agg['closed_qty']:.6f}", f"{agg['realized_pnl']:.2f}", agg["trades"]])
    return rows


def maybe_write_xlsx():
    # optional: create XLSX if openpyxl is installed
    try:
        import openpyxl
    except Exception:
        return False
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def add_sheet_from_csv(title, path):
        if not path.exists():
            return
        ws = wb.create_sheet(title=title)
        with path.open("r", encoding="utf-8") as f:
            for r, line in enumerate(csv.reader(f), start=1):
                for c, val in enumerate(line, start=1):
                    ws.cell(row=r, column=c, value=val)

    add_sheet_from_csv("orders", ORDERS_CSV)
    add_sheet_from_csv("pnl_trades", PNL_TRADES_CSV)
    add_sheet_from_csv("pnl_daily", PNL_DAILY_CSV)
    wb.save(XLSX_PATH)
    return True


def main():
    events = load_events()
    if not events:
        print("No audit events found; run a demo/smoke to generate fills.")
        return 0
    write_orders_csv(events)
    trades = fifo_pnl(events)
    write_pnl_trades_csv(trades)
    daily = write_daily(trades)
    wrote_xlsx = maybe_write_xlsx()

    total_trades = len(trades)
    total_pnl = sum(t["pnl"] for t in trades)
    print("=== Export/PnL ===")
    print(f"orders.csv:      {ORDERS_CSV}")
    print(f"pnl_trades.csv:  {PNL_TRADES_CSV}  (rows={total_trades}, realized_pnl={total_pnl:.2f})")
    print(f"pnl_daily.csv:   {PNL_DAILY_CSV}   (days={len(daily)})")
    if wrote_xlsx:
        print(f"xlsx workbook:   {XLSX_PATH}")
    else:
        print("xlsx workbook:   (install `openpyxl` to enable)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
