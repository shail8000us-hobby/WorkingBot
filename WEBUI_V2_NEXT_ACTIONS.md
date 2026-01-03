# WebUI v2 - Next Actions (Priority Ordered)

> **Date:** January 2, 2026  
> **Quick Reference:** What to do next after Phase 1-4 completion

---

## 📊 Current Status Summary

**Completed:** Phases 1-4 (Foundation, Core Panels, WebSocket, Advanced Viz)  
**Progress:** 23/42 components (65% complete)  
**Ready for:** Production testing with missing non-critical features

---

## 🎯 OPTION A: Fast Track to Production (Recommended)

**Goal:** Get v2 production-ready in 5 days  
**Strategy:** Port only critical missing features, deploy with v1 fallback

### Day 1-3: Bot Brain Analyzer ⭐⭐⭐ CRITICAL

**Why:** Traders need to see why bot makes decisions

**Tasks:**
1. Copy `/webui/frontend/src/components/BotBrainAnalyzer/` structure
2. Convert to TypeScript in `/webui/frontend-v2/src/components/BotBrainAnalyzer/`
3. Update API calls:
   ```typescript
   // Port these API calls
   GET /api/brain-analyzer/status
   GET /api/brain-analyzer/decision-tree
   GET /api/brain-analyzer/scenario?action=X
   ```
4. Add to Sidebar navigation
5. Test with running bot instance

**Files to create:**
```
/webui/frontend-v2/src/components/BotBrainAnalyzer/
├── BotBrainAnalyzer.tsx
├── BotBrainAnalyzer.module.css
├── DecisionTree.tsx
├── ScenarioSimulator.tsx
└── types.ts
```

**Acceptance:** Can visualize current bot state and decision path

---

### Day 4-5: Enhanced Error Handling ⭐⭐⭐ CRITICAL

**Why:** Production needs robust error recovery

**Tasks:**
1. Port `EnhancedErrorBoundary` from v1:
   ```typescript
   // /webui/frontend-v2/src/components/ErrorBoundary/
   class EnhancedErrorBoundary extends React.Component {
     // Error logging to backend
     // User-friendly fallback UI
     // Auto-recovery attempts
   }
   ```

2. Add Circuit Breaker to API service:
   ```typescript
   // /webui/frontend-v2/src/services/circuitBreaker.ts
   class CircuitBreaker {
     state: 'closed' | 'open' | 'half-open';
     failureThreshold: 5;
     timeout: 30000;
   }
   ```

3. Wrap all components with error boundaries
4. Add error toast notifications
5. Test failure scenarios

**Acceptance:** UI gracefully handles backend failures

---

### Day 5: Production Deployment

1. Run full test suite
2. Deploy v2 to production port (3002)
3. Keep v1 on port 3001 as fallback
4. Add "Switch to v1" button in v2 header
5. Monitor for 24 hours

---

## 🔄 OPTION B: Full Feature Parity (7 weeks)

### Week 1-2: Critical Missing Features

| Task | Days | Priority |
|------|------|----------|
| Bot Brain Analyzer | 3 | P0 |
| Enhanced Error Handling | 2 | P0 |
| Multi-Instance Manager (Advanced) | 3 | P1 |
| Error Intelligence Dashboard | 2 | P1 |

### Week 3-4: Quality Features

| Task | Days | Priority |
|------|------|----------|
| Strategy Editor (Visual Config) | 5 | P2 |
| Performance Monitor | 2 | P2 |
| Shutdown Panel | 1 | P2 |
| Capital Protection Panel | 2 | P2 |
| Liquidation Protection | 2 | P2 |

### Week 5-6: AI & Intelligence

| Task | Days | Priority |
|------|------|----------|
| Institutional AI Panel (Real Backend) | 3 | P3 |
| Predictive Intelligence | 3 | P3 |
| Market Signal Panel | 2 | P3 |
| AI Advisor Widget | 2 | P3 |

### Week 7: Polish & Testing

| Task | Days |
|------|------|
| Documentation Viewer | 2 |
| Command Knowledge Base | 1 |
| Market News Widget | 1 |
| Comprehensive Testing | 3 |

---

## 🚀 Quick Start Commands

### Start v2 Development Server
```bash
cd /Users/ssr/Projects/WorkingBot/webui/frontend-v2
npm run dev
# Opens http://127.0.0.1:3002
```

### Start Backend (if not running)
```bash
cd /Users/ssr/Projects/WorkingBot/webui/backend
python3 app.py
# Runs on http://localhost:5555
```

### Check What's Running
```bash
lsof -i :3002  # Frontend v2
lsof -i :3001  # Frontend v1
lsof -i :5555  # Backend
```

---

## 📋 Implementation Checklist

### Before Starting Any New Component

- [ ] Check if v1 equivalent exists in `/webui/frontend/src/components/`
- [ ] Read v1 component code to understand features
- [ ] Identify API endpoints used
- [ ] Create TypeScript interfaces for data types
- [ ] Plan component structure (functional component + hooks)
- [ ] Add to `App.tsx` routing
- [ ] Add to `Sidebar.tsx` navigation

### After Completing Component

