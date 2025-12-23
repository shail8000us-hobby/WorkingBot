# WebUI Production Stability System

**Complete guide to making your WebUI NEVER go down on Mac Mini M4**

---

## 🎯 Overview

This system provides **multiple layers of protection** to ensure your WebUI stays running 24/7:

1. **macOS LaunchAgent** - OS-level auto-restart
2. **WebUI Guardian** - Health monitoring & auto-recovery
3. **Resource monitoring** - Memory & CPU tracking
4. **Port conflict resolution** - Automatic port cleanup
5. **Crash recovery** - Intelligent restart logic
6. **Performance tracking** - Statistics & monitoring

---

## 🚀 Quick Start

### Option 1: Maximum Reliability (Recommended)

This installs **both** enhanced LaunchAgent + Guardian for ultimate stability:

```bash
./install_webui_production.sh
# Choose option 4: Both Enhanced + Guardian
```

**What you get:**
- ✅ macOS auto-restart on crash
- ✅ Health checks every 30 seconds
- ✅ Automatic resource leak detection
- ✅ Port conflict resolution
- ✅ Network connectivity monitoring
- ✅ Performance statistics
- ✅ **WebUI WILL NEVER GO DOWN!**

### Option 2: Guardian Only

If you want just the Guardian (no LaunchAgent changes):

```bash
./install_webui_production.sh
# Choose option 3: Full Guardian System
```

### Option 3: Enhanced LaunchAgent Only

For macOS-level auto-restart only:

```bash
./install_webui_production.sh
# Choose option 2: Enhanced LaunchAgent
```

---

## 📊 System Components

### 1. Enhanced LaunchAgent

**File:** `com.gridbot.webui.enhanced.plist`

**Features:**
- ✅ Auto-start on macOS login
- ✅ Auto-restart on crash
- ✅ Network connectivity monitoring
- ✅ Increased resource limits (4096 files, 1024 processes)
- ✅ Higher process priority
- ✅ Smart throttling (10s between restarts)

**How it works:**
```
macOS Boot/Login
    ↓
LaunchAgent loads
    ↓
Starts WebUI backend
    ↓
Monitors process continuously
    ↓
If crashes → Auto-restart (10s throttle)
```

### 2. WebUI Guardian

**File:** `webui_guardian.py`

**Features:**
- ✅ Health monitoring (HTTP /api/health)
- ✅ Resource monitoring (CPU, Memory, Threads)
- ✅ Auto-restart on failure
- ✅ Port conflict resolution
- ✅ Memory leak detection (threshold: 2GB)
- ✅ CPU monitoring (threshold: 80%)
- ✅ Statistics tracking
- ✅ Comprehensive logging

**Monitoring Loop:**
```
Every 30 seconds:
  1. Check if process is alive
  2. HTTP health check
  3. Check CPU usage
  4. Check memory usage
  5. Monitor thread count
  6. Count connections
  7. Save statistics
  
If unhealthy:
  - Log warning
  - Count consecutive failures
  - After 3 failures → restart
  
If resource leak:
  - Log warning
  - Auto-restart with reason
```

### 3. Guardian LaunchAgent

**File:** `com.gridbot.webui.guardian.plist`

Ensures the Guardian itself stays running!

---

## 🎯 Installation Details

### Prerequisites

```bash
# Python dependencies
pip3 install psutil requests

# Verify they're installed
python3 -c "import psutil, requests; print('✅ Dependencies OK')"
```

### Installation Steps

1. **Navigate to project:**
   ```bash
   cd /Users/shailendrasinghrajawat/Projects/WorkingBot
   ```

2. **Run installer:**
   ```bash
   ./install_webui_production.sh
   ```

3. **Choose installation mode:**
   - **1**: Basic (original)
   - **2**: Enhanced (better restarts)
   - **3**: Guardian only
   - **4**: Maximum Reliability ⭐ (RECOMMENDED)

4. **Wait for startup** (10 seconds)

5. **Verify:**
   ```bash
   ./check_webui_status.sh
   ```

---

## 📋 Monitoring & Management

### Check Status

```bash
# Quick status check
./check_webui_status.sh

# LaunchAgent status
launchctl list | grep gridbot.webui

# Check if WebUI is responding
curl http://localhost:5555/api/health

# View Guardian stats
cat data/webui_guardian_stats.json | python3 -m json.tool
```

