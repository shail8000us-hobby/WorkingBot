# WebUI Performance Optimization Plan V2 — Granular & Safe

**Project:** WorkingBot WebUI
**Architecture:** Flask Backend (port 5555) + React 18 Frontend (CRA + react-app-rewired)
**State Management:** Zustand + 6 Context providers
**Data Fetching:** DataAggregator (single poller) + apiClient (dedup + TTL cache)
**Created:** March 2, 2026
**Principle:** _Every step must leave the WebUI fully functional. Zero downtime development._

---

## Current State Snapshot

| Metric | Current | Target |
|--------|---------|--------|
| Main bundle (gzipped) | 192 KB | <150 KB |
| Total initial load (gzipped) | ~575 KB | <400 KB |
| App.js lines | 1,754 | <400 |
| App.js hooks/useEffect | 15+ useEffect, 20+ useMemo | <5 useEffect |
| Lazy-loaded components | 45+ ✅ | 45+ ✅ |
| Context providers nesting | 6 deep (InstanceProvider → SymbolProvider → AutoloopProvider → MobileOptimizationProvider + SystemStatusContext + MMMProvider) | 2-3 max |
| Backend route files | 62 | 62 (no change needed) |
| Backend caching | SimpleCache (4 endpoints) | SimpleCache (15+ endpoints) |
| Polling | DataAggregator 10-120s adaptive ✅ | ✅ Already optimized |
| Request dedup | apiClient.pendingRequests ✅ | ✅ Already optimized |

### What's Already Done (Phases 1, 3, 4 from V1 Plan)
- ✅ Lazy loading (45+ components)
- ✅ Code splitting (60+ chunks via config-overrides.js)
- ✅ Flask-Caching on 4 endpoints
- ✅ Gzip compression (Flask-Compress)
- ✅ DataAggregator (single poller replacing 91 individual pollers)
- ✅ Request deduplication + client-side TTL cache
- ✅ Adjacent section preloading
- ✅ Adaptive polling (visible/hidden tab)

### What's Left (High Impact)
- ❌ App.js is 1,754 lines — monolith with all section renders
- ❌ 20+ `useMemo` render functions inside App.js (re-evaluated on state changes)
- ❌ 8 nested context providers (ErrorBoundary → ThemeMode → SystemStatus → Notification → Keyboard → Instance → Symbol → Autoloop → Mobile)
- ❌ `AppWrapper.js` is dead code (not imported anywhere — entry is `index.js`)
- ❌ Only 4/62 backend routes have caching
- ❌ No virtual scrolling for large lists
- ❌ `framer-motion` still in bundle (~82KB gzipped) — 16 files actively import it despite comment saying "replaced with CSS"
- ❌ Both `recharts` (16 files) AND `chart.js` (1 file: BreakevenChart.js) in bundle
- ❌ No Brotli compression
- ❌ No resource hints in index.html

---

## Safety Rules (Apply to ALL Phases)

1. **Git branch per sub-step:** `git checkout -b perf/phase-X-step-Y`
2. **Test after every file change:** Open WebUI, verify navigation works, check console for errors
3. **No simultaneous backend + frontend changes** — do one at a time
4. **Rollback-ready:** Every step can be reverted with `git checkout main`
5. **Feature flag new behavior** when possible (already have `useFeatureFlag` infrastructure)
6. **Never modify component APIs** — only move/wrap, don't change props
7. **Build verification:** `npm run build` must pass with 0 errors after each step

---

## Phase 2: App.js Decomposition (Monolith → Modular)

> **Why this phase first:** App.js at 1,754 lines is the #1 maintainability and performance bottleneck. Every state change potentially re-evaluates 20+ `useMemo` render functions. Breaking it up reduces re-render scope and makes future optimization easier.

**Timeline:** 3-4 days
**Impact:** 🔥🔥🔥 — Reduces re-render blast radius by 80%, makes codebase maintainable
**Risk:** ⚠️ Medium — Pure refactoring, no logic changes

### Pre-Condition Checklist
- [ ] All current tests pass: `npm test -- --watchAll=false`
- [ ] Production build succeeds: `npm run build`
- [ ] Screenshot current UI state for visual regression comparison
- [ ] Create branch: `git checkout -b perf/phase2-app-decomposition`

---

### Step 2.1: Extract Section Render Functions → Page Components
**Time:** 4-6 hours
**Risk:** 🟢 Low — Moving JSX to new files, zero logic change

**What:** Each `renderXxx` useMemo block in App.js becomes a standalone page component file.

**Current Pattern (App.js lines 767-1596):**
```javascript
// 20+ blocks like this inside App():
const renderTodos = useMemo(() => (
  <Suspense fallback={...}>
    <CollapsibleCard ...>
      <EnhancedErrorBoundary ...>
        <TodoListPanel />
      </EnhancedErrorBoundary>
    </CollapsibleCard>
  </Suspense>
), []);
```

