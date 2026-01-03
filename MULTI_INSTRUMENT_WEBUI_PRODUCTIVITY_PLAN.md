# Multi-Instrument WebUI Productivity Enhancement Plan
**Deep Technical Analysis & Redesign Strategy for v5.0 Multi-Symbol Trading Interface**

Date: January 1, 2026  
Analysis Type: Senior Web Development Engineer - Code-First Approach  
Status: Planning & Architecture Phase  
Priority: CRITICAL - Production Trading Requirements

---

## 🚨 PRODUCTION SAFETY NOTICE 🚨

**CRITICAL REQUIREMENT: Production v4.0 Branch & WebUI MUST remain untouched and stable**

### Production Environment v4.0 (DO NOT MODIFY - SEPARATE BRANCH)
- **Git Branch:** `production-4.0-clean` (or production branch)
- **Backend Port:** 5556 (launchagent managed - see backend_frontend.md)
- **Frontend Port:** 5555 (production build served by backend)
- **Trading Mode:** Single instrument (BTC only)
- **Config:** v4.0 single-symbol mode
- **Status:** ⚠️ LIVE TRADING - ABSOLUTELY HANDS OFF
- **Management:** LaunchAgent (`com.gridbot.webui`)
- **Purpose:** Active production trading - cannot be disrupted

### Development Environment v5.0 (Safe to Modify - CURRENT BRANCH)
- **Git Branch:** Current working branch (NOT production-4.0-clean)
- **Backend Port:** 5557 (development mode)
- **Frontend Port:** 3001 (React dev server with hot-reload)
- **Trading Mode:** Multi-symbol (BTCUSD + ETHUSD) 
- **Config:** v5.0 multi-symbol mode (config.yaml with symbols section)
- **Status:** DEVELOPMENT ONLY - Safe to experiment
- **Management:** Manual or PM2 (webui-backend-dev)
- **Purpose:** Testing v5.0 multi-symbol features

### Isolation Strategy (CRITICAL)
1. **Separate Git Branches:** Production v4.0 on `production-4.0-clean`, Development v5.0 on current branch
2. **Separate Ports:** Production uses 5555/5556, Development uses 3001/5557
3. **Separate Processes:** Production managed by launchagent, Development by PM2 or manual
4. **Zero Cross-Contamination:** Development work never touches production branch or ports
5. **Independent Configs:** Production uses v4.0 config, Development uses v5.0 multi-symbol config

### Deployment Strategy (Future)
1. **Phase 1-4:** ALL work in development branch (ports 3001/5557)
2. **Phase 5:** After comprehensive testing, CREATE NEW BRANCH for v5.0 production
3. **Production v4.0 stays alive** until v5.0 is bulletproof tested
4. **Migration:** Switch launchagent to v5.0 branch when ready (separate deployment plan)
5. **Zero downtime requirement:** Production trading never stops during development

---

## Executive Summary

After comprehensive code analysis of the entire WebUI codebase, backend APIs, and bot architecture, I have identified **critical gaps** in the current v5.0 multi-symbol implementation that prevent productive multi-instrument trading:

### Critical Requirements (User Specified)
1. **RSI Safety Layer** - Must calculate and monitor RSI for BOTH BTCUSD and ETHUSD independently
2. **Guardian Protection** - Must protect ALL instruments with separate loss limits and monitoring
3. **Individual vs Simultaneous Trading** - Clear controls to trade symbols separately or together
4. **PM2 Process Controls** - Start/stop individual instruments or all at once
5. **Symbol-Specific Configuration** - Clear, isolated config editing per instrument

### Current State Analysis

**What EXISTS ✅:**
- Backend multi-symbol API (`/api/symbols`) - Lists BTCUSD and ETHUSD
- SymbolContext (frontend) - Global symbol state management
- SymbolSelector dropdown - Visual symbol switching
- Guardian API (`/api/guardian/status`) - Running status and health
- RSI API (`/api/guardian/rsi/status`) - Current RSI calculation
- PM2 API (`/api/pm2/status`) - Process management
- ConfigPanel - General configuration editing

**What is BROKEN or MISSING ❌:**
1. **RSI is GLOBAL, not per-symbol** - Only calculates RSI for bot.symbol (v4.0 logic)
2. **Guardian monitors ONE product_id** - Not multi-symbol aware
3. **No symbol-specific start/stop** - PM2 manages `gridbot-live` (single process)
4. **Configuration API doesn't accept symbol parameter** - Edits apply to first enabled symbol only
5. **No visual separation** - Can't tell which symbol you're configuring/trading
6. **No multi-symbol process architecture** - Bot runs as single instance

**📊 Detailed Analysis:** See [COMPONENT_INVENTORY_ANALYSIS.md](COMPONENT_INVENTORY_ANALYSIS.md)
- **Frontend:** 76/94 components (81%) not multi-symbol ready
- **Backend:** 15+ APIs need symbol parameter support
- **Critical:** Bot architecture requires multi-process refactor
- **Effort:** 427-702 hours for complete implementation

---

## 📊 Week 0 Progress Update (January 1, 2026)

### ✅ Completed Tasks

1. **Production Safety - VERIFIED** ✅
   - Production backend running on port 5556 (PID varies, managed by PM2/launchagent)
   - Production frontend built and served
   - Zero impact on production trading
   - No production files modified

2. **Config Validation Fixed** ✅
   - Fixed 32 Pydantic validation errors in config.yaml
   - Removed empty string values from legacy v4.0 bot section
   - Added proper default values for all required fields
   - Config now loads successfully in development

3. **Development Backend - RUNNING** ✅
   - Created `/webui/backend/app_dev.py` (development backend launcher)
   - Fixed import issue (WEBUI_PORT not exported from app.py)
   - Development backend SUCCESSFULLY RUNNING on port 5557
   - Health endpoint verified: `{"status": "healthy"}`
   - All 39 blueprints loaded successfully
   - Git branch verified: BTEH (NOT production-4.0-clean)
   - Updated `/webui/frontend/.env.development` (points to dev backend)
   - Updated `ecosystem.gridbot.config.js` (added PM2 dev processes)

4. **Instance Lock Investigation - RESOLVED** ✅
   - Investigated `WebUIInstanceLock` in `/webui/backend/utils/instance_lock.py`
   - **DISCOVERY:** Lock is ALREADY port-based (`.webui_instance_{port}.lock`)
   - Production uses `.webui_instance_5556.lock`
   - Development uses `.webui_instance_5557.lock`
   - **RESULT:** No conflict - dev and prod can run simultaneously
   - Both backends verified running: Dev (5557) + Prod (5556)

5. **Development Environment - FULLY OPERATIONAL** ✅
   - Frontend dev server running on port 3001
   - Backend dev server running on port 5557  
   - API endpoints tested and working:
     - `/api/health` → `{"status": "healthy"}`
     - `/api/symbols` → Returns BTCUSD (enabled) + ETHUSD (disabled)
     - `/api/guardian/status` → Guardian status accessible
   - Frontend serving at http://localhost:3001
   - Backend serving at http://localhost:5557
   - Production backend SAFE on port 5556 (untouched)

### ✅ Week 0 Sprint 0.2 Status: DEVELOPMENT INFRASTRUCTURE COMPLETE

**Development Environment:**
- ✅ Dev backend running on port 5557 (PID 18466)
- ✅ Dev frontend running on port 3001  
- ✅ Prod backend running on port 5556 (verified healthy)
- ✅ Port-based instance locking (no conflicts)
- ✅ API communication tested and working
- ✅ PM2 processes configured
- ✅ Git branch isolation (BTEH vs production-4.0-clean)

**Pending Week 0 Tasks:**
- ⏳ Sprint 0.2: Code quality tools (ESLint, Prettier, testing setup)
- ⏳ Sprint 0.1: UX design artifacts (information architecture, design system, prototype)
- ⏳ Sprint 0.3: Professional standards documentation

### 📋 Next Steps

1. **Complete Sprint 0.2 Remaining Items**
   - Set up ESLint + Prettier for code quality
   - Configure Jest + React Testing Library
   - Set up pre-commit hooks (Husky)

2. **Begin Sprint 0.1: UX Design**
   - Analyze current component architecture
   - Create information architecture diagram
   - Design visual system and component library
   - Build interactive prototype

3. **Complete Sprint 0.3: Documentation**
   - Git workflow and branching strategy
   - Testing strategy and coverage requirements
   - Deployment procedures and rollback plan

4. **Update Plan Document**
   - Mark Week 0 as "In Progress - Blocked by Instance Lock"
   - Document actual timeline impact (add 1-2 days for lock fix)
   - Update estimated completion dates

---

## 🎯 Professional-Grade UX & Development Standards

### Before Writing Any Code - Design Principles

#### 1. User-Centered Design Philosophy

**Problem:** Current WebUI assumes user knows technical details (PM2 processes, config structure)  
**Solution:** Hide complexity, show only what matters for trading decisions

**Core UX Principles:**
1. **Progressive Disclosure** - Basic features prominent, advanced features hidden until needed
2. **Consistency** - Same action patterns across all symbols and components
3. **Feedback** - Every action shows immediate, clear feedback
4. **Error Prevention** - Guard rails prevent dangerous actions
5. **Forgiveness** - Easy undo/rollback for mistakes

#### 2. Information Architecture Redesign

**Current Navigation (Problematic):**
```
Dashboard → Configuration → Risk → RSI → Positions → Bot Management → Guardian → Actions → Intelligence → Logs
```
*Problem: 9 top-level items, unclear hierarchy, no symbol context*

**Proposed Navigation (User-Friendly):**
```
┌─────────────────────────────────────────────────────────────┐
│  🏠 Portfolio Overview (NEW - Landing Page)                  │
│     ├─ All Symbols Summary Cards                            │
│     ├─ Total P&L, Risk, Capital Allocation                  │
│     └─ Quick Actions: Start/Stop All, Enable/Disable        │
└─────────────────────────────────────────────────────────────┘
         │
         ├─ 📊 Symbol Dashboard (Per-Symbol Workspace)
         │     ├─ BTCUSD Tab
         │     │   ├─ Overview (Grid status, P&L, positions)
         │     │   ├─ Configuration (symbol-specific settings)
         │     │   ├─ Safety (RSI, Guardian, limits)
         │     │   ├─ Monitoring (price, health, orders)
         │     │   └─ Controls (Start/Stop, Emergency actions)
         │     │
         │     └─ ETHUSD Tab
         │         └─ (same structure)
         │
         ├─ ⚙️ System (Global Settings)
         │     ├─ PM2 Process Management
         │     ├─ API Keys & Credentials
         │     ├─ Notifications & Alerts
         │     └─ System Logs
         │
         └─ 📚 Help & Documentation
               ├─ Quick Start Guide
               ├─ Multi-Symbol Tutorial
               ├─ Troubleshooting
               └─ API Reference
```

**Benefits:**
- Clear hierarchy: Portfolio → Symbol → Details
- Reduced cognitive load: 4 top-level sections instead of 9
- Context preservation: Always know which symbol you're viewing
- Task-oriented: Grouped by what user wants to do, not technical components

#### 3. Visual Design System

