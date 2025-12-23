# Mac → Windows GridBot Sync Guide (Nov 9, 2025)

## 🎯 Objective

Create a **mirror** of the GridBot project from Mac to Windows over LAN, syncing all critical bot brain and decision-making files while respecting OS-specific differences.

---

## 📋 System Information

### Mac (Source)
- **Location:** `/Users/ssr/Projects/WorkingBot`
- **OS:** macOS
- **Process Manager:** PM2
- **Python:** 3.9+

### Windows (Target)
- **Location:** `D:\Projects\WorkingBot`
- **OS:** Windows 10/11
- **Process Manager:** Windows Service or PM2 (if Node.js installed)
- **Python:** 3.9+
- **Connection:** LAN

---

## 🔄 Sync Methods

### Method 1: Automatic Sync Script (RECOMMENDED)

```bash
# On Mac
cd /Users/ssr/Projects/WorkingBot
./sync_to_windows.sh [windows-ip] [username]

# Example:
./sync_to_windows.sh 192.168.1.100 ssr
```

**What it syncs:**
- ✅ All bot brain files (`bot/strategy/`, `bot/api/`, etc.)
- ✅ All decision-making modules (7 core modules + handlers)
- ✅ Monitoring system (5 layers)
- ✅ Configuration files (`grid_config.env`)
- ✅ Documentation (AI_CONTEXT.md, etc.)
- ✅ WebUI backend (Python files)

**What it EXCLUDES:**
- ❌ `.sh` scripts (Mac-specific)
- ❌ `.plist` files (Mac LaunchAgent)
- ❌ Log files (machine-specific)
- ❌ Runtime state files (machine-specific)
- ❌ Lock files
- ❌ `.git/` (use git pull on Windows instead)

### Method 2: Git Pull (If Windows has Git)

```powershell
# On Windows PowerShell
cd D:\Projects\WorkingBot
git fetch origin
git pull origin production-v2.0
```

**Pros:**
- Fast and reliable
- Preserves Git history
- Easy rollback

**Cons:**
- Requires Git on Windows
- May include Mac-specific files (need to ignore)

### Method 3: Manual SMB Copy

```bash
# On Mac - Mount Windows share
mkdir -p /Volumes/WindowsBot
mount_smbfs //ssr@192.168.1.100/D$ /Volumes/WindowsBot

# Copy files
cp -r bot /Volumes/WindowsBot/Projects/WorkingBot/
cp grid_config.env /Volumes/WindowsBot/Projects/WorkingBot/
cp *.md /Volumes/WindowsBot/Projects/WorkingBot/

# Unmount
umount /Volumes/WindowsBot
```

---

## 📁 Critical Files to Sync

### 🧠 Bot Brain Files (MUST SYNC)

These are the core trading logic files:

```
bot/
├── run.py                              # Entry point
├── strategy/
│   ├── gridbot.py                      # Main orchestrator (538 lines)
│   ├── modules/
│   │   ├── grid_calculator.py          # Grid math
│   │   ├── position_manager.py         # State management
│   │   ├── fill_detector.py            # Fill detection
│   │   ├── order_manager.py            # Order operations
│   │   ├── reconciliation.py           # Exchange sync
│   │   ├── volatility_handler.py       # Volatility safety
│   │   └── websocket_handler.py        # Event routing
│   └── handlers/
│       ├── long_handler.py             # LONG mode logic
│       └── short_handler.py            # SHORT mode logic
├── api/
│   └── delta_client.py                 # Delta Exchange API
├── delta_websocket/
│   └── ws_manager.py                   # WebSocket manager
├── guardian/
│   └── guardian_bot.py                 # Loss protection
├── heartbeat/
│   └── monitor.py                      # Dead man's switch
├── volatility/
│   └── iv_rv_tracker.py                # IV/RV monitoring
├── config/
│   └── config_manager_core.py          # Configuration hot reload
├── safety/
│   ├── loss_limits.py                  # Loss limit validation
│   ├── blocker_tracker.py              # Safety tracker
│   └── single_instance_lock.py         # Prevent multiple bots
└── monitoring/
    ├── price_health.py                 # Layer 1: Price staleness
    ├── pre_order_logger.py             # Layer 2: Decision logging
    ├── tp_verification.py              # Layer 3: Orphan detection
    ├── anomaly_detection.py            # Layer 4: Pattern detection
    ├── predictive_display.py           # Layer 5: Next actions
    └── data_writer.py                  # WebUI integration
```

### ⚙️ Configuration Files

```
grid_config.env                         # Main configuration (1,535 lines)
secrets/api_keys.env                    # API credentials (MANUAL COPY - Security)
```

### 📚 Documentation Files

```
AI_CONTEXT.md                           # Complete system overview (4,835 lines)
BOT_BRAIN_ARCHITECTURE.md               # Module connections
AI_CRITICAL_RULES.md                    # Immutable rules
BOT_STRUCTURE.md                        # Technical reference
START_HERE.md                           # Quick start guide
USER_MANUAL.md                          # Configuration guide
PM2_COMPLETE_SYSTEM.md                  # PM2 documentation
```

