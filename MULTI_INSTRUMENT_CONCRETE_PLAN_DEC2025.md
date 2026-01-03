# Multi-Instrument Trading Platform: Complete Redesign Plan

**Date:** December 27, 2025  
**Updated:** January 1, 2026 - V2.0 Phase 1-5 COMPLETE  
**Status:** ✅ V2.0 CORE INFRASTRUCTURE COMPLETE  
**Author:** Analysis from comprehensive codebase review

---

# 🚨 CRITICAL INSIGHT: Instance-Centric Architecture Required

The previous implementation was **symbol-centric** but true multi-instrument trading requires **instance-centric** thinking:

**Instance = Symbol + Mode** (e.g., `BTCUSD_LONG`, `BTCUSD_SHORT`, `ETHUSD_LONG`)

This allows:
- Same symbol trading in LONG and SHORT simultaneously
- Independent configuration per instance
- Separate databases per instance
- Opposite RSI thresholds (LONG stops at overbought, SHORT stops at oversold)

---

# ✅ V2.0 IMPLEMENTATION STATUS

## Phase 0: Architecture Decision ✅
**Status:** ✅ COMPLETE

**Decision:** Use **Instance Model** where each instance = `{symbol}_{mode}`

## Phase 1: Config YAML Restructure ✅
**Status:** ✅ COMPLETE (January 1, 2026)

### Completed:
- ✅ Added `InstanceConfig` model to `config/models.py`
- ✅ Added `InstanceRSIConfig` with mode-appropriate defaults
- ✅ Added `instances` section to `RootConfig`
- ✅ Added validation for instance name format (`SYMBOL_MODE`)
- ✅ Updated `config.yaml` to v6.0 with instances section
- ✅ Added helper functions to `config/loader.py`:
  - `get_instance_config(name)` - Get config for specific instance
  - `get_all_instances(enabled_only)` - Get all configured instances
  - `get_instances_for_symbol(symbol)` - Get instances for a symbol
  - `parse_instance_name(name)` - Parse symbol and mode from instance name
  - `make_instance_name(symbol, mode)` - Create instance name

## Phase 2: CLI Arguments ✅
**Status:** ✅ COMPLETE (January 1, 2026)

### Completed:
- ✅ Updated `bot/run.py` with `--instance BTCUSD_LONG` argument
- ✅ Updated `start_guardian.py` with `--instance` argument
- ✅ Maintained backward compatibility with `--symbol` (legacy)

## Phase 3: Instance-Aware Databases ✅
**Status:** ✅ COMPLETE (January 1, 2026)

### Completed:
- ✅ Updated `AsyncGridBot.__init__` to accept `instance_name`
- ✅ Database naming: `data/bot_events_{instance_name}.db`
- ✅ Each instance (BTCUSD_LONG, BTCUSD_SHORT) gets separate database

## Phase 4: PM2 Ecosystem ✅
**Status:** ✅ COMPLETE (January 1, 2026)

### Completed:
- ✅ Updated `ecosystem.multi-symbol.config.js` for v6.0
- ✅ Added processes: `gridbot-btcusd-long`, `gridbot-btcusd-short`, `gridbot-ethusd-long`
- ✅ Added guardians: `guardian-btcusd-long`, `guardian-btcusd-short`, `guardian-ethusd-long`

## Phase 5: Backend API ✅
**Status:** ✅ COMPLETE (January 1, 2026)

### Completed:
- ✅ Added `GET /api/instances` endpoint
- ✅ Updated `GET /api/symbols` for v6.0 compatibility
- ✅ Added `is_v6` flag for frontend detection

---

# 📋 REMAINING PHASES

## Phase 6: Frontend Instance Selector
**Duration:** 4-6 hours | **Priority:** HIGH

### TODO:
- [ ] Create `InstanceContext.js` (or update SymbolContext)
- [ ] Add instance dropdown in header
- [ ] Update all API calls to use `?instance=BTCUSD_LONG`
- [ ] Add instance status badges (LONG/SHORT indicators)

## Phase 7: RSI Guardian Integration
**Duration:** 4-6 hours | **Priority:** HIGH

### TODO:
- [ ] Update Guardian to read instance-specific RSI thresholds
- [ ] LONG mode: Stop at RSI <= 30 (oversold)
- [ ] SHORT mode: Stop at RSI >= 70 (overbought)
- [ ] Test RSI logic for both modes

## Phase 8: End-to-End Testing
**Duration:** 4-6 hours | **Priority:** CRITICAL

### TODO:
- [ ] Test BTCUSD_LONG instance startup
- [ ] Test BTCUSD_SHORT instance startup (disabled)
- [ ] Verify separate databases created
- [ ] Verify PM2 process management
- [ ] Verify frontend instance switching

---

# 📋 V1.0 ARCHIVED (Symbol-Centric - DEPRECATED)

The following phases were completed for V1.0 but are now superseded by V2.0:
      limits:
        max_open_positions: 30
        lot_size: 3
    safety:
      max_account_loss_inr: 5000
      rsi_stop_threshold: 30      # SHORT: Stop when oversold
      rsi_resume_threshold: 35
      min_liquidation_distance_pct: 10.0
      
  ETHUSD_LONG:
    symbol: ETHUSD
    mode: LONG
    product_id: 3136
    enabled: false
    grid: ...
    safety: ...
