#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

CFG="grid_config.env"
[ -f "$CFG" ] || { echo "✖ grid_config.env not found at project root"; exit 1; }

# Load values from grid_config.env
set -a
source "$CFG"
set +a

echo "⚙️  Applying grid:"
echo "  LOWER=$GRID_LOWER  UPPER=$GRID_UPPER  STEP=$GRID_STEP  REF=$REFERENCE_LEVEL  LOT=$LOT"

# Backup state.json and write new params
python3 - <<'PY'
import json, os, time
path="state.json"
backup=f"state.backup.{int(time.time())}.json"
try:
    data=json.load(open(path))
except Exception:
    data={}
def f(name): return float(os.environ[name])
params={
  "GRID_LOWER": f("GRID_LOWER"),
  "GRID_UPPER": f("GRID_UPPER"),
  "GRID_STEP": f("GRID_STEP"),
  "REFERENCE_LEVEL": f("REFERENCE_LEVEL"),
  "LOT": float(os.environ["LOT"]),
  "GRID_ACTIVE": True,
  "LAST_SET_AT": int(time.time())
}
if os.path.exists(path):
    open(backup,"w").write(open(path).read())
data.update(params)
open(path,"w").write(json.dumps(data, indent=2))
print("[ok] state.json updated with:", params)
print("[ok] backup written to:", backup if os.path.exists(backup) else "(none)")
PY

echo "✅ Grid applied. Restart the bot if it was already running."
# auto-prune after set_grid
bash scripts/prune_backups.sh
