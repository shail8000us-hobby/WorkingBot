# V3 Complete Migration Plan - Make Every V1 Component Work

**Goal:** Ensure v3 works with each and every component from v1  
**Strategy:** Systematic migration and API integration fixes

---

## Phase 1: API Integration Fixes (IMMEDIATE)

**Issue:** 75+ files using `localhost:5557` instead of `5555`  
**Solution:** 
1. Create utility to use centralized API client
2. Fix all hardcoded API URLs
3. Ensure all components use `api.ts` client

**Files to Fix:** 20+ components with hardcoded URLs

---

## Phase 2: Missing Component Migration (HIGH PRIORITY)

### Critical Missing Components:

1. **SymbolPortfolio** - Multi-symbol overview
   - Status: ❌ Missing
   - Priority: HIGH
   - Location: `/portfolio` page placeholder

2. **BotBrainAnalyzer** - Decision flowchart
   - Status: ❌ Missing
   - Priority: HIGH  
   - Location: `/brain-flow` page placeholder
   - Sub-components needed: DecisionFlowGraph, SequenceTimeline, BrainModulesList, etc.

3. **ModeSwitcherPanel** - Auto mode switching
   - Status: ❌ Missing
   - Priority: MEDIUM
   - Location: `/mode-switcher` page placeholder

4. **TodoListPanel** - Todo tracking
   - Status: ❌ Missing
   - Priority: LOW
   - Location: `/todos` page placeholder

5. **FileEditor** - Code editing
   - Status: ❌ Missing
   - Priority: MEDIUM
   - Location: `/file-editor` page placeholder

6. **ConfigVisualEditor** - Visual config editor
   - Status: ❌ Missing
   - Priority: MEDIUM
   - Location: `/config-visual-editor` page placeholder

---

## Phase 3: Component Enhancement (MEDIUM PRIORITY)

Components that exist but need enhancements to match v1:
- RiskSafetyDashboard (exists but may need v1 features)
- GuardianDashboard (exists but verify all features)
- Various panels that may be missing features

---

## Phase 4: Testing & Verification (ONGOING)

- Test each component functionality
- Verify API endpoints work
- Ensure UI/UX matches v1
- Fix any bugs or missing features

---

## Implementation Strategy

1. **Fix API URLs first** - Use find/replace to update all hardcoded URLs
2. **Migrate critical components** - Start with SymbolPortfolio and BotBrainAnalyzer
3. **Test as we go** - Verify each component works
4. **Iterate** - Continue until all components work

---

**Estimated Time:** 20-30 hours for full completion  
**Current Status:** Starting Phase 1

