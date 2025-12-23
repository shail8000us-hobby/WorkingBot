#!/bin/bash

# Simple sync script for WorkingBot → WorkingBot-demo
# Since demo is just a directory copy (not git), we use direct file copy

PROD="/Users/ssr/Projects/WorkingBot"
DEMO="/Users/ssr/Projects/WorkingBot-demo"

echo "🔄 Syncing WorkingBot → WorkingBot-demo..."
echo ""

# Check if demo exists
if [ ! -d "$DEMO" ]; then
    echo "❌ Error: WorkingBot-demo directory not found at $DEMO"
    exit 1
fi

# Sync core strategy files
echo "📁 Syncing bot/strategy..."
rsync -av --progress \
    "$PROD/bot/strategy/" \
    "$DEMO/bot/strategy/"

# Sync monitoring (if needed)
echo ""
echo "📊 Syncing bot/monitoring..."
rsync -av --progress \
    "$PROD/bot/monitoring/" \
    "$DEMO/bot/monitoring/"

# Sync volatility tracking
echo ""
echo "🌊 Syncing bot/volatility..."
rsync -av --progress \
    "$PROD/bot/volatility/" \
    "$DEMO/bot/volatility/"

# Sync important modules
echo ""
echo "🔧 Syncing bot/strategy/modules..."
rsync -av --progress \
    "$PROD/bot/strategy/modules/" \
    "$DEMO/bot/strategy/modules/"

# Copy recent documentation
echo ""
echo "📝 Syncing documentation..."
cp "$PROD"/ASYNC_ORDER_REPLACEMENT_NOV10_2025.md "$DEMO/" 2>/dev/null
cp "$PROD"/MARKET_PRICE_SYNC_FIX_NOV10_2025.md "$DEMO/" 2>/dev/null
cp "$PROD"/AI_CONTEXT.md "$DEMO/" 2>/dev/null

echo ""
echo "✅ Sync complete!"
echo ""
echo "Next steps:"
echo "  1. cd $DEMO"
echo "  2. pm2 restart gridbot-demo"
echo "  3. pm2 logs gridbot-demo --lines 100"