**Color Coding Strategy:**
```javascript
const SYMBOL_THEMES = {
  BTCUSD: {
    primary: '#F7931A',      // Bitcoin orange
    secondary: '#FF9500',
    accent: '#FFA726',
    border: 'border-l-4 border-orange-500',
    bg: 'bg-orange-500/10',
    badge: 'bg-orange-500 text-white'
  },
  ETHUSD: {
    primary: '#627EEA',      // Ethereum blue
    secondary: '#8C9EFF',
    accent: '#7B90FF',
    border: 'border-l-4 border-blue-500',
    bg: 'bg-blue-500/10',
    badge: 'bg-blue-500 text-white'
  }
};

const STATUS_COLORS = {
  running: 'text-emerald-400',
  stopped: 'text-slate-500',
  error: 'text-rose-400',
  warning: 'text-amber-400'
};

const RISK_GRADIENT = {
  safe: 'bg-emerald-500',      // 0-30% of max loss
  caution: 'bg-amber-500',     // 30-60%
  danger: 'bg-rose-500'        // 60-100%
};
```

**Typography Hierarchy:**
```css
/* Clear information hierarchy */
.page-title     { font-size: 28px; font-weight: 700; }  /* Portfolio Overview */
.section-title  { font-size: 20px; font-weight: 600; }  /* BTCUSD Dashboard */
.card-title     { font-size: 16px; font-weight: 600; }  /* Grid Configuration */
.metric-value   { font-size: 32px; font-weight: 700; }  /* $1,234.56 */
.metric-label   { font-size: 12px; font-weight: 500; text-transform: uppercase; }
.body-text      { font-size: 14px; font-weight: 400; }
.helper-text    { font-size: 12px; font-weight: 400; color: slate-400; }
```

#### 4. Smart Defaults & Onboarding

**First-Time User Experience:**
```
1. Welcome Screen
   ├─ "Welcome to Multi-Symbol Trading" 
   ├─ Quick tour: "Let's set up your first symbol"
   └─ Skip tour (for experienced users)

2. Guided Symbol Setup
   ├─ "Choose your first symbol: BTCUSD or ETHUSD?"
   ├─ Simple form: Grid range (with smart defaults)
   ├─ Safety limits (recommended values shown)
   └─ "Review & Start Trading" confirmation

3. Dashboard Walkthrough (Interactive)
   ├─ Highlight: "This is your P&L"
   ├─ Highlight: "Click here to stop trading"
   ├─ Highlight: "Your Guardian is protecting you here"
   └─ "Got it, let me trade!" (dismisses tour)

4. Contextual Help
   ├─ ? icons next to every setting
   ├─ Tooltips on hover (explain in plain English)
   └─ "Learn more" links to detailed docs
```

**Smart Defaults:**
```javascript
const SMART_DEFAULTS = {
  BTCUSD: {
    grid: {
      reference: '88000',  // Current market price (auto-populated)
      lower: '85000',      // -3.4% (safe range)
      upper: '91000',      // +3.4%
      step: '100',         // $100 steps (balanced)
      lot_size: '25'       // $25 per order (conservative)
    },
    safety: {
      max_loss_inr: '7000',        // Recommended: 7% of capital
      rsi_threshold: '30',         // Standard oversold
      max_open_positions: '30'     // Safe starting point
    }
  }
};

// Auto-populate with explanation
"We recommend starting with $100 steps - you can adjust this later based on your risk tolerance."
```

#### 5. Error Handling & User Feedback

**Professional Error Messages:**

❌ **BAD (Current):**
```
Error: Failed to start process
```

✅ **GOOD (Professional):**
```
┌──────────────────────────────────────────────────┐
│ ⚠️  Failed to Start BTCUSD Trading               │
│                                                   │
│ Reason: Guardian process is not running          │
│                                                   │
│ What to do:                                       │
│ 1. Start Guardian first (click "Start Guardian") │
│ 2. Then start trading bot                        │
│                                                   │
│ [Start Guardian] [Cancel] [Learn More]           │
└──────────────────────────────────────────────────┘
```

**Success Feedback:**
```javascript
// Toast notifications with context
showSuccess({
  title: "BTCUSD Trading Started",
  message: "Grid bot is now monitoring 30 price levels",
  duration: 5000,
  action: {
    label: "View Dashboard",
    onClick: () => navigate('/symbol/BTCUSD')
  }
});

// Progress indicators for async actions
startTradingWithFeedback(symbol) {
  showProgress("Checking configuration...");
  await validateConfig(symbol);
  
  showProgress("Starting Guardian...");
  await startGuardian(symbol);
  
  showProgress("Initializing grid bot...");
  await startGridBot(symbol);
  
  showSuccess("BTCUSD is now trading!");
}
```

#### 6. Confirmation Dialogs for Critical Actions

**Danger Actions Require Confirmation:**
```javascript
const DANGER_ACTIONS = {
  stopAllSymbols: {
    title: "Stop All Trading?",
    message: "This will stop BTCUSD and ETHUSD trading immediately. Open positions will remain but no new orders will be placed.",
    confirmText: "Yes, Stop All Trading",
    cancelText: "Cancel",
    danger: true,
    requireTyping: false
  },
  
  deleteAllOrders: {
    title: "Cancel All Orders?",
    message: "This will cancel all pending orders across all symbols. This action cannot be undone.",
    confirmText: "Type 'CANCEL ALL' to confirm",
    cancelText: "Back to Safety",
    danger: true,
    requireTyping: "CANCEL ALL"  // Must type exact phrase
  },
  
  modifyMaxLoss: {
    title: "Change Loss Limit?",
    message: "You're changing max loss from ₹7,000 to ₹15,000 for BTCUSD. Guardian will allow more risk.",
    confirmText: "Yes, Increase Limit",
    cancelText: "Keep Current Limit",
    danger: true,
    requireTyping: false,
    warning: "Higher limits = higher risk"
  }
};
```

#### 7. Accessibility & Responsiveness

**WCAG 2.1 AA Compliance:**
- Keyboard navigation for all actions (Tab, Enter, Esc)
- Screen reader support (ARIA labels)
- Color contrast ratios ≥ 4.5:1
- Focus indicators on all interactive elements
- No critical info conveyed by color alone

**Responsive Breakpoints:**
```css
/* Desktop (1920px+) */
.portfolio-grid { grid-template-columns: repeat(4, 1fr); }

/* Laptop (1280px-1919px) */
@media (max-width: 1919px) {
  .portfolio-grid { grid-template-columns: repeat(3, 1fr); }
}

/* Tablet (768px-1279px) */
@media (max-width: 1279px) {
  .portfolio-grid { grid-template-columns: repeat(2, 1fr); }
  .sidebar { display: none; }  /* Collapse to hamburger menu */
}

/* Mobile (< 768px) */
@media (max-width: 767px) {
  .portfolio-grid { grid-template-columns: 1fr; }
  .data-table { display: none; }  /* Show cards instead */
}
```

#### 8. Performance Optimization Standards

**Loading States:**
```javascript
// Skeleton screens while loading
<SymbolCard loading>
  <Skeleton height={200} />
</SymbolCard>

// Optimistic updates
async function startTrading(symbol) {
  // Update UI immediately (optimistic)
  setSymbolStatus(symbol, 'starting');
  
  try {
    await api.startSymbol(symbol);
    setSymbolStatus(symbol, 'running');  // Confirm
  } catch (error) {
    setSymbolStatus(symbol, 'stopped');  // Revert on error
    showError("Failed to start trading");
  }
}

// Debounced search/filter
const debouncedSearch = useDebouncedCallback(
  (searchTerm) => filterSymbols(searchTerm),
  500  // 500ms delay
);
```

**Data Fetching Strategy:**
```javascript
// Stale-While-Revalidate pattern
const { data, isLoading } = useQuery({
  queryKey: ['symbol', symbol],
  queryFn: () => fetchSymbolData(symbol),
  staleTime: 5000,        // Consider fresh for 5s
  cacheTime: 300000,      // Keep in cache for 5min
  refetchInterval: 30000  // Auto-refresh every 30s
});

// Prefetch on hover
<Link 
  to={`/symbol/${symbol}`}
  onMouseEnter={() => prefetchSymbolData(symbol)}
>
  View {symbol}
</Link>
```

#### 9. Professional Development Workflow

**Code Quality Standards:**
```javascript
// ESLint + Prettier enforced
{
  "extends": ["airbnb", "prettier"],
  "rules": {
    "no-console": "warn",
    "no-unused-vars": "error",
    "react-hooks/exhaustive-deps": "error"
  }
}

// TypeScript for type safety (optional but recommended)
interface SymbolConfig {
  name: string;
  enabled: boolean;
  product_id: number;
  grid: GridGeometry;
  safety: SafetyLimits;
}

// Comprehensive testing
describe('SymbolDashboard', () => {
  it('shows correct P&L for selected symbol', () => {
    render(<SymbolDashboard symbol="BTCUSD" />);
    expect(screen.getByText('$1,234.56')).toBeInTheDocument();
  });
  
  it('prevents starting trading when Guardian is stopped', () => {
    const { getByText } = render(<SymbolControls symbol="BTCUSD" guardianRunning={false} />);
    const startButton = getByText('Start Trading');
    expect(startButton).toBeDisabled();
  });
});
```

**Git Workflow:**
```bash
# Feature branches
main (production)
├── develop (integration)
    ├── feature/symbol-portfolio-dashboard
    ├── feature/guardian-multi-symbol-ui
    └── feature/config-symbol-isolation

# Commit message standards
git commit -m "feat(dashboard): Add portfolio overview with multi-symbol cards

- Implement SymbolCard component with P&L display
- Add quick start/stop actions per symbol
- Add total portfolio metrics calculation
- Add color-coded risk indicators

Closes #123"

# Pull request template
## Description
Brief description of changes

## Testing
- [ ] Unit tests pass
- [ ] E2E tests pass
- [ ] Manual testing on dev environment
- [ ] Tested on both BTCUSD and ETHUSD

## Screenshots
[Attach before/after screenshots]

## Deployment Notes
Safe to deploy - no breaking changes
```

**Code Review Checklist:**
- [ ] Code follows style guide (ESLint passes)
- [ ] All functions have JSDoc comments
- [ ] No console.log statements in production code
- [ ] Error handling implemented for all async operations
- [ ] Loading states implemented for all data fetches
- [ ] Accessibility: keyboard navigation works
- [ ] Accessibility: ARIA labels present
- [ ] Mobile responsive (tested at 768px, 1280px, 1920px)
- [ ] Performance: No unnecessary re-renders
- [ ] Security: No sensitive data in logs or errors
- [ ] Tests: New features have test coverage
- [ ] Documentation: README updated if needed

#### 10. Monitoring & Analytics

**Production Monitoring:**
```javascript
// Error tracking (Sentry or similar)
Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: 'production',
  beforeSend(event) {
    // Don't send sensitive trading data
    if (event.request?.data?.api_key) {
      delete event.request.data.api_key;
    }
    return event;
  }
});

// Performance monitoring
import { measurePerformance } from './analytics';

measurePerformance('SymbolDashboard Load Time', async () => {
  await fetchSymbolData(symbol);
});

// User analytics (non-PII)
trackEvent('Symbol Trading Started', {
  symbol: 'BTCUSD',
  mode: 'LONG',
  grid_step: 100
});

// Real-time health checks
setInterval(() => {
  checkAPIHealth();
  checkGuardianHealth();
  checkPM2ProcessHealth();
}, 60000);  // Every minute
```

