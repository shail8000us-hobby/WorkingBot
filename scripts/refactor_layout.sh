#!/usr/bin/env bash
set -euo pipefail

# A) Folders
mkdir -p reports audit debugging scripts
mkdir -p bot/logs

echo "➤ Refactor: ensuring standard layout"
echo "   - reports/: PnL & analytics"
echo "   - audit/:   raw execution journals (future)"
echo "   - scripts/misc_debug/: health checks & tails (already in use)"

# B) Move any report-ish files out of scripts/misc_debug/ if they exist
shopt -s nullglob
found=0
for f in scripts/misc_debug/export_pnl.py scripts/misc_debug/pnl*.csv scripts/misc_debug/*.xlsx scripts/misc_debug/*.parquet scripts/misc_debug/*.feather; do
  mv "$f" reports/ && echo "   moved: $f -> reports/" && found=1 || true
done
[[ $found -eq 0 ]] && echo "   nothing to move from scripts/misc_debug/ (all good)"

# C) Minimal reports/README so the purpose is clear
if [[ ! -f reports/README.md ]]; then
  cat > reports/README.md <<'MD'
# reports/
- **What**: PnL summaries, mark-to-market, analytics exports (CSV/XLSX/Parquet), charts.
- **Sources**: data derived from `audit/` (raw fills/orders) and/or `bot/logs/`.
- **Keep** debugging helpers in `scripts/misc_debug/`, not here.
MD
  echo "   created: reports/README.md"
fi

# D) Optional: create a thin placeholder exporter only if none exists
if [[ ! -f reports/export_pnl.py ]]; then
  cat > reports/export_pnl.py <<'PY'
#!/usr/bin/env python3
"""
Minimal placeholder exporter.
Writes reports/pnl_demo.csv so the shortcut works without touching trading logic.
Replace later with real audit->PnL once fills journaling is enabled.
"""
from pathlib import Path
import csv, time
out = Path("reports/pnl_demo.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="") as fp:
    w = csv.writer(fp)
    w.writerow(["timestamp","ref_price","unrealized_pnl","note"])
    w.writerow([int(time.time()), "", "", "placeholder; replace with real exporter later"])
print(f"✅ wrote {out}")
PY
  chmod +x reports/export_pnl.py
  echo "   created: reports/export_pnl.py (placeholder)"
fi

# E) Shortcuts (aliases) for your daily use
mkdir -p scripts
cat > scripts/aliases.sh <<'BASH'
# Source this file in a shell:  source scripts/aliases.sh
alias grid-smoke='bash scripts/misc_debug/run_all.sh smoke'
alias grid-fast='bash scripts/misc_debug/run_all.sh'
alias grid-tail='bash scripts/misc_debug/tail_live.sh'
alias grid-pnl='python reports/export_pnl.py && ls -l reports/pnl_*.csv reports/pnl_demo.csv 2>/dev/null | tail -n 3'
BASH
echo "   created/updated: scripts/aliases.sh"

echo "➤ Done. Tip: add to your shell profile so aliases persist:"
echo "     source \"$(pwd)/scripts/aliases.sh\""
