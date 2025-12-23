# Backend/Frontend Sync & Bot Log Monitoring - Quick Reference

**Created:** November 9, 2025  
**Status:** ✅ Backend running in production mode | Frontend built | Ready to use

---

## 🎯 Current Status (Nov 9, 2025)

**Bots (PM2):**
- 🤖 Managed via PM2 process manager
- 📊 Check status: `pm2 status` or `./pm2_gridbot.sh status`
- 📝 View logs: `pm2 logs` or `./watch_bot_logs.sh`

**Backend:**
- ✅ Running on port 5555 (LaunchAgent)
- ✅ Serving production-built React app
- ✅ Health endpoint responsive

**Frontend:**
- ✅ Production build exists (`webui/frontend/build/`)
- ⚠️ Dev server NOT running (normal for production mode)
- ✅ Proxy configured: `http://localhost:5555`

**Mode:** 🟢 Production Mode (Backend serves static frontend + Bots via PM2)

---

## 🤖 PM2 Bot Management (Primary Method)

### Quick Start

```bash
# Check bot status
pm2 status
./pm2_gridbot.sh status

# Start bots
./pm2_gridbot.sh start live          # Start live trading bot
./pm2_gridbot.sh start guardian-live # Start guardian
./pm2_gridbot.sh start all           # Start everything

# Watch logs (real-time)
pm2 logs gridbot-live                # Live bot only
pm2 logs guardian-live               # Guardian only
pm2 logs                             # All bots

# Monitor (dashboard)
pm2 monit

# Stop bots (graceful, 30s timeout)
./pm2_gridbot.sh stop live
./pm2_gridbot.sh stop all

# Restart bots
./pm2_gridbot.sh restart live
```

### Complete PM2 Commands

```bash
# Status & Info
pm2 status                           # List all processes
pm2 describe gridbot-live            # Detailed info
pm2 list                             # Same as status

# Start/Stop
./pm2_gridbot.sh start live          # Start live bot
./pm2_gridbot.sh start demo          # Start demo bot
./pm2_gridbot.sh start guardian-live # Start guardian (live)
./pm2_gridbot.sh start heartbeat     # Start heartbeat monitor
./pm2_gridbot.sh start all           # Start all

./pm2_gridbot.sh stop live           # Stop live bot (graceful)
./pm2_gridbot.sh stop all            # Stop all

./pm2_gridbot.sh restart live        # Restart live bot
./pm2_gridbot.sh restart all         # Restart all

# Logs
pm2 logs gridbot-live                # Watch live bot (Ctrl+C to exit)
pm2 logs gridbot-live --lines 100    # Last 100 lines
pm2 logs gridbot-live --nostream     # Don't follow, just print
pm2 logs --raw                       # No timestamps

# Advanced
./pm2_gridbot.sh reload live         # Zero-downtime reload
./pm2_gridbot.sh flush               # Clear all log files
./pm2_gridbot.sh save                # Save current process list
./pm2_gridbot.sh startup             # Enable auto-start on reboot
```

---

## 🚀 Quick Commands

### Backend/Frontend Management

```bash
# Interactive sync tool (recommended)
./sync_backend_frontend.sh

# Check status & test endpoints
echo "9" | ./sync_backend_frontend.sh

# Start development mode (backend + frontend dev server)
echo "1" | ./sync_backend_frontend.sh

# Production mode (rebuild frontend + restart backend)
echo "5" | ./sync_backend_frontend.sh

# Stop everything
echo "2" | ./sync_backend_frontend.sh

# Fix port conflicts
echo "7" | ./sync_backend_frontend.sh
```

### Direct Backend Control

```bash
# Restart backend
launchctl restart com.gridbot.webui

# Stop backend
launchctl stop com.gridbot.webui

# Start backend
launchctl start com.gridbot.webui

# Check status
launchctl list | grep gridbot.webui

# View logs
tail -f logs/launchagent_webui.log
tail -f logs/launchagent_webui_error.log
```

### Frontend Development

```bash
# Start dev server (development mode)
cd webui/frontend && npm start

# Build for production
cd webui/frontend && npm run build

# Kill dev server
pkill -f react-app-rewired
```

---

## 📊 Bot Log Monitoring (PM2)

### PM2 Quick Commands

```bash
# View all bot status
pm2 status

# Watch logs (real-time)
pm2 logs gridbot-live         # Live trading bot
pm2 logs guardian-live        # Guardian bot
pm2 logs                      # All bots

# View recent logs (last 100 lines)
pm2 logs gridbot-live --lines 100 --nostream
pm2 logs guardian-live --lines 100 --nostream

# Monitor (dashboard view)
pm2 monit

# Bot management
./pm2_gridbot.sh start live   # Start live bot
./pm2_gridbot.sh stop live    # Stop live bot
./pm2_gridbot.sh restart live # Restart live bot
./pm2_gridbot.sh status       # Show status
```

### Interactive Log Monitor

```bash
# Show menu (auto-detects PM2)
./watch_bot_logs.sh

# Quick access
./watch_bot_logs.sh main        # Main trading bot (PM2 or file)
./watch_bot_logs.sh guardian    # Guardian bot (PM2 or file)
./watch_bot_logs.sh webui       # WebUI backend
./watch_bot_logs.sh all         # All bots (tmux multi-pane with PM2)
./watch_bot_logs.sh errors      # Only errors from all bots
./watch_bot_logs.sh live        # Live trading mode
./watch_bot_logs.sh health      # Phase 2 & 3 health checks
```

### Direct Log Commands (Fallback)

