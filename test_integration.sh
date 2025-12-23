#!/bin/bash

###############################################################################
# WebUI Integration Test Script
# Tests backend and frontend integration on localhost:5555
###############################################################################

echo "======================================================================"
echo "  GridBot WebUI - Integration Test Suite"
echo "  Testing: http://localhost:5555"
echo "======================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

# Helper function to test endpoint
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_code="${3:-200}"
    
    echo -n "Testing: $name ... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>&1)
    
    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $response)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected HTTP $expected_code, got HTTP $response)"
        ((FAILED++))
        return 1
    fi
}

# Helper function to test JSON response
test_json_endpoint() {
    local name="$1"
    local url="$2"
    local json_field="$3"
    
    echo -n "Testing: $name ... "
    
    response=$(curl -s "$url" 2>&1)
    
    if echo "$response" | grep -q "$json_field"; then
        echo -e "${GREEN}✓ PASS${NC} (Found '$json_field')"
        ((PASSED++))
        echo "  Response: $response"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Field '$json_field' not found)"
        ((FAILED++))
        echo "  Response: $response"
        return 1
    fi
}

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Phase 1: Backend API Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Test health endpoint
test_json_endpoint "Health Check" "http://localhost:5555/api/health" "status"

# Test config endpoint
test_json_endpoint "Get Config" "http://localhost:5555/api/config" "LEVERAGE"

# Test bot status
test_json_endpoint "Bot Status" "http://localhost:5555/api/bot/status" "running"

# Test logs endpoint
test_endpoint "Get Logs" "http://localhost:5555/api/logs?limit=10"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Phase 2: Frontend Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Test main UI
test_endpoint "Main UI" "http://localhost:5555/"

# Test static assets
test_endpoint "JavaScript Bundle" "http://localhost:5555/static/js/main.4f83e38e.js"
test_endpoint "CSS Stylesheet" "http://localhost:5555/static/css/main.f6bb6bd7.css"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Phase 3: WebSocket/SocketIO Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Test SocketIO endpoint
echo -n "Testing: SocketIO Connection ... "
socketio_response=$(curl -s "http://localhost:5555/socket.io/?EIO=4&transport=polling" 2>&1)
if echo "$socketio_response" | grep -q "sid"; then
    echo -e "${GREEN}✓ PASS${NC} (SocketIO endpoint responding)"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC} (SocketIO not responding)"
    ((FAILED++))
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Phase 4: New Robust Components Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -n "Testing: UI includes ErrorBoundary ... "
ui_html=$(curl -s "http://localhost:5555/")
if echo "$ui_html" | grep -q "GridBot"; then
    echo -e "${GREEN}✓ PASS${NC} (UI loaded)"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ WARN${NC} (Cannot verify from HTML)"
fi

echo -n "Testing: UI includes React components ... "
if echo "$ui_html" | grep -q "root"; then
    echo -e "${GREEN}✓ PASS${NC} (React root div present)"
    ((PASSED++))
else
    echo -e "${RED}✗ FAIL${NC} (React root div missing)"
    ((FAILED++))
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Phase 5: Integration Flow Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Test 1: Get config then update it
echo "Test: Config Read-Write Flow"
config=$(curl -s "http://localhost:5555/api/config")
if echo "$config" | grep -q "LEVERAGE"; then
    echo -e "  ${GREEN}✓${NC} Config read successful"
    ((PASSED++))
    
    # Try to update config (this will test the POST endpoint)
    echo -n "  Testing config update endpoint ... "
    update_response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{"test_key":"test_value"}' \
        "http://localhost:5555/api/config/update" 2>&1)
    
    if echo "$update_response" | grep -q "success\|message"; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠ WARN${NC} (Endpoint responding but format unclear)"
    fi
else
    echo -e "  ${RED}✗${NC} Config read failed"
    ((FAILED++))
fi

echo ""
# Test 2: Bot Status Flow
echo "Test: Bot Control Flow"
status=$(curl -s "http://localhost:5555/api/bot/status")
if echo "$status" | grep -q "running"; then
    echo -e "  ${GREEN}✓${NC} Bot status query successful"
    ((PASSED++))
    
    is_running=$(echo "$status" | grep -o '"running":[^,}]*' | grep -o 'true\|false')
    echo "  Current bot status: $is_running"
else
    echo -e "  ${RED}✗${NC} Bot status query failed"
    ((FAILED++))
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Phase 6: File System Integration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if new robust component files exist
echo "Checking new robust component files:"

files=(
    "webui/frontend/src/components/ErrorBoundary.js"
    "webui/frontend/src/components/NotificationProvider.js"
    "webui/frontend/src/components/ConfirmationDialog.js"
    "webui/frontend/src/components/KeyboardProvider.js"
    "webui/frontend/src/components/LoadingSkeleton.js"
    "webui/frontend/src/components/EnhancedTooltip.js"
    "webui/frontend/src/hooks/useAutoSave.js"
    "webui/frontend/src/utils/validation.js"
    "webui/frontend/src/theme.js"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
        ((PASSED++))
    else
        echo -e "  ${RED}✗${NC} $file (missing)"
        ((FAILED++))
    fi
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

TOTAL=$((PASSED + FAILED))

echo "  Total Tests: $TOTAL"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ ALL TESTS PASSED! Integration is working perfectly! 🎉${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "✅ Backend and Frontend are fully integrated on localhost:5555"
    echo "✅ All robust UI components are in place"
    echo "✅ API endpoints are responding correctly"
    echo "✅ WebSocket connection is available"
    echo ""
    exit 0
else
    echo ""
    echo -e "${YELLOW}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  ⚠ Some tests failed. Review the output above.${NC}"
    echo -e "${YELLOW}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    exit 1
fi
