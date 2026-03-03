#!/bin/bash
echo "=== BOT MONITORING SCRIPT ==="
echo "Starting monitoring at $(date)"
echo ""

# Monitor bot process
echo "1. BOT PROCESS:"
ps aux | grep -E "python.*bot|python.*run" | grep -v grep || echo "Bot not running"

echo ""
echo "2. POSITION FILES:"
echo "positions_demo.json:"
cat /Users/shailendrasinghrajawat/Projects/WorkingBot/positions_demo.json | jq '.positions | length' 2>/dev/null || echo "Error reading file"

echo "positions_live.json:"
cat /Users/shailendrasinghrajawat/Projects/WorkingBot/positions_live.json | jq '.positions | length' 2>/dev/null || echo "Error reading file"

echo ""
echo "3. RECENT LOGS:"
tail -5 /Users/shailendrasinghrajawat/Projects/WorkingBot/bot.log 2>/dev/null || echo "No recent logs"

echo ""
echo "4. CONFIG SYNC:"
echo "state.json REFERENCE_LEVEL:"
cat /Users/shailendrasinghrajawat/Projects/WorkingBot/state.json | jq '.REFERENCE_LEVEL' 2>/dev/null || echo "Error reading state.json"

echo "grid_config.env GRIDBOT_REF:"
grep "GRIDBOT_REF" /Users/shailendrasinghrajawat/Projects/WorkingBot/grid_config.env 2>/dev/null || echo "Error reading grid_config.env"

echo ""
echo "=== MONITORING COMPLETE ==="