```bash
# If not using PM2, these work too:

# Main trading bot
tail -f bot/logs/bot.log | grep -E "ERROR|WARNING|FILL|ORDER|POSITION"

# Guardian bot
tail -f bot/logs/guardian.log | grep -E "ERROR|WARNING|RESTART|RECOVERY"

# WebUI backend
tail -f logs/launchagent_webui.log logs/launchagent_webui_error.log

# All errors
tail -f bot/logs/bot.log bot/logs/guardian.log logs/launchagent_webui*.log | grep -E "ERROR|CRITICAL"

# Live trading
tail -f logs/bot_live.log

# Health checks (Phase 2 & 3)
tail -f bot/logs/bot.log | grep -E "Memory check|Health check|Circuit breaker|Watchdog"
```

### Multi-Pane Log Watching (tmux)

```bash
# All bots in split panes
./watch_bot_logs.sh all

# Detach from tmux: Ctrl+B then D
# Reattach: tmux attach -t botlogs
# Kill session: tmux kill-session -t botlogs
```

---

## 🔧 Common Operations

### Development Mode (hot-reload frontend)

1. **Start backend + frontend dev server:**
   ```bash
   ./sync_backend_frontend.sh
   # Choose option 1
   ```

2. **Access:**
   - Frontend dev: http://localhost:3000
   - Backend API: http://localhost:5555

3. **Benefits:**
   - Hot-reload on frontend changes
   - React DevTools available
   - Fast iteration

### Production Mode (single port)

1. **Build frontend + restart backend:**
   ```bash
   ./sync_backend_frontend.sh
   # Choose option 5
   ```

2. **Access:**
   - Everything: http://localhost:5555
   - Backend serves pre-built React

3. **Benefits:**
   - Production-ready
   - Single port
   - What users see

---

## 🚨 Troubleshooting

### Port 5555 Conflict

```bash
# Quick fix
./sync_backend_frontend.sh
# Choose option 7 (Fix Port Conflicts)

# Manual fix
lsof -ti:5555 | xargs kill -9
launchctl restart com.gridbot.webui
```

### Backend Not Responding

```bash
# Check logs
tail -50 logs/launchagent_webui_error.log

# Restart
launchctl restart com.gridbot.webui

# Full reset
./sync_backend_frontend.sh
# Choose option 8 (Full Reset)
```

### Frontend Can't Connect to Backend

```bash
# Verify backend is running
curl http://localhost:5555/api/health

# Check proxy in package.json
grep proxy webui/frontend/package.json
# Should show: "proxy": "http://localhost:5555"

# Restart frontend dev server
pkill -f react-app-rewired
cd webui/frontend && npm start
```

### Frontend Build Issues

```bash
# Clean rebuild
cd webui/frontend
rm -rf node_modules build
npm install
npm run build
cd ../..

# Restart backend
launchctl restart com.gridbot.webui
```

---

## 📝 File Locations

### Scripts
- `./sync_backend_frontend.sh` - Backend/frontend management
- `./watch_bot_logs.sh` - Log monitoring tool (PM2-aware)
- `./pm2_gridbot.sh` - PM2 bot management

### PM2 Configuration
- `ecosystem.gridbot.config.js` - PM2 process definitions
- PM2 logs: `~/.pm2/logs/` (gridbot-live-out.log, guardian-live-out.log)

### Backend
- `webui/backend/app.py` - Main Flask app (port 5555)
- `logs/launchagent_webui.log` - Backend output
- `logs/launchagent_webui_error.log` - Backend errors

### Frontend
- `webui/frontend/package.json` - Frontend config
- `webui/frontend/build/` - Production build (served by backend)
- `webui/frontend/src/` - React source code

### Bot Logs (Fallback)
- `bot/logs/bot.log` - Main trading bot (if not using PM2)
- `bot/logs/guardian.log` - Guardian bot (if not using PM2)
- `logs/bot_live.log` - Live trading mode

### LaunchAgent
- `~/Library/LaunchAgents/com.gridbot.webui.plist` - macOS service config

---

## 🎯 Architecture

### Development Mode
```
┌─────────────────────────────────────────┐
│  Frontend (React Dev)   →  Port 3000   │
│      ↓ Proxy API calls                  │
│  Backend (Flask)        →  Port 5555   │
└─────────────────────────────────────────┘
```

### Production Mode (Current)
```
┌─────────────────────────────────────────┐
│  Backend (Flask)        →  Port 5555   │
│    ↳ Serves static React build         │
│    ↳ API endpoints: /api/*              │
└─────────────────────────────────────────┘
```

---

## ✅ Configuration Checklist

- [x] Backend running on port 5555
- [x] Frontend proxy configured: `http://localhost:5555`
- [x] LaunchAgent registered and running
- [x] Production build exists
- [x] Health endpoint responding
- [x] Log monitoring scripts ready

---

## 🔗 Key Endpoints

**Backend (port 5555):**
```
http://localhost:5555/api/health
http://localhost:5555/api/liquidation/status
http://localhost:5555/api/positions
http://localhost:5555/api/bot-actions/next
http://localhost:5555/api/config
```

**Frontend:**
- Development: http://localhost:3000
- Production: http://localhost:5555

---

## 📚 Related Documentation

- **Complete Guide:** `backend_frontend.md`
- **Production Stability:** `WEBUI_PRODUCTION_STABILITY.md`
- **Mobile Access:** `TAILSCALE_MOBILE_OPTIMIZATION.md`
- **Phase 2 & 3 Features:** Health checks, memory monitoring, circuit breaker

---

## 💡 Best Practices

1. **Use Production Mode** unless actively developing frontend
2. **Monitor logs** regularly with `./watch_bot_logs.sh`
3. **Check backend health** before debugging frontend
4. **Rebuild frontend** after React code changes in production
5. **Use sync script** for all operations (prevents port conflicts)

---

**Last Updated:** November 9, 2025  
**Status:** ✅ All systems operational
