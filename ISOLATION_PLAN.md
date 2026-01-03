# PRODUCTION ISOLATION PLAN
**Date:** December 31, 2025
**Objective:** Complete separation of production-4.0-clean and BTEH development environments

---

## CURRENT STATE (DANGEROUS)
- ❌ **PROBLEM:** Both branches share `webui/frontend/build/` directory
- ❌ **RISK:** Rebuilding frontend affects BOTH production and development
- ❌ **IMPACT:** Production WebUI (5555) gets polluted with BTEH code

### Active Services:
```
Production (production-4.0-clean):
  - Backend: LaunchAgent on port 5555 ✅ STABLE
  - Frontend: Serves from webui/frontend/build/ ⚠️ CONTAMINATED
  - Bot: gridbot-live (PM2) ✅ RUNNING
  - Guardian: guardian-live (PM2) ✅ RUNNING

Development (BTEH branch):
  - Backend: PM2 webui-backend-dev on port 5556 ✅ RUNNING
  - Frontend: PM2 webui-frontend-dev on port 3001 ✅ RUNNING
  - Bot: NOT RUNNING (development only)
```

---

## ISOLATION STRATEGY

### Phase 1: PROTECT PRODUCTION (IMMEDIATE)
**Goal:** Lock down production-4.0-clean - NO MORE CHANGES

**Actions:**
1. ✅ Stop modifying `webui/frontend/` on BTEH branch
2. ✅ Rebuild production frontend from production-4.0-clean branch
3. ✅ Create snapshot of clean production state
4. ✅ Verify production WebUI stability

### Phase 2: CREATE BTEH DEVELOPMENT ENVIRONMENT
**Goal:** Separate frontend for BTEH development

**Option A: Dedicated Dev Frontend Directory (RECOMMENDED)**
- Create `webui/frontend-dev/` as copy of frontend
- BTEH development uses frontend-dev/
- Production uses original frontend/
- Complete isolation

**Option B: Use React Dev Server Only (CURRENT)**
- Keep using port 3001 React dev server for BTEH
- Never build BTEH frontend
- Production uses stable build from production-4.0-clean

**DECISION:** Option B (React dev server) - Faster, cleaner

### Phase 3: BACKEND ISOLATION
**Goal:** Ensure backend services don't interfere

**Setup:**
```
Production Backend (port 5555):
  - Branch: production-4.0-clean
  - Launch: LaunchAgent (auto-restart)
  - Config: config.yaml (v4.0 single-symbol)
  
BTEH Dev Backend (port 5556):
  - Branch: BTEH
  - Launch: PM2 manual
  - Config: config.yaml (v5.0 multi-symbol)
```

### Phase 4: BRANCH WORKFLOW
**Goal:** Clear separation of code changes

**Rules:**
1. **production-4.0-clean:**
   - NO changes except critical bug fixes
   - NO frontend modifications
   - NO experimental features
   
2. **BTEH:**
   - All development happens here
   - Test with dev server (3001)
   - Only merge to production when stable

---

## EXECUTION PLAN

### Step 1: Restore Production Frontend (5 min)
```bash
# Switch to production branch
git stash  # Save BTEH changes
git checkout production-4.0-clean

# Rebuild clean production frontend
cd webui/frontend
npm run build  # Build with port 5555

# Verify production WebUI
curl http://localhost:5555/

# Return to BTEH
git checkout BTEH
git stash pop
```

### Step 2: Configure BTEH Development (5 min)
```bash
# Ensure PM2 services are running
pm2 start webui-backend-dev  # Port 5556
pm2 start webui-frontend-dev # Port 3001 (React dev server)

# Test BTEH WebUI
open http://localhost:3001
```

### Step 3: Document Ports & Services
```
PRODUCTION (production-4.0-clean):
  ✅ WebUI: http://localhost:5555 (LaunchAgent)
  ✅ Bot: PM2 gridbot-live
  ✅ Guardian: PM2 guardian-live
  
DEVELOPMENT (BTEH):
  ✅ WebUI: http://localhost:3001 (PM2 React dev server)
  ✅ Backend API: http://localhost:5556 (PM2)
  ⚠️ Bot: Not running (dev only)
```

### Step 4: Testing Protocol
1. Production test: Access 5555, verify no errors
2. Development test: Access 3001, test multi-symbol features
3. Isolation test: Change BTEH code, verify 5555 unaffected

---

## RISK MITIGATION

### If Production Breaks:
1. Stop LaunchAgent: `launchctl stop com.gridbot.production.webui`
2. Switch to production-4.0-clean branch
3. Rebuild frontend: `cd webui/frontend && npm run build`
4. Restart LaunchAgent: `launchctl start com.gridbot.production.webui`

### If Development Breaks:
1. Restart dev services: `pm2 restart webui-backend-dev webui-frontend-dev`
2. Check logs: `pm2 logs webui-frontend-dev`
3. No impact on production

---

## SUCCESS CRITERIA
- ✅ Production WebUI (5555) stable with v4.0 code
- ✅ BTEH WebUI (3001) working with v5.0 multi-symbol
- ✅ No shared build artifacts
- ✅ Clear separation documented
- ✅ Production trading continues uninterrupted

---

## NEXT STEPS AFTER ISOLATION
1. Complete BTEH multi-symbol development on port 3001
2. Test thoroughly in development environment
3. When stable, create merge plan for production
4. Only then affect production-4.0-clean branch
