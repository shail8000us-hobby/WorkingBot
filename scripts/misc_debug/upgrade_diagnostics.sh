#!/usr/bin/env bash
set -euo pipefail

echo "➤ Installing diagnostics fingerprint & snapshot"

# 1) Create bot/diagnostics.py
mkdir -p bot
cat > bot/diagnostics.py <<'PY'
from __future__ import annotations
import os, sys, json, hashlib, time, subprocess, shutil, platform
from pathlib import Path
from typing import Dict, Any

SNAPSHOT_PATH = Path("bot/run_snapshot.json")

KEY_ENVS = [
    "EXECUTE_ORDERS","DELTA_DRY_ORDERS","I_UNDERSTAND_LIVE",
    "DELTA_BASE_URL","WD_MAX_API_FAIL","WD_MAX_STALE_S","WD_AUTOSAVE_EVERY",
    "SYMBOL","LOT","STEP","BOUNDS_LOW","BOUNDS_HIGH"
]

def _git_info() -> Dict[str, Any]:
    def run(*cmd):
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            return out
        except Exception:
            return None
    if shutil.which("git") is None:
        return {"present": False}
    root = run("git","rev-parse","--show-toplevel")
    if not root: return {"present": False}
    branch = run("git","rev-parse","--abbrev-ref","HEAD")
    commit = run("git","rev-parse","HEAD")
    status = run("git","status","--porcelain")
    dirty = bool(status)
    return {"present": True, "root": root, "branch": branch, "commit": commit, "dirty": dirty}

def _env_subset() -> Dict[str, str]:
    out: Dict[str,str] = {}
    for k in KEY_ENVS:
        v = os.getenv(k)
        if v is not None:
            out[k] = v
    return out

def _runtime_info() -> Dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "venv": os.getenv("VIRTUAL_ENV"),
        "cwd": str(Path.cwd()),
    }

def _hash_of(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",",":")).encode()
    return hashlib.sha256(b).hexdigest()

def snapshot(logger=None) -> str:
    """Write a run snapshot JSON and return a short fingerprint string."""
    data = {
        "ts": int(time.time()),
        "env": _env_subset(),
        "runtime": _runtime_info(),
        "git": _git_info()
    }
    try:
        SNAPSHOT_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        if logger: logger.warning(f"DIAG: failed to write snapshot: {e}")
    fp = _hash_of(data)[:12]
    if logger:
        logger.info(f"DIAG: fingerprint={fp} envs={data['env']}")
        gi = data["git"]
        if gi.get("present"):
            logger.info(f"DIAG: git branch={gi.get('branch')} commit={gi.get('commit')}{' (dirty)' if gi.get('dirty') else ''}")
    else:
        print(f"fingerprint={fp} envs={data['env']}")
    return fp
PY

# 2) Patch bot/run.py to import and call diagnostics.snapshot(logger) after safety.preflight
python3 - <<'PY'
import re
from pathlib import Path

p = Path("bot/run.py")
s = p.read_text(encoding="utf-8", errors="replace")
orig = s

# Ensure import line
if not re.search(r'(?m)^\s*from\s+bot\s+import\s+diagnostics\b', s) and \
   not re.search(r'(?m)^\s*import\s+bot\.diagnostics\b', s):
    s = re.sub(r'(?m)^(\s*(?:from\s+\S+\s+import\s+\S+|import\s+\S+).*\n)+',
               lambda m: m.group(0) + "from bot import diagnostics\n",
               s, count=1) or ("from bot import diagnostics\n" + s)

# Find where we already inserted safety.preflight and add diagnostics call right after it.
m = re.search(r'(?m)^\s*safety\.preflight\(logger\)\s*$', s)
if m:
    insert_at = m.end()
    s = s[:insert_at] + "\n" + "diagnostics.snapshot(logger)\n" + s[insert_at:]
else:
    # fallback: before banner or Ping
    m2 = re.search(r'(?m)logger\.info\(\s*[\'\"]=== Bot Startup Status ===[\'\"]\s*\)', s) \
         or re.search(r'(?m)logger\.info\(\s*[f]?[\'\"]Ping\s*->', s)
    if m2:
        s = s[:m2.start()] + "diagnostics.snapshot(logger)\n" + s[m2.start():]

if s != orig:
    p.write_text(s, encoding="utf-8")
    print("✅ Patched run.py: diagnostics.snapshot(logger) added.")
else:
    print("ℹ️ run.py seems already patched; no change.")
PY

# 3) Compile
python3 -m py_compile $(find bot -name '*.py' -print)
echo "✔ Diagnostics upgrade installed"