**Target Structure:**
```
src/pages/
├── DashboardPage.js       ← renderDashboard (lines 833-978)
├── PositionsPage.js        ← renderPositions (lines 980-1005)
├── OptionsPage.js          ← renderOptions (lines 1008-1026)
├── OptionsChainPage.js     ← renderOptionsChain (lines 1029-1047)
├── StrategyBuilderPage.js  ← renderStrategyBuilder (lines 1050-1070)
├── MVStraddlePage.js       ← renderMVStraddle (lines 1545-1549)
├── MMMPage.js              ← renderMMM (lines 1551-1559)
├── SSRAlgoPage.js          ← renderSSRAlgo (lines 1561-1567)
├── ZeroDTEPage.js          ← renderZeroDTE (lines 803-811)
├── RiskPage.js             ← renderRisk (lines 1092-1188)
├── ConfigPage.js           ← renderConfig (lines 1190-1243)
├── RSIPage.js              ← renderRSI (lines 1072-1090)
├── TradingViewPage.js      ← renderTradingView (lines 1569-1573)
├── MLTradingPage.js        ← renderMLTrading (lines 1386-1479)
├── BotManagementPage.js    ← renderBotManagement (lines 1481-1536)
├── EmergencyPage.js        ← renderEmergency (lines 1245-1277)
├── MonitoringPage.js       ← renderMonitoring (lines 1279-1322)
├── IntelligencePage.js     ← renderIntelligence (lines 1324-1384)
├── TodosPage.js            ← renderTodos (lines 767-783)
├── SystemHealthPage.js     ← renderSystemHealth (lines 785-801)
├── ExperimentalPage.js     ← renderExperimental (lines 813-821)
├── AdvancedFeaturesPage.js ← renderAdvancedFeatures (lines 823-831)
├── GuardianPage.js         ← renderGuardian (lines 1575-1595)
└── PortfolioPage.js        ← renderPortfolio (lines 1539-1543)
```

**Execution Order (do one at a time, test between each):**

**Batch A — Zero-dependency pages (no props from App.js):**
1. `TodosPage.js` — renderTodos has `[]` deps
2. `PortfolioPage.js` — renderPortfolio has `[]` deps
3. `OptionsPage.js` — renderOptions has `[]` deps
4. `SSRAlgoPage.js` — renderSSRAlgo has `[]` deps
5. `TradingViewPage.js` — renderTradingView has `[]` deps
6. `ZeroDTEPage.js` — renderZeroDTE has `[]` deps

**Batch B — Simple dependency pages (only `isMobile` or `botIsRunning`):**
7. `SystemHealthPage.js` — deps: `[]` (no actual deps)
8. `ExperimentalPage.js` — deps: `[]`
9. `AdvancedFeaturesPage.js` — deps: `[]`
10. `RSIPage.js` — deps: `[isMobile]`
11. `PositionsPage.js` — deps: `[botIsRunning, isMobile]`
12. `IntelligencePage.js` — deps: `[isMobile, botIsRunning]`
13. `RiskPage.js` — deps: `[isMobile]` (botIsRunning used inline)

**Batch C — Complex dependency pages (socket, config, etc.):**
14. `OptionsChainPage.js` — deps: `[navParams]`
15. `StrategyBuilderPage.js` — deps: uses `setActiveSection` + `setNavParams`
16. `MVStraddlePage.js` — deps: `[]`
17. `MMMPage.js` — deps: `[socket]`
18. `MLTradingPage.js` — deps: `[isMobile]`
19. `BotManagementPage.js` — deps: `[isMobile, botIsRunning, logs]`
20. `EmergencyPage.js` — deps: `[isMobile, socket]`
21. `MonitoringPage.js` — deps: `[isMobile, botIsRunning, botStatus, config]`
22. `ConfigPage.js` — deps: `[config, configMeta, busy, loading, isMobile, featureFlags, ...]`
23. `DashboardPage.js` — deps: `[socket, latencyStats, connectionQuality, botIsRunning, isMobile, botStatus, config]` (most complex)
24. `GuardianPage.js` — deps: `[guardianEnabled]`

**Template for each page component:**
```javascript
// src/pages/TodosPage.js
import React, { Suspense } from 'react';
import PanelSkeleton from '../components/common/PanelSkeleton';
import CollapsibleCard from '../components/common/CollapsibleCard.tsx';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';

const TodoListPanel = React.lazy(() => import('../components/TodoListPanel'));

const TodosPage = React.memo(function TodosPage() {
  return (
    <Suspense fallback={<PanelSkeleton type="list" />}>
      <div className="grid gap-6">
        <CollapsibleCard id="todo-list" title="📝 Improvement Todo List" ...>
          <EnhancedErrorBoundary componentName="TodoListPanel">
            <TodoListPanel />
          </EnhancedErrorBoundary>
        </CollapsibleCard>
      </div>
    </Suspense>
  );
});

export default TodosPage;
```

**For pages needing App.js data (Batch B/C), props are passed from App.js:**
```javascript
// src/pages/DashboardPage.js
const DashboardPage = React.memo(function DashboardPage({
  socket, latencyStats, connectionQuality, botIsRunning, isMobile, botStatus, config
}) {
  // ... existing renderDashboard JSX
});
```

**Validation after each batch:**
- [ ] `npm run build` — zero errors
- [ ] Open WebUI → navigate to the extracted section → verify content renders
- [ ] Check React DevTools → confirm component tree shows new page component
- [ ] Check console → no new warnings/errors

---

### Step 2.2: Simplify App.js getSectionContent
**Time:** 1 hour
**Risk:** 🟢 Low — Replacing inline JSX with component references

