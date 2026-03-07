# WebUI Component Inventory & Multi-Symbol Readiness Analysis
**Date:** January 1, 2026  
**Purpose:** Technical audit of all components for v5.0 multi-symbol implementation  
**Environment:** Development (port 5557/3001), analyzing BTEH branch  

---

## Executive Summary

**Total Components:** 94 frontend components + 39 backend blueprints  
**Multi-Symbol Ready:** 6 components (6%)  
**Partially Ready:** 12 components (13%) - Need symbol parameter  
**Not Ready:** 76 components (81%) - Single-symbol logic

**Critical Finding:** 81% of frontend UI assumes single-symbol architecture. Backend APIs need refactoring to accept symbol parameters. Bot process architecture must support multiple concurrent symbol instances.

---

## Frontend Components (94 Total)

### ✅ Multi-Symbol Ready (6 components - 6%)

1. **SymbolSelector.js** (241 lines)
   - Location: `/webui/frontend/src/components/SymbolSelector.js`
   - Status: ✅ READY
   - Features: Dropdown symbol selection, status indicators, localStorage persistence
   - API Usage: `GET /api/symbols` ✅
   - Multi-Symbol Logic: Yes - iterates over symbols array
   - Action Required: None
   
2. **SymbolContext.js** (150 lines)
   - Location: `/webui/frontend/src/context/SymbolContext.js`
   - Status: ✅ READY
   - Features: Global selectedSymbol state, symbols list, helpers (`withSymbol`, `fetchWithSymbol`)
   - API Usage: `GET /api/symbols` ✅
   - Multi-Symbol Logic: Yes - context provider for all components
   - Action Required: None
   
3. **BotStatus.js**
   - Status: ⚠️ PARTIALLY READY
   - Current: Shows symbol in header
   - Missing: Per-symbol status indicators
   - Action Required: Add symbol filter to status queries
   
4. **ConnectionStatusIndicator.js**
   - Status: ✅ READY (symbol-agnostic)
   
5. **NotificationProvider.js**
   - Status: ✅ READY (symbol-agnostic)
   
6. **LoadingSkeletons.js**
   - Status: ✅ READY (symbol-agnostic)

### ⚠️ Partially Ready (12 components - 13%)
**Need:** Add symbol parameter to API calls, use `useSymbol()` hook

7. **ConfigPanel.js** (500+ lines)
   - Location: `/webui/frontend/src/components/ConfigPanel.js`
   - Current API: `GET /api/config/all` (no symbol parameter) ❌
   - Needed API: `GET /api/config/all?symbol=BTCUSD` ✅
   - Issue: Config changes apply to first enabled symbol only
   - Fix Required:
     ```javascript
     // Before
     const response = await fetch('/api/config/all');
     
     // After
     import { useSymbol } from '../context/SymbolContext';
     const { selectedSymbol, fetchWithSymbol } = useSymbol();
     const response = await fetchWithSymbol('/api/config/all');
     ```

8. **GuardianPanel.js**
   - Current API: `GET /api/guardian/status` (no symbol) ❌
   - Needed API: `GET /api/guardian/status?symbol=BTCUSD` ✅
   - Fix: Add `useSymbol()` hook, use `fetchWithSymbol()`

9. **GuardianDashboard.js**
   - Needs: Per-symbol Guardian metrics + aggregated view
   - Backend Support: Requires `/api/guardian/all` endpoint

10. **RSIPanel.js**
    - Current API: `GET /api/guardian/rsi/status` (global RSI) ❌
    - Needed API: `GET /api/guardian/rsi/status?symbol=BTCUSD` ✅
    - Critical Issue: RSI calculation in Guardian assumes single symbol
    - Backend Fix Required: Guardian must calculate RSI per symbol

11. **PositionsPanel.js**
    - Current: Shows all positions (mixed symbols)
    - Needed: Filter positions by selected symbol
    - API Fix: `GET /api/positions?symbol=BTCUSD`