**User Activity Logging (for debugging):**
```javascript
// Non-sensitive action log
const actionLog = {
  timestamp: '2026-01-01T10:30:00Z',
  user_action: 'started_trading',
  symbol: 'BTCUSD',
  component: 'SymbolControls',
  result: 'success',
  duration_ms: 1250
};

// Helpful for support tickets: "What did user do before error?"
```

---

## Part 1: Current Code Architecture Analysis

### 1.1 Backend API Structure

#### Symbols API (`webui/backend/routes/symbols.py`)
```python
@symbols_bp.route('/api/symbols', methods=['GET'])
def list_symbols():
    # ✅ EXISTS: Returns BTCUSD and ETHUSD from config.yaml
    # ✅ Includes: enabled status, product_id, grid config, limits
    # ✅ Returns: monitoring_file, database_file paths
    
    # ❌ MISSING: No /api/symbols/<symbol>/status endpoint
    # ❌ MISSING: No /api/symbols/<symbol>/enable endpoint  
    # ❌ MISSING: No /api/symbols/<symbol>/disable endpoint
```

**Analysis:** Symbol listing works, but no individual symbol control endpoints.

#### Guardian API (`webui/backend/routes/guardian.py`)
```python
@guardian_bp.route('/api/guardian/status', methods=['GET'])
def guardian_status():
    # ✅ EXISTS: Returns Guardian health and monitoring data
    # ❌ PROBLEM: Reads single health file (.guardian_health)
    # ❌ PROBLEM: No symbol parameter accepted
    # ❌ PROBLEM: monitoring.total_loss_inr is GLOBAL, not per-symbol
    
@guardian_bp.route('/api/guardian/rsi/status', methods=['GET'])
def rsi_status():
    # ✅ EXISTS: Creates RSICollector and gets current RSI
    # ❌ PROBLEM: Uses config.bot.symbol (v4.0 single-symbol mode)
    # ❌ PROBLEM: No symbol parameter - always checks same symbol
    # ❌ CRITICAL: In v5.0, config.bot.symbol doesn't exist!
```

**Analysis:** Guardian and RSI are fundamentally **single-symbol** - they don't know about multi-symbol at all.

#### PM2 API (`webui/backend/routes/pm2.py`)
```python
@pm2_bp.route('/api/pm2/status', methods=['GET'])
def pm2_status():
    # ✅ EXISTS: Lists all PM2 processes
    # ✅ Shows: gridbot-live, guardian-live, gridbot-demo
    # ❌ MISSING: No gridbot-btcusd, gridbot-ethusd separate processes
    # ❌ PROBLEM: gridbot-live runs SINGLE bot instance
    
@pm2_bp.route('/api/pm2/start/:name', methods=['POST'])
def start_process(name):
    # ✅ EXISTS: Can start/stop processes by name
    # ❌ PROBLEM: No /api/pm2/start/symbol/<symbol> endpoint
    # ❌ PROBLEM: Starting gridbot-live starts ALL enabled symbols
```

**Analysis:** PM2 integration exists but **no per-symbol process management**.

#### Configuration API (`webui/backend/routes/yaml_config_api.py`)
```python
@yaml_config_bp.route('/api/config/all', methods=['GET'])
def get_all_config_compat():
    # ✅ EXISTS: Returns flattened config
    # ✅ FIXED: Extracts first enabled symbol (BTCUSD) for backward compat
    # ❌ PROBLEM: No ?symbol=ETHUSD parameter support
    # ❌ PROBLEM: Always returns BTCUSD config, never ETHUSD
    
# ❌ MISSING COMPLETELY:
# - GET /api/config/symbols/<symbol>
# - POST /api/config/symbols/<symbol>/save
# - GET /api/config/symbols/<symbol>/grid
```

**Analysis:** Configuration editing is **not multi-symbol aware** at all.

### 1.2 Frontend Component Analysis

#### RSIPanel (`webui/frontend/src/components/RSIPanel.js`)
```javascript
const RSIPanel = () => {
  // ✅ EXISTS: Fetches /api/guardian/rsi/status
  // ✅ Displays: Current RSI, thresholds, status (GO/STOP)
  // ❌ PROBLEM: No symbol selector - shows RSI for whatever symbol backend returns
  // ❌ PROBLEM: No "BTCUSD RSI" vs "ETHUSD RSI" indicator
  // ❌ MISSING: No side-by-side BTCUSD and ETHUSD RSI display
```

**Analysis:** RSI panel is **single-symbol only** - doesn't use SymbolContext at all.

#### GuardianPanel (`webui/frontend/src/components/GuardianPanel.js`)
```javascript
const GuardianPanel = () => {
  const { selectedSymbol } = useSymbol(); // ✅ Imports symbol context
  
  const fetchGuardianStatus = useCallback(async () => {
    // ✅ Gets selectedSymbol
    // ❌ PROBLEM: Doesn't pass symbol to API (/api/guardian/status)
    // ❌ COMMENT: "Guardian status is global, but we'll add symbol param when Phase 2C is implemented"
    const response = await api.get('/api/guardian/status');
  }, []);
  
  // ✅ Shows: Total loss INR, max loss limit, risk percentage
  // ❌ PROBLEM: No per-symbol loss breakdown
  // ❌ PROBLEM: Can't see "BTCUSD: -$200, ETHUSD: +$50"
```

**Analysis:** Guardian panel is **aware of symbols but doesn't use it** - API doesn't support per-symbol data.

#### PM2Panel (`webui/frontend/src/components/PM2Panel.js`)
```javascript
const PM2Panel = () => {
  const [activeTab, setActiveTab] = useState('live'); // 'live', 'demo', or 'all'
  
  const handleStart = async (name) => {
    // ✅ Can start specific process: gridbot-live, guardian-live
    await apiClient.startPM2Process(name);
  };
  
  // ✅ Shows: Process list with CPU, memory, uptime
  // ❌ PROBLEM: No concept of "Start BTCUSD only"
  // ❌ PROBLEM: No "Enable ETHUSD and start trading" button
  // ❌ MISSING: No filter by symbol: "Show BTCUSD processes"
```

**Analysis:** PM2 panel shows **all processes equally** - no symbol grouping or symbol-specific controls.

#### ConfigPanel (`webui/frontend/src/components/ConfigPanel.js`)
```javascript
const ConfigPanel = ({ config, meta, onUpdate, loading }) => {
  // ❌ PROBLEM: No symbol prop or symbol selector
  // ❌ PROBLEM: Doesn't use SymbolContext at all
  // ❌ PROBLEM: onUpdate() doesn't pass symbol parameter
  
  const handleSave = async () => {
    const result = await onUpdate(values);
    // ❌ PROBLEM: Saves to first enabled symbol always
  };
  
  // ✅ Has tabs: Essential, Trading, Safety, Advanced
  // ❌ MISSING: No "Symbol" tab or symbol selector at top
```

**Analysis:** Configuration panel is **completely symbol-blind** - major blocker for multi-instrument config.

#### MonitoringDashboard (`webui/frontend/src/components/MonitoringDashboard.js`)
```javascript
const MonitoringDashboard = () => {
  const api = useSymbolAPI(); // ✅ Uses symbol-aware API wrapper
  const { selectedSymbol } = useSymbol(); // ✅ Gets current symbol
  
  useEffect(() => {
    fetchMonitoringData();
  }, [selectedSymbol]); // ✅ Refetches on symbol change
  
  const fetchMonitoringData = async () => {
    // ✅ Uses api.fetchJSON (adds ?symbol=BTCUSD automatically)
    const health = await api.fetchJSON('/api/monitoring/price-health');
    // ✅ CORRECT APPROACH - this is how all components should work
  };
```

**Analysis:** Monitoring dashboard is **CORRECTLY implemented** - good reference for other components.

### 1.3 Bot Architecture Analysis

#### Current Bot Structure
```
bot/
├── gridbot.py                    # Main GridBot class
├── guardian/
│   ├── guardian.py              # Guardian daemon
│   └── collectors/
│       └── rsi_collector.py     # RSI calculation
├── strategy/
│   └── sed/                     # Single Exchange Delta strategy
└── utils/
```

**Critical Finding:** Bot is designed for **single-symbol execution**:
```python
# gridbot.py (simplified)
class GridBot:
    def __init__(self, config):
        self.symbol = config.bot.symbol      # ❌ v4.0 single-symbol
        self.product_id = config.bot.product_id
        self.grid = Grid(config.grid)
        
    def run(self):
        while True:
            self.check_grid()
            self.place_orders()
            time.sleep(self.interval)
```

**Problem:** No multi-symbol loop. Bot handles ONE symbol per process.

#### Guardian Architecture
```python
# guardian/guardian.py (simplified)
class Guardian:
    def __init__(self, config):
        self.max_loss = config.safety.max_account_loss_inr  # ❌ Global limit
        self.product_id = config.bot.product_id              # ❌ Single symbol
        
    def monitor(self):
        positions = self.get_positions(self.product_id)      # ❌ One symbol
        total_loss = sum(p.unrealized_pnl for p in positions)
        if total_loss > self.max_loss:
            self.emergency_close_all()
```

**Problem:** Guardian monitors **one product_id** - needs multi-symbol awareness.

---

## Part 2: Required Architecture Changes

### 2.1 Backend Multi-Symbol API Extensions

#### Phase 1A: Symbol Management Endpoints (NEW)
```python
# webui/backend/routes/symbols.py - ADD THESE ENDPOINTS

@symbols_bp.route('/api/symbols/<symbol>/status', methods=['GET'])
def get_symbol_status(symbol):
    """
    Get real-time status for specific symbol
    
    Returns:
        - enabled: bool
        - trading_active: bool (bot running for this symbol)
        - pm2_process: "gridbot-btcusd-live" or null
        - positions_count: int
        - unrealized_pnl: float
        - grid_status: {...}
    """
    pass

@symbols_bp.route('/api/symbols/<symbol>/enable', methods=['POST'])
def enable_symbol(symbol):
    """
    Enable symbol in config.yaml
    
    Actions:
        1. Set symbols.BTCUSD.enabled = true
        2. Save config.yaml
        3. Reload bot config (if running)
    """
    pass

@symbols_bp.route('/api/symbols/<symbol>/disable', methods=['POST'])
def disable_symbol(symbol):
    """
    Disable symbol and stop trading
    
    Actions:
        1. Stop PM2 process gridbot-{symbol}-live
        2. Set symbols.BTCUSD.enabled = false
        3. Save config.yaml
    """
    pass

@symbols_bp.route('/api/symbols/<symbol>/process/start', methods=['POST'])
def start_symbol_trading(symbol):
    """
    Start trading for specific symbol only
    
    Actions:
        1. Verify symbol enabled in config
        2. Start PM2 process: gridbot-{symbol}-live
        3. Start PM2 process: guardian-{symbol}-live
        4. Return process PIDs
    """
    pass

@symbols_bp.route('/api/symbols/<symbol>/process/stop', methods=['POST'])
def stop_symbol_trading(symbol):
    """
    Stop trading for specific symbol
    
    Actions:
        1. Stop gridbot-{symbol}-live (graceful 30s timeout)
        2. Stop guardian-{symbol}-live
        3. Keep monitoring data/logs intact
    """
    pass

@symbols_bp.route('/api/symbols/all/start', methods=['POST'])
def start_all_symbols():
    """
    Start trading for ALL enabled symbols
    
    Actions:
        for symbol in symbols where enabled=true:
            start_symbol_trading(symbol)
    """
    pass
```

