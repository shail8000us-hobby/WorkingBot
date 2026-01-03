# Multi-Instrument System Deep-Dive Analysis

**Date:** January 1, 2026  
**Analyst:** GitHub Copilot  
**Scope:** Comprehensive gap analysis for true multi-instrument trading support

---

## Executive Summary

The system has **foundational multi-instrument support** in place but is **incomplete**. The bot core is well-architected for multi-symbol (v5.0), but the WebUI, PM2 configuration, and monitoring systems have significant gaps. Currently, BTCUSD can run in LONG mode while ETHUSD runs in SHORT mode, but **the WebUI cannot fully control or monitor this**.

### Overall Assessment

| Area | Status | Score |
|------|--------|-------|
| Config Structure (YAML) | ✅ Well Designed | 90% |
| Bot Core (async_gridbot.py) | ✅ Multi-Symbol Ready | 95% |
| Database Architecture | ✅ Per-Symbol Isolated | 90% |
| Backend APIs | ⚠️ Partial Support | 60% |
| Frontend Components | ⚠️ Major Gaps | 40% |
| PM2/Process Management | ❌ Single-Symbol Only | 20% |
| Guardian (Risk Monitor) | ⚠️ Needs Work | 50% |

---

## Part 1: Config Structure Analysis

### Current State

**File:** [config.yaml](config.yaml)

```yaml
symbols:
  BTCUSD:
    enabled: true
    product_id: 139
    mode: LONG          # ✅ Per-symbol mode
    grid:
      geometry:
        lower: '85000'
        upper: '95000'
        step: '500'
    safety:
      max_account_loss_inr: '10000'  # ✅ Per-symbol loss limit
  ETHUSD:
    enabled: false
    product_id: 3136
    mode: LONG          # Could be SHORT independently
    grid:
      geometry:
        lower: '3200'
        upper: '3800'
        step: '50'
    safety:
      max_account_loss_inr: '5000'
```

### ✅ What Works

1. **Independent Mode per Symbol**: Each symbol can have `mode: LONG` or `mode: SHORT`
2. **Separate Grid Parameters**: Each symbol has its own geometry (lower, upper, step, reference)
3. **Per-Symbol Safety Limits**: Each symbol has `max_account_loss_inr`
4. **Enable/Disable per Symbol**: `enabled: true/false` flag
5. **Product ID Mapping**: Each symbol has correct exchange product ID

### ❌ Gaps Identified

| Gap | Description | Severity |
|-----|-------------|----------|
| **No BTCUSD SHORT + BTCUSD LONG** | Same symbol can't run in both modes simultaneously | Medium |
| **RSI Thresholds Not Per-Symbol** | `safety.rsi` is global, not under each symbol | High |
| **Capital Allocation Duplicated** | `capital_allocation.allocations.BTCUSD` AND `symbols.BTCUSD.capital` exist | Low |
| **Guardian Config is Global** | Single `guardian.max_account_loss_inr` vs per-symbol | High |

### Recommendations

1. **Rename to Symbol+Mode Key**: 
   ```yaml
   symbols:
     BTCUSD_LONG:
       base_symbol: BTCUSD
       mode: LONG
     BTCUSD_SHORT:
       base_symbol: BTCUSD  
       mode: SHORT
   ```
2. **Move RSI to Per-Symbol**:
   ```yaml
   symbols:
     BTCUSD:
       rsi:
         long_threshold: 25
         short_threshold: 75
   ```
3. **Consolidate Capital Allocation** into `symbols.*.capital` only

---

## Part 2: Bot Core Analysis

### Current State

**File:** [bot/run.py](bot/run.py) (Lines 1-115)

```python
def parse_args():
    parser.add_argument(
        '--symbol', '-s',
        type=str,
        default=None,
        help='Symbol to trade (e.g., BTCUSD, ETHUSD)'
    )

async def main(symbol_name: str = None):
    bot = AsyncGridBot(
        symbol_name=symbol_name  # v5.0: Pass symbol for multi-symbol mode
    )
```