12. **PM2Panel.js**
    - Current: Start/stop `gridbot-live` (single process) ❌
    - Needed: Start/stop `gridbot-btcusd` OR `gridbot-ethusd` OR both ✅
    - Critical: Requires PM2 ecosystem refactor (separate processes per symbol)
    - API Endpoints Needed:
      - `POST /api/pm2/process/gridbot-btcusd/start`
      - `POST /api/pm2/process/gridbot-btcusd/stop`
      - `POST /api/pm2/process/gridbot-ethusd/start`
      - `POST /api/pm2/process/all/start` (start both)

13. **MonitoringPanel.js**
    - Current: Single bot monitoring snapshot
    - Needed: Per-symbol monitoring file
    - API: `GET /api/monitoring/snapshot?symbol=BTCUSD`

14. **CapitalProtectionPanel.js**
    - Current: Global loss limit
    - Needed: Per-symbol loss tracking + total portfolio loss
    - API: `GET /api/capital/status?symbol=BTCUSD`

15. **RiskSafetyDashboard.js**
    - Needed: Aggregated risk view + per-symbol breakdown
    - Complex: Must show total account risk + individual symbol risk

16. **LogsPanel.js**
    - Current: Mixed logs from all bots
    - Needed: Symbol filter
    - API: `GET /api/logs?symbol=BTCUSD&lines=100`

17. **TradingStatusPanel.js**
    - Current: Single bot trading metrics
    - Needed: Per-symbol metrics
    - API: `GET /api/trading/status?symbol=BTCUSD`

18. **BotActionsPanel.js**
    - Current: Single start/stop button
    - Needed: Per-symbol + "Start All" / "Stop All" controls
    - UI Change: Button group with symbol dropdown

### ❌ Not Multi-Symbol Compatible (76 components - 81%)

#### Configuration Components (4)
- ConfigSection.js - Single symbol config editing
- ConfigVisualEditor/index.js - Visual config (single symbol)
- ConfigChangeConfirmDialog.js - Confirmation for single symbol
- ConfigPanel_Backup_Nov2.js - Legacy backup

#### Monitoring & Health (11)
- HealthCheckDashboard.js - Single bot health
- MonitoringDashboard.js - Single bot monitoring
- MonitoringRecoveryPanel.js - Single recovery state
- UnrealizedPnLPanel.js - Single symbol P&L
- VolatilityRegimePanel.js - Single symbol volatility
- GridLevelChart.js - Single grid visualization
- VolatilityChart.js - Single symbol chart
- charts/LatencyChart.js
- charts/PnLChart.js
- charts/VolatilityChart.js
- panels/MonitoringRecoveryPanel.js

#### Bot Management (8)
- BotManagementDashboard.js - Single bot lifecycle
- BotManagerPanel.js - Single bot process
- ShutdownPanel.js - Single bot shutdown
- ReconciliationPanelV2.js - Single bot recon
- SyncReconciliationPanel.js - Single bot sync
- OpportunisticRecoveryPanel.js - Single recovery
- TmuxPanel.js - Single tmux session
- TodoListPanel.js - Single bot tasks

#### Trading & Orders (5)
- OrdersPanel.js - Hard-coded to single bot instance
- TradingModeSwitch.js - Global mode switch (needs per-symbol)
- EmergencyControlsPanel.js - Single emergency flag
- EmergencyKillButton.js - Global kill
- EmergencyToggle.js - Global toggle

#### Intelligence & Analysis (48 components)

**Bot Brain Analyzer (9 files):**
- BotBrainAnalyzer/BrainModulesList.js - Single brain
- BotBrainAnalyzer/ComprehensiveDashboard.js - Single brain
- BotBrainAnalyzer/DecisionFlowGraph.js - Single brain
- BotBrainAnalyzer/InteractiveSimulator.js - Single brain
- BotBrainAnalyzer/RealTimePredictions.js - Single brain
- BotBrainAnalyzer/RobustSimulator.js - Single brain
- BotBrainAnalyzer/SequenceTimeline.js - Single brain
- BotBrainAnalyzer/SimpleTradingSimulator.js - Single brain
- BotBrainAnalyzer/index.js

**AI & Prediction:**
- AIAdvisorWidget.js
- InstitutionalAIPanel.js
- PredictiveIntelligence/SpikePredictor.js
- MarketSignalPanel.js
- MarketNewsWidget.js

