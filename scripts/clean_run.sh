#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Desktop/SSR/bot_pro"

# clear locals (safe)
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("state.json")
d = json.loads(p.read_text()) if p.exists() else {}
d["open_positions"] = []
p.write_text(json.dumps(d, indent=2))
print("state.json cleared: open_positions=[]")
PY

# activate venv & run
. venv/bin/activate
python -m bot.run
