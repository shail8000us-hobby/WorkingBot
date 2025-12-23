#!/usr/bin/env bash
set -euo pipefail

CFG="${GRID_CONFIG_PATH:-grid_config.env}"

# Read current values if file exists
if [[ -f "$CFG" ]]; then
  # shellcheck disable=SC1090
  source "$CFG"
  OLD_LOWER="${LOWER:-}"
  OLD_UPPER="${UPPER:-}"
  OLD_REF="${REF:-}"
  OLD_STEP="${STEP:-}"
  OLD_LOT="${LOT:-}"
  OLD_MAX_OPEN="${MAX_OPEN:-}"
else
  OLD_LOWER=""; OLD_UPPER=""; OLD_REF=""; OLD_STEP=""; OLD_LOT=""; OLD_MAX_OPEN=""
fi

# Defaults (in case user omits some flags)
LOWER="${LOWER:-}"; UPPER="${UPPER:-}"; REF="${REF:-}"; STEP="${STEP:-}"; LOT="${LOT:-1}"; MAX_OPEN="${MAX_OPEN:-5}"

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lower) LOWER="$2"; shift 2;;
    --upper) UPPER="$2"; shift 2;;
    --ref|--reference) REF="$2"; shift 2;;
    --step) STEP="$2"; shift 2;;
    --lot) LOT="$2"; shift 2;;
    --max-open) MAX_OPEN="$2"; shift 2;;
    --preset) PRESET="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

# Optional presets
if [[ "${PRESET:-}" == "tight" ]]; then
  : "${STEP:=250}"
elif [[ "${PRESET:-}" == "wide" ]]; then
  : "${STEP:=1000}"
fi

# Helpers
num() { [[ "$1" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; }
fail() { echo "Error: $*" >&2; exit 3; }

# Required
[[ -n "${LOWER:-}" ]] || fail "LOWER missing (--lower)"
[[ -n "${UPPER:-}" ]] || fail "UPPER missing (--upper)"
[[ -n "${REF:-}"   ]] || fail "REF missing (--ref)"
[[ -n "${STEP:-}"  ]] || fail "STEP missing (--step)"

# Numeric checks
num "$LOWER" && num "$UPPER" && num "$REF" && num "$STEP" && num "$LOT" && num "$MAX_OPEN" || fail "All values must be numeric"

# bc check
if ! command -v bc >/dev/null 2>&1; then
  fail "'bc' is required (brew install bc)"
fi

# Order & positivity
(( $(echo "$STEP > 0" | bc -l) )) || fail "STEP must be > 0"
(( $(echo "$LOWER < $UPPER" | bc -l) )) || fail "LOWER must be < UPPER"
(( $(echo "$LOWER < $REF && $REF < $UPPER" | bc -l) )) || fail "REF must be strictly between LOWER and UPPER"

# Safety rails
MAX_WIDTH="${GRID_MAX_WIDTH:-10000}"
MAX_STEP_DELTA="${GRID_MAX_STEP_DELTA:-2000}"
MAX_LOT="${GRID_MAX_LOT:-5}"

WIDTH=$(echo "$UPPER - $LOWER" | bc -l)
(( $(echo "$WIDTH <= $MAX_WIDTH" | bc -l) )) || fail "Width $WIDTH exceeds MAX_WIDTH $MAX_WIDTH"
(( $(echo "$LOT <= $MAX_LOT" | bc -l) )) || fail "LOT $LOT exceeds MAX_LOT $MAX_LOT"

# Step delta guard (compare with OLD_STEP if available)
if [[ -n "${OLD_STEP}" ]]; then
  STEP_DELTA=$(echo "$STEP - $OLD_STEP" | bc -l)
  ABS_DELTA=$(echo "if ($STEP_DELTA < 0) -$STEP_DELTA else $STEP_DELTA" | bc -l)
  (( $(echo "$ABS_DELTA <= $MAX_STEP_DELTA" | bc -l) )) || fail "STEP change $ABS_DELTA exceeds MAX_STEP_DELTA $MAX_STEP_DELTA"
fi

# Atomic write
TMP="$(mktemp "${CFG}.XXXXXX")"
{
  echo "LOWER=$LOWER"
  echo "UPPER=$UPPER"
  echo "REF=$REF"
  echo "STEP=$STEP"
  echo "LOT=$LOT"
  echo "MAX_OPEN=$MAX_OPEN"
} > "$TMP"
mv "$TMP" "$CFG"

# Fingerprint
if command -v sha256sum >/dev/null 2>&1; then
  FP=$(sha256sum "$CFG" | awk '{print $1}')
else
  FP=$(shasum -a 256 "$CFG" | awk '{print $1}')
fi

echo "✅ grid_config.env updated atomically"
echo "   LOWER=$LOWER  REF=$REF  UPPER=$UPPER  STEP=$STEP  LOT=$LOT  MAX_OPEN=$MAX_OPEN"
echo "   fingerprint=$FP"
