# Know Your Bot - Quick Reference v3.0
**Updated:** November 15, 2025  
**System:** Async GridBot (WebSocket + Actor Model + YAML Config)  
**Process Management:** PM2  
**Shell:** zsh (macOS)

---

## 🚀 **CORE COMMANDS - PM2 PRODUCTION**

### Start/Stop/Restart

```bash
# Start the async gridbot
cd ~/Projects/WorkingBot && pm2 start ecosystem.gridbot.config.js --only gridbot-live

# Stop the bot
pm2 stop gridbot-live

# Restart the bot (after config changes)
pm2 restart gridbot-live

# Check status
pm2 status

# View logs (live stream)
pm2 logs gridbot-live

# Monitor dashboard (interactive)
pm2 monit
```

---

## 📊 **MONITORING COMMANDS**

### PM2 Logs

```bash
# Live logs (tail -f style)
pm2 logs gridbot-live --lines 50

# Last 100 lines
pm2 logs gridbot-live --lines 100 --nostream

# Error logs only
pm2 logs gridbot-live --err --lines 50

# All processes
pm2 logs --lines 30
```

### WebSocket Health

```bash
# Check WebSocket connection status
pm2 logs gridbot-live --lines 20 --nostream | grep -E "WebSocket|authenticated|subscribed"

# Verify price feed flowing
pm2 logs gridbot-live --lines 50 --nostream | grep -E "ticker|mark_price|funding"

# Check for disconnections
pm2 logs gridbot-live --lines 200 --nostream | grep -E "disconnected|reconnecting|CONNECTION LOST"
```

### Bot Health

```bash
# Check bot is processing orders
pm2 logs gridbot-live --lines 100 --nostream | grep -E "OrderManager|PositionManager|placed|filled"

# Check for errors
pm2 logs gridbot-live --err --lines 50

# System resources
pm2 monit
```

---

## 🔧 **CONFIGURATION MANAGEMENT**

### YAML Configuration

```bash
# View current config
cat ~/Projects/WorkingBot/config.yaml

# Edit config (use your preferred editor)
nano ~/Projects/WorkingBot/config.yaml
# OR
code ~/Projects/WorkingBot/config.yaml

# Validate config after editing
cd ~/Projects/WorkingBot && python3 -c "from config.loader import get_config; get_config(); print('✅ Config valid')"

# Restart bot to apply changes
pm2 restart gridbot-live
```

### WebUI Configuration

Access via browser: http://localhost:5555

- Config Panel: Edit grid parameters
- PM2 Panel: Monitor bot status
- Logs Panel: View real-time logs
- Know Your Bot: This command reference

---

## 🐛 **TROUBLESHOOTING**

### Bot Won't Start

```bash
# Check PM2 error logs
pm2 logs gridbot-live --err --lines 50

# Check config is valid
cd ~/Projects/WorkingBot && python3 -c "from config.loader import get_config; get_config()"

# Check if another instance is running
ps aux | grep async_gridbot

# Kill all bot processes
pkill -f async_gridbot

# Clean start
pm2 delete gridbot-live
pm2 start ecosystem.gridbot.config.js --only gridbot-live
```

### WebSocket Issues

```bash
# Check authentication
pm2 logs gridbot-live --lines 100 --nostream | grep -E "Authentication|auth.*failed|401|403"

# Check subscription status
pm2 logs gridbot-live --lines 50 --nostream | grep -E "Subscribed|subscription.*confirmed"

# Force reconnect (restart bot)
pm2 restart gridbot-live
```

### Configuration Not Saving

```bash
# Check WebUI backend logs
tail -50 ~/Projects/WorkingBot/logs/webui_production.log

# Test config API directly
curl -X POST http://localhost:5555/api/config \
  -H "Content-Type: application/json" \
  -d '{"GRIDBOT_REF": "95500"}'

# Check YAML file permissions
ls -la ~/Projects/WorkingBot/config.yaml
```

### Emergency Stop

```bash
# Stop bot via PM2
pm2 stop gridbot-live

# OR kill immediately
pkill -9 -f async_gridbot

# Check no processes remain
ps aux | grep async_gridbot
```

---

## 🎯 **DIRECT COMMANDS (WITHOUT PM2)**

These commands run the bot directly (not recommended for production):

```bash
# Start async bot directly
cd ~/Projects/WorkingBot && python3 bot/strategy/async_gridbot.py

# With environment override
cd ~/Projects/WorkingBot && TRADING_MODE=demo python3 bot/strategy/async_gridbot.py

# Background process
cd ~/Projects/WorkingBot && nohup python3 bot/strategy/async_gridbot.py >> bot_async.log 2>&1 &

# Stop direct process
pkill -f async_gridbot
```