**After Step 2.1, App.js `getSectionContent` becomes:**
```javascript
import TodosPage from './pages/TodosPage';
import PortfolioPage from './pages/PortfolioPage';
// ... etc

const getSectionContent = useCallback((sectionId) => {
  const contentMap = {
    todos: <TodosPage />,
    portfolio: <PortfolioPage />,
    positions: <PositionsPage botIsRunning={botIsRunning} isMobile={isMobile} />,
    dashboard: <DashboardPage socket={socket} ... />,
    // ... etc
  };
  return contentMap[sectionId] || <DashboardPage ... />;
}, [botIsRunning, isMobile, socket, /* minimal deps */]);
```

**Expected App.js reduction:** 1,754 → ~500 lines

**Validation:**
- [ ] Every sidebar tab still works
- [ ] Panel switching is still instant (no flicker)
- [ ] No new console errors

---

### Step 2.3: Extract Navigation & Section Config
**Time:** 1 hour
**Risk:** 🟢 Low

**Move the `sections` array (lines 520-692) to:**
```
src/config/navigationSections.js
```

**Move preloading logic (lines 163-205) to:**
```
src/utils/sectionPreloader.js
```

**Move `MobileNav` component (lines 214-255) to:**
```
src/components/layout/MobileNav.js
```

**Move `LoadingFallback` component (lines 207-212) to:**
```
src/components/common/LoadingFallback.js
```

**Expected App.js reduction:** ~500 → ~350 lines

---

### Step 2.4: Extract Custom Hooks from App.js
**Time:** 2 hours
**Risk:** 🟡 Low-Medium — Moving hook logic

**Extract these inline hooks to dedicated files:**

| Hook Logic | New File | Lines in App.js |
|------------|----------|-----------------|
| `pushLatencySample` + `latencyBufferRef` | `hooks/useLatencyTracker.js` | 390-412 |
| `ensureFresh` + `handleHardRefresh` + `handleClearCache` | `hooks/useConnectionActions.js` | 414-445 |
| Mobile detection (`isMobile` + resize listener) | `hooks/useIsMobile.js` | 283-380 |
| Keyboard event listeners | `hooks/useKeyboardEvents.js` | 495-509 |
| Visibility/online listeners | `hooks/useVisibilityRefresh.js` | 471-485 |
| `handleDeepLink` + `handleSectionSelect` | `hooks/useNavigation.js` | 731-765 |

**Expected App.js reduction:** ~350 → ~250 lines (final target)

**Validation:**
- [ ] Every keyboard shortcut still works
- [ ] Tab visibility change still triggers refresh
- [ ] Online/offline detection still works
- [ ] Latency display still updates in TopBar

---

### Phase 2 Completion Checklist
- [ ] App.js is <300 lines
- [ ] All 23+ sections render correctly
- [ ] No new console errors
- [ ] `npm run build` succeeds
- [ ] Bundle size unchanged (pure refactoring)
- [ ] Panel switching speed unchanged or improved
- [ ] Commit: `git commit -m "Phase 2: Decompose App.js monolith into page components"`
- [ ] Merge to main: `git checkout main && git merge perf/phase2-app-decomposition`

---

## Phase 5: Dependency Cleanup & Bundle Reduction

> **Why before Phase 2 original (React optimization):** Removing dead dependencies is zero-risk and reduces bundle immediately.

**Timeline:** 0.5-1 day
**Impact:** 🔥🔥 — 50-100KB bundle reduction
**Risk:** 🟢 Low

### Pre-Condition Checklist
- [ ] Branch: `git checkout -b perf/phase5-dependency-cleanup`

---

### Step 5.1: Remove chart.js (Keep Recharts)
**Time:** 30 minutes
**Risk:** 🟢 Low

**Analysis (verified):** Recharts is used in **16 files**. Chart.js + react-chartjs-2 is used in **only 1 file:**
- `src/components/optionsStrategy/strategies/BreakevenChart.js` — Simple `<Line>` chart

**Action:**
1. Rewrite `BreakevenChart.js` to use Recharts `<LineChart>` (same data shape, simple conversion)
2. Remove from package.json:
   ```json
   "chart.js": "^4.5.1",
   "react-chartjs-2": "^5.3.1",
   ```
3. `npm install` to update lockfile

**Estimated saving:** ~60KB gzipped (chart.js alone is 200KB uncompressed)

**Validation:**
- [ ] The one component using Chart.js still renders
- [ ] `npm run build` — no import errors
- [ ] Bundle analysis shows charts chunk reduced

---

### Step 5.2: Reduce framer-motion Usage (16 Files Still Import It)
**Time:** 3-4 hours (split across multiple sessions)
**Risk:** 🟡 Medium — 16 files actively use `motion.div` / `AnimatePresence`

**App.js line 32:** `// framer-motion AnimatePresence removed: replaced with CSS for instant panel switches`

**BUT framer-motion is still actively imported in 16 files (verified):**

