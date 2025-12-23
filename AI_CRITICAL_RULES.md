# 🚨 CRITICAL RULES FOR AI ASSISTANTS

**MANDATORY READING BEFORE ANY CODE CHANGES**

This document contains IMMUTABLE rules that prevent common mistakes made by AI assistants. Violating these rules will break the production system.

---

## ⛔ FORBIDDEN CHANGES - NEVER MODIFY

### 1. Port Configuration (IMMUTABLE)

```
Backend (Flask API):     Port 5555  ← Production server (NEVER CHANGE)
Frontend (React Dev):    Port 3000  ← Development only
Frontend (Production):   Port 5555  ← Served by backend
```

**❌ FORBIDDEN:**
- Changing port 5555 in `webui/backend/app.py`
- Running React dev server on port 5555
- Modifying `socketio.run(port=5555)`
- Changing LaunchAgent port configuration

**Why:** Port 5555 is hardcoded in:
- LaunchAgent plist file (`com.gridbot.webui`)
- Frontend API client (`http://localhost:5555`)
- Production deployment scripts
- Monitoring dashboards

**Common Error:**
```
Address already in use - Port 5555 is in use by another program
```

**Solution:** Kill React dev server, not change the port!
```bash
lsof -ti:5555 | xargs kill -9
launchctl start com.gridbot.webui
```

---

### 2. Currency Conversion (SINGLE POINT)

**CRITICAL: Delta Exchange API returns USD. We display INR. Convert ONCE, not twice!**

**✅ CORRECT - Convert in API Endpoints ONLY:**
```python
# webui/backend/routes/liquidation.py
balance_usd = float(wallet_data.get('balance', 0))
usd_to_inr_rate = float(os.getenv('USD_TO_INR_RATE', '85'))
balance_inr = balance_usd * usd_to_inr_rate  # ✅ Convert once
```

**❌ WRONG - Don't convert again in consumers:**
```python
# bot/guardian/guardian_bot.py
balance_inr = liq_status.get('total_balance')  # Already INR!
balance_inr = balance_inr * 85  # ❌ WRONG! Double conversion!
# Result: ₹87 lac instead of ₹1 lac
```

**Conversion Points (EXHAUSTIVE LIST):**
1. `webui/backend/routes/liquidation.py` - Wallet balance, PnL, maintenance margin
2. `webui/backend/routes/positions.py` - Position PnL, notional deployed
3. **NOWHERE ELSE!** All other modules consume INR values.

**Verification Commands:**
```bash
# Should show ~103,000 (₹1 lac in INR)
curl -s http://localhost:5555/api/liquidation/status | jq '.margin.total_balance'

# Should match above (NOT 87 lac from double conversion)
curl -s http://localhost:5555/api/guardian/status | jq '.health.liquidation.margin.total_balance'
```

---

### 3. Backend-Frontend Architecture (IMMUTABLE)

**Structure:**
```
webui/
├── backend/            ← Python Flask (Port 5555)
│   ├── app.py          ← ENTRY POINT (DO NOT MOVE/RENAME)
│   └── routes/         ← 23 blueprints (DO NOT REORGANIZE)
└── frontend/           ← React SPA
    ├── src/            ← Source (edit freely)
    ├── build/          ← Production (auto-generated, DO NOT EDIT)
    └── package.json    ← Port 3000 dev, proxy to 5555
```

**❌ FORBIDDEN:**
- Moving `app.py` to different location
- Renaming `webui/` folder
- Merging backend and frontend into single folder
- Changing `routes/` structure (breaks imports)

**Development Workflow:**
```bash
# Option 1: Development Mode (UI changes)
Terminal 1: launchctl start com.gridbot.webui  # Backend 5555
Terminal 2: cd webui/frontend && npm start      # Dev server 3000

# Option 2: Production Mode (backend changes)
cd webui/frontend && npm run build
launchctl restart com.gridbot.webui  # Serves build/ on 5555
```

---

### 4. Service Management (macOS LaunchAgent)

**This is macOS, NOT Linux!**

**✅ CORRECT:**
```bash
launchctl start com.gridbot.webui
launchctl stop com.gridbot.webui
launchctl list | grep gridbot
```

