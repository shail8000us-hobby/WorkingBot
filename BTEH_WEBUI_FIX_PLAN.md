# 🔧 BTEH BRANCH WEBUI FIX PLAN (Port 3001)
**Date:** January 4, 2026  
**Branch:** BTEH  
**Port:** 3001  
**Status:** 🔴 6 Critical Issues

---

## 📊 **ISSUE SUMMARY**

| # | Component | Issue | Status | Priority |
|---|-----------|-------|--------|----------|
| 1 | Market Signal Intelligence | "Market signal waiting for bot" | 🔴 Broken | P0 |
| 2 | Risk Intelligence | "Error intelligence idle" | 🔴 Broken | P0 |
| 3 | Open Positions | "No positions until bot starts" | 🔴 Broken | P0 |
| 4 | PM2 Process Manager | Shows 0 processes (not multi-instance aware) | 🔴 Broken | P0 |
| 5 | AI Advisor & Institutional Toolkit | "AI Advisor paused" | 🔴 Broken | P1 |
| 6 | Live Logs Stream | "Logs unavailable" | 🔴 Broken | P1 |

---

## 🔍 **ROOT CAUSE ANALYSIS**

### **Current State:**
- ✅ WebUI Backend running on port 3001 (PID 3414)
- ✅ API responding: `{"pm2_managed":true,"running":false}`
- ❌ **NO bots running via PM2** (`pm2 list` is empty)
- ⚠️ Guardian running manually (PID 792) - not via PM2
- ⚠️ GridBot NOT running at all

### **Why Everything is Broken:**
1. **WebUI expects PM2-managed processes** but BTEH branch bots run manually
2. **No GridBot running** → No positions, no trading data, no logs
3. **Guardian not via PM2** → PM2 panel shows 0 processes
4. **Backend can't find bot data** → All intelligence modules idle

---

## ✅ **FIX PLAN - 3 PHASES**

---

## **PHASE 1: START BOTS WITH PM2 (30 minutes)**

### Step 1.1: Verify ecosystem.config.js for BTEH branch
**Action:** Check if ecosystem.config.js exists and is configured for BTEH

```bash
# Check ecosystem config
cat ecosystem.config.js | grep -A 10 "gridbot"
```

**Expected:** Should have entries for:
- `gridbot-btcusd-live` (or similar)
- `guardian-live`

### Step 1.2: Start GridBot via PM2
**Action:** Start the main trading bot

```bash
# From BTEH branch
pm2 start ecosystem.config.js --only gridbot-live
# OR if multi-symbol:
pm2 start ecosystem.config.js --only gridbot-btcusd-live
```

**Verification:**
```bash
pm2 list  # Should show gridbot running
pm2 logs gridbot-live --lines 20  # Check for errors
```

### Step 1.3: Restart Guardian via PM2
**Action:** Stop manual Guardian (PID 792) and start via PM2

```bash
# Stop manual guardian
kill 792

# Start via PM2
pm2 start ecosystem.config.js --only guardian-live
```

**Verification:**
```bash
pm2 list  # Should show 2+ processes
curl http://localhost:3001/api/bot/status  # Should show running:true
```

**Expected Result After Phase 1:**
- ✅ PM2 shows 2+ processes
- ✅ GridBot trading
- ✅ Guardian monitoring
- ✅ Open Positions panel shows data
- ✅ PM2 Process Manager shows processes

---

## **PHASE 2: FIX INTELLIGENCE MODULES (1 hour)**

### Step 2.1: Fix Market Signal Intelligence
**Issue:** "Market signal waiting for bot"  
**Root Cause:** Backend route expects WebSocket data from bot

**Files to Check:**
- `webui/backend/routes/monitoring.py` - Market signal endpoint
- `bot/strategy/async_gridbot.py` - Signal emission

**Action:**
```python
# Check if bot emits market signals
grep -r "market_signal" webui/backend/routes/
grep -r "volatility" webui/backend/routes/
```

**Fix Options:**
1. **If signal route exists:** Ensure bot is emitting signals
2. **If missing:** Add signal aggregation endpoint in `monitoring.py`