**⚠️ Note:** PM2 is strongly recommended for production (auto-restart, log management, monitoring).

---

## 📁 **FILE LOCATIONS**

### Configuration

- **Main Config:** `~/Projects/WorkingBot/config.yaml`
- **Secrets:** `~/Projects/WorkingBot/secrets/api_keys.env`
- **PM2 Config:** `~/Projects/WorkingBot/ecosystem.gridbot.config.js`

### Logs

- **PM2 Logs:** `~/Projects/WorkingBot/reports/pm2-gridbot-live-*.log`
- **WebUI Logs:** `~/Projects/WorkingBot/logs/webui_production.log`
- **Direct Bot Logs:** `~/Projects/WorkingBot/bot.log` (if running without PM2)

### Code

- **Async Bot:** `~/Projects/WorkingBot/bot/strategy/async_gridbot.py`
- **Config Loader:** `~/Projects/WorkingBot/config/loader.py`
- **WebUI Backend:** `~/Projects/WorkingBot/webui/backend/app.py`

---

## 🔍 **KEY CHANGES FROM LEGACY BOT**

### Architecture

| Component | Legacy | Async (Current) |
|-----------|--------|-----------------|
| **Config** | `grid_config.env` | `config.yaml` (Pydantic) |
| **Main Script** | `bot/run.py` | `bot/strategy/async_gridbot.py` |
| **Data Feed** | REST polling | WebSocket real-time |
| **Concurrency** | Threading | Actor Model + asyncio |
| **Error Handling** | Try/catch | Saga Pattern |
| **PM2 Process** | `gridbot-live` | `gridbot-live` (same name) |

### Configuration Updates

```bash
# OLD (deprecated):
GRIDBOT_REF=95500
GRIDBOT_STEP=500

# NEW (YAML):
grid:
  geometry:
    reference: 95500
    step: 500
```

**🎉 Good News:** WebUI automatically handles legacy aliases! You can still use `GRIDBOT_REF` in API calls.

---

## 📞 **QUICK TROUBLESHOOTING CHECKLIST**

1. **Bot not starting?**
   - ✅ Check `pm2 logs gridbot-live --err`
   - ✅ Validate `config.yaml`
   - ✅ Check no other bot instances running

2. **No orders being placed?**
   - ✅ Check WebSocket authenticated: `pm2 logs gridbot-live | grep auth`
   - ✅ Check price feed flowing: `pm2 logs gridbot-live | grep ticker`
   - ✅ Check safety settings: `SAFETY_EXECUTE_ORDERS=true` in config

3. **Config not saving in WebUI?**
   - ✅ Check backend logs: `tail ~/Projects/WorkingBot/logs/webui_production.log`
   - ✅ Test API: `curl -X POST http://localhost:5555/api/config -d '{"GRIDBOT_REF":"95500"}'`
   - ✅ Check file permissions on `config.yaml`

4. **PM2 monit showing no logs?**
   - ✅ Bot must be running: `pm2 status`
   - ✅ Check logs exist: `ls ~/Projects/WorkingBot/reports/pm2-gridbot-live-*.log`
   - ✅ Restart PM2: `pm2 restart gridbot-live`

---

## 🎓 **LEARN MORE**

- **Architecture:** See `ASYNC_GRIDBOT_ARCHITECTURE_DIAGRAMS.md`
- **Event Sourcing:** See `BOT_ACTIONS_COMPREHENSIVE_EVENTS.md`
- **WebUI Guide:** See `ASYNC_BOT_PM2_WEBUI_INTEGRATION_COMPLETE.md`
- **Quick Start:** See `ASYNC_BOT_QUICK_START.md`

---

## ✅ **PRODUCTION CHECKLIST**

Before going live:

- [ ] `config.yaml` validated
- [ ] Secrets loaded from `secrets/api_keys.env`
- [ ] `TRADING_MODE=live` set
- [ ] `SAFETY_EXECUTE_ORDERS=true` set
- [ ] PM2 configured: `pm2 start ecosystem.gridbot.config.js`
- [ ] PM2 saved: `pm2 save`
- [ ] PM2 startup enabled: `pm2 startup`
- [ ] WebUI accessible: http://localhost:5555
- [ ] WebSocket connected: Check `pm2 logs | grep authenticated`
- [ ] First order placed successfully

---

**END OF QUICK REFERENCE**

*For detailed documentation, see the `docs/` directory and markdown files in the project root.*
