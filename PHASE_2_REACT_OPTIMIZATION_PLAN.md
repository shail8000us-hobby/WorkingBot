# Phase 2: React Performance Optimization - Detailed Implementation Plan

**Project:** WorkingBot WebUI
**Phase:** 2 of 6
**Status:** 📋 Planning Complete - Ready for Execution
**Risk Level:** ⚠️ HIGH (touches core App.js with 1,749 lines)
**Timeline:** 4-6 days (extended from original 2-3 days estimate)
**Impact:** 🔥🔥 Medium-High - Eliminate UI lag, improve re-render performance
**Dependencies:** Phase 1 ✅ Complete

---

## Executive Summary

Phase 2 addresses the core React performance issues in App.js (1,749 lines, 61+ hooks). This phase is **high-risk** because App.js is the central component of the entire application. The strategy is to break down the monolith into smaller, testable units while maintaining backward compatibility.

**Key Goals:**
1. Refactor App.js from 1,749 lines → <300 lines
2. Reduce hooks from 61+ → <15 in main component
3. Eliminate excessive re-renders (target 60-70% reduction)
4. Implement virtual scrolling for large lists
5. Optimize context providers (8+ providers → 3-4 combined contexts)

**Expected Results:**
- 60-70% reduction in unnecessary re-renders
- Smooth 60fps animations
- Faster panel switching (<100ms)
- Improved maintainability for future development

---

## Pre-Requisites

### Before Starting Phase 2:

1. **✅ Verify Phase 1 is deployed and stable**
   - Confirm bundle sizes are as expected (~192KB gzipped)
   - No regression in production
   - Git commit: `9831915cd` deployed

2. **✅ Create comprehensive backup**
   ```bash
   git checkout -b phase-2-react-optimization
   git commit -m "Checkpoint: Before Phase 2 (App.js refactoring)"
   ```

3. **✅ Document current behavior**
   - Record current user flows (video screen capture recommended)
   - Take screenshots of all panels/pages
   - Document all features that must continue working

4. **✅ Set up testing environment**
   - Ensure backend is running on port 5555
   - Have browser DevTools React Profiler ready
   - Install React DevTools browser extension

5. **✅ Install required dependencies**
   ```bash
   cd webui/frontend
   npm install --save-dev @welldone-software/why-did-you-render
   npm install react-window react-router-dom@6 zustand immer
   ```

6. **✅ Create rollback plan**
   - Document current App.js line count: 1,749 lines
   - Create backup file: `cp src/App.js src/App.js.backup.phase1`
   - Note current git commit hash

---

## Risk Assessment & Mitigation

### High-Risk Areas:

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing functionality | **HIGH** | Critical | Incremental refactoring, test after each step |
| State management issues | **MEDIUM** | High | Keep existing state logic initially, refactor gradually |
| WebSocket connection breaks | **MEDIUM** | High | Extract WebSocket logic first, test independently |
| Context provider bugs | **MEDIUM** | Medium | Combine contexts one at a time, verify each |
| Hook dependency issues | **HIGH** | Medium | Use ESLint exhaustive-deps, audit manually |
| Navigation regression | **LOW** | Medium | Test all route transitions thoroughly |

### Mitigation Strategy:
- **Incremental approach**: Break Phase 2 into 12 micro-steps
- **Test after every step**: Verify UI still works before proceeding
- **Git commits per step**: Easy rollback to any point
- **Parallel development**: Keep old App.js until new architecture is proven
- **Feature flags**: Use environment variable to toggle new vs. old App.js

---

## Detailed Step-by-Step Plan

---

### Step 1: Audit Current State (Day 1, Morning - 2 hours)

**Objective:** Understand exactly what App.js does before touching it.

#### 1.1 Analyze App.js Structure
**Tasks:**
- [ ] Read through entire App.js file (1,749 lines)
- [ ] Document all hooks used (target: find all 61+)
- [ ] List all state variables (`useState` calls)
- [ ] List all effects (`useEffect` calls)
- [ ] Identify all API calls
- [ ] Map all WebSocket event handlers
- [ ] Document all context providers used
- [ ] List all child components rendered

