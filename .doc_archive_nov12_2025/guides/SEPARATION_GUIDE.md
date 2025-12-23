# WorkingBot & WorkingBot-demo - Complete Separation Guide

**Date:** November 10, 2025  
**Purpose:** Ensure WorkingBot and WorkingBot-demo remain completely independent

---

## 🎯 SEPARATION CHECKLIST

### ✅ **1. Different Ports**

| Component | WorkingBot (Main) | WorkingBot-demo |
|-----------|-------------------|-----------------|
| WebUI | **5555** | **5556** |
| Config Variable | `WEBUI_PORT=5555` | `WEBUI_PORT=5556` |

**Files to Check:**
- `/Users/ssr/Projects/WorkingBot/grid_config.env` → `WEBUI_PORT=5555`
- `/Users/ssr/Projects/WorkingBot-demo/grid_config.env` → `WEBUI_PORT=5556`

---

### ✅ **2. Different Lock Files**

| Lock File | WorkingBot (Main) | WorkingBot-demo |
|-----------|-------------------|-----------------|
| Bot Instance | `.bot_instance_live.lock` | `.bot_instance_demo.lock` |
| Heartbeat | `.heartbeat` | `.heartbeat_demo` |
| WebUI | `.webui_instance.lock` | `.webui_instance_demo.lock` |

**Fix Applied:** WebUI API `/api/bots/status` now filters by project directory

---

### ✅ **3. Different Runtime State Files**

| State File | WorkingBot (Main) | WorkingBot-demo |
|-----------|-------------------|-----------------|
| Runtime State | `runtime_state.json` | `runtime_state_demo.json` |
| Config Hash | `config_hash_live.json` | `config_hash_demo.json` |
| Equity Snapshots | `equity_snapshots_live.json` | `equity_snapshots_demo.json` |

---

### ✅ **4. Different Trading Modes**

| Mode | WorkingBot (Main) | WorkingBot-demo |
|------|-------------------|-----------------|
| Trading Mode | `TRADING_MODE=live` | `TRADING_MODE=demo` |
| Exchange | `api.india.delta.exchange` | `testnet-api.delta.exchange` |
| API Keys | `LIVE_DELTA_API_KEY` | `DEMO_DELTA_API_KEY` |

---

### ✅ **5. Independent Process Detection**

**Code Fix Applied:**
```python
# File: webui/backend/routes/bot_control.py
# /api/bots/status now filters by project directory

# Only shows processes from THIS project
current_project = str(Path(__file__).parent.parent.parent.parent)

# Skip WorkingBot-demo processes
if 'workingbot-demo' in proc_cwd.lower():
    continue
```

**Result:** Each WebUI only shows its own processes

---

## 🚀 STARTUP PROCEDURES

### **WorkingBot (Main - Live Trading)**

```bash
cd /Users/ssr/Projects/WorkingBot

# 1. Start WebUI (LaunchAgent manages this)
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist

# 2. Start Trading Bot
python3 -m bot.run &

# 3. Start Guardian Bot
python3 -m bot.guardian.guardian_bot &

# 4. Verify
ps aux | grep "WorkingBot" | grep python | grep -v grep
curl http://localhost:5555/api/health
```

### **WorkingBot-demo (Testnet)**

```bash
cd /Users/ssr/Projects/WorkingBot-demo

# 1. Start Demo WebUI
python3 webui/backend/app.py &

# 2. Start Demo Bot (if needed)
python3 -m bot.run &

# 3. Verify
ps aux | grep "WorkingBot-demo" | grep python | grep -v grep
curl http://localhost:5556/api/health
```

---

## 🛑 SHUTDOWN PROCEDURES

### **WorkingBot (Main)**

```bash
cd /Users/ssr/Projects/WorkingBot

# Kill main bot processes only
pkill -f "/Users/ssr/Projects/WorkingBot/bot/run.py"
pkill -f "/Users/ssr/Projects/WorkingBot/bot/guardian"

# WebUI managed by LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.plist

# Clean locks
rm -f .bot_instance*.lock .heartbeat .webui_instance.lock
```