**File:** [bot/strategy/async_gridbot.py](bot/strategy/async_gridbot.py) (Lines 180-350)

```python
# Multi-symbol initialization
if symbol_name:
    symbol_config = config.symbols[symbol_name]
    self.symbol_name = symbol_name
    self.mode = symbol_config.mode  # Gets mode from symbol config
    
# Symbol-specific database
db_name = f"data/bot_events_{self.symbol_name}_{self.mode}.db"
self.event_store = EventStore(db_name)
```

### ✅ What Works

1. **CLI Symbol Selection**: `python3 -m bot.run --symbol BTCUSD` works
2. **Symbol Config Loading**: Reads from `config.symbols.BTCUSD`
3. **Mode from Symbol**: Gets LONG/SHORT from symbol's config
4. **Isolated Database**: Creates `bot_events_BTCUSD_LONG.db` per symbol+mode
5. **Isolated Monitoring File**: `data/monitoring_snapshot_BTCUSD_LONG.json`
6. **Isolated Recovery State**: `data/recovery/recovery_state_BTCUSD_LONG.json`

### ❌ Gaps Identified

| Gap | Description | Severity |
|-----|-------------|----------|
| **Legacy Fallback Still Exists** | If no `--symbol`, uses deprecated `config.bot.symbol` | Low |
| **No Mode Override** | Can't run `--symbol BTCUSD --mode SHORT` to override config | Medium |
| **Product ID Hardcoded Fallback** | `self.product_id = product_id or 27` defaults to wrong value | Low |

### Recommendations

1. **Add `--mode` CLI Argument**: Allow runtime override of mode
2. **Remove Legacy `config.bot` Section** after migration complete
3. **Fail Fast if No Symbol**: Remove fallback to single-symbol mode

---

## Part 3: Database Architecture Analysis

### Current State

**Directory:** [data/](data/)

```
data/
├── bot_events_LONG.db              # ❌ Legacy - no symbol prefix
├── bot_events_None.db              # ❌ Bug - created when symbol_name=None
├── guardian_events.db              # Global guardian events
├── errors.db                       # Global error tracking
├── volatility.db                   # Global volatility data
├── instances/                      # Saved grid configurations
└── recovery/                       # Per-symbol recovery states
```

### ✅ What Works

1. **Bot Events Isolated**: `bot_events_{symbol}_{mode}.db` pattern works when symbol specified
2. **Recovery State Isolated**: `recovery_state_{symbol}_{mode}.json` exists
3. **Monitoring Snapshot Isolated**: `monitoring_snapshot_{symbol}_{mode}.json` pattern

### ❌ Gaps Identified

| Gap | Description | Severity |
|-----|-------------|----------|
| **Legacy Databases Exist** | `bot_events_LONG.db` without symbol prefix | Medium |
| **Guardian Events Global** | Single `guardian_events.db` for all symbols | High |
| **Volatility DB Global** | Single `volatility.db` - should be per-symbol | Medium |
| **None.db Bug** | `bot_events_None.db` created when symbol_name missing | Low |
| **Errors DB Global** | All symbols write to single `errors.db` | Low |

### Recommendations

1. **Migrate Legacy DBs**: Rename `bot_events_LONG.db` → `bot_events_BTCUSD_LONG.db`
2. **Per-Symbol Volatility**: Create `volatility_BTCUSD.db`, `volatility_ETHUSD.db`
3. **Guardian Events Per-Symbol**: `guardian_events_BTCUSD.db`
4. **Add Migration Script**: Auto-migrate old databases on startup

---

## Part 4: Frontend Components Analysis

### 4.1 MonitoringDashboard.js

**File:** [MonitoringDashboard.js](webui/frontend/src/components/MonitoringDashboard.js)

**Current Behavior:**
- Uses `selectedSymbol` from SymbolContext
- Shows SymbolBadge on Price Health card
- Fetches `/api/monitoring/status` (no symbol parameter!)

