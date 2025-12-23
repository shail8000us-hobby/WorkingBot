# 🤖 AI Prompt for Windows Bot Verification & Startup

**Date:** November 9, 2025  
**Purpose:** Guide AI assistant to verify and start GridBot on Windows after sync from Mac  
**Windows Location:** `D:\Projects\WorkingBot`

---

## 📋 CONTEXT FOR AI

The GridBot trading system has just been synced from Mac (192.168.1.3) to this Windows machine (192.168.1.32). All core bot brain files, decision-making modules, safety systems, and monitoring layers have been mirrored.

**Your task:** Verify all changes, test imports, and start the bot in demo mode.

---

## ✅ STEP-BY-STEP VERIFICATION CHECKLIST

### Step 1: Environment Setup

```powershell
# Set PYTHONPATH
$env:PYTHONPATH = "D:\Projects\WorkingBot"

# Navigate to project
cd D:\Projects\WorkingBot

# Verify Python version (must be 3.9+)
python --version
```

**Expected:** Python 3.9 or higher

---

### Step 2: Verify File Structure

```powershell
# Check critical files exist
Test-Path bot\run.py
Test-Path bot\strategy\gridbot.py
Test-Path bot\strategy\modules\grid_calculator.py
Test-Path bot\strategy\handlers\long_handler.py
Test-Path grid_config.env

# All should return: True
```

**Expected:** All return `True`

---

### Step 3: Check File Sizes & Dates

```powershell
# Main orchestrator (should be 88KB, dated Nov 9)
Get-Item bot\strategy\gridbot.py | Select-Object Length, LastWriteTime

# Core modules (should all be recent - Nov 9)
Get-ChildItem bot\strategy\modules\*.py | Select-Object Name, Length, LastWriteTime

# Handlers (should be recent - Nov 9)
Get-ChildItem bot\strategy\handlers\*.py | Select-Object Name, Length, LastWriteTime
```

**Expected:**
- `gridbot.py` = ~88-90KB, Nov 9, 2025
- All modules updated Nov 9, 2025
- Both handlers updated Nov 9, 2025

---

### Step 4: Verify Dependencies

```powershell
# Check if virtual environment exists
Test-Path .venv\Scripts\activate.bat

# If True, activate it
.venv\Scripts\activate

# If False or if you need to reinstall
pip install -r requirements.txt
```

**Expected:** All packages install without errors

**Key packages to verify:**
- flask
- flask-socketio
- requests
- websocket-client
- numpy
- pandas

---

### Step 5: Test Python Imports (CRITICAL)

```powershell
# Test 1: Main orchestrator
python -c "from bot.strategy.gridbot import GridBot; print('✅ GridBot import OK')"

# Test 2: Core modules
python -c "from bot.strategy.modules import GridCalculator, PositionManager, FillDetector, OrderManager, Reconciliation, VolatilityHandler, WebSocketHandler; print('✅ All modules import OK')"

# Test 3: Handlers
python -c "from bot.strategy.handlers import LongFillHandler, ShortFillHandler; print('✅ Handlers import OK')"

# Test 4: Delta API client
python -c "from bot.api.delta_client import DeltaClient; print('✅ DeltaClient import OK')"

# Test 5: WebSocket manager
python -c "from bot.delta_websocket.ws_manager import WebSocketManager; print('✅ WebSocket manager OK')"

# Test 6: Configuration manager
python -c "from bot.config.config_manager_core import load_config; print('✅ Config manager OK')"

# Test 7: Monitoring system
python -c "from bot.monitoring import PriceHealthMonitor, PreOrderLogger, TPVerification, AnomalyDetection, PredictiveDisplay; print('✅ Monitoring system OK')"

# Test 8: Safety systems
python -c "from bot.guardian.guardian_bot import GuardianBot; from bot.heartbeat.monitor import HeartbeatMonitor; from bot.volatility.iv_rv_tracker import IVRVTracker; print('✅ Safety systems OK')"
```

**Expected:** All tests print `✅ ... OK` with no errors

**If any import fails:**
1. Check PYTHONPATH is set correctly
2. Check file exists at expected location
3. Check for syntax errors: `python -m py_compile <filename>`
4. Review error message carefully

---

### Step 6: Syntax Validation

```powershell
# Validate syntax of critical files (no output = success)
python -m py_compile bot\strategy\gridbot.py
python -m py_compile bot\strategy\modules\grid_calculator.py
python -m py_compile bot\strategy\modules\position_manager.py
python -m py_compile bot\strategy\modules\fill_detector.py
python -m py_compile bot\strategy\modules\order_manager.py
python -m py_compile bot\strategy\handlers\long_handler.py
python -m py_compile bot\strategy\handlers\short_handler.py
python -m py_compile bot\api\delta_client.py
```

**Expected:** No output (silence = success)

**If syntax error:** Fix the reported line/file

---

### Step 7: Configuration Check

```powershell
# Verify grid_config.env exists and is readable
Get-Content grid_config.env -TotalCount 50

# Check critical parameters
Select-String -Path grid_config.env -Pattern "TRADING_MODE|GRIDBOT_LOWER|GRIDBOT_UPPER|GRIDBOT_STEP|MAX_OPEN_POSITIONS"
```

