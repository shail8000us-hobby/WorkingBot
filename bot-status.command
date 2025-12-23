#!/bin/bash
# Quick bot status check
# Shows current positions, price, and recent activity

cd "$(dirname "$0")"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    GridBot Quick Status                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if bot is running
if pm2 show gridbot-live > /dev/null 2>&1; then
    echo "✅ Bot Status: RUNNING"
    echo ""
    
    # Show process info
    pm2 show gridbot-live | grep -E "uptime|memory|cpu"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    
    # Show recent heartbeat
    echo "💓 Latest Heartbeat:"
    pm2 logs gridbot-live --nostream --lines 100 | grep "\[HB\]" | tail -1
    echo ""
    
    # Count positions
    echo "📊 Current Positions:"
    pm2 logs gridbot-live --nostream --lines 50 | grep "Positions:" | tail -1 | sed 's/.*Positions: /  /'
    echo ""
    
    # Show recent activity
    echo "📝 Recent Activity (last 5 lines):"
    pm2 logs gridbot-live --nostream --lines 20 | tail -5
    echo ""
else
    echo "❌ Bot Status: NOT RUNNING"
    echo ""
    echo "Start the bot with: pm2 start gridbot-live"
    echo ""
fi

echo "════════════════════════════════════════════════════════════════"
echo "Press any key to exit..."
read -n 1
