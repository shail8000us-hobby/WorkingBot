#!/usr/bin/env python3
"""
PnL Reporter (exchange-fee-first)

- Pulls fills via CCXT (authoritative) for a time window
- Uses exchange-reported fees from each trade (trade.fee.cost)
- Uses exchange-reported realized PnL if present in trade.info (falls back to local FIFO)
- Computes local realized PnL (FIFO) for reconciliation
- Shows unrealized PnL from current position at the latest price

Usage:
  python3 -m bot.reports.pnl            # last 24h (default symbol from config)
  python3 -m bot.reports.pnl --hours 6
  python3 -m bot.reports.pnl --since "2025-09-09 00:00:00"
  python3 -m bot.reports.pnl --symbol "BTC/USD:USD"

Env:
  DELTA_API_KEY, DELTA_API_SECRET (from environment for security)
"""

from __future__ import annotations
import os, sys, time, argparse, datetime as dt
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import ccxt  # type: ignore

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

# ---------- utils ----------
def color(txt: str, code: str) -> str:
    cfg = get_config()
    if not cfg.logging.color_logs:
        return txt
    return f"\x1b[{code}m{txt}\x1b[0m"

def parse_args():
    cfg = get_config()
    p = argparse.ArgumentParser(description="PnL Reporter (exchange-fee-first)")
    p.add_argument("--hours", type=float, default=24.0, help="lookback hours (ignored if --since provided)")
    p.add_argument("--since", type=str, default=None, help="since local time 'YYYY-MM-DD HH:MM:SS'")
    p.add_argument("--symbol", type=str, default=cfg.trading.symbol, help="Trading symbol")
    p.add_argument("--limit", type=int, default=1000, help="max trades to fetch")
    p.add_argument("--show", action="store_true", help="print per-trade rows")
    return p.parse_args()

def to_ms(t: dt.datetime) -> int:
    return int(t.timestamp() * 1000)

def parse_since(args) -> int:
    if args.since:
        try:
            local = dt.datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
            return to_ms(local)
        except Exception:
            print("Invalid --since; use 'YYYY-MM-DD HH:MM:SS'", file=sys.stderr)
            sys.exit(2)
    else:
        return to_ms(dt.datetime.now() - dt.timedelta(hours=args.hours))

def connect_ccxt() -> ccxt.delta:
    cfg = get_config()
    ex = ccxt.delta({
        "apiKey": os.getenv("DELTA_API_KEY"),
        "secret": os.getenv("DELTA_API_SECRET"),
        "enableRateLimit": True,
    })
    # Get API URL from config based on trading mode
    if cfg.safety.trading_mode == 'demo':
        base_url = cfg.api.demo.public_url
    else:
        base_url = cfg.api.live.public_url
    ex.urls["api"] = {"public": base_url, "private": base_url}
    return ex

# ---------- fetchers ----------
def fetch_trades(ex: ccxt.delta, symbol: str, since_ms: int, limit: int) -> List[Dict[str, Any]]:
    try:
        return ex.fetch_my_trades(symbol, since=since_ms, limit=limit) or []
    except Exception as e:
        print(f"Failed to fetch trades: {e}")
        return []

def fetch_positions(ex: ccxt.delta, symbol: str) -> Tuple[float, Optional[float]]:
    try:
        try:
            poss = ex.fetch_positions([symbol])
        except Exception:
            poss = ex.fetch_positions()
        for p in poss or []:
            if p.get("symbol") == symbol:
                size  = p.get("contracts") or p.get("size") or p.get("amount") or 0
                entry = p.get("entryPrice") or p.get("entry_price")
                return float(size or 0), (float(entry) if entry is not None else None)
    except Exception:
        pass
    return 0.0, None

