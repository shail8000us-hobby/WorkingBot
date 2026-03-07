# Production Setup - January 5, 2026

## ✅ Successfully Migrated to Production Workflow

### What Changed

**BEFORE (Development Mode):**
- ❌ Frontend dev server on port 3000/3001/3002 (confusion!)
- ❌ Backend on port 5555
- ❌ Two separate processes
- ❌ Port conflicts common

**AFTER (Production Mode):**
- ✅ **Single port architecture: 5555**
- ✅ Backend serves production frontend
- ✅ LaunchAgent manages backend
- ✅ Guardian monitors health
- ✅ No port confusion!

---

## 🚀 Current Architecture

```
┌─────────────────────────────────────────┐
│  Production Mode (ACTIVE)               │
├─────────────────────────────────────────┤
│  Backend (Flask)        →  Port 5555   │
│    ↳ Serves React build from            │
│      /webui/frontend/build/             │
│    ↳ API endpoints: /api/*              │
│    ↳ WebSocket: /socket.io/*            │
│    ↳ Options Chain: /api/options-chain/*│
└─────────────────────────────────────────┘
```

---

## 📦 Services Running

### Backend (LaunchAgent)
```bash
# Status
launchctl list | grep gridbot.webui
# Output: 7739    0       com.gridbot.webui ✅

# URL
http://localhost:5555

# Health Check
curl http://localhost:5555/api/health
```

### Guardian (LaunchAgent)
```bash
# Status  
launchctl list | grep gridbot.webui.guardian
# Output: 31567   -9      com.gridbot.webui.guardian ✅

# Monitors backend health every 30 seconds
# Auto-restarts on crash
# Memory leak detection (restart at 2GB)
```

---

## 🎯 Access Points

### Main WebUI
```
http://localhost:5555
```

### Options Chain (with Trading)
```
http://localhost:5555
→ Navigate to "Options Chain" tab
→ Click B/S buttons to trade
```

### API Endpoints
```
http://localhost:5555/api/health
http://localhost:5555/api/options-chain/health
http://localhost:5555/api/options-chain/expirations?underlying=BTC
http://localhost:5555/api/options-chain/data?underlying=BTC&expiry=06012026
```

---

## 🔧 Management Commands

### Backend Control
```bash
# Start
launchctl start com.gridbot.webui

# Stop
launchctl stop com.gridbot.webui

# Restart
launchctl restart com.gridbot.webui

# Status
launchctl list | grep gridbot.webui

# Logs
tail -f logs/launchagent_webui.log
tail -f logs/launchagent_webui_error.log
```

### Frontend (Production Build)
```bash
# Rebuild frontend (when you make changes)
cd /Users/ssr/Projects/WorkingBot/webui/frontend
npm run build

# Restart backend to serve new build
launchctl restart com.gridbot.webui
```

### Port Management
```bash
# Check what's on port 5555
lsof -i :5555

# Clear port if needed (emergency only)
lsof -ti:5555 | xargs kill -9

# Restart backend after clearing
launchctl start com.gridbot.webui
```

---

## 🚨 Troubleshooting

### WebUI not accessible
```bash
# 1. Check LaunchAgent
launchctl list | grep gridbot.webui

# 2. Check logs
tail -50 logs/launchagent_webui_error.log

# 3. Restart
launchctl restart com.gridbot.webui

# 4. Wait 5 seconds and test
curl http://localhost:5555/api/health
```

### Port 5555 conflict
```bash
# Should never happen now!
# But if it does:

# 1. Find what's using it
lsof -i :5555

# 2. Kill it
lsof -ti:5555 | xargs kill -9

# 3. Restart
launchctl start com.gridbot.webui
```

### Frontend not updating
```bash
# Rebuild and restart
cd /Users/ssr/Projects/WorkingBot/webui/frontend
npm run build
launchctl restart com.gridbot.webui
```

### Options Chain not working
```bash
# 1. Test backend API
curl http://localhost:5555/api/options-chain/health

# 2. Test data fetch
curl 'http://localhost:5555/api/options-chain/expirations?underlying=BTC'

# 3. Check backend logs
tail -50 logs/launchagent_webui_error.log | grep -i "options"

# 4. Restart if needed
launchctl restart com.gridbot.webui
```

---

## 📊 Health Monitoring