```javascript
const { selectedSymbol } = useSymbol();

// ❌ No symbol parameter in API calls!
const data = await api.fetchJSON('/api/monitoring/status');
const health = await api.fetchJSON('/api/monitoring/price-health');
```

| Feature | Status | Issue |
|---------|--------|-------|
| Symbol Badge Display | ✅ | Shows current symbol |
| API Symbol Parameter | ❌ | Doesn't pass symbol to API |
| Multi-Symbol View | ❌ | No "All Symbols" toggle |
| Aggregate P&L | ❌ | Only shows selected symbol |

### 4.2 RSIPanel.js

**File:** [RSIPanel.js](webui/frontend/src/components/RSIPanel.js)

**Current Behavior:**
- Has "Current Symbol" / "All Symbols" toggle ✅
- Fetches `/api/guardian/rsi/status?symbol=${selectedSymbol}` ✅
- Shows `RSISymbolCard` for each symbol

```javascript
const [viewMode, setViewMode] = useState('current'); // 'current' or 'all'

if (viewMode === 'all') {
  const response = await api.get('/api/guardian/rsi/status');
  // Shows all symbols
}
```

| Feature | Status | Issue |
|---------|--------|-------|
| Per-Symbol RSI | ✅ | Works |
| All Symbols View | ✅ | Toggle exists |
| Config Per-Symbol | ❌ | RSI thresholds are global |
| Mode-Aware Thresholds | ⚠️ | Shows LONG/SHORT threshold but saves globally |

### 4.3 GuardianPanel.js

**File:** [GuardianPanel.js](webui/frontend/src/components/GuardianPanel.js)

**Current Behavior:**
- Shows "Per-Symbol Loss Tracking" section ✅
- Displays `symbols` object from API
- Has aggregate P&L view

```javascript
const { running, health, symbols = {}, global = {} } = guardianStatus;

{Object.entries(symbols).map(([sym, data]) => (
  <SymbolCard symbol={sym} ... />
))}
```

| Feature | Status | Issue |
|---------|--------|-------|
| Per-Symbol Loss Display | ✅ | Shows loss per symbol |
| Global Portfolio Summary | ✅ | Shows totals |
| Per-Symbol Start/Stop | ❌ | Single Start/Stop for all |
| Per-Symbol Loss Limits | ❌ | Uses global max_loss |

### 4.4 ConfigPanel.js

**File:** [ConfigPanel.js](webui/frontend/src/components/ConfigPanel.js)

**Current Behavior:**
- Has "Global" / "Symbol" config mode toggle ✅
- Calls `apiClient.getSymbolConfig(selectedSymbol)` for symbol mode
- Uses legacy GRIDBOT_* field names

```javascript
const [configMode, setConfigMode] = useState('global'); // 'global' or 'symbol'

if (configMode === 'symbol') {
  const result = await apiClient.updateSymbolConfig(selectedSymbol, values);
}
```

| Feature | Status | Issue |
|---------|--------|-------|
| Symbol Mode Toggle | ✅ | Switch exists |
| Symbol Config Load | ⚠️ | API may not return symbol-specific values |
| Mode Selection (LONG/SHORT) | ❌ | Can't edit BTCUSD LONG vs BTCUSD SHORT |
| Grid Per-Symbol | ⚠️ | May save to wrong section |
| Loss Limit Per-Symbol | ❌ | Saves to global guardian section |

### 4.5 PM2Panel.js

**File:** [PM2Panel.js](webui/frontend/src/components/PM2Panel.js)

**Current Behavior:**
- Has `extractSymbolFromProcess()` function to detect symbol from name
- Groups processes by symbol
- Has per-symbol start/stop buttons

```javascript
const extractSymbolFromProcess = (processName) => {
  // Pattern: gridbot-BTCUSD-live, guardian-ETHUSD-live
  const symbolMatch = processName.match(/-(BTCUSD|ETHUSD|[A-Z]{6})(?:-|$)/i);
  if (symbolMatch) return symbolMatch[1].toUpperCase();
  return null; // System process
};

const handleStartSymbol = async (symbol) => {
  await api.post(`/api/symbols/${symbol}/process/start`);
};
```

