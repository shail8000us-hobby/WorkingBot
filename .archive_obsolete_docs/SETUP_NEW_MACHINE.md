# 🚀 Setup Guide for New Machine (Mac M4)

**Date**: November 3, 2025  
**Machine**: New Mac (macOS Darwin 25.0.0)  
**User**: ssr  
**Project**: WorkingBot - Bitcoin Grid Trading Bot  

---

## ✅ Migration Status

### Already Present:
- ✅ Project files transferred (522 items)
- ✅ Python 3.9.6 installed
- ✅ `secrets/api_keys.env` (4.4KB)
- ✅ `grid_config.env` (107KB)
- ✅ Frontend dependencies in `webui/frontend/node_modules/`

### Needs Installation:
- ❌ Node.js and npm
- ❌ Python packages (from requirements.txt)
- ❌ LaunchAgent configuration
- ⚠️ Pip cache permissions fix

---

## 📋 **STEP-BY-STEP SETUP**

### **Step 1: Install Homebrew** (if not already installed)

```bash
# Check if Homebrew is installed
which brew

# If not installed, install it:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

### **Step 2: Install Node.js and npm**

```bash
# Install Node.js (includes npm)
brew install node

# Verify installation
node --version   # Should show v20.x or v18.x
npm --version    # Should show v9.x or v10.x
```

---

### **Step 3: Fix Pip Cache Permissions**

```bash
# Fix pip cache directory permissions
sudo chown -R $USER:staff ~/Library/Caches/pip
chmod -R 755 ~/Library/Caches/pip

# Or use pip with --user flag (no sudo needed)
```

---

### **Step 4: Install Python Dependencies**

```bash
cd /Users/ssr/Projects/WorkingBot

# Install all required packages
pip3 install -r requirements.txt

# Expected packages:
# - python-dotenv (1.1.1)
# - requests (2.32.5)
# - ccxt (crypto exchange library)
# - websocket-client
# - websockets
# - aiohttp
# - cryptography
# - psutil

# Verify critical packages
pip3 show ccxt
pip3 show flask
pip3 show python-socketio
```

**Note**: Your `requirements.txt` only has 8 packages listed, but the WebUI backend needs additional packages. Let me check what's missing...

---

### **Step 5: Install Additional WebUI Dependencies**

```bash
# The backend also needs:
pip3 install flask flask-cors flask-socketio python-socketio

# For monitoring and system checks:
pip3 install psutil

# Verify all installed
pip3 list | grep -E '(flask|socketio|ccxt|websocket)'
```

---

### **Step 6: Rebuild Frontend (Optional - node_modules exists)**

```bash
cd /Users/ssr/Projects/WorkingBot/webui/frontend

# Check if build exists
ls -la build/

# If build/ doesn't exist or is outdated, rebuild:
npm run build

# This creates optimized production build in build/
```

---

### **Step 7: Verify Configuration Files**

```bash
cd /Users/ssr/Projects/WorkingBot

# Check API keys file
cat secrets/api_keys.env | head -5

# Should contain:
# DELTA_API_KEY=your_key
# DELTA_API_SECRET=your_secret
# DELTA_PRIVATE_BASE_URL=https://api.india.delta.exchange

# Check grid config
cat grid_config.env | head -20

# Verify critical settings:
# TRADING_MODE=demo or live
# GRIDBOT_LOWER, GRIDBOT_UPPER, GRIDBOT_STEP
```

**⚠️ CRITICAL**: Update paths in config files from old machine to new machine:

```bash
# Search for old username paths
grep -r "shailendrasinghrajawat" grid_config.env

# If found, update to new username (ssr)
# Use text editor or sed command
```

---

### **Step 8: Setup LaunchAgent for WebUI**

```bash
cd /Users/ssr/Projects/WorkingBot

# Check if LaunchAgent plist exists
ls -la ~/Library/LaunchAgents/com.gridbot.webui*.plist

# If not exists, create it
mkdir -p ~/Library/LaunchAgents

# Create LaunchAgent plist (see template below)
```

**LaunchAgent Template** (`~/Library/LaunchAgents/com.gridbot.webui.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gridbot.webui</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/ssr/Projects/WorkingBot/webui/backend/app.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/ssr/Projects/WorkingBot</string>
    
    <key>StandardOutPath</key>
    <string>/Users/ssr/Projects/WorkingBot/logs/launchagent_webui.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/ssr/Projects/WorkingBot/logs/launchagent_webui_error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/ssr/Projects/WorkingBot</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
```

**Load the LaunchAgent:**

```bash
# Create logs directory
mkdir -p /Users/ssr/Projects/WorkingBot/logs

# Load the LaunchAgent
launchctl load ~/Library/LaunchAgents/com.gridbot.webui.plist

# Start the service
launchctl start com.gridbot.webui

# Verify it's running
launchctl list | grep gridbot.webui
```

---

### **Step 9: Test WebUI Backend**

```bash
# Wait 5 seconds for backend to start
sleep 5

# Test health endpoint
curl http://localhost:5555/api/health

# Expected response:
# {"status":"healthy","timestamp":"..."}

# Test version
curl http://localhost:5555/api/version

# Open in browser
open http://localhost:5555
```

**If port 5555 is in use:**

```bash
# Check what's using port 5555
lsof -ti:5555

# Kill the process if needed
lsof -ti:5555 | xargs kill -9

# Restart LaunchAgent
launchctl restart com.gridbot.webui
```

---

### **Step 10: Verify Trading Bot Can Start**

```bash
cd /Users/ssr/Projects/WorkingBot

