#!/bin/bash
# WebUI Performance Review Script
# Phase 11 — Monthly performance regression check
#
# Usage: ./scripts/performance-review.sh
#
# Runs all automated checks and produces a summary report.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  📊 WebUI Performance Review — $(date '+%B %Y')${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

ISSUES=0

# ---- 1. Bundle size budget ----
echo -e "${BLUE}▸ 1. Bundle Size Budget${NC}"
if "$SCRIPT_DIR/check-bundle-size.sh" 2>/dev/null; then
  echo ""
else
  ISSUES=$((ISSUES + 1))
  echo ""
fi

# ---- 2. Unused dependencies ----
echo -e "${BLUE}▸ 2. Unused Dependencies${NC}"
cd "$FRONTEND_DIR"
if command -v npx &>/dev/null; then
  DEPCHECK_JSON=$(npx depcheck --json 2>/dev/null) || DEPCHECK_JSON=""
  if [[ -n "$DEPCHECK_JSON" ]]; then
    UNUSED=$(echo "$DEPCHECK_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    deps = d.get('dependencies', [])
    if deps:
        print('\n'.join(['  ⚠️  ' + x for x in deps]))
    else:
        print('  ✅ No unused dependencies found')
except:
    print('  ⚠️  Could not parse depcheck output')
" 2>/dev/null)
    echo "$UNUSED"
    if echo "$UNUSED" | grep -q "⚠️"; then
      ISSUES=$((ISSUES + 1))
    fi
  else
    echo -e "  ${YELLOW}⚠️  depcheck not available (npm i -g depcheck)${NC}"
  fi
else
  echo -e "  ${YELLOW}⚠️  npx not available${NC}"
fi
echo ""

# ---- 3. Security audit ----
echo -e "${BLUE}▸ 3. Security Audit${NC}"
cd "$FRONTEND_DIR"
AUDIT_OUTPUT=$(npm audit --production 2>/dev/null | tail -5 || echo "audit failed")
if echo "$AUDIT_OUTPUT" | grep -q "found 0 vulnerabilities"; then
  echo -e "  ${GREEN}✅ No vulnerabilities found${NC}"
else
  echo "$AUDIT_OUTPUT" | head -8 | sed 's/^/  /'
  ISSUES=$((ISSUES + 1))
fi
echo ""

# ---- 4. TypeScript check ----
echo -e "${BLUE}▸ 4. TypeScript Errors${NC}"
cd "$FRONTEND_DIR"
TSC_OUTPUT=$(npx tsc --noEmit 2>&1 || true)
TSC_ERRORS=$(echo "$TSC_OUTPUT" | grep -c "error TS" 2>/dev/null || echo "0")
if [[ "$TSC_ERRORS" == "0" ]]; then
  echo -e "  ${GREEN}✅ No TypeScript errors${NC}"
else
  echo -e "  ${YELLOW}⚠️  $TSC_ERRORS TypeScript errors${NC}"
  ISSUES=$((ISSUES + 1))
fi
echo ""

# ---- 5. Large file check ----
echo -e "${BLUE}▸ 5. Large Source Files (>500 lines)${NC}"
cd "$FRONTEND_DIR/src"
LARGE_FILES=$(find . -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" | while read f; do
  lines=$(wc -l < "$f" | tr -d ' ')
  if [[ $lines -gt 500 ]]; then
    echo "  ⚠️  $f — $lines lines"
  fi
done)
if [[ -z "$LARGE_FILES" ]]; then
  echo -e "  ${GREEN}✅ All source files under 500 lines${NC}"
else
  echo "$LARGE_FILES"
fi
echo ""

# ---- Summary ----
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
if [[ $ISSUES -eq 0 ]]; then
  echo -e "${GREEN}  ✅ All checks passed — no performance regressions${NC}"
else
  echo -e "${YELLOW}  ⚠️  $ISSUES issue(s) found — review above${NC}"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
