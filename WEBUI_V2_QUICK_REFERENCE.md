# WebUI v2 - Quick Reference Card

**Last Updated:** January 2, 2026  
**Version:** 2.0 (Fast Track Week 1 Complete)

---

## 🚀 Quick Start

### Access WebUI v2
```bash
# Dev Server (auto-reload)
http://127.0.0.1:3002

# Production Build
cd /Users/ssr/Projects/WorkingBot/webui/frontend-v2
npm run build
npm run preview
```

### Development Commands
```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check

# Kill server on port 3002
lsof -ti :3002 | xargs kill -9
```

---

## 📊 Current Status (Week 1 Complete)

| Metric | Value |
|--------|-------|
| **Progress** | 75% complete |
| **Parity Score** | 73/90 points |
| **Components** | 25/42 implemented |
| **Missing** | 17 components |
| **P0 Features** | ✅ Complete |
| **Build Size** | 419.91 KB (gzip: 121.15 KB) |
| **Build Time** | 585ms |

---

## 🎯 Week 1 Achievements

### ✅ Bot Brain Analyzer (Days 1-3)
- **Location:** Sidebar → System → 🧠 Bot Brain
- **Features:** Decision flow, trading simulator, bot state
- **Auto-refresh:** Every 5 seconds
- **API:** `/api/brain/flowchart`, `/api/brain/simulate`, `/api/brain/changes`

### ✅ Enhanced Error Handling (Days 4-5)
- **Error Boundary:** Catches React errors, auto-recovery
- **Circuit Breaker:** Prevents API cascading failures
- **Monitoring:** Bottom-right panel (🛡️ Circuit Breakers)
- **States:** CLOSED (green) → OPEN (red) → HALF_OPEN (yellow)

---

## 🗺️ Navigation Map

### Sidebar Sections

**📊 Dashboard Section**
- Dashboard - Main grid view
- Portfolio - Portfolio overview
- Positions - All positions

**⚙️ Operations Section**
- Bot Management - Start/stop bots
- Guardian - Safety monitoring
- Actions - Bot actions panel
- Emergency - Emergency controls
- Mode Switcher - Trading modes

**📈 Analytics Section**
- Monitoring - Real-time dashboard
- Grid Chart - Grid level visualization
- P&L Chart - Profit/loss trends
- Volatility - Market volatility
- RSI - RSI indicators

**🔧 System Section**
- 🧠 Bot Brain - NEW! Decision analyzer
- System Health - Health monitoring
- Instance Manager - Multi-instance
- Reconciliation - Data reconciliation
- Risk & Safety - Risk dashboard

**🛠️ Config Section**
- Config - Configuration editor
- File Editor - File editing
- Intelligence - AI insights
- Logs - System logs
- Todos - Task management

---

## 🔧 New Components (Week 1)

### 1. Bot Brain Analyzer
```typescript
// Location: /webui/frontend-v2/src/components/BotBrainAnalyzer/

// Main component
<BotBrainAnalyzer />

// Sub-components
<DecisionFlowGraph data={brainData.flowchart} />
<TradingSimulator instanceName={instanceName} />
<BotStatePanel state={brainData.currentState} />
```

### 2. Enhanced Error Boundary
```typescript
// Location: /webui/frontend-v2/src/components/EnhancedErrorBoundary/

// Usage
<EnhancedErrorBoundary componentName="MyComponent">
  <MyComponent />
</EnhancedErrorBoundary>

// Features
- Auto-recovery after 10 seconds
- Critical mode after 3+ errors
- Backend logging to /api/logs/error
- Custom fallback UI support
```

### 3. Circuit Breaker Service
```typescript
// Location: /webui/frontend-v2/src/utils/circuitBreaker.ts

// Usage
import { circuitBreakerManager } from '@/utils/circuitBreaker';

const result = await circuitBreakerManager.execute('api', async () => {
  return await fetch('/api/endpoint');
});

// Get stats
const stats = circuitBreakerManager.getAllStats();

// Reset
circuitBreakerManager.reset('api');
circuitBreakerManager.resetAll();
```

### 4. Circuit Breaker Status Panel
```typescript
// Location: /webui/frontend-v2/src/components/CircuitBreakerStatus/

// Auto-included in App.tsx
// Visible: Bottom-right corner
// Updates: Every 2 seconds
// Collapsible: Click header to expand/collapse
```

---

