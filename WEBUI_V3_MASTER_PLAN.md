# 🎯 WebUI v3 Master Implementation Plan

## The Driver's Logbook

**Created:** January 2, 2026  
**Role:** AI is the driver, User observes  
**Status:** 🟢 PHASE 3 COMPLETE  
**Last Updated:** January 2, 2026 - Phase 3 Safety & Actions Complete

---

## 📋 Document Purpose

This is my (the AI's) living document to track progress across context sessions. I will:
1. Update this document as I complete each task
2. Mark phases/tasks complete with dates
3. Document decisions and learnings
4. Track blockers and resolutions

**User Agreement:** User will not interfere. I drive, they observe.

---

## ✅ COMPLETED PHASES

### Phase 0: Extraction & Setup ✅ COMPLETE
**Completed:** January 2, 2026

- [x] Research v1 components (94 components analyzed)
- [x] Research v2 types (364 lines documented)
- [x] Research backend API (40+ endpoints catalogued)
- [x] Research config structure (v6.0 multi-instance)
- [x] Create this master plan document
- [x] Create Next.js 15 project in `/webui/frontend-v3/`
- [x] Copy types from v2 to v3 (enhanced)
- [x] Create API endpoint reference file

### Phase 1: Foundation ✅ COMPLETE
**Completed:** January 2, 2026

#### Day 1: Project Setup ✅
- [x] Initialize Next.js 15.3.3 with App Router + Turbopack
- [x] Configure TypeScript strict mode
- [x] Tailwind CSS 4.0 configured
- [x] Initialize shadcn/ui (11 components installed)
- [x] Set up folder structure (types, lib, hooks, stores, components)
- [x] Create .env.local for API URL (port 5555) and WS URL

#### Day 2: Base Component Library ✅
- [x] Install shadcn/ui components (button, card, badge, input, switch, tooltip, separator, scroll-area, tabs, alert, skeleton)
- [x] Create `PriceDisplay.tsx` with color coding and size variants
- [x] Create `StatusBadge.tsx` (running/stopped/warning/error + pulse animation)
- [x] Create `TimeAgo.tsx` relative timestamps with auto-update
- [x] Create `SafetyCheck.tsx` & `SafetyGate.tsx` - WHY THIS IS SAFE display
- [x] Create `Metric.tsx` & `MetricGrid.tsx` for dashboard metrics
- [x] Create `LoadingState.tsx` (LoadingSpinner, LoadingCard, LoadingTable, FullPageLoading)

#### Day 3: WebSocket Backbone ✅
- [x] Create `lib/websocket.ts` - WebSocket client class
- [x] Implement auto-reconnection with exponential backoff
- [x] Create `hooks/useWebSocket.ts` - React hook with status tracking
- [x] Create `hooks/useLivePrice.ts` - Price subscription with polling fallback
- [x] Create `hooks/useBrainStream.ts` - Brain thought stream

#### Day 4: TanStack Query + API Layer ✅
- [x] Install TanStack Query v5 + devtools
- [x] Create `lib/api.ts` - Fetch wrapper with full error handling
  - All 40+ API endpoints wrapped
  - Typed responses
- [x] Create `hooks/useQueries.ts` - All API hooks
  - useInstances, usePositions, useOrders
  - usePnLHistory, useGuardianStatus, useBotStatus
  - useTradingStatus, useHealth
  - useBrainPrediction, useBrainScenarios
  - useEmergencyFlag, useEmergencyKillAll, useClearEmergencyFlag
  - useRiskAnalytics, useConfig, useUpdateConfig
- [x] Create Zustand stores (appStore, tradingStore)
- [x] Configure QueryClient with staleTime, caching

#### Day 5: Layout + Routing ✅
- [x] Create `app/layout.tsx` with AppShell wrapper
- [x] Create `components/layout/AppShell.tsx` - Main layout wrapper
- [x] Create `components/layout/Header.tsx` - Top bar with instance selector
- [x] Create `components/layout/Sidebar.tsx` - Navigation with quick stats
- [x] Create `components/layout/BrainPanel.tsx` - Right sidebar brain stream
- [x] Create `components/providers/QueryProvider.tsx` - TanStack Query setup
- [x] Create `components/providers/ThemeProvider.tsx` - Dark/light theme
- [x] Create Dashboard page (`app/page.tsx`) with:
  - Key metrics (P&L, positions, orders, portfolio delta)
  - Trading status grid
  - System health/safety checks
  - Positions preview
- [x] Build verified working (npm run build passes)
- [x] Dev server running on port 3003

### Phase 2: Core Features ✅ COMPLETE
**Completed:** January 3, 2026

#### Day 6: Command Center Enhancements ✅
- [x] Create `components/dashboard/PnLChart.tsx` with Recharts area chart
- [x] Create `components/dashboard/Timeline.tsx` for recent events
- [x] Create `components/dashboard/QuickActions.tsx`
  - Pause/Resume button with SafetyGate
  - Emergency Stop button with AlertDialog confirmation
- [x] Create `components/dashboard/ConnectionStatus.tsx` WebSocket indicator
- [x] Create `components/dashboard/index.ts` barrel export
- [x] Integrate all dashboard components into `app/page.tsx`

#### Day 7: Bot Brain Stream ✅
- [x] Create `components/brain/ThoughtBubble.tsx` - thought display with type icons
- [x] Create `components/brain/PredictionCard.tsx` - prediction with confidence
- [x] Create `components/brain/ThoughtStream.tsx` - live stream with filtering
- [x] Create `components/brain/index.ts` barrel export
- [x] Create `app/brain/page.tsx` - full page with tabs (Live Feed/Prediction/Scenarios)

#### Day 8: Grid Visualization 2D ✅
- [x] Create `components/grid/GridChart.tsx` - 2D visualization
  - Price levels visualization
  - Buy/Sell zones
  - Current price indicator
- [x] Create `components/grid/GridConfigCard.tsx` - configuration display
- [x] Create `components/grid/index.ts` barrel export
- [x] Create `app/grid/page.tsx` - grid page with visualization/levels/settings tabs

#### Day 9: Multi-Instance Control ✅
- [x] Create `components/instances/InstanceCard.tsx` - instance card with metrics
- [x] Create `components/instances/InstanceList.tsx` - grid/list view with filtering
- [x] Create `components/instances/index.ts` barrel export
- [x] Create `app/instances/page.tsx` - instance management with details panel
- [x] Implement instance filtering and sorting

#### Day 10: Positions & Orders Pages ✅
- [x] Create `components/trading/PositionCard.tsx` - position with P&L
- [x] Create `components/trading/OrderCard.tsx` - order with status
- [x] Create `components/trading/index.ts` barrel export
- [x] Create `app/positions/page.tsx` - positions list with filtering
- [x] Create `app/orders/page.tsx` - orders with tabs (open/filled/cancelled)

---

## 🚀 REMAINING PHASES

### Phase 3: Safety & Actions ✅ COMPLETE
**Completed:** January 2, 2026

#### Day 11: Safety-First Actions ✅
- [x] SafetyGate already exists in `components/common/SafetyCheck.tsx`
  - Shows "WHY THIS IS SAFE" before action
  - Lists all safety checks with pass/fail
  - Requires all checks pass before button active
- [x] Create `components/trading/EmergencyStopButton.tsx`
  - 3-second hold requirement
  - Confirmation modal with AlertDialog
  - Safety explanation visible
- [x] Create `components/trading/PauseTradingButton.tsx`
- [x] Create `components/trading/ConfirmActionDialog.tsx`
- [x] Add pause/resume API and hooks

#### Day 12: Guardian Integration ✅
- [x] Create `components/dashboard/GuardianStatus.tsx`
- [x] Create `components/dashboard/GuardianWidget.tsx` (compact version)
- [x] Show Guardian running status with GO/STOP/WARNING signal
- [x] Display RSI, volatility, margin, drawdown checks
- [x] Display active blockers
- [x] Start/Stop Guardian controls
- [x] Wire to `/api/guardian/status` endpoint

#### Day 13: Keyboard Shortcuts ✅
- [x] Create `hooks/useKeyboardShortcuts.ts`
- [x] Implement global shortcuts:
  - `1-5` - Quick navigation (Dashboard, Brain, Grid, Positions, Orders)
  - `I` - Go to Instances
  - `B` - Toggle Brain Panel
  - `?` - Show shortcuts help
  - `R` - Refresh data
- [x] Create `components/common/ShortcutsHelp.tsx` modal
- [x] Integrated into AppShell

#### Day 14: Command Palette ✅
- [x] Create `components/common/CommandPalette.tsx`
- [x] Fuzzy search with scoring
- [x] Commands for navigation, actions (pause/resume), view (theme toggle, brain panel)
- [x] Keyboard activation with `:` or `Cmd+K`
- [x] Arrow key navigation and Enter to select

---

## 🚀 REMAINING PHASES

### Phase 4: Polish & Deploy (Week 2.5)
**Duration:** 4 days  
**Status:** 🟡 UP NEXT

#### Day 15: Focus Modes (Imagination Feature)
- [ ] Create `stores/uiStore.ts` with focus mode state
- [ ] Implement Zen Mode (minimal UI when quiet)
- [ ] Implement Battle Mode (max density when active)
- [ ] Auto-switch based on activity level
- [ ] Persist user preference

#### Day 16: Error States & Edge Cases
- [ ] Handle backend down gracefully
- [ ] Handle WebSocket disconnect
- [ ] Handle stale data (>5 seconds)
- [ ] Add error boundaries per section
- [ ] Add loading skeletons
- [ ] Add empty states

#### Day 17: Mobile Responsiveness
- [ ] Test on mobile viewport
- [ ] Adjust grid layout for small screens
- [ ] Add touch-friendly buttons
- [ ] Swipeable metrics in header
- [ ] Bottom navigation for mobile

#### Day 18: Testing & Documentation
- [ ] Write key component tests (Vitest)
- [ ] Test WebSocket reconnection
- [ ] Test API error handling
- [ ] Create user guide in README
- [ ] Document all keyboard shortcuts
- [ ] Performance audit (Lighthouse)

#### Day 19: Side-by-Side Deployment
- [ ] Configure v3 to run on port 3003
- [ ] Update start scripts
- [ ] Test with production backend
- [ ] Compare v1 vs v3 feature parity
- [ ] Document any missing features

---

### Phase 5: Advanced Features (Week 3+)
**Duration:** TBD  
**Status:** ⏳ Future

**Deferred to Phase 5:**
- [ ] AI Advisor (Constrained Analyst - per mentor correction)
- [ ] 3D Grid Visualization (Analysis mode only)
- [ ] Config Wizard with live preview
- [ ] Time Travel mode (historical replay)
- [ ] Audio cues (spatial audio feedback)
- [ ] Widget marketplace concept
- [ ] Mobile PWA

---

## 📊 PROGRESS TRACKER

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| Phase 0 | 🟡 In Progress | Jan 2, 2026 | - | Research complete, setup pending |
| Phase 1 | ⏳ Not Started | - | - | Foundation week |
| Phase 2 | ⏳ Not Started | - | - | Core features |
| Phase 3 | ⏳ Not Started | - | - | Safety + actions |
| Phase 4 | ⏳ Not Started | - | - | Polish + deploy |
| Phase 5 | ⏳ Future | - | - | Advanced features |

---

## 🔧 TECHNICAL DECISIONS LOG

### Decision 1: Next.js 15 over Vite
**Date:** Jan 2, 2026  
**Decision:** Use Next.js 15 with App Router  
**Reason:** Server Components, streaming SSR, better SEO, file-based routing  
**Trade-off:** Slightly more complex than Vite SPA, but benefits outweigh

### Decision 2: No Mock Data
**Date:** Jan 2, 2026  
**Decision:** No mock data fallbacks - real data only  
**Reason:** User's valid critique - mock data hides backend bugs  
**Impact:** v3 requires working backend, which is fine for production use

### Decision 3: 2D Grid Default (Mentor Correction)
**Date:** Jan 2, 2026  
**Decision:** 3D visualization is Analysis Mode only, behind toggle  
**Reason:** Traders act fast, not admire geometry. 2D = lower cognitive load  
**Impact:** Phase 1 builds 2D only, 3D deferred to Phase 5

### Decision 4: AI = Constrained Analyst (Mentor Correction)
**Date:** Jan 2, 2026  
**Decision:** AI speaks in evidence-backed language, not opinions  
**Reason:** "I recommend" is dangerous. "Given X, Y reduces Z" is safe.  
**Impact:** AI feature deferred to Phase 5, will be read-only insights

---

## ⚠️ KNOWN BLOCKERS

| Blocker | Status | Resolution |
|---------|--------|------------|
| None yet | - | - |

---

## 📝 SESSION NOTES

### Session 1: January 2, 2026
**Context:** Initial research and planning  
**Completed:**
- Analyzed 94 v1 components
- Catalogued 40+ backend API endpoints
- Reviewed v2 TypeScript types (364 lines)
- Understood v6.0 multi-instance config
- Created this master plan document
- Created vision documents (ULTIMATE_VISION, PHASE1_SPEC, IMAGINATION_UNLEASHED)

**Next Session:**
- Start Phase 0 tasks: Create Next.js project, copy types
- Begin Phase 1 Day 1: Project setup

---

## 🎯 SUCCESS CRITERIA

### Phase 1 Complete When:
- [ ] Next.js 15 project running on port 3003
- [ ] Can connect to existing backend API
- [ ] WebSocket connection working
- [ ] Basic layout with navigation
- [ ] At least 5 shadcn/ui components working

### v3 MVP Complete When:
- [ ] Command Center shows live P&L, positions, prices
- [ ] Bot Brain Stream shows real-time thoughts
- [ ] Grid visualization shows orders/positions
- [ ] Emergency stop works with safety gate
- [ ] Multi-instance switching works
- [ ] Runs side-by-side with v1

### v3 Production Ready When:
- [ ] Feature parity with v1 (core features)
- [ ] Mobile responsive
- [ ] Keyboard shortcuts working
- [ ] Focus modes implemented
- [ ] All action buttons have safety gates
- [ ] No data displayed without staleness indicator
- [ ] Lighthouse score > 90

---

## 🔗 REFERENCE FILES

| File | Purpose |
|------|---------|
| `WEBUI_V3_ULTIMATE_VISION.md` | Original creative vision |
| `WEBUI_V3_PHASE1_SPEC.md` | Mentor-corrected Phase 1 spec |
| `WEBUI_V3_IMAGINATION_UNLEASHED.md` | Creative features catalog |
| `AI_CONTEXT.md` | Bot architecture reference |
| `/webui/frontend-v2/src/types/index.ts` | TypeScript types to copy |
| `/webui/backend/app.py` | Backend entry point |
| `/config.yaml` | v6.0 config structure |

---

**Document Version:** 1.0  
**Next Update:** When Phase 0 setup tasks begin
