#!/usr/bin/env python3
import csv
import json
import os
import pathlib
import re
import sys
import time

LOG = pathlib.Path("bot/logs/bot.log")
AUDIT_DIR = pathlib.Path("bot/audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = AUDIT_DIR / "orders.csv"
JSONL_PATH = AUDIT_DIR / "orders.jsonl"

# Example line:
# 2025-09-07 11:51:37,085 [INFO] runner: Tick 1/10 price=...
# We’ll capture timestamp, level, component, message.
LINE_RE = re.compile(
    r"""
^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+
\[(?P<level>[A-Z]+)\]\s+
(?P<comp>[^:]+):\s+
(?P<msg>.+)$
""",
    re.X,
)

# Heuristics to categorize order lines from free-form logs
KEYS = {
    "placed_buy": re.compile(r"\b(placed|submitted|new order)\b.*\bbuy\b", re.I),
    "placed_sell": re.compile(r"\b(placed|submitted|new order)\b.*\bsell\b", re.I),
    "filled": re.compile(r"\b(filled|executed|matched)\b", re.I),
    "take_profit": re.compile(r"\b(tp sell|take profit)\b", re.I),
    "breaker": re.compile(r"\bcircuit breaker|panic\.on\b", re.I),
    "error": re.compile(r"\b(traceback|error|exception)\b", re.I),
    "warning": re.compile(r"\bwarning\b", re.I),
}

# Try to pull qty/price/order_id if present inside the message
PRICE_RE = re.compile(r"\bprice[=:]\s*([0-9]+(?:\.[0-9]+)?)", re.I)
QTY_RE = re.compile(r"\b(qty|quantity|size)[=:]\s*([0-9]+(?:\.[0-9]+)?)", re.I)
OID_RE = re.compile(r"\b(order[_\s-]?id|id)[=:]\s*([A-Za-z0-9\-]+)", re.I)
SIDE_RE = re.compile(r"\b(buy|sell)\b", re.I)


def classify(msg: str):
    msg_l = msg.lower()
    for k, rx in KEYS.items():
        if rx.search(msg_l):
            return k
    return "info"


def parse_fields(msg: str):
    def m(rx, idx=1):
        mo = rx.search(msg)
        return mo.group(idx) if mo else None

    return {
        "price": m(PRICE_RE),
        "qty": m(QTY_RE, 2),
        "order_id": m(OID_RE, 2),
        "side": (m(SIDE_RE) or "").lower() or None,
    }


def write_csv_header_if_needed():
    new = not CSV_PATH.exists()
    f = open(CSV_PATH, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(
        f,
        fieldnames=[
            "ts",
            "level",
            "component",
            "category",
            "side",
            "qty",
            "price",
            "order_id",
            "text",
        ],
    )
    if new:
        w.writeheader()
    return f, w


def record(ev):
    # JSONL
    with open(JSONL_PATH, "a", encoding="utf-8") as j:
        j.write(json.dumps(ev, ensure_ascii=False) + "\n")
    # CSV
    f, w = write_csv_header_if_needed()
    try:
        w.writerow(
            {
                "ts": ev["ts"],
                "level": ev["level"],
                "component": ev["component"],
                "category": ev["category"],
                "side": ev.get("side") or "",
                "qty": ev.get("qty") or "",
                "price": ev.get("price") or "",
                "order_id": ev.get("order_id") or "",
                "text": ev["msg"],
            }
        )
    finally:
        f.close()


def handle_line(line: str):
    m = LINE_RE.match(line)
    if not m:
        return
    d = m.groupdict()
    cat = classify(d["msg"])
    extra = parse_fields(d["msg"])
    ev = {
        "ts": d["ts"],
        "level": d["level"],
        "component": d["comp"],
        "msg": d["msg"],
        "category": cat,
        **extra,
    }
    # Only persist interesting trading categories & problems
    if cat in {"placed_buy", "placed_sell", "filled", "take_profit", "error", "warning", "breaker"}:
        record(ev)


def run_once():
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            handle_line(line)


def run_stream():
    # naive tail -F implemented in Python (works if file grows)
    with open(LOG, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            handle_line(line.rstrip("\n"))


def main():
    mode = "--live" if "--live" in sys.argv else "--once"
    # fresh outputs per session (append behavior but we can start clean)
    # Comment the next two lines if you prefer cumulative logs forever:
    if "--fresh" in sys.argv:
        JSONL_PATH.unlink(missing_ok=True)
        CSV_PATH.unlink(missing_ok=True)
    if mode == "--live":
        run_stream()
    else:
        run_once()


if __name__ == "__main__":
    main()
