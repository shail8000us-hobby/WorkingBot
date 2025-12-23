# Unified Bot + Shadow Mode Control

**Single command to manage both threaded bot and shadow mode together!**

## 🎯 Your Workflow

1. **Configure**: Use WebUI (http://localhost:5555) to change settings
2. **Start/Stop**: Use terminal commands
3. **Monitor**: Built-in dashboard shows both systems

---

## 🚀 Quick Commands

### Interactive Menu (Recommended)
```bash
./scripts/unified_bot_control.sh
```

### Direct Commands
```bash
# Start both systems
./scripts/unified_bot_control.sh start

# Stop both systems
./scripts/unified_bot_control.sh stop

# Restart both systems
./scripts/unified_bot_control.sh restart

# Show status
./scripts/unified_bot_control.sh status

# View logs
./scripts/unified_bot_control.sh logs

# Open dashboard
./scripts/unified_bot_control.sh dashboard
```

---

## 📋 What Happens

### When You Run `./scripts/unified_bot_control.sh start`:

1. **Cleans up** any stale lock files
2. **Starts threaded bot** via PM2 (gridbot-live)
3. **Waits 10 seconds** for initialization
4. **Starts shadow mode** in background
5. **Shows status** of both systems

### When You Run `./scripts/unified_bot_control.sh stop`:

1. **Stops shadow mode** gracefully
2. **Stops threaded bot** via PM2
3. **Cleans up** lock files
4. **Shows final status**

---

## 🎨 Interactive Menu

```
╔════════════════════════════════════════════════════════╗
║                                                        ║
║    🤖 Unified Bot + Shadow Mode Controller 🤖         ║
║                                                        ║
╚════════════════════════════════════════════════════════╝

═══ System Status ═══
Threaded Bot:    RUNNING (PM2: gridbot-live)
Shadow Mode:     RUNNING (PID: 12345)
WebUI Backend:   RUNNING

═══ Actions ═══
1) 🚀 Start Both (Threaded + Shadow)
2) 🛑 Stop Both
3) 🔄 Restart Both
4) 📊 View Logs
5) 📈 Shadow Mode Dashboard
6) 🔍 Status Only
7) ❌ Exit

Select option (1-7):
```

---

## 🖥️ WebUI Configuration Control

While bots are running, you can change configuration via WebUI:

**URL**: http://localhost:5555

**What You Can Change:**
- Grid parameters (upper/lower bounds, levels)
- Trade amounts
- Stop loss / Take profit
- Volatility settings
- Enable/disable features

**Changes are picked up** by the threaded bot via hot-reload mechanism.

---

## 📊 Monitoring

### Real-Time Status
```bash
./scripts/unified_bot_control.sh status
```

### Shadow Mode Dashboard
```bash
./scripts/unified_bot_control.sh dashboard
```

### View Logs
```bash
# Interactive log viewer
./scripts/unified_bot_control.sh logs

# Or directly:
tail -f logs/shadow_mode.log        # Shadow mode
pm2 logs gridbot-live               # Threaded bot
```

---

## 💡 Typical Testing Workflow

### Day 1: Setup
```bash
# 1. Start WebUI (if not running)
pm2 start ecosystem.config.js --only webui-backend

# 2. Configure bot via WebUI
# Open http://localhost:5555

# 3. Start unified system
./scripts/unified_bot_control.sh start

# 4. Monitor
./scripts/unified_bot_control.sh dashboard
```

### Day 2-7: Adjust & Monitor
```bash
# Adjust configuration via WebUI
# No need to restart!

# Check status anytime
./scripts/unified_bot_control.sh status

# View shadow mode progress
./scripts/unified_bot_control.sh dashboard
```

### Day 7+: Review Results
```bash
# View shadow mode report
cat logs/shadow_mode_report.json | jq '.'

# If match rate ≥99.9%, proceed to cutover
# Otherwise, fix issues and restart
```

---

## 🔧 Advanced Usage

### Start with Custom Duration
```bash
# Edit the script to change duration:
# Line 101: --duration 24  → change to desired hours
```

### Background Mode
```bash
# Start and exit terminal
./scripts/unified_bot_control.sh start
# Systems keep running in background

# Check status later
./scripts/unified_bot_control.sh status
```

### Auto-start on Boot
```bash
# Add to crontab
@reboot /Users/ssr/Projects/WorkingBot/scripts/unified_bot_control.sh start
```

---

## 🛡️ Safety Features

✅ **Clean Shutdown**
- Stops shadow mode gracefully
- Stops bot via PM2 (graceful shutdown)
- Cleans up all lock files

✅ **Status Tracking**
- Always know what's running
- PID files for process management
- Clear status messages

✅ **Log Management**
- All logs saved to files
- Easy access via menu
- No log rotation issues

✅ **WebUI Integration**
- Configuration changes picked up automatically
- No restart needed for most settings
- Visual feedback on status

---

## 📝 Files Created

```
scripts/
  └── unified_bot_control.sh    # Main control script

.pids/
  ├── shadow_mode.pid           # Shadow mode process ID
  └── threaded_bot.pid          # Threaded bot PID (if needed)

logs/
  ├── shadow_mode.log           # Shadow mode output
  └── shadow_mode_report.json   # Final comparison report
```

---

## 🆘 Troubleshooting

### Issue: "Threaded bot won't start"
```bash
# Clean PM2 state
pm2 delete gridbot-live
pm2 start ecosystem.config.js --only gridbot-live
```

### Issue: "Shadow mode keeps restarting"
```bash
# Check shadow mode logs
tail -100 logs/shadow_mode.log

# Manually start to see errors
python3 scripts/migrate_to_async.py --mode shadow --duration 1
```

### Issue: "Can't access WebUI"
```bash
# Check if WebUI is running
ps aux | grep "webui/backend/app.py"

# Start WebUI if needed
pm2 start ecosystem.config.js --only webui-backend
```

---

## ⚡ Quick Reference

| Command | Purpose |
|---------|---------|
| `./scripts/unified_bot_control.sh` | Interactive menu |
| `./scripts/unified_bot_control.sh start` | Start both |
| `./scripts/unified_bot_control.sh stop` | Stop both |
| `./scripts/unified_bot_control.sh restart` | Restart both |
| `./scripts/unified_bot_control.sh status` | Check status |
| `./scripts/unified_bot_control.sh logs` | View logs |
| `./scripts/unified_bot_control.sh dashboard` | Open dashboard |

---

## 🎯 Perfect for Testing!

This unified system is **ideal for your workflow**:

1. ✅ **Single command** to start/stop both systems
2. ✅ **WebUI for configuration** (visual, easy)
3. ✅ **Terminal for control** (fast, scriptable)
4. ✅ **No conflicts** - both systems isolated
5. ✅ **Easy monitoring** - built-in dashboard
6. ✅ **Safe shutdown** - graceful cleanup

**Start testing:**
```bash
./scripts/unified_bot_control.sh
```

Choose option 1 to start both systems! 🚀
