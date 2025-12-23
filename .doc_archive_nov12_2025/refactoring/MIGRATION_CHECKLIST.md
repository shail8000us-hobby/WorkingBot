# ✅ Migration Checklist - New Machine Setup

**Date**: November 3, 2025  
**From**: Old Mac (shailendrasinghrajawat)  
**To**: New Mac M4 (ssr)  
**Project**: WorkingBot GridBot Trading System  

---

## 📋 **PRE-MIGRATION STATUS**

### Files Transferred: ✅
- [x] Project directory copied (522 items)
- [x] secrets/api_keys.env (4.4KB)
- [x] grid_config.env (107KB)
- [x] All Python source files
- [x] All documentation (.md files)
- [x] Frontend node_modules
- [x] Git repository (if applicable)

---

## 🔧 **SYSTEM REQUIREMENTS CHECKLIST**

### Operating System:
- [x] macOS (Darwin 25.0.0) ✅
- [x] User account: ssr ✅

### Core Software:
- [x] Python 3.9+ ✅ (3.9.6 installed)
- [x] pip3 ✅ (Available)
- [ ] Node.js 18+ ❌ (Not installed)
- [ ] npm 9+ ❌ (Not installed)
- [ ] Homebrew (Optional but recommended)

---

## 📦 **INSTALLATION CHECKLIST**

### Step 1: Install System Dependencies
- [ ] Install Homebrew (if not present)
- [ ] Install Node.js via Homebrew: `brew install node`
- [ ] Verify Node.js: `node --version`
- [ ] Verify npm: `npm --version`

### Step 2: Fix Permissions
- [ ] Fix pip cache permissions
  ```bash
  sudo chown -R $USER:staff ~/Library/Caches/pip
  chmod -R 755 ~/Library/Caches/pip
  ```

### Step 3: Install Python Dependencies
- [ ] Install from requirements.txt: `pip3 install -r requirements.txt --user`
- [ ] Install WebUI dependencies: `pip3 install flask flask-cors flask-socketio python-socketio --user`
- [ ] Verify ccxt: `pip3 show ccxt`
- [ ] Verify flask: `pip3 show flask`
- [ ] Verify websockets: `pip3 show websockets`

### Step 4: Update Configuration Paths
- [ ] Check grid_config.env for old username
- [ ] Replace `/Users/shailendrasinghrajawat` with `/Users/ssr`
- [ ] Backup config before changes: `cp grid_config.env grid_config.env.backup`
- [ ] Update any shell scripts with hardcoded paths

### Step 5: Verify Configuration Files
- [ ] secrets/api_keys.env has Delta API credentials
- [ ] grid_config.env has correct TRADING_MODE (demo/live)
- [ ] Grid parameters are correct (LOWER, UPPER, STEP, REF)
- [ ] Safety limits configured (MAX_ACCOUNT_LOSS, etc.)

### Step 6: Setup LaunchAgent
- [ ] Create ~/Library/LaunchAgents/ directory
- [ ] Copy/create com.gridbot.webui.plist
- [ ] Update plist paths to /Users/ssr/...
- [ ] Load LaunchAgent: `launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist`
- [ ] Verify loaded: `launchctl list | grep gridbot`

### Step 7: Create Required Directories
- [ ] `mkdir -p logs`
- [ ] `mkdir -p data`
- [ ] `mkdir -p reports`
- [ ] `mkdir -p bot/logs`
- [ ] `mkdir -p bot/audit`

### Step 8: Start WebUI Backend
- [ ] Check port 5555 is free: `lsof -ti:5555`
- [ ] Start LaunchAgent: `launchctl start com.gridbot.webui`
- [ ] Wait 5 seconds for startup
- [ ] Test health: `curl http://localhost:5555/api/health`
- [ ] Open in browser: `open http://localhost:5555`

### Step 9: Verify Bot Can Run
- [ ] Set PYTHONPATH: `export PYTHONPATH=/Users/ssr/Projects/WorkingBot:$PYTHONPATH`
- [ ] Test imports: `python3 -c "from bot.strategy.gridbot import GridBot"`
- [ ] Test ccxt: `python3 -c "import ccxt"`
- [ ] Test websockets: `python3 -c "import websockets"`

### Step 10: Optional - Setup Telegram
- [ ] Verify TELEGRAM_BOT_TOKEN in secrets/api_keys.env
- [ ] Verify TELEGRAM_CHAT_ID in secrets/api_keys.env
- [ ] Test Telegram alerts (if configured)

---

## ✅ **VERIFICATION TESTS**

### Basic Functionality:
- [ ] WebUI loads at http://localhost:5555
- [ ] Dashboard displays correctly
- [ ] Bot status panel shows status
- [ ] Logs panel displays logs
- [ ] Configuration panel loads
- [ ] No JavaScript errors in browser console

### Backend API:
- [ ] GET /api/health returns 200
- [ ] GET /api/version returns version info
- [ ] GET /api/bot/status returns status
- [ ] GET /api/system/status returns system info
- [ ] GET /api/config returns configuration

### Trading Bot:
- [ ] Bot can import successfully
- [ ] Bot can connect to Delta Exchange API (test mode)
- [ ] WebSocket connection works
- [ ] Price updates received

---

## 🚨 **CRITICAL CHECKS BEFORE LIVE TRADING**