```

### 1.2 Update Config Loader
**File:** `config/loader.py`, `config/models.py`

| Task | Description |
|------|-------------|
| Add `InstanceConfig` model | New Pydantic model for instance config |
| Update `RootConfig` | Add `instances: Dict[str, InstanceConfig]` |
| Add `get_instance_config(name)` | Helper to get specific instance config |
| Keep backward compatibility | Still support `symbols` section for migration |

### 1.3 Migration Script
**New File:** `scripts/migrate_config_v5_to_v6.py`

- Read existing `symbols` section
- Generate `instances` section (symbol_mode format)
- Preserve all existing values
- Add instance-specific RSI thresholds

---

## Phase 2: Bot CLI Enhancement ⏳
**Duration:** 3-4 hours | **Priority:** HIGH

### 2.1 Add --mode Argument
**File:** `bot/run.py`

**Current:**
```bash
python3 -m bot.run --symbol BTCUSD
```

**New:**
```bash
python3 -m bot.run --instance BTCUSD_LONG
# OR (backward compatible)
python3 -m bot.run --symbol BTCUSD --mode LONG
```

### 2.2 Update AsyncGridBot
**File:** `bot/strategy/async_gridbot.py`

| Task | Description |
|------|-------------|
| Accept `instance_name` parameter | Primary identifier for v6.0 |
| Parse instance to symbol+mode | Extract from `BTCUSD_LONG` format |
| Load from `config.instances[name]` | Use new config structure |
| Database naming | `bot_events_BTCUSD_LONG.db` |

### 2.3 Update Guardian Bot
**File:** `bot/guardian/core/guardian_bot.py`

```bash
python3 start_guardian.py --instance BTCUSD_LONG
```

| Task | Description |
|------|-------------|
| Accept `instance_name` parameter | Match bot naming |
| Load instance-specific thresholds | RSI differs for LONG vs SHORT |
| Instance-specific health file | `.guardian_health_BTCUSD_LONG` |

---

## Phase 3: Database Isolation ⏳
**Duration:** 2-3 hours | **Priority:** HIGH

### 3.1 Verify Database Naming
**File:** `bot/strategy/async_gridbot.py`

Already implemented:
```python
db_name = f"data/bot_events_{self.symbol_name}_{self.mode}.db"
```

### 3.2 Update EventStore Queries
**File:** `bot/strategy/modules/event_store.py`

| Task | Description |
|------|-------------|
| Add instance_id to events | Tag all events with instance name |
| Query by instance | Filter positions/orders by instance |

### 3.3 Clean Up Old Databases
**Current state:**
```
bot_events_LONG.db        # OLD - single mode
bot_events_None.db        # ERROR case
```

**Target state:**
```
bot_events_BTCUSD_LONG.db
bot_events_BTCUSD_SHORT.db
bot_events_ETHUSD_LONG.db
```

---

## Phase 4: PM2 Multi-Instance Config ⏳
**Duration:** 2-3 hours | **Priority:** HIGH

### 4.1 Update ecosystem.multi-symbol.config.js
**File:** `ecosystem.multi-symbol.config.js`

```javascript
module.exports = {
  apps: [
    // ============ BTCUSD LONG ============
    {
      name: 'gridbot-BTCUSD-LONG-live',
      script: 'python3',
      args: '-m bot.run --instance BTCUSD_LONG',
      cwd: '/Users/ssr/Projects/WorkingBot',
      autorestart: true,
      env: { PYTHONPATH: '.', TRADING_MODE: 'live' },
      error_file: 'logs/gridbot-BTCUSD-LONG-error.log',
      out_file: 'logs/gridbot-BTCUSD-LONG-out.log'
    },
    {
      name: 'guardian-BTCUSD-LONG-live',
      script: 'python3',
      args: 'start_guardian.py --instance BTCUSD_LONG',
      autorestart: true
    },
    
    // ============ BTCUSD SHORT ============
    {
      name: 'gridbot-BTCUSD-SHORT-live',
      script: 'python3',
      args: '-m bot.run --instance BTCUSD_SHORT',
      autorestart: false  // Disabled by default
    },
    {
      name: 'guardian-BTCUSD-SHORT-live',
      script: 'python3',
      args: 'start_guardian.py --instance BTCUSD_SHORT',
      autorestart: false
    },
    
    // ============ ETHUSD LONG ============
    {
      name: 'gridbot-ETHUSD-LONG-live',
      script: 'python3',
      args: '-m bot.run --instance ETHUSD_LONG',
      autorestart: false
    },
    {
      name: 'guardian-ETHUSD-LONG-live',
      script: 'python3',
      args: 'start_guardian.py --instance ETHUSD_LONG',
      autorestart: false
    }
  ]
};
```

### 4.2 PM2 Naming Convention
```
gridbot-{SYMBOL}-{MODE}-{ENVIRONMENT}
guardian-{SYMBOL}-{MODE}-{ENVIRONMENT}

Examples:
- gridbot-BTCUSD-LONG-live
- gridbot-BTCUSD-SHORT-live
- guardian-ETHUSD-LONG-live
```

---

## Phase 5: Backend API Updates ⏳
**Duration:** 6-8 hours | **Priority:** HIGH

### 5.1 New Instance Endpoints
**File:** `webui/backend/routes/instances.py` (NEW)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/instances` | GET | List all instances with status |
| `/api/instances/{name}` | GET | Get specific instance details |
| `/api/instances/{name}/config` | GET/POST | Instance config CRUD |
| `/api/instances/{name}/start` | POST | Start instance (bot + guardian) |
| `/api/instances/{name}/stop` | POST | Stop instance |
| `/api/instances/{name}/positions` | GET | Instance positions |
| `/api/instances/{name}/status` | GET | Instance health status |

