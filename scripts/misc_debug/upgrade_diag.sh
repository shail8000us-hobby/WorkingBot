#!/usr/bin/env bash
set -euo pipefail

file="bot/run.py"
backup="bot/run.py.bak.$(date +%s)"
cp -v "$file" "$backup"

python3 - <<'PY'
import re, sys, json
from pathlib import Path

p = Path("bot/run.py")
s = p.read_text(encoding="utf-8", errors="replace")
orig = s

# 1) Ensure imports
def ensure_import(src, mod):
    if re.search(rf'(?m)^\s*import\s+{re.escape(mod)}\b', src): return src
    # Insert after first import line if any, else prepend
    m = re.search(r'(?m)^(?:from\s+\S+\s+import\s+\S+|import\s+\S+).*$', src)
    if m:
        return src[:m.end()] + f"\nimport {mod}" + src[m.end():]
    return f"import {mod}\n{src}"

for mod in ("json","time","os","pathlib","logging"):
    s = ensure_import(s, mod)

# 2) Insert diag helper if missing
if "def _wd_diag_emit(" not in s:
    helper = '''
# ---- diagnostics helper (opt-in via WD_DIAG=1) ----
def _wd_diag_emit(stage, extra=None):
    try:
        if not os.environ.get("WD_DIAG"):
            return
        logger = logging.getLogger("runner")
        payload = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "stage": stage,
        }
        if isinstance(extra, dict):
            payload["extra"] = extra
        try:
            from pathlib import Path as _Path
            _Path("bot/run_snapshot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as _e:
            logger.debug("diag snapshot write failed: %s", _e)
        try:
            logger.info("DIAG: %s", json.dumps(payload, separators=(",",":")))
        except Exception as _e:
            pass
    except Exception as e:
        logging.getLogger("runner").debug("diag emit failed: %s", e)
# ---------------------------------------------------
'''
    # put the helper after all imports (first blank line after imports)
    m = re.search(r'(?s)(^(?:from\s+\S+\s+import.*|import\s+\S+).*\n)(?:\n)?', s)
    if m:
        s = s[:m.end()] + helper + s[m.end():]
    else:
        s = helper + s

# 3) Emit "start" before the first Tick log
if "DIAG: " not in s or "stage\":\"start\"" not in s:
    # find first Tick log line
    m = re.search(r'(?m)^([ \t]*)logger\.(?:info|debug)\(\s*[f]?[\'"]Tick\b', s)
    if m:
        indent = m.group(1)
        inject = f"{indent}_wd_diag_emit('start')\n"
        s = s[:m.start()] + inject + s[m.start():]

# 4) Emit "end" right before the "Loop done." banner
loop_pat = r'(?m)^(?P<ind>[ \t]*)logger\.(?:info|debug)\(\s*[\'"]Loop done\.'
if re.search(loop_pat, s) and "stage\":\"end\"" not in s:
    s = re.sub(loop_pat, r"\g<ind>_wd_diag_emit('end')\n\g<ind>logger.info(\"Loop done.", s, count=1)

if s != orig:
    Path("bot/run.py").write_text(s, encoding="utf-8")
    print("✅ Diagnostics hooks inserted (opt-in with WD_DIAG=1).")
else:
    print("ℹ️ No changes made (hooks already present).")
PY

# sanity compile
python3 -m py_compile $(find bot -name '*.py' -print) >/dev/null
echo "✔ upgrade applied and compiled"
