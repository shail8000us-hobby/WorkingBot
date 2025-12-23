#!/usr/bin/env bash
set -euo pipefail
JSONL="bot/audit/orders.jsonl"

# Colors (fallback to plain if not a TTY)
if [[ -t 1 ]]; then RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; CYA=$'\033[36m'; DIM=$'\033[2m'; CLR=$'\033[0m'
else RED=""; GRN=""; YEL=""; CYA=""; DIM=""; CLR=""
fi

# Ensure we have fresh audit data (order_audit.sh will also create CSV)
if [[ ! -s "$JSONL" ]]; then
  bash debugging/order_audit.sh once >/dev/null 2>&1 || true
fi
[[ -s "$JSONL" ]] || { echo "${YEL}No audit events found (yet).${CLR}"; exit 0; }

python - <<'PY'
import json, pathlib, sys
p = pathlib.Path("bot/audit/orders.jsonl")
events = []
with p.open("r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            events.append(json.loads(line))
        except Exception:
            pass

from collections import Counter, defaultdict
cat = Counter(e.get("category","info") for e in events)
lvl = Counter(e.get("level","INFO") for e in events)
side = Counter(e.get("side") for e in events if e.get("side"))

# Keep only interesting last 5 events
interesting = [e for e in events if e.get("category") in {
    "placed_buy","placed_sell","filled","take_profit","error","warning","breaker"
}]
tail = interesting[-5:]

def n(x): return cat.get(x,0)
def L(x): return lvl.get(x,0)

print("\n=== Order Audit Summary ===")
print(f"Total events: {len(events)} | Interesting: {len(interesting)}")
print("Categories:")
print(f"  placed_buy:  {n('placed_buy'):>4}   placed_sell: {n('placed_sell'):>4}   filled: {n('filled'):>4}   take_profit: {n('take_profit'):>4}")
print(f"  warnings:    {n('warning'):>4}   errors:      {n('error'):>4}   breaker: {n('breaker'):>4}")
print("Sides:")
print(f"  buy: {side.get('buy',0):>4}   sell: {side.get('sell',0):>4}")
print("Log levels:")
print(f"  INFO: {L('INFO'):>4}   WARNING: {L('WARNING'):>4}   ERROR: {L('ERROR'):>4}")

if tail:
    print("\nLast 5 interesting events:")
    for e in tail:
        ts = e.get("ts","")
        catg = e.get("category","")
        s = e.get("side") or "-"
        px = e.get("price") or "-"
        q = e.get("qty") or "-"
        txt = e.get("msg","").strip()
        if len(txt) > 120: txt = txt[:117] + "..."
        print(f"  {ts}  {catg:12} side={s:4} qty={q:6} px={px:10}  | {txt}")
PY
