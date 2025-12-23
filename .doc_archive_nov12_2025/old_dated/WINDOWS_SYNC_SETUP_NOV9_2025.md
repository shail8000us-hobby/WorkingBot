# Windows Sync & Setup Guide - November 9, 2025

## 🎯 Quick Sync from Mac (Method 1: Git - RECOMMENDED)

### Step 1: Pull Latest Changes on Windows

Open **PowerShell** on Windows and run:

```powershell
# Navigate to WorkingBot directory
cd D:\WorkingBot

# Pull latest changes from Mac
git pull origin production-v2.0
```

**Expected Output:**
```
Updating 3cb2361..b2fb3c3
Fast-forward
 bot_command_center.sh              | 350 ++++++++++++++++
 fix_bot_instance_lock.sh           | 200 ++++++++++
 watch_bot_logs.sh                  | 215 ++++++++++
 ... (12 files changed, 2673 insertions(+), 54 deletions(-))
```

---

## 🚀 Setup on Windows (After Sync)

### 1. Install/Update Python Dependencies

```powershell
cd D:\WorkingBot
pip install -r requirements.txt
```

### 2. Install/Update Node Dependencies

```powershell
cd D:\WorkingBot\webui\frontend
npm install
```

### 3. Install PM2 (if not already installed)

```powershell
npm install -g pm2
npm install -g pm2-windows-startup

# Enable PM2 startup
pm2-startup install
```

### 4. Build Frontend

```powershell
cd D:\WorkingBot\webui\frontend
npm run build
```

### 5. Update Configuration Files

#### A. Update `grid_config.env` for Windows paths
```powershell
# Edit grid_config.env
notepad D:\WorkingBot\grid_config.env
```

**Change these lines (if needed):**
```ini
# Paths should use forward slashes or double backslashes
LOG_DIR=D:/WorkingBot/bot/logs
STATE_DIR=D:/WorkingBot/bot/state
REPORTS_DIR=D:/WorkingBot/reports
```

#### B. Set up API keys (if not already done)
```powershell
# Copy template
copy D:\WorkingBot\secrets\api_keys.env.template D:\WorkingBot\secrets\api_keys.env

# Edit with your keys
notepad D:\WorkingBot\secrets\api_keys.env
```

---

## 📋 Important Files Synced from Mac

### New Scripts (converted for Windows):
- `bot_command_center.sh` → Use with Git Bash or WSL
- `fix_bot_instance_lock.sh` → Use with Git Bash or WSL
- `watch_bot_logs.sh` → Use with Git Bash or WSL
- `sync_backend_frontend.sh` → Use with Git Bash or WSL
- `PM2_LOG_COMMANDS.sh` → Use with Git Bash or WSL
- `disable_telegram_alerts.sh` → Use with Git Bash or WSL

### Documentation:
- `BOT_RESTART_COMMANDS_UPDATE_NOV9_2025.md` ✅
- `BOT_INSTANCE_LOCK_FIX_ANALYSIS.md` ✅
- `FIX_TELEGRAM_404_ERRORS.md` ✅
- `BACKEND_FRONTEND_BOT_LOGS_QUICK_REF.md` ✅

### Updated Code:
- `webui/frontend/src/components/CommandKnowledgeBase.js` - 80+ commands
- `bot/safety/single_instance_lock.py` - Enhanced lock validation

---

## 🤖 Starting Bot on Windows

### Method 1: PM2 (Recommended)

```powershell
cd D:\WorkingBot

# Start trading bot
pm2 start ecosystem.config.js --only gridbot-live

# Start guardian
pm2 start ecosystem.config.js --only guardian-live

# Start heartbeat
pm2 start ecosystem.config.js --only heartbeat

# Check status
pm2 status

# Save PM2 state (auto-restart on reboot)
pm2 save
```

### Method 2: Direct Python (Development)

```powershell
cd D:\WorkingBot
python -m bot.run
```

---

## 🖥️ Starting WebUI on Windows

### Start Backend

```powershell
cd D:\WorkingBot\webui\backend
python app.py
```

**Backend will start on:** http://localhost:5555

### Start Frontend (Dev Mode)

```powershell
cd D:\WorkingBot\webui\frontend
npm start
```

**Frontend dev server:** http://localhost:3000 (proxies to 5555)

### Production Mode

```powershell
# Backend serves built frontend
cd D:\WorkingBot\webui\backend
python app.py

# Access: http://localhost:5555
```

---

## 🔧 Windows-Specific PM2 Commands

```powershell
# View all processes
pm2 list

# View logs
pm2 logs gridbot-live

# View logs (last 50 lines, then stop)
pm2 logs gridbot-live --lines 50 --nostream

# Stop bot
pm2 stop gridbot-live

# Restart bot
pm2 restart gridbot-live

# Real-time monitor
pm2 monit

# View detailed info
pm2 describe gridbot-live

# Reset restart counter
pm2 reset gridbot-live

# Stop all
pm2 stop all

# Start all
pm2 start all
```

---

## 🛠️ Converting Mac Scripts for Windows

### Option 1: Use Git Bash (Comes with Git for Windows)

```bash
# Open Git Bash and run Mac scripts directly
cd /d/WorkingBot
./bot_command_center.sh
```

### Option 2: Use WSL (Windows Subsystem for Linux)