**Expected output should include:**
```
TRADING_MODE=live  (or demo)
GRIDBOT_LOWER=105000
GRIDBOT_UPPER=120000
GRIDBOT_STEP=1000
MAX_OPEN_POSITIONS=3
```

---

### Step 8: API Keys Check (SECURITY)

```powershell
# Check if API keys file exists
Test-Path secrets\api_keys.env
```

**If False:**
```
⚠️ STOP! API keys not found.
Copy secrets\api_keys.env from:
- USB drive
- Secure backup location
- Mac (via secure method)

Required content:
DELTA_API_KEY=your_key_here
DELTA_API_SECRET=your_secret_here
```

**If True:** Proceed to next step

---

### Step 9: Module Initialization Test

```powershell
# Test GridBot initialization (without starting trading)
python -c "
import os
import sys
sys.path.insert(0, '.')
os.environ['GRIDBOT_GRID_MODE'] = 'LONG'
os.environ['TRADING_MODE'] = 'demo'
os.environ['EXECUTE_ORDERS'] = 'false'

from bot.strategy.gridbot import GridBot
print('✅ GridBot initialization successful')
"
```

**Expected:** `✅ GridBot initialization successful`

**If error:** Review error message - likely missing dependency or config issue

---

### Step 10: Dry Run Test (No Real Orders)

```powershell
# Create a test script to run bot in dry mode
@"
import os
import sys

# Set dry run mode
os.environ['PYTHONPATH'] = r'D:\Projects\WorkingBot'
os.environ['TRADING_MODE'] = 'demo'
os.environ['EXECUTE_ORDERS'] = 'false'
os.environ['GRIDBOT_GRID_MODE'] = 'LONG'

sys.path.insert(0, r'D:\Projects\WorkingBot')

print('Starting GridBot dry run test...')
print('TRADING_MODE:', os.getenv('TRADING_MODE'))
print('EXECUTE_ORDERS:', os.getenv('EXECUTE_ORDERS'))
print()

try:
    from bot.strategy.gridbot import GridBot
    bot = GridBot()
    print('✅ Bot initialized successfully!')
    print('✅ All modules loaded!')
    print('✅ Ready for trading!')
except Exception as e:
    print('❌ Error:', str(e))
    import traceback
    traceback.print_exc()
"@ | Out-File -Encoding utf8 test_bot.py

# Run the test
python test_bot.py
```

**Expected output:**
```
Starting GridBot dry run test...
TRADING_MODE: demo
EXECUTE_ORDERS: false

✅ Bot initialized successfully!
✅ All modules loaded!
✅ Ready for trading!
```

---

### Step 11: Start Bot (Demo Mode)

If all tests pass, start the bot using the Windows batch file:

```powershell
# Method 1: Using batch file
.\windows\start_bot.bat demo

# Method 2: Direct Python
$env:TRADING_MODE = "demo"
python bot\run.py
```

**Expected:** Bot starts without errors

**Monitor for:**
- ✅ "WebSocket authenticated" message
- ✅ "Subscription confirmed" message
- ✅ Price updates appearing
- ✅ No ModuleNotFoundError
- ✅ No syntax errors
- ✅ Grid calculator working
- ✅ Position manager initialized

---

### Step 12: Real-Time Monitoring

```powershell
# In separate PowerShell window, monitor logs
Get-Content bot\logs\bot.log -Wait -Tail 50

# Or filter for important events
Get-Content bot\logs\bot.log -Wait -Tail 100 | Select-String "ERROR|Fill|Order|HALT|WebSocket authenticated"
```

**Watch for:**
- ✅ WebSocket connection established
- ✅ Price updates flowing
- ✅ No errors in log
- ✅ Monitoring system active
- ✅ Safety systems initialized

---

## 🚨 TROUBLESHOOTING GUIDE

### Issue: ModuleNotFoundError: No module named 'bot'

**Solution:**
```powershell
$env:PYTHONPATH = "D:\Projects\WorkingBot"
```

Or set permanently:
```powershell
[System.Environment]::SetEnvironmentVariable('PYTHONPATH', 'D:\Projects\WorkingBot', 'User')
```

---

### Issue: Import error in specific module

**Solution:**
1. Check file exists: `Test-Path bot\strategy\modules\<module>.py`
2. Check syntax: `python -m py_compile bot\strategy\modules\<module>.py`
3. Check dependencies imported in that module are installed
4. Try importing dependencies individually

---

### Issue: API connection failed

**Solution:**
1. Check `secrets\api_keys.env` exists and has valid keys
2. Check internet connection
3. Check Delta Exchange API status
4. Verify API keys are correct (test on Mac first if needed)

---

### Issue: WebSocket connection failed

**Solution:**
1. Check internet connection
2. Check firewall allows outbound WebSocket (port 443)
3. Check Delta Exchange WebSocket status
4. Review `bot\delta_websocket\ws_manager.py` for connection details

---

### Issue: Configuration error