### 5.2 Response Format
```json
GET /api/instances
{
  "success": true,
  "instances": [
    {
      "name": "BTCUSD_LONG",
      "symbol": "BTCUSD",
      "mode": "LONG",
      "enabled": true,
      "status": "running",
      "pnl": 234.50,
      "positions": 5,
      "gridbot_pid": 12345,
      "guardian_pid": 12346
    },
    {
      "name": "BTCUSD_SHORT",
      "symbol": "BTCUSD",
      "mode": "SHORT",
      "enabled": false,
      "status": "stopped"
    }
  ],
  "summary": {
    "total_pnl": 456.78,
    "running_count": 1,
    "stopped_count": 2
  }
}
```

### 5.3 Update Existing Endpoints
**Files:** Various routes

| Endpoint | Change |
|----------|--------|
| `/api/positions` | Add `?instance=BTCUSD_LONG` filter |
| `/api/guardian/status` | Accept `?instance=` parameter |
| `/api/guardian/rsi/status` | Return instance-specific RSI |
| `/api/config/all` | Deprecate, redirect to `/api/instances/{name}/config` |

---

## Phase 6: Frontend Complete Redesign ⏳
**Duration:** 16-24 hours | **Priority:** HIGH

### 6.1 Replace SymbolContext with InstanceContext
**File:** `webui/frontend/src/context/InstanceContext.js` (NEW)

```javascript
const InstanceContext = createContext();

export const InstanceProvider = ({ children }) => {
  const [instances, setInstances] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null); // null = portfolio view
  const [viewMode, setViewMode] = useState('portfolio'); // 'portfolio' | 'instance'
  
  // Load instances from API
  const loadInstances = useCallback(async () => {
    const response = await fetch('/api/instances');
    const data = await response.json();
    setInstances(data.instances);
  }, []);
  
  // Select instance for detail view
  const selectInstance = useCallback((instanceName) => {
    setSelectedInstance(instanceName);
    setViewMode(instanceName ? 'instance' : 'portfolio');
  }, []);
  
  return (
    <InstanceContext.Provider value={{
      instances,
      selectedInstance,
      viewMode,
      selectInstance,
      loadInstances,
      // Helper getters
      runningInstances: instances.filter(i => i.status === 'running'),
      enabledInstances: instances.filter(i => i.enabled),
    }}>
      {children}
    </InstanceContext.Provider>
  );
};
```

### 6.2 New Instance Selector Component
**File:** `webui/frontend/src/components/common/InstanceSelector.js`

```
┌─────────────────────────────────────────────────────────┐
│  Instance: [📊 Portfolio Overview ▼]                    │
│            ├─ 📊 Portfolio Overview (All Instances)     │
│            ├─ ────────────────────────                  │
│            ├─ ₿ BTCUSD_LONG   ● Running   +$234        │
│            ├─ ₿ BTCUSD_SHORT  ○ Stopped                │
│            └─ Ξ ETHUSD_LONG   ○ Stopped                │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Portfolio Dashboard (Default View)
**File:** `webui/frontend/src/components/PortfolioDashboard.js` (NEW)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📊 PORTFOLIO OVERVIEW                     Total PnL: +$456.78      │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ ₿ BTCUSD_LONG    │  │ ₿ BTCUSD_SHORT   │  │ Ξ ETHUSD_LONG    │  │
│  │ ● RUNNING        │  │ ○ STOPPED        │  │ ○ STOPPED        │  │
│  │                  │  │                  │  │                  │  │
│  │ PnL: +$345.50    │  │ PnL: --          │  │ PnL: --          │  │
│  │ Positions: 5     │  │ Positions: 0     │  │ Positions: 0     │  │
│  │ Grid: 85k-95k    │  │ Grid: 92k-102k   │  │ Grid: 3.2k-3.8k  │  │
│  │ RSI: 42 ✓ GO     │  │ RSI: -- N/A      │  │ RSI: -- N/A      │  │
│  │                  │  │                  │  │                  │  │
│  │ [View] [Stop]    │  │ [View] [Start]   │  │ [View] [Start]   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│ ─────────────────────────────────────────────────────────────────── │
│ 📈 POSITIONS (All Instances)                                        │
│ ┌─────────────────────────────────────────────────────────────────┐│
│ │ Instance     │ Symbol │ Side │ Entry   │ Size │ PnL     │ TP   ││
│ ├─────────────────────────────────────────────────────────────────┤│
│ │ BTCUSD_LONG  │ BTC    │ LONG │ $87,500 │ 5    │ +$45.00 │ $88k ││
│ │ BTCUSD_LONG  │ BTC    │ LONG │ $87,000 │ 5    │ +$95.00 │ $87.5k││
│ │ BTCUSD_LONG  │ BTC    │ LONG │ $86,500 │ 5    │ +$145.00│ $87k ││
│ └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 6.4 Instance Detail View
**File:** `webui/frontend/src/components/InstanceDetailView.js` (NEW)

When user clicks "View" on an instance:
```
┌─────────────────────────────────────────────────────────────────────┐
│ ₿ BTCUSD_LONG                              [← Back to Portfolio]   │
│ ─────────────────────────────────────────────────────────────────── │
│                                                                     │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│ │ Status      │ │ PnL         │ │ Positions   │ │ RSI         │    │
│ │ ● RUNNING   │ │ +$345.50    │ │ 5/50        │ │ 42 ✓ GO     │    │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │
│                                                                     │
│ [Tabs: Positions | Grid | Config | Guardian | Logs]                │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐│
│ │                    [Tab Content Here]                           ││
│ └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│ ─────────────────────────────────────────────────────────────────── │
│ [Stop Instance]  [Restart Instance]  [Edit Config]                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.5 Update Existing Components