#### Phase 1B: Guardian Multi-Symbol API (REFACTOR)
```python
# webui/backend/routes/guardian.py - REFACTOR EXISTING

@guardian_bp.route('/api/guardian/status', methods=['GET'])
def guardian_status():
    """
    Get Guardian status - NOW SYMBOL-AWARE
    
    Query Params:
        ?symbol=BTCUSD (optional) - Get status for specific symbol
        
    Returns (when no symbol):
        {
            "global": {
                "total_loss_inr": -1500,
                "total_capital_allocated": 10000,
                "total_positions": 18
            },
            "symbols": {
                "BTCUSD": {
                    "running": true,
                    "pid": 27759,
                    "loss_inr": -800,
                    "max_loss_inr": 7000,
                    "positions": 12,
                    "health_file": ".guardian_health_BTCUSD",
                    "last_check": 1704096000
                },
                "ETHUSD": {
                    "running": false,
                    "loss_inr": 0,
                    "positions": 0
                }
            }
        }
    
    Returns (when ?symbol=BTCUSD):
        {
            "symbol": "BTCUSD",
            "running": true,
            "health": {...}  // Existing format
        }
    """
    symbol = request.args.get('symbol')
    
    if symbol:
        # Return single-symbol data (backward compatible)
        return _get_single_symbol_guardian_status(symbol)
    else:
        # Return multi-symbol aggregate
        return _get_all_symbols_guardian_status()

@guardian_bp.route('/api/guardian/<symbol>/start', methods=['POST'])
def start_guardian_for_symbol(symbol):
    """Start Guardian for specific symbol"""
    pass

@guardian_bp.route('/api/guardian/<symbol>/stop', methods=['POST'])
def stop_guardian_for_symbol(symbol):
    """Stop Guardian for specific symbol"""
    pass
```

#### Phase 1C: RSI Multi-Symbol API (REFACTOR)
```python
# webui/backend/routes/guardian.py - REFACTOR RSI ENDPOINT

@guardian_bp.route('/api/guardian/rsi/status', methods=['GET'])
def rsi_status():
    """
    Get RSI status - NOW SYMBOL-AWARE
    
    Query Params:
        ?symbol=BTCUSD (optional) - Get RSI for specific symbol
        
    Returns (when no symbol):
        {
            "symbols": {
                "BTCUSD": {
                    "rsi": 42.5,
                    "status": "GO",
                    "threshold": 30.0,
                    "mode": "LONG"
                },
                "ETHUSD": {
                    "rsi": 68.2,
                    "status": "GO",
                    "threshold": 70.0,
                    "mode": "LONG"
                }
            }
        }
    
    Returns (when ?symbol=BTCUSD):
        {
            "symbol": "BTCUSD",
            "rsi": 42.5,
            "status": "GO",
            ...  // Existing format
        }
    """
    symbol = request.args.get('symbol')
    
    if symbol:
        # Calculate RSI for specific symbol
        return _calculate_rsi_for_symbol(symbol)
    else:
        # Calculate RSI for all enabled symbols
        return _calculate_rsi_for_all_symbols()

def _calculate_rsi_for_symbol(symbol_name):
    """Helper to calculate RSI for one symbol"""
    config = get_config()
    symbol_config = config.symbols[symbol_name]
    
    # Create symbol-specific exchange and RSI collector
    exchange = ccxt.delta({'enableRateLimit': True})
    rsi_collector = RSICollector(
        exchange=exchange,
        symbol=symbol_name,
        product_id=symbol_config.product_id,
        config=config
    )
    
    current_rsi = rsi_collector.get_latest_rsi()
    should_stop = rsi_collector.should_stop_trading()
    
    # Return symbol-specific RSI data
    return jsonify({
        'success': True,
        'symbol': symbol_name,
        'data': {
            'rsi': current_rsi,
            'status': 'STOP' if should_stop else 'GO',
            'bot_mode': symbol_config.mode,
            'threshold': symbol_config.safety.rsi.long_threshold if symbol_config.mode == 'LONG' else symbol_config.safety.rsi.short_threshold
        }
    })
```

#### Phase 1D: Configuration API Multi-Symbol (NEW)
```python
# webui/backend/routes/yaml_config_api.py - ADD SYMBOL ENDPOINTS

@yaml_config_bp.route('/api/config/symbols/<symbol>', methods=['GET'])
def get_symbol_config(symbol):
    """
    Get configuration for specific symbol
    
    Returns flattened config with GRIDBOT_* fields for this symbol only
    """
    config = get_config()
    
    if symbol not in config.symbols:
        return jsonify({'error': f'Symbol {symbol} not found'}), 404
    
    symbol_config = config.symbols[symbol]
    
    # Flatten symbol-specific config
    flat_config = {
        'GRIDBOT_SYMBOL': symbol,
        'GRIDBOT_REF': symbol_config.grid.geometry.reference,
        'GRIDBOT_LOWER': symbol_config.grid.geometry.lower,
        'GRIDBOT_UPPER': symbol_config.grid.geometry.upper,
        'GRIDBOT_STEP': symbol_config.grid.geometry.step,
        'GRIDBOT_LOT': symbol_config.grid.limits.lot_size,
        'GRIDBOT_MAX_OPEN': symbol_config.grid.limits.max_open_positions,
        'GRIDBOT_GRID_MODE': symbol_config.mode,
        # ... all other fields
    }
    
    return jsonify({'config': flat_config})

@yaml_config_bp.route('/api/config/symbols/<symbol>', methods=['POST'])
def update_symbol_config(symbol):
    """
    Update configuration for specific symbol
    
    Request Body:
        {
            "GRIDBOT_REF": "88500",
            "GRIDBOT_LOWER": "85000",
            ...
        }
    
    Actions:
        1. Validate changes
        2. Update symbols.BTCUSD.* in config.yaml
        3. Save config
        4. Reload bot (if running)
    """
    pass
```

### 2.2 Bot Architecture Multi-Symbol Refactor

#### Option A: Multi-Process Architecture (RECOMMENDED)
```
PM2 Ecosystem (Recommended):
├── gridbot-btcusd-live    # Separate bot instance for BTCUSD
├── gridbot-ethusd-live    # Separate bot instance for ETHUSD
├── guardian-btcusd-live   # Guardian monitoring BTCUSD
├── guardian-ethusd-live   # Guardian monitoring ETHUSD
└── webui-backend          # Shared WebUI backend
```

**Pros:**
- ✅ Complete isolation - BTCUSD crash doesn't affect ETHUSD
- ✅ Independent start/stop per symbol
- ✅ Separate health files (.guardian_health_BTCUSD)
- ✅ Separate databases (bot_events_BTCUSD_LONG.db)
- ✅ Easy to scale to 5+ symbols

**Implementation:**
```python
# bot/gridbot.py - MINIMAL CHANGES NEEDED
class GridBot:
    def __init__(self, config, symbol_name):  # ADD symbol_name parameter
        self.symbol_name = symbol_name
        self.symbol_config = config.symbols[symbol_name]
        
        # Use symbol-specific config
        self.product_id = self.symbol_config.product_id
        self.grid = Grid(self.symbol_config.grid)
        self.mode = self.symbol_config.mode
        
        # Symbol-specific files
        self.db_file = f"data/bot_events_{symbol_name}_{self.mode}.db"
        self.monitoring_file = f"data/monitoring_snapshot_{symbol_name}_{self.mode}.json"

# bot/main.py - UPDATED LAUNCHER
def main():
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not symbol:
        print("Usage: python -m bot.main BTCUSD")
        sys.exit(1)
    
    config = get_config()
    
    if symbol not in config.symbols:
        print(f"Symbol {symbol} not found in config")
        sys.exit(1)
    
    if not config.symbols[symbol].enabled:
        print(f"Symbol {symbol} is disabled")
        sys.exit(1)
    
    bot = GridBot(config, symbol_name=symbol)
    bot.run()

# PM2 ecosystem update
module.exports = {
  apps: [
    {
      name: 'gridbot-btcusd-live',
      script: 'python -m bot.main BTCUSD',
      cwd: '/Users/ssr/Projects/WorkingBot',
      interpreter: 'none'
    },
    {
      name: 'gridbot-ethusd-live',
      script: 'python -m bot.main ETHUSD',
      cwd: '/Users/ssr/Projects/WorkingBot',
      interpreter: 'none'
    },
    {
      name: 'guardian-btcusd-live',
      script: 'python -m bot.guardian.guardian BTCUSD',
      cwd: '/Users/ssr/Projects/WorkingBot',
      interpreter: 'none'
    },
    {
      name: 'guardian-ethusd-live',
      script: 'python -m bot.guardian.guardian ETHUSD',
      cwd: '/Users/ssr/Projects/WorkingBot',
      interpreter: 'none'
    }
  ]
};
```

#### Option B: Single-Process Multi-Threading (NOT RECOMMENDED)
```python
# Alternative: One bot process with multiple threads
class MultiSymbolGridBot:
    def __init__(self, config):
        self.threads = {}
        for symbol, symbol_config in config.symbols.items():
            if symbol_config.enabled:
                bot = GridBot(config, symbol)
                thread = threading.Thread(target=bot.run, name=f"bot-{symbol}")
                self.threads[symbol] = thread
    
    def start_all(self):
        for thread in self.threads.values():
            thread.start()
```

**Cons:**
- ❌ Can't start/stop individual symbols easily
- ❌ One crash affects all symbols
- ❌ Harder to monitor per-symbol health
- ❌ Complex shutdown logic

**Decision:** Use **Option A (Multi-Process)** for production robustness.

### 2.3 Frontend Component Refactor Requirements

#### Component Audit Matrix

| Component | Symbol Aware? | Needs Refactor? | Priority | Complexity |
|-----------|---------------|-----------------|----------|-----------|
| RSIPanel.js | ❌ No | ✅ Yes | **HIGH** | Medium |
| GuardianPanel.js | ⚠️ Partial | ✅ Yes | **HIGH** | Medium |
| PM2Panel.js | ❌ No | ✅ Yes | **HIGH** | High |
| ConfigPanel.js | ❌ No | ✅ Yes | **CRITICAL** | High |
| MonitoringDashboard.js | ✅ Yes | ❌ No | Low | - |
| PositionsPanel.js | ✅ Yes | ❌ No | Low | - |
| SymbolSelector.js | ✅ Yes | ⚠️ Polish | Medium | Low |
| TopBar.js | ✅ Yes | ❌ No | Low | - |

#### Required Component Changes