### 🌐 WebUI Files (Backend)

```
webui/backend/
├── app.py                              # Flask backend (8,850 lines)
├── routes/
│   ├── __init__.py
│   ├── pm2.py                          # PM2 control
│   ├── bot_control.py                  # Bot start/stop
│   ├── config.py                       # Configuration API
│   ├── monitoring.py                   # Monitoring data
│   └── ... (other route files)
└── utils/
    ├── pm2_adapter.py                  # PM2 integration
    └── ... (other utilities)
```

**Note:** WebUI frontend (React) should be identical on both systems. Backend may need minor path adjustments.

---

## 🚫 Files to EXCLUDE (OS-Specific)

### Mac-Specific Files (Don't Sync)

```
*.sh                                    # Shell scripts
*.plist                                 # LaunchAgent files
launchd/                                # Mac services
scripts/start_tmux_daemon.sh            # Mac startup script
.DS_Store                               # Mac metadata
```

### Runtime Files (Don't Sync)

```
bot/logs/*.log                          # Log files (machine-specific)
runtime_state.json                      # Bot state (machine-specific)
state.json                              # Position tracking
.heartbeat                              # Heartbeat timestamp
.guardian_health                        # Guardian status
*.pid                                   # Process IDs
.bot_instance*.lock                     # Lock files
.volatility_status.json                 # Volatility status
```

### Build Artifacts (Don't Sync)

```
__pycache__/                            # Python cache
*.pyc                                   # Compiled Python
.venv/                                  # Virtual environment
node_modules/                           # NPM packages
.git/                                   # Git repository (use git pull instead)
```

---

## 🪟 Windows-Specific Setup

After syncing files from Mac, create these Windows-specific files:

### 1. Batch Scripts (Included)

Located in `windows/` directory:

```
windows/start_bot.bat                   # Start trading bot
windows/stop_bot.bat                    # Stop trading bot
windows/start_webui.bat                 # Start WebUI backend
```

Copy these to `D:\Projects\WorkingBot\` on Windows.

### 2. Path Adjustments

Some Python files may reference Unix paths. Windows handles these automatically in most cases, but check:

```python
# Mac: /Users/ssr/Projects/WorkingBot
# Windows: D:\Projects\WorkingBot  or  D:/Projects/WorkingBot (Python accepts both)
```

Python's `os.path` module handles cross-platform paths automatically.

### 3. Virtual Environment Setup

```powershell
# On Windows
cd D:\Projects\WorkingBot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. PM2 on Windows (Optional)

If you want PM2 on Windows:

```powershell
# Install Node.js first (from nodejs.org)
# Then install PM2
npm install -g pm2

# Start bot with PM2
pm2 start ecosystem.config.js --only gridbot-live
```

**Note:** PM2 works on Windows but process management differs slightly from Mac.

---

## ✅ Post-Sync Validation

Run these checks on Windows after sync:

### 1. File Structure Verification

```powershell
# On Windows PowerShell
cd D:\Projects\WorkingBot

# Check critical files exist
Test-Path bot\run.py
Test-Path bot\strategy\gridbot.py
Test-Path bot\strategy\modules\grid_calculator.py
Test-Path grid_config.env
```

### 2. Python Import Test

```powershell
# Set PYTHONPATH
$env:PYTHONPATH = "D:\Projects\WorkingBot"

# Test imports
python -c "from bot.strategy.gridbot import GridBot; print('✅ Imports OK')"
python -c "from bot.strategy.handlers import LongFillHandler; print('✅ Handlers OK')"
python -c "from bot.api.delta_client import DeltaClient; print('✅ API client OK')"
```

### 3. Configuration Test

```powershell
python -c "from bot.config.config_manager_core import load_config; print('✅ Config OK')"
```

### 4. Syntax Check

```powershell
python -m py_compile bot\strategy\gridbot.py
python -m py_compile bot\strategy\handlers\long_handler.py
python -m py_compile bot\api\delta_client.py
```

### 5. Dry Run Test

```powershell
# Set environment variables
$env:PYTHONPATH = "D:\Projects\WorkingBot"
$env:TRADING_MODE = "demo"
$env:EXECUTE_ORDERS = "false"

# Start bot (dry run)
python bot\run.py
```

---

## 🔧 Configuration Adjustments for Windows

### grid_config.env

Most parameters work identically on Windows, but check these:

```ini
# Paths (if absolute paths used)
# Mac: LOG_DIR=/Users/ssr/Projects/WorkingBot/bot/logs
# Windows: LOG_DIR=D:\Projects\WorkingBot\bot\logs  or  D:/Projects/WorkingBot/bot/logs

# Process management (if PM2 not installed)
# PM2_ENABLED=false  # Use Windows Service or Task Scheduler instead
```

### secrets/api_keys.env

**SECURITY: Manual copy required**