| Component | Changes Required |
|-----------|------------------|
| **ConfigPanel.js** | - Instance selector instead of symbol<br>- Load/save to `/api/instances/{name}/config`<br>- Show instance-specific RSI threshold |
| **PositionsPanel.js** | - Filter by instance when in detail view<br>- Show all with instance column in portfolio view |
| **PM2Panel.js** | - Group by instance (gridbot + guardian)<br>- Instance-level start/stop controls |
| **RSIPanel.js** | - Show RSI for all instances in portfolio view<br>- Note LONG vs SHORT threshold difference |
| **GuardianPanel.js** | - Per-instance loss tracking<br>- Instance-specific emergency stop |
| **MonitoringDashboard.js** | - Instance selector<br>- Instance-specific metrics |

### 6.6 Update App.js Routing
**File:** `webui/frontend/src/App.js`

```javascript
// Replace SymbolProvider with InstanceProvider
<InstanceProvider>
  <App />
</InstanceProvider>

// Add routing logic
{viewMode === 'portfolio' ? (
  <PortfolioDashboard />
) : (
  <InstanceDetailView instance={selectedInstance} />
)}
```

---

## Phase 7: RSI Threshold Logic ⏳
**Duration:** 3-4 hours | **Priority:** MEDIUM

### 7.1 LONG vs SHORT RSI Rules

| Mode | Stop Trading When | Resume Trading When |
|------|-------------------|---------------------|
| LONG | RSI >= 70 (overbought) | RSI < 65 |
| SHORT | RSI <= 30 (oversold) | RSI > 35 |

### 7.2 Update RSICollector
**File:** `bot/guardian/collectors/rsi_collector.py`

```python
def should_stop_trading(self) -> bool:
    rsi = self.get_latest_rsi()
    if rsi is None:
        return False  # No data, allow trading
    
    if self.mode == 'LONG':
        # LONG mode: Stop when overbought (price likely to fall)
        return rsi >= self.instance_config.safety.rsi_stop_threshold
    else:
        # SHORT mode: Stop when oversold (price likely to rise)
        return rsi <= self.instance_config.safety.rsi_stop_threshold
```

### 7.3 Instance-Specific RSI Display

