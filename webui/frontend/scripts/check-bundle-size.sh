#!/bin/bash
# Bundle Size Budget Enforcement
# Phase 10.4 — Prevents bundle size regressions
#
# Usage:
#   ./scripts/check-bundle-size.sh           # Check existing build
#   ./scripts/check-bundle-size.sh --build   # Build first, then check
#
# Budget baselines (as of March 2026, post-Phase 12+9):
#   Main bundle:   150KB raw / 43KB gzipped
#   Vendor chunk:  ~485KB raw / ~149KB gzipped
#   Total JS:      <1,400KB raw
#   Chunk count:   ~74 files (67 lazy chunks + runtime + main + vendors)

set -euo pipefail

# ---- Configuration ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$FRONTEND_DIR/build/static/js"

# Budget limits (in bytes, raw uncompressed)
# Baselines measured March 2026 post-Phase 12+9:
#   Main: 150KB raw / 42KB gz | Largest chunk: 781KB | Total: 3,770KB / 74 files
MAIN_BUDGET=200000      # 200KB raw — 33% headroom over current 150KB
VENDOR_BUDGET=1000000   # 1MB raw — 28% headroom over current 781KB (common chunk includes shared code)
TOTAL_BUDGET=5000000    # 5MB raw total JS — 33% headroom over current 3.77MB (74 lazy chunks)
MAIN_GZ_BUDGET=60000    # 60KB gzipped main — 43% headroom over current 42KB

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---- Build if requested ----
if [[ "${1:-}" == "--build" ]]; then
  echo -e "${BLUE}📦 Building frontend...${NC}"
  cd "$FRONTEND_DIR" && npm run build 2>&1 | tail -5
  echo ""
fi

# ---- Verify build exists ----
if [[ ! -d "$BUILD_DIR" ]]; then
  echo -e "${RED}❌ No build directory found at $BUILD_DIR${NC}"
  echo "   Run: npm run build (or use --build flag)"
  exit 1
fi

# ---- Measure sizes ----
MAIN_FILE=$(ls "$BUILD_DIR"/main.*.js 2>/dev/null | head -1)
VENDOR_FILE=$(ls "$BUILD_DIR"/*chunk.js 2>/dev/null | sort -k5 -t' ' -rn | head -1)

if [[ -z "$MAIN_FILE" ]]; then
  echo -e "${RED}❌ No main.*.js found in build${NC}"
  exit 1
fi

MAIN_SIZE=$(wc -c < "$MAIN_FILE" | tr -d ' ')
MAIN_GZ_SIZE=$(gzip -c "$MAIN_FILE" | wc -c | tr -d ' ')

# Find the vendor/largest chunk
VENDOR_SIZE=0
VENDOR_NAME="(none)"
for f in "$BUILD_DIR"/*.chunk.js; do
  sz=$(wc -c < "$f" | tr -d ' ')
  if [[ $sz -gt $VENDOR_SIZE ]]; then
    VENDOR_SIZE=$sz
    VENDOR_NAME=$(basename "$f")
  fi
done

# Total JS size
TOTAL_SIZE=0
FILE_COUNT=0
for f in "$BUILD_DIR"/*.js; do
  sz=$(wc -c < "$f" | tr -d ' ')
  TOTAL_SIZE=$((TOTAL_SIZE + sz))
  FILE_COUNT=$((FILE_COUNT + 1))
done

# ---- Display results ----
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  📊 Bundle Size Report${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

FAILED=0

# Main bundle
MAIN_KB=$((MAIN_SIZE / 1024))
MAIN_GZ_KB=$((MAIN_GZ_SIZE / 1024))
MAIN_BUDGET_KB=$((MAIN_BUDGET / 1024))
MAIN_GZ_BUDGET_KB=$((MAIN_GZ_BUDGET / 1024))
if [[ $MAIN_SIZE -gt $MAIN_BUDGET ]]; then
  echo -e "  ${RED}❌ Main bundle:  ${MAIN_KB}KB raw (budget: ${MAIN_BUDGET_KB}KB)${NC}"
  FAILED=1
else
  PERCENT=$((MAIN_SIZE * 100 / MAIN_BUDGET))
  echo -e "  ${GREEN}✅ Main bundle:  ${MAIN_KB}KB raw / ${MAIN_GZ_KB}KB gz  (${PERCENT}% of ${MAIN_BUDGET_KB}KB budget)${NC}"
fi

# Main gzipped
if [[ $MAIN_GZ_SIZE -gt $MAIN_GZ_BUDGET ]]; then
  echo -e "  ${RED}❌ Main gzipped: ${MAIN_GZ_KB}KB (budget: ${MAIN_GZ_BUDGET_KB}KB)${NC}"
  FAILED=1
else
  GZ_PERCENT=$((MAIN_GZ_SIZE * 100 / MAIN_GZ_BUDGET))
  echo -e "  ${GREEN}✅ Main gzipped: ${MAIN_GZ_KB}KB  (${GZ_PERCENT}% of ${MAIN_GZ_BUDGET_KB}KB budget)${NC}"
fi

# Vendor/largest chunk
VENDOR_KB=$((VENDOR_SIZE / 1024))
VENDOR_BUDGET_KB=$((VENDOR_BUDGET / 1024))
if [[ $VENDOR_SIZE -gt $VENDOR_BUDGET ]]; then
  echo -e "  ${RED}❌ Largest chunk: ${VENDOR_KB}KB — $VENDOR_NAME (budget: ${VENDOR_BUDGET_KB}KB)${NC}"
  FAILED=1
else
  V_PERCENT=$((VENDOR_SIZE * 100 / VENDOR_BUDGET))
  echo -e "  ${GREEN}✅ Largest chunk: ${VENDOR_KB}KB — $VENDOR_NAME  (${V_PERCENT}% of ${VENDOR_BUDGET_KB}KB budget)${NC}"
fi

# Total
TOTAL_KB=$((TOTAL_SIZE / 1024))
TOTAL_BUDGET_KB=$((TOTAL_BUDGET / 1024))
if [[ $TOTAL_SIZE -gt $TOTAL_BUDGET ]]; then
  echo -e "  ${RED}❌ Total JS:     ${TOTAL_KB}KB across $FILE_COUNT files (budget: ${TOTAL_BUDGET_KB}KB)${NC}"
  FAILED=1
else
  T_PERCENT=$((TOTAL_SIZE * 100 / TOTAL_BUDGET))
  echo -e "  ${GREEN}✅ Total JS:     ${TOTAL_KB}KB across $FILE_COUNT files  (${T_PERCENT}% of ${TOTAL_BUDGET_KB}KB budget)${NC}"
fi

echo ""

# ---- Summary ----
if [[ $FAILED -eq 1 ]]; then
  echo -e "${RED}══════════════════════════════════════════════════${NC}"
  echo -e "${RED}  ❌ BUDGET EXCEEDED — investigate before deploying${NC}"
  echo -e "${RED}══════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "  ${YELLOW}Tips:${NC}"
  echo "  • Run 'npm run analyze' to identify large modules"
  echo "  • Run 'npx depcheck' to find unused dependencies"
  echo "  • Check if new dependencies added unnecessary weight"
  echo ""
  exit 1
else
  echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}  ✅ All bundle sizes within budget${NC}"
  echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
  exit 0
fi
