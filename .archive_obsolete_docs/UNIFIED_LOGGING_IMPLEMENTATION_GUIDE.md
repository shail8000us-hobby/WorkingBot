# 🔄 UNIFIED LOGGING IMPLEMENTATION GUIDE
## Guardian + Trading Bot Combined Logs

**User Requirement**: "whenever an user start the bot guardian and trading bot logs should appear together"

---

## 📋 Overview

Currently, Guardian and Trading Bot run as separate processes with separate log outputs. This guide implements **unified log viewing** so users see both logs together in real-time.

---

## 🎯 Solution: PM2 Process Manager

**Why PM2**:
- ✅ Already installed in project
- ✅ Manages multiple processes
- ✅ Combines log output automatically
- ✅ Auto-restart on crash
- ✅ Process monitoring dashboard
- ✅ Zero code changes required

---

## 🛠️ Implementation

### Step 1: Create PM2 Ecosystem Config

Create file: `ecosystem.config.js`

```javascript
module.exports = {
  apps: [
    {
      name: 'guardian',
      script: 'bot/guardian/guardian_bot.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      
      // Logging configuration
      out_file: './logs/guardian.log',
      error_file: './logs/guardian_error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      
      // Auto-restart configuration
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      
      // Environment
      env: {
        PYTHONUNBUFFERED: '1'  // Disable Python output buffering
      },
      
      // Graceful shutdown
      kill_timeout: 5000,
      
      // Advanced features
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    },
    
    {
      name: 'gridbot',
      script: 'bot_launcher.py',
      interpreter: 'python3',
      cwd: '/Users/ssr/Projects/WorkingBot',
      
      // Logging configuration
      out_file: './logs/gridbot.log',
      error_file: './logs/gridbot_error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      
      // Auto-restart configuration
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      
      // Environment
      env: {
        PYTHONUNBUFFERED: '1'  // Disable Python output buffering
      },
      
      // Graceful shutdown
      kill_timeout: 5000,
      
      // Advanced features
      watch: false,
      instances: 1,
      exec_mode: 'fork'
    }
  ]
};
```

---

### Step 2: Create Startup Script

Create file: `start_trading_system.sh`

```bash
#!/bin/bash
#
# Unified startup script for Guardian + Trading Bot
# Shows combined logs from both processes
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Trading System..."
echo ""

# Create logs directory
mkdir -p logs

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 not found. Installing..."
    npm install -g pm2
fi

# Stop any existing processes
echo "🧹 Cleaning up existing processes..."
pm2 delete all 2>/dev/null || true

# Start Guardian + GridBot via PM2
echo "🛡️  Starting Guardian..."
echo "🤖 Starting GridBot..."
pm2 start ecosystem.config.js

echo ""
echo "✅ Trading System Started!"
echo ""
echo "📊 Process Status:"
pm2 status

echo ""
echo "📋 View combined logs:"
echo "   pm2 logs --lines 50"
echo ""
echo "🔄 Follow live logs:"
echo "   pm2 logs"
echo ""
echo "⏸️  Stop all:"
echo "   pm2 stop all"
echo ""
echo "🔄 Restart all:"
echo "   pm2 restart all"
echo ""
echo "🚨 Emergency stop:"
echo "   pm2 delete all"
echo ""

# Auto-show logs (can press Ctrl+C to exit)
echo "Showing combined logs (press Ctrl+C to exit)..."
sleep 2
pm2 logs --lines 100
```

Make executable:
```bash
chmod +x start_trading_system.sh
```

---

### Step 3: Create Stop Script

Create file: `stop_trading_system.sh`

```bash
#!/bin/bash
#
# Stop Guardian + Trading Bot gracefully
#

echo "🛑 Stopping Trading System..."
pm2 stop all

echo ""
echo "✅ All processes stopped"
echo ""
echo "📊 Final status:"
pm2 status

echo ""
echo "To completely remove processes from PM2:"
echo "   pm2 delete all"
```

Make executable:
```bash
chmod +x stop_trading_system.sh
```

---

### Step 4: Create Status Script

Create file: `status_trading_system.sh`

