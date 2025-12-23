#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# 🧪 AI Advisor Integration Test Suite
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

BACKEND_URL="http://localhost:5555"
TEST_RESULTS=()

print_header() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  🧪 ${BLUE}AI Advisor Integration Test Suite${NC}                                   ${CYAN}║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_test() {
    echo -e "${CYAN}▶ Test: $1${NC}"
}

print_pass() {
    echo -e "${GREEN}  ✅ PASS: $1${NC}"
    TEST_RESULTS+=("PASS: $1")
}

print_fail() {
    echo -e "${RED}  ❌ FAIL: $1${NC}"
    TEST_RESULTS+=("FAIL: $1")
}

print_info() {
    echo -e "${BLUE}  ℹ️  $1${NC}"
}

print_section() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 1: Ollama Status
# ═══════════════════════════════════════════════════════════════════════════

test_ollama_status() {
    print_test "Ollama Service Status"
    
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        print_pass "Ollama service is running"
        
        # Check for model
        MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | head -1)
        if [ -n "$MODELS" ]; then
            print_pass "Model available: $MODELS"
        else
            print_fail "No models found"
        fi
    else
        print_fail "Ollama service is not running"
        print_info "Start with: ./start_ollama.sh start"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 2: Backend Status
# ═══════════════════════════════════════════════════════════════════════════