**Error Handling:**
- ErrorIntelligenceLive.js
- ErrorIntelligencePanel.js
- ErrorIntelligencePanel_simple.js
- ErrorResolutionPanel.js
- ErrorResolutionPanelSimple.js
- ErrorBoundary.js
- EnhancedErrorBoundary.js
- incidents/ErrorCard.js
- incidents/ErrorList.js
- incidents/IncidentsPanel.js
- incidents/ParamSyncDiff.js

**Strategy & Editing:**
- StrategyEditor/index.js
- CodeEditor/index.js
- CodeExplanationPanel/index.js
- FileEditor/index.js

**Documentation & Help:**
- DocumentationPanel.js
- DocumentationViewer.js
- help/HelpDrawer.js
- help/HelpIcon.js
- HelpIcon.js
- CommandKnowledgeBase.js

**System & Utilities:**
- RobustnessPanel.js
- LiquidationProtectionPanel.js
- TelegramStatusPanel.js
- SafetyWarningBanner.js
- IntegrationExample.js
- TailscaleMobileOptimizer.js
- MobileBatteryIndicator.js
- IdleIndicator.js
- EnhancedNotificationSystem.js
- EnhancedTooltip.js
- ConfirmationDialog.js
- BackendDownError.js

**Layout & Common:**
- layout/FloatingActionBar.js
- layout/Sidebar.js
- layout/TopBar.js
- common/CollapsibleCard.js
- common/ErrorStates.js
- common/ToastProvider.js
- panels/index.js

---

## Backend API Analysis (39 Blueprints)

### ✅ Multi-Symbol Ready (3 endpoints)

1. **`GET /api/symbols`** (Blueprint: symbols)
   - Status: ✅ READY
   - Returns: All configured symbols from config.yaml v5.0
   - Response:
     ```json
     {
       "config_version": "5.0",
       "symbols": [
         {"name": "BTCUSD", "enabled": true, "product_id": 139, ...},
         {"name": "ETHUSD", "enabled": false, "product_id": 3136, ...}
       ],
       "total": 2,
       "enabled_count": 1
     }
     ```

2. **`GET /api/health`** (Blueprint: system_health)
   - Status: ✅ READY (symbol-agnostic)
   - Returns: `{"status": "healthy", "timestamp": "..."}`

3. **`GET /api/system/status`** (Blueprint: system)
   - Status: ✅ READY (system-wide metrics)

### ⚠️ Needs Symbol Parameter (15+ critical endpoints)

4. **`GET /api/config/all`** (Blueprint: yaml_config)
   - Current: Returns config for first enabled symbol ❌
   - Needed: `GET /api/config/all?symbol=BTCUSD` ✅
   - Backend Fix: Accept `symbol` query parameter, return symbol-specific config
   
5. **`POST /api/config/update`** (Blueprint: yaml_config)
   - Current: Updates config without symbol context ❌
   - Needed: Accept `symbol` in request body ✅
   - Backend Fix:
     ```python
     @app.route('/api/config/update', methods=['POST'])
     def update_config():
         data = request.json
         symbol = data.get('symbol')  # NEW
         updates = data.get('updates')
         # Update config.yaml symbols array for specific symbol
     ```

6. **`GET /api/guardian/status`** (Blueprint: guardian)
   - Current: Returns status for `cfg.bot.product_id` (single symbol) ❌
   - Needed: `GET /api/guardian/status?symbol=BTCUSD` ✅
   - Critical Issue: Guardian class monitors ONE product_id
   - Backend Fix: Refactor Guardian to support multiple concurrent symbols

7. **`GET /api/guardian/rsi/status`** (Blueprint: guardian)
   - Current: Returns RSI for `cfg.bot.symbol` ❌
   - Needed: `GET /api/guardian/rsi/status?symbol=BTCUSD` ✅
   - Critical Issue: RSI calculated globally, not per-symbol
   - Backend Fix: Calculate RSI per symbol, store in separate state

8. **`POST /api/guardian/start`** (Blueprint: guardian)
   - Needed: `POST /api/guardian/start` with `{"symbol": "BTCUSD"}` in body