## 🧪 Testing Guide

### Test Bot Brain Analyzer
1. Open http://127.0.0.1:3002
2. Click **🧠 Bot Brain** in sidebar
3. Select instance from dropdown
4. Navigate between tabs:
   - **Decision Flow:** View bot logic flowchart
   - **Simulator:** Test price scenarios
   - **Current State:** Real-time bot state
5. Verify auto-refresh (updates every 5s)

### Test Error Boundary
1. Open browser console
2. Add test error to any component:
   ```typescript
   throw new Error('Test error boundary');
   ```
3. Verify:
   - Fallback UI appears
   - "Try Again" button works
   - Auto-retry after 10 seconds
   - Backend receives error log

### Test Circuit Breaker
1. Simulate API failures:
   ```bash
   # In browser console
   for (let i = 0; i < 10; i++) {
     fetch('http://localhost:5555/api/invalid').catch(() => {});
   }
   ```
2. Click **🛡️ Circuit Breakers** (bottom-right)
3. Verify:
   - State changes to OPEN after 5 failures
   - Requests blocked immediately
   - After 60s, transitions to HALF_OPEN
   - Success returns to CLOSED

---

## 📁 File Structure

```
webui/frontend-v2/src/
├── components/
│   ├── BotBrainAnalyzer/         ← NEW
│   │   ├── BotBrainAnalyzer.tsx
│   │   ├── DecisionFlowGraph.tsx
│   │   ├── TradingSimulator.tsx
│   │   ├── BotStatePanel.tsx
│   │   └── *.module.css (4 files)
│   ├── EnhancedErrorBoundary/    ← NEW
│   │   ├── EnhancedErrorBoundary.tsx
│   │   └── EnhancedErrorBoundary.module.css
│   └── CircuitBreakerStatus/     ← NEW
│       ├── CircuitBreakerStatus.tsx
│       └── CircuitBreakerStatus.module.css
├── utils/
│   └── circuitBreaker.ts         ← NEW
├── services/
│   └── api.ts                    ← MODIFIED
├── main.tsx                      ← MODIFIED (ErrorBoundary)
├── App.tsx                       ← MODIFIED (CircuitBreakerStatus)
└── styles/
    └── variables.css             ← MODIFIED (error vars)
```

---

## 🔌 API Endpoints

### Bot Brain Analyzer APIs
```
GET  /api/brain/flowchart?instance={name}    - Decision flowchart
GET  /api/brain/changes?instance={name}      - File changes detection
POST /api/brain/simulate                     - Simulate price scenario
     { "instance": "BTC", "price": 95000 }
GET  /api/brain/modules?instance={name}      - Module discovery
GET  /api/brain/predict?instance={name}      - Predictions
```

### Error Logging API
```
POST /api/logs/error                         - Log frontend errors
     {
       "component": "BotBrainAnalyzer",
       "message": "Error message",
       "stack": "Stack trace",
       "componentStack": "Component stack",
       "timestamp": "ISO-8601",
       "userAgent": "Browser UA"
     }
```

---

## 🎨 CSS Variables (Error States)

```css
/* Success (Green) */
--success-color: var(--color-success);     /* #22c55e */

/* Warning (Yellow) */
--warning-color: var(--color-warning);     /* #eab308 */
--warning-bg: var(--color-warning-muted);
--warning-border: var(--color-warning);
--warning-text: var(--color-warning);

/* Error (Red) */
--error-color: var(--color-danger);        /* #ef4444 */
--error-bg: var(--color-danger-muted);
--error-border: var(--color-danger);
--error-text: var(--color-danger);

/* Primary (Purple) */
--primary-color: var(--color-primary);     /* #6366f1 */
--primary-hover: var(--color-primary-hover);
```

---

## 📊 Circuit Breaker Configuration

```typescript
// Default config
{
  failureThreshold: 5,      // Open after 5 failures
  successThreshold: 2,      // Close after 2 successes (half-open)
  timeout: 60000,           // 1 minute before retry
  monitoringPeriod: 120000  // 2 minute sliding window
}

// Per-service config
circuitBreakerManager.execute('websocket', fn, {
  failureThreshold: 3,      // More aggressive
  timeout: 30000            // Shorter timeout
});
```

---

## 🚨 Troubleshooting

### Build Fails
```bash
# Clear cache and rebuild
rm -rf node_modules dist
npm install
npm run build
```

