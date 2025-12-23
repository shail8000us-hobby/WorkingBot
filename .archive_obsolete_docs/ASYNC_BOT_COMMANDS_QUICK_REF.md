# Async Bot Commands - Quick Reference

**Updated:** November 14, 2025  
**For:** Async GridBot (Production v2.0)

---

## 🚀 Start Commands

### Start Async Bot (PM2 - Recommended)
```bash
cd ~/Projects/WorkingBot && pm2 start gridbot-live
```

### Start Async Bot (Direct - Backup)
```bash
cd ~/Projects/WorkingBot && USE_ASYNC_BOT=true python3 -m bot.run
```

### Start Async Bot (Demo Mode)
```bash
cd ~/Projects/WorkingBot && TRADING_MODE=demo USE_ASYNC_BOT=true python3 bot/run.py
```

### Clean Start (Removes all locks)
```bash
cd ~/Projects/WorkingBot && ./clean_start_async.sh
```

---

## 🛑 Stop Commands

### Stop Async Bot (Graceful)
```bash
pm2 stop gridbot-live
```

### Stop All Components
```bash
cd ~/Projects/WorkingBot && ./pm2_gridbot.sh stop all
```

### Emergency Stop (Immediate)
```bash
pkill -TERM -f "bot.run" && pm2 stop all
```

---

## 📊 Monitoring Commands

### View Live Async Bot Logs
```bash
pm2 logs gridbot-live --lines 50
```

### View All Logs (Multi-pane tmux)
```bash
cd ~/Projects/WorkingBot && ./watch_bot_logs.sh all
```

### Check PM2 Status
```bash
pm2 status
```

### Real-Time Dashboard
```bash
pm2 monit
```

---

## 🔍 Async Bot Health Checks

### Check WebSocket Connection
```bash
pm2 logs gridbot-live --lines 20 | grep -E "WebSocket|authenticated|subscribed"
```

### Verify WebSocket Health
```bash
pm2 logs gridbot-live --lines 100 | grep -E "WebSocket authenticated|Subscriptions active|Price.*flowing|Connection stable"
```

### Check Actor System
```bash
pm2 logs gridbot-live --lines 100 | grep -E "Actor.*processing|actor.*active|OrderManager|PositionTracker"
```

### Debug WebSocket Reconnections
```bash
pm2 logs gridbot-live --lines 200 | grep -E "disconnected|reconnecting|CONNECTION LOST|RECONNECTING NOW"
```

---

## 🔧 Troubleshooting

### Fix Instance Lock
```bash
cd ~/Projects/WorkingBot && ./fix_bot_instance_lock.sh
```

### Remove All Locks
```bash
cd ~/Projects/WorkingBot && rm -f .bot_instance_*.lock .bot.lock /tmp/webui_backend.lock
```

### Check for Duplicate Bots
```bash
ps aux | grep -E "python.*bot.run" | grep -v grep
```

### View Error Logs
```bash
cat ~/.pm2/logs/gridbot-live-error.log | tail -50
```

### Reset PM2 Restart Counter
```bash
pm2 reset gridbot-live
```

---

## 🔄 Restart Commands

### Restart Async Bot
```bash
pm2 restart gridbot-live
```

### Restart All Components
```bash
cd ~/Projects/WorkingBot && ./pm2_gridbot.sh restart all
```

---

## 📈 Performance Monitoring

### View Resource Usage
```bash
ps aux | grep -E "python.*(bot|guardian|webui)" | grep -v grep | awk '{print $2, $3"%", $4"%", $11}'
```

### Check PM2 Restart Count
```bash
pm2 status | grep -E "gridbot|guardian|heartbeat"
```

---

## 🔐 Configuration

### Edit Bot Config
```bash
nano ~/Projects/WorkingBot/grid_config.env
```

### View Current Config
```bash
cat ~/Projects/WorkingBot/grid_config.env | grep -v "^#" | grep -v "^$"
```

### Check Trading Mode
```bash
echo $TRADING_MODE
```

---

## 🌐 WebUI Management

### Start Enhanced WebUI
```bash
launchctl start com.gridbot.webui.enhanced
```

### Stop Enhanced WebUI
```bash
launchctl stop com.gridbot.webui.enhanced
```

### Check WebUI Status
```bash
cd ~/Projects/WorkingBot && ./check_webui_status.sh
```

### Test Backend Health
```bash
curl -s http://localhost:5555/api/health | python3 -m json.tool
```

---

## 💾 Save & Persist

### Save PM2 State
```bash
pm2 save
```

### Configure Auto-start on Boot
```bash
pm2 startup
# Run the command it outputs with sudo
pm2 save
```

---

## 🎯 Key Differences from Legacy Bot

| Feature | Legacy Bot | Async Bot |
|---------|-----------|-----------|
| **Architecture** | Sync/Thread-based | Async/Actor Model |
| **Communication** | REST API polling | WebSocket (real-time) |
| **Concurrency** | Threading | Actor messages |
| **Resilience** | Basic retry | Saga pattern |
| **Logging** | Technical only | Narrative + Technical |
| **Environment** | Default | `USE_ASYNC_BOT=true` |

---

## 📝 Important Notes

1. **Default Mode:** Async bot is now the default (`USE_ASYNC_BOT=true`)
2. **PM2 Required:** Always use PM2 for production
3. **WebSocket:** Bot connects via WebSocket (not REST polling)
4. **Narrative Logs:** Human-readable logging enabled by default
5. **Actor Model:** OrderManager, PositionTracker, etc. use message passing

---

## 🆘 Quick Troubleshooting

### Bot Won't Start
```bash
# Fix instance lock
./fix_bot_instance_lock.sh

# Check for duplicates
ps aux | grep "bot.run" | grep -v grep

# Clean start
./clean_start_async.sh
```

### No Orders Being Placed
```bash
# Check actor system
pm2 logs gridbot-live | grep -E "OrderManager|checking for entry"

# Check WebSocket
pm2 logs gridbot-live | grep -E "Price.*flowing|Connection stable"

# Check volatility halt
cat .volatility_halt.json
```

### WebSocket Issues
```bash
# Check connection
pm2 logs gridbot-live | grep "WebSocket authenticated"

# Check reconnections
pm2 logs gridbot-live | grep -E "disconnected|reconnecting"

# Restart to force reconnect
pm2 restart gridbot-live
```

---

## 📚 More Information

- **Full Documentation:** See `KNOW_YOUR_BOT_ASYNC_UPDATE.md`
- **WebUI:** "Know Your Bot" section in dashboard
- **Architecture:** `ASYNC_GRIDBOT_ARCHITECTURE_DIAGRAMS.md`
- **Logging:** `bot/utils/human_logger.py`

---

**All commands tested on macOS with zsh shell** ✅