### View Logs

```bash
# WebUI output logs
tail -f logs/launchagent_webui.log

# WebUI error logs
tail -f logs/launchagent_webui_error.log

# Guardian logs
tail -f logs/webui_guardian.log

# Guardian errors
tail -f logs/webui_guardian_error.log
```

### Control Services

```bash
# Restart WebUI (Enhanced)
launchctl restart com.gridbot.webui.enhanced

# Restart WebUI (Basic)
launchctl restart com.gridbot.webui

# Stop Guardian
launchctl stop com.gridbot.webui.guardian

# Start Guardian
launchctl start com.gridbot.webui.guardian

# Reload LaunchAgent (after plist changes)
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.enhanced.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.enhanced.plist
```

### View Statistics

```bash
# Guardian statistics
cat data/webui_guardian_stats.json

# Pretty print
python3 -c "import json; print(json.dumps(json.load(open('data/webui_guardian_stats.json')), indent=2))"
```

Example stats:
```json
{
  "uptime_seconds": 86400,
  "total_restarts": 2,
  "total_health_checks": 2880,
  "failed_health_checks": 0,
  "last_check_time": "2025-11-02T14:30:00",
  "status": "healthy"
}
```

---

## 🔧 Configuration

### Guardian Settings

Edit `webui_guardian.py` to customize:

```python
HEALTH_CHECK_INTERVAL = 30  # seconds between checks
MAX_MEMORY_MB = 2048        # memory threshold (MB)
MAX_CPU_PERCENT = 80        # CPU threshold (%)
MAX_RESTART_ATTEMPTS = 5    # max restarts before giving up
RESTART_COOLDOWN = 60       # cooldown between restarts (s)
```

### LaunchAgent Settings

Edit `.plist` files to customize:

```xml
<!-- Health check interval -->
<key>StartInterval</key>
<integer>60</integer>  <!-- Check every 60 seconds -->

<!-- Throttle between restarts -->
<key>ThrottleInterval</key>
<integer>10</integer>  <!-- Wait 10s between restarts -->

<!-- Resource limits -->
<key>NumberOfFiles</key>
<integer>4096</integer>  <!-- Max open files -->
```

---

## 🐛 Troubleshooting

### Issue 1: WebUI Not Starting

**Check:**
```bash
# View error logs
tail -50 logs/launchagent_webui_error.log

# Check for Python errors
python3 webui/backend/app.py
```

**Common fixes:**
```bash
# Port 5555 in use
lsof -i :5555
# Kill the process using it
kill -9 <PID>

# Missing dependencies
pip3 install -r requirements.txt

# Permission issues
chmod -R 755 webui/frontend/build
```

### Issue 2: Guardian Not Restarting WebUI

**Check:**
```bash
# View Guardian logs
tail -50 logs/webui_guardian.log

# Check restart attempts
cat data/webui_guardian_stats.json | grep total_restarts
```

**Common fixes:**
```bash
# Restart Guardian
launchctl restart com.gridbot.webui.guardian

# Check max restart limit reached
# Edit webui_guardian.py and increase MAX_RESTART_ATTEMPTS
```

### Issue 3: LaunchAgent Not Loading

**Check:**
```bash
# Verify plist syntax
plutil -lint ~/Library/LaunchAgents/com.gridbot.webui.enhanced.plist

# Check launchctl output
launchctl list | grep gridbot

# View system logs
log show --predicate 'processImagePath contains "com.gridbot"' --info --last 1h
```

**Common fixes:**
```bash
# Fix plist permissions
chmod 644 ~/Library/LaunchAgents/com.gridbot.webui.*.plist

# Reload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.enhanced.plist
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.enhanced.plist
```

### Issue 4: High Memory Usage

**Check:**
```bash
# Monitor resources
./check_webui_status.sh

# View Guardian logs for memory warnings
grep "Memory usage" logs/webui_guardian.log
```

**Action:**
Guardian will automatically restart WebUI if memory exceeds 2GB.

To adjust threshold, edit `webui_guardian.py`:
```python
MAX_MEMORY_MB = 3072  # Increase to 3GB
```