```
┌─────────────────────────────────────────────────────────────┐
│ RSI Status by Instance                                       │
├─────────────────────────────────────────────────────────────┤
│ BTCUSD_LONG   RSI: 42   [====|----] 70   ✓ GO (< 70)       │
│ BTCUSD_SHORT  RSI: 42   [====|----] 30   ✓ GO (> 30)       │
│ ETHUSD_LONG   RSI: 58   [======|--] 70   ✓ GO (< 70)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 8: Testing & Validation ⏳
**Duration:** 8-12 hours | **Priority:** HIGH

### 8.1 Unit Tests
| Test | Description |
|------|-------------|
| Config loading | Verify instances load correctly |
| Instance isolation | BTCUSD_LONG doesn't affect BTCUSD_SHORT |
| Database separation | Each instance uses own database |
| RSI thresholds | LONG vs SHORT logic works correctly |

### 8.2 Integration Tests
| Test | Description |
|------|-------------|
| Start BTCUSD_LONG | Verify process starts, database created |
| Start BTCUSD_SHORT | Verify separate process, separate DB |
| Stop one, keep other | Verify independence |
| Config change | Verify only affects target instance |

### 8.3 UI Tests
| Test | Description |
|------|-------------|
| Portfolio view | Shows all instances |
| Instance detail | Drill down works |
| Instance selector | Switches correctly |
| Config edit | Saves to correct instance |

---

## Implementation Timeline

| Phase | Duration | Dependencies | Priority |
|-------|----------|--------------|----------|
| Phase 0: Architecture | 1 day | None | ✅ DONE |
| Phase 1: Config Restructure | 4-6 hrs | None | 🔴 CRITICAL |
| Phase 2: Bot CLI | 3-4 hrs | Phase 1 | 🔴 CRITICAL |
| Phase 3: Database | 2-3 hrs | Phase 1 | 🟠 HIGH |
| Phase 4: PM2 Config | 2-3 hrs | Phase 2 | 🟠 HIGH |
| Phase 5: Backend API | 6-8 hrs | Phase 1 | 🟠 HIGH |
| Phase 6: Frontend | 16-24 hrs | Phase 5 | 🟠 HIGH |
| Phase 7: RSI Logic | 3-4 hrs | Phase 1 | 🟡 MEDIUM |
| Phase 8: Testing | 8-12 hrs | All | 🟠 HIGH |

**Total Estimated Time:** 45-65 hours (6-8 days focused work)

---

## Quick Reference: Key File Changes

| File | Change Type |
|------|-------------|
| `config.yaml` | Restructure to instances format |
| `config/models.py` | Add InstanceConfig model |
| `config/loader.py` | Add get_instance_config() |
| `bot/run.py` | Add --instance argument |
| `bot/strategy/async_gridbot.py` | Load from instances config |
| `start_guardian.py` | Add --instance argument |
| `bot/guardian/core/guardian_bot.py` | Instance-aware monitoring |
| `ecosystem.multi-symbol.config.js` | Instance-based process names |
| `webui/backend/routes/instances.py` | NEW - Instance API |
| `webui/frontend/src/context/InstanceContext.js` | NEW - Replace SymbolContext |
| `webui/frontend/src/components/PortfolioDashboard.js` | NEW - Multi-instance view |
| `webui/frontend/src/components/InstanceDetailView.js` | NEW - Single instance view |
| All existing panels | Update to use InstanceContext |

---

---

# 📦 ARCHIVE: V1.0 Symbol-Centric Implementation (Completed)

> **Note:** V1.0 implemented symbol-level multi-instrument support. V2.0 (above) extends this to instance-level (symbol+mode) support.

## V1.0 Completion Summary (Previous Work)

### Phase 1: Backend API Foundation ✅ COMPLETE
**Completed:** January 1, 2026

| Task | Status | Files Changed |
|------|--------|---------------|
| Symbol Process Control API | ✅ Done | `webui/backend/routes/symbols.py` |
| Guardian Multi-Symbol API | ✅ Done | `webui/backend/routes/guardian.py` |
| RSI Multi-Symbol API | ✅ Done | `webui/backend/routes/guardian.py` |
| Config Multi-Symbol API | ✅ Done | `webui/backend/routes/yaml_config_api.py` |

### Phase 2: Frontend Components ✅ COMPLETE
**Completed:** January 1, 2026

| Component | Status | Changes |
|-----------|--------|---------|
| RSIPanel.js | ✅ Done | View mode toggle (current/all symbols), per-symbol cards |
| GuardianPanel.js | ✅ Done | Per-symbol loss tracking, portfolio aggregation |
| PM2Panel.js | ✅ Done | Symbol grouping view, per-symbol start/stop controls |
| ConfigPanel.js | ✅ Done | Global vs Symbol config mode toggle |
| apiClient.js | ✅ Done | Symbol config API methods |
| PM2Panel.css | ✅ Done | Symbol view styles |

### Phase 3: Bot Architecture ✅ COMPLETE
**Completed:** January 1, 2026

| Task | Status | Notes |
|------|--------|-------|
| Add `--symbol` CLI argument | ✅ Done | `bot/run.py` - accepts `--symbol BTCUSD` or `-s ETHUSD` |
| Activate multi-symbol PM2 config | ✅ Done | `ecosystem.multi-symbol.config.js` - updated with new CLI format |
| Guardian Multi-Symbol Mode | ✅ Done | `--symbol` CLI + per-symbol PM2 processes |

### Phase 4: Testing & Deployment ✅ ALL CODE COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| API Testing | ✅ Done | All endpoints responding correctly |
| Frontend Compilation | ✅ Done | No syntax errors |
| Integration Testing | ✅ Done | APIs verified, UI accessible |
| Bot CLI Testing | ✅ Done | `bot/run.py --symbol` and `start_guardian.py --symbol` both work |
| Stability Testing | ⏳ Manual | 48h+ dual-symbol run (user-initiated) |
| Production Deployment | ⏳ Manual | After stability testing |

---

## 🎉 IMPLEMENTATION COMPLETE

All code changes for multi-symbol trading are complete. The system now supports:

1. **Per-Symbol Bot Processes:** `python3 -m bot.run --symbol BTCUSD`
2. **Per-Symbol Guardian Processes:** `python3 start_guardian.py --symbol BTCUSD`
3. **PM2 Multi-Symbol Config:** `ecosystem.multi-symbol.config.js`
4. **Symbol-Aware APIs:** All endpoints accept `?symbol=` parameter
5. **Symbol-Aware Frontend:** All panels support symbol switching

**To Start Multi-Symbol Trading:**
```bash
# Start BTCUSD bot + guardian
pm2 start ecosystem.multi-symbol.config.js --only gridbot-btcusd-live,guardian-btcusd-live

