# 🔄 Mac → Windows Sync - Quick Reference

## 🚀 Quick Sync Command

```bash
# On Mac
cd /Users/ssr/Projects/WorkingBot
./sync_to_windows.sh 192.168.1.100 ssr
```

Replace `192.168.1.100` with your Windows IP address.

---

## 📋 What Gets Synced

### ✅ YES (Synced Automatically)
- All bot brain files (`bot/strategy/`, `bot/api/`)
- 7 core modules (grid_calculator, position_manager, etc.)
- Fill handlers (long_handler, short_handler)
- Monitoring system (5 layers)
- Guardian bot, heartbeat monitor
- Configuration (`grid_config.env`)
- Documentation (`.md` files)
- WebUI backend (Python files)

### ❌ NO (Not Synced)
- `.sh` scripts (Mac-specific)
- `.plist` files (Mac LaunchAgent)
- Log files (machine-specific)
- Runtime state files (`runtime_state.json`, `.heartbeat`)
- Lock files (`.bot_instance*.lock`)
- Git repository (use `git pull` on Windows instead)

### ⚠️ MANUAL (Security)
- `secrets/api_keys.env` (copy manually via USB or secure method)

---

## 🪟 After Sync on Windows

### 1. Set PYTHONPATH
```powershell
$env:PYTHONPATH = "D:\Projects\WorkingBot"
```

### 2. Install Dependencies
```powershell
cd D:\Projects\WorkingBot
pip install -r requirements.txt
```

### 3. Copy API Keys (MANUAL)
```powershell
# From USB or secure location
copy E:\api_keys.env D:\Projects\WorkingBot\secrets\api_keys.env
```

### 4. Test Imports
```powershell
python -c "from bot.strategy.gridbot import GridBot; print('✅ OK')"
```

### 5. Start Bot (Dry Run)
```powershell
# Use provided batch file
windows\start_bot.bat demo

# Or directly
python bot\run.py
```

---

## 🔧 Windows Batch Files

Located in `windows/` directory (included in sync):

```
windows\start_bot.bat       # Start trading bot
windows\stop_bot.bat        # Stop trading bot
windows\start_webui.bat     # Start WebUI backend
```

Copy to `D:\Projects\WorkingBot\` on Windows.

---

## 🌐 WebUI Access

### From Windows
```
http://localhost:5555
```

### From Mac (via LAN)
```
http://[windows-ip]:5555
```

**Windows Firewall Rule:**
```powershell
netsh advfirewall firewall add rule name="GridBot WebUI" dir=in action=allow protocol=TCP localport=5555
```

---

## 🐛 Common Issues

### "ModuleNotFoundError: No module named 'bot'"
**Fix:**
```powershell
$env:PYTHONPATH = "D:\Projects\WorkingBot"
```

### WebUI not accessible from Mac
**Fix:**
```powershell
# Allow port 5555 in Windows Firewall
netsh advfirewall firewall add rule name="GridBot WebUI" dir=in action=allow protocol=TCP localport=5555
```

### Bot crashes on Windows
**Check:**
1. Python 3.9+ installed
2. Dependencies: `pip install -r requirements.txt`
3. API keys: `secrets\api_keys.env` exists
4. PYTHONPATH: `$env:PYTHONPATH` is set
5. Logs: `bot\logs\bot.log`

---

## 📊 Verification Checklist

After sync on Windows:

```powershell
# 1. File structure
Test-Path bot\run.py                    # Should be True
Test-Path bot\strategy\gridbot.py       # Should be True
Test-Path grid_config.env               # Should be True

# 2. Python imports
python -c "from bot.strategy.gridbot import GridBot; print('✅')"
python -c "from bot.api.delta_client import DeltaClient; print('✅')"

# 3. Configuration
python -c "from bot.config.config_manager_core import load_config; print('✅')"

# 4. Syntax check
python -m py_compile bot\strategy\gridbot.py
```

All should complete without errors.

---

## 🔄 Sync Methods

### Method 1: Sync Script (Best)
```bash
./sync_to_windows.sh [windows-ip] [username]
```

### Method 2: Git Pull
```powershell
# On Windows
cd D:\Projects\WorkingBot
git pull origin production-v2.0
```

### Method 3: Manual SMB
```bash
# On Mac
mount_smbfs //ssr@[windows-ip]/D$ /Volumes/WindowsBot
cp -r bot /Volumes/WindowsBot/Projects/WorkingBot/
```

---

## 📚 Documentation

Available on both systems after sync:

- `AI_CONTEXT.md` - Complete system overview (4,835 lines)
- `BOT_BRAIN_ARCHITECTURE.md` - Module connections
- `MAC_WINDOWS_SYNC_GUIDE_NOV9_2025.md` - Full sync guide (this)

---

## 🎯 Expected Result

Windows bot should be a **perfect mirror** of Mac bot:
- ✅ Same trading logic
- ✅ Same decision-making algorithms
- ✅ Same safety systems (6 layers)
- ✅ Same monitoring system (5 layers)
- ✅ Same configuration
- ✅ Working WebUI

**Independent per machine:**
- ⚠️  Log files
- ⚠️  Runtime state
- ⚠️  Process management (PM2 on Mac, batch files on Windows)

---

**Last Updated:** November 9, 2025  
**Contact:** physics.ssr@gmail.com | Telegram: 8170794676