```bash
#!/bin/bash
#
# Check status of Guardian + Trading Bot
#

echo "📊 Trading System Status"
echo "=" * 80
echo ""

# PM2 status
pm2 status

echo ""
echo "💾 Memory Usage:"
pm2 jlist | jq -r '.[] | "\(.name): \(.monit.memory / 1024 / 1024 | floor)MB"'

echo ""
echo "⏱️  Uptime:"
pm2 jlist | jq -r '.[] | "\(.name): \(.pm2_env.status) (PID: \(.pid))"'

echo ""
echo "📋 Recent Logs:"
echo "   Guardian: tail -20 logs/guardian.log"
echo "   GridBot:  tail -20 logs/gridbot.log"
echo ""
echo "🔍 View live logs:"
echo "   pm2 logs"
```

Make executable:
```bash
chmod +x status_trading_system.sh
```

---

## 📝 Usage

### Start Trading System
```bash
./start_trading_system.sh
```

**Output**:
```
🚀 Starting Trading System...

🧹 Cleaning up existing processes...
🛡️  Starting Guardian...
🤖 Starting GridBot...

✅ Trading System Started!

📊 Process Status:
┌─────┬──────────┬─────────────┬─────────┬─────────┬──────────┬────────┬──────┬───────────┬──────────┬──────────┬──────────┬──────────┐
│ id  │ name     │ namespace   │ version │ mode    │ pid      │ uptime │ ↺    │ status    │ cpu      │ mem      │ user     │ watching │
├─────┼──────────┼─────────────┼─────────┼─────────┼──────────┼────────┼──────┼───────────┼──────────┼──────────┼──────────┼──────────┤
│ 0   │ guardian │ default     │ N/A     │ fork    │ 12345    │ 2s     │ 0    │ online    │ 0%       │ 45.2mb   │ ssr      │ disabled │
│ 1   │ gridbot  │ default     │ N/A     │ fork    │ 12346    │ 2s     │ 0    │ online    │ 0%       │ 52.1mb   │ ssr      │ disabled │
└─────┴──────────┴─────────────┴─────────┴─────────┴──────────┴────────┴──────┴───────────┴──────────┴──────────┴──────────┴──────────┘

Showing combined logs (press Ctrl+C to exit)...

[GUARDIAN] 2025-11-17 18:30:15 | INFO     | 🛡️  Guardian Bot v3.0 Starting...
[GUARDIAN] 2025-11-17 18:30:15 | INFO     | 📊 Monitoring: BTC-USD-PERP
[GRIDBOT]  2025-11-17 18:30:16 | INFO     | 🤖 AsyncGridBot Starting...
[GRIDBOT]  2025-11-17 18:30:16 | INFO     | 📊 Mode: LONG | Symbol: BTC-USD-PERP
[GUARDIAN] 2025-11-17 18:30:16 | INFO     | ✅ Risk limits: PASS
[GUARDIAN] 2025-11-17 18:30:16 | INFO     | 📤 Signal: GO (published to SQL)
[GRIDBOT]  2025-11-17 18:30:17 | INFO     | 🟢 Guardian signal: GO
[GRIDBOT]  2025-11-17 18:30:17 | INFO     | ✅ Initial order placed @ $95,000
...
```

**Press Ctrl+C to exit log view** (processes keep running in background)

---

### View Live Logs Anytime
```bash
pm2 logs
```

Shows both Guardian and GridBot logs interleaved in real-time.

**View specific process**:
```bash
pm2 logs guardian
pm2 logs gridbot
```

**View last N lines**:
```bash
pm2 logs --lines 50
```

---

### Check Status
```bash
./status_trading_system.sh
```

OR:

```bash
pm2 status
```

---

### Stop Trading System
```bash
./stop_trading_system.sh
```

OR:

```bash
pm2 stop all
```

**Completely remove from PM2**:
```bash
pm2 delete all
```

---

### Restart After Code Changes
```bash
pm2 restart all
```

**Restart specific process**:
```bash
pm2 restart guardian
pm2 restart gridbot
```

---

## 🎨 Advanced PM2 Features

### 1. **Web Dashboard**
```bash
pm2 plus
```

Opens web-based monitoring dashboard with:
- Real-time CPU/memory graphs
- Log viewer
- Process management
- Alert notifications