# Start ETHUSD bot + guardian (when ready)
pm2 start ecosystem.multi-symbol.config.js --only gridbot-ethusd-live,guardian-ethusd-live
```

---

## Executive Summary

**Current State:** Your bot infrastructure *already supports* multi-symbol trading at the core level, but the WebUI and process management do NOT properly expose this capability.

**The Gap:** Config.yaml has BTCUSD + ETHUSD defined. Bot accepts `symbol_name` parameter. But:
- WebUI shows ONE symbol's data everywhere
- Guardian monitors ONE product_id  
- RSI calculates for ONE symbol globally
- PM2 has no per-symbol start/stop controls
- Configuration editing is NOT symbol-aware

---

## What EXISTS vs What is BROKEN

### ✅ Already Working (Don't Touch)

| Component | Status | Evidence |
|-----------|--------|----------|
| config.yaml v5.0 structure | ✅ Working | `symbols.BTCUSD`, `symbols.ETHUSD` sections |
| AsyncGridBot symbol support | ✅ Working | Accepts `symbol_name` parameter, creates symbol-specific databases |
| PM2 multi-symbol config | ✅ Exists | `ecosystem.multi-symbol.config.js` with `gridbot-btc-live`, `gridbot-eth-live` |
| MultiSymbolRiskAggregator | ✅ Exists | `bot/guardian/multi_symbol_aggregator.py` |
| SymbolContext (React) | ✅ Working | `selectedSymbol`, `setSelectedSymbol`, `symbols` list |
| useSymbolAPI hook | ✅ Working | Auto-adds `?symbol=` to API calls |
| SymbolSelector component | ✅ Working | Dropdown to switch symbols |
| MonitoringDashboard | ✅ Correct | Uses `useSymbol()` + `useSymbolAPI()` properly |
| Positions filtering | ✅ Exists | Backend has `_filter_positions_by_symbol()` |

### ❌ Broken/Missing (Must Fix)

| Component | Problem | Status |
|-----------|---------|--------|
| **RSIPanel.js** | No symbol awareness - shows global RSI | ✅ FIXED - Now has view mode toggle |
| **RSICollector** | Uses single `self.symbol` from config | ✅ FIXED - Accepts `symbol_name` parameter |
| **GuardianPanel.js** | Imports `useSymbol` but doesn't use it | ✅ FIXED - Per-symbol loss tracking |
| **Guardian Bot** | `product_id` hardcoded to one symbol | ✅ FIXED - Accepts `--symbol` CLI argument |
| **PM2Panel.js** | No symbol grouping or per-symbol controls | ✅ FIXED - Symbol grouping view |
| **ConfigPanel.js** | No symbol selector at all | ✅ FIXED - Global/Symbol mode toggle |
| **Bot Control API** | `single_process_mode: True` | ✅ FIXED - Process control endpoints |
| **Config API** | No `?symbol=` parameter support | ✅ FIXED - Per-symbol config endpoints |

---

## 5 Critical Requirements (From User)

### 1. RSI Safety Layer - Independent Per Symbol
**Current:** RSI calculated globally for `config.bot.symbol` (BTCUSD only)
**Required:** Calculate RSI for BTCUSD AND ETHUSD independently

**Backend Changes:**
```python
# /api/guardian/rsi/status?symbol=BTCUSD  → BTCUSD RSI
# /api/guardian/rsi/status?symbol=ETHUSD  → ETHUSD RSI
# /api/guardian/rsi/status               → Both symbols
```

**Frontend Changes:**
- RSIPanel.js: Add symbol selector or dual-symbol view
- Show: "BTCUSD RSI: 42.5 (GO)" | "ETHUSD RSI: 68.2 (GO)"

**Files to Modify:**
- `webui/backend/routes/guardian.py` - Add symbol parameter
- `bot/guardian/collectors/rsi_collector.py` - Accept symbol parameter
- `webui/frontend/src/components/RSIPanel.js` - Use SymbolContext

**Effort:** 8-12 hours

---

### 2. Guardian Protection - Protect ALL Instruments
**Current:** Guardian monitors ONE `product_id`, ONE `max_account_loss_inr`
**Required:** Per-symbol loss limits + aggregate portfolio protection

**Architecture Options:**

**Option A: Multi-Process Guardians (Recommended)**
```
PM2 Ecosystem:
├── guardian-btcusd-live  (monitors BTCUSD only, limit ₹7,000)
├── guardian-ethusd-live  (monitors ETHUSD only, limit ₹3,500)
└── guardian-portfolio    (monitors total portfolio, limit ₹10,000)
```

**Option B: Single Multi-Symbol Guardian**
```python
class MultiSymbolGuardian:
    def __init__(self, config):
        self.symbol_limits = {
            'BTCUSD': config.symbols.BTCUSD.safety.max_account_loss_inr,
            'ETHUSD': config.symbols.ETHUSD.safety.max_account_loss_inr
        }
        self.total_limit = config.capital_allocation.total_capital_inr * 0.10