**Tools:**
```bash
# Count hooks
grep -c "useState" webui/frontend/src/App.js
grep -c "useEffect" webui/frontend/src/App.js
grep -c "useCallback" webui/frontend/src/App.js
grep -c "useMemo" webui/frontend/src/App.js
grep -c "useRef" webui/frontend/src/App.js

# Find all context providers
grep -n "Provider>" webui/frontend/src/App.js

# Find all components rendered
grep -n "^  return" webui/frontend/src/App.js -A 100
```

**Output:** Create `docs/APP_JS_AUDIT.md` with findings

#### 1.2 Install Why Did You Render
**Tasks:**
- [ ] Create `src/wdyr.js` configuration file
- [ ] Import in `src/index.js` (development only)
- [ ] Run app and observe console logs
- [ ] Document which components re-render most frequently

**Goal:** Identify the top 10 components causing excessive re-renders

**Output:** Create `docs/RERENDER_HOTSPOTS.md` with data

#### 1.3 Profile Current Performance
**Tasks:**
- [ ] Open Chrome DevTools → Performance tab
- [ ] Record 30 seconds of typical user interaction:
  - Switch between panels
  - Scroll positions list
  - Change symbol/instance
  - View charts
- [ ] Analyze flame graph for long tasks (>50ms)
- [ ] Take screenshots of React Profiler showing render times

**Output:** Save profiler data as `docs/baseline-performance.json`

**Success Criteria:**
- Complete understanding of App.js architecture
- Identified top 10 re-render hotspots
- Baseline performance metrics recorded

---

### Step 2: Extract WebSocket Logic (Day 1, Afternoon - 3 hours)

**Objective:** Move WebSocket logic out of App.js into dedicated hook.

**Why first?** WebSocket is critical infrastructure. If we break it, entire app fails. Test early.

#### 2.1 Create `useWebSocket` Hook
**Tasks:**
- [ ] Create new file: `src/hooks/useWebSocket.js`
- [ ] Copy all `socketRef` related code from App.js
- [ ] Copy all `socket.on()` event handlers
- [ ] Copy connection/disconnection logic
- [ ] Export hook with clean interface:
  ```javascript
  const { socket, isConnected, emit } = useWebSocket({
    onPositionUpdate: handlePositionUpdate,
    onTradeUpdate: handleTradeUpdate,
    // ... other handlers
  });
  ```

**Files to create:**
- `src/hooks/useWebSocket.js` (new)

**Files to modify:**
- `src/App.js` (remove WebSocket code, replace with hook)

#### 2.2 Test WebSocket Hook
**Tasks:**
- [ ] Replace WebSocket code in App.js with new hook
- [ ] Start backend server
- [ ] Verify WebSocket connects (check browser console)
- [ ] Verify all event handlers still work:
  - Position updates appear
  - Trade notifications show
  - Health status updates
  - Log messages arrive
- [ ] Test reconnection after backend restart

**Success Criteria:**
- App.js reduced by ~100-150 lines
- All WebSocket functionality works identically
- No console errors
- Git commit: "Extract WebSocket logic into useWebSocket hook"

---

### Step 3: Extract Navigation State (Day 1, Evening - 2 hours)

**Objective:** Move sidebar/navigation state into dedicated hook.

#### 3.1 Create `useNavigation` Hook
**Tasks:**
- [ ] Create new file: `src/hooks/useNavigation.js`
- [ ] Move all `activePanel` state
- [ ] Move all `sidebarCollapsed` state
- [ ] Move all panel switching logic
- [ ] Move all sidebar toggle logic
- [ ] Export clean interface:
  ```javascript
  const {
    activePanel,
    setActivePanel,
    sidebarCollapsed,
    toggleSidebar,
    navigationHistory
  } = useNavigation();
  ```

**Files to create:**
- `src/hooks/useNavigation.js` (new)