| Feature | Status | Issue |
|---------|--------|-------|
| Symbol Detection | ⚠️ | Only works if process name contains symbol |
| Per-Symbol Start/Stop | ✅ | API exists |
| Start All / Stop All | ✅ | Buttons exist |
| Process Grouping | ❌ | Current PM2 config has no symbol in names |

### 4.6 PositionsPanel.js

**File:** [PositionsPanel.js](webui/frontend/src/components/PositionsPanel.js)

**Current Behavior:**
- Shows SymbolBadge for selected symbol
- Fetches `/api/positions` (no symbol filter!)

```javascript
// ❌ Comment says "will be updated in Phase 2C"
const { data } = await api.get('/api/positions');
```

| Feature | Status | Issue |
|---------|--------|-------|
| Symbol Badge | ✅ | Shows selected |
| Symbol Filter | ❌ | API not passing symbol |
| Multi-Symbol View | ❌ | Can't see all positions |
| Per-Symbol Aggregation | ❌ | No breakdown by symbol |

### 4.7 SymbolPortfolio.js

**File:** [SymbolPortfolio.js](webui/frontend/src/components/SymbolPortfolio.js)

**Current Behavior:**
- Fetches data for ALL symbols in parallel ✅
- Shows position count and P&L per symbol
- Has "View" button to switch to symbol

```javascript
const promises = symbols.map(async (symbol) => {
  const posResponse = await fetch(`/api/positions?symbol=${symbol.name}`);
  const configResponse = await fetch(`/api/config/flat?symbol=${symbol.name}`);
});
```

| Feature | Status | Issue |
|---------|--------|-------|
| All Symbols View | ✅ | Shows cards for each |
| Per-Symbol P&L | ✅ | Calculates from positions |
| Start/Stop Per-Symbol | ❌ | No control buttons |
| Mode Display | ❌ | Doesn't show LONG/SHORT |

---

## Part 5: Backend API Analysis

### 5.1 symbols.py Routes

**File:** [symbols.py](webui/backend/routes/symbols.py)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/symbols` | ✅ | Lists all symbols with config |
| `GET /api/symbols/<symbol>` | ✅ | Gets symbol details |
| `POST /api/symbols/<symbol>/process/start` | ⚠️ | PM2 names don't match |
| `POST /api/symbols/<symbol>/process/stop` | ⚠️ | PM2 names don't match |
| `POST /api/symbols/all/start` | ❌ | Not implemented |
| `POST /api/symbols/all/stop` | ❌ | Not implemented |

**Issue:** Process names in PM2 are `gridbot-live` not `gridbot-btcusd-live`, so start/stop fail.

### 5.2 yaml_config_api.py Routes

**File:** [yaml_config_api.py](webui/backend/routes/yaml_config_api.py)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/yaml-config` | ✅ | Returns full config |
| `GET /api/config/flat?symbol=BTCUSD` | ⚠️ | Returns flattened but may mix global |
| `POST /api/yaml-config` | ⚠️ | Saves but doesn't update per-symbol |
| `POST /api/config/update` | ⚠️ | Uses legacy key mapping |

**Issue:** Legacy GRIDBOT_* keys map to global `grid.*` section, not `symbols.BTCUSD.grid.*`

---

## Part 6: PM2/Process Management Analysis

### Current State

**File:** [ecosystem.config.js](ecosystem.config.js)

```javascript
{
  name: "gridbot-live",           // ❌ No symbol in name
  script: "bot/strategy/async_gridbot.py",
  // No --symbol argument!
},
{
  name: "guardian-live",          // ❌ No symbol in name  
  script: "bot/guardian/core/guardian_bot.py",
}
```

### ❌ Critical Issues