```powershell
# On Mac - Copy to USB or secure transfer
cp secrets/api_keys.env /Volumes/USB/

# On Windows - Copy from USB
copy E:\api_keys.env D:\Projects\WorkingBot\secrets\api_keys.env
```

**Never** transmit API keys over unsecured network!

---

## 🌐 WebUI Considerations

### Backend (Flask)

Should work identically on Windows:
- Python/Flask is cross-platform
- Port 5555 (check Windows Firewall)
- File paths handled by Python's `os.path`

### Frontend (React)

Completely platform-independent:
- JavaScript/React runs in browser
- Same on Mac and Windows
- May need: `npm install && npm run build`

### Accessing WebUI

```
Local (Windows): http://localhost:5555
From Mac (via LAN): http://[windows-ip]:5555
```

**Windows Firewall:** Allow port 5555 inbound

```powershell
# Allow port 5555
netsh advfirewall firewall add rule name="GridBot WebUI" dir=in action=allow protocol=TCP localport=5555
```

---

## 🔄 Ongoing Sync Strategy

### Option 1: Manual Sync (When Needed)

```bash
# On Mac - When you make changes
./sync_to_windows.sh 192.168.1.100 ssr
```

### Option 2: Git (Recommended)

```bash
# On Mac - Commit and push
git add .
git commit -m "Update bot logic"
git push origin production-v2.0

# On Windows - Pull changes
git pull origin production-v2.0
```

### Option 3: Automated Sync (Advanced)

Set up rsync daemon on Windows or use scheduled task to run sync script.

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'bot'"

**Solution:**
```powershell
# Set PYTHONPATH
$env:PYTHONPATH = "D:\Projects\WorkingBot"

# Or add to Windows environment variables permanently
setx PYTHONPATH "D:\Projects\WorkingBot"
```

### Issue: "Permission denied" on files

**Solution:**
```powershell
# Run PowerShell as Administrator
# Or adjust file permissions
icacls D:\Projects\WorkingBot /grant Users:F /T
```

### Issue: WebUI can't access from Mac

**Solution:**
```powershell
# Check Windows Firewall
netsh advfirewall firewall show rule name="GridBot WebUI"

# Add rule if missing
netsh advfirewall firewall add rule name="GridBot WebUI" dir=in action=allow protocol=TCP localport=5555
```

### Issue: Bot crashes on Windows

**Check:**
1. Python version (3.9+ required)
2. Dependencies installed (`pip install -r requirements.txt`)
3. API keys configured (`secrets/api_keys.env`)
4. PYTHONPATH set correctly
5. Logs: `D:\Projects\WorkingBot\bot\logs\bot.log`

---

## 📊 Sync Checklist

Before sync:
- [ ] Stop Windows bot (if running)
- [ ] Backup Windows `grid_config.env` (if customized)
- [ ] Note current bot state/positions

During sync:
- [ ] Run `./sync_to_windows.sh [ip] [user]` on Mac
- [ ] Or use Git pull on Windows
- [ ] Manually copy `secrets/api_keys.env` (secure method)

After sync:
- [ ] Verify file structure (Test-Path checks)
- [ ] Test Python imports
- [ ] Verify configuration loads
- [ ] Run syntax checks
- [ ] Test bot startup (dry run mode)
- [ ] Check WebUI access
- [ ] Review logs for errors

---

## 🎯 Expected Results

After successful sync, Windows should have:

- ✅ Identical bot brain logic (7 modules + handlers)
- ✅ Same decision-making algorithms
- ✅ Same monitoring system (5 layers)
- ✅ Same configuration parameters
- ✅ Same documentation
- ✅ Working WebUI backend
- ✅ All Python imports successful
- ✅ No errors on bot startup

**Differences (intentional):**
- ⚠️  Startup scripts (`.bat` instead of `.sh`)
- ⚠️  Process management (PM2 or Windows Service)
- ⚠️  Log file locations (machine-specific)
- ⚠️  Runtime state (independent per machine)

---

## 📞 Support

**Owner:** Shailendra Singh Rajawat  
**Email:** physics.ssr@gmail.com  
**Telegram:** 8170794676  

**Documentation:**
- Mac: `/Users/ssr/Projects/WorkingBot/AI_CONTEXT.md`
- Windows: `D:\Projects\WorkingBot\AI_CONTEXT.md` (after sync)

---

## 🔗 Related Documentation

- `AI_CONTEXT.md` - Complete system overview
- `BOT_BRAIN_ARCHITECTURE.md` - Module connections and dependencies
- `WINDOWS_REFACTORING_SYNC_NOV8_2025.md` - Previous Windows sync (Nov 8)
- `PM2_COMPLETE_SYSTEM.md` - PM2 process management
- `START_HERE.md` - Quick start guide

---

**Status:** Ready for sync  
**Date:** November 9, 2025  
**Sync Type:** Complete mirror (bot brain + decision logic)  
**Method:** Automated script with LAN connection  
**Impact:** No impact on Mac system (read-only sync)
