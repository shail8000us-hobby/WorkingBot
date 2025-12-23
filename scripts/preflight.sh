#!/usr/bin/env bash
# Preflight checks: run before deployment
# Note: We don't use 'set -e' because we want to collect all failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              GridBot Pre-Flight Checks                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

check() {
    local name="$1"
    local cmd="$2"
    
    printf "%-50s" "$name"
    
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}[PASS]${NC}"
        ((PASS++))
        return 0
    else
        echo -e "${RED}[FAIL]${NC}"
        ((FAIL++))
        return 1
    fi
}

warn_check() {
    local name="$1"
    local cmd="$2"
    
    printf "%-50s" "$name"
    
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}[PASS]${NC}"
        ((PASS++))
    else
        echo -e "${YELLOW}[WARN]${NC}"
        ((WARN++))
    fi
}

# ═══════════════════════════════════════════════════════════════════
echo "📦 Dependencies"
echo "───────────────────────────────────────────────────────────────"
check "Python 3.8+" "python3 --version"
check "pip available" "pip3 --version"
warn_check "Node.js available" "node --version"
warn_check "npm available" "npm --version"
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "📁 Project Structure"
echo "───────────────────────────────────────────────────────────────"
check "grid_config.env exists" "test -f grid_config.env"
check "webui/backend/app.py exists" "test -f webui/backend/app.py"
check "webui/frontend exists" "test -d webui/frontend"
warn_check "Frontend built" "test -d webui/frontend/build"
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "🔐 Security"
echo "───────────────────────────────────────────────────────────────"
check "secrets/ in .gitignore" "grep -q '^secrets/' .gitignore"
check "secrets/ not tracked by git" "! git ls-files | grep -q '^secrets/'"
check ".env.local in .gitignore" "grep -q '.env.local' .gitignore"

# Check if auth is enabled
if grep -q "^@app.before_request" webui/backend/app.py && \
   grep -A1 "^@app.before_request" webui/backend/app.py | grep -q "def enforce_api_auth"; then
    printf "%-50s${GREEN}[PASS]${NC}\n" "API authentication enabled"
    ((PASS++))
else
    printf "%-50s${RED}[FAIL]${NC}\n" "API authentication enabled"
    ((FAIL++))
fi

warn_check "WEBUI_AUTH_TOKEN set" "test -n \"$WEBUI_AUTH_TOKEN\""
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "🧪 Python Tests"
echo "───────────────────────────────────────────────────────────────"
warn_check "Import webui.backend.app" "python3 -c 'import webui.backend.app' 2>/dev/null"
warn_check "Import bot.grid_main" "python3 -c 'import bot.grid_main' 2>/dev/null"

# Run unit tests if pytest available
if command -v pytest > /dev/null 2>&1; then
    printf "%-50s" "Unit tests (pytest)"
    if pytest tests/ -q --tb=no > /dev/null 2>&1; then
        echo -e "${GREEN}[PASS]${NC}"
        ((PASS++))
    else
        echo -e "${YELLOW}[WARN]${NC}"
        ((WARN++))
    fi
else
    printf "%-50s${YELLOW}[SKIP]${NC}\n" "Unit tests (pytest not installed)"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "🔌 API Endpoint Checks"
echo "───────────────────────────────────────────────────────────────"

# Check that critical endpoints exist in code
ENDPOINTS=(
    "/api/health"
    "/api/version"
    "/api/bot/start"
    "/api/bot/stop"
    "/api/bot/restart"
    "/api/config"
    "/api/config/verify"
    "/api/config/apply"
    "/api/logs/recent"
    "/api/system/status"
    "/api/positions"
    "/api/emergency/kill-all"
)

for endpoint in "${ENDPOINTS[@]}"; do
    name="Endpoint '$endpoint' defined"
    check "$name" "grep -q \"@app.route('$endpoint\" webui/backend/app.py"
done
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "🔄 SocketIO Events"
echo "───────────────────────────────────────────────────────────────"

# Check backend emits
BACKEND_EVENTS=(
    "bot_status"
    "positions_update"
    "liquidation_alert"
    "liquidation_update"
    "fix_result"
)

for event in "${BACKEND_EVENTS[@]}"; do
    name="Backend emits '$event'"
    check "$name" "grep -rq \"socketio.emit('$event'\" webui/backend/ || grep -rq \"socketio_instance.emit('$event'\" webui/backend/"
done

# Check frontend listeners
FRONTEND_EVENTS=(
    "liquidation_alert"
    "liquidation_update"
    "fix_result"
)

for event in "${FRONTEND_EVENTS[@]}"; do
    name="Frontend listens '$event'"
    if [ -f "webui/frontend/src/utils/connectionManager.js" ]; then
        check "$name" "grep -q \"socket.on('$event'\" webui/frontend/src/utils/connectionManager.js"
    else
        printf "%-50s${YELLOW}[SKIP]${NC}\n" "$name"
    fi
done
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "🛡️  Rate Limiting"
echo "───────────────────────────────────────────────────────────────"
check "Rate limit decorator defined" "grep -q 'def rate_limit' webui/backend/app.py"
check "/api/bot/start rate limited" "grep -B1 'def bot_start' webui/backend/app.py | grep -q '@rate_limit'"
check "/api/bot/stop rate limited" "grep -B1 'def bot_stop' webui/backend/app.py | grep -q '@rate_limit'"
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "📋 Documentation"
echo "───────────────────────────────────────────────────────────────"
check "README.md exists" "test -f README.md"
check "SECURITY.md exists" "test -f SECURITY.md"
check "RUNBOOK.md exists" "test -f RUNBOOK.md"
check "SECRETS_SETUP.md exists" "test -f SECRETS_SETUP.md"
check "grid_config.env.example exists" "test -f grid_config.env.example"
echo ""

# ═══════════════════════════════════════════════════════════════════
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                        Summary                                ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${GREEN}PASS:${NC} $PASS"
echo -e "  ${YELLOW}WARN:${NC} $WARN"
echo -e "  ${RED}FAIL:${NC} $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ All critical checks passed!${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ $FAIL critical check(s) failed!${NC}"
    echo ""
    echo "Fix failures before deploying to production."
    exit 1
fi
