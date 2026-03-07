# Memory Issue - Quick Fix Guide

## 🚨 Problem
Your trading bot accumulated **121,374 events** (211MB database) causing system memory exhaustion.

## ✅ Solution Implemented

### Automatic Event Retention
- Keeps last 7 days of guardian signals
- Auto-cleanup runs every hour
- Database stays under 20MB

## 🚀 How to Fix NOW

### Option 1: Emergency Fix (Recommended)
```bash
cd /Users/ssr/Projects/WorkingBot

# Stop the bot
killall -TERM python3

# Run emergency fix
./tools/emergency_memory_fix.sh

# Restart bot (auto-cleanup is now active)
python3 -m bot.guardian.core.guardian_bot
```

### Option 2: Manual Cleanup
```bash
# Dry run (see what will be deleted)
python3 tools/cleanup_event_database.py --dry-run

# Actual cleanup (keeps last 7 days)
python3 tools/cleanup_event_database.py

# Custom retention (e.g., 3 days)
python3 tools/cleanup_event_database.py --keep-days 3
```

## 📊 Before vs After

| Metric | Before | After |
|--------|--------|-------|
| Total Events | 121,374 | ~10,000 |
| Database Size | 211 MB | ~20 MB |
| Memory Usage | 15GB (maxed) | Normal |
| Guardian Signals | 99% of events | 99% of events |
| Oldest Event | Nov 20 | Last 7 days |

## 🔍 Check Database Health

```bash
# Quick stats
./tools/check_database_health.sh

# Detailed analysis
sqlite3 data/bot_events_LONG.db "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
```

## 🎯 What Gets Deleted

✅ **Deleted** (to free memory):
- Old `guardian_signal_go` events (>7 days)
- Old `guardian_signal_stop` events (>7 days)

❌ **Preserved** (important for audit):
- All trading events (orders, positions, sagas)
- Recent guardian signals (last 7 days)

## 🔐 Safety

- ✅ Backup created automatically
- ✅ Dry-run mode available
- ✅ Only deletes guardian signals
- ✅ All trading history preserved
- ✅ Graceful bot shutdown

## 📈 Going Forward

After restart, the bot will:
1. Auto-cleanup old events every hour
2. Keep database under 20MB
3. Maintain stable memory usage
4. Log cleanup activity

Monitor with:
```bash
# Watch database size
watch -n 60 'ls -lh data/bot_events_LONG.db'

# Monitor cleanup logs  
tail -f bot/logs/guardian.log | grep retention

# Check memory usage
watch -n 5 'ps aux | grep guardian'
```

## ❓ FAQ

**Q: Will I lose trading history?**
A: No! Only guardian signals are deleted. All orders, positions, and sagas are preserved.

**Q: How often does cleanup run?**
A: Automatically every hour when the bot is running.

**Q: Can I change retention period?**
A: Yes, modify `retention_days` in the EventRetentionPolicy initialization.

**Q: Is it safe to run while bot is running?**
A: For safety, stop the bot first. The bot uses auto-cleanup which is safe.

## 🆘 Still Having Issues?

1. Check bot logs: `tail -100 bot/logs/guardian.log`
2. Verify cleanup ran: `grep "retention cleanup" bot/logs/guardian.log`
3. Check memory: `top -l 1 -o mem -n 10`
4. Database stats: `./tools/check_database_health.sh`

## 📝 Files Created

- `/tools/cleanup_event_database.py` - Manual cleanup tool
- `/tools/emergency_memory_fix.sh` - Quick fix script
- `/tools/check_database_health.sh` - Health check tool
- `/bot/strategy/modules/event_retention.py` - Auto retention policy
- [MEMORY_ISSUE_FIX_DEC18_2025.md](MEMORY_ISSUE_FIX_DEC18_2025.md) - Full documentation
