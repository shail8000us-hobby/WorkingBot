# WebUI v1 vs v3 - Feature Comparison & Roadmap

**Date:** January 2, 2026  
**Status:** v3 Basic Implementation Complete, Missing Advanced Features from v1

---

## Critical Issues Fixed (Jan 2, 2026)

### ✅ Immediate Fixes Applied:

1. **API Endpoints Corrected:**
   - ❌ `/api/instances` → ✅ `/api/instances/list`
   - ❌ `/api/trading/status` → ✅ `/api/trading_status`
   - ✅ Guardian status errors handled gracefully (backend returns 500)
   - ✅ WebSocket URL corrected to `ws://localhost:5555/ws`

2. **React Warnings Fixed:**
   - ✅ Missing `key` props in position lists
   - ✅ Position type updated (`id` now optional)
   - ✅ Guardian query refetch interval increased (3s → 10s)

3. **Error Handling:**
   - ✅ Guardian 500 errors handled gracefully
   - ✅ Retry logic limited to prevent console spam
   - ✅ Background refetching disabled for problematic endpoints

---

## Feature Comparison

### Core Trading Features

| Feature | v1 | v3 | Status |
|---------|----|----|--------|
| **Positions Display** | ✅ Full table | ✅ Card grid | COMPLETE |
| **Orders Management** | ✅ Full table | ✅ Card grid | COMPLETE |
| **P&L Summary** | ✅ Multiple views | ✅ Chart | COMPLETE |
| **Bot Status** | ✅ Detailed | ✅ Basic | COMPLETE |
| **Guardian Status** | ✅ Full dashboard | ⚠️ Basic | PARTIAL |
| **Trading Mode** | ✅ Switch | ⚠️ Missing | **TODO** |

### Data Points v1 Has That v3 Needs

#### 1. Health Monitoring (v1 has comprehensive health dashboard)
```javascript
// v1 endpoints:
/api/health/detailed  // ← Missing in v3
/api/health           // Partial in v3
/api/websocket/health // ← Missing in v3
/api/errors/statistics // ← Missing in v3
```

**v3 TODO:** Add comprehensive health monitoring dashboard

#### 2. Volatility & Market Signals
```javascript
// v1 endpoints:
/api/volatility/signal    // ← Missing in v3
/api/liquidation/status   // ← Missing in v3
```

**v3 TODO:** Add VolatilityRegimePanel component

#### 3. Incident/Error Management
```javascript
// v1 endpoints:
/api/errors/?status=open
/api/errors/acknowledge
/api/errors/resolve
/api/errors/run_fix
```

**v3 TODO:** Add IncidentsPanel component

#### 4. Configuration Management
```javascript
// v1 endpoints:
/api/config/confirm-runtime
/api/config/verify
/api/config/apply
/api/utility/check-log
```

**v3 TODO:** Add ConfigPanel component

#### 5. Robustness & Safety
```javascript
// v1 endpoints:
/api/robustness/gatekeeper/status
/api/robustness/loss-limits
/api/robustness/reset-safety-limits
```

**v3 TODO:** Add Robustness dashboard

#### 6. Symbols & Instances
```javascript
// v1 endpoints:
/api/symbols  // ← Missing in v3
/api/instances // Implemented as /api/instances/list
```

**v3 TODO:** Add symbol selector

---

## Architecture Differences

### v1 Architecture:
- **State:** Zustand store with data aggregator
- **Data Fetching:** Custom `dataAggregator` service
- **Real-time:** WebSocket + polling hybrid
- **UI:** Material-UI components
- **Features:** Guardian Dashboard, Health Checks, Incident Management

### v3 Architecture:
- **State:** Zustand + TanStack Query
- **Data Fetching:** TanStack Query hooks (more modern)
- **Real-time:** WebSocket client (similar to v1)
- **UI:** shadcn/ui + Tailwind CSS (more modern)
- **Features:** Basic dashboard only

---

## What v3 Does Better

✅ **Modern Stack:**
- Next.js 16 with App Router
- React Server Components
- TanStack Query v5 (better caching)
- TypeScript strict mode
- Tailwind CSS v4

✅ **Better DX:**
- Hot module replacement
- Type safety
- Better error boundaries
- Modern component architecture