### **WorkingBot-demo**

```bash
cd /Users/ssr/Projects/WorkingBot-demo

# Kill demo processes only
pkill -f "/Users/ssr/Projects/WorkingBot-demo"

# Clean locks
rm -f .bot_instance*.lock .heartbeat .webui_instance.lock
```

---

## 🔍 VERIFICATION

### **Check Both Are Running Independently**

```bash
# Check ports
lsof -nP -iTCP -sTCP:LISTEN | grep -E "5555|5556"
# Should show:
# Python  *:5555 (WorkingBot)
# Python  *:5556 (WorkingBot-demo)

# Check processes
ps aux | grep "WorkingBot" | grep python | grep -v grep
# Should clearly show separate project paths

# Test APIs
curl http://localhost:5555/api/health  # Main
curl http://localhost:5556/api/health  # Demo
```

---

## ⚠️ COMMON ISSUES & SOLUTIONS

### **Issue 1: Port Conflict**
**Symptom:** "Address already in use" error  
**Solution:**
```bash
# Find what's using the port
lsof -i :5555
# Kill specific process
kill -9 <PID>
```

### **Issue 2: Demo Processes Showing in Main WebUI**
**Symptom:** See WorkingBot-demo processes in main dashboard  
**Solution:** Already fixed! WebUI filters by project directory now.

### **Issue 3: Both Using Same Config**
**Symptom:** Demo bot tries to trade live  
**Solution:** Verify `TRADING_MODE` in each `grid_config.env`

### **Issue 4: Duplicate Bot Processes**
**Symptom:** Multiple bot.run processes for same project  
**Solution:**
```bash
# Kill all bots for that project
cd /Users/ssr/Projects/WorkingBot
pkill -f "$(pwd)/bot/run.py"
# Restart once
python3 -m bot.run &
```

---

## 📊 MONITORING

### **Check Status Regularly**

```bash
# Quick status script
cat << 'EOF' > /Users/ssr/check_both_bots.sh
#!/bin/bash
echo "=== WorkingBot (Main) ==="
echo "Port 5555: $(lsof -i :5555 | wc -l) process(es)"
echo "Processes: $(ps aux | grep '/WorkingBot/.*python' | grep -v demo | grep -v grep | wc -l)"

echo ""
echo "=== WorkingBot-demo ==="
echo "Port 5556: $(lsof -i :5556 | wc -l) process(es)"
echo "Processes: $(ps aux | grep '/WorkingBot-demo/.*python' | grep -v grep | wc -l)"
EOF

chmod +x /Users/ssr/check_both_bots.sh
```

Run: `/Users/ssr/check_both_bots.sh`

---

## 🎓 BEST PRACTICES

1. **Always use full paths** when starting processes to avoid confusion
2. **Check current directory** before running commands
3. **Use separate terminal windows** for each project
4. **Name terminal tabs** appropriately (Main / Demo)
5. **Monitor logs separately**:
   - Main: `tail -f /Users/ssr/Projects/WorkingBot/bot.log`
   - Demo: `tail -f /Users/ssr/Projects/WorkingBot-demo/bot.log`

---

## 🔐 SECURITY NOTES

- **Never share API keys** between projects
- **Demo uses testnet** - no real money
- **Main uses live trading** - real money!
- Keep `secrets/api_keys.env` separate for each project

---

## ✅ SEPARATION VERIFICATION CHECKLIST

- [ ] Different ports (5555 vs 5556)
- [ ] Different lock files
- [ ] Different runtime state files
- [ ] Different trading modes
- [ ] Different API keys
- [ ] WebUI shows only own processes
- [ ] Can run both simultaneously
- [ ] Stopping one doesn't affect other
- [ ] Each has independent logs

---

**Last Updated:** November 10, 2025  
**Status:** ✅ Complete Separation Achieved
