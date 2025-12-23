#!/usr/bin/env bash
set -euo pipefail

echo "➤ Installing live-execution safety guard"

# 1) Create bot/safety.py (idempotent overwrite is fine)
mkdir -p bot
cat > bot/safety.py <<'PY'
from __future__ import annotations
import os, sys

def color(s: str, c: str) -> str:
    codes = {"red":"\033[31m","grn":"\033[32m","ylw":"\033[33m","dim":"\033[2m","clr":"\033[0m"}
    return f"{codes.get(c,'')}{s}{codes['clr']}"

def preflight(logger=None):
    """Hard stop if EXECUTE_ORDERS=true and user hasn't set I_UNDERSTAND_LIVE=YES."""
    exec_orders = (os.getenv("EXECUTE_ORDERS","false").lower() == "true")
    understood   = (os.getenv("I_UNDERSTAND_LIVE","NO").upper() == "YES")
    mode = "LIVE" if exec_orders else "DRY"
    note = f"Mode={mode}  EXECUTE_ORDERS={exec_orders}  I_UNDERSTAND_LIVE={os.getenv('I_UNDERSTAND_LIVE','NO')}"
    if exec_orders and not understood:
        msg = f"SAFETY BLOCK: {note} — set I_UNDERSTAND_LIVE=YES to allow live execution."
        if logger: logger.error(msg)
        else:      print(color(msg,"red"), file=sys.stderr)
        sys.exit(2)
    # Optional, log a friendly banner when safe
    ok = f"SAFETY OK: {note}"
    if logger: logger.info(ok)
    else:      print(color(ok,"grn"))
PY

# 2) Patch bot/run.py to import and call safety.preflight() before status banner
python3 - <<'PY'
import re
from pathlib import Path

p = Path("bot/run.py")
s = p.read_text(encoding="utf-8", errors="replace")

orig = s

# Ensure import
if not re.search(r'(?m)^\s*from\s+bot\s+import\s+safety\b', s) and \
   not re.search(r'(?m)^\s*import\s+bot\.safety\b', s):
    # place after first import block
    s = re.sub(r'(?m)^(\s*(?:from\s+\S+\s+import\s+\S+|import\s+\S+).*\n)+',
               lambda m: m.group(0) + "from bot import safety\n",
               s, count=1) or ("from bot import safety\n" + s)

# Insert safety.preflight(logger) just before the "=== Bot Startup Status ===" banner line (or near first Ping/Tick if banner missing)
insertion_done = False

# Primary anchor: banner
m = re.search(r'(?m)logger\.info\(\s*[\'"]=== Bot Startup Status ===[\'"]\s*\)', s)
if m:
    # insert a line right before
    s = s[:m.start()] + "safety.preflight(logger)\n" + s[m.start():]
    insertion_done = True
else:
    # Fallback: before first 'Ping ->' log
    m2 = re.search(r'(?m)logger\.info\(\s*[f]?[\'"]Ping\s*->', s)
    if m2:
        s = s[:m2.start()] + "safety.preflight(logger)\n" + s[m2.start():]
        insertion_done = True

# If still not inserted, just put near top of main
if not insertion_done:
    # After we get a 'logger =' line, insert once
    m3 = re.search(r'(?m)^\s*logger\s*=\s*.*$', s)
    if m3:
        s = s[:m3.end()] + "\n\nsafety.preflight(logger)\n" + s[m3.end():]
        insertion_done = True

if s != orig:
    Path("bot/run.py").write_text(s, encoding="utf-8")
    print("✅ Patched run.py: safety.preflight(logger) added.")
else:
    print("ℹ️ run.py already contains safety preflight (no change).")
PY

# 3) Quick compile sanity
python3 -m py_compile $(find bot -name '*.py' -print)
echo "✔ Safety upgrade installed"