**Files to modify:**
- `src/App.js` (remove navigation state, replace with hook)

#### 3.2 Test Navigation Hook
**Tasks:**
- [ ] Click through all sidebar menu items
- [ ] Verify panel switching works
- [ ] Test sidebar collapse/expand
- [ ] Verify navigation state persists (if it did before)
- [ ] Check for console warnings

**Success Criteria:**
- App.js reduced by ~80-120 lines
- All navigation works identically
- Git commit: "Extract navigation logic into useNavigation hook"

---

### Step 4: Create Layout Components (Day 2, Morning - 3 hours)

**Objective:** Extract layout structure from App.js.

#### 4.1 Create `DashboardLayout.js`
**Tasks:**
- [ ] Create new file: `src/layouts/DashboardLayout.js`
- [ ] Move sidebar rendering logic
- [ ] Move top bar rendering logic
- [ ] Move main content area wrapper
- [ ] Keep all context providers here (don't move yet)
- [ ] Accept `children` prop for page content

**Structure:**
```javascript
// DashboardLayout wraps the entire authenticated app
<DashboardLayout>
  {/* Context providers stay here */}
  <Sidebar />
  <TopBar />
  <MainContent>
    {children}
  </MainContent>
</DashboardLayout>
```

**Files to create:**
- `src/layouts/DashboardLayout.js` (new)

#### 4.2 Create `MinimalLayout.js`
**Tasks:**
- [ ] Create new file: `src/layouts/MinimalLayout.js`
- [ ] Simple wrapper for login/error pages
- [ ] No sidebar, no top bar
- [ ] Basic styling only

**Files to create:**
- `src/layouts/MinimalLayout.js` (new)

#### 4.3 Update App.js to Use Layouts
**Tasks:**
- [ ] Import DashboardLayout
- [ ] Wrap main content in layout
- [ ] Remove sidebar/topbar JSX from App.js
- [ ] Verify rendering

**Success Criteria:**
- App.js reduced by ~200-300 lines
- Layout visually identical
- All UI elements render correctly
- Git commit: "Extract layout components from App.js"

---

### Step 5: Create Page Components (Day 2, Afternoon - 4 hours)

**Objective:** Break App.js panels into separate page components.

#### 5.1 Identify All Panels/Pages
**Tasks:**
- [ ] List all panels currently rendered in App.js:
  - Dashboard/Overview panel
  - Positions panel
  - Options trading panel
  - Analytics panel
  - Backtest panel
  - Configuration panel
  - Logs panel
  - Brain analyzer panel
  - Health check panel
  - (Add any others found)

#### 5.2 Create Page Components (One by One)
**Strategy:** Create one page at a time, test, commit, repeat.

**For EACH page, do:**

**Tasks:**
- [ ] Create new file: `src/pages/[PageName]Page.js`
- [ ] Copy relevant JSX from App.js for this panel
- [ ] Copy relevant state variables (keep them local for now)
- [ ] Copy relevant useEffect hooks
- [ ] Copy relevant API calls
- [ ] Import all necessary components
- [ ] Export page component
- [ ] Update App.js to render this page component instead of inline JSX
- [ ] Test the page works identically
- [ ] Git commit: "Extract [PageName] into separate page component"

**Files to create (one per panel):**
- `src/pages/DashboardPage.js`
- `src/pages/PositionsPage.js`
- `src/pages/OptionsPage.js`
- `src/pages/AnalyticsPage.js`
- `src/pages/BacktestPage.js`
- `src/pages/ConfigPage.js`
- `src/pages/LogsPage.js`
- `src/pages/BrainAnalyzerPage.js`
- `src/pages/HealthCheckPage.js`

**Success Criteria:**
- App.js reduced by ~600-900 lines (most significant reduction)
- Each page works identically to before
- All panels accessible and functional
- 9+ git commits (one per page)

---

### Step 6: Implement Client-Side Routing (Day 3, Morning - 3 hours)

**Objective:** Replace panel switching with proper routing.

#### 6.1 Set Up React Router
**Tasks:**
- [ ] Verify `react-router-dom` v6 is installed
- [ ] Create `src/routes/index.js` with route definitions
- [ ] Define routes for each page:
  ```javascript
  const routes = [
    { path: '/', element: <DashboardPage /> },
    { path: '/positions', element: <PositionsPage /> },
    { path: '/options', element: <OptionsPage /> },
    { path: '/analytics', element: <AnalyticsPage /> },
    { path: '/backtest', element: <BacktestPage /> },
    { path: '/config', element: <ConfigPage /> },
    { path: '/logs', element: <LogsPage /> },
    { path: '/brain', element: <BrainAnalyzerPage /> },
    { path: '/health', element: <HealthCheckPage /> },
  ];
  ```

**Files to create:**
- `src/routes/index.js` (new)

#### 6.2 Update App.js to Use Router
**Tasks:**
- [ ] Import `BrowserRouter`, `Routes`, `Route` from react-router-dom
- [ ] Replace `activePanel` conditional rendering with `<Routes>`
- [ ] Wrap app in `<BrowserRouter>`
- [ ] Update sidebar links to use `<Link>` or `<NavLink>`

**Files to modify:**
- `src/App.js` (replace panel switching with routing)
- `src/layouts/DashboardLayout.js` (update sidebar links)

#### 6.3 Test Routing
**Tasks:**
- [ ] Click all sidebar links
- [ ] Verify URL changes (e.g., `/positions`, `/options`)
- [ ] Test browser back/forward buttons
- [ ] Test direct URL navigation (refresh on `/positions`)
- [ ] Verify active link highlighting still works

**Success Criteria:**
- URL-based navigation working
- Browser history works correctly
- Deep linking works (can bookmark `/positions`)
- Git commit: "Implement React Router for page navigation"

---

### Step 7: Optimize Context Providers (Day 3, Afternoon - 4 hours)

**Objective:** Reduce 8+ context providers to 3-4 combined contexts.

#### 7.1 Audit Current Contexts
**Tasks:**
- [ ] List all context providers in App.js/DashboardLayout:
  - SymbolProvider
  - InstanceProvider
  - AutoloopProvider
  - MMMProvider
  - SystemStatusProvider
  - (Add any others found)
- [ ] Document what each context provides
- [ ] Identify which contexts change frequently
- [ ] Identify which contexts are read-only

**Output:** Create `docs/CONTEXT_AUDIT.md`

#### 7.2 Group Related Contexts
**Strategy:**
- Combine related contexts
- Separate frequently-changing from rarely-changing
- Use Zustand for high-frequency updates

**Proposed grouping:**
- **TradingContext**: Symbol + Instance + Positions (changes frequently)
- **SystemContext**: SystemStatus + Health (changes moderately)
- **FeatureContext**: Autoloop + MMM (changes rarely)
- **UserPreferencesContext**: Theme, sidebar state (changes rarely)

#### 7.3 Create Combined Contexts (One at a Time)

**For TradingContext:**
**Tasks:**
- [ ] Create `src/contexts/TradingContext.js`
- [ ] Combine SymbolProvider + InstanceProvider logic
- [ ] Use `useReducer` or Zustand for complex state
- [ ] Export combined provider and hooks
- [ ] Replace old providers in DashboardLayout
- [ ] Test all trading-related functionality
- [ ] Git commit: "Combine Symbol+Instance into TradingContext"

**For SystemContext:**
**Tasks:**
- [ ] Create `src/contexts/SystemContext.js`
- [ ] Combine SystemStatusProvider + HealthProvider logic
- [ ] Export combined provider and hooks
- [ ] Replace old providers in DashboardLayout
- [ ] Test system status displays
- [ ] Git commit: "Combine SystemStatus+Health into SystemContext"

**For FeatureContext:**
**Tasks:**
- [ ] Create `src/contexts/FeatureContext.js`
- [ ] Combine AutoloopProvider + MMMProvider logic
- [ ] Export combined provider and hooks
- [ ] Replace old providers in DashboardLayout
- [ ] Test feature toggles
- [ ] Git commit: "Combine Autoloop+MMM into FeatureContext"

**Files to create:**
- `src/contexts/TradingContext.js`
- `src/contexts/SystemContext.js`
- `src/contexts/FeatureContext.js`
- `src/contexts/UserPreferencesContext.js`

**Files to modify:**
- `src/layouts/DashboardLayout.js` (replace old providers)

**Success Criteria:**
- 8+ providers reduced to 4 providers
- All functionality works identically
- Reduced provider nesting (better performance)
- 3-4 git commits (one per context group)

---

### Step 8: Audit and Fix Hook Dependencies (Day 4, Morning - 3 hours)

**Objective:** Fix all `useEffect` dependency warnings and optimize re-renders.

#### 8.1 Enable ESLint Exhaustive Deps
**Tasks:**
- [ ] Ensure ESLint rule is enabled in `.eslintrc`:
  ```json
  {
    "rules": {
      "react-hooks/exhaustive-deps": "warn"
    }
  }
  ```
- [ ] Run ESLint on all pages and hooks:
  ```bash
  npm run lint src/pages/
  npm run lint src/hooks/
  ```
- [ ] Document all warnings

**Output:** Create `docs/HOOK_DEPENDENCY_WARNINGS.md`

#### 8.2 Fix Dependencies (File by File)

**For EACH warning, decide:**
1. **Add missing dependency** (most common)
2. **Wrap in `useCallback`/`useMemo`** (if function/object dependency)
3. **Move static data outside component** (if doesn't need to be inside)
4. **Disable warning with comment** (if intentionally omitted, rare)

**Tasks:**
- [ ] Fix App.js hook dependencies
- [ ] Fix DashboardLayout.js hook dependencies
- [ ] Fix each page component hook dependencies
- [ ] Fix each custom hook dependencies
- [ ] Re-run ESLint to verify no warnings remain

**Success Criteria:**
- Zero `react-hooks/exhaustive-deps` warnings
- No infinite render loops (test thoroughly)
- Git commit: "Fix all hook dependency warnings"

#### 8.3 Add `useCallback` for Event Handlers
**Tasks:**
- [ ] Find all event handler functions passed as props
- [ ] Wrap in `useCallback` with correct dependencies:
  ```javascript
  const handlePositionClick = useCallback((position) => {
    setSelectedPosition(position);
  }, []); // Only recreate if dependencies change
  ```
- [ ] Test functionality unchanged

**Success Criteria:**
- Event handlers don't cause unnecessary child re-renders
- Git commit: "Wrap event handlers in useCallback"

---

### Step 9: Implement `React.memo` for Expensive Components (Day 4, Afternoon - 3 hours)

**Objective:** Prevent unnecessary re-renders of heavy components.

#### 9.1 Identify Memo Candidates
**Tasks:**
- [ ] Review "Why Did You Render" logs from Step 1.2
- [ ] Find components that re-render frequently but props don't change
- [ ] Prioritize large/expensive components:
  - Chart components
  - Large data tables
  - Monaco Editor wrapper
  - Complex forms

**Output:** List of 10-15 components to memoize

#### 9.2 Apply `React.memo` (One at a Time)
**Tasks:**
- [ ] For EACH component:
  - [ ] Wrap export in `React.memo()`:
    ```javascript
    export default React.memo(PositionRow);
    ```
  - [ ] If props include functions/objects, provide custom comparison:
    ```javascript
    export default React.memo(ChartPanel, (prevProps, nextProps) => {
      return prevProps.data === nextProps.data &&
             prevProps.symbol === nextProps.symbol;
    });
    ```
  - [ ] Test component still updates when it should
  - [ ] Verify re-renders reduced (use React Profiler)

**Success Criteria:**
- 10-15 components memoized
- Visible reduction in re-renders (use Profiler to verify)
- No broken functionality
- Git commit: "Memoize expensive components to reduce re-renders"

---

### Step 10: Implement Virtual Scrolling (Day 5, Morning - 4 hours)

**Objective:** Use `react-window` for large lists (positions, trades, logs).

#### 10.1 Identify Long Lists
**Tasks:**
- [ ] Find all places rendering long lists with `.map()`:
  - Positions list
  - Trade history
  - Log viewer
  - Grid levels (if applicable)
- [ ] Measure typical list lengths:
  - How many positions are typical? (e.g., 50-500)
  - How many trades in history? (e.g., 100-1000)
  - How many log lines? (e.g., 500-5000)

#### 10.2 Implement Virtual Scrolling (One List at a Time)

**For Positions List:**
**Tasks:**
- [ ] Find positions list rendering in PositionsPage.js
- [ ] Import `FixedSizeList` from `react-window`
- [ ] Calculate item height (measure in DevTools)
- [ ] Replace `.map()` with `<FixedSizeList>`:
  ```javascript
  <FixedSizeList
    height={600}
    itemCount={positions.length}
    itemSize={60} // Height of each row
    width="100%"
  >
    {({ index, style }) => (
      <PositionRow style={style} position={positions[index]} />
    )}
  </FixedSizeList>
  ```
- [ ] Update PositionRow component to accept `style` prop
- [ ] Test scrolling performance (should be smooth even with 1000+ items)
- [ ] Git commit: "Add virtual scrolling to positions list"

**For Trade History:**
**Tasks:**
- [ ] Same process as positions list
- [ ] Git commit: "Add virtual scrolling to trade history"

**For Log Viewer:**
**Tasks:**
- [ ] Use `VariableSizeList` if log lines vary in height
- [ ] Git commit: "Add virtual scrolling to log viewer"

**Success Criteria:**
- Smooth scrolling even with 1000+ items
- No layout shift or flickering
- Selection/interaction still works
- 3 git commits (one per list)

---

### Step 11: Optimize Data Fetching in Pages (Day 5, Afternoon - 3 hours)

**Objective:** Prevent duplicate API calls, use shared state.

#### 11.1 Audit Data Fetching
**Tasks:**
- [ ] Review each page component
- [ ] Document which API endpoints each page calls
- [ ] Identify duplicate fetches (e.g., both DashboardPage and PositionsPage fetch positions)
- [ ] Check if dataAggregator is being used properly

**Output:** Create `docs/DATA_FETCHING_AUDIT.md`

#### 11.2 Centralize Shared Data Fetching
**Strategy:**
- Use existing Zustand dataAggregator for shared data
- Only fetch page-specific data in page components

**Tasks:**
- [ ] Move common data fetching to DashboardLayout (runs once on mount):
  - Positions
  - Config
  - Health status
  - System status
- [ ] Update pages to consume from dataAggregator instead of fetching directly
- [ ] Keep page-specific data in page components:
  - Backtest results (BacktestPage only)
  - Brain analyzer data (BrainAnalyzerPage only)
  - etc.

**Files to modify:**
- `src/layouts/DashboardLayout.js` (add shared data fetching)
- `src/pages/*.js` (remove duplicate fetches)

**Success Criteria:**
- No duplicate API calls for shared data
- Page load times improved
- Git commit: "Centralize shared data fetching in DashboardLayout"

---

### Step 12: Final Optimization & Testing (Day 6 - Full Day)

**Objective:** Polish, test, and verify all improvements.

#### 12.1 Run Performance Profiler Again
**Tasks:**
- [ ] Open Chrome DevTools → Performance tab
- [ ] Record same 30-second interaction as Step 1.3
- [ ] Compare to baseline performance
- [ ] Analyze flame graph for improvements
- [ ] Take screenshots of React Profiler

**Output:** Save as `docs/phase2-performance.json`

#### 12.2 Measure Re-render Reduction
**Tasks:**
- [ ] Enable "Why Did You Render" again
- [ ] Perform typical user actions
- [ ] Count re-renders before vs. after
- [ ] Document results

**Target:** 60-70% reduction in unnecessary re-renders

#### 12.3 Verify All Functionality
**Tasks:**
- [ ] Click through every page/panel
- [ ] Test all features:
  - [ ] Position management
  - [ ] Trade execution
  - [ ] Config changes
  - [ ] Symbol/instance switching
  - [ ] Autoloop toggle
  - [ ] MMM features
  - [ ] Backtest runs
  - [ ] Brain analyzer
  - [ ] Log viewing
  - [ ] Health monitoring
- [ ] Test WebSocket updates appear correctly
- [ ] Test error handling
- [ ] Check browser console for errors/warnings

#### 12.4 Performance Testing
**Tasks:**
- [ ] Test with large datasets:
  - [ ] Load 500+ positions
  - [ ] View 1000+ trades
  - [ ] Scroll through 5000+ log lines
- [ ] Monitor memory usage (should be stable, no leaks)
- [ ] Test on slower hardware if possible
- [ ] Measure frame rate during scrolling (should be 60fps)

#### 12.5 Code Quality Check
**Tasks:**
- [ ] Run ESLint on all modified files: `npm run lint`
- [ ] Fix any remaining warnings
- [ ] Run Prettier to format code: `npm run format`
- [ ] Review all files for TODOs/FIXMEs
- [ ] Remove any debugging console.logs

#### 12.6 Update Documentation
**Tasks:**
- [ ] Update `WEBUI_PERFORMANCE_OPTIMIZATION_PLAN.md`:
  - Mark Phase 2 as ✅ Complete
  - Document actual results vs. targets
  - Note any deviations from plan
  - Add commit hash
- [ ] Update code comments where needed
- [ ] Create `docs/ARCHITECTURE.md` documenting new structure:
  - Page components
  - Layout components
  - Custom hooks
  - Context providers
  - Routing structure

#### 12.7 Final Git Commit
**Tasks:**
- [ ] Review all changes one last time
- [ ] Ensure all tests pass (if tests exist)
- [ ] Create final commit:
  ```bash
  git add .
  git commit -m "Phase 2 Complete: React performance optimization

  - Refactored App.js from 1,749 lines to <300 lines
  - Reduced hooks from 61+ to <15 in main component
  - Extracted 9 page components
  - Created 4 custom hooks (useWebSocket, useNavigation, etc.)
  - Combined 8+ contexts into 4 optimized contexts
  - Implemented React Router for proper navigation
  - Added virtual scrolling to large lists
  - Memoized 10+ expensive components
  - Fixed all hook dependency warnings
  - 60-70% reduction in unnecessary re-renders

  Performance improvements:
  - Panel switching: <100ms
  - Smooth 60fps scrolling
  - Reduced re-renders by XX%
  - Improved maintainability
  "
  ```

---

## Testing Checklist

Before marking Phase 2 complete, verify:

### Functionality Tests
- [ ] All pages accessible via sidebar
- [ ] All pages accessible via direct URL
- [ ] Browser back/forward buttons work
- [ ] WebSocket connection stable
- [ ] Real-time updates appear (positions, trades, health)
- [ ] Symbol/instance switching works
- [ ] Autoloop toggle works
- [ ] MMM features work
- [ ] Config changes save
- [ ] Backtest execution works
- [ ] Brain analyzer loads
- [ ] Logs display correctly
- [ ] Charts render correctly
- [ ] Modal dialogs open/close
- [ ] Forms submit correctly
- [ ] Error messages display

### Performance Tests
- [ ] No console errors
- [ ] No console warnings (except expected)
- [ ] No memory leaks (use Chrome Memory Profiler)
- [ ] Smooth scrolling on large lists (1000+ items)
- [ ] Fast panel switching (<100ms)
- [ ] 60fps animations
- [ ] React Profiler shows reduced render times
- [ ] Network tab shows no duplicate requests

### Code Quality Tests
- [ ] ESLint passes with no errors
- [ ] No unused imports
- [ ] No unused variables
- [ ] Consistent code formatting
- [ ] Proper PropTypes/TypeScript types (if applicable)
- [ ] Meaningful component/function names
- [ ] Code comments where needed

---

## Rollback Procedure

If Phase 2 needs to be rolled back:

### Immediate Rollback (emergency)
```bash
# Return to pre-Phase 2 state
git checkout main
git branch -D phase-2-react-optimization

# Restart frontend
cd webui/frontend
npm start
```

### Partial Rollback (specific step)
```bash
# Find the commit before the problematic step
git log --oneline

# Reset to that commit
git reset --hard <commit-hash>

# Or revert specific commits
git revert <commit-hash>
```

### Recovery from Backup
```bash
# If all else fails, restore from backup
cp src/App.js.backup.phase1 src/App.js
git checkout main -- src/
```

---

## Success Metrics

Phase 2 is considered successful when:

### Performance Metrics
- [x] App.js reduced from 1,749 lines → **<300 lines**
- [x] Hooks in App.js reduced from 61+ → **<15 hooks**
- [x] Panel switching time: **<100ms**
- [x] Re-render reduction: **60-70%**
- [x] Scrolling frame rate: **60fps**
- [x] Memory usage: **Stable, no leaks**

### Code Quality Metrics
- [x] Zero ESLint errors
- [x] Zero hook dependency warnings
- [x] All pages in separate files
- [x] All layout logic extracted
- [x] Clean routing implementation
- [x] Optimized context providers

### Functional Metrics
- [x] All existing features work identically
- [x] No regressions introduced
- [x] Improved developer experience
- [x] Better code maintainability

---

## Dependencies for Next Phases

Phase 2 enables:
- **Phase 5**: Better production builds (cleaner code splits)
- **Phase 6**: Easier performance monitoring (discrete components to track)
- **Future development**: Much easier to add new features

---

## Notes & Lessons Learned

(To be filled in during/after implementation)

### What Went Well:
-

### Challenges Encountered:
-

### Deviations from Plan:
-

### Recommendations for Future:
-

---

## Appendix: File Structure After Phase 2

```
webui/frontend/src/
├── App.js                         # <300 lines, routing only
├── index.js                       # Entry point
├── wdyr.js                        # Why Did You Render (dev only)
│
├── hooks/                         # Custom hooks
│   ├── useWebSocket.js           # WebSocket connection logic
│   ├── useNavigation.js          # Navigation state
│   ├── useDataFetching.js        # (if created)
│   └── ...
│
├── contexts/                      # Context providers
│   ├── TradingContext.js         # Symbol + Instance + Positions
│   ├── SystemContext.js          # SystemStatus + Health
│   ├── FeatureContext.js         # Autoloop + MMM
│   └── UserPreferencesContext.js # Theme, sidebar state
│
├── layouts/                       # Layout components
│   ├── DashboardLayout.js        # Main app layout
│   └── MinimalLayout.js          # Login/error pages
│
├── pages/                         # Page components (routes)
│   ├── DashboardPage.js
│   ├── PositionsPage.js
│   ├── OptionsPage.js
│   ├── AnalyticsPage.js
│   ├── BacktestPage.js
│   ├── ConfigPage.js
│   ├── LogsPage.js
│   ├── BrainAnalyzerPage.js
│   └── HealthCheckPage.js
│
├── routes/                        # Route definitions
│   └── index.js
│
├── components/                    # Existing components (unchanged)
│   ├── positions/
│   ├── options/
│   ├── charts/
│   └── ...
│
├── utils/                         # Utilities (existing)
│   ├── apiClient.js
│   ├── dataAggregator.js
│   └── ...
│
└── services/                      # Services (existing)
    └── ...
```

---

**Phase 2 Plan Status:** 📋 Ready for Implementation
**Estimated Completion Date:** 6 days from start
**Next Phase:** Phase 5 (Production Build & Delivery) or Phase 6 (Monitoring)

---

*Plan created: March 2, 2026*
*Based on Phase 1 completion: March 1, 2026*
*Current App.js: 1,749 lines, 61+ hooks*
