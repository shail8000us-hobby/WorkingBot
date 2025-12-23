#!/bin/bash
# Quick fix for Telegram 404 errors
# This disables Telegram notifications to stop error spam

echo "🔧 Disabling Telegram notifications..."

# Backup current config
cp grid_config.env grid_config.env.backup_before_telegram_fix

# Set tokens to empty (effectively disables)
sed -i '' 's/^TELEGRAM_BOT_TOKEN=.*/TELEGRAM_BOT_TOKEN=/' grid_config.env
sed -i '' 's/^LIVE_TELEGRAM_BOT_TOKEN=.*/LIVE_TELEGRAM_BOT_TOKEN=/' grid_config.env
sed -i '' 's/^DEMO_TELEGRAM_BOT_TOKEN=.*/DEMO_TELEGRAM_BOT_TOKEN=/' grid_config.env

echo "✅ Telegram tokens cleared in grid_config.env"
echo ""
echo "📋 Next steps:"
echo "  1. Restart guardian: ./pm2_gridbot.sh restart guardian-live"
echo "  2. Check logs: pm2 logs guardian-live --lines 20"
echo ""
echo "💾 Backup saved to: grid_config.env.backup_before_telegram_fix"
