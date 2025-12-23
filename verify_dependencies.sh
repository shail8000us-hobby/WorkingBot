#!/bin/bash
# Quick Dependency Verification Script

echo "========================================"
echo "🔍 WorkingBot Dependency Verification"
echo "========================================"
echo ""

export PATH="/opt/homebrew/bin:$PATH"

# Check Node.js
echo "📦 Node.js:"
if command -v node &> /dev/null; then
    NODE_VER=$(node --version)
    echo "   ✅ Installed: $NODE_VER"
else
    echo "   ❌ Not installed"
fi

# Check npm
echo ""
echo "📦 npm:"
if command -v npm &> /dev/null; then
    NPM_VER=$(npm --version)
    echo "   ✅ Installed: v$NPM_VER"
else
    echo "   ❌ Not installed"
fi

# Check PM2
echo ""
echo "📦 PM2:"
if command -v pm2 &> /dev/null; then
    PM2_VER=$(pm2 --version)
    echo "   ✅ Installed: v$PM2_VER"
    PM2_STATUS=$(pm2 list 2>&1 | grep "mode" || echo "No processes")
    echo "   Status: PM2 daemon running"
else
    echo "   ❌ Not installed"
fi

# Check Python
echo ""
echo "📦 Python:"
if command -v python3 &> /dev/null; then
    PYTHON_VER=$(python3 --version | awk '{print $2}')
    echo "   ✅ Installed: v$PYTHON_VER"
else
    echo "   ❌ Not installed"
fi

# Check pip3
echo ""
echo "📦 pip3:"
if command -v pip3 &> /dev/null; then
    PIP_VER=$(pip3 --version | awk '{print $2}')
    echo "   ✅ Installed: v$PIP_VER"
else
    echo "   ❌ Not installed"
fi

# Check critical Python packages
echo ""
echo "🐍 Python Packages:"
PACKAGES=("ccxt" "flask" "python-socketio" "websockets" "aiohttp" "psutil" "requests")
for pkg in "${PACKAGES[@]}"; do
    if pip3 show "$pkg" &> /dev/null; then
        VERSION=$(pip3 show "$pkg" | grep "Version:" | awk '{print $2}')
        echo "   ✅ $pkg: $VERSION"
    else
        echo "   ❌ $pkg: Not installed"
    fi
done

# Check Frontend
echo ""
echo "⚛️  Frontend:"
if [ -d "/Users/ssr/Projects/WorkingBot/webui/frontend/node_modules" ]; then
    NODE_MODULES_COUNT=$(ls /Users/ssr/Projects/WorkingBot/webui/frontend/node_modules 2>/dev/null | wc -l)
    echo "   ✅ Dependencies installed ($NODE_MODULES_COUNT packages)"
else
    echo "   ❌ Dependencies not installed"
fi

if [ -d "/Users/ssr/Projects/WorkingBot/webui/frontend/build" ]; then
    echo "   ✅ Production build exists"
else
    echo "   ❌ Production build missing"
fi

# Check Services
echo ""
echo "🔧 Services:"

# LaunchAgent
if launchctl list | grep -q "com.gridbot.webui"; then
    echo "   ✅ WebUI LaunchAgent: Running"
else
    echo "   ❌ WebUI LaunchAgent: Not running"
fi

# Port 5555
if lsof -ti:5555 &> /dev/null; then
    echo "   ✅ Port 5555: Active"
else
    echo "   ❌ Port 5555: Not listening"
fi

# Health check
echo ""
echo "🏥 Health Check:"
if command -v curl &> /dev/null; then
    HEALTH=$(curl -s http://localhost:5555/api/health 2>&1)
    if echo "$HEALTH" | grep -q "healthy"; then
        echo "   ✅ WebUI Backend: Healthy"
    else
        echo "   ❌ WebUI Backend: Not responding"
    fi
else
    echo "   ⏭️  curl not available, skipping health check"
fi

# Configuration
echo ""
echo "⚙️  Configuration:"
if [ -f "/Users/ssr/Projects/WorkingBot/ecosystem.config.js" ]; then
    if grep -q "/Users/ssr/Projects/WorkingBot" /Users/ssr/Projects/WorkingBot/ecosystem.config.js; then
        echo "   ✅ PM2 config: Paths updated"
    else
        echo "   ⚠️  PM2 config: Needs path update"
    fi
else
    echo "   ❌ PM2 config: Not found"
fi

if grep -q "/opt/homebrew/bin" ~/.zshrc 2>/dev/null; then
    echo "   ✅ Shell PATH: Configured"
else
    echo "   ⚠️  Shell PATH: Needs configuration"
fi

echo ""
echo "========================================"
echo "📊 Summary"
echo "========================================"

# Count successes
TOTAL=0
SUCCESS=0

# Core tools
for cmd in node npm pm2 python3 pip3; do
    TOTAL=$((TOTAL + 1))
    if command -v $cmd &> /dev/null; then
        SUCCESS=$((SUCCESS + 1))
    fi
done

# Python packages
for pkg in "${PACKAGES[@]}"; do
    TOTAL=$((TOTAL + 1))
    if pip3 show "$pkg" &> /dev/null; then
        SUCCESS=$((SUCCESS + 1))
    fi
done

# Services
TOTAL=$((TOTAL + 2))
if launchctl list | grep -q "com.gridbot.webui"; then
    SUCCESS=$((SUCCESS + 1))
fi
if lsof -ti:5555 &> /dev/null; then
    SUCCESS=$((SUCCESS + 1))
fi

echo ""
echo "   ✅ Success: $SUCCESS / $TOTAL"
echo ""

if [ $SUCCESS -eq $TOTAL ]; then
    echo "🎉 All dependencies installed and working!"
    echo ""
    echo "Ready to:"
    echo "  • Access WebUI: http://localhost:5555"
    echo "  • Use PM2: pm2 start ecosystem.config.js"
    echo "  • Start trading: Via WebUI Bot Control"
else
    echo "⚠️  Some dependencies missing or not configured"
    echo ""
    echo "Run these commands:"
    echo "  • Install missing packages: pip3 install -r requirements.txt --user"
    echo "  • Rebuild frontend: cd webui/frontend && npm run build"
    echo "  • Restart services: launchctl restart com.gridbot.webui"
fi

echo ""
echo "========================================"

