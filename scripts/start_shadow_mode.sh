#!/bin/bash
# Quick start script for shadow mode deployment

echo "╔════════════════════════════════════════════════════════╗"
echo "║   Phase 2+3 Shadow Mode Deployment - Quick Start      ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Pre-flight checks
echo "🔍 Running pre-flight checks..."
echo ""

# Check if threaded bot is running (PM2 or direct)
if pm2 list 2>/dev/null | grep -q "gridbot-live.*online"; then
    echo "✅ Threaded bot is running (PM2: gridbot-live)"
elif pm2 list 2>/dev/null | grep -q "gridbot-demo.*online"; then
    echo "✅ Threaded bot is running (PM2: gridbot-demo)"
elif pgrep -f "bot_launcher\|grid_strategy\|bot/run.py" > /dev/null; then
    echo "✅ Threaded bot is running (Direct process)"
else
    echo "❌ Threaded bot is NOT running - please start it first"
    echo ""
    echo "To start with PM2:"
    echo "  pm2 start ecosystem.config.js --only gridbot-live"
    echo "  # or for demo:"
    echo "  pm2 start ecosystem.config.js --only gridbot-demo"
    exit 1
fi

# Check if tests pass
echo "🧪 Verifying Phase 2+3 tests..."
if python3 -m pytest tests/test_async_actors_saga.py tests/test_chaos_compensation.py -q --tb=no 2>&1 | grep -q "22 passed"; then
    echo "✅ All 22 tests passing"
else
    echo "⚠️  Warning: Tests may not be passing - check manually"
fi

# Create backup
echo "💾 Creating pre-deployment backup..."
BACKUP_DIR="state_backups/pre_shadow_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "runtime_state.json" ]; then
    cp runtime_state.json "$BACKUP_DIR/"
    echo "✅ Backed up runtime_state.json to $BACKUP_DIR"
fi

if [ -d "audit" ]; then
    cp -r audit/ "$BACKUP_DIR/"
    echo "✅ Backed up audit/ to $BACKUP_DIR"
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║              Shadow Mode Ready to Start               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "This will:"
echo "  • Run async system in READ-ONLY mode alongside threaded bot"
echo "  • Compare states every 60 seconds for 24 hours"
echo "  • Log any discrepancies for investigation"
echo "  • Keep threaded bot as primary (ZERO RISK)"
echo ""
echo "Two terminal windows will be used:"
echo "  Terminal 1: Shadow mode execution"
echo "  Terminal 2: Real-time dashboard"
echo ""

# Ask for confirmation
read -p "Start shadow mode deployment? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting shadow mode..."
    echo ""
    echo "Instructions:"
    echo "1. This terminal will run the shadow mode process"
    echo "2. Open a NEW terminal and run: ./scripts/shadow_mode_dashboard.sh"
    echo "3. Monitor the dashboard for 24 hours"
    echo "4. Press Ctrl+C anytime to stop (safe - threaded bot continues)"
    echo ""
    echo "Press ENTER to start..."
    read
    
    # Start shadow mode
    python3 scripts/migrate_to_async.py --mode shadow --duration 24
else
    echo ""
    echo "❌ Shadow mode deployment cancelled"
    echo ""
    echo "When ready, run:"
    echo "  ./scripts/start_shadow_mode.sh"
    exit 0
fi