### Quick Status Check
```bash
# Create a status script
cat > check_status.sh << 'EOF'
#!/bin/bash
echo "=== WebUI Status ==="
echo ""
echo "LaunchAgent:"
launchctl list | grep gridbot.webui
echo ""
echo "Port 5555:"
lsof -i :5555 | grep LISTEN
echo ""
echo "Health Check:"
curl -s http://localhost:5555/api/health | python3 -m json.tool
echo ""
echo "Options Chain:"
curl -s http://localhost:5555/api/options-chain/health | python3 -m json.tool
EOF

chmod +x check_status.sh
./check_status.sh
```

### Expected Output
```
=== WebUI Status ===

LaunchAgent:
7739    0       com.gridbot.webui
31567   -9      com.gridbot.webui.guardian

Port 5555:
Python     7739  ssr    8u  IPv4 ... TCP *:personal-agent (LISTEN)

Health Check:
{
    "status": "healthy",
    "timestamp": "2026-01-05T14:14:24.169674Z"
}

Options Chain:
{
    "message": "Options Chain module is running",
    "module": "options_chain",
    "status": "ok"
}
```

---

## 🎉 Benefits of Production Setup

### Eliminated Confusion
- ✅ Single port: 5555
- ✅ No more 3000/3001/3002 conflicts
- ✅ Clear production vs development separation

### Improved Reliability
- ✅ LaunchAgent auto-restart on crash
- ✅ Guardian monitors health 24/7
- ✅ Memory leak protection
- ✅ Process isolation

### Better Performance
- ✅ Production-optimized React build
- ✅ Minified JS/CSS
- ✅ Compressed assets
- ✅ Faster load times

### Easier Management
- ✅ Single service to control
- ✅ Clear logs location
- ✅ Simple status checks
- ✅ Consistent behavior

---

## 🔐 Security Notes

### Port Access
- Port 5555 listens on `0.0.0.0` (all interfaces)
- Access via LAN: `http://192.168.1.X:5555`
- Access via Tailscale: `http://mymac.tail289dc3.ts.net:5555`

### API Keys
- Stored in: `secrets/api_keys.env`
- Never committed to git
- Loaded by backend automatically

---

## 📝 Files Modified

### Frontend
```
/webui/frontend/build/           ← Production build (regenerated)
/webui/frontend/package.json     ← Proxy points to 5555
```

### Backend
```
/webui/backend/app.py            ← Serves static files from build/
/webui/backend/options_chain/    ← Options Chain module with trading
```

### LaunchAgents
```
~/Library/LaunchAgents/com.gridbot.webui.plist         ← Backend
~/Library/LaunchAgents/com.gridbot.webui.guardian.plist ← Guardian
```

### Documentation
```
/backend_frontend.md              ← Updated with current setup
/PRODUCTION_SETUP_JAN2026.md     ← This file
```

---

## ✅ Verification Checklist

After setup, verify:

- [ ] Backend accessible: `curl http://localhost:5555/api/health`
- [ ] Frontend loads: Open `http://localhost:5555` in browser
- [ ] Options Chain works: Navigate to Options Chain tab
- [ ] Trading buttons visible: See B/S buttons on each option row
- [ ] LaunchAgent running: `launchctl list | grep gridbot.webui`
- [ ] Guardian monitoring: Check `logs/webui_guardian.log`
- [ ] No dev servers: `ps aux | grep react-app-rewired` shows nothing
- [ ] Port 5555 only: `lsof -i :3000-3002` shows nothing

---

## 🎯 Next Steps

### For Development
If you need to make frontend changes:

1. **Make changes** in `/webui/frontend/src/`
2. **Build** with `npm run build`
3. **Restart backend** with `launchctl restart com.gridbot.webui`
4. **Test** at `http://localhost:5555`

### For Monitoring
- Check logs daily: `tail logs/launchagent_webui.log`
- Review guardian stats: `cat data/webui_guardian_stats.json`
- Monitor restarts (should be 0): `grep "total_restarts" data/webui_guardian_stats.json`

---

**Setup Date:** January 5, 2026  
**Status:** ✅ Production Ready  
**Architecture:** Single Port (5555)  
**Services:** Backend (LaunchAgent) + Guardian (LaunchAgent)  
**Frontend:** Production Build Served by Backend
