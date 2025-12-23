# Guardian Bot Defense System

## Overview
The Guardian Bot is a critical defense mechanism that monitors risk levels, position sizes, and market conditions to protect your trading operations. It runs continuously via macOS LaunchAgent with automatic restart capabilities.

## System Status (Current)
- **LaunchAgent PID**: 21591
- **Status**: RUNNING ✅
- **Uptime**: 1h16m
- **Memory Usage**: 92MB (0.6%)
- **CPU Usage**: 0.0%
- **Auto-Restart**: Enabled
- **Launch on Boot**: Enabled

## LaunchAgent Configuration

### Service Details
- **Service Name**: `com.workingbot.guardian`
- **Configuration File**: `~/Library/LaunchAgents/com.workingbot.guardian.plist`
- **Log File**: `/Users/ssr/Projects/WorkingBot/logs/guardian_bot.log`
- **Error Log**: `/Users/ssr/Projects/WorkingBot/logs/guardian_bot_error.log`

### Key Settings
```xml
<key>KeepAlive</key>
<true/>  <!-- Auto-restart if crashes -->

<key>RunAtLoad</key>
<true/>  <!-- Start on system boot -->

<key>ThrottleInterval</key>
<integer>30</integer>  <!-- Wait 30s between restarts -->
```

## Monitoring System

### Automatic Monitoring
A cron job runs every 5 minutes to verify the guardian is running:
```bash
*/5 * * * * /Users/ssr/Projects/WorkingBot/check_guardian_status.sh
```

### Manual Status Check
```bash
# Quick status check
./check_guardian_status.sh

# Detailed LaunchAgent status
launchctl list | grep guardian

# View process details
ps aux | grep guardian_bot.py
```

### Monitor Logs
```bash
# Real-time monitoring
tail -f logs/guardian_monitor.log

# Last 50 guardian events
tail -50 logs/guardian_bot.log

# Check for errors
tail -50 logs/guardian_bot_error.log
```

## Management Commands

### Start/Stop/Restart
```bash
# Stop the guardian
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Start the guardian
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Restart (unload then load)
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist && \
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
```

### Emergency Manual Start
If LaunchAgent fails, you can run manually:
```bash
cd /Users/ssr/Projects/WorkingBot
export PYTHONPATH=/Users/ssr/Projects/WorkingBot
python3 bot/guardian/core/guardian_bot.py
```

## Defense Capabilities

### Risk Monitoring
- Position size verification
- Leverage limits enforcement
- Exposure monitoring
- Margin requirement checks

### Event-Based Actions
- Auto-close oversized positions
- Throttle order creation during high volatility
- Alert on margin calls
- Emergency stop on critical events

### Data Integrity
- Validates order consistency
- Detects duplicate orders
- Monitors API connection health
- Tracks execution delays

## Log Rotation
Guardian logs use RotatingFileHandler to prevent disk bloat:
- **Max Log Size**: 10 MB per file
- **Backup Count**: 3 files
- **Total Max Size**: ~40 MB
- **Error Throttling**: Same error max once per 60 seconds

## Auto-Cleanup Integration
The guardian's logs and events are managed by the auto-cleanup system:
- **Log Files**: Cleaned after 48 hours
- **Database Events**: Cleaned after 48 hours
- **Error Records**: Cleaned after 48 hours
- **Cleanup Schedule**: Runs hourly

## Troubleshooting

### Guardian Not Starting
1. Check LaunchAgent status:
   ```bash
   launchctl list | grep guardian
   ```
   - If exit code is 0: Running successfully
   - If exit code is 1: Check error logs

2. Verify file integrity:
   ```bash
   cd /Users/ssr/Projects/WorkingBot
   git status bot/guardian/core/guardian_bot.py
   ```
   - If modified unexpectedly, restore: `git restore bot/guardian/core/guardian_bot.py`

3. Check Python path:
   ```bash
   cat ~/Library/LaunchAgents/com.workingbot.guardian.plist | grep PYTHONPATH
   ```
   - Should include: `/Users/ssr/Projects/WorkingBot`

### Guardian Crashing Repeatedly
1. Check error log:
   ```bash
   tail -100 logs/guardian_bot_error.log
   ```

2. Test startup manually:
   ```bash
   export PYTHONPATH=/Users/ssr/Projects/WorkingBot
   python3 bot/guardian/core/guardian_bot.py
   ```

