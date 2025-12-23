#!/usr/bin/env bash
set -euo pipefail

# Colors
GRN="\033[32m"; YEL="\033[33m"; DIM="\033[2m"; CLR="\033[0m"

echo -e "${DIM}➤ Standardizing layout (debugging ⇢ reports/audit)…${CLR}"
mkdir -p debugging reports audit bot/logs scripts

# Patterns to move OUT of scripts/misc_debug/
shopt -s nullglob
moved_any=0

move_to() {
  local dest="$1"; shift
  for f in "$@"; do
    [[ -e "$f" ]] || continue
    mkdir -p "$dest"
    mv "$f" "$dest"/
    echo -e "   ${GRN}moved:${CLR} $f  →  $dest/"
    moved_any=1
  done
}

# A) Reports (analytics/outputs)
move_to reports \
  scripts/misc_debug/export_pnl.py \
  scripts/misc_debug/pnl*.csv \
  scripts/misc_debug/*.xlsx \
  scripts/misc_debug/*.parquet \
  scripts/misc_debug/*.feather

# B) Audit (journals/raw data)
move_to audit \
  scripts/misc_debug/order_audit.py \
  audit/order_audit.sh \
  scripts/misc_debug/*journal*.csv \
  scripts/misc_debug/fills*.json \
  scripts/misc_debug/orders*.json

# C) Things that should STAY in scripts/misc_debug/ (no move, just informative)
stay_list=(
  "scripts/misc_debug/run_all.sh"
  "scripts/misc_debug/tail_live.sh"
  "scripts/preflight.sh"
)
for f in "${stay_list[@]}"; do
  [[ -e "$f" ]] && echo -e "   ${DIM}keep :${CLR} $f"
done

# D) Readmes to clarify intent
if [[ ! -f scripts/misc_debug/README.md ]]; then
  cat > scripts/misc_debug/README.md <<'MD'
# scripts/misc_debug/
Health checks, smoke tests, live log tails, and preflight diagnostics.
Keep analytics and journals OUT of this folder (see ../reports and ../audit).
MD
  echo -e "   ${GRN}created:${CLR} scripts/misc_debug/README.md"
fi

if [[ ! -f reports/README.md ]]; then
  cat > reports/README.md <<'MD'
# reports/
PnL & analytics (CSV/XLSX/Parquet), charts, summaries generated from audit data.
MD
  echo -e "   ${GRN}created:${CLR} reports/README.md"
fi

if [[ ! -f audit/README.md ]]; then
  cat > audit/README.md <<'MD'
# audit/
Raw, append-only execution evidence: fills, order journals, event streams.
These power the reports/ exporters.
MD
  echo -e "   ${GRN}created:${CLR} audit/README.md"
fi

# E) Update handy aliases
cat > scripts/aliases.sh <<'BASH'
# Source me:  source scripts/aliases.sh
alias grid-fast='bash scripts/misc_debug/run_all.sh'
alias grid-smoke='bash scripts/misc_debug/run_all.sh smoke'
alias grid-tail='bash scripts/misc_debug/tail_live.sh'
alias grid-audit='ls -lh audit | tail -n +1'
alias grid-report='ls -lh reports | tail -n +1'
BASH
echo -e "   ${GRN}updated:${CLR} scripts/aliases.sh"
echo -e "${DIM}   Tip: run  source scripts/aliases.sh  to load aliases in this terminal${CLR}"

# F) Summary
if [[ $moved_any -eq 0 ]]; then
  echo -e "${YEL}   Nothing to move; layout already clean.${CLR}"
fi
echo -e "${GRN}✔ Layout normalized.${CLR}"