# Set Python path
export PYTHONPATH=/Users/ssr/Projects/WorkingBot:$PYTHONPATH

# Test bot import
python3 -c "from bot.strategy.gridbot import GridBot; print('✅ GridBot import OK')"

# Test demo mode start (will run for 30 seconds then stop)
# DON'T run this yet - just verify dependencies work
python3 -c "import ccxt; print('✅ ccxt OK')"
python3 -c "import websockets; print('✅ websockets OK')"
python3 -c "import aiohttp; print('✅ aiohttp OK')"
```

---

### **Step 11: Update Paths in Scripts**

Several scripts may have hardcoded paths from old machine:

```bash
cd /Users/ssr/Projects/WorkingBot

# Find scripts with old username
grep -r "shailendrasinghrajawat" *.sh *.py 2>/dev/null | head -20

# Common files to update:
# - start_webui.sh
# - bot_launcher.py
# - check_webui_status.sh
# - Any other shell scripts

# Update them with:
# OLD: /Users/shailendrasinghrajawat/Projects/WorkingBot
# NEW: /Users/ssr/Projects/WorkingBot
```

---

### **Step 12: Setup Telegram Alerts (Optional)**

```bash
cd /Users/ssr/Projects/WorkingBot

# Check if Telegram is configured
cat secrets/api_keys.env | grep TELEGRAM

# Should have:
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id

# If missing, follow TELEGRAM_QUICK_REF.txt for setup
cat TELEGRAM_QUICK_REF.txt
```

---

## 🎯 **VERIFICATION CHECKLIST**

After completing all steps, verify everything works:

### Core System:
- [ ] Python 3.9.6+ installed: `python3 --version`
- [ ] pip3 working: `pip3 --version`
- [ ] Node.js installed: `node --version`
- [ ] npm installed: `npm --version`

### Python Dependencies:
- [ ] ccxt installed: `pip3 show ccxt`
- [ ] flask installed: `pip3 show flask`
- [ ] websockets installed: `pip3 show websockets`
- [ ] All requirements.txt packages: `pip3 list | grep -E '(ccxt|flask|socketio)'`

### Configuration:
- [ ] `secrets/api_keys.env` exists and has API keys
- [ ] `grid_config.env` exists and has correct paths
- [ ] Paths updated from old username to `ssr`

### WebUI:
- [ ] LaunchAgent loaded: `launchctl list | grep gridbot`
- [ ] Backend running on port 5555: `curl http://localhost:5555/api/health`
- [ ] WebUI accessible in browser: `http://localhost:5555`
- [ ] No errors in logs: `tail -20 logs/launchagent_webui_error.log`

### Trading Bot:
- [ ] Bot imports work: `python3 -c "from bot.strategy.gridbot import GridBot"`
- [ ] Exchange libraries work: `python3 -c "import ccxt"`
- [ ] WebSocket libraries work: `python3 -c "import websockets"`

---

## 🚨 **TROUBLESHOOTING**

### Issue 1: "command not found: node"

**Solution:**
```bash
brew install node
# Or download from: https://nodejs.org/
```

---

### Issue 2: "Package(s) not found: ccxt"

**Solution:**
```bash
pip3 install ccxt --user
# Or fix permissions:
sudo chown -R $USER ~/Library/Caches/pip
```

---

### Issue 3: "Port 5555 already in use"

**Solution:**
```bash
lsof -ti:5555 | xargs kill -9
launchctl restart com.gridbot.webui
```

---

### Issue 4: "ModuleNotFoundError: No module named 'bot'"

**Solution:**
```bash
export PYTHONPATH=/Users/ssr/Projects/WorkingBot:$PYTHONPATH
# Add to ~/.zshrc to make permanent:
echo 'export PYTHONPATH=/Users/ssr/Projects/WorkingBot:$PYTHONPATH' >> ~/.zshrc
```

---

### Issue 5: WebUI shows 500 errors

**Check logs:**
```bash
tail -50 logs/launchagent_webui_error.log

# Common causes:
# - Missing Python packages (install them)
# - Wrong file paths in config (update to /Users/ssr/...)
# - API keys not loaded (check secrets/api_keys.env)
```

---

## 📚 **NEXT STEPS AFTER SETUP**

Once everything is installed and verified:

1. **Read START_HERE.md** - Complete user guide
2. **Review AI_CRITICAL_RULES.md** - Important rules for AI assistants
3. **Check BOT_STRUCTURE.md** - Technical architecture
4. **Test in Demo Mode** - Run bot with fake money first
5. **Configure Grid Parameters** - Use WebUI to adjust settings
6. **Monitor Logs** - Watch for any errors or warnings

---

## 🎉 **SETUP COMPLETE!**

Your WorkingBot is now configured on the new Mac M4!

**What You Can Do Now:**
- ✅ Access WebUI at: `http://localhost:5555`
- ✅ Start bot in demo mode (paper trading)
- ✅ Monitor positions and P&L
- ✅ Configure grid parameters
- ✅ View real-time logs

**Before Live Trading:**
- Test in demo mode for 24+ hours
- Verify all safety limits are set
- Check API keys are correct
- Read USER_MANUAL.md safety section

---

**Questions?** Check these files:
- `START_HERE.md` - Quick start guide
- `QUICK_REFERENCE.md` - Common commands
- `AI_CRITICAL_RULES.md` - Port/config rules
- `backend_frontend.md` - WebUI architecture

---

**Status**: ✅ Ready for Testing  
**Risk**: 🟢 Low (demo mode available)  
**Support**: 📚 Comprehensive documentation

Good luck! 🚀

