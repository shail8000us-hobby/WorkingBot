#!/bin/bash
# Test All Flask Blueprints
# Tests that all blueprints import successfully

set -e

echo "=========================================="
echo "Testing Flask API Refactoring"
echo "=========================================="
echo ""

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📦 Testing Individual Blueprints..."
echo ""

# Test each blueprint individually
blueprints=(
    "utility"
    "health"
    "logs"
    "docs"
    "metrics"
    "websocket_api"
    "system"
    "monitor"
    "guardian"
    "tmux"
    "orders"
    "pnl"
    "positions"
    "config"
    "bot_control"
)

failed=0
passed=0

for bp in "${blueprints[@]}"; do
    echo -n "Testing ${bp}_bp... "
    if python3 -c "from webui.backend.routes.${bp} import ${bp}_bp" 2>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((passed++))
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((failed++))
    fi
done

echo ""
echo "=========================================="
echo "Testing All Blueprints Together..."
echo "=========================================="

if python3 -c "from webui.backend.routes import *; print('All imports successful')" 2>/dev/null; then
    echo -e "${GREEN}✅ All blueprints import successfully!${NC}"
    ((passed++))
else
    echo -e "${RED}❌ Failed to import all blueprints together${NC}"
    ((failed++))
fi

echo ""
echo "=========================================="
echo "Testing Utilities..."
echo "=========================================="

utils=(
    "process_helpers"
    "file_helpers"
    "response_helpers"
)

for util in "${utils[@]}"; do
    echo -n "Testing ${util}... "
    if python3 -c "from webui.backend.utils.${util} import *" 2>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((passed++))
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((failed++))
    fi
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}${passed}${NC}"
echo -e "Failed: ${RED}${failed}${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Ready to deploy.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please check the errors above.${NC}"
    exit 1
fi
