#!/bin/bash
# Backend/Frontend Sync & Restart Script
# Ensures backend and frontend are properly configured and running

set -e

PROJECT_ROOT="/Users/ssr/Projects/WorkingBot"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

BACKEND_PORT=5555
FRONTEND_DEV_PORT=3000

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🔄 Backend/Frontend Sync Tool${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Function to check if port is in use
check_port() {
    lsof -ti:$1 2>/dev/null
}

# Function to kill process on port
kill_port() {
    local port=$1
    local pids=$(check_port $port)
    if [ ! -z "$pids" ]; then
        echo -e "${YELLOW}  Killing process(es) on port $port: $pids${NC}"
        kill -9 $pids 2>/dev/null || true
        sleep 1
    fi
}

# Check current status
echo -e "${CYAN}1️⃣  Checking Current Status...${NC}"
echo ""

# Check backend
if check_port $BACKEND_PORT > /dev/null; then
    echo -e "${GREEN}  ✅ Backend running on port $BACKEND_PORT${NC}"
    BACKEND_RUNNING=true
else
    echo -e "${YELLOW}  ⚠️  Backend NOT running on port $BACKEND_PORT${NC}"
    BACKEND_RUNNING=false
fi

# Check frontend dev server
if check_port $FRONTEND_DEV_PORT > /dev/null; then
    echo -e "${GREEN}  ✅ Frontend dev server running on port $FRONTEND_DEV_PORT${NC}"
    FRONTEND_RUNNING=true
else
    echo -e "${YELLOW}  ⚠️  Frontend dev server NOT running on port $FRONTEND_DEV_PORT${NC}"
    FRONTEND_RUNNING=false
fi

# Check LaunchAgent
if launchctl list | grep -q "com.gridbot.webui"; then
    echo -e "${GREEN}  ✅ LaunchAgent registered${NC}"
    LAUNCHAGENT_REGISTERED=true
else
    echo -e "${YELLOW}  ⚠️  LaunchAgent NOT registered${NC}"
    LAUNCHAGENT_REGISTERED=false
fi

echo ""
echo -e "${CYAN}2️⃣  Select Operation:${NC}"
echo ""
echo "  ${YELLOW}Development Mode:${NC}"
echo "    1) Start Backend (LaunchAgent) + Frontend Dev Server"
echo "    2) Stop Everything"
echo "    3) Restart Backend Only"
echo "    4) Restart Frontend Dev Server Only"
echo ""
echo "  ${YELLOW}Production Mode:${NC}"
echo "    5) Build Frontend + Restart Backend (Production)"
echo "    6) Rebuild Frontend Only"
echo ""
echo "  ${YELLOW}Fix Issues:${NC}"
echo "    7) Fix Port Conflicts (kill all on 5555 & 3000)"
echo "    8) Full Reset (stop all, rebuild, restart)"
echo ""
echo "  ${YELLOW}Status:${NC}"
echo "    9) Check Status & Test Endpoints"
echo "    0) Exit"
echo ""
read -p "Enter choice [0-9]: " choice

case $choice in
    1)
        echo -e "${CYAN}3️⃣  Starting Development Mode...${NC}"
        echo ""
        
        # Stop any conflicts
        echo -e "${YELLOW}  Stopping conflicting processes...${NC}"
        pkill -f "react-app-rewired" 2>/dev/null || true
        
        # Start backend via LaunchAgent
        echo -e "${YELLOW}  Starting backend (LaunchAgent)...${NC}"
        launchctl stop com.gridbot.webui 2>/dev/null || true
        sleep 1
        launchctl start com.gridbot.webui
        sleep 2
        
        # Verify backend
        if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Backend started on http://localhost:$BACKEND_PORT${NC}"
        else
            echo -e "${RED}  ❌ Backend failed to start! Check logs: tail -f logs/launchagent_webui_error.log${NC}"
            exit 1
        fi
        
        # Start frontend dev server
        echo -e "${YELLOW}  Starting frontend dev server...${NC}"
        cd webui/frontend
        npm start &
        FRONTEND_PID=$!
        cd ../..
        
        echo -e "${GREEN}  ✅ Frontend dev server starting on http://localhost:$FRONTEND_DEV_PORT${NC}"
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}  🎉 Development Mode Active!${NC}"
        echo ""
        echo -e "  Backend:  ${CYAN}http://localhost:$BACKEND_PORT${NC}"
        echo -e "  Frontend: ${CYAN}http://localhost:$FRONTEND_DEV_PORT${NC}"
        echo ""
        echo -e "  ${YELLOW}Logs:${NC}"
        echo -e "    Backend:  tail -f logs/launchagent_webui.log"
        echo -e "    Frontend: (showing in this terminal)"
        echo ""
        echo -e "  ${YELLOW}To stop:${NC} ./sync_backend_frontend.sh (choose option 2)"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        ;;
        
    2)
        echo -e "${CYAN}3️⃣  Stopping Everything...${NC}"
        echo ""
        
        echo -e "${YELLOW}  Stopping backend...${NC}"
        launchctl stop com.gridbot.webui 2>/dev/null || true
        
        echo -e "${YELLOW}  Stopping frontend dev server...${NC}"
        pkill -f "react-app-rewired" 2>/dev/null || true
        
        # Wait for ports to be released
        sleep 2
        
        # Verify
        if ! check_port $BACKEND_PORT > /dev/null && ! check_port $FRONTEND_DEV_PORT > /dev/null; then
            echo -e "${GREEN}  ✅ All services stopped${NC}"
        else
            echo -e "${YELLOW}  ⚠️  Some processes may still be running. Use option 7 to force kill.${NC}"
        fi
        ;;
        
    3)
        echo -e "${CYAN}3️⃣  Restarting Backend...${NC}"
        echo ""
        
        launchctl stop com.gridbot.webui 2>/dev/null || true
        sleep 1
        launchctl start com.gridbot.webui
        sleep 2
        
        if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Backend restarted successfully${NC}"
        else
            echo -e "${RED}  ❌ Backend failed to start!${NC}"
        fi
        ;;
        
    4)
        echo -e "${CYAN}3️⃣  Restarting Frontend Dev Server...${NC}"
        echo ""
        
        echo -e "${YELLOW}  Stopping frontend...${NC}"
        pkill -f "react-app-rewired" 2>/dev/null || true
        sleep 1
        
        echo -e "${YELLOW}  Starting frontend...${NC}"
        cd webui/frontend
        npm start &
        cd ../..
        
        echo -e "${GREEN}  ✅ Frontend dev server starting on http://localhost:$FRONTEND_DEV_PORT${NC}"
        ;;
        
    5)
        echo -e "${CYAN}3️⃣  Production Mode: Building Frontend + Restarting Backend...${NC}"
        echo ""
        
        # Stop services
        echo -e "${YELLOW}  Stopping services...${NC}"
        launchctl stop com.gridbot.webui 2>/dev/null || true
        pkill -f "react-app-rewired" 2>/dev/null || true
        sleep 1
        
        # Build frontend
        echo -e "${YELLOW}  Building frontend (this may take a minute)...${NC}"
        cd webui/frontend
        npm run build
        cd ../..
        
        # Start backend
        echo -e "${YELLOW}  Starting backend...${NC}"
        launchctl start com.gridbot.webui
        sleep 2
        
        if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Production mode active!${NC}"
            echo ""
            echo -e "  Access at: ${CYAN}http://localhost:$BACKEND_PORT${NC}"
            echo -e "  (Backend serves pre-built React app)"
        else
            echo -e "${RED}  ❌ Backend failed to start!${NC}"
        fi
        ;;
        
    6)
        echo -e "${CYAN}3️⃣  Rebuilding Frontend...${NC}"
        echo ""
        
        cd webui/frontend
        echo -e "${YELLOW}  Building frontend (this may take a minute)...${NC}"
        npm run build
        cd ../..
        
        echo -e "${GREEN}  ✅ Frontend rebuilt!${NC}"
        echo -e "  Restart backend to serve new build: launchctl restart com.gridbot.webui"
        ;;
        
    7)
        echo -e "${CYAN}3️⃣  Fixing Port Conflicts...${NC}"
        echo ""
        
        echo -e "${YELLOW}  Killing all processes on port $BACKEND_PORT...${NC}"
        kill_port $BACKEND_PORT
        
        echo -e "${YELLOW}  Killing all processes on port $FRONTEND_DEV_PORT...${NC}"
        kill_port $FRONTEND_DEV_PORT
        
        echo -e "${GREEN}  ✅ Ports cleared!${NC}"
        echo ""
        echo -e "  Now you can start services with option 1 or 5"
        ;;
        
    8)
        echo -e "${CYAN}3️⃣  Full Reset...${NC}"
        echo ""
        
        # Stop everything
        echo -e "${YELLOW}  Stopping all services...${NC}"
        launchctl stop com.gridbot.webui 2>/dev/null || true
        pkill -f "react-app-rewired" 2>/dev/null || true
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_DEV_PORT
        sleep 1
        
        # Rebuild frontend
        echo -e "${YELLOW}  Rebuilding frontend...${NC}"
        cd webui/frontend
        npm run build
        cd ../..
        
        # Restart backend
        echo -e "${YELLOW}  Starting backend...${NC}"
        launchctl start com.gridbot.webui
        sleep 2
        
        if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Full reset complete!${NC}"
            echo ""
            echo -e "  Access at: ${CYAN}http://localhost:$BACKEND_PORT${NC}"
        else
            echo -e "${RED}  ❌ Backend failed to start!${NC}"
        fi
        ;;
        
    9)
        echo -e "${CYAN}3️⃣  Checking Status & Testing Endpoints...${NC}"
        echo ""
        
        # Backend status
        echo -e "${YELLOW}Backend (port $BACKEND_PORT):${NC}"
        if check_port $BACKEND_PORT > /dev/null; then
            echo -e "  ${GREEN}✅ Process running${NC}"
            
            # Test health endpoint
            if response=$(curl -s http://localhost:$BACKEND_PORT/api/health 2>&1); then
                echo -e "  ${GREEN}✅ Health endpoint OK${NC}"
                echo "     Response: $response"
            else
                echo -e "  ${RED}❌ Health endpoint failed${NC}"
            fi
        else
            echo -e "  ${RED}❌ Not running${NC}"
        fi
        
        echo ""
        
        # Frontend status
        echo -e "${YELLOW}Frontend Dev Server (port $FRONTEND_DEV_PORT):${NC}"
        if check_port $FRONTEND_DEV_PORT > /dev/null; then
            echo -e "  ${GREEN}✅ Running${NC}"
        else
            echo -e "  ${YELLOW}⚠️  Not running (normal in production mode)${NC}"
        fi
        
        echo ""
        
        # LaunchAgent status
        echo -e "${YELLOW}LaunchAgent:${NC}"
        if launchctl list | grep -q "com.gridbot.webui"; then
            echo -e "  ${GREEN}✅ Registered${NC}"
        else
            echo -e "  ${RED}❌ Not registered${NC}"
        fi
        
        echo ""
        
        # Configuration check
        echo -e "${YELLOW}Configuration:${NC}"
        
        # Check backend port
        if grep -q "port=5555" webui/backend/app.py; then
            echo -e "  ${GREEN}✅ Backend configured for port 5555${NC}"
        else
            echo -e "  ${RED}❌ Backend port misconfigured${NC}"
        fi
        
        # Check frontend proxy
        if grep -q '"proxy": "http://localhost:5555"' webui/frontend/package.json; then
            echo -e "  ${GREEN}✅ Frontend proxy configured${NC}"
        else
            echo -e "  ${RED}❌ Frontend proxy misconfigured${NC}"
        fi
        
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        ;;
        
    0)
        echo -e "${GREEN}Exiting...${NC}"
        exit 0
        ;;
        
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
