#!/bin/bash
# Master development script - starts both backend and frontend with auto-reload

set -e

echo "🚀 Starting GridBot WebUI Development Environment"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Kill existing processes
echo -e "${YELLOW}🛑 Stopping existing processes...${NC}"

# Kill backend
if [ -f "$BACKEND_DIR/.webui_backend.pid" ]; then
    OLD_PID=$(cat "$BACKEND_DIR/.webui_backend.pid")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "   Stopping backend (PID: $OLD_PID)..."
        kill $OLD_PID 2>/dev/null || true
        sleep 1
    fi
    rm "$BACKEND_DIR/.webui_backend.pid"
fi

# Kill any process on port 5000 (backend)
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

# Kill any process on port 3000 (frontend)
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

sleep 2

echo -e "${GREEN}✅ Cleanup complete${NC}"
echo ""

# Start backend with auto-reload
echo -e "${BLUE}🔧 Starting Backend (Flask + SocketIO)${NC}"
echo "   📍 Port: 5000"
echo "   🔄 Auto-reload: ENABLED"
echo "   📝 Watching: *.py files"
echo ""

cd "$BACKEND_DIR"
export FLASK_ENV=development
export FLASK_DEBUG=1

# Start backend in background
python3 dev_server.py > backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > .webui_backend.pid

echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo "   📄 Logs: $BACKEND_DIR/backend.log"
echo ""

# Wait for backend to be ready
echo -e "${YELLOW}⏳ Waiting for backend to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠️  Backend health check timeout (continuing anyway)${NC}"
    fi
    sleep 1
done
echo ""

# Start frontend with hot reload
echo -e "${BLUE}⚛️  Starting Frontend (React)${NC}"
echo "   📍 Port: 3000"
echo "   🔄 Hot reload: ENABLED (built-in)"
echo "   🔌 Proxy: http://localhost:5000"
echo ""

cd "$FRONTEND_DIR"

# Start frontend in background
BROWSER=none npm start > frontend.log 2>&1 &
FRONTEND_PID=$!

echo -e "${GREEN}✅ Frontend started (PID: $FRONTEND_PID)${NC}"
echo "   📄 Logs: $FRONTEND_DIR/frontend.log"
echo ""

echo "=================================================="
echo -e "${GREEN}🎉 Development environment is ready!${NC}"
echo "=================================================="
echo ""
echo "📱 Frontend:  http://localhost:3000"
echo "🔧 Backend:   http://localhost:5000"
echo "📊 Health:    http://localhost:5000/health"
echo ""
echo "🔄 Auto-reload enabled for both:"
echo "   • Backend: Changes to .py files trigger restart"
echo "   • Frontend: Changes to .js/.jsx files hot-reload"
echo ""
echo "📝 Logs:"
echo "   • Backend:  tail -f $BACKEND_DIR/backend.log"
echo "   • Frontend: tail -f $FRONTEND_DIR/frontend.log"
echo ""
echo "🛑 To stop: Press Ctrl+C or run: kill $BACKEND_PID $FRONTEND_PID"
echo "=================================================="
echo ""

# Keep script running and forward signals
trap "echo ''; echo '🛑 Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for both processes
wait