| Issue | Description | Impact |
|-------|-------------|--------|
| **Single Process Per Mode** | Only one gridbot-live, not gridbot-btcusd-live | **BLOCKING** |
| **No Symbol Argument** | Script runs without `--symbol BTCUSD` | **BLOCKING** |
| **Guardian Single Process** | One guardian for all symbols | High |
| **Frontend Name Mismatch** | PM2Panel expects `gridbot-BTCUSD-live` | High |

### Required Changes for Multi-Symbol

```javascript
// NEW: Multi-symbol ecosystem.config.js
{
  name: "gridbot-btcusd-live",
  script: "bot/strategy/async_gridbot.py",
  args: "--symbol BTCUSD",
  interpreter: "python3",
},
{
  name: "gridbot-ethusd-live", 
  script: "bot/strategy/async_gridbot.py",
  args: "--symbol ETHUSD",
  interpreter: "python3",
},
{
  name: "guardian-btcusd-live",
  script: "bot/guardian/core/guardian_bot.py",
  args: "--symbol BTCUSD",
},
{
  name: "guardian-ethusd-live",
  script: "bot/guardian/core/guardian_bot.py", 
  args: "--symbol ETHUSD",
}
```

---

## Part 7: Critical Questions Answered

### Q1: Symbol + Mode Isolation

**Question:** Can BTCUSD run in LONG mode while ETHUSD runs in SHORT mode simultaneously?

**Answer:** ✅ YES, but only at the bot core level.

| Layer | Isolated? | Notes |
|-------|-----------|-------|
| Config | ✅ | Each symbol has `mode: LONG/SHORT` |
| Bot Process | ⚠️ | Needs PM2 with `--symbol` arg |
| Database | ✅ | `bot_events_BTCUSD_LONG.db` |
| Guardian | ⚠️ | Needs separate process per symbol |
| RSI Thresholds | ⚠️ | Config is global, not per-symbol |
| WebUI Control | ❌ | Can't start/stop per symbol |

### Q2: Dashboard Design

**Question:** Should dashboard show unified portfolio or per-symbol?

**Current:** Shows ONE symbol at a time via selector.

**Recommendation:** BOTH options needed:

```
┌────────────────────────────────────────────────────────────┐
│ 📊 Portfolio Overview                                       │
│ Total P&L: +$1,234.56  │  Total Positions: 15              │
├─────────────────┬─────────────────┬────────────────────────┤
│ BTCUSD (LONG)   │ ETHUSD (SHORT)  │ Add Symbol +          │
│ P&L: +$800      │ P&L: +$434      │                        │
│ Positions: 10   │ Positions: 5    │                        │
│ [View] [Stop]   │ [View] [Stop]   │                        │
└─────────────────┴─────────────────┴────────────────────────┘
```

**Components to Update:**
1. `SymbolPortfolio.js` - Add start/stop buttons, show mode
2. `MonitoringDashboard.js` - Add multi-symbol toggle
3. `PositionsPanel.js` - Show all positions grouped by symbol
4. `GuardianPanel.js` - Per-symbol emergency stop

### Q3: Configuration Gaps

**Question:** Can you select "BTCUSD LONG" vs "BTCUSD SHORT" separately?

**Answer:** ❌ NO - Major Gap

**Current Flow:**
1. Select BTCUSD from dropdown
2. ConfigPanel loads `symbols.BTCUSD` config
3. Mode is displayed but editing affects the ONLY BTCUSD config

**What's Missing:**
- No way to configure BTCUSD for BOTH long and short
- Config assumes one mode per symbol
- Would need `symbols.BTCUSD_LONG` and `symbols.BTCUSD_SHORT` keys

### Q4: Monitoring Gaps

| Feature | Current | Needed |
|---------|---------|--------|
| Positions table shows symbol | ✅ | Works |
| Order history filter by symbol | ❌ | Need filter |
| P&L chart separates symbols | ❌ | Need per-symbol lines |
| Aggregate portfolio P&L | ❌ | Need sum across symbols |

### Q5: Control Gaps

