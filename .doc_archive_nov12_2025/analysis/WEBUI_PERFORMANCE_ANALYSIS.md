# WebUI Performance Analysis - Shaky Panel Behavior

**Issue:** Panels showing shaky/laggy behavior  
**Date:** November 2, 2025

---

## 🔍 Root Causes Identified

### 1. **Excessive Polling - Critical Issue** ⚠️

Multiple panels using aggressive polling intervals that overlap with WebSocket updates:

| Panel | Polling Interval | WebSocket | Issue |
|-------|-----------------|-----------|-------|
| **ErrorIntelligenceLive** | **5 seconds** | ❌ No | Too aggressive |
| **SyncReconciliationPanel** | **5 seconds** | ✅ Yes | Redundant |
| **RobustnessPanel** | 30 seconds | ✅ Yes | Redundant |
| **HealthCheckDashboard** | 30 seconds | ✅ Yes | Acceptable |
| **VolatilityChart** | 30 seconds | ✅ Yes | Has debouncing (1s) |

**Problem:**
- 5-second polling causes re-renders 12 times per minute
- WebSocket + polling creates duplicate updates
- Each poll triggers full component re-render

---

### 2. **Multiple Timers in Single Component**

**RobustnessPanel** has 3 concurrent intervals:
```javascript
// Timer 1: Data fetch (30s)
setInterval(() => fetchAllData(), 30000)

// Timer 2: Volatility updates (WebSocket)
socket.on('volatility_update', handleVolatilityUpdate)

// Timer 3: Countdown timer (1s)
setInterval(tick, 1000)
```

**Impact:** 1 panel = 3 timers = 3× state updates

---

### 3. **useCallback Dependency Issues**

Many components have `useCallback` with empty `[]` dependencies, causing:
- Stale closures
- Missed updates
- Unnecessary re-renders when dependencies change

**Example (RobustnessPanel):**
```javascript
const fetchAllData = useCallback(async () => {
  // Uses state/props but has empty deps
}, []);  // ❌ Missing dependencies
```

---

### 4. **No Debouncing on Real-time Updates**

**ErrorIntelligenceLive** updates on every message without delay:
```javascript
// Every 5 seconds = instant state update
useEffect(() => {
  if (autoRefresh) {
    interval = setInterval(() => {
      fetchErrors(true); // Immediate setState
    }, 5000);
  }
}, [severityFilter, autoRefresh]);
```

**Impact:** Rapid fire state changes cause UI flicker

---

### 5. **Socket Connection Issues**

**Multiple socket instances:**
- `useSocket()` hook creates singleton
- Some components import directly from `socket.io-client`
- `RobustConnectionManager` creates another instance

**Result:** 2-3 WebSocket connections fighting for updates

---

### 6. **Countdown Timers**

Multiple 1-second interval timers for countdowns:
```javascript
// RobustnessPanel - next update countdown
setInterval(tick, 1000)

// Other panels have similar
```

**Impact:** 60 re-renders per minute per panel

---

## 🎯 Performance Metrics

### Current State:
- **ErrorIntelligenceLive**: 12 polls/min + continuous re-renders
- **SyncReconciliationPanel**: 12 polls/min + WebSocket
- **RobustnessPanel**: 2 polls/min + WebSocket + 60 countdown updates/min
- **Total**: ~86 state updates per minute minimum

### Memory Leaks:
- Timer cleanup in `return () => clearInterval()` - ✅ Good
- WebSocket cleanup - ✅ Good  
- But multiple subscriptions might not cleanup properly

---

## ✅ Recommended Fixes

### Fix 1: Reduce Polling Frequency (High Priority)

```javascript
// ErrorIntelligenceLive.js
// BEFORE: 5 seconds (too aggressive)
interval = setInterval(() => fetchErrors(true), 5000);

// AFTER: 30 seconds OR remove polling (use WebSocket only)
interval = setInterval(() => fetchErrors(true), 30000);
```

### Fix 2: Remove Redundant Polling

Panels with WebSocket don't need polling:
```javascript
// BEFORE: Both WebSocket + Polling
useEffect(() => {
  fetchData();
  const interval = setInterval(fetchData, 30000);
  return () => clearInterval(interval);
}, []);

useEffect(() => {
  socket.on('update', handleUpdate);
  return () => socket.off('update', handleUpdate);
}, [socket]);

// AFTER: WebSocket only (with fallback)
useEffect(() => {
  fetchData(); // Initial load only
  
  if (socket) {
    socket.on('update', handleUpdate);
    return () => socket.off('update', handleUpdate);
  } else {
    // Fallback polling if no socket
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }
}, [socket]);
```

### Fix 3: Debounce State Updates

```javascript
// Add debouncing to rapid updates
const debouncedSetState = useMemo(() => 
  debounce((newState) => setState(newState), 500),
  []
);

socket.on('rapid_update', (data) => {
  debouncedSetState(data); // Debounced
});
```