```

**Frontend Changes:**
- GuardianPanel.js: Show per-symbol + total loss
- Visual: "BTCUSD: -₹800/₹7,000 (11%)" | "ETHUSD: -₹200/₹3,500 (6%)" | "Total: -₹1,000/₹10,000"

**Files to Modify:**
- `bot/guardian/core/guardian_bot.py` - Accept symbol parameter OR multi-symbol loop
- `webui/backend/routes/guardian.py` - Return per-symbol data
- `webui/frontend/src/components/GuardianPanel.js` - Display all symbols

**Effort:** 16-24 hours

---

### 3. Individual vs Simultaneous Trading
**Current:** Bot runs as single process, trades whatever symbols are enabled
**Required:** UI controls to:
- Start BTCUSD only
- Start ETHUSD only  
- Start BOTH simultaneously
- Stop one while other continues

**PM2 Process Architecture:**
```javascript
// ecosystem.multi-symbol.config.js (already exists, needs activation)
module.exports = {
  apps: [
    {
      name: 'gridbot-btcusd-live',
      script: 'python',
      args: '-m bot.run --symbol BTCUSD',
      autorestart: true
    },
    {
      name: 'gridbot-ethusd-live', 
      script: 'python',
      args: '-m bot.run --symbol ETHUSD',
      autorestart: false  // Disabled by default
    }
  ]
};
```

**Backend API:**
```python
POST /api/symbols/BTCUSD/process/start  → pm2 start gridbot-btcusd-live
POST /api/symbols/ETHUSD/process/stop   → pm2 stop gridbot-ethusd-live
POST /api/symbols/all/start             → Start all enabled symbols
```

**Frontend UI:**
```
┌───────────────────────────────────────┐
│ Trading Controls                       │
├───────────────────────────────────────┤
│ BTCUSD  [▶ Running]  [Stop] [Restart] │
│ ETHUSD  [⏸ Stopped]  [Start]          │
├───────────────────────────────────────┤
│ [Start All]  [Stop All]               │
└───────────────────────────────────────┘
```

**Files to Modify:**
- `bot/run.py` - Add `--symbol` argument
- `webui/backend/routes/symbols.py` - Add process control endpoints
- `webui/frontend/src/components/PM2Panel.js` - Symbol-grouped controls

**Effort:** 24-32 hours

---

### 4. PM2 Process Controls - Start/Stop Individual Instruments
**Current:** PM2Panel shows flat list: gridbot-live, guardian-live, etc.
**Required:** Symbol-grouped view with individual controls

**Current PM2Panel Display:**
```
gridbot-live      [Running]  [Stop]
guardian-live     [Running]  [Stop]
heartbeat-monitor [Running]  [Stop]
```

**Required PM2Panel Display:**
```
┌─ BTCUSD ─────────────────────────────┐
│ gridbot-btcusd-live   ● Running  2h  │
│ guardian-btcusd-live  ● Running  2h  │
│ [Stop BTCUSD Trading]                │
└──────────────────────────────────────┘

┌─ ETHUSD ─────────────────────────────┐
│ gridbot-ethusd-live   ○ Stopped      │
│ guardian-ethusd-live  ○ Stopped      │
│ [Start ETHUSD Trading]               │
└──────────────────────────────────────┘