### Step 2.2: Fix Risk Intelligence
**Issue:** "Error intelligence idle"  
**Root Cause:** Live log parsing requires bot to be running

**Files to Check:**
- `webui/backend/routes/monitoring.py` - Risk intelligence endpoint
- `bot/logs/gridbot_detailed.log` - Log file path

**Action:**
```bash
# Verify log file exists and is being written
tail -f bot/logs/gridbot_detailed.log
```

**Fix:**
```python
# In monitoring.py, ensure log path points to correct file
LOG_FILE = "bot/logs/gridbot_detailed.log"
```

### Step 2.3: Fix AI Advisor
**Issue:** "AI Advisor paused"  
**Root Cause:** Requires real-time telemetry from bot

**Files to Check:**
- `webui/backend/routes/monitoring.py` - AI advisor endpoint
- `webui/backend/utils/bot_prediction_engine.py` - Brain analyzer

**Action:**
1. Check if bot is streaming telemetry
2. Verify brain analyzer can read bot state

---

## **PHASE 3: FIX PM2 MULTI-INSTANCE AWARENESS (1 hour)**

### Step 3.1: Update PM2 Process Manager Component
**Issue:** Panel shows "0" for all tabs (By Symbol, Live Trading, Demo Trading, All Processes)

**Root Cause:** Frontend component not parsing V6.0 multi-instance naming

**Files to Modify:**
- `webui/frontend/src/components/PM2Panel.js` (or similar)
- `webui/backend/routes/pm2_manager.py` (if exists)

**Current Naming:** V6.0 uses `BTCUSD_LONG`, `BTCUSD_SHORT`  
**Expected:** Component should parse `SYMBOL_MODE` format

**Fix:**
```javascript
// In PM2Panel.js
const parseInstanceName = (name) => {
  // OLD: gridbot-live, gridbot-demo
  // NEW: gridbot-btcusd-long, gridbot-btcusd-short
  const match = name.match(/gridbot-(\w+)-(\w+)/);
  if (match) {
    return {
      symbol: match[1].toUpperCase(),
      mode: match[2].toUpperCase(),
      isLive: match[2] === 'live' || match[2] === 'long' || match[2] === 'short'
    };
  }
  return null;
};
```

### Step 3.2: Update Symbol Filtering
**Action:** Make "By Symbol" tab group by BTCUSD, ETHUSD, etc.

**Logic:**
```javascript
const groupBySymbol = (processes) => {
  return processes.reduce((groups, proc) => {
    const parsed = parseInstanceName(proc.name);
    if (parsed) {
      if (!groups[parsed.symbol]) groups[parsed.symbol] = [];
      groups[parsed.symbol].push(proc);
    }
    return groups;
  }, {});
};
```

### Step 3.3: Update Tab Counts
**Action:** Make counters reflect actual running processes

```javascript
// In PM2Panel.js
const liveCount = processes.filter(p => {
  const parsed = parseInstanceName(p.name);
  return parsed && parsed.isLive && p.status === 'online';
}).length;
```

---

## **PHASE 4: FIX LIVE LOGS STREAM (30 minutes)**

### Step 4.1: Check Log File Path
**Issue:** "Logs unavailable"  
**Root Cause:** Backend can't find log file or bot not writing logs

**Files to Check:**
- `webui/backend/routes/logs.py` - Log streaming endpoint
- `bot/logs/gridbot_detailed.log` - Actual log file

**Action:**
```bash
# Check if log exists and is growing
ls -lh bot/logs/gridbot_detailed.log
tail -f bot/logs/gridbot_detailed.log | head -20
```

**Fix:**
```python
# In logs.py, update log path for BTEH branch
LOG_FILE_PATH = Path(__file__).parent.parent.parent / "bot" / "logs" / "gridbot_detailed.log"
```

### Step 4.2: Restart WebUI Backend (if needed)
**Action:** If log path was wrong, restart backend to reload config