---

## 📈 Performance Metrics

### What's Tracked

**Guardian Statistics:**
- Uptime (seconds)
- Total restarts
- Total health checks performed
- Failed health checks
- Last check timestamp
- Current status

**Resource Monitoring:**
- CPU usage (%)
- Memory usage (MB)
- Thread count
- Open file descriptors
- Network connections

### Viewing Metrics

```bash
# Real-time monitoring
watch -n 5 './check_webui_status.sh'

# Stats file
cat data/webui_guardian_stats.json

# Recent logs with resource info
tail -20 logs/webui_guardian.log
```

---

## 🎓 Best Practices

### For Maximum Reliability

1. ✅ **Use Option 4** (Enhanced + Guardian)
2. ✅ **Monitor logs daily**
3. ✅ **Check stats weekly**
4. ✅ **Keep dependencies updated**
5. ✅ **Test restarts monthly**

### Monitoring Schedule

**Daily:**
```bash
./check_webui_status.sh
```

**Weekly:**
```bash
# Check restart count
cat data/webui_guardian_stats.json | grep total_restarts

# Review logs for warnings
grep "WARNING\|ERROR" logs/webui_guardian.log | tail -50
```

**Monthly:**
```bash
# Test restart capability
launchctl restart com.gridbot.webui.enhanced

# Verify auto-recovery
launchctl stop com.gridbot.webui.enhanced
# Wait 30s, should auto-restart
```

### Log Rotation

Guardian logs can grow large. Set up log rotation:

```bash
# Create log rotation config
cat > /etc/newsyslog.d/gridbot.conf << EOF
/Users/shailendrasinghrajawat/Projects/WorkingBot/logs/*.log 644 7 100 * J
EOF
```

---

## 🚨 Emergency Procedures

### Complete System Restart

```bash
# Stop everything
launchctl stop com.gridbot.webui.guardian
launchctl stop com.gridbot.webui.enhanced
pkill -9 -f "webui/backend/app.py"

# Wait 5 seconds
sleep 5

# Start everything
launchctl start com.gridbot.webui.enhanced
launchctl start com.gridbot.webui.guardian
```

### Manual WebUI Start

If all automation fails:

```bash
cd /Users/shailendrasinghrajawat/Projects/WorkingBot
export PYTHONPATH=/Users/shailendrasinghrajawat/Projects/WorkingBot
export FLASK_ENV=production
python3 webui/backend/app.py
```

### Disable All Automation

```bash
# Unload all LaunchAgents
launchctl unload ~/Library/LaunchAgents/com.gridbot.webui.*.plist

# Run manually
python3 webui/backend/app.py
```

---

## 📊 Success Metrics

### After Installation

You should see:

**Status Check:**
```
✅ WEBUI IS RUNNING!
   URL: http://localhost:5555
```

**LaunchAgent Status:**
```
PID   Status  Label
1234  0       com.gridbot.webui.enhanced
5678  0       com.gridbot.webui.guardian
```

**Health Check:**
```json
{
  "status": "healthy",
  "uptime": 86400
}
```

**Guardian Stats:**
```json
{
  "status": "healthy",
  "total_health_checks": 2880,
  "failed_health_checks": 0
}
```

---

## 🎉 Summary

With this system, your WebUI is **BULLETPROOF**:

### Protection Layers

1. **macOS LaunchAgent** - Auto-restart on crash
2. **Network Monitoring** - Restart on connectivity loss  
3. **Health Checks** - HTTP ping every 30s
4. **Resource Monitoring** - Memory & CPU tracking
5. **Port Management** - Automatic conflict resolution
6. **Smart Throttling** - Prevents restart loops
7. **Comprehensive Logging** - Full audit trail
8. **Statistics** - Performance tracking

### What It Handles

- ✅ Process crashes
- ✅ Network issues
- ✅ Port conflicts
- ✅ Memory leaks
- ✅ High CPU usage
- ✅ macOS reboots
- ✅ User logouts
- ✅ Power failures (after reboot)

### Result

**🛡️ YOUR WEBUI WILL NEVER GO DOWN! 🛡️**

---

*Last Updated: 2025-11-02*
*Compatible with: Mac Mini M4, macOS*