**1. RSIPanel.js - Multi-Symbol RSI Display**
```javascript
const RSIPanel = () => {
  const { selectedSymbol, symbols } = useSymbol();
  const [rsiData, setRsiData] = useState({});
  const [viewMode, setViewMode] = useState('single'); // 'single' or 'all'
  
  const fetchRSIData = async () => {
    if (viewMode === 'single') {
      // Fetch RSI for selected symbol only
      const response = await api.get(`/api/guardian/rsi/status?symbol=${selectedSymbol}`);
      setRsiData({ [selectedSymbol]: response.data });
    } else {
      // Fetch RSI for all enabled symbols
      const response = await api.get('/api/guardian/rsi/status');
      setRsiData(response.data.symbols);
    }
  };
  
  return (
    <div>
      {/* View Mode Toggle */}
      <div className="flex gap-2 mb-4">
        <button onClick={() => setViewMode('single')}>
          Current Symbol ({selectedSymbol})
        </button>
        <button onClick={() => setViewMode('all')}>
          All Symbols
        </button>
      </div>
      
      {viewMode === 'single' ? (
        <RSICard symbol={selectedSymbol} data={rsiData[selectedSymbol]} />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(rsiData).map(([symbol, data]) => (
            <RSICard key={symbol} symbol={symbol} data={data} />
          ))}
        </div>
      )}
    </div>
  );
};

const RSICard = ({ symbol, data }) => (
  <div className={`border-l-4 ${getSymbolColor(symbol).border} p-4`}>
    <div className="flex items-center justify-between mb-2">
      <h3 className="font-semibold">{symbol}</h3>
      <SymbolBadge symbol={symbol} />
    </div>
    
    <div className="text-3xl font-bold mb-1">
      {data?.rsi?.toFixed(1) || '—'}
    </div>
    
    <div className="flex items-center gap-2">
      <span className={`px-2 py-1 rounded text-sm ${
        data?.status === 'GO' ? 'bg-emerald-500/20 text-emerald-300' : 
        'bg-rose-500/20 text-rose-300'
      }`}>
        {data?.status || 'UNKNOWN'}
      </span>
      <span className="text-xs text-slate-400">
        Threshold: {data?.threshold}
      </span>
    </div>
  </div>
);
```

**2. GuardianPanel.js - Multi-Symbol Protection**
```javascript
const GuardianPanel = () => {
  const { selectedSymbol, symbols } = useSymbol();
  const [guardianStatus, setGuardianStatus] = useState({});
  const [viewMode, setViewMode] = useState('overview'); // 'overview', 'symbol', 'all'
  
  const fetchGuardianStatus = async () => {
    if (viewMode === 'symbol') {
      // Fetch for selected symbol only
      const response = await api.get(`/api/guardian/status?symbol=${selectedSymbol}`);
      setGuardianStatus({ [selectedSymbol]: response.data });
    } else {
      // Fetch global + all symbols
      const response = await api.get('/api/guardian/status');
      setGuardianStatus(response.data);
    }
  };
  
  const handleStartGuardian = async (symbol) => {
    await api.post(`/api/guardian/${symbol}/start`);
    fetchGuardianStatus();
  };
  
  const handleStopGuardian = async (symbol) => {
    await api.post(`/api/guardian/${symbol}/stop`);
    fetchGuardianStatus();
  };
  
  return (
    <div>
      {/* Global Summary */}
      {guardianStatus.global && (
        <div className="bg-slate-800 rounded-lg p-4 mb-6">
          <h3 className="text-lg font-semibold mb-2">Total Portfolio</h3>
          <div className="grid grid-cols-3 gap-4">
            <Metric 
              label="Total Loss" 
              value={formatCurrency(guardianStatus.global.total_loss_inr, 'INR')}
              color="text-rose-300"
            />
            <Metric 
              label="Capital Allocated" 
              value={formatCurrency(guardianStatus.global.total_capital_allocated, 'USD')}
            />
            <Metric 
              label="Total Positions" 
              value={guardianStatus.global.total_positions}
            />
          </div>
        </div>
      )}
      
      {/* Per-Symbol Guardian Status */}
      <div className="grid grid-cols-2 gap-4">
        {Object.entries(guardianStatus.symbols || {}).map(([symbol, data]) => (
          <GuardianSymbolCard
            key={symbol}
            symbol={symbol}
            data={data}
            onStart={() => handleStartGuardian(symbol)}
            onStop={() => handleStopGuardian(symbol)}
          />
        ))}
      </div>
    </div>
  );
};

const GuardianSymbolCard = ({ symbol, data, onStart, onStop }) => (
  <div className={`border-l-4 ${getSymbolColor(symbol).border} bg-slate-800 rounded-lg p-4`}>
    <div className="flex items-center justify-between mb-3">
      <h4 className="font-semibold">{symbol}</h4>
      <div className="flex items-center gap-2">
        <StatusDot running={data.running} />
        <span className="text-xs">
          {data.running ? `PID: ${data.pid}` : 'Stopped'}
        </span>
      </div>
    </div>
    
    {data.running && (
      <>
        <div className="space-y-2 mb-4">
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Loss</span>
            <span className="text-rose-300 font-semibold">
              {formatCurrency(data.loss_inr, 'INR')}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Max Loss</span>
            <span>{formatCurrency(data.max_loss_inr, 'INR')}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Positions</span>
            <span className="font-semibold">{data.positions}</span>
          </div>
        </div>
        
        {/* Risk Progress Bar */}
        <div className="mb-3">
          <div className="flex justify-between text-xs mb-1">
            <span>Risk</span>
            <span>{((data.loss_inr / data.max_loss_inr) * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500"
              style={{ width: `${Math.min((data.loss_inr / data.max_loss_inr) * 100, 100)}%` }}
            />
          </div>
        </div>
      </>
    )}
    
    {/* Start/Stop Button */}
    <button
      onClick={data.running ? onStop : onStart}
      className={`w-full py-2 rounded-lg font-semibold transition ${
        data.running 
          ? 'bg-rose-500/20 text-rose-300 hover:bg-rose-500/30' 
          : 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'
      }`}
    >
      {data.running ? 'Stop Guardian' : 'Start Guardian'}
    </button>
  </div>
);
```

**3. PM2Panel.js - Symbol-Grouped Process Management**
```javascript
const PM2Panel = () => {
  const [pm2Status, setPM2Status] = useState([]);
  const [groupBy, setGroupBy] = useState('symbol'); // 'symbol', 'type', 'all'
  
  const fetchPM2Status = async () => {
    const response = await apiClient.getPM2Status();
    setPM2Status(response.processes);
  };
  
  // Group processes by symbol
  const groupedProcesses = useMemo(() => {
    if (groupBy === 'symbol') {
      const groups = {};
      pm2Status.forEach(process => {
        // Extract symbol from process name: gridbot-btcusd-live -> BTCUSD
        const match = process.name.match(/(btcusd|ethusd)/i);
        const symbol = match ? match[1].toUpperCase() : 'Other';
        
        if (!groups[symbol]) groups[symbol] = [];
        groups[symbol].push(process);
      });
      return groups;
    }
    return { 'All': pm2Status };
  }, [pm2Status, groupBy]);
  
  const handleStartSymbol = async (symbol) => {
    // Start all processes for this symbol
    await Promise.all([
      apiClient.startPM2Process(`gridbot-${symbol.toLowerCase()}-live`),
      apiClient.startPM2Process(`guardian-${symbol.toLowerCase()}-live`)
    ]);
    fetchPM2Status();
  };
  
  const handleStopSymbol = async (symbol) => {
    // Stop all processes for this symbol
    await Promise.all([
      apiClient.stopPM2Process(`gridbot-${symbol.toLowerCase()}-live`),
      apiClient.stopPM2Process(`guardian-${symbol.toLowerCase()}-live`)
    ]);
    fetchPM2Status();
  };
  
  return (
    <div>
      {/* Group By Toggle */}
      <div className="flex gap-2 mb-4">
        <button onClick={() => setGroupBy('symbol')}>By Symbol</button>
        <button onClick={() => setGroupBy('type')}>By Type</button>
        <button onClick={() => setGroupBy('all')}>All</button>
      </div>
      
      {/* Symbol Groups */}
      {Object.entries(groupedProcesses).map(([symbol, processes]) => (
        <div key={symbol} className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              {symbol !== 'Other' && <SymbolBadge symbol={symbol} />}
              {symbol} Processes
            </h3>
            
            {symbol !== 'Other' && (
              <div className="flex gap-2">
                <button
                  onClick={() => handleStartSymbol(symbol)}
                  className="px-4 py-2 bg-emerald-500/20 text-emerald-300 rounded"
                >
                  Start All {symbol}
                </button>
                <button
                  onClick={() => handleStopSymbol(symbol)}
                  className="px-4 py-2 bg-rose-500/20 text-rose-300 rounded"
                >
                  Stop All {symbol}
                </button>
              </div>
            )}
          </div>
          
          {/* Process Table */}
          <table className="w-full">
            <thead>
              <tr>
                <th>Process</th>
                <th>Status</th>
                <th>PID</th>
                <th>CPU</th>
                <th>Memory</th>
                <th>Uptime</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {processes.map(process => (
                <ProcessRow key={process.name} process={process} />
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
};
```