```bash
# Kill current webui
kill 3414

# Restart on port 3001
cd /Users/ssr/Projects/WorkingBot
nohup python3 webui/backend/app.py 3001 > webui/logs/webui_3001.log 2>&1 &
```

---

## 📋 **EXECUTION CHECKLIST**

### **Phase 1: Start Bots (DO THIS FIRST)** ⏱️ 30 min
- [ ] Check `ecosystem.config.js` configuration
- [ ] Start GridBot via PM2: `pm2 start ecosystem.config.js --only gridbot-live`
- [ ] Stop manual Guardian (kill 792)
- [ ] Start Guardian via PM2: `pm2 start ecosystem.config.js --only guardian-live`
- [ ] Verify: `pm2 list` shows 2+ processes
- [ ] Verify: `curl localhost:3001/api/bot/status` shows `running:true`
- [ ] **Test:** Open Positions panel should show data
- [ ] **Test:** PM2 Process Manager should show processes

### **Phase 2: Fix Intelligence** ⏱️ 1 hour
- [ ] Check Market Signal route in `monitoring.py`
- [ ] Verify bot emits signals
- [ ] Check Risk Intelligence log parsing
- [ ] Verify AI Advisor brain analyzer
- [ ] **Test:** All 3 intelligence panels show data

### **Phase 3: Fix PM2 Multi-Instance** ⏱️ 1 hour
- [ ] Update PM2Panel.js to parse `SYMBOL_MODE` naming
- [ ] Add symbol grouping logic
- [ ] Update tab counters
- [ ] Rebuild frontend: `cd webui/frontend && npm run build`
- [ ] Restart backend on 3001
- [ ] **Test:** PM2 panel shows correct counts in all tabs

### **Phase 4: Fix Logs Stream** ⏱️ 30 min
- [ ] Verify log file path in backend
- [ ] Check bot is writing logs
- [ ] Update log route if needed
- [ ] Restart backend if config changed
- [ ] **Test:** Live Logs panel streams data

---

## 🎯 **EXPECTED RESULTS**

After completing all phases:

| Component | Before | After |
|-----------|--------|-------|
| Market Signal Intelligence | ❌ Waiting | ✅ Showing volatility data |
| Risk Intelligence | ❌ Idle | ✅ Scanning logs |
| Open Positions | ❌ Empty | ✅ Showing grid positions |
| PM2 Process Manager | ❌ 0 processes | ✅ 2+ processes with tabs |
| AI Advisor | ❌ Paused | ✅ Active predictions |
| Live Logs Stream | ❌ Unavailable | ✅ Streaming bot logs |

---

## 🚨 **CRITICAL NOTES**

1. **Port Isolation:**
   - Port 3001 (BTEH branch) - Development only
   - Port 5555 (production-4.0-clean) - Leave untouched!

2. **PM2 vs Manual:**
   - BTEH must use PM2 for WebUI to work
   - Don't run bots manually (python bot/strategy/async_gridbot.py)

3. **Multi-Instance Naming:**
   - V6.0 format: `gridbot-SYMBOL-MODE` (e.g., `gridbot-btcusd-long`)
   - Old format: `gridbot-live`, `gridbot-demo`
   - Frontend must support both

4. **Testing Order:**
   - Always start with Phase 1 (bots running)
   - Without bots, nothing else will work

---

## 📞 **QUICK COMMANDS**

```bash
# Check what's running
pm2 list
lsof -i :3001
ps aux | grep -E "gridbot|guardian"

# Start BTEH bots
pm2 start ecosystem.config.js

# Restart WebUI backend
kill 3414 && cd /Users/ssr/Projects/WorkingBot && nohup python3 webui/backend/app.py 3001 > webui/logs/webui_3001.log 2>&1 &

# Check logs
pm2 logs gridbot-live --lines 50
tail -f webui/logs/webui_3001.log
tail -f bot/logs/gridbot_detailed.log

# Rebuild frontend
cd webui/frontend && npm run build
```

---

**Total Estimated Time:** 3 hours  
**Priority:** P0 - Critical for BTEH branch development
