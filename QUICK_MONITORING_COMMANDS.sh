#!/bin/bash
# Quick Monitoring Commands for Bot Error Analysis
# Generated: October 15, 2025

echo "============================================"
echo "🔍 BOT HEALTH CHECK - Quick Commands"
echo "============================================"
echo ""

# 1. Check bot processes
echo "1️⃣  Bot Processes Status:"
ps aux | grep -E "(python|guardian|bot)" | grep -v grep | grep -E "bot.run|guardian_bot" || echo "⚠️  Bot not running!"
echo ""

# 2. Recent errors (last hour)
echo "2️⃣  Error Count (Last Hour):"
sqlite3 data/errors.db "SELECT COUNT(*) as errors FROM errors WHERE datetime(last_seen) > datetime('now', '-1 hour')" 2>/dev/null || echo "⚠️  Could not query errors.db"
echo ""

# 3. TP placement success rate
echo "3️⃣  TP Placement Status (Last 20 attempts):"
grep -E "TP placed|TP placement failed|create TP.*failed" bot_run.log | tail -20 | sed 's/^/  /'
echo ""

# 4. API instability detection
echo "4️⃣  API Instability Events (Last 50 lines):"
grep "API instability detected" bot_run.log | tail -10 | sed 's/^/  /' || echo "  ✅ No API instability detected"
echo ""

# 5. Temporarily exposed positions
echo "5️⃣  Temporarily Exposed Positions:"
grep "temporarily exposed" bot_run.log | tail -10 | sed 's/^/  /' || echo "  ✅ No exposed positions detected"
echo ""

# 6. Recent cooldowns
echo "6️⃣  Recent Cooldown Events:"
grep "cooldown" bot_run.log | tail -10 | sed 's/^/  /'
echo ""

# 7. Bot heartbeat
echo "7️⃣  Bot Heartbeat (Last 5):"
grep "\[HB\]" bot_run.log | tail -5 | sed 's/^/  /'
echo ""

# 8. Error breakdown by severity
echo "8️⃣  Error Breakdown (Last 6 Hours):"
sqlite3 data/errors.db "SELECT severity, COUNT(*) as count FROM errors WHERE datetime(last_seen) > datetime('now', '-6 hours') GROUP BY severity ORDER BY count DESC" 2>/dev/null || echo "⚠️  Could not query errors.db"
echo ""

echo "============================================"
echo "✅ Health Check Complete"
echo "============================================"
echo ""
echo "💡 TIP: Run this script periodically to monitor bot health"
echo "   Usage: bash QUICK_MONITORING_COMMANDS.sh"
echo ""