---

### 2. **Save Process List** (Auto-restart on system reboot)
```bash
pm2 save
pm2 startup
```

PM2 will auto-start Guardian + GridBot after system reboot.

---

### 3. **Log Rotation** (Prevent log files from growing indefinitely)
```bash
pm2 install pm2-logrotate

# Configure rotation
pm2 set pm2-logrotate:max_size 10M        # Rotate at 10MB
pm2 set pm2-logrotate:retain 7            # Keep 7 rotated files
pm2 set pm2-logrotate:compress true       # Compress old logs
```

---

### 4. **Monitoring Metrics**
```bash
# CPU and memory usage
pm2 monit
```

Shows real-time resource usage in terminal UI.

---

### 5. **Export Logs to File**
```bash
pm2 logs --json > trading_system.json
```

---

## 📂 Log File Locations

PM2 creates individual log files:

```
logs/
├── guardian.log         # Guardian stdout
├── guardian_error.log   # Guardian stderr
├── gridbot.log          # GridBot stdout
└── gridbot_error.log    # GridBot stderr
```

**View individual logs**:
```bash
tail -f logs/guardian.log
tail -f logs/gridbot.log
```

**Search logs**:
```bash
grep "ERROR" logs/*.log
grep "Guardian signal: STOP" logs/gridbot.log
```

---

## 🔧 Troubleshooting

### Issue: Processes Not Starting

**Check PM2 logs**:
```bash
pm2 logs --err
```

**Check Python interpreter**:
```bash
which python3
```

Update `interpreter` in `ecosystem.config.js` if needed.

---

### Issue: Logs Not Showing

**Check PYTHONUNBUFFERED**:
```javascript
env: {
  PYTHONUNBUFFERED: '1'  // Must be '1' not true
}
```

**Force flush in Python** (if needed):
Add to bot code:
```python
import sys
sys.stdout.flush()
```

---

### Issue: Process Keeps Restarting

**Check restart count**:
```bash
pm2 status
```

Look at "restart" column.

**View error logs**:
```bash
pm2 logs gridbot --err
```

**Increase min_uptime**:
```javascript
min_uptime: '30s',  // Increase from 10s
```

---

### Issue: PM2 Not Found

**Install PM2**:
```bash
npm install -g pm2
```

**If npm not found**:
```bash
# macOS
brew install node

# Ubuntu/Debian
sudo apt install nodejs npm
```

---

## 🎯 Next Steps

1. ✅ Create `ecosystem.config.js`
2. ✅ Create startup/stop scripts
3. ✅ Make scripts executable
4. ✅ Test startup
5. ✅ Verify combined logs
6. ✅ Update documentation

---

## 📚 PM2 Quick Reference

| Command | Description |
|---------|-------------|
| `pm2 start ecosystem.config.js` | Start all processes |
| `pm2 stop all` | Stop all processes |
| `pm2 restart all` | Restart all processes |
| `pm2 delete all` | Remove all processes from PM2 |
| `pm2 logs` | View combined live logs |
| `pm2 logs --lines 50` | View last 50 lines |
| `pm2 logs guardian` | View Guardian logs only |
| `pm2 status` | Show process status |
| `pm2 monit` | Real-time monitoring UI |
| `pm2 save` | Save process list |
| `pm2 startup` | Enable auto-start on boot |
| `pm2 flush` | Clear all logs |

---

## ✅ Advantages Over Manual Launching

| Feature | Manual Launch | PM2 |
|---------|--------------|-----|
| **Unified Logs** | ❌ Separate terminals | ✅ Combined view |
| **Auto-Restart** | ❌ Manual restart | ✅ Automatic |
| **Background Running** | ❌ Terminal must stay open | ✅ Runs in background |
| **Process Monitoring** | ❌ Manual `ps` commands | ✅ Built-in dashboard |
| **Log Management** | ❌ Manual file handling | ✅ Automatic rotation |
| **Startup on Boot** | ❌ Manual configuration | ✅ One command |
| **Resource Monitoring** | ❌ Manual `top` | ✅ Real-time graphs |

---

**End of Unified Logging Guide**

**Status**: ✅ READY FOR IMPLEMENTATION