**4. ConfigPanel.js - Symbol-Specific Configuration**
```javascript
const ConfigPanel = ({ config, meta, onUpdate, loading }) => {
  const { selectedSymbol, symbols } = useSymbol();
  const [values, setValues] = useState({});
  const [editingSymbol, setEditingSymbol] = useState(null);
  
  // Fetch config for currently selected symbol
  useEffect(() => {
    fetchSymbolConfig(selectedSymbol);
  }, [selectedSymbol]);
  
  const fetchSymbolConfig = async (symbol) => {
    const response = await fetch(`/api/config/symbols/${symbol}`);
    const data = await response.json();
    setValues(data.config);
    setEditingSymbol(symbol);
  };
  
  const handleSave = async () => {
    // Save to specific symbol endpoint
    const response = await fetch(`/api/config/symbols/${editingSymbol}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values)
    });
    
    const result = await response.json();
    
    if (result.success) {
      showNotification(`${editingSymbol} configuration saved successfully`, 'success');
    } else {
      showNotification(`Failed to save ${editingSymbol} configuration`, 'error');
    }
  };
  
  return (
    <div>
      {/* Symbol Context Header */}
      <div className="flex items-center justify-between mb-6 p-4 bg-slate-800 rounded-lg">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">Editing Configuration</h3>
          <SymbolBadge symbol={editingSymbol} size="lg" />
        </div>
        
        {/* Symbol Switcher (for config editing) */}
        <select
          value={editingSymbol}
          onChange={(e) => fetchSymbolConfig(e.target.value)}
          className="px-4 py-2 bg-slate-700 rounded"
        >
          {symbols.filter(s => s.enabled).map(s => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </select>
      </div>
      
      {/* Warning: You are editing BTCUSD */}
      <Alert severity="info" className="mb-4">
        You are editing <strong>{editingSymbol}</strong> configuration. 
        Changes will only affect this symbol.
      </Alert>
      
      {/* Existing config fields */}
      <ConfigFields values={values} onChange={setValues} />
      
      {/* Save Button */}
      <button
        onClick={handleSave}
        className="w-full py-3 bg-sky-500 text-white rounded-lg font-semibold"
      >
        Save {editingSymbol} Configuration
      </button>
    </div>
  );
};
```

---

## Part 3: Detailed Implementation Plan

### 🛡️ Development Environment Setup (Prerequisites)

**BEFORE ANY CODING - Ensure complete isolation from production**

#### Development Backend (Port 5557)
```bash
# webui/backend/app_dev.py - NEW FILE
# Copy of app.py running on port 5557 for development
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5557, debug=True)
```

#### Development Frontend (Port 3001)
```bash
# webui/frontend/.env.development
REACT_APP_API_URL=http://localhost:5557
REACT_APP_SOCKET_URL=http://localhost:5557
REACT_APP_API_BASE_URL=http://localhost:5557
PORT=3001
```

#### PM2 Separation
```javascript
// ecosystem.gridbot.config.js - ADD development processes
module.exports = {
  apps: [
    // PRODUCTION (DO NOT MODIFY)
    {
      name: 'webui-backend-prod',
      script: 'python -m webui.backend.app',
      cwd: '/Users/ssr/Projects/WorkingBot',
      port: 5556,
      env: { FLASK_ENV: 'production' }
    },
    
    // DEVELOPMENT (Safe to modify)
    {
      name: 'webui-backend-dev',  
**Environment:** Development config only (config_dev.yaml)  
**Production Impact:** ZERO - production bot continues using v4.0 config
      script: 'python -m webui.backend.app_dev',
      cwd: '/Users/ssr/Projects/WorkingBot',
      port: 5557,
      env: { FLASK_ENV: 'development' }
    },
    {
      name: 'webui-frontend-dev',
      script: 'npm start',
      cwd: '/Users/ssr/Projects/WorkingBot/webui/frontend',
      env: {
        PORT: 3001,
        REACT_APP_API_URL: 'http://localhost:5557'
      }
    }
  ]
};
```

#### Testing Checklist
- [ ] Verify production backend on 5556 still works
- [ ] Verify production frontend on 5555 still works
- [ ] Verify development backend on 5557 starts successfully
- [ ] Verify development frontend on 3001 starts successfully
- [ ] Verify production and development don't interfere with each other
- [ ] Test production WebUI continues trading during development work

---

### Phase 0: Professional Setup & Design (Week 0 - MANDATORY)

**Goal:** Establish professional development practices and finalize UX design  
**Environment:** Planning & Design Phase  
**Production Impact:** ZERO - no code changes yet

#### Sprint 0.1: UX Design & Prototyping (3 days)
- [ ] **Day 1: Information Architecture**
  - [ ] Create sitemap for new navigation structure
  - [ ] Design user flow diagrams (onboarding → trading → monitoring)
  - [ ] Validate with stakeholders
  
- [ ] **Day 2: Visual Design**
  - [ ] Create design system (colors, typography, spacing)
  - [ ] Design symbol color coding system
  - [ ] Create component library mockups (Figma/Sketch)
  - [ ] Design responsive breakpoints
  
- [ ] **Day 3: Interactive Prototype**
  - [ ] Build clickable prototype (Figma)
  - [ ] User testing session (internal)
  - [ ] Iterate based on feedback
  - [ ] Get final design approval

#### Sprint 0.2: Development Environment Setup (2 days) ✅ MOSTLY COMPLETE
- [ ] **Code Quality Tools** ⏳ PENDING
  - [ ] Set up ESLint + Prettier
  - [ ] Configure TypeScript (optional)
  - [ ] Set up pre-commit hooks (Husky)
  - [ ] Configure Jest + React Testing Library
  
- [x] **Development Infrastructure** ✅ COMPLETE
  - [x] Create development backend (port 5557) - `app_dev.py` running, PID 18466
  - [x] Create development frontend (port 3001) - React dev server running
  - [x] Set up PM2 dev processes - Added to ecosystem.gridbot.config.js
  - [x] Test production isolation - Production port 5556 verified healthy, separate git branch
  
- [ ] **Documentation Framework** ⏳ PENDING
  - [ ] Set up component documentation (Storybook)
  - [ ] Create API documentation structure
  - [ ] Set up changelog automation
  - [ ] Create contribution guidelines

#### Sprint 0.3: Professional Standards Documentation (2 days)
- [ ] **Development Guidelines**
  - [ ] Git workflow and branching strategy
  - [ ] Commit message standards
  - [ ] Pull request template
  - [ ] Code review checklist
  
- [ ] **Testing Strategy**
  - [ ] Unit test coverage requirements (80%+)
  - [ ] E2E test scenarios
  - [ ] Performance benchmarks
  - [ ] Accessibility testing checklist
  
- [ ] **Deployment Procedures**
  - [ ] Staging deployment checklist
  - [ ] Production deployment runbook
  - [ ] Rollback procedures
  - [ ] Post-deployment monitoring

---

### Phase 1: Backend Foundation (Week 1)

**Goal:** Make backend multi-symbol aware without breaking v4.0 compatibility  
**Environment:** Development only (port 5557)  
**Production Impact:** ZERO - production backend on 5556 remains unchanged  
**Quality Gate:** Code review + unit tests + API documentation

#### Sprint 1.1: Symbol Management API (2 days)
- [ ] Create `/api/symbols/<symbol>/status` endpoint
- [ ] Create `/api/symbols/<symbol>/enable` endpoint  
- [ ] Create `/api/symbols/<symbol>/disable` endpoint
- [ ] Create `/api/symbols/<symbol>/process/start` endpoint
- [ ] Create `/api/symbols/<symbol>/process/stop` endpoint
- [ ] Create `/api/symbols/all/start` endpoint
- [ ] Write unit tests for all symbol endpoints

#### Sprint 1.2: Guardian Multi-Symbol (2 days)
- [ ] Refactor `guardian.py` to accept `symbol` CLI argument
- [ ] Update `/api/guardian/status` to support `?symbol=BTCUSD` parameter
- [ ] Add aggregated `/api/guardian/status` (no param) for all symbols
- [ ] Create `/api/guardian/<symbol>/start` endpoint
- [ ] Create `/api/guardian/<symbol>/stop` endpoint
- [ ] Update Guardian to read `.guardian_health_BTCUSD` files
- [ ] Test multi-Guardian process isolation

#### Sprint 1.3: RSI Multi-Symbol (1 day)
- [ ] Refactor `RSICollector` to accept `symbol` parameter
- [ ] Update `/api/guardian/rsi/status` to support `?symbol=BTCUSD`
- [ ] Add `/api/guardian/rsi/status` (no param) for all symbols
- [ ] Test RSI calculation for BTCUSD and ETHUSD simultaneously

#### Sprint 1.4: Configuration API Multi-Symbol (2 days)
- [ ] Create `/api/config/symbols/<symbol>` GET endpoint
- [ ] Create `/api/config/symbols/<symbol>` POST endpoint
- [ ] Add validation for symbol-specific config changes
- [ ] Test saving BTCUSD config doesn't affect ETHUSD
- [ ] Add hot-reload trigger for symbol-specific config changes

### Phase 2: Bot Multi-Process Architecture (Week 2)

**Goal:** Run separate bot instances per symbol

#### Sprint 2.1: Bot Refactor (2 days)
- [ ] Update `gridbot.py` to accept `symbol` parameter
- [ ] Extract symbol config from `config.symbols[symbol]`
- [ ] Update all file paths to be symbol-specific
- [ ] Test bot runs correctly with `python -m bot.main BTCUSD`
- [ ] Test bot refuses to start if symbol disabled

#### Sprint 2.2: Guardian Refactor (1 day)
- [ ] Update `guardian.py` to accept `symbol` parameter
- [ ] Update health file path: `.guardian_health_{symbol}`
- [ ] Test Guardian monitors only specified symbol's positions
- [ ] Test multi-symbol Guardian isolation

#### Sprint 2.3: PM2 Ecosystem (2 days)
- [ ] Create `ecosystem.gridbot.config.js` with per-symbol apps
- [ ] Add `gridbot-btcusd-live` process definition
- [ ] Add `gridbot-ethusd-live` process definition
- [ ] Add `guardian-btcusd-live` process definition
- [ ] Add `guardian-ethusd-live` process definition
- [ ] Test starting individual symbol processes
- [ ] Test starting all symbols with PM2

#### Sprint 2.4: Integration Testing (2 days)
- [ ] Test BTCUSD trading independently
- [ ] Test ETHUSD trading independently
- [ ] Test both symbols trading simultaneously
- [ ] Test stopping BTCUSD doesn't affect ETHUSD
- [ ] Test Guardian per-symbol loss limits
- [ ] Test RSI per-symbol calculation
- [ ] Verify no data mixing between symbols

### Phase 3: Frontend Multi-Symbol UI (Week 3)  
**Environment:** Development frontend only (port 3001)  
**Production Impact:** ZERO - production frontend on 5555 uses production build

**Goal:** Visual clarity for multi-symbol operations

#### Sprint 3.1: RSIPanel Refactor (1 day)
- [ ] Add symbol selector / view mode toggle
- [ ] Implement single-symbol view (current)
- [ ] Implement all-symbols grid view
- [ ] Add color-coded RSI cards per symbol
- [ ] Test switching between BTCUSD and ETHUSD RSI

#### Sprint 3.2: GuardianPanel Refactor (2 days)
- [ ] Add global portfolio summary section
- [ ] Add per-symbol Guardian status cards
- [ ] Implement start/stop Guardian per symbol
- [ ] Add per-symbol risk progress bars
- [ ] Add per-symbol loss metrics
- [ ] Test starting Guardian for BTCUSD only

#### Sprint 3.3: PM2Panel Refactor (2 days)
- [ ] Add "Group by Symbol" view mode
- [ ] Implement symbol-grouped process tables
- [ ] Add "Start All BTCUSD" / "Stop All BTCUSD" buttons
- [ ] Add "Start All Symbols" master button
- [ ] Add visual indicators for process-to-symbol mapping
- [ ] Test bulk start/stop operations

#### Sprint 3.4: ConfigPanel Refactor (2 days)
- [ ] Add symbol selector at top of config panel
- [ ] Add "Editing: BTCUSD" context header
- [ ] Implement symbol-specific config fetching
- [ ] Implement symbol-specific config saving
- [ ] Add warning: "Changes only affect BTCUSD"
- [ ] Test config isolation (editing BTCUSD doesn't change ETHUSD)

#### Sprint 3.5: Symbol Context Enhancements (1 day)
- [ ] Add SymbolContextBar component (persistent header)
- [ ] Show current symbol's grid range, status, PnL
- [ ] Add color coding system for symbols
- [ ] Add SymbolBadge component
- [ ] Apply symbol colors throughout UI

### Phase 4: User Experience Polish (Week 4)

**Goal:** Make multi-symbol intuitive and safe

#### Sprint 4.1: Multi-Symbol Dashboard (2 days)
- [ ] Create SymbolPortfolio overview page
- [ ] Show all symbols in card grid
- [ ] Display per-symbol PnL, positions, status
- [ ] Add quick enable/disable toggle per symbol
- [ ] Add "View Details" link to symbol-specific view
- [ ] Add total portfolio metrics

#### Sprint 4.2: Symbol Switching UX (1 day)
- [ ] Add unsaved changes warning when switching symbols in ConfigPanel
- [ ] Implement soft data refresh (no page reload)
- [ ] Add loading state during symbol switch
- [ ] Add success notification: "Switched to ETHUSD"
- [ ] Test rapid symbol switching stability

#### Sprint 4.3: Process Management UX (2 days)
- [ ] Add "Trading Mode" selector in PM2Panel
  - Individual: Start/stop symbols separately
  - Simultaneous: Start/stop all enabled symbols
- [ ] Add confirmation dialogs for process actions
- [ ] Add process dependency warnings (e.g., "Start Guardian before GridBot")
- [ ] Add health checks before starting processes
- [ ] Test error handling for failed process starts

#### Sprint 4.4: Documentation & Help (1 day)
- [ ] Update all component help text for multi-symbol
- [ ] Add tooltips explaining symbol-specific actions
- [ ] Create multi-symbol quick start guide
- [ ] Document PM2 process naming convention
- [ ] Create troubleshooting guide for symbol-specific issues

### Phase 5: Testing & Deployment (Week 5)  
**Environment:** Staging → Production migration  
**Production Impact:** CONTROLLED - Only after comprehensive testing

#### 🚨 PRE-DEPLOYMENT SAFETY CHECKLIST
- [ ] Development system stable for 72 hours continuous operation
- [ ] All 5 requirements tested and verified
- [ ] No data mixing incidents in testing
- [ ] Production v4.0 system backed up completely
- [ ] Rollback procedure tested and documented
- [ ] Emergency shutdown procedure documented
- [ ] Production trading schedule planned (deploy during low-volume period)
- [ ] Stakeholder approval obtained

**Goal:** Production-ready multi-symbol system

#### Sprint 5.1: Integration Testing (2 days)
- [ ] E2E test: Configure BTCUSD, start trading
- [ ] E2E test: Configure ETHUSD, start trading
- [ ] E2E test: Trade both symbols simultaneously
- [ ] E2E test: Guardian stops BTCUSD on loss limit
- [ ] E2E test: RSI stops ETHUSD on oversold
- [ ] E2E test: Stop BTCUSD, ETHUSD keeps running
- [ ] E2E test: Config changes only affect target symbol

#### Sprint 5.2: Load Testing (1 day)
- [ ] **Verify production v4.0 files are backed up and unmodified**

#### Sprint 5.4: Production Deployment (1 day)

**🚨 PRODUCTION DEPLOYMENT PROTOCOL 🚨**

**Pre-Deployment:**
1. [ ] Stop all development processes (PM2 stop webui-backend-dev webui-frontend-dev)
2. [ ] Backup production files:
   ```bash
   cp -r webui/backend webui/backend.v4.0.backup
   cp -r webui/frontend/build webui/frontend/build.v4.0.backup
   cp config.yaml config.v4.0.backup.yaml
   ```
3. [ ] Verify production backup integrity
4. [ ] Document current production state (versions, configs, PM2 status)

**Deployment Steps:**
1. [ ] Choose low-volume trading window (e.g., Sunday 2AM UTC)
2. [ ] Notify users of planned maintenance
3. [ ] Stop production bot trading (graceful shutdown)
4. [ ] Build production frontend: `REACT_APP_API_URL=http://localhost:5556 npm run build`
5. [ ] Copy development backend to production: `cp -r webui/backend/* webui/backend/`
6. [ ] Copy development frontend build: `cp -r webui/frontend/build/* webui/frontend/build/`
7. [ ] Restart production WebUI: `pm2 restart webui-backend-prod`
8. [ ] Verify production WebUI loads on port 5555
9. [ ] Verify all 5 requirements working in production
10. [ ] Start production bot trading
11. [ ] Monitor first 2 hours closely (every 15 minutes)
12. [ ] Monitor first 24 hours (every 2 hours)