test_backend_status() {
    print_test "WebUI Backend Status"
    
    if curl -s "${BACKEND_URL}/health" >/dev/null 2>&1; then
        print_pass "Backend is running on port 5555"
    else
        print_fail "Backend is not responding"
        print_info "Start backend: python3 webui/backend/app.py &"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 3: Health Endpoint
# ═══════════════════════════════════════════════════════════════════════════

test_health_endpoint() {
    print_test "AI Health Endpoint"
    
    RESPONSE=$(curl -s "${BACKEND_URL}/api/ai/health" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$RESPONSE" ]; then
        print_pass "Health endpoint is accessible"
        
        # Parse response
        if echo "$RESPONSE" | grep -q "ollama_status"; then
            print_pass "Health endpoint returns valid data"
            
            OLLAMA_STATUS=$(echo "$RESPONSE" | grep -o '"ollama_status":"[^"]*"' | cut -d'"' -f4)
            print_info "Ollama Status: $OLLAMA_STATUS"
            
            if [ "$OLLAMA_STATUS" = "connected" ]; then
                print_pass "Ollama is connected"
            else
                print_fail "Ollama is not connected"
            fi
        else
            print_fail "Health endpoint returns invalid data"
        fi
    else
        print_fail "Health endpoint not found"
        print_info "Backend may need to be restarted with new code"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 4: AI Ask Endpoint
# ═══════════════════════════════════════════════════════════════════════════

test_ask_endpoint() {
    print_test "AI Ask Endpoint"
    
    RESPONSE=$(curl -s -X POST "${BACKEND_URL}/api/ai/ask" \
        -H "Content-Type: application/json" \
        -d '{"question": "test"}' 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$RESPONSE" ]; then
        print_pass "Ask endpoint is accessible"
        
        # Check for answer
        if echo "$RESPONSE" | grep -q "answer"; then
            print_pass "Ask endpoint returns answer"
            
            # Check source
            SOURCE=$(echo "$RESPONSE" | grep -o '"source":"[^"]*"' | cut -d'"' -f4)
            if [ -n "$SOURCE" ]; then
                print_pass "Response includes source: $SOURCE"
            fi
        else
            print_fail "Ask endpoint returns invalid data"
        fi
    else
        print_fail "Ask endpoint not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Fallback System
# ═══════════════════════════════════════════════════════════════════════════

test_fallback_system() {
    print_test "Fallback System"
    
    # Check if rule-based advisor works
    if [ -f "bot/ai/advisor.py" ]; then
        print_pass "Rule-based advisor exists"
        
        # Test import
        python3 -c "from bot.ai.advisor import get_ai_advisor" 2>/dev/null
        if [ $? -eq 0 ]; then
            print_pass "Rule-based advisor can be imported"
        else
            print_fail "Rule-based advisor has import errors"
        fi
    else
        print_fail "Rule-based advisor not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 6: Intelligent Advisor
# ═══════════════════════════════════════════════════════════════════════════

test_intelligent_advisor() {
    print_test "Intelligent Advisor"
    
    if [ -f "bot/ai/conversational/intelligent_advisor.py" ]; then
        print_pass "Intelligent advisor exists"
        
        # Test import
        python3 -c "from bot.ai.conversational.intelligent_advisor import get_intelligent_advisor" 2>/dev/null
        if [ $? -eq 0 ]; then
            print_pass "Intelligent advisor can be imported"
        else
            print_fail "Intelligent advisor has import errors"
        fi
    else
        print_fail "Intelligent advisor not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 7: Configuration
# ═══════════════════════════════════════════════════════════════════════════

test_configuration() {
    print_test "AI Configuration"
    
    if grep -q "AI_ADVISOR_ENABLED" grid_config.env 2>/dev/null; then
        print_pass "AI configuration found in grid_config.env"
        
        # Check key settings
        if grep -q "OLLAMA_URL" grid_config.env; then
            print_pass "Ollama URL configured"
        fi
        
        if grep -q "OLLAMA_MODEL" grid_config.env; then
            MODEL=$(grep "OLLAMA_MODEL" grid_config.env | head -1 | cut -d'=' -f2)
            print_pass "Ollama model configured: $MODEL"
        fi
    else
        print_fail "AI configuration not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Test 8: Startup Script
# ═══════════════════════════════════════════════════════════════════════════

test_startup_script() {
    print_test "Startup Script"
    
    if [ -f "start_ollama.sh" ]; then
        print_pass "start_ollama.sh exists"
        
        if [ -x "start_ollama.sh" ]; then
            print_pass "start_ollama.sh is executable"
        else
            print_fail "start_ollama.sh is not executable"
            print_info "Fix with: chmod +x start_ollama.sh"
        fi
    else
        print_fail "start_ollama.sh not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Run All Tests
# ═══════════════════════════════════════════════════════════════════════════

run_all_tests() {
    print_header
    
    print_section "1️⃣  Ollama Service Tests"
    test_ollama_status
    
    print_section "2️⃣  Backend Tests"
    test_backend_status
    
    print_section "3️⃣  API Endpoint Tests"
    test_health_endpoint
    test_ask_endpoint
    
    print_section "4️⃣  Advisor Module Tests"
    test_fallback_system
    test_intelligent_advisor
    
    print_section "5️⃣  Configuration Tests"
    test_configuration
    
    print_section "6️⃣  Tool Tests"
    test_startup_script
    
    # Summary
    print_section "📊 Test Summary"
    
    TOTAL=${#TEST_RESULTS[@]}
    PASSED=$(echo "${TEST_RESULTS[@]}" | grep -o "PASS" | wc -l | tr -d ' ')
    FAILED=$(echo "${TEST_RESULTS[@]}" | grep -o "FAIL" | wc -l | tr -d ' ')
    
    echo -e "Total Tests:  ${CYAN}$TOTAL${NC}"
    echo -e "Passed:       ${GREEN}$PASSED${NC}"
    echo -e "Failed:       ${RED}$FAILED${NC}"
    echo ""
    
    if [ "$FAILED" -eq 0 ]; then
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║${NC}  🎉 ${GREEN}ALL TESTS PASSED! AI Advisor is ready!${NC}                             ${GREEN}║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║${NC}  ⚠️  ${YELLOW}Some tests failed. Review above for details.${NC}                       ${YELLOW}║${NC}"
        echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${CYAN}Quick Fixes:${NC}"
        echo -e "  • Restart backend: ${YELLOW}pkill -f 'webui/backend/app.py' && python3 webui/backend/app.py &${NC}"
        echo -e "  • Start Ollama:    ${YELLOW}./start_ollama.sh start${NC}"
    fi
}

# Run tests
run_all_tests