```bash
# In WSL terminal
cd /mnt/d/WorkingBot
./bot_command_center.sh
```

### Option 3: PowerShell Equivalents

#### Fix Instance Lock (PowerShell)
```powershell
# Stop PM2 processes
pm2 stop all

# Remove lock files
Remove-Item D:\WorkingBot\.bot_instance_*.lock -ErrorAction SilentlyContinue

# Start bot
pm2 start gridbot-live
pm2 list
```

#### Watch Logs (PowerShell)
```powershell
# Bot logs
Get-Content D:\WorkingBot\bot\logs\bot.log -Wait -Tail 50

# PM2 logs
pm2 logs gridbot-live --lines 50

# All PM2 logs
pm2 logs --lines 30
```

#### Sync Backend/Frontend (PowerShell)
```powershell
# Restart backend
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
cd D:\WorkingBot\webui\backend
Start-Process python -ArgumentList "app.py" -NoNewWindow

# Rebuild frontend
cd D:\WorkingBot\webui\frontend
npm run build
```

---

## 🔍 Troubleshooting on Windows

### Issue: Bot Won't Start (Instance Lock)

```powershell
# 1. Check if bot is already running
Get-Process | Where-Object {$_.CommandLine -like "*bot.run*"}

# 2. Stop PM2
pm2 stop all

# 3. Remove lock files
Remove-Item D:\WorkingBot\.bot_instance_*.lock

# 4. Start fresh
pm2 start gridbot-live
pm2 status
```

### Issue: Port 5555 Already in Use

```powershell
# Find what's using port 5555
netstat -ano | findstr :5555

# Kill the process (use PID from above)
Stop-Process -Id <PID> -Force

# Or kill all Python processes
Stop-Process -Name "python" -Force
```

### Issue: Frontend Won't Build

```powershell
# Clean and reinstall
cd D:\WorkingBot\webui\frontend
Remove-Item node_modules -Recurse -Force
Remove-Item package-lock.json
npm install
npm run build
```

### Issue: PM2 Not Working

```powershell
# Reinstall PM2
npm uninstall -g pm2
npm install -g pm2
npm install -g pm2-windows-startup
pm2-startup install
```

---

## 📊 Check System Status on Windows

```powershell
# PM2 status
pm2 status

# Backend health
Invoke-WebRequest -Uri http://localhost:5555/api/health | Select-Object -ExpandProperty Content

# Bot processes
Get-Process | Where-Object {$_.Name -eq "python"}

# Check specific port
netstat -ano | findstr :5555
```

---

## 🔄 Regular Sync from Mac

### Daily Sync (Pull from Git)

```powershell
cd D:\WorkingBot
git pull origin production-v2.0
```

### After Config Changes

```powershell
# Pull changes
git pull origin production-v2.0

# Restart bot (if running)
pm2 restart gridbot-live

# Rebuild frontend (if WebUI changed)
cd D:\WorkingBot\webui\frontend
npm run build
```

---

## 📁 Important Windows Paths

| Purpose | Path |
|---------|------|
| Project Root | `D:\WorkingBot` |
| Bot Logs | `D:\WorkingBot\bot\logs\bot.log` |
| Guardian Logs | `D:\WorkingBot\bot\logs\guardian.log` |
| WebUI Backend | `D:\WorkingBot\webui\backend\app.py` |
| WebUI Frontend | `D:\WorkingBot\webui\frontend` |
| Config | `D:\WorkingBot\grid_config.env` |
| API Keys | `D:\WorkingBot\secrets\api_keys.env` |
| PM2 Logs | `%USERPROFILE%\.pm2\logs\` |

---

## ⚡ Quick Start Commands (Copy-Paste)

### Full Setup (First Time)
```powershell
cd D:\WorkingBot
git pull origin production-v2.0
pip install -r requirements.txt
cd webui\frontend
npm install
npm run build
cd ..\..
pm2 start ecosystem.config.js
pm2 save
```

### Daily Start
```powershell
cd D:\WorkingBot
pm2 start all
pm2 logs gridbot-live
```

### Daily Stop
```powershell
pm2 stop all
```

### Check Everything
```powershell
pm2 status
Invoke-WebRequest http://localhost:5555/api/health
Get-Process | Where-Object {$_.Name -eq "python"}
```

---

## 🎉 Success Criteria

After sync, you should see:

✅ **Git Pull:** No errors, shows updated files  
✅ **PM2 Status:** `gridbot-live`, `guardian-live`, `heartbeat` all **online**  
✅ **Backend Health:** `{"status": "healthy"}`  
✅ **WebUI:** Accessible at http://localhost:5555  
✅ **"Know Your Bot":** Shows 80+ commands in WebUI  
✅ **No Lock Errors:** Bot starts without instance lock errors  

---

## 📞 Need Help?

1. **Check logs:** `pm2 logs gridbot-live --lines 100`
2. **Check status:** `pm2 status`
3. **View errors:** `Get-Content D:\WorkingBot\bot\logs\bot.log -Tail 50`
4. **Fix locks:** `Remove-Item D:\WorkingBot\.bot_instance_*.lock`

---

**Last Updated:** November 9, 2025  
**Commit:** b2fb3c370  
**Branch:** production-v2.0  
**Status:** ✅ Ready for Windows Sync