✅ **Performance:**
- Faster initial load
- Better code splitting
- Server-side rendering ready

---

## What v1 Does Better

✅ **Feature Completeness:**
- Full guardian dashboard
- Health monitoring
- Incident/error management
- Configuration tools
- Market signal panels
- Volatility indicators

✅ **Data Points:**
- More comprehensive metrics
- Better real-time updates
- More detailed status info
- Error tracking & resolution

✅ **User Features:**
- Help system
- Command knowledge base
- Emergency controls
- Instance management

---

## Immediate Action Items (Priority Order)

### 🔴 High Priority (User-Blocking)

1. **Add Trading Mode Switch**
   - Endpoint exists: `POST /api/trading-mode`
   - v1 has this prominently displayed
   - **Impact:** Users can't change trading mode

2. **Fix Guardian Dashboard**
   - Backend has issues (returns 500)
   - v3 needs to handle this gracefully
   - Show degraded state, not errors
   - **Impact:** Console spam, bad UX

3. **Add Symbol Selector**
   - Endpoint: `/api/symbols`
   - v1 allows switching symbols
   - **Impact:** Users stuck on one symbol

### 🟡 Medium Priority (Missing Features)

4. **Add Health Dashboard**
   - Implement `/api/health/detailed`
   - Show system health metrics
   - **Impact:** No visibility into system health

5. **Add Volatility Panel**
   - Implement `/api/volatility/signal`
   - Show market conditions
   - **Impact:** Missing critical trading context

6. **Add Incident Management**
   - Implement error tracking
   - Add resolution tools
   - **Impact:** No way to handle errors

### 🟢 Low Priority (Nice to Have)

7. **Add Help System**
   - Port from v1
   - Add tooltips and guides

8. **Add Configuration Panel**
   - Runtime config changes
   - Log checking

9. **Add Command Knowledge Base**
   - Quick command reference
   - Terminal integration

---

## Backend Issues Discovered

### 1. Guardian API Returns 500
```bash
$ curl http://localhost:5555/api/guardian/status
{"error":"an integer is required (got type str)","health":null,"running":false}
```

**Backend Fix Needed:** Guardian status endpoint has a bug

### 2. Missing Endpoints
- `/api/volatility/signal` - Not found
- `/api/liquidation/status` - Not found
- `/api/symbols` - Not found
- `/api/errors/*` - Not found

**Note:** These may be v1-specific endpoints that need to be re-implemented

---

## Recommended Next Steps

### Option A: Quick Fixes (2-4 hours)
1. Fix guardian error handling ✅ **DONE**
2. Add trading mode switch
3. Add symbol selector
4. Improve error messages

**Result:** v3 usable for basic trading

### Option B: Feature Parity (1-2 days)
1. All Option A items
2. Add health dashboard
3. Add volatility panel
4. Add incident management

**Result:** v3 matches v1 core features

### Option C: Full Port (3-5 days)
1. All Option B items
2. Add configuration panel
3. Add help system
4. Add all missing endpoints
5. Port all v1 features

**Result:** v3 exceeds v1 with modern architecture

---

## Technical Debt in v3

1. **Missing Backend Endpoints:**
   - Need to verify which v1 endpoints still exist
   - Some may need backend implementation

2. **Type Definitions:**
   - Position.id is optional (should be required if available)
   - Some types don't match actual API responses

3. **Error Handling:**
   - Guardian errors handled, but should be more graceful
   - Need global error boundary

4. **Testing:**
   - Only 35 unit tests
   - No integration tests
   - No E2E tests

---

## Conclusion

**Current State (Jan 2, 2026):**
- ✅ v3 has modern, clean architecture
- ✅ Basic trading features working
- ❌ Missing many advanced features from v1
- ❌ Some backend endpoints broken/missing

**Recommendation:**
Follow **Option B: Feature Parity** approach:
1. Fix immediate blockers (trading mode, symbols)
2. Add critical missing features (health, volatility)
3. Gradually port remaining v1 features
4. Keep modern architecture advantages

**Estimated Time:** 1-2 days for feature parity with v1's core functionality.

---

**Last Updated:** January 2, 2026  
**Next Review:** After implementing Option A quick fixes
