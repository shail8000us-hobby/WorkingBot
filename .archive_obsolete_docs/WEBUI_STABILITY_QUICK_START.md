# WebUI Stability - Quick Start Guide

**Make your WebUI never go down on Mac Mini M4 - in 5 minutes!**

---

## 🚀 Installation (Choose One)

### Option 1: Maximum Protection (Recommended) ⭐

```bash
cd /Users/shailendrasinghrajawat/Projects/WorkingBot
./install_webui_production.sh
# Choose: 4 (Both Enhanced + Guardian)
```

**Result:** WebUI will NEVER go down! 🛡️

### Option 2: Quick Setup

```bash
cd /Users/shailendrasinghrajawat/Projects/WorkingBot

# Install dependencies
pip3 install psutil requests

# Install Guardian
./install_webui_production.sh
# Choose: 3 (Guardian Only)
```

---

## ✅ Verify Installation

```bash
# Check status
./check_webui_status.sh

# Should see:
# ✅ WEBUI IS RUNNING!
# ✅ LaunchAgents active
# ✅ Health: OK
```

---

## 📊 Daily Monitoring

```bash
# Quick status
./check_webui_status.sh

# View logs
tail -f logs/webui_guardian.log

# Check stats
cat data/webui_guardian_stats.json
```

---

## 🔧 Common Commands

```bash
# Restart WebUI
launchctl restart com.gridbot.webui.enhanced

# Check health
curl http://localhost:5555/api/health

# View services
launchctl list | grep gridbot.webui

# Emergency restart
pkill -9 -f "webui/backend/app.py" && sleep 5
```

---

## 🛡️ What You Get

### 8 Protection Layers:

1. ✅ **macOS auto-restart** on crash
2. ✅ **Health monitoring** every 30s
3. ✅ **Memory leak detection** (auto-restart at 2GB)
4. ✅ **CPU monitoring** (warning at 80%)
5. ✅ **Port conflict resolution** (auto-kill conflicts)
6. ✅ **Network monitoring** (restart on connectivity loss)
7. ✅ **Crash recovery** (smart throttling)
8. ✅ **Performance tracking** (statistics & logs)

### Auto-Recovers From:

- ✅ Process crashes
- ✅ Memory leaks
- ✅ Port conflicts
- ✅ Network issues
- ✅ macOS reboots
- ✅ High CPU usage
- ✅ Process hangs
- ✅ Python errors

---

## 📈 What to Monitor

### Daily:
```bash
./check_webui_status.sh
```

### Weekly:
```bash
# Check restart count (should be 0 or minimal)
cat data/webui_guardian_stats.json | grep total_restarts
```

### Monthly:
```bash
# Test auto-restart
launchctl stop com.gridbot.webui.enhanced
# Wait 30 seconds - should auto-restart
```

---

## 🚨 Troubleshooting

### Problem: WebUI not responding

```bash
# 1. Check logs
tail -50 logs/webui_guardian.log

# 2. Check status
./check_webui_status.sh

# 3. Restart manually
launchctl restart com.gridbot.webui.enhanced
```

### Problem: Port 5555 in use

```bash
# Guardian handles this automatically!
# Or manually:
lsof -i :5555
kill -9 <PID>
```

### Problem: High memory usage

```bash
# Guardian will auto-restart at 2GB
# Check current usage:
./check_webui_status.sh
```

---

## 📝 File Locations

```
/Users/shailendrasinghrajawat/Projects/WorkingBot/
├── webui_guardian.py                    # Guardian script
├── install_webui_production.sh          # Installer
├── check_webui_status.sh                # Status checker
├── logs/
│   ├── webui_guardian.log              # Guardian logs
│   ├── launchagent_webui.log           # WebUI output
│   └── launchagent_webui_error.log     # WebUI errors
└── data/
    └── webui_guardian_stats.json        # Statistics

~/Library/LaunchAgents/
├── com.gridbot.webui.enhanced.plist     # Enhanced LaunchAgent
└── com.gridbot.webui.guardian.plist     # Guardian LaunchAgent
```

---

## 🎯 Success Checklist

After installation, verify:

- [ ] WebUI accessible at http://localhost:5555
- [ ] `./check_webui_status.sh` shows "✅ WEBUI IS RUNNING!"
- [ ] `launchctl list | grep gridbot.webui` shows 2 services
- [ ] `curl http://localhost:5555/api/health` returns healthy status
- [ ] Logs show "✅ Healthy" messages
- [ ] Stats file exists: `data/webui_guardian_stats.json`

---

## 💡 Pro Tips

1. **Set up daily monitoring:**
   ```bash
   # Add to crontab
   0 9 * * * cd /Users/shailendrasinghrajawat/Projects/WorkingBot && ./check_webui_status.sh
   ```

2. **Test auto-restart weekly:**
   ```bash
   # Kill WebUI, should auto-restart in 30s
   pkill -9 -f "webui/backend/app.py"
   ```

3. **Monitor logs:**
   ```bash
   # Watch in real-time
   tail -f logs/webui_guardian.log
   ```

4. **Check stats regularly:**
   ```bash
   # Should show 0 or minimal restarts
   cat data/webui_guardian_stats.json
   ```

---

## 🎉 Done!

Your WebUI is now production-ready with:
- ✅ Auto-restart on crash
- ✅ Health monitoring
- ✅ Resource tracking
- ✅ Automatic recovery
- ✅ 24/7 uptime

**🛡️ YOUR WEBUI WILL NEVER GO DOWN! 🛡️**

For detailed documentation, see: `WEBUI_PRODUCTION_STABILITY.md`

---

*Quick Start Guide - Last Updated: 2025-11-02*

