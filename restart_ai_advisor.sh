#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# 🔄 AI Advisor Quick Restart
# ═══════════════════════════════════════════════════════════════════════════
#
# This script restarts the WebUI backend to activate AI Advisor changes
#
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  🔄 Restarting AI Advisor Backend                                       ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Stop existing backend
echo -e "${CYAN}▶${NC} Stopping existing backend..."
pkill -f "webui/backend/app.py" 2>/dev/null || echo "  No backend running"
sleep 2

# Step 2: Verify Ollama is running
echo -e "${CYAN}▶${NC} Checking Ollama service..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${GREEN}  ✅ Ollama is running${NC}"
else
    echo -e "${YELLOW}  ⚠️  Ollama not running - starting it...${NC}"
    ./start_ollama.sh start
fi

echo ""

# Step 3: Start backend
echo -e "${CYAN}▶${NC} Starting backend with new AI Advisor..."
nohup python3 webui/backend/app.py > webui_backend.log 2>&1 &
BACKEND_PID=$!

echo -e "${GREEN}  ✅ Backend started (PID: $BACKEND_PID)${NC}"
sleep 3

# Step 4: Test health endpoint
echo ""
echo -e "${CYAN}▶${NC} Testing AI health endpoint..."
RESPONSE=$(curl -s http://localhost:5555/api/ai/health 2>/dev/null)

if echo "$RESPONSE" | grep -q "ollama_status"; then
    OLLAMA_STATUS=$(echo "$RESPONSE" | grep -o '"ollama_status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$OLLAMA_STATUS" = "connected" ]; then
        echo -e "${GREEN}  ✅ AI Advisor ready! (Ollama connected)${NC}"
    else
        echo -e "${YELLOW}  ⚠️  AI Advisor ready (Fallback mode only)${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠️  Health endpoint responding (may need a moment to initialize)${NC}"
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Restart complete!${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo -e "  1. Open WebUI: ${YELLOW}http://localhost:5555${NC}"
echo -e "  2. Look for AI Advisor widget (bottom-right corner)"
echo -e "  3. Click to expand and test with: ${YELLOW}\"Why is trading stopped?\"${NC}"
echo ""
echo -e "${CYAN}View logs:${NC} ${YELLOW}tail -f webui_backend.log${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
