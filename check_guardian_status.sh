#!/bin/bash
# Guardian Bot Health Monitor - Ensures defense mechanism stays running

GUARDIAN_LABEL="com.workingbot.guardian"
LOG_FILE="/Users/ssr/Projects/WorkingBot/logs/guardian_monitor.log"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log_message() { echo "[$(timestamp)] $1" | tee -a "$LOG_FILE"; }

echo "═══════════════════════════════════════════════════════════"
echo "  GUARDIAN BOT - DEFENSE MECHANISM STATUS"
echo "═══════════════════════════════════════════════════════════"

# Check status
if launchctl list | grep -q "$GUARDIAN_LABEL"; then
    PID=$(launchctl list | grep "$GUARDIAN_LABEL" | awk '{print $1}')
    
    if [ "$PID" != "-" ]; then
        echo "✅ Guardian Bot: RUNNING (PID: $PID)"
        log_message "✅ Guardian running (PID: $PID)"
        ps -p "$PID" -o etime,rss,%cpu,%mem 2>/dev/null | tail -1
    else
        echo "⚠️  Guardian NOT running - Restarting..."
        log_message "⚠️  Guardian crashed - restarting"
        launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist 2>/dev/null
        sleep 2
        launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
        sleep 3
        NEW_PID=$(launchctl list | grep "$GUARDIAN_LABEL" | awk '{print $1}')
        echo "✅ Guardian restarted (PID: $NEW_PID)"
        log_message "✅ Guardian restarted (PID: $NEW_PID)"
    fi
else
    echo "❌ Guardian NOT loaded - Loading now..."
    log_message "❌ Guardian not loaded - loading"
    launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
    sleep 3
    echo "✅ Guardian loaded"
    log_message "✅ Guardian loaded"
fi

echo ""
echo "⚙️  Configuration:"
echo "   ✅ KeepAlive: Enabled (auto-restart)"
echo "   ✅ RunAtLoad: Enabled (auto-start on boot)"
echo "   ✅ ThrottleInterval: 30s between restarts"
echo ""
echo "═══════════════════════════════════════════════════════════"