**❌ WRONG (These don't exist on macOS):**
```bash
systemctl start gridbot-webui    # ❌ No systemd
pm2 start webui                  # ❌ Not using PM2
service gridbot-webui restart    # ❌ Not SysVinit
```

**LaunchAgent Location:**
```
~/Library/LaunchAgents/com.gridbot.webui.plist
```

**Logs Location:**
```
/Users/shailendrasinghrajawat/Projects/WorkingBot/logs/launchagent_webui_error.log
```

---

## ✅ PRE-CHANGE CHECKLIST

**Before modifying ANY file, verify:**

1. **Is backend running?**
   ```bash
   curl http://localhost:5555/api/health
   ```

2. **Is port 5555 available?**
   ```bash
   lsof -ti:5555
   # If returns PIDs, kill them (usually React dev server)
   ```

3. **Is data in USD or INR?**
   ```bash
   # Check the source API/module
   # If from Delta Exchange → USD → need conversion
   # If from liquidation/positions endpoint → INR → don't convert
   ```

4. **Is SocketIO version compatible?**
   ```bash
   pip3 list | grep socketio
   # Backend: python-socketio 5.x, flask-socketio 5.x
   
   cd webui/frontend && cat package.json | grep socket.io-client
   # Frontend: socket.io-client 4.8.x or higher
   ```

5. **Did you read backend_frontend.md?**
   ```bash
   cat backend_frontend.md
   ```

---

## 🔍 COMMON MISTAKES & SOLUTIONS

### Mistake 1: "Port 5555 already in use"

**Root Cause:** React dev server running on 5555

**Detection:**
```bash
lsof -ti:5555
ps -p <PID>  # Check if it's node/react-app-rewired
```

**Solution:**
```bash
# Kill React dev server
pkill -f "react-app-rewired"

# Restart backend
launchctl stop com.gridbot.webui
launchctl start com.gridbot.webui
```

**Prevention:** Always run React dev on port 3000 (default)

---

### Mistake 2: "Balance showing ₹87 lac instead of ₹1 lac"

**Root Cause:** Double USD-to-INR conversion

**Detection:**
```bash
# If this shows ~8,700,000 instead of ~103,000
curl -s http://localhost:5555/api/guardian/status | jq '.health.liquidation.margin.total_balance'
```

**Solution:** Remove conversion in Guardian/consumer:
```python
# BEFORE (Wrong):
balance_inr = balance_usd * usd_to_inr_rate  # Already converted!

# AFTER (Correct):
balance_inr = liq_status.get('total_balance')  # Already INR
```

---

### Mistake 3: "SocketIO error - unsupported protocol version"

**Root Cause:** Version mismatch between frontend and backend

**Detection:**
```bash
tail -f logs/launchagent_webui_error.log | grep "unsupported version"
```

**Solution:**
```bash
cd webui/frontend
npm install socket.io-client@latest --legacy-peer-deps
# Must be 4.8.x or higher for python-socketio 5.x
```

---

### Mistake 4: "Backend won't start - NameError"

**Root Cause:** Missing imports (often after refactoring)

**Detection:**
```bash
tail -20 logs/launchagent_webui_error.log
# Look for: NameError: name 'log' is not defined
```

**Solution:** Add missing imports:
```python
import logging
log = logging.getLogger(__name__)
```

---

## 📋 QUICK REFERENCE COMMANDS

### Backend Management
```bash
# Start
launchctl start com.gridbot.webui

# Stop
launchctl stop com.gridbot.webui

# Restart
launchctl stop com.gridbot.webui && sleep 2 && launchctl start com.gridbot.webui

# Status
launchctl list | grep gridbot.webui

# Logs
tail -f logs/launchagent_webui_error.log
```

### Port Management
```bash
# Check what's using port 5555
lsof -ti:5555

# Kill process on port 5555
lsof -ti:5555 | xargs kill -9

# Verify backend is listening
curl http://localhost:5555/api/health
```

### Currency Verification
```bash
# Check liquidation endpoint (source of truth)
curl -s http://localhost:5555/api/liquidation/status | jq '{
  total_balance: .margin.total_balance,
  available: .margin.available_balance,
  pnl: .mtm.current_mtm_inr
}'

# Should show:
# total_balance: ~103,000 (₹1 lac)
# available: ~92,000
# pnl: ~9,000
```

### Frontend Management
```bash
# Development (hot reload)
cd webui/frontend
npm start  # Runs on port 3000, proxies API to 5555

# Production build
cd webui/frontend
npm run build  # Creates optimized build/

# Clear cache and rebuild
cd webui/frontend
rm -rf build node_modules/.cache
npm run build
```

---

## 🎯 GOLDEN RULES (MEMORIZE THESE)

1. **Port 5555 = Backend ONLY** (Frontend dev uses 3000)
2. **Convert Currency ONCE** (In API endpoints, not consumers)
3. **macOS = LaunchAgent** (Not systemd/pm2/service)
4. **SocketIO versions MUST match** (Backend 5.x, Frontend 4.8+)
5. **Check before modifying** (Is it running? Port free? Data type?)

---

## 📚 Related Documentation

- **backend_frontend.md** - Complete port/architecture reference
- **AI_CONTEXT.md** - Full project context
- **START_HERE.md** - Quick start guide
- **USER_MANUAL.md** - Configuration and usage

---

**Last Updated:** October 31, 2025
**Maintainer:** Shailendra Singh Rajawat
**Emergency Contact:** Check port 5555, read logs, consult this file!
