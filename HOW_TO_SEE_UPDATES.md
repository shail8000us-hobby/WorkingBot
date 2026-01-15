# How to See the Production Monitoring Updates

## Why You Couldn't See Changes

The new components were created but **NOT rendered in the WebUI**. Here's what was missing:

1. ❌ `ProductionMonitoringDashboard` wasn't imported in `App.js`
2. ❌ Frontend wasn't rebuilt after adding new components
3. ❌ Backend server may need restart to load new API routes

## ✅ Fixed Now (Commit 4ecc7fcf1)

### 1. Frontend Build
```bash
cd /Users/ssr/Projects/WorkingBot/webui/frontend
npm run build
```
**Status:** ✅ Built successfully (main.34d8cc9a.js created)

### 2. ProductionMonitoringDashboard Added to App.js
**Location:** Between "Monitoring & Recovery System" and "Bot Management Dashboard"

**What it shows:**
- 🔒 **Production Monitoring** panel (purple accent)
  - System Health: CPU, Memory, Disk usage bars
  - API Rate Limits: Order/API/Public endpoint usage
  - Risk Status: Trading permission & risk level
  - Execution Stats: Fill rate, orders placed/filled/failed

### 3. Where to See It

**Main Dashboard:**
1. Open WebUI: `http://localhost:5002` (or your WebUI URL)
2. Scroll down to **Monitoring** section
3. Look for 🔒 **Production Monitoring** (purple card)
4. Click to expand and see real-time metrics

**Options Strategy Builder:**
1. Navigate to **Options → Strategy Builder** tab
2. Create any strategy (straddle, strangle, etc.)
3. You'll see **Pre-Execution Validation** panel
   - Auto-validates strategy structure
   - Checks risk limits
   - Shows ✅ or ❌ before execution

---

## To Restart and See Changes

### Option 1: Restart Backend Only (Fastest)
```bash
# If backend is running in terminal, press Ctrl+C then:
cd /Users/ssr/Projects/WorkingBot/webui/backend
python3 app.py
```

### Option 2: Full Restart
```bash
# Stop all
pkill -f "python.*app.py"
pkill -f "bot_launcher"

# Start backend
cd /Users/ssr/Projects/WorkingBot/webui/backend
python3 app.py &

# Frontend is served from backend, so no separate start needed
```

### Option 3: Check if Backend Loaded New Routes
```bash
# Check backend logs for:
✅ Registered production_monitoring blueprint (health, risk, rate limits)
```

---

## Test the New APIs Directly

### 1. Health Check
```bash
curl http://localhost:5002/api/production/health | jq
```
**Expected Response:**
```json
{
  "status": "success",
  "health": {
    "overall_status": "healthy",
    "cpu_percent": 25.3,
    "memory_percent": 42.1,
    "disk_percent": 68.5
  }
}
```

### 2. Rate Limits
```bash
curl http://localhost:5002/api/production/rate-limits | jq
```

### 3. Risk Status
```bash
curl http://localhost:5002/api/production/risk/can-trade | jq
```

### 4. Combined Dashboard Data
```bash
curl http://localhost:5002/api/production/dashboard | jq
```

---

## Troubleshooting

### "Module not found" errors
**Solution:** Frontend needs rebuild
```bash
cd webui/frontend && npm run build
```

### "404 Not Found" for /api/production/*
**Solution:** Backend hasn't loaded new routes - restart it
```bash
cd webui/backend && python3 app.py
```

### Panel shows "Health monitor not available"
**Solution:** Health monitor initializes on first request - refresh after 5 seconds

### StrategyValidationStatus not showing
**Solution:** 
1. Must be in **Options → Strategy Builder** tab
2. Must have **created a strategy** (not just selected type)
3. Validation panel appears in the right column above Strategy Details

---

## What Each New Component Does

### ProductionMonitoringDashboard.js
**Purpose:** Real-time system monitoring for production trading
**Updates:** Every 5 seconds automatically
**Sections:**
- System Health (CPU/Memory/Disk)
- API Rate Limits (prevents 429 errors)
- Risk Status (trading permission)
- Execution Statistics (fill rates)

### StrategyValidationStatus.js
**Purpose:** Pre-flight checks before executing options strategies
**Validates:**
- Option symbol format
- Strike prices vs spot price
- Strategy structure (correct # of legs)
- Risk limits compliance
**Blocks execution if:** Validation fails or risk limits exceeded

### leg_executor.py Integration
**New Features:**
- Rate limiting (auto-waits if hitting API limits)
- Pre-execution validation (checks before submitting orders)
- Execution statistics tracking
**Safety:** Prevents bad orders from being submitted

---

## Verification Checklist

- [ ] Frontend built (check `webui/frontend/build/` has new files)
- [ ] Backend restarted (see "✅ Registered production_monitoring" in logs)
- [ ] Open WebUI in browser
- [ ] Hard refresh (Cmd+Shift+R or Ctrl+F5)
- [ ] Scroll to "🔒 Production Monitoring" section
- [ ] Click to expand and see 4 panels
- [ ] Navigate to Options → Strategy Builder
- [ ] Create a strategy and see validation panel

---

## Summary

**What was added:**
- 6 new utility files (rate limiter, validators, health monitor, risk manager)
- 1 new API blueprint (10 routes under `/api/production/*`)
- 2 new React components (ProductionMonitoringDashboard, StrategyValidationStatus)
- Integration into existing leg_executor.py and StrategyBuilder.js

**Why you couldn't see it:**
- Components created but not rendered in App.js
- Frontend not rebuilt
- Backend may not have loaded new routes

**Now fixed:**
- ProductionMonitoringDashboard added to App.js (line ~857)
- Frontend rebuilt (build/static/js/main.34d8cc9a.js)
- Ready to see after backend restart

**Git commits:**
- `47f474dcf` - Pre-import checkpoint
- `6e5302df8` - New utility files
- `7e38c047c` - Full integration
- `4ecc7fcf1` - **WebUI rendering fix** ← Current

---

*Generated: January 12, 2026*