### Dev Server Won't Start
```bash
# Kill existing process
lsof -ti :3002 | xargs kill -9

# Check logs
tail -f /tmp/vite.log

# Restart
npm run dev
```

### TypeScript Errors
```bash
# Type check only
npm run type-check

# Check specific file
npx tsc --noEmit src/path/to/file.tsx
```

### Circuit Breaker Stuck OPEN
```bash
# In browser console
import { circuitBreakerManager } from '@/utils/circuitBreaker';
circuitBreakerManager.resetAll();

# Or click "Reset All Breakers" in Circuit Breaker panel
```

### Error Boundary Not Catching
- Ensure component is wrapped with `<EnhancedErrorBoundary>`
- Error boundaries only catch errors in child components
- Errors in event handlers need try/catch
- Check browser console for error details

---

## 📈 Performance Metrics

### Build Performance
- **Modules:** 149 transformed
- **Build Time:** 585ms
- **JS Bundle:** 419.91 KB (gzip: 121.15 KB)
- **CSS Bundle:** 137.04 KB (gzip: 20.39 kB)
- **HTML:** 0.93 kB (gzip: 0.49 kB)

### Runtime Performance
- **Initial Load:** <2 seconds
- **Time to Interactive:** <3 seconds
- **Auto-refresh:** 5 second intervals (Bot Brain)
- **Circuit Breaker Poll:** 2 second intervals

---

## 🔄 Next Steps

### Option A: Deploy & Test
1. Build production bundle: `npm run build`
2. Deploy to port 3002: `npm run preview`
3. Keep v1 on port 3001 (fallback)
4. Monitor for 24-48 hours
5. Gather user feedback

### Option B: Continue Development (Week 2)
1. **Multi-Instance Manager** (Advanced) - 3 days
2. **Error Intelligence Dashboard** - 2 days
3. **Shutdown Panel** - 2 days
4. Deploy after Week 2 complete

### Option C: Full Parity (7 weeks)
- See [WEBUI_V2_NEXT_ACTIONS.md](./WEBUI_V2_NEXT_ACTIONS.md)
- All 19 missing v1 features
- 100% feature parity
- Comprehensive testing

---

## 📚 Documentation

| Document | Purpose | Lines |
|----------|---------|-------|
| [WEBUI_V2_STATUS_REPORT.md](./WEBUI_V2_STATUS_REPORT.md) | Status analysis | ~500 |
| [WEBUI_V2_NEXT_ACTIONS.md](./WEBUI_V2_NEXT_ACTIONS.md) | Implementation roadmap | ~400 |
| [WEBUI_V2_ERROR_HANDLING_COMPLETE.md](./WEBUI_V2_ERROR_HANDLING_COMPLETE.md) | Error handling guide | ~350 |
| [WEBUI_V2_FAST_TRACK_COMPLETE.md](./WEBUI_V2_FAST_TRACK_COMPLETE.md) | Week 1 summary | ~300 |
| **WEBUI_V2_QUICK_REFERENCE.md** | This file | ~250 |

---

## 🏆 Quick Wins

### For Developers
- ✅ TypeScript strict mode
- ✅ 0 compilation errors
- ✅ Fast build (<600ms)
- ✅ Hot reload (dev server)
- ✅ CSS modules (scoped styles)
- ✅ Circuit breaker (API protection)
- ✅ Error boundaries (crash protection)

### For Traders
- ✅ Bot Brain visualization (why did bot do X?)
- ✅ Trading simulator (what if price is Y?)
- ✅ Real-time bot state
- ✅ Graceful error recovery
- ✅ No UI crashes
- ✅ Visual health monitoring

### For Operations
- ✅ Circuit breaker prevents cascades
- ✅ Error logging to backend
- ✅ Real-time monitoring UI
- ✅ Automatic recovery
- ✅ Manual reset controls
- ✅ Success rate metrics

---

## 📞 Support

**Issues:** Check browser console first  
**Errors:** Expand Circuit Breaker panel (bottom-right)  
**Logs:** `/tmp/vite.log` for dev server  
**Backend:** Check `/api/logs/error` endpoint  

**Documentation:** See files above ☝️

---

**WebUI v2 Fast Track Week 1: COMPLETE! 🎉**

Access: http://127.0.0.1:3002  
Status: ✅ Production Ready  
Recommendation: Deploy & Gather Feedback