| Action | Current | Needed |
|--------|---------|--------|
| Start BTCUSD only | ❌ | PM2 process per symbol |
| Stop ETHUSD without affecting BTCUSD | ❌ | Separate processes |
| Emergency stop ALL | ⚠️ | Works but stops single process |
| Emergency stop ONE symbol | ❌ | Need per-symbol Guardian |
| Restart just one symbol | ❌ | Need PM2 separation |

---

## Part 8: Architecture Issues Requiring Redesign

### Issue 1: PM2 Configuration (CRITICAL)

**Current:** Single `gridbot-live` process for all symbols

**Required:**
```
gridbot-btcusd-live
gridbot-ethusd-live
guardian-btcusd-live
guardian-ethusd-live
```

**Impact:** Cannot start/stop symbols independently

### Issue 2: Guardian Single Instance

**Current:** One Guardian monitors all symbols

**Problem:** 
- Emergency stop affects all symbols
- Loss limits are global
- RSI thresholds are global

**Required:**
- Either: Per-symbol Guardian process
- Or: Single Guardian with per-symbol tracking and stop

### Issue 3: Config Save Path

**Current:** ConfigPanel saves to legacy `grid.*` path

**Required:** Save to `symbols.BTCUSD.grid.*`

**Example Fix:**
```javascript
// Before
'grid.geometry.reference': value

// After  
`symbols.${selectedSymbol}.grid.geometry.reference`: value
```

### Issue 4: Mode as First-Class Concept

**Current:** Mode is a property of symbol config

**Problem:** Can't run BTCUSD LONG and BTCUSD SHORT simultaneously

**Options:**
1. Change key to `symbols.BTCUSD_LONG` (breaking change)
2. Add mode to all API paths: `/api/symbols/BTCUSD/LONG/config`
3. Create mode switcher that changes config.mode and restarts

---

## Part 9: WebUI Redesign Recommendations

### 9.1 SymbolContextBar Redesign

**Current:** Dropdown with symbol name

**Proposed:**
```
┌─────────────────────────────────────────────────────────┐
│ [BTCUSD LONG ▼] [ETHUSD SHORT ▼] [+ Add] │ 📊 Portfolio │
└─────────────────────────────────────────────────────────┘
```

- Show symbol + mode as combined badge
- Allow adding new symbol+mode combinations
- Portfolio button shows all-symbols view

### 9.2 Dashboard Tabs

**Current:** Single dashboard for selected symbol

**Proposed Tabs:**
1. **Portfolio** - All symbols overview (SymbolPortfolio enhanced)
2. **BTCUSD** - Full dashboard for BTCUSD
3. **ETHUSD** - Full dashboard for ETHUSD
4. **+ Add Tab** - Add new symbol

### 9.3 Config Panel Symbol Mode

**Add Mode Toggle:**
```
Symbol: [BTCUSD ▼]  Mode: [LONG ▼ | SHORT]
─────────────────────────────────────────
Grid for BTCUSD LONG:
  Lower: 85000  Upper: 95000  Step: 500
```

### 9.4 Process Control Redesign

**PM2Panel Changes:**
```
┌────────────────────────────────────────────────────────┐
│ Symbol Trading Processes                                │
├─────────────────────────────────────────────────────────┤
│ BTCUSD LONG                                             │
│   gridbot-btcusd-live   ● Running  [Stop] [Restart]    │
│   guardian-btcusd-live  ● Running  [Stop] [Restart]    │
├─────────────────────────────────────────────────────────┤
│ ETHUSD SHORT                                            │
│   gridbot-ethusd-live   ○ Stopped  [Start]             │
│   guardian-ethusd-live  ○ Stopped  [Start]             │
├─────────────────────────────────────────────────────────┤
│ [Start All Enabled] [Stop All] [Emergency Stop]        │
└─────────────────────────────────────────────────────────┘
```

### 9.5 Positions Panel Grouping

**Current:** Flat list of positions