9. **`POST /api/guardian/stop`** (Blueprint: guardian)
   - Needed: `POST /api/guardian/stop` with `{"symbol": "BTCUSD"}` in body

10. **`GET /api/positions`** (Blueprint: positions)
    - Needed: `GET /api/positions?symbol=BTCUSD`

11. **`GET /api/orders`** (Blueprint: orders)
    - Needed: `GET /api/orders?symbol=BTCUSD`

12. **`GET /api/pnl`** (Blueprint: pnl)
    - Needed: `GET /api/pnl?symbol=BTCUSD` (per-symbol) + `GET /api/pnl` (total)

13. **`GET /api/monitoring/snapshot`** (Blueprint: monitoring)
    - Needed: `GET /api/monitoring/snapshot?symbol=BTCUSD`
    - Reads: `data/monitoring_snapshot_{symbol}_{mode}.json`

14. **`POST /api/bot/start`** (Blueprint: bot_control)
    - Current: Starts single `gridbot-live` process ❌
    - Needed: `POST /api/bot/start` with `{"symbol": "BTCUSD"}` ✅
    - PM2 Command: `pm2 start gridbot-btcusd`

15. **`POST /api/bot/stop`** (Blueprint: bot_control)
    - Needed: `POST /api/bot/stop` with `{"symbol": "BTCUSD"}`
    - PM2 Command: `pm2 stop gridbot-btcusd`

16. **`GET /api/bot/status`** (Blueprint: bot_control)
    - Current: Returns status for single bot ❌
    - Needed: `GET /api/bot/status?symbol=BTCUSD` OR `GET /api/bot/status` (all) ✅

17. **`GET /api/logs`** (Blueprint: logs)
    - Needed: `GET /api/logs?symbol=BTCUSD&lines=100`

18. **`GET /api/metrics`** (Blueprint: metrics)
    - Needed: Per-symbol metrics + aggregated portfolio metrics

### Blueprint Inventory (39 total)
1. yaml_config - Config management
2. utility - Utility endpoints
3. logs - Log retrieval
4. docs - Documentation
5. metrics - Metrics tracking
6. websocket_api - WebSocket events
7. system - System status
8. monitor - Health monitoring
9. guardian - Guardian protection
10. pm2 - Process management
11. orders - Order management
12. pnl - P&L calculations
13. positions - Position tracking
14. bot_control - Bot lifecycle
15. todos - Task management
16. risk - Risk assessment
17. capital - Capital management
18. recon - Reconciliation
19. robustness - Robustness checks
20. emergency - Emergency controls
21. ai - AI advisor
22. liquidation - Liquidation protection
23. strategy - Strategy management
24. dynamic_brain - Bot brain API
25. prediction - Prediction models
26. grid_mode - Grid mode switching
27. monitoring - Monitoring snapshots
28. unified_safety - Safety layer
29. brain_analyzer - Brain analysis
30. file_manager - File operations
31. mode_switcher - Mode switching
32. system_health - Health checks
33. instance_manager - Instance control
34. code_explainer - Code explanation
35. recovery - Recovery procedures
36. reconciliation - Reconciliation v2
37. symbols - Symbol management ✅
38. position_liquidation - Liquidation (Delta India)
39. (various utility blueprints)

---

## Bot Architecture Analysis

### Current Architecture (Single Process) ❌

```
PM2 Process: gridbot-live
  ├─ Runs: grid_bot.py --symbol BTCUSD --mode LONG
  ├─ Monitors: BTCUSD only
  ├─ Guardian: Protects BTCUSD only
  ├─ RSI: Calculates for BTCUSD only
  └─ Recovery: Monitors BTCUSD recovery state
```

**Problem:** Can only trade one symbol at a time

### Needed Architecture (Multi-Process) ✅