**Solution:**
1. Verify `grid_config.env` is readable
2. Check no syntax errors in config file
3. Verify all required parameters present
4. Compare with Mac version if needed

---

### Issue: Permission denied errors

**Solution:**
```powershell
# Run PowerShell as Administrator
# Or adjust file permissions
icacls D:\Projects\WorkingBot /grant Users:F /T
```

---

## ✅ SUCCESS CRITERIA

Bot is ready when ALL of these are true:

- ✅ All import tests pass
- ✅ Syntax validation clean (no errors)
- ✅ Configuration loaded successfully
- ✅ API keys present and valid
- ✅ Bot initializes without errors
- ✅ WebSocket connects and authenticates
- ✅ Price updates flowing
- ✅ All 7 core modules initialized
- ✅ Both handlers (LONG/SHORT) loaded
- ✅ Monitoring system active (5 layers)
- ✅ Safety systems active (6 layers)
- ✅ No errors in logs

---

## 🎯 FINAL START COMMAND

Once all verifications pass:

### For Demo/Testing:
```powershell
cd D:\Projects\WorkingBot
$env:PYTHONPATH = "D:\Projects\WorkingBot"
$env:TRADING_MODE = "demo"
python bot\run.py
```

### For Live Trading (CAUTION):
```powershell
cd D:\Projects\WorkingBot
$env:PYTHONPATH = "D:\Projects\WorkingBot"
$env:TRADING_MODE = "live"
$env:I_UNDERSTAND_LIVE = "YES"
python bot\run.py
```

**⚠️ LIVE TRADING WARNING:**
- Only start live mode after demo mode runs successfully
- Verify all safety systems are active
- Check margin requirements
- Review loss limits are set correctly
- Monitor closely for first 10-15 minutes

---

## 📊 POST-STARTUP MONITORING

After bot starts, monitor these for 15 minutes:

```powershell
# Terminal 1: Bot logs
Get-Content bot\logs\bot.log -Wait -Tail 50

# Terminal 2: Guardian logs
Get-Content bot\logs\guardian.log -Wait -Tail 20

# Terminal 3: Check bot status
python -c "
import json
with open('.heartbeat', 'r') as f:
    print('Heartbeat:', f.read())
with open('.guardian_health', 'r') as f:
    print('Guardian:', json.load(f))
"
```

**Monitor for:**
- Heartbeat updates every 10-15 seconds
- Guardian active and monitoring
- No repeated errors
- Position tracking working
- Fill detection working
- Order placement working (if EXECUTE_ORDERS=true)

---

## 📚 REFERENCE DOCUMENTATION

Available on Windows at `D:\Projects\WorkingBot\`:

1. **AI_CONTEXT.md** - Complete system overview (4,835 lines)
2. **BOT_BRAIN_ARCHITECTURE.md** - Module connections & dependencies
3. **AI_CRITICAL_RULES.md** - Immutable rules (READ BEFORE CHANGES!)
4. **START_HERE.md** - Quick start guide
5. **USER_MANUAL.md** - Configuration guide (171 parameters)
6. **WINDOWS_SYNC_QUICK_REF.md** - Windows-specific quick reference
7. **MAC_WINDOWS_SYNC_GUIDE_NOV9_2025.md** - Complete sync guide

---

## 🤖 AI AGENT INSTRUCTIONS

If you are an AI assistant helping with this:

1. **Execute each step sequentially** - Don't skip steps
2. **Report results clearly** - Use ✅ for success, ❌ for failure
3. **Stop on first error** - Don't proceed until error is resolved
4. **Provide error context** - Full error messages and tracebacks
5. **Suggest solutions** - Based on troubleshooting guide above
6. **Verify before proceeding** - Confirm each step before next
7. **Document any issues** - Note any deviations or fixes applied

**Example output format:**
```
Step 1: Environment Setup
✅ PYTHONPATH set to D:\Projects\WorkingBot
✅ Python version: 3.9.13
✅ Current directory: D:\Projects\WorkingBot

Step 2: File Structure
✅ bot\run.py exists
✅ bot\strategy\gridbot.py exists (88KB, Nov 9 2025)
✅ All core modules present (7/7)
✅ Both handlers present (2/2)

Step 3: Test Imports
✅ GridBot import successful
✅ All modules import successful
...
```

---

## 🎉 SUCCESS MESSAGE

When all tests pass and bot is running:

```
═══════════════════════════════════════════════════════════════
   ✅ GridBot Windows Startup Complete! 
═══════════════════════════════════════════════════════════════

Date: [timestamp]
Mode: [demo/live]
Location: D:\Projects\WorkingBot

✅ All verification tests passed
✅ Bot initialized successfully
✅ WebSocket connected
✅ All 7 modules active
✅ Safety systems armed
✅ Monitoring systems active

Status: TRADING 🚀

Monitor logs: bot\logs\bot.log
Guardian status: .guardian_health
Heartbeat: .heartbeat

═══════════════════════════════════════════════════════════════
```

---

**Last Updated:** November 9, 2025  
**Sync Version:** Mac production-v2.0 → Windows mirror  
**Contact:** physics.ssr@gmail.com | Telegram: 8170794676