┌─ System ─────────────────────────────┐
│ webui-backend         ● Running  24h │
│ heartbeat-monitor     ● Running  24h │
└──────────────────────────────────────┘
```

**Files to Modify:**
- `webui/frontend/src/components/PM2Panel.js` - Complete refactor
- `webui/backend/routes/pm2_routes.py` - Add symbol-aware endpoints
- `ecosystem.config.js` - Use multi-symbol config

**Effort:** 16-20 hours

---

### 5. Symbol-Specific Configuration - Isolated Editing
**Current:** ConfigPanel edits `config.bot.*` (always BTCUSD)
**Required:** Edit `config.symbols.BTCUSD.*` or `config.symbols.ETHUSD.*`

**Current ConfigPanel:**
```
Grid Configuration
├── Reference Price: 88500   ← Always BTCUSD
├── Lower Bound: 85000       ← Always BTCUSD
└── Step Size: 100           ← Always BTCUSD
```

**Required ConfigPanel:**
```
┌─────────────────────────────────────────┐
│ Symbol: [BTCUSD ▼]  ← Symbol Selector   │
├─────────────────────────────────────────┤
│ Grid Configuration (BTCUSD)             │
│ ├── Reference Price: 88500              │
│ ├── Lower Bound: 85000                  │
│ └── Step Size: 100                      │
├─────────────────────────────────────────┤
│ Safety Settings (BTCUSD)                │
│ ├── Max Loss: ₹7,000                    │
│ ├── RSI Threshold: 30                   │
│ └── Max Open Positions: 30              │
└─────────────────────────────────────────┘
```

**Backend API:**
```python
GET  /api/config/symbols/BTCUSD  → Returns BTCUSD-specific config
POST /api/config/symbols/BTCUSD  → Saves to symbols.BTCUSD.* in YAML
GET  /api/config/symbols/ETHUSD  → Returns ETHUSD-specific config
POST /api/config/symbols/ETHUSD  → Saves to symbols.ETHUSD.* in YAML
```

**Files to Modify:**
- `webui/backend/routes/yaml_config_api.py` - Add symbol parameter
- `webui/frontend/src/components/ConfigPanel.js` - Add symbol selector, use SymbolContext

**Effort:** 20-28 hours

---

## Implementation Priority Order

### Phase 1: Backend API Foundation (Week 1) - 40 hours
**Must complete first - frontend depends on these APIs**

1. **Symbol Process Control API** (16 hours)
   - `POST /api/symbols/<symbol>/process/start`
   - `POST /api/symbols/<symbol>/process/stop`
   - `GET /api/symbols/<symbol>/status`
   
2. **Guardian Multi-Symbol API** (8 hours)
   - `GET /api/guardian/status?symbol=BTCUSD`
   - Aggregate endpoint returns all symbols
   
3. **RSI Multi-Symbol API** (8 hours)
   - `GET /api/guardian/rsi/status?symbol=BTCUSD`
   - Aggregate endpoint returns all symbols

4. **Config Multi-Symbol API** (8 hours)
   - `GET /api/config/symbols/<symbol>`
   - `POST /api/config/symbols/<symbol>`

---

### Phase 2: Bot Architecture (Week 2) - 32 hours
**Enable actual multi-symbol execution**

1. **Bot Entry Point** (8 hours)
   - Add `--symbol` argument to `bot/run.py`
   - Validate symbol exists and is enabled
   
2. **PM2 Ecosystem Activation** (8 hours)
   - Enable `ecosystem.multi-symbol.config.js`
   - Configure per-symbol processes
   - Test individual start/stop

3. **Guardian Multi-Symbol** (16 hours)
   - Option A: Separate guardian processes per symbol
   - OR Option B: Single guardian with multi-symbol loop
   - Per-symbol health files (`.guardian_health_BTCUSD`)

---

### Phase 3: Frontend Components (Week 3-4) - 56 hours

1. **RSIPanel Refactor** (12 hours)
   - Use SymbolContext
   - Show per-symbol RSI
   - "All Symbols" overview mode

2. **GuardianPanel Refactor** (16 hours)
   - Per-symbol loss display
   - Portfolio aggregate
   - Visual risk indicators

3. **PM2Panel Refactor** (16 hours)
   - Symbol-grouped layout
   - Per-symbol start/stop buttons
   - "Start All" / "Stop All"

4. **ConfigPanel Refactor** (12 hours)
   - Symbol selector at top
   - Save to correct symbol
   - Clear visual indicator

---

### Phase 4: Testing & Deployment (Week 5) - 24 hours

1. **Integration Testing** (12 hours)
   - Start BTCUSD only → verify ETHUSD not affected
   - Edit ETHUSD config → verify BTCUSD unchanged
   - Stop BTCUSD → verify ETHUSD continues
   
2. **Stability Testing** (8 hours)
   - Run both symbols for 48+ hours
   - Verify no data mixing
   - Verify Guardian catches limits per symbol

3. **Production Deployment** (4 hours)
   - Backup v4.0 production
   - Deploy v5.0
   - Monitor 24 hours

---

## Total Effort Estimate

| Phase | Hours | Calendar Time |
|-------|-------|---------------|
| Phase 1: Backend APIs | 40 | 1 week |
| Phase 2: Bot Architecture | 32 | 1 week |
| Phase 3: Frontend | 56 | 2 weeks |
| Phase 4: Testing | 24 | 1 week |
| **Total** | **152 hours** | **5 weeks** |

**With buffer for issues:** 200 hours / 6 weeks

---

## Files Summary - What to Modify

### Backend (Python)
| File | Changes |
|------|---------|
| `webui/backend/routes/symbols.py` | Add process control endpoints |
| `webui/backend/routes/guardian.py` | Add symbol parameter support |
| `webui/backend/routes/yaml_config_api.py` | Add per-symbol config endpoints |
| `webui/backend/routes/pm2_routes.py` | Add symbol-grouped status |
| `bot/run.py` | Add `--symbol` CLI argument |
| `bot/guardian/core/guardian_bot.py` | Accept symbol parameter |
| `bot/guardian/collectors/rsi_collector.py` | Accept symbol parameter |

### Frontend (React)
| File | Changes |
|------|---------|
| `components/RSIPanel.js` | Use SymbolContext, per-symbol display |
| `components/GuardianPanel.js` | Use symbol parameter, multi-symbol view |
| `components/PM2Panel.js` | Symbol-grouped layout, per-symbol controls |
| `components/ConfigPanel.js` | Symbol selector, save to correct symbol |

### Configuration
| File | Changes |
|------|---------|
| `ecosystem.config.js` | Switch to multi-symbol version |
| `config.yaml` | Already has multi-symbol structure (no changes) |

---

## Risk Mitigation

### Risk: Data Mixing Between Symbols
**Mitigation:** 
- Symbol-specific database files: `bot_events_BTCUSD_LONG.db`
- Symbol-specific recovery files: `recovery_BTCUSD.json`
- API parameter validation: reject requests without symbol

### Risk: Production Disruption
**Mitigation:**
- Develop on port 5557/3001 (not production 5555/5556)
- Test in isolation for 48+ hours before production
- Rollback plan: restore v4.0 in under 5 minutes

### Risk: Guardian Misses One Symbol
**Mitigation:**
- Multi-process architecture: separate guardian per symbol
- Portfolio-level guardian: catches aggregate risk
- Health file monitoring per symbol

---

## Decision Points

Before starting implementation, confirm:

1. **Architecture:** Multi-process (recommended) OR single-process multi-thread?
2. **Timeline:** 5-week aggressive OR 6-week safe?
3. **Priority:** All 5 requirements equal OR some first?
4. **Testing:** How long to run before production (48h? 72h? 1 week?)
5. **Rollback:** Acceptable downtime for rollback (5 min? 30 min?)

---

## Immediate Next Steps

**This Week (Planning Only):**
1. ✅ Review this plan
2. ⏳ Decide on multi-process vs single-process Guardian
3. ⏳ Confirm development port isolation (5557/3001)
4. ⏳ Create Jira/GitHub tickets for Phase 1

**Next Week (Start Implementation):**
1. Backend API: Symbol process control
2. Backend API: Guardian multi-symbol
3. Test: Can start/stop BTCUSD via new API

---

## References

- Existing detailed plan: `MULTI_INSTRUMENT_WEBUI_PRODUCTIVITY_PLAN.md` (2513 lines)
- Bot architecture: `bot/strategy/async_gridbot.py` (5078 lines, already symbol-aware)
- Multi-symbol aggregator: `bot/guardian/multi_symbol_aggregator.py` (already exists!)
- PM2 config: `ecosystem.multi-symbol.config.js` (already exists!)
- Config structure: `config.yaml` (v5.0 with symbols.BTCUSD, symbols.ETHUSD)