```
PM2 Ecosystem:
  ├─ gridbot-btcusd
  │   ├─ Runs: grid_bot.py --symbol BTCUSD --mode LONG
  │   ├─ Database: bot_events_BTCUSD_LONG.db
  │   ├─ Monitoring: monitoring_snapshot_BTCUSD_LONG.json
  │   └─ Recovery: recovery_state_BTCUSD_LONG.json
  │
  ├─ gridbot-ethusd
  │   ├─ Runs: grid_bot.py --symbol ETHUSD --mode LONG
  │   ├─ Database: bot_events_ETHUSD_LONG.db
  │   ├─ Monitoring: monitoring_snapshot_ETHUSD_LONG.json
  │   └─ Recovery: recovery_state_ETHUSD_LONG.json
  │
  ├─ guardian-btcusd (separate process)
  │   └─ Monitors: BTCUSD positions, RSI, loss limits
  │
  └─ guardian-ethusd (separate process)
      └─ Monitors: ETHUSD positions, RSI, loss limits
```

**Benefit:** Independent symbol trading + per-symbol protection

### PM2 Ecosystem Refactor Required

**Current `ecosystem.gridbot.config.js`:**
```javascript
{
  apps: [
    {
      name: "gridbot-live",
      script: "grid_bot.py",
      args: "--symbol BTCUSD --mode LONG",
      // ...
    }
  ]
}
```

**Needed:**
```javascript
{
  apps: [
    // BTCUSD Bot
    {
      name: "gridbot-btcusd",
      script: "grid_bot.py",
      args: "--symbol BTCUSD --mode LONG",
      env: {
        SYMBOL: "BTCUSD"
      }
    },
    
    // ETHUSD Bot
    {
      name: "gridbot-ethusd",
      script: "grid_bot.py",
      args: "--symbol ETHUSD --mode LONG",
      env: {
        SYMBOL: "ETHUSD"
      }
    },
    
    // BTCUSD Guardian
    {
      name: "guardian-btcusd",
      script: "guardian.py",
      args: "--symbol BTCUSD --mode LONG",
      env: {
        SYMBOL: "BTCUSD"
      }
    },
    
    // ETHUSD Guardian
    {
      name: "guardian-ethusd",
      script: "guardian.py",
      args: "--symbol ETHUSD --mode LONG",
      env: {
        SYMBOL: "ETHUSD"
      }
    }
  ]
}
```

---

## Configuration System Analysis

### ✅ Config Structure (v5.0) - READY

```yaml
config_version: "5.0"

symbols:
  - name: BTCUSD
    enabled: true
    product_id: 139
    mode: LONG
    grid:
      lower: "85000"
      reference: "88500"
      upper: "95000"
      step: "500"
    limits:
      lot_size: "5"
      max_open_positions: "50"
      max_qty_per_order: "2"
    safety:
      max_account_loss_inr: "10000"
      min_liquidation_distance_pct: 10.0
    database_file: "data/bot_events_BTCUSD_LONG.db"
    monitoring_file: "data/monitoring_snapshot_BTCUSD_LONG.json"
    recovery_file: "data/recovery/recovery_state_BTCUSD_LONG.json"
  
  - name: ETHUSD
    enabled: false
    product_id: 3136
    mode: LONG
    grid:
      lower: "3200"
      reference: "3500"
      upper: "3800"
      step: "50"
    limits:
      lot_size: "10"
      max_open_positions: "30"
      max_qty_per_order: "3"
    safety:
      max_account_loss_inr: "5000"
      min_liquidation_distance_pct: 10.0
    database_file: "data/bot_events_ETHUSD_LONG.db"
    monitoring_file: "data/monitoring_snapshot_ETHUSD_LONG.json"
    recovery_file: "data/recovery/recovery_state_ETHUSD_LONG.json"

# Legacy v4.0 bot section (commented out)
# bot:
#   symbol: "BTCUSD"
#   product_id: 139
#   ...
```

### ❌ Config Loading Issues

**Problem:** Backend loads config correctly, but most code still uses v4.0 patterns

**v4.0 Pattern (BROKEN for multi-symbol):**
```python
# In guardian.py, grid_bot.py, etc.
symbol = cfg.bot.symbol  # Returns "BTCUSD" - single value ❌
product_id = cfg.bot.product_id  # Returns 139 - single value ❌
```

**v5.0 Pattern (CORRECT):**
```python
# Should iterate over symbols
for symbol_config in cfg.symbols:
    if symbol_config.enabled:
        symbol = symbol_config.name
        product_id = symbol_config.product_id
        # Process each symbol independently
```