| File | Usage | Can Replace? |
|------|-------|-------------|
| `components/common/CollapsibleCard.tsx` | `motion.div` + `AnimatePresence` for expand/collapse | 🔴 Keep (core UI) |
| `components/common/CollapsibleCard.js` | Same (duplicate?) | Check if dead code |
| `components/common/AnimatedNumber.tsx` | `motion.span` for number animation | 🟡 CSS `@property` possible |
| `components/layout/TopBar.js` | `motion.div` | 🟢 Replace with CSS |
| `components/layout/Sidebar.js` | `motion.div` | 🟢 Replace with CSS |
| `components/layout/FloatingActionBar.js` | `motion.div` | 🟢 Replace with CSS |
| `components/PositionsPanel.js` | `motion.div` | 🟢 Replace with CSS |
| `components/MarketSignalPanel.js` | `motion.div` | 🟢 Replace with CSS |
| `components/SymbolPortfolio.js` | `motion.div` | 🟢 Replace with CSS |
| `components/ExperimentalPanel.js` | `motion.div` | 🟢 Replace with CSS |
| `components/AdvancedFeaturesPanel.js` | `motion.div` | 🟢 Replace with CSS |
| `components/OfflineIndicator.js` | `motion.div` + `AnimatePresence` | 🟡 CSS with transition |
| `components/SymbolSelector.js` | `motion.div` + `AnimatePresence` | 🟡 CSS with transition |
| `components/TradeNotification.js` | `motion.div` + `AnimatePresence` | 🟡 CSS with transition |
| `components/RiskSafetyDashboard.js` | `motion.div` + `AnimatePresence` | 🟡 CSS with transition |
| `components/WalletBalanceIndicator.jsx` | `motion.div` | 🟢 Replace with CSS |
| `components/UnrealizedPnLIndicator.jsx` | `motion.div` | 🟢 Replace with CSS |
| `components/ui/Button.js` | `motion.button` | 🟡 CSS hover effect |
| `components/ui/Card.js` | `motion.div` | 🟡 CSS hover effect |

**Strategy: Gradual removal (do NOT remove all at once):**

**Sub-step 5.2a — Easy replacements (no AnimatePresence):**
Replace `motion.div` with plain `<div className="transition-all duration-300">` in:
- TopBar.js, Sidebar.js, FloatingActionBar.js
- PositionsPanel.js, MarketSignalPanel.js, SymbolPortfolio.js
- ExperimentalPanel.js, AdvancedFeaturesPanel.js
- WalletBalanceIndicator.jsx, UnrealizedPnLIndicator.jsx
- Button.js, Card.js

**Sub-step 5.2b — AnimatePresence replacements (harder):**
Replace `AnimatePresence` enter/exit animations with CSS:
```css
.animate-enter { animation: fadeIn 200ms ease-out; }
.animate-exit { animation: fadeOut 200ms ease-in; }
```
Apply to: OfflineIndicator, SymbolSelector, TradeNotification, RiskSafetyDashboard

**Sub-step 5.2c — Keep framer-motion ONLY for CollapsibleCard:**
CollapsibleCard uses `AnimatePresence` for smooth expand/collapse height animation.
This is the hardest to replace with CSS (auto-height transition).
Decision: Keep for now, or use `@starting-style` (CSS 2024) if browser support is OK.

**After 5.2a+5.2b:** framer-motion will be tree-shaken down to only what CollapsibleCard uses.
**Estimated saving:** ~40-60KB gzipped (partial tree shaking)

**To fully remove (future):** Replace CollapsibleCard animation with:
```css
.card-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 300ms ease;
}
.card-body.open { grid-template-rows: 1fr; }
.card-body > div { overflow: hidden; }
```

**Do NOT remove from package.json until ALL imports are gone.**

---

### Step 5.3: Audit Unused Imports
**Time:** 30 minutes
**Risk:** 🟢 Low

```bash
# Find unused dependencies
npx depcheck
```

**Verified dependency usage (March 2, 2026):**
| Package | Used In | Status |
|---------|---------|--------|
| `@dnd-kit/*` | `OptionsPanel.js` (drag-and-drop position reorder) | ✅ Keep |
| `uuid` | `commandSender.js` (confirmation IDs) | ✅ Keep — could replace with `crypto.randomUUID()` |
| `@monaco-editor/react` | `CodeEditor.jsx` (YAML editor) | ✅ Keep (lazy loaded) |
| `monaco-editor` | peer dep of `@monaco-editor/react` | ✅ Keep |
| `remark-gfm` | Used with `react-markdown` | ✅ Keep |
| `prop-types` | Legacy prop validation | 🟡 Can remove if migrating to TypeScript |

**Quick win:** Replace `uuid` with native `crypto.randomUUID()` to save ~3KB:
```javascript
// Before
import { v4 as uuidv4 } from 'uuid';
const id = uuidv4();

// After (no import needed, built into browsers)
const id = crypto.randomUUID();
```

**Validation:**
- [ ] `npm run build` passes
- [ ] No runtime errors

---

### Step 5.4: Optimize MUI Icon Imports
**Time:** 15 minutes
**Risk:** 🟢 Low

Verify all MUI imports use specific paths:
```bash
# BAD: imports entire library
grep -rn "from '@mui/material'" webui/frontend/src/ | head -20

# GOOD: imports specific component
# from '@mui/material/Button'
```

Most lucide-react icons are already imported specifically (App.js lines 3-31 ✅).

**Validation:**
- [ ] No change to functionality
- [ ] Icons chunk may shrink

---

### Phase 5 Completion Checklist
- [ ] chart.js removed (or justified keeping)
- [ ] framer-motion removed (or justified keeping)
- [ ] Unused packages removed
- [ ] `npm run build` passes
- [ ] Bundle size reduced by 50-150KB gzipped
- [ ] All UI animations still work
- [ ] Commit & merge to main

---

## Phase 6: Context Provider Optimization

> **Why:** 7+ nested context providers cause re-render cascading. SymbolProvider appears in App.js but is NOT in index.js. Also, `AppWrapper.js` is **dead code** (not imported anywhere — entry point is `index.js`).

