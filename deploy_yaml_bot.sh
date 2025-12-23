#!/bin/bash
#
# INSTANT YAML MIGRATION - PRODUCTION DEPLOYMENT
# This script switches the bot to YAML configuration immediately
#

set -e

echo "═══════════════════════════════════════════════════════════════════════════"
echo "GRIDBOT YAML MIGRATION - INSTANT PRODUCTION CUTOVER"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found!"
    echo "   Please ensure config.yaml exists in the project root"
    exit 1
fi

echo "✅ config.yaml found"
echo ""

# Validate Python dependencies
echo "📦 Checking dependencies..."
python3 -c "import pydantic; import yaml; import watchdog" 2>/dev/null || {
    echo "❌ Missing dependencies!"
    echo "   Installing pydantic, pyyaml, watchdog..."
    pip3 install pydantic pyyaml watchdog
}
echo "✅ Dependencies OK"
echo ""

# Test config loading
echo "🧪 Testing config loading..."
python3 -c "from config.loader import get_config; config = get_config(); print(f'   Version: {config.version}'); print(f'   Mode: {config.trading_mode}')" || {
    echo "❌ Config validation failed!"
    echo "   Please check config.yaml for errors"
    exit 1
}
echo "✅ Config validated"
echo ""

# Check if old bot is running
OLD_BOT_RUNNING=$(pm2 list | grep gridbot | grep -v gridbot-yaml | wc -l | tr -d ' ')

if [ "$OLD_BOT_RUNNING" -gt 0 ]; then
    echo "⚠️  Old bot (ENV-based) is still running"
    echo "   Stopping old bot..."
    pm2 stop gridbot 2>/dev/null || true
    echo "✅ Old bot stopped"
    echo ""
fi

# Deploy new YAML-based bot
echo "🚀 Deploying YAML-based bot..."
pm2 delete gridbot-yaml 2>/dev/null || true
pm2 start ecosystem.yaml-bot.json

echo ""
echo "✅ Bot deployed with YAML configuration!"
echo ""

# Show status
pm2 list | grep gridbot

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "✅ MIGRATION COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "📊 View logs:"
echo "   pm2 logs gridbot-yaml"
echo ""
echo "⚙️ Edit config:"
echo "   1. Edit config.yaml manually, OR"
echo "   2. Use WebUI at http://localhost:5555/config"
echo ""
echo "🔄 Reload config (hot-reload):"
echo "   Just save config.yaml - bot will auto-reload!"
echo ""
echo "🛡️ Rollback (if needed):"
echo "   pm2 stop gridbot-yaml"
echo "   mv config.yaml config.yaml.backup"
echo "   pm2 restart gridbot  # Old ENV-based bot"
echo ""