### Safety Verification:
- [ ] TRADING_MODE set correctly (demo first!)
- [ ] API keys are correct for the intended environment
- [ ] MAX_ACCOUNT_LOSS_INR is set appropriately
- [ ] GUARDIAN_MAX_ACCOUNT_LOSS_INR is set
- [ ] MAX_MARGIN_UTILIZATION is reasonable (40% or less)
- [ ] Volatility limits configured
- [ ] Max open positions is reasonable

### Testing Requirements:
- [ ] Ran in demo mode for 24+ hours successfully
- [ ] No errors in logs
- [ ] All safety systems working
- [ ] Guardian bot functioning
- [ ] Heartbeat monitor active
- [ ] WebSocket reconnection works

---

## 📊 **AUTOMATED SETUP OPTION**

Instead of manual steps, you can run the automated setup script:

```bash
cd /Users/ssr/Projects/WorkingBot
./quick_setup.sh
```

**What it does:**
- ✅ Checks all prerequisites
- ✅ Installs Node.js (if Homebrew available)
- ✅ Fixes pip permissions
- ✅ Installs all Python dependencies
- ✅ Updates configuration paths
- ✅ Creates required directories
- ✅ Sets up LaunchAgent
- ✅ Starts WebUI backend
- ✅ Verifies installation

**Time**: 5-10 minutes (depending on installation speed)

---

## 🔍 **POST-MIGRATION VERIFICATION**

### Day 1:
- [ ] WebUI accessible and responsive
- [ ] Backend stays running (no crashes)
- [ ] Logs are being written correctly
- [ ] Memory usage is normal (< 500MB for backend)
- [ ] CPU usage is normal (< 10% idle, < 50% active)

### Week 1:
- [ ] Bot has run successfully in demo mode
- [ ] No unexpected errors or warnings
- [ ] All features working as expected
- [ ] Performance is acceptable
- [ ] Mobile access works (if using Tailscale)

### Before Live Trading:
- [ ] Demo mode ran successfully for 7+ days
- [ ] Thoroughly tested all features
- [ ] Reviewed and understood all safety systems
- [ ] Set appropriate loss limits
- [ ] Ready to monitor actively

---

## 📚 **REFERENCE DOCUMENTATION**

**Essential Reading:**
1. `START_HERE.md` - Quick start guide
2. `SETUP_NEW_MACHINE.md` - Detailed setup instructions
3. `AI_CRITICAL_RULES.md` - Critical configuration rules
4. `backend_frontend.md` - Port and architecture guide
5. `README.md` - Project overview

**For Trading:**
1. `USER_MANUAL.md` - Complete user manual
2. `BOT_STRUCTURE.md` - Technical architecture
3. `ROBUSTNESS_FEATURES.md` - Safety systems documentation
4. `QUICK_REFERENCE.md` - Quick command reference

---

## 🎯 **SUCCESS CRITERIA**

Your migration is complete when:
- ✅ All items in this checklist are checked
- ✅ WebUI accessible at http://localhost:5555
- ✅ Backend health check returns OK
- ✅ Bot can run in demo mode
- ✅ No errors in logs
- ✅ All safety systems functional

---

## 🆘 **TROUBLESHOOTING**

### If Setup Script Fails:
1. Read the error message carefully
2. Check logs: `tail -50 logs/launchagent_webui_error.log`
3. Verify Python packages: `pip3 list | grep -E '(ccxt|flask|socketio)'`
4. Check port 5555: `lsof -ti:5555`
5. Refer to SETUP_NEW_MACHINE.md for manual steps

### If WebUI Won't Start:
1. Check LaunchAgent: `launchctl list | grep gridbot`
2. Check logs: `tail -50 logs/launchagent_webui_error.log`
3. Check port: `lsof -ti:5555`
4. Try manual start: `python3 webui/backend/app.py`
5. Check Python path: `export PYTHONPATH=/Users/ssr/Projects/WorkingBot:$PYTHONPATH`

### If Bot Won't Import:
1. Set PYTHONPATH: `export PYTHONPATH=/Users/ssr/Projects/WorkingBot:$PYTHONPATH`
2. Check dependencies: `pip3 list | grep ccxt`
3. Try manual import: `python3 -c "from bot.strategy.gridbot import GridBot"`
4. Check for syntax errors in bot files

---

## 📞 **SUPPORT RESOURCES**

**Documentation Location**: `/Users/ssr/Projects/WorkingBot/`

**Key Files:**
- Error logs: `logs/launchagent_webui_error.log`
- Bot logs: `bot_live.log` or `bot_demo.log`
- LaunchAgent plist: `~/Library/LaunchAgents/com.gridbot.webui.plist`
- API keys: `secrets/api_keys.env`
- Configuration: `grid_config.env`

**Quick Commands:**
```bash
# Check backend status
launchctl list | grep gridbot

# View logs
tail -f logs/launchagent_webui_error.log

# Restart backend
launchctl restart com.gridbot.webui

# Test health
curl http://localhost:5555/api/health

# Open WebUI
open http://localhost:5555
```

---

## ✅ **MIGRATION COMPLETE!**

Once all items are checked:
- 🎉 Your WorkingBot is fully migrated
- 🚀 Ready for testing in demo mode
- 📊 Monitor for 24-48 hours before live trading
- 🛡️ All safety systems should be verified

**Status**: [ ] In Progress  /  [ ] Complete  
**Date Completed**: _______________  
**Verified By**: _______________  

---

**Good luck with your migrated WorkingBot!** 🚀