**Proposed:**
```
┌────────────────────────────────────────────────────────┐
│ All Positions │ BTCUSD │ ETHUSD │                      │
├────────────────────────────────────────────────────────┤
│ ◉ BTCUSD LONG (7 positions)  P&L: +$523.40            │
│   ├─ Entry: $87,500  Size: 5  P&L: +$125.00           │
│   ├─ Entry: $87,000  Size: 5  P&L: +$180.00           │
│   └─ ... 5 more                                        │
│                                                         │
│ ◉ ETHUSD SHORT (3 positions) P&L: -$45.20             │
│   ├─ Entry: $3,450   Size: 10 P&L: -$25.00            │
│   └─ ... 2 more                                        │
└────────────────────────────────────────────────────────┘
```

---

## Part 10: Implementation Priority

### Phase 1: PM2 Foundation (BLOCKING)

1. Create `ecosystem.multi.config.js` with per-symbol processes
2. Update `symbols.py` to use correct process names
3. Test: Start BTCUSD, verify ETHUSD not affected

### Phase 2: Config API Fixes

1. Fix `yaml_config_api.py` to save to `symbols.X.grid.*`
2. Add `?symbol=X&mode=Y` to all config endpoints
3. Update ConfigPanel to use symbol-specific paths

### Phase 3: Frontend Multi-Symbol

1. Add mode to SymbolBadge: `BTCUSD LONG`
2. Update PM2Panel to group by symbol+mode
3. Add Portfolio view with aggregate P&L
4. Add per-symbol start/stop buttons

### Phase 4: Guardian Per-Symbol

1. Add `--symbol` argument to guardian_bot.py
2. Create guardian process per symbol in PM2
3. Per-symbol loss limits and emergency stop

### Phase 5: Advanced Features

1. Multiple modes per symbol (BTCUSD_LONG + BTCUSD_SHORT)
2. Cross-symbol correlation monitoring
3. Portfolio-wide risk management

---

## Appendix A: File-by-File Gap Summary

| File | Gaps | Priority |
|------|------|----------|
| `ecosystem.config.js` | No symbol in process names/args | **P0** |
| `symbols.py` | Process names don't match PM2 | **P0** |
| `yaml_config_api.py` | Saves to legacy paths | **P1** |
| `ConfigPanel.js` | No mode selection | **P1** |
| `PM2Panel.js` | Name matching fails | **P1** |
| `PositionsPanel.js` | No symbol filter | **P2** |
| `MonitoringDashboard.js` | No symbol in API calls | **P2** |
| `GuardianPanel.js` | No per-symbol stop | **P2** |
| `SymbolPortfolio.js` | No start/stop, no mode display | **P2** |
| `RSIPanel.js` | Global thresholds only | **P3** |

---

## Appendix B: API Endpoints Needed

### New Endpoints Required

```
POST /api/symbols/{symbol}/mode      # Switch symbol mode
GET  /api/positions?symbol={symbol}  # Filter positions (exists but not used)
POST /api/guardian/stop/{symbol}     # Emergency stop per symbol
GET  /api/portfolio/summary          # Aggregate all symbols
POST /api/config/symbol/{symbol}/grid  # Update symbol-specific grid
```

### Existing Endpoints to Fix

```
GET  /api/monitoring/status          # Add ?symbol= parameter
GET  /api/config/flat                # Return symbol-specific when ?symbol=
POST /api/symbols/{symbol}/process/* # Fix PM2 process names
```

---

## Conclusion

The multi-instrument foundation is solid in the bot core, but **PM2 configuration is the critical blocker**. Without per-symbol processes, the WebUI cannot control symbols independently. 

**Recommended First Step:** Create `ecosystem.multi.config.js` with:
- `gridbot-btcusd-live --symbol BTCUSD`
- `gridbot-ethusd-live --symbol ETHUSD`
- `guardian-btcusd-live --symbol BTCUSD`
- `guardian-ethusd-live --symbol ETHUSD`

This unblocks all other WebUI improvements.