**Backend Modules Still Using v4.0 Pattern:**
- `guardian.py` - Uses `cfg.bot.product_id`
- `grid_bot.py` - Uses `cfg.bot.symbol`
- RSI calculation - Uses `cfg.bot.symbol`
- Recovery module - Uses single monitoring file
- Most API blueprints - Reference `cfg.bot.*`

---

## Database & State Management

### ✅ File Naming (Per-Symbol Pattern) - READY

```
data/
├── bot_events_BTCUSD_LONG.db           ✅ Symbol in filename
├── bot_events_ETHUSD_LONG.db           ✅ Symbol in filename
├── monitoring_snapshot_BTCUSD_LONG.json ✅ Symbol in filename
├── monitoring_snapshot_ETHUSD_LONG.json ✅ Symbol in filename
└── recovery/
    ├── recovery_state_BTCUSD_LONG.json  ✅ Symbol in filename
    └── recovery_state_ETHUSD_LONG.json  ✅ Symbol in filename
```

**Good:** File naming convention already supports multi-symbol

### ❌ Database Access Issues

**Problem:** Backend doesn't load both databases simultaneously

**Current (v4.0):**
```python
db_path = cfg.bot.database_file  # Single database
conn = sqlite3.connect(db_path)
```

**Needed (v5.0):**
```python
# Load all enabled symbol databases
db_connections = {}
for symbol_config in cfg.symbols:
    if symbol_config.enabled:
        db_path = symbol_config.database_file
        db_connections[symbol_config.name] = sqlite3.connect(db_path)

# Query specific symbol
btc_conn = db_connections['BTCUSD']
btc_positions = fetch_positions(btc_conn)
```

---

## Critical Gaps Summary

### Frontend (81% Not Ready)
1. **76 components (81%) hardcoded to single symbol**
   - Need: Add `useSymbol()` hook
   - Need: Use `fetchWithSymbol()` for API calls
   - Effort: 2-4 hours per component (152-304 hours total)

2. **12 components (13%) partially ready**
   - Need: Add symbol parameter to existing API calls
   - Effort: 1-2 hours per component (12-24 hours total)

### Backend (Major Refactor Required)
1. **15+ APIs need symbol parameter**
   - Effort: 1-2 hours per endpoint (15-30 hours)

2. **Guardian refactor critical**
   - Must support multiple concurrent symbols
   - Must calculate RSI per symbol
   - Effort: 8-16 hours

3. **Bot architecture refactor**
   - Must support multi-process (one per symbol)
   - PM2 ecosystem config refactor
   - Effort: 16-24 hours

### Configuration
1. **Code migration from cfg.bot.* to cfg.symbols[]**
   - Affects: 10+ Python modules
   - Effort: 8-12 hours

### Testing
1. **All refactored components need tests**
   - Unit tests: 80+ hours
   - E2E tests: 40+ hours
   - Integration tests: 20+ hours

---

## Total Effort Estimate

| Category | Components | Hours (Conservative) |
|----------|-----------|---------------------|
| Frontend - Full Refactor | 76 | 228-456 |
| Frontend - Partial Refactor | 12 | 12-24 |
| Backend APIs | 15+ | 15-30 |
| Guardian Refactor | 1 | 8-16 |
| Bot Architecture | 1 | 16-24 |
| Config Migration | 10+ modules | 8-12 |
| Testing | All | 140+ |
| **TOTAL** | **115+** | **427-702 hours** |

**Timeline:** 10-17 weeks (1 developer, 40 hrs/week)  
**Recommended:** 10-week timeline with professional practices (testing, code review, documentation)

---

## Conclusion

The v5.0 multi-symbol implementation requires:
1. **Systematic refactoring** of 88 components (76 full + 12 partial)
2. **Backend API redesign** to accept symbol parameters
3. **Bot architecture change** from single-process to multi-process
4. **Guardian refactor** to monitor multiple symbols concurrently
5. **Comprehensive testing** at every stage

**Critical Success Factor:** Complete Week 0 (design, setup, standards) before Phase 1 development to ensure professional-grade implementation.
