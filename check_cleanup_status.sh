#!/bin/bash
# Quick Reference: Automatic Data Cleanup System

echo "═══════════════════════════════════════════════════════════"
echo "  AUTOMATIC DATA CLEANUP - STATUS CHECK"
echo "═══════════════════════════════════════════════════════════"

# Check LaunchAgent
echo ""
echo "🤖 LaunchAgent Status:"
if launchctl list | grep -q "com.gridbot.auto.cleanup"; then
    echo "   ✅ Auto-cleanup service is RUNNING"
    launchctl list | grep cleanup
else
    echo "   ❌ Auto-cleanup service is NOT running"
    echo "   Start with: launchctl load ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist"
fi

# Check disk space
echo ""
echo "💾 Disk Usage:"
df -h / | tail -1 | awk '{print "   Total: "$2"  Used: "$3"  Free: "$4"  Usage: "$5}'

# Check log directory size
echo ""
echo "📝 Log Directory Size:"
du -sh /Users/ssr/Projects/WorkingBot/logs 2>/dev/null | awk '{print "   "$1}'

# Check database sizes
echo ""
echo "💿 Database Sizes:"
du -sh /Users/ssr/Projects/WorkingBot/*.db /Users/ssr/Projects/WorkingBot/data/*.db /Users/ssr/Projects/WorkingBot/webui/backend/*.db 2>/dev/null | head -5 | awk '{print "   "$1" - "$2}'

# Check last cleanup
echo ""
echo "🧹 Last Cleanup Run:"
if [ -f "/Users/ssr/Projects/WorkingBot/logs/auto_cleanup.log" ]; then
    tail -5 /Users/ssr/Projects/WorkingBot/logs/auto_cleanup.log | grep "CLEANUP COMPLETED" | tail -1
    echo "   Recent stats:"
    tail -10 /Users/ssr/Projects/WorkingBot/logs/auto_cleanup.log | grep -E "removed|deleted|freed" | tail -3
else
    echo "   ❌ No cleanup log found"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  QUICK COMMANDS"
echo "═══════════════════════════════════════════════════════════"
echo "  Run cleanup now:       python3 auto_data_cleanup.py --once"
echo "  Check disk health:     python3 disk_health_monitor.py"
echo "  View cleanup logs:     tail -f logs/auto_cleanup.log"
echo "  Restart LaunchAgent:   launchctl unload ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist"
echo "                         launchctl load ~/Library/LaunchAgents/com.gridbot.auto.cleanup.plist"
echo "═══════════════════════════════════════════════════════════"