**Rollback Plan (if anything goes wrong):**
```bash
# EMERGENCY ROLLBACK TO v4.0
pm2 stop webui-backend-prod
rm -rf webui/backend
mv webui/backend.v4.0.backup webui/backend
rm -rf webui/frontend/build
mv webui/frontend/build.v4.0.backup webui/frontend/build
cp config.v4.0.backup.yaml config.yaml
pm2 restart webui-backend-prod
# Verify production restored in under 5 minutes
```

**Success Criteria:**
- [ ] Production WebUI accessible on port 5555
- [ ] Multi-symbol features working
- [ ] No data corruption
- [ ] No performance degradation
- [ ] Bot trading resumed successfully
- [ ] No emergency rollback needed in first 24 hourk Safety (1 day)
- [ ] Create v4.0 fallback procedure
- [ ] Test rollback from v5.0 to v4.0
- [ ] Document emergency disable multi-symbol
- [ ] Create single-symbol mode toggle
- [ ] Test backward compatibility

#### Sprint 5.4: Production Deployment (1 day)
- [ ] Deploy to staging environment
- [ ] Run 24-hour soak test
- [ ] Deploy to production
- [ ] Monitor first 2 hours closely
- [ ] Document any issues

---

## Part 4: Risk Mitigation & Constraints

### Technical Risks

#### Risk 1: Data Mixing Between Symbols
**Likelihood:** Medium  
**Impact:** CRITICAL - Could trade ETHUSD with BTCUSD config

**Mitigation:**
- Runtime validation: Every API call validates symbol parameter
- Database separation: Separate SQLite files per symbol
- File path validation: Reject paths without symbol suffix
- E2E tests: Verify complete data isolation
- Code review: All symbol-specific code paths reviewed

#### Risk 2: Process Management Complexity
**Likelihood:** High  
**Impact:** High - PM2 processes could fail to start/stop correctly

**Mitigation:**
- Dependency ordering: Start Guardian after checking bot health
- Timeout handling: 30s graceful shutdown, then force kill
- Health checks: Verify process actually started before returning success
- Atomic operations: Either all processes start or all roll back
- Monitoring: Alert if any symbol process crashes repeatedly

#### Risk 3: Configuration Corruption
**Likelihood:** Low  
**Impact:** CRITICAL - Could overwrite entire config.yaml

**Mitigation:**
- Atomic writes: Write to temp file, then atomic rename
- Validation: Schema validation before saving
- Backups: Auto-backup before each config save
- Rollback: Keep last 10 config versions
- Confirmation: Require explicit confirmation for risky changes

#### Risk 4: Guardian False Positives
**Likelihood:** Medium  
**Impact:** Medium - Could stop profitable trading unnecessarily

**Mitigation:**
- Per-symbol limits: BTCUSD: $7000 loss limit, ETHUSD: $3000
- Hysteresis: 60s cooldown before re-checking
- Manual override: Emergency bypass in WebUI
- Alerts: Telegram notification before auto-stop
- Testing: Simulate loss scenarios in staging

### User Experience Risks

#### Risk 5: User Confusion - Which Symbol Am I Editing?
**Likelihood:** HIGH  
**Impact:** High - Users edit wrong symbol config

**Mitigation:**
- Persistent symbol header: Always visible at top
- Color coding: BTCUSD=blue, ETHUSD=purple everywhere
- Confirmation dialogs: "Save BTCUSD configuration?"
- Symbol badges: Show symbol name in every card
- Breadcrumbs: "Configuration → BTCUSD → Grid Geometry"

#### Risk 6: Accidental All-Symbol Actions
**Likelihood:** Medium  
**Impact:** Medium - User stops all symbols instead of one

**Mitigation:**
- Visual distinction: "Stop BTCUSD" vs "STOP ALL SYMBOLS"
- Confirmation: "Are you sure you want to stop ALL symbols?"
- Default to individual: Require explicit "all" selection
- Undo: Allow process restart within 30s window

### Performance Constraints

#### Constraint 1: API Response Time
**Target:** < 300ms for all symbol-specific endpoints  
**Current:** ~150ms for `/api/symbols` (acceptable)

**Optimization:**
- Caching: Cache symbol status for 5s
- Parallel fetching: Fetch all symbols in parallel
- Lazy loading: Only load data for visible symbols

#### Constraint 2: PM2 Process Count
**Target:** < 20 processes total  
**Current:** 4-6 processes (2 symbols × 2 services + WebUI)

**Scale Plan:**
- 5 symbols = 15 processes (acceptable)
- 10 symbols = 30 processes (may need process pooling)

#### Constraint 3: Frontend Bundle Size
**Target:** < 3MB total bundle  
**Current:** ~2.2MB (acceptable)

**Monitoring:**
- Code splitting: Lazy load RSI/Guardian panels
- Tree shaking: Remove unused dependencies
- Compression: Enable gzip on WebUI backend

---

## Part 5: Success Metrics

### Technical Metrics

1. **Symbol Isolation:** 0 data mixing incidents in 30 days
2. **API Performance:** < 300ms response time (95th percentile)
3. **Process Stability:** < 1 unplanned process restart per week
4. **Configuration Accuracy:** 100% config saves to correct symbol
5. **Guardian Accuracy:** 0 false positive stops in 14 days

### User Experience Metrics

1. **Symbol Clarity:** Users can identify current symbol in < 2 seconds
2. **Process Control:** Start/stop individual symbol in < 3 clicks
3. **Configuration Editing:** Edit symbol config without confusion (0 support tickets)
4. **Error Recovery:** Recover from process failure in < 5 minutes
5. **Learning Curve:** New user can trade 2 symbols in < 15 minutes

### Business Metrics

1. **Multi-Symbol Adoption:** 80% of users trade 2+ symbols within 2 weeks
2. **Trading Uptime:** 99.5% uptime per symbol
3. **Capital Efficiency:** 90% of allocated capital actively trading
4. **Risk Management:** 0 guardian limit breaches undetected
5. **Support Burden:** < 2 multi-symbol issues per week

---

## Part 6: Implementation Priorities

### Must-Have (Production Blockers)

**Cannot go to production without these:**

1. ✅ **Backend Symbol API** (Sprint 1.1)
   - `/api/symbols/<symbol>/status`
   - `/api/symbols/<symbol>/process/start`
   - `/api/symbols/<symbol>/process/stop`

2. ✅ **Bot Multi-Process** (Sprint 2.1-2.3)
   - Separate bot instances per symbol
   - Separate Guardian instances per symbol
   - PM2 ecosystem configuration

3. ✅ **Guardian Multi-Symbol** (Sprint 1.2)
   - Per-symbol loss tracking
   - Per-symbol health files
   - Aggregated portfolio view

4. ✅ **Configuration API** (Sprint 1.4)
   - `/api/config/symbols/<symbol>` GET/POST
   - Symbol-specific config isolation
   - Validation & atomic saves

5. ✅ **ConfigPanel Refactor** (Sprint 3.4)
   - Symbol selector
   - Symbol-specific config editing
   - Clear visual context

6. ✅ **PM2Panel Refactor** (Sprint 3.3)
   - S**CRITICAL: Set up development environment isolation**
  - [ ] Create `webui/backend/app_dev.py` on port 5557
  - [ ] Create `webui/frontend/.env.development` pointing to port 5557
  - [ ] Add PM2 dev processes to ecosystem config
  - [ ] Test production WebUI still works on 5555/5556
  - [ ] Test development WebUI runs on 3001/5557
  - [ ] Verify complete isolation (no cross-contamination)