- [ ] Test with real backend API
- [ ] Test with backend offline (graceful degradation)
- [ ] Test with multiple instances
- [ ] Add error boundaries
- [ ] Document props and usage
- [ ] Update this checklist

---

## 🐛 Known Issues to Fix

### High Priority
- [ ] Guardian status returns 500 when instance stopped (add try-catch)
- [ ] Some components show "No data" unnecessarily (better loading states)
- [ ] WebSocket reconnection not always working (add retry logic)

### Medium Priority
- [ ] Instance selector doesn't remember last selection on refresh
- [ ] Config panel validation could be better
- [ ] Logs panel doesn't auto-scroll to bottom

### Low Priority
- [ ] Dark mode colors need refinement
- [ ] Some panels need better mobile responsiveness
- [ ] Add keyboard shortcuts

---

## 📖 Reference: v1 Components to Port

### P0 - Critical (Do First)
```
✅ MonitoringDashboard      → Already done
✅ GridLevelChart           → Already done  
✅ ReconciliationPanel      → Already done
✅ VolatilityChart          → Already done
✅ RiskSafetyDashboard      → Already done
❌ BotBrainAnalyzer         → PORT THIS NEXT
❌ EnhancedErrorBoundary    → PORT THIS NEXT
```

### P1 - High (Do Second)
```
❌ MultiInstanceManager     → Port advanced features
❌ ErrorIntelligenceLive    → Error pattern detection
❌ ShutdownPanel            → Graceful shutdown
```

### P2 - Medium (Do Third)
```
❌ StrategyEditor           → Visual strategy config
❌ ConfigVisualEditor       → GUI config alternative
❌ OpportunisticRecoveryPanel
❌ CapitalProtectionPanel
❌ LiquidationProtectionPanel
❌ RobustnessPanel
```

### P3 - Low (Do Last)
```
❌ InstitutionalAIPanel (Real)
❌ PredictiveIntelligence
❌ MarketSignalPanel
❌ AIAdvisorWidget
❌ DocumentationViewer
❌ CommandKnowledgeBase
❌ MarketNewsWidget
❌ CodeExplanationPanel
❌ TelegramStatusPanel
```

---

## 🎯 Success Metrics

### Phase 1-4 ✅ (Completed)
- [x] 23 components built
- [x] Instance context working
- [x] WebSocket connected
- [x] Data aggregator polling
- [x] All core trading functions work

### Fast Track Goal (5 days)
- [ ] Bot Brain Analyzer working
- [ ] Error boundaries protect all components
- [ ] Circuit breaker prevents API cascade failures
- [ ] Production deployment successful
- [ ] Zero critical bugs in 24h monitoring

### Full Parity Goal (7 weeks)
- [ ] All 42 components implemented
- [ ] 100% v1 feature coverage
- [ ] Comprehensive error handling
- [ ] Performance monitoring active
- [ ] AI features with real backends
- [ ] Full documentation

---

## 💡 Tips for Porting v1 Components

### 1. File Organization
```typescript
// v1 structure
/components/BotBrainAnalyzer.js          // Single file
/components/BotBrainAnalyzer.css

// v2 structure (better)
/components/BotBrainAnalyzer/
├── BotBrainAnalyzer.tsx                 // Main component
├── BotBrainAnalyzer.module.css          // Scoped styles
├── DecisionNode.tsx                     // Sub-component
├── ScenarioSim.tsx                      // Sub-component
├── types.ts                             // TypeScript types
└── index.ts                             // Export barrel
```

### 2. Convert Hooks Pattern
```javascript
// v1 - JavaScript hooks
const [data, setData] = useState(null);

// v2 - TypeScript hooks
const [data, setData] = useState<BrainData | null>(null);
```

### 3. API Calls Pattern
```javascript
// v1 - Direct fetch
const response = await fetch('/api/brain-analyzer/status');
const data = await response.json();

// v2 - Use typed service
import { getBrainAnalyzerStatus } from '../../services/api';
const data = await getBrainAnalyzerStatus(instance);
```

### 4. Instance Awareness
```javascript
// v1 - Used SymbolContext
const { selectedSymbol } = useSymbol();

// v2 - Use InstanceContext
const { selectedInstance } = useInstance();
const url = withInstance('/api/endpoint');  // Adds ?instance=X
```

---

## 📞 Need Help?

### Where to Look
- **Implementation Plan:** `/webui/frontend-v2/WEBUI_V2_IMPLEMENTATION_PLAN.md`
- **Status Report:** `/WEBUI_V2_STATUS_REPORT.md`
- **v1 Code Reference:** `/webui/frontend/src/components/`
- **v2 Code:** `/webui/frontend-v2/src/components/`

### Common Questions

**Q: Which API endpoint to use?**  
A: Check `/WEBUI_V2_IMPLEMENTATION_PLAN.md` Section 5 for endpoint mapping

**Q: How to add instance selector?**  
A: Use `useInstance()` hook from InstanceContext

**Q: Component not showing in sidebar?**  
A: Add to `Sidebar.tsx` sections array and `App.tsx` switch statement

**Q: API returns 404/500?**  
A: Expected when bot not running. Add try-catch and show graceful fallback

**Q: How to test with no backend?**  
A: Components should show demo/fallback data when API fails

---

*Last Updated: January 2, 2026*