**Timeline:** 1-2 days
**Impact:** 🔥🔥 — 30-50% fewer re-renders
**Risk:** 🟡 Medium

### Pre-Condition Checklist
- [ ] Phase 2 complete (App.js decomposed)
- [ ] Branch: `git checkout -b perf/phase6-context-optimization`

---

### Step 6.0: Delete Dead Code — AppWrapper.js
**Time:** 5 minutes
**Risk:** 🟢 None — It's not imported anywhere

**Finding:** `AppWrapper.js` is dead code:
- Imports `App` from `./AppContent` (which doesn't exist)
- No file in the codebase imports `AppWrapper`
- The actual entry point is `index.js` → renders `<App />`

**Action:** Delete `webui/frontend/src/AppWrapper.js`

**Validation:**
- [ ] `npm run build` still passes
- [ ] App still works (it was never used)

---

### Step 6.1: Document Actual Provider Hierarchy
**Time:** 10 minutes
**Risk:** 🟢 None — Documentation only

**Actual hierarchy (from `index.js` + `App.js`):**
```
React.StrictMode
  └─ ErrorBoundary (index.js)
    └─ ThemeModeProvider (index.js)
      └─ SystemStatusProvider (index.js)
        └─ NotificationProvider (index.js)
          └─ KeyboardProvider (index.js)
            └─ App (App.js)
              └─ InstanceProvider (App.js line 1643)
                └─ SymbolProvider (App.js line 1644)
                  └─ AutoloopProvider (App.js line 1645)
                    └─ MobileOptimizationProvider (App.js line 1646)
                      └─ actual content (8 levels deep!)
```

**That's 8 providers deep!** Every state change in any provider potentially re-renders everything below it.

---

### Step 6.2: Consolidate Provider Hierarchy (8 → 5 levels)
**Time:** 2-3 hours
**Risk:** 🟡 Medium

**Target nesting (5 deep):**
```
React.StrictMode
  └─ ErrorBoundary (index.js)
    └─ ThemeModeProvider (index.js)
      └─ AppProviders (NEW — combines 4 providers)
        └─ App (App.js)
          └─ actual content (only wrap specific pages with Autoloop/Mobile if needed)
```

**Action:**
1. Create `src/context/AppProviders.js`:
   ```javascript
   const AppProviders = ({ children }) => (
     <SystemStatusProvider>
       <NotificationProvider>
         <KeyboardProvider callbacks={...}>
           <InstanceProvider>
             <SymbolProvider>
               {children}
             </SymbolProvider>
           </InstanceProvider>
         </KeyboardProvider>
       </NotificationProvider>
     </SystemStatusProvider>
   );
   ```
2. Simplify `index.js` to use `<AppProviders>`
3. Remove `InstanceProvider`, `SymbolProvider` from App.js return block
4. Move `AutoloopProvider` to only wrap pages that use autoloop (PositionsPage, OptionsPage)
5. Move `MobileOptimizationProvider` to only wrap on `isMobile`

**Validation:**
- [ ] All context consumers still receive data
- [ ] No "missing context" errors
- [ ] Autoloop status bar still works
- [ ] Mobile optimization still works

---

### Step 6.3: Audit Context Update Frequency
**Time:** 1 hour
**Risk:** 🟢 Low — Read-only analysis

**Check which contexts update frequently (cause re-renders):**

| Context | Update Frequency | Impact |
|---------|-----------------|--------|
| SystemStatusContext | Every botStatus change | 🔴 High |
| SymbolContext | On symbol change only | 🟢 Low |
| InstanceContext | On instance change only | 🟢 Low |
| AutoloopContext | Every autoloop tick | 🟡 Medium |
| MobileOptimizationContext | On resize only | 🟢 Low |
| IdleContext | On idle state change | 🟢 Low |

**Action for high-frequency contexts:**
- Split `SystemStatusContext` into `SystemStatusContext` (rarely changes: botRunning) and `SystemMetricsContext` (frequently changes: latency, warnings)
- Use `useShallow` selector from Zustand for Zustand store reads (already imported but verify usage)

**Validation:**
- [ ] React DevTools Profiler shows fewer re-renders
- [ ] No functionality changes

---

### Phase 6 Completion Checklist
- [ ] Duplicate SymbolProvider removed
- [ ] Provider nesting reduced from 6 to 4
- [ ] No "missing context" errors
- [ ] React DevTools shows fewer re-renders
- [ ] Commit & merge to main

---

## Phase 7: Backend Caching Expansion

> **Why:** Only 4 of 62 routes have caching. Adding caching to more routes reduces server load and speeds up responses with zero frontend risk.

**Timeline:** 1-2 days
**Impact:** 🔥🔥🔥 — 50-80% reduction in API response times
**Risk:** 🟢 Low — Backend-only, additive changes

### Pre-Condition Checklist
- [ ] Branch: `git checkout -b perf/phase7-backend-caching`
- [ ] Backend starts successfully: `python3 webui/backend/app.py`

---

### Step 7.1: Cache Read-Only Endpoints (Batch 1 — Safe)
**Time:** 2-3 hours
**Risk:** 🟢 Low — Read-only endpoints, cache won't affect writes

**Add `@cache.cached()` to these routes:**

| Route File | Endpoint | TTL | Notes |
|------------|----------|-----|-------|
| `analytics.py` | `/api/analytics/*` | 30s | Heavy DB queries |
| `pnl.py` | `/api/pnl` | 5s | Called frequently |
| `orders.py` | `/api/orders` | 5s | Called frequently |
| `market.py` | `/api/market/*` | 10s | External API calls |
| `system.py` | `/api/system/*` | 30s | System info rarely changes |
| `risk.py` | `/api/risk/*` | 10s | Risk metrics |
| `performance.py` | `/api/performance/*` | 30s | Historical data |
| `todos.py` | `/api/todos` (GET only) | 10s | Rarely changes |
| `metrics.py` | `/api/metrics` | 5s | Frequently polled |

**Pattern for each file:**
```python
from cache import cache, make_cache_key, CACHE_TIMEOUTS

@blueprint.route('/api/pnl')
@cache.cached(timeout=CACHE_TIMEOUTS['positions'], make_cache_key=make_cache_key)
def get_pnl():
    # existing code unchanged
```

**Validation per route:**
- [ ] First request: normal response time
- [ ] Second request within TTL: faster response
- [ ] After TTL: fresh data returned

---

### Step 7.2: Cache Invalidation for Write Endpoints
**Time:** 1-2 hours
**Risk:** 🟡 Medium — Must ensure stale data is cleared on writes

**For endpoints that modify data, clear related caches:**
```python
@blueprint.route('/api/config', methods=['POST'])
def update_config():
    result = do_update()
    cache.delete_memoized(get_config)  # Clear config cache
    return jsonify(result)
```

**Write endpoints that need invalidation:**
| Write Endpoint | Caches to Clear |
|---------------|-----------------|
| POST `/api/config` | config cache |
| POST `/api/bot/start` | bot status, positions |
| POST `/api/bot/stop` | bot status, positions |
| POST `/api/todos` | todos cache |
| POST `/api/orders` | orders cache |

**Validation:**
- [ ] Update config → next GET returns new config
- [ ] Start bot → status immediately reflects running
- [ ] Add todo → list immediately shows new item

---

### Step 7.3: Add Cache Headers for Browser Caching
**Time:** 30 minutes
**Risk:** 🟢 Low

**Add Cache-Control headers for static-ish endpoints:**
```python
@blueprint.after_request
def add_cache_headers(response):
    if request.method == 'GET':
        response.headers['Cache-Control'] = 'public, max-age=5'
    return response
```

**Validation:**
- [ ] Browser DevTools → Network tab → check Cache-Control headers

---

### Phase 7 Completion Checklist
- [ ] 15+ endpoints now cached (up from 4)
- [ ] Write endpoints properly invalidate caches
- [ ] API response times reduced by 50-80%
- [ ] No stale data bugs
- [ ] Commit & merge to main

---

## Phase 8: Virtual Scrolling for Large Lists

> **Why:** Positions, orders, logs, and trade history can have 100-1000+ items. Rendering all DOM nodes causes jank.

**Timeline:** 1 day
**Impact:** 🔥🔥 — Smooth 60fps scrolling for large datasets
**Risk:** 🟢 Low — Additive, component-level change

### Pre-Condition Checklist
- [ ] Branch: `git checkout -b perf/phase8-virtual-scrolling`
- [ ] Install: `npm install react-window`

---

### Step 8.1: Virtualize PositionsPanel
**Time:** 2-3 hours
**Risk:** 🟡 Medium — Most visible panel

**Identify the list rendering in PositionsPanel.js:**
```bash
grep -n "\.map(" webui/frontend/src/components/PositionsPanel.js | head -10
```

**Wrap with `react-window` `FixedSizeList`:**
```javascript
import { FixedSizeList as List } from 'react-window';

// Replace .map() with:
<List
  height={Math.min(positions.length * 60, 600)}
  itemCount={positions.length}
  itemSize={60}
  width="100%"
>
  {({ index, style }) => (
    <PositionRow style={style} position={positions[index]} />
  )}
</List>
```

**Only apply if >20 items.** For small lists, keep normal rendering:
```javascript
{positions.length > 20 ? (
  <VirtualizedList items={positions} ... />
) : (
  positions.map(p => <PositionRow key={p.id} {...p} />)
)}
```

**Validation:**
- [ ] Small list (<20): renders normally
- [ ] Large list (>20): scroll is smooth
- [ ] All position data visible
- [ ] Click handlers still work

---

### Step 8.2: Virtualize LogsPanel
**Time:** 1-2 hours
**Risk:** 🟢 Low — Logs are text-only, simple rows

**Apply same pattern to LogsPanel.js** for log entries.

**Validation:**
- [ ] Log filtering still works
- [ ] Auto-scroll to bottom still works
- [ ] Log entries are readable

---

### Step 8.3: Virtualize Options Chain Table
**Time:** 2-3 hours
**Risk:** 🟡 Medium — Complex table with headers and interactive cells

**Only if the options chain table renders >50 strikes.**

**Use `react-window` `VariableSizeList` for variable-height rows.**

**Validation:**
- [ ] Strike prices render correctly
- [ ] Greeks columns align
- [ ] Click-to-trade still works

---

### Phase 8 Completion Checklist
- [ ] `react-window` installed
- [ ] PositionsPanel virtualized
- [ ] LogsPanel virtualized
- [ ] Options chain virtualized (if applicable)
- [ ] Small lists still render normally
- [ ] Commit & merge to main

---

## Phase 9: React Re-render Optimization

> **Why:** After App.js decomposition (Phase 2), each page component is isolated. Now we can optimize individual components without risking the whole app.

**Timeline:** 1-2 days
**Impact:** 🔥🔥 — 40-60% fewer re-renders
**Risk:** 🟢 Low — Non-breaking optimizations

### Pre-Condition Checklist
- [ ] Phase 2 complete (App.js decomposed)
- [ ] Branch: `git checkout -b perf/phase9-rerender-optimization`

---

### Step 9.1: Profile Current Re-renders
**Time:** 30 minutes
**Risk:** 🟢 None — Read-only analysis

**Using React DevTools Profiler:**
1. Open Chrome DevTools → Profiler tab
2. Click "Start profiling"
3. Navigate between 3-4 tabs
4. Stop profiling
5. Look for "Why did this render?" on each component

**Document the top 10 most re-rendered components.**

---

### Step 9.2: Add React.memo to Heavy Components
**Time:** 1-2 hours
**Risk:** 🟢 Low

**Wrap these components with `React.memo()`:**
- `CollapsibleCard`
- `TopBar`
- `Sidebar`
- `SymbolContextBar`
- `AutoloopStatusBar`
- Any component re-rendering >5 times per navigation

**Pattern:**
```javascript
// Before
export default function CollapsibleCard({ ... }) { ... }

// After
export default React.memo(function CollapsibleCard({ ... }) { ... });
```

**Validation:**
- [ ] React DevTools shows fewer renders
- [ ] All components still update when their data changes

---

### Step 9.3: Verify Zustand Store Selectors (Already Mostly Done)
**Time:** 30 minutes
**Risk:** 🟢 Low

**Good news:** The store already exports dedicated selector hooks:
- `usePositions()`, `useOrders()`, `useHealth()`, etc. — each uses `useStore(state => state.X)`
- `useStoreActions()` — uses `useShallow()` for action methods (no re-render on data changes)

**Remaining check:** Verify no component imports `useStore` directly without a selector:

```javascript
// BAD: Re-renders on ANY store change
const state = useStore();

// GOOD: Re-renders only when positions change
const positions = useStore(state => state.positions);

// BEST: Multiple values with shallow comparison
const { positions, orders } = useStore(
  useShallow(state => ({ positions: state.positions, orders: state.orders }))
);
```

**Validation:**
- [ ] Components only re-render when their specific data changes
- [ ] No missing data updates

---

### Step 9.4: Debounce Rapid WebSocket Updates
**Time:** 1 hour
**Risk:** 🟡 Medium — Must not lose critical updates

**Check if socket events trigger too many state updates:**
```bash
grep -n "setTradingSnapshot\|setPositionsData\|setBotStatus" webui/frontend/src/hooks/useSocketConnection.js
```

**If updates come faster than 100ms, batch them:**
```javascript
// Debounce position updates to max 5/second
const debouncedSetPositions = useMemo(
  () => debounce(setPositionsData, 200),
  [setPositionsData]
);
```

**Critical: Do NOT debounce:**
- Emergency stop signals
- Error notifications
- Connection state changes

**Validation:**
- [ ] Position data still updates in real-time
- [ ] No visible lag in UI
- [ ] Emergency controls still instant

---

### Phase 9 Completion Checklist
- [ ] Re-render audit complete
- [ ] React.memo applied to heavy components
- [ ] Zustand selectors optimized
- [ ] WebSocket updates debounced (non-critical)
- [ ] React DevTools shows 40-60% fewer renders
- [ ] Commit & merge to main

---

## Phase 10: Production Build & Delivery Optimization

**Timeline:** 0.5-1 day
**Impact:** 🔥 — 20-30% faster asset delivery
**Risk:** 🟢 Low — Infrastructure-only

### Pre-Condition Checklist
- [ ] Branch: `git checkout -b perf/phase10-production-polish`

---

### Step 10.1: Add Resource Hints to index.html
**Time:** 15 minutes
**Risk:** 🟢 None

**File:** `webui/frontend/public/index.html`

Add inside `<head>`:
```html
<!-- Preconnect to API backend -->
<link rel="preconnect" href="http://localhost:5555">
<link rel="dns-prefetch" href="http://localhost:5555">

<!-- Preload critical font -->
<link rel="preload" href="/static/css/main.css" as="style">
```

**Validation:**
- [ ] Chrome DevTools → Network → resource hints visible
- [ ] No CORS errors

---

### Step 10.2: Enable Brotli Compression (Backend)
**Time:** 30 minutes
**Risk:** 🟢 Low

```bash
pip install brotli flask-compress
```

**In `webui/backend/app.py`:**
```python
app.config['COMPRESS_ALGORITHM'] = ['br', 'gzip']  # Prefer Brotli
```

**Validation:**
- [ ] Response headers show `Content-Encoding: br`
- [ ] 20-30% smaller than gzip

---

### Step 10.3: Long-term Cache for Static Assets
**Time:** 15 minutes
**Risk:** 🟢 None

CRA already adds content hashes to built files (`main.abc123.js`). Verify the Flask static file handler sets long cache:

```python
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year for hashed files
```

**Validation:**
- [ ] Static JS/CSS files have `Cache-Control: max-age=31536000`

---

### Step 10.4: Bundle Size Budget Enforcement
**Time:** 15 minutes
**Risk:** 🟢 None

**Add to `config-overrides.js`:**
```javascript
config.performance = {
  maxAssetSize: 250000,      // 250KB per file warning
  maxEntrypointSize: 500000,  // 500KB entry point warning
  hints: 'warning',
};
```

**Already partially done** (line 80+ of config-overrides.js). Verify thresholds are enforced.

**Validation:**
- [ ] Build shows warnings if any chunk exceeds 250KB

---

### Phase 10 Completion Checklist
- [ ] Resource hints added
- [ ] Brotli compression enabled
- [ ] Static cache headers set
- [ ] Bundle budget enforced
- [ ] Commit & merge to main

---

## Phase 11: Monitoring & Regression Prevention

**Timeline:** Ongoing
**Impact:** 🔧 — Prevents performance regressions
**Risk:** 🟢 None

### Step 11.1: Bundle Size Tracking Script
**Time:** 15 minutes

**Create `webui/frontend/scripts/check-bundle-size.sh`:**
```bash
#!/bin/bash
npm run build 2>&1 | tail -20
MAIN_SIZE=$(wc -c < build/static/js/main.*.js)
if [ "$MAIN_SIZE" -gt 250000 ]; then
  echo "❌ ALERT: Main bundle exceeds 250KB ($MAIN_SIZE bytes)"
  exit 1
fi
echo "✅ Bundle size OK: $MAIN_SIZE bytes"
```

---

### Step 11.2: Performance Monitoring Hook
**Time:** Already exists — `utils/performanceMonitor.js`

**Verify it tracks:**
- [ ] Page load time
- [ ] Panel switch time
- [ ] API response times
- [ ] WebSocket reconnect time

---

### Step 11.3: Monthly Review Checklist
- [ ] Run `npm run analyze` — check for new bloated dependencies
- [ ] Run `npx depcheck` — remove unused packages
- [ ] Check React DevTools Profiler — identify regression
- [ ] Review `npm audit` — security + performance
- [ ] Check backend response times for new routes

---

## Implementation Priority & Timeline

```
Week 1:
├── Day 1-2: Phase 5 (Dependency Cleanup) — Quick wins, low risk
├── Day 3-4: Phase 7 Steps 7.1-7.2 (Backend Caching) — Backend only, no frontend risk
│
Week 2:
├── Day 5-7: Phase 2 Steps 2.1 Batch A+B (Extract simple pages) — 15 pages
├── Day 8:   Phase 2 Steps 2.1 Batch C (Extract complex pages) — 9 pages
├── Day 9:   Phase 2 Steps 2.2-2.4 (App.js cleanup) — Final reduction
│
Week 3:
├── Day 10:  Phase 6 (Context Provider fix) — Fix duplicate, consolidate
├── Day 11:  Phase 8 (Virtual Scrolling) — PositionsPanel + LogsPanel
├── Day 12:  Phase 9 (Re-render optimization) — React.memo + selectors
│
Week 4:
├── Day 13:  Phase 10 (Production polish) — Brotli, hints, cache
├── Day 14:  Phase 11 (Monitoring setup) — Scripts, budgets
```

---

## Expected Final Results

| Metric | Before | After All Phases | Improvement |
|--------|--------|------------------|-------------|
| Main bundle (gzipped) | 192 KB | <130 KB | 32% smaller |
| Total initial load | ~575 KB | <350 KB | 39% smaller |
| App.js lines | 1,754 | <250 | 86% reduction |
| Context provider depth | 6 | 3-4 | 33-50% fewer |
| Cached backend routes | 4 | 15+ | 275% more |
| Re-renders per nav | ~50 | ~15 | 70% fewer |
| Large list rendering | All DOM nodes | Virtual (visible only) | 95% fewer nodes |
| API P95 latency | ~500ms | <100ms | 80% faster |
| Lighthouse Score | ~70 | 90+ | +20 points |

---

## Risk Matrix

| Phase | Risk | Impact if Failed | Rollback Time |
|-------|------|-----------------|---------------|
| Phase 2 (App.js decomp) | 🟡 Medium | UI won't render | `git checkout main` (instant) |
| Phase 5 (Dep cleanup) | 🟢 Low | Missing animation/chart | `npm install` + revert |
| Phase 6 (Context) | 🟡 Medium | Missing context data | `git checkout main` |
| Phase 7 (Backend cache) | 🟢 Low | Stale data | Remove `@cache.cached` |
| Phase 8 (Virtual scroll) | 🟢 Low | Scroll issues | Revert component file |
| Phase 9 (Re-render) | 🟢 Low | Missing updates | Remove `React.memo` |
| Phase 10 (Production) | 🟢 Low | No compression | Revert config |

---

## Quick Command Reference

```bash
# Create branch for any phase
git checkout -b perf/phase-X-step-Y

# Build and verify
cd webui/frontend && npm run build

# Analyze bundle
npm run analyze

# Check unused deps
npx depcheck

# Run tests
npm test -- --watchAll=false

# Start backend for testing
cd webui/backend && python3 app.py

# Start frontend dev server
cd webui/frontend && npm start

# Profile re-renders
# Open Chrome → React DevTools → Profiler → Start → Navigate → Stop

# Merge completed phase
git checkout main && git merge perf/phase-X-step-Y
```

---

**Start with Phase 5 (Dependency Cleanup) for immediate, zero-risk wins.**






