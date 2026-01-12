# WebUI Consolidation Strategy - January 3, 2026

## 🔴 Current Mess - Multiple WebUI Versions

### Active Services Right Now:
```
Port 5555: Production Backend (LaunchAgent) - 4.0 clean branch
Port 5557: BTEH Dev Backend (PM2) - Current branch
Port 3001: V1 Frontend (PM2) - React, WORKING ✅
Port 3002: V2 Frontend (NOT RUNNING) - Unknown state
Port 3003: V3 Frontend (PM2, stopped) - Next.js, NOT READY ❌
```

### Directory Structure:
```
webui/
├── backend/           # Flask backend (multiple configs)
├── frontend/          # V1 React (100% multi-instance ready) ✅
├── frontend-v2/       # V2 (unknown state)
└── frontend-v3/       # V3 Next.js (incomplete)
```

---

## ✅ RECOMMENDED STRATEGY: Focus on V1

### Decision Matrix:

| Version | Port | Status | Multi-Instance | Action |
|---------|------|--------|----------------|--------|
| **Production** | 5555 | Running | ❌ 4.0 only | Keep for legacy |
| **V1 (Dev)** | 3001 | Working | ✅ 100% ready | **PRIMARY DEV** |
| **V2** | 3002 | Unknown | ❓ Unknown | **DISABLE** |
| **V3** | 3003 | Incomplete | ❓ Not ready | **DISABLE** |

---

## 🎯 IMMEDIATE ACTION PLAN

### Step 1: Stop Confusing Services
```bash
# Stop V3 (already stopped, keep it that way)
pm2 delete frontend-v3

# Check if V2 exists in PM2
pm2 list | grep v2
# If found, stop it

# Keep V1 running
pm2 list webui-frontend-dev  # Should be online
```

### Step 2: Clear Port Mapping

**PRODUCTION (4.0 clean branch):**
- Backend: Port 5555 (LaunchAgent)
- Frontend: Served by backend on 5555
- Branch: `4.0-clean` or `main`
- Purpose: Legacy production system

**DEVELOPMENT (BTEH branch - Current Work):**
- Backend: Port 5557 (PM2: webui-backend-dev)
- Frontend: Port 3001 (PM2: webui-frontend-dev)
- Branch: `BTEH`
- Purpose: V6.0 multi-instance development
- Status: **100% multi-instance implementation complete**

### Step 3: Documentation Update

Create clear separation in ecosystem.gridbot.config.js:

```javascript
// PRODUCTION SERVICES (Port 5555 - LaunchAgent managed)
// - Not in PM2, managed by macOS LaunchAgent
// - For 4.0 clean branch only

// DEVELOPMENT SERVICES (BTEH branch only)
{
  name: "webui-backend-dev",
  script: "webui/backend/app_dev.py",
  port: 5557  // Development backend
},
{
  name: "webui-frontend-dev", 
  script: "npm start",
  port: 3001  // Development frontend (V1 React)
}

// V2 and V3 - DISABLED until ready
// Do not use these in ecosystem config
```

---

## 📋 Workflow Going Forward

### For BTEH Branch Development (Multi-Instance Work):
```bash
# 1. Ensure you're on BTEH branch
git branch --show-current  # Should show: BTEH

# 2. Start dev backend (if not running)
pm2 start ecosystem.gridbot.config.js --only webui-backend-dev

# 3. Start dev frontend V1 (if not running)
pm2 start ecosystem.gridbot.config.js --only webui-frontend-dev

# 4. Access at:
# http://localhost:3001 (Frontend)
# Backend API: http://localhost:5557/api/*
```

### For Production Branch (4.0 clean):
```bash
# 1. Switch to production branch
git checkout 4.0-clean  # or main

# 2. Use LaunchAgent backend only
launchctl start com.gridbot.webui

# 3. Access at:
# http://localhost:5555
```

---

## 🗑️ What to Delete/Disable

### Immediate Actions:

1. **Remove V3 from PM2 permanently:**
   ```bash
   pm2 delete frontend-v3
   pm2 save
   ```

2. **Comment out V2/V3 in ecosystem.gridbot.config.js:**
   - Find frontend-v2 and frontend-v3 entries
   - Comment them out or remove
   - Prevent accidental starts

3. **Archive V2/V3 directories (optional):**
   ```bash
   cd webui
   mkdir archive/incomplete-versions
   mv frontend-v2 archive/incomplete-versions/ 2>/dev/null || true
   mv frontend-v3 archive/incomplete-versions/ 2>/dev/null || true
   ```

---

## ✅ Benefits of This Consolidation

1. **Clear Separation:**
   - Production: Port 5555 (LaunchAgent)
   - Development: Ports 5557 + 3001 (PM2)

2. **No Confusion:**
   - Only ONE active development frontend (V1)
   - V2/V3 disabled until explicitly needed

3. **100% Multi-Instance Ready:**
   - V1 has complete instance support
   - All 24 backend routes instance-aware
   - All 12 frontend components instance-aware
   - Tested and verified

4. **Easier Context Switching:**
   - BTEH branch → Use PM2 services (5557/3001)
   - Production branch → Use LaunchAgent (5555)

---

## 🚀 When to Introduce V2/V3

**V2 Criteria:**
- [ ] Clear differentiation from V1 documented
- [ ] Multi-instance support verified
- [ ] Feature parity with V1 achieved
- [ ] User explicitly requests it

**V3 Criteria:**
- [ ] Next.js setup complete
- [ ] Multi-instance architecture implemented
- [ ] All V1 features migrated
- [ ] Performance benefits proven
- [ ] User explicitly requests it

**Until then:** V1 is the ONLY development frontend.

---

## 📝 Environment Variables Clarity

### Production (Port 5555):
```env
NODE_ENV=production
FLASK_ENV=production
PORT=5555
```

### Development V1 (Ports 5557/3001):
```env
NODE_ENV=development
FLASK_ENV=development

# Backend
BACKEND_PORT=5557

# Frontend
PORT=3001
REACT_APP_API_URL=http://localhost:5557
REACT_APP_SOCKET_URL=http://localhost:5557
```

---

## 🔍 Quick Status Check Commands

```bash
# See all active services
pm2 list

# Check which ports are listening
lsof -i :5555 -i :5557 -i :3001 -i :3002 -i :3003 | grep LISTEN

# Check LaunchAgent
launchctl list | grep gridbot

# Current branch
git branch --show-current

# Current running services
pm2 jlist | jq '.[] | select(.name | contains("webui")) | {name, status: .pm2_env.status, port: .pm2_env.PORT}'
```

---

## 🎯 SUMMARY - The Clean Setup

**Production (4.0 clean branch):**
- Service: LaunchAgent com.gridbot.webui
- Port: 5555
- URL: http://localhost:5555
- Use: Legacy production

**Development (BTEH branch - CURRENT WORK):**
- Backend: PM2 webui-backend-dev on port 5557
- Frontend: PM2 webui-frontend-dev on port 3001 (V1 React)
- URL: http://localhost:3001
- Use: Multi-instance development

**Disabled:**
- V2 (all instances)
- V3 (all instances)

**Your Take is 100% Correct:** Work on V1 until V3 is completely ready. V1 has full multi-instance support and is production-ready for the BTEH branch.