3. If ModuleNotFoundError, check dependencies:
   ```bash
   pip3 list | grep -E 'ccxt|python-binance|config'
   ```

### High Memory Usage
If memory exceeds 500 MB:
1. Check for event accumulation:
   ```bash
   sqlite3 data/bot_events_LONG.db "SELECT COUNT(*) FROM events WHERE timestamp > datetime('now', '-48 hours')"
   ```

2. Force cleanup:
   ```bash
   python3 auto_data_cleanup.py
   ```

3. Restart guardian:
   ```bash
   launchctl kickstart -k gui/$(id -u)/com.workingbot.guardian
   ```

## Recovery Procedures

### File Corruption
If guardian_bot.py is corrupted:
```bash
cd /Users/ssr/Projects/WorkingBot
git restore bot/guardian/core/guardian_bot.py
launchctl unload ~/Library/LaunchAgents/com.workingbot.guardian.plist
launchctl load ~/Library/LaunchAgents/com.workingbot.guardian.plist
```

### Database Corruption
If guardian database is corrupted:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/bot_events_LONG.db')
conn.execute('VACUUM')
conn.close()
print('Database repaired')
"
```

### LaunchAgent Not Responding
```bash
# Kill the process
launchctl kill SIGTERM gui/$(id -u)/com.workingbot.guardian

# Wait 5 seconds for cleanup
sleep 5

# LaunchAgent will auto-restart due to KeepAlive=true
launchctl list | grep guardian
```

## Integration Points

### Event Store
- Writes risk events to: `data/bot_events_LONG.db`
- Table: `events`
- Retention: 48 hours (auto-cleanup)

### Risk Decision Engine
- Evaluates positions against risk rules
- Uses configuration from: `config/` directory
- Triggers actions based on thresholds

### WebUI Integration
- Status visible in WebUI dashboard
- Recent events displayed in activity feed
- Alert badges for critical events

## Performance Metrics

### Normal Operation
- **CPU Usage**: 0.0% - 2.0%
- **Memory Usage**: 50 MB - 150 MB
- **Event Processing**: < 100ms per event
- **Database Writes**: < 10ms per write

### Warning Thresholds
- **CPU Usage**: > 10% sustained
- **Memory Usage**: > 300 MB
- **Event Processing**: > 1 second
- **Crash Count**: > 3 per hour

## Security Considerations

### File Permissions
```bash
# LaunchAgent should be readable by user only
chmod 644 ~/Library/LaunchAgents/com.workingbot.guardian.plist

# Python script should be executable
chmod 755 bot/guardian/core/guardian_bot.py

# Logs should be writable
chmod 644 logs/guardian_*.log
```

### API Key Protection
- Guardian has read-only access to positions
- Cannot place orders (safety feature)
- Uses encrypted credential storage

## Maintenance Schedule

### Daily
- ✅ Auto-monitored via cron (every 5 minutes)
- ✅ Auto-cleaned via cleanup service (hourly)

### Weekly
- Review error log for patterns
- Check memory/CPU trends
- Verify database size < 50 MB

### Monthly
- Review guardian rules for adjustments
- Update risk thresholds if needed
- Test emergency shutdown procedures

## Version History
- **Dec 14, 2025**: File corruption fixed via git restore, LaunchAgent restarted
- **Nov 16, 2025**: Added RotatingFileHandler (10MB max, 3 backups)
- **Nov 16, 2025**: Implemented error throttling (60s cooldown)
- **Nov 16, 2025**: Integrated with auto-cleanup system (48h retention)
- **Nov 16, 2025**: Created monitoring cron job (every 5 minutes)

## Support Resources
- Guardian Bot Implementation: [bot/guardian/core/guardian_bot.py](bot/guardian/core/guardian_bot.py)
- Risk Decision Engine: [bot/guardian/core/risk_decision_engine.py](bot/guardian/core/risk_decision_engine.py)
- Event Store: [bot/core/event_store.py](bot/core/event_store.py)
- Monitoring Script: [check_guardian_status.sh](check_guardian_status.sh)
- Auto-Cleanup: [auto_data_cleanup.py](auto_data_cleanup.py)

---

**Status**: Guardian Bot is OPERATIONAL as a defense mechanism ✅
**Last Verified**: Dec 14, 2025
**Next Review**: Weekly