### Fix 4: Fix useCallback Dependencies

```javascript
// BEFORE (causes issues)
const fetchAllData = useCallback(async () => {
  // Uses state
}, []); // ❌ Missing deps

// AFTER
const fetchAllData = useCallback(async () => {
  // Uses state
}, [/* add all dependencies */]);

// OR use useRef for stable references
const fetchAllData = useRef();
fetchAllData.current = async () => {
  // No dependency issues
};
```

### Fix 5: Optimize Countdown Timers

```javascript
// BEFORE: 1 second interval (60 updates/min)
setInterval(tick, 1000);

// AFTER: Only update when visible or needed
useEffect(() => {
  if (!isVisible) return; // Skip if panel hidden
  
  const tick = () => {
    const newCount = calculateCountdown();
    if (newCount !== countdown) { // Only update if changed
      setCountdown(newCount);
    }
  };
  
  const interval = setInterval(tick, 5000); // Less frequent
  return () => clearInterval(interval);
}, [isVisible, countdown]);
```

### Fix 6: Single Socket Instance

Ensure all components use the same socket:
```javascript
// Use useSocket() hook everywhere
import { useSocket } from '../hooks/useSocket';

const MyPanel = () => {
  const socket = useSocket(); // Singleton
  // ...
};
```

---

## 📊 Impact Assessment

### By Panel:

**ErrorIntelligenceLive:**
- Current: 12 polls/min + continuous re-renders
- After fix: 2 polls/min OR WebSocket only
- **Improvement: 83% less API calls**

**SyncReconciliationPanel:**
- Current: 12 polls/min + WebSocket
- After fix: WebSocket only (with 60s fallback)
- **Improvement: 90% less polling**

**RobustnessPanel:**
- Current: 2 polls/min + 60 countdown updates/min
- After fix: WebSocket + 12 countdown updates/min
- **Improvement: 80% less updates**

---

## 🚀 Quick Fixes (Priority Order)

### 1. **Immediate** - Change Aggressive Polling

```bash
# ErrorIntelligenceLive: 5s → 30s
# SyncReconciliationPanel: 5s → 30s (or WebSocket only)
```

### 2. **High** - Add Debouncing

```bash
# Install lodash if not present
npm install lodash
```

### 3. **Medium** - Fix useCallback Dependencies

Run ESLint to find issues:
```bash
npm run lint
```

### 4. **Low** - Optimize Countdowns

Use 5s intervals instead of 1s

---

## 🔧 Implementation Plan

### Phase 1: Quick Wins (15 mins)
1. Change `ErrorIntelligenceLive` polling: 5s → 30s
2. Change `SyncReconciliationPanel` polling: 5s → 30s
3. Add `React.memo()` to heavy components

### Phase 2: Debouncing (30 mins)
1. Add debounce utility
2. Wrap rapid state updates
3. Test with Chrome DevTools Performance

### Phase 3: Socket Optimization (45 mins)
1. Audit all socket usage
2. Consolidate to `useSocket()` hook
3. Remove redundant connections

### Phase 4: Memory Optimization (30 mins)
1. Add cleanup verification
2. Test for memory leaks
3. Profile with React DevTools

---

## 📝 Testing Checklist

After fixes:

- [ ] Open Chrome DevTools → Performance
- [ ] Record 60 seconds of WebUI usage
- [ ] Check for:
  - [ ] Frequent re-renders (should be < 10/min per panel)
  - [ ] Memory leaks (heap should be stable)
  - [ ] Long tasks (should be < 50ms)
  - [ ] API call frequency (should match expected intervals)
- [ ] Test each panel individually
- [ ] Test with multiple panels open
- [ ] Test on mobile (if applicable)

---

## 🎯 Expected Results

**Before:**
- ~86 state updates/minute
- Visible UI lag
- High CPU usage
- Shaky animations

**After:**
- ~20 state updates/minute (75% reduction)
- Smooth UI
- Lower CPU usage
- Stable animations

---

## 📚 Related Files

**Components to Fix:**
1. `webui/frontend/src/components/ErrorIntelligenceLive.js` (5s → 30s)
2. `webui/frontend/src/components/SyncReconciliationPanel.js` (5s → 30s)
3. `webui/frontend/src/components/RobustnessPanel.js` (optimize countdown)
4. `webui/frontend/src/components/VolatilityChart.js` (already has debouncing ✅)
5. `webui/frontend/src/components/HealthCheckDashboard.js` (acceptable as-is ✅)

**Utilities to Update:**
1. `webui/frontend/src/hooks/useSocket.js` ✅ Good
2. `webui/frontend/src/utils/RobustConnectionManager.js` - Check for duplicates
3. `webui/frontend/src/utils/connectionManager.js` - Consolidate if needed

---

*Last Updated: November 2, 2025*

