# ✅ PRODUCTION & DEVELOPMENT ISOLATION - COMPLETE

**Date:** December 31, 2025  
**Status:** ✅ SUCCESSFULLY ISOLATED  
**Risk Level:** 🟢 SAFE - Production Protected

---

## FINAL CONFIGURATION

### 🔒 PRODUCTION ENVIRONMENT (PROTECTED)
```
Branch:    production-4.0-clean
WebUI:     http://localhost:5555 (LaunchAgent - auto-restart)
Backend:   Flask app serving from webui/frontend/build/
Frontend:  v4.0 single-symbol (clean build)
Bot:       PM2 gridbot-live (BTCUSD LONG)
Guardian:  PM2 guardian-live
Config:    config.yaml (v4.0 format)

Status:    ✅ STABLE - NO CHANGES ALLOWED
```

### 🛠️ DEVELOPMENT ENVIRONMENT (BTEH)
```
Branch:    BTEH
WebUI:     http://localhost:3001 (React dev server with hot-reload)
Backend:   http://localhost:5556 (PM2 webui-backend-dev)
Frontend:  v5.0 multi-symbol (development mode)
Bot:       NOT RUNNING (development only)
Config:    config.yaml (v5.0 format with BTCUSD + ETHUSD)

Status:    ✅ ACTIVE - Safe to modify
```

---

## ISOLATION GUARANTEES

### ✅ What's Protected:
1. **Production WebUI (5555)** - Built from production-4.0-clean branch
2. **Production Trading** - gridbot-live and guardian-live untouched
3. **Production Config** - Separate from BTEH config
4. **LaunchAgent** - Serves stable v4.0 frontend

### ✅ What's Isolated:
1. **BTEH Development** - Uses React dev server (port 3001)
2. **BTEH Backend** - Runs on separate port (5556)
3. **BTEH Frontend** - Never builds to production directory
4. **BTEH Changes** - Stay in BTEH branch

---

## WORKFLOW RULES

### 🔴 PRODUCTION (Never Touch Unless Critical Bug)
```bash
# Only for emergency fixes:
git checkout production-4.0-clean
# Make MINIMAL changes
cd webui/frontend && npm run build
# Test thoroughly
git commit && git push
```

### 🟢 DEVELOPMENT (Work Freely)
```bash
# Always work on BTEH branch:
git checkout BTEH

# Frontend changes auto-reload at port 3001
# Backend changes: pm2 restart webui-backend-dev

# Test at: http://localhost:3001
```

---

## PM2 SERVICES MANAGEMENT

### Check Status:
```bash
pm2 list
```

### Development Services:
```bash
# Start dev services
pm2 start webui-backend-dev webui-frontend-dev

# Restart after changes
pm2 restart webui-backend-dev

# View logs
pm2 logs webui-frontend-dev --lines 50
```

### Production Services (LaunchAgent - Auto-managed):
```bash
# Status
launchctl list | grep gridbot

# Manual restart (if needed)
launchctl stop com.gridbot.production.webui
launchctl start com.gridbot.production.webui
```

---

## TESTING CHECKLIST

### Before Any Production Change:
- [ ] All changes tested on BTEH (port 3001)
- [ ] Multi-symbol features verified
- [ ] No errors in browser console
- [ ] Backend API stable
- [ ] Production (5555) still working
- [ ] Trading bots still running
- [ ] Guardian still monitoring

### After Production Rebuild (Emergency Only):
- [ ] Access http://localhost:5555
- [ ] Verify dashboard loads
- [ ] Check bot status
- [ ] Confirm trading continues
- [ ] Monitor for 10 minutes

---

## PORT REFERENCE

| Service | Port | Branch | Purpose |
|---------|------|--------|---------|
| Production WebUI | 5555 | production-4.0-clean | Live trading interface |
| Dev WebUI | 3001 | BTEH | Development & testing |
| Dev Backend API | 5556 | BTEH | Development API server |
| Production Bot | - | production-4.0-clean | PM2 gridbot-live |
| Guardian | - | production-4.0-clean | PM2 guardian-live |

---

## CURRENT BRANCH WORK

**You are on:** `BTEH` branch  
**Working with:** Port 3001 (dev server)  
**Production:** Unaffected and stable on port 5555

### To Continue BTEH Development:
```bash
# 1. Verify you're on BTEH branch
git branch

# 2. Check dev services running
pm2 list

# 3. Access development WebUI
open http://localhost:3001

# 4. Make changes to frontend - auto-reload happens
# Files in: webui/frontend/src/

# 5. Backend changes require restart
pm2 restart webui-backend-dev
```

---

## EMERGENCY PROCEDURES

### If Production Breaks:
```bash
# 1. Switch to production branch
git checkout production-4.0-clean

# 2. Rebuild frontend
cd webui/frontend && npm run build

# 3. Restart LaunchAgent
launchctl restart com.gridbot.production.webui

# 4. Verify
curl http://localhost:5555/api/health
```

### If Development Breaks:
```bash
# Just restart - no impact on production
pm2 restart webui-backend-dev webui-frontend-dev

# Or delete and restart
pm2 delete webui-frontend-dev
pm2 start webui/start_dev_frontend.sh --name webui-frontend-dev
```

---

## SUCCESS METRICS

✅ **Achieved:**
- Production WebUI (5555) serving clean v4.0 code
- Development WebUI (3001) running v5.0 multi-symbol code
- Zero interference between environments
- Production trading continues uninterrupted
- Clear separation documented

✅ **Protected:**
- Production branch remains pristine
- Live trading never disrupted
- Stable production frontend preserved

✅ **Enabled:**
- Safe BTEH development
- Multi-symbol feature testing
- Risk-free experimentation

---

## NEXT STEPS

1. ✅ **Test BTEH features on port 3001** - Fix any errors in dev environment
2. ✅ **Complete multi-symbol implementation** - Symbol selector, MonitoringDashboard, etc.
3. ✅ **Integration testing** - Test with real config.yaml (v5.0)
4. ⏳ **When stable** - Create merge plan to production
5. ⏳ **Production upgrade** - Only after thorough testing

---

**🔒 PRODUCTION IS NOW SAFE**  
**🛠️ DEVELOPMENT CAN PROCEED FREELY**  
**📊 BOTH ENVIRONMENTS VERIFIED WORKING**
