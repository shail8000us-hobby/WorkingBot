#!/usr/bin/env bash
set -euo pipefail

# Load experimental env and grid file
set -a
[[ -f ".env.experimental" ]] && source ".env.experimental" || true
set +a

CFG="${GRID_CONFIG_PATH:-grid_config.env}"
if [[ -f "$CFG" ]]; then
  # shellcheck disable=SC1090
  source "$CFG"
else
  echo "Error: $CFG not found" >&2
  exit 1
fi

# Map to legacy variable names expected by dashboard/set_grid.sh
export GRID_LOWER="${LOWER}"
export GRID_UPPER="${UPPER}"
export GRID_REF="${REF}"
export GRID_STEP="${STEP}"
export GRID_LOT="${LOT}"
export GRID_MAX_OPEN="${MAX_OPEN}"

# Some scripts expect REFERENCE_LEVEL explicitly
export REFERENCE_LEVEL="${REF}"
# (Safe extras in case the legacy script uses other names)
export GRID_REFERENCE_LEVEL="${REF}"

echo "⚙️  APPLY adapter → set_grid.sh"
echo "   GRID_LOWER=${GRID_LOWER} REFERENCE_LEVEL=${REFERENCE_LEVEL} GRID_UPPER=${GRID_UPPER} GRID_STEP=${GRID_STEP} GRID_LOT=${GRID_LOT} GRID_MAX_OPEN=${GRID_MAX_OPEN}"

exec bash dashboard/set_grid.sh