def fetch_ticker(ex: ccxt.delta, symbol: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    try:
        t = ex.fetch_ticker(symbol)
        return t.get("last"), t.get("bid"), t.get("ask")
    except Exception:
        return None, None, None

# ---------- local FIFO realized PnL ----------
def fifo_realized_pnl(trades: List[Dict[str, Any]]) -> Tuple[float, float, int]:
    """
    Returns: (realized_pnl_quote, total_fees_quote, trade_count)
    """
    inv: List[Tuple[str, float, float]] = []
    realized = 0.0
    fees = 0.0
    count = 0

    for tr in trades:
        side = tr.get("side")
        price = float(tr.get("price") or 0.0)
        amount = float(tr.get("amount") or 0.0)
        if amount <= 0 or price <= 0 or side not in ("buy","sell"):
            continue

        # Exchange-reported fee
        fee = tr.get("fee") or {}
        try:
            fees += float(fee.get("cost") or 0.0)
        except Exception:
            pass

        count += 1

        if side == "buy":
            remaining = amount
            i = 0
            while i < len(inv) and remaining > 0:
                s, q, p = inv[i]
                if s == "sell":
                    take = min(q, remaining)
                    realized += (p - price) * take  # closing short
                    q -= take; remaining -= take
                    if q <= 1e-12:
                        inv.pop(i); continue
                    else:
                        inv[i] = (s, q, p)
                i += 1
            if remaining > 1e-12:
                inv.append(("buy", remaining, price))
        else:
            remaining = amount
            i = 0
            while i < len(inv) and remaining > 0:
                s, q, p = inv[i]
                if s == "buy":
                    take = min(q, remaining)
                    realized += (price - p) * take  # closing long
                    q -= take; remaining -= take
                    if q <= 1e-12:
                        inv.pop(i); continue
                    else:
                        inv[i] = (s, q, p)
                i += 1
            if remaining > 1e-12:
                inv.append(("sell", remaining, price))

    return realized, fees, count

# ---------- extract exchange-reported realized pnl if present ----------
def extract_exchange_pnl(trades: List[Dict[str, Any]]) -> Optional[float]:
    """
    Some exchanges include realized PnL at trade level inside trade.info.
    If Delta exposes it, surface the sum here. If not present, return None.
    """
    total = 0.0
    found = False
    for tr in trades:
        info = tr.get("info") or {}
        # try common keys
        for k in ("realized_pnl", "realizedPnl", "pnl", "realized"):
            v = info.get(k)
            if v is not None:
                try:
                    total += float(v)
                    found = True
                    break
                except Exception:
                    pass
    return total if found else None

# ---------- pretty print ----------
def print_table(trades: List[Dict[str, Any]]):
    from math import isnan
    headers = ["time", "id", "side", "price", "amount", "cost", "fee", "maker?"]
    print(" | ".join(headers))
    print("-" * 90)
    for tr in trades:
        ts = tr.get("timestamp")
        tstr = dt.datetime.fromtimestamp(ts/1000.0).strftime("%Y-%m-%d %H:%M:%S") if ts else "?"
        tid = tr.get("id") or tr.get("order")
        side = tr.get("side")
        price = tr.get("price")
        amount = tr.get("amount")
        cost = tr.get("cost")
        fee = (tr.get("fee") or {}).get("cost")
        mk = tr.get("takerOrMaker")
        print(f"{tstr} | {tid} | {side} | {price} | {amount} | {cost} | {fee} | {mk}")

# ---------- main ----------
def main():
    args = parse_args()
    symbol = args.symbol
    since_ms = parse_since(args)

    ex = connect_ccxt()

    # Pull authoritative data
    try:
        bal = ex.fetch_balance()
    except Exception as e:
        print(f"WARNING: balance fetch failed: {e}")
        bal = {}

    trades = fetch_trades(ex, symbol, since_ms, args.limit)
    last, bid, ask = fetch_ticker(ex, symbol)
    pos_size, pos_entry = fetch_positions(ex, symbol)

    # Local math (FIFO) + exchange fee total
    realized_local, fee_total, n_tr = fifo_realized_pnl(trades)
    pnl_exchange = extract_exchange_pnl(trades)  # may be None if not reported
    net_local = realized_local - fee_total

    # Unrealized PnL
    unreal = None
    if pos_size and pos_entry and last:
        if pos_size >= 0:
            unreal = (last - pos_entry) * pos_size
        else:
            unreal = (pos_entry - last) * abs(pos_size)

    # Output
    print(color("=== PnL SUMMARY (Delta via CCXT) ===", "36"))
    print(f"Symbol          : {symbol}")
    print(f"Window start    : {dt.datetime.fromtimestamp(since_ms/1000.0)} (local)")
    print(f"Fills counted   : {n_tr}")
    if pnl_exchange is not None:
        print(f"Realized (EXCH) : {color(f'{pnl_exchange:.4f}', '32' if pnl_exchange>=0 else '31')} (quote)")
    else:
        print("Realized (EXCH) : n/a (exchange did not report per-trade realized PnL)")
    print(f"Fees   (EXCH)   : {fee_total:.4f} (quote)")
    print(f"Realized (LOCAL): {color(f'{realized_local:.4f}', '32' if realized_local>=0 else '31')} (quote)")
    print(f"Net    (LOCAL)  : {color(f'{net_local:.4f}', '32' if net_local>=0 else '31')} (quote)")
    print(f"Last/Bid/Ask    : {last} / {bid} / {ask}")
    if pos_size:
        print(f"Position        : size={pos_size} entry={pos_entry}")
    else:
        print("Position        : none")
    if unreal is not None:
        print(f"Unrealized PnL  : {color(f'{unreal:.4f}', '32' if unreal>=0 else '31')} (quote)")
    print(color("====================================", "36"))

    if args.show and trades:
        print()
        print(color("Trades (most recent first):", "90"))
        print_table(trades[::-1])

if __name__ == "__main__":
    main()