- [ ] ymbol-grouped process view
   - Start/stop per symbol
   - Start/stop all symbols

### Should-Have (Important UX)

**Significantly improves usability:**

7. ⭐ **RSIPanel Multi-Symbol** (Sprint 3.1)
   - Per-symbol RSI display
   - All-symbols overview
   - Color-coded status

8. ⭐ **GuardianPanel Multi-Symbol** (Sprint 3.2)
   - Per-symbol Guardian cards
   - Portfolio-level summary
   - Visual risk indicators

9. ⭐ **Symbol Context Bar** (Sprint 3.5)
   - Persistent symbol indicator
   - Quick symbol info
   - Color coding system

10. ⭐ **Symbol Portfolio Dashboard** (Sprint 4.1)
    - Multi-symbol overview
    - Quick enable/disable
    - Aggregate metrics

### Nice-to-Have (Polish)

**Enhances experience but not critical:**

11. 🎨 **Advanced Symbol Switching** (Sprint 4.2)
    - Unsaved changes warning
    - Smooth transitions
    - Smart defaults

12. 🎨 **Process Management UX** (Sprint 4.3)
    - Trading mode selector
    - Dependency checking
    - Confirmation dialogs

13. 🎨 **Documentation & Help** (Sprint 4.4)
    - Multi-symbol guide
    - Tooltips & hints
    - Troubleshooting docs

---

## Part 7: Immediate Next Steps

### This Week (Jan 1-7, 2026)

**Day 1 (Today):**
- [ ] Review this plan with stakeholders
- [ ] Confirm priorities: Must-Have vs Should-Have vs Nice-to-Have
- [ ] Set up project tracking (GitHub Projects, Notion, or Jira)
- [ ] Create detailed tickets for Sprint 1.1 (Symbol Management API)

### Week 1: Backend Foundation (Jan 8-14, 2026)

**Sprint 1.1: Symbol Management API (2 days)**
- [ ] Implement `/api/symbols/<symbol>/status` endpoint
- [ ] Implement `/api/symbols/<symbol>/enable` endpoint
- [ ] Implement `/api/symbols/<symbol>/disable` endpoint
- [ ] Write unit tests (80%+ coverage)
- [ ] Write API documentation
- [ ] Code review

**Sprint 1.2: Symbol Process Control (2 days)**
- [ ] Implement `/api/symbols/<symbol>/process/start` endpoint
- [ ] Implement `/api/symbols/<symbol>/process/stop` endpoint
- [ ] Implement `/api/symbols/all/start` endpoint
- [ ] Write unit tests
- [ ] Integration test: Start/stop BTCUSD via API
- [ ] Code review

**Sprint 1.3: Guardian Multi-Symbol (2 days)**
- [ ] Refactor guardian.py for symbol parameter
- [ ] Update `/api/guardian/status` (symbol-aware)
- [ ] Write unit tests
- [ ] Code review
- [ ] Update API documentation

**Sprint 1.4: Week 1 Integration (1 day)**
- [ ] End-to-end testing of all Week 1 endpoints
- [ ] Performance testing (< 300ms response time)
- [ ] Security review (input validation)
- [ ] Documentation review
- [ ] Sprint 1 retrospective

### Next Week (Jan 8-14, 2026)
Production isolation** - v4.0 production NEVER touched during development
- ✅ **Complete data isolation** - Never mix BTCUSD and ETHUSD data
- ✅ **Visual clarity** - User always knows which symbol they're working with
- ✅ **Robust error handling** - Process failures don't cascade
- ✅ **Backward compatibility** - Can fall back to v4.0 if needed
- ✅ **Zero downtime deployment** - Production trading never stops during migration
**Integration Testing** (2 days)

### Timeline to Production

**Aggressive Schedule (4 weeks):**
- Week 1: Backend Foundation (Sprints 1.1-1.4)
- Week 2: Bot Multi-Process (Sprints 2.1-2.4)
- Week 3: Frontend Multi-Symbol (Sprints 3.1-3.5)
- Week 4: Testing & Deployment (Sprints 5.1-5.4)

**Realistic Schedule (6 weeks):**
- Week 1-2: Backend Foundation + Testing
- Week 3-4: Bot Multi-Process + Testing
- Week 5: Frontend Multi-Symbol
- Week 6: Integration Testing + Production Deployment

**Safe Schedule (8 weeks):**
- Week 1-2: Backend Foundation
- Week 3-4: Bot Multi-Process
- Week 5-6: Frontend Multi-Symbol
- Week 7: UX Polish (Phase 4)
- Week 8: Testing & Deployment

---

## Conclusion

### Current Situation
The v5.0 multi-symbol configuration exists in `config.yaml`, but the **entire codebase is still v4.0 single-symbol**:
- Bot runs as single instance
- Guardian monitors one symbol
- RSI calculates for one symbol
- Configuration API returns first symbol only
- Frontend has symbol selector but components don't use it

### What Needs to Change
**Backend:** Symbol-aware APIs + Multi-process architecture  
**Bot:** Accept symbol parameter + Symbol-specific files  
**Frontend:** Symbol-specific component refactors  

### Recommended Approach
1. **Start with Backend** (Week 1) - API foundation must exist first
2. **Then Bot Multi-Process** (Week 2) - Allows independent symbol trading
3. **Then Frontend** (Week 3) - Visual controls for multi-symbol
4. **Test Extensively** (Week 4) - Cannot compromise trading stability

### Critical Success Factors
- ✅ **Complete data isolation** - Never mix BTCUSD and ETHUSD data
- ✅ **Visual clarity** - User always knows which symbol they're working with
- ✅ **Robust error handling** - Process failures don't cascade
- ✅ **Backward compatibility** - Can fall back to v4.0 if needed

### Estimated Effort (REVISED)
- **Phase 0 (Professional Setup):** 40 hours (1 week)
  - UX Design: 24 hours
  - Dev Environment: 8 hours
  - Standards Documentation: 8 hours
  
- **Backend Development:** 80 hours (2 weeks)
  - Symbol API: 16 hours
  - Guardian Multi-Symbol: 16 hours
  - RSI Multi-Symbol: 8 hours
  - Config API: 16 hours
  - Testing & Code Review: 24 hours
  
- **Bot Architecture:** 80 hours (2 weeks)
  - Bot Refactor: 16 hours
  - Guardian Refactor: 8 hours
  - PM2 Ecosystem: 16 hours
  - Integration Testing: 24 hours
  - Documentation: 16 hours
  
- **Frontend Development:** 120 hours (3 weeks)
  - RSI Panel: 12 hours
  - Guardian Panel: 16 hours
  - PM2 Panel: 20 hours
  - Config Panel: 20 hours
  - Portfolio Dashboard: 24 hours
  - Symbol Context System: 12 hours
  - Testing & Refinement: 16 hours
  
- **UX Polish & Accessibility:** 40 hours (1 week)
  - Onboarding Flow: 12 hours
  - Help System: 8 hours
  - Accessibility Audit: 12 hours
  - Mobile Responsive: 8 hours
  
- **Testing & Deployment:** 80 hours (2 weeks)
  - E2E Testing: 24 hours
  - Performance Testing: 16 hours
  - Staging Deployment: 8 hours
  - Production Deployment: 8 hours
  - Post-Launch Monitoring: 24 hours

**Total Effort:** 440 hours (~11 weeks at 40hr/week)

### Decision Required
1. Approve this plan with professional-grade UX standards?
2. Timeline: 10-week (Professional), 12-week (Safe), or 8-week (Risky)?
3. Approve Week 0 (Design & Setup) before any coding?
4. Which features are must-have for v1.0?
5. When do you want production deployment?
6. **CONFIRM:** Production v4.0 isolation strategy approved?
7. **CONFIRM:** Professional development standards (code review, testing, docs) approved?

---

## 🛡️ Production Protection Summary

**What stays in production v4.0:**
- Backend on port 5556 (unchanged)
- Frontend on port 5555 (unchanged)
- Single-symbol config.yaml (unchanged)
- All PM2 production processes (unchanged)
- Current bot/guardian processes (unchanged)

**What we develop in v5.0:**
- Backend on port 5557 (NEW development instance)
- Frontend on port 3001 (NEW React dev server)
- Multi-symbol config_dev.yaml (NEW development config)
- New PM2 dev processes (NEW, isolated)
- Multi-symbol bot architecture (NEW, tested in dev first)

**Migration path:**
1. Weeks 1-4: Develop v5.0 in isolation (ports 3001/5557)
2. Week 5: Test v5.0 thoroughly (72+ hours stability)
3. Week 6: Deploy to production (with rollback plan)
4. Post-deployment: Monitor 24/7 for first week

**Rollback guarantee:**
- v4.0 files backed up before deployment
- Can restore v4.0 in under 5 minutes
- Production trading never offline > 10 minutes

---

## 📋 Pre-Development Checklist

**Before writing ANY code, complete these steps:**

### Design Phase ✅
- [ ] Review and approve information architecture redesign
- [ ] Review and approve visual design system (colors, typography)
- [ ] Review and approve interactive prototype (Figma)
- [ ] Conduct user testing session (internal)
- [ ] Get stakeholder sign-off on final designs
- [ ] Document design decisions and rationale

### Development Environment ✅
- [ ] Set up development backend (port 5557)
- [ ] Set up development frontend (port 3001)
- [ ] Verify production isolation (5555/5556 untouched)
- [ ] Configure ESLint + Prettier
- [ ] Configure testing framework (Jest)
- [ ] Set up Storybook for component docs
- [ ] Test all tools working correctly

### Standards & Guidelines ✅
- [ ] Document Git workflow
- [ ] Create PR template and code review checklist
- [ ] Define testing strategy (unit, E2E, performance)
- [ ] Create deployment runbook
- [ ] Set up project tracking (Jira/GitHub Projects)
- [ ] Assign roles (developers, reviewers, testers)

### Stakeholder Alignment ✅
- [ ] Confirm timeline (10-week professional vs 8-week risky)
- [ ] Confirm must-have vs nice-to-have features
- [ ] Confirm production deployment window
- [ ] Confirm rollback procedures
- [ ] Get budget approval (if needed)
- [ ] Schedule weekly progress reviews

---

**Next Actions (IN ORDER):**

1. **THIS WEEK (Week 0):** 
   - Day 1-3: Complete UX design and prototype
   - Day 4-5: Set up development environment
   - Day 6-7: Document standards and create tickets
   
2. **NEXT WEEK (Week 1):**
   - Begin Sprint 1.1 (Symbol Management API)
   - ONLY AFTER completing Week 0 quality gates
   
3. **ONGOING:**
   - Weekly progress reviews
   - Daily standups (15 min)
   - Sprint retrospectives
   - Continuous production monitoring

**🚦 Quality Gates - Cannot proceed without:**
- ✅ Design approval
- ✅ Development environment working
- ✅ Production isolation verified
- ✅ Standards documented
- ✅ Team aligned on timeline
### Decision Required
1. Approve this plan?
2. Aggressive (4 weeks), Realistic (6 weeks), or Safe (8 weeks) timeline?
3. Which features are must-have for v1.0?
4. When do you want production deployment?

---

**Next Action:** Review plan, confirm priorities, and approve to begin Sprint 1.1 (Symbol Management API).
