# V6.0 Multi-Instance Architecture: CRITICAL GAP ANALYSIS

**Date:** January 1, 2026  
**Status:** ❌ **NOT PRODUCTION READY**  
**Analyst:** Deep-dive audit of actual codebase vs documentation claims

---

## Executive Summary

The documentation claims V2.0 Phases 1-8 are complete. **This is FALSE.** Only the infrastructure was created but **NOT integrated** into the actual components. The WebUI is NOT ready for multi-instance trading.

### Reality Check

| What Documentation Says | What Actually Exists |
|-------------------------|---------------------|
| "Phase 6 Complete: Frontend Instance Integration" | ❌ Only 1/14 components uses InstanceContext |
| "Phase 7 Complete: Guardian RSI modes" | ⚠️ Config exists but guardian uses global thresholds |
| "Phase 8 Complete: E2E Testing" | ❌ Frontend doesn't use instance parameter |

---

## PART 1: Frontend Component Gaps

### Context Usage Reality

| Component | Uses `useInstance`? | Uses `useSymbol`? | Status |
|-----------|-------------------|------------------|--------|
| InstanceContextBar.js | ✅ Yes | - | ✅ Ready |
| PositionsPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| LogsPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| GuardianPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| MonitoringPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| RSIPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| PM2Panel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| SymbolPortfolio.js | ❌ No | ✅ Yes | ❌ NOT READY |
| BotManagerPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| MonitoringDashboard.js | ❌ No | ✅ Yes | ❌ NOT READY |
| ConfigPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |
| TopBar.js | ❌ No | ✅ Yes | ❌ NOT READY |
| SymbolContextBar.js | ❌ No | ✅ Yes | ❌ NOT READY |
| MonitoringRecoveryPanel.js | ❌ No | ✅ Yes | ❌ NOT READY |

**Score: 1/14 components (7%) are instance-aware**

### API Client Usage Reality

| Component | API Client | Auto-injects Symbol? | Passes Instance? |
|-----------|-----------|---------------------|------------------|
| MonitoringDashboard.js | `useSymbolAPI` | ✅ Symbol only | ❌ No |
| PositionsPanel.js | `apiClient` | ❌ No | ❌ No |
| GuardianPanel.js | `apiClient` | ❌ No | ❌ No |
| RSIPanel.js | `apiClient` | ❌ No | ⚠️ Manual symbol |
| PM2Panel.js | `apiClient` + `useSymbolAPI` | ⚠️ Partial | ⚠️ Manual symbol |
| ConfigPanel.js | `apiClient` | ❌ No | ⚠️ Manual symbol |
| SymbolPortfolio.js | Native `fetch` | - | ⚠️ Manual symbol |

### What Was Created But Not Used

```
CREATED (exists):
├── InstanceContext.js ✅
├── useInstanceAPI.js ✅
├── InstanceContextBar.js ✅
├── useBotControl.js with instance support ✅
└── apiClient.js with instance methods ✅

NOT INTEGRATED (still uses old code):
├── PositionsPanel.js → still uses useSymbol
├── GuardianPanel.js → still uses useSymbol
├── RSIPanel.js → still uses useSymbol
├── ConfigPanel.js → still uses useSymbol
├── PM2Panel.js → still uses useSymbol
├── MonitoringDashboard.js → still uses useSymbol
├── MonitoringPanel.js → still uses useSymbol
├── LogsPanel.js → still uses useSymbol
├── BotManagerPanel.js → still uses useSymbol
├── SymbolPortfolio.js → still uses useSymbol
├── TopBar.js → still uses useSymbol
├── SymbolContextBar.js → still uses useSymbol
└── MonitoringRecoveryPanel.js → still uses useSymbol
```

---

## PART 2: Backend API Gaps

### Endpoints NOT Instance-Aware

| Endpoint | Accepts Instance? | Actually Filters? | Impact |
|----------|------------------|-------------------|--------|
| `GET /api/positions` | ❌ No | ❌ No | Shows ALL positions, not filtered |
| `GET /api/guardian/status` | ❌ No (symbol only) | ❌ No | Global guardian only |
| `POST /api/bot/start` | ⚠️ In body | ❌ Not used | Starts global bot |
| `POST /api/bot/stop` | ⚠️ In body | ❌ Not used | Stops global bot |
| `GET /api/monitoring/status` | ❌ (symbol+mode separate) | ⚠️ Partial | Uses symbol_mode.json pattern |
| `GET /api/config/flat` | ❌ (symbol only) | ⚠️ Partial | No instance format |
| `GET /api/orders/open` | ❌ No | ❌ No | Shows ALL orders |
| `GET /api/orders/history` | ❌ No | ❌ No | Shows ALL orders |

### Process Control Gap

```
CURRENT (single-process):
pm2 start gridbot-live        # ONE bot for all symbols
pm2 start guardian-live       # ONE guardian for all symbols

REQUIRED (multi-instance):
pm2 start gridbot-btcusd-long    # Bot for BTCUSD_LONG
pm2 start gridbot-btcusd-short   # Bot for BTCUSD_SHORT
pm2 start guardian-btcusd-long   # Guardian for BTCUSD_LONG
pm2 start guardian-btcusd-short  # Guardian for BTCUSD_SHORT
```

### PM2 Configuration Reality

```
ecosystem.config.js (CURRENTLY USED):
├── gridbot-live          # ❌ No --instance argument
├── guardian-live         # ❌ No --instance argument
└── webui-backend-dev     # OK

ecosystem.multi-symbol.config.js (EXISTS BUT NOT USED):
├── gridbot-btcusd-long   # ✅ Has --instance BTCUSD_LONG
├── gridbot-btcusd-short  # ✅ Has --instance BTCUSD_SHORT
├── guardian-btcusd-long  # ✅ Has --instance BTCUSD_LONG
└── guardian-btcusd-short # ✅ Has --instance BTCUSD_SHORT
```

---

## PART 3: Data Flow Gaps

### Positions Panel Flow (BROKEN)

```
User selects "BTCUSD_LONG" in instance dropdown
       │
       ▼
PositionsPanel.js:
  const { selectedSymbol } = useSymbol();  // ❌ Gets BTCUSD, loses mode
  fetch('/api/positions');                  // ❌ No instance param
       │
       ▼
Backend:
  Returns ALL positions                     // ❌ Not filtered
       │
       ▼
UI shows positions from ALL instances       // ❌ WRONG
```

### Guardian Panel Flow (BROKEN)

```
User selects "BTCUSD_LONG" in instance dropdown
       │
       ▼
GuardianPanel.js:
  fetch('/api/guardian/status');            // ❌ No instance param
       │
       ▼
Backend:
  Reads global guardian health file         // ❌ Not per-instance
       │
       ▼
UI shows global guardian status             // ❌ WRONG
```

### Config Panel Flow (BROKEN)

```
User selects "BTCUSD_LONG" in instance dropdown
       │
       ▼
ConfigPanel.js:
  const { selectedSymbol } = useSymbol();   // ❌ Gets BTCUSD, loses mode
  fetch('/api/config/flat?symbol=BTCUSD');  // ❌ No mode/instance
       │
       ▼
Backend:
  Returns symbols.BTCUSD config             // ⚠️ One config for symbol
       │
       ▼
No way to configure BTCUSD_LONG vs BTCUSD_SHORT separately!
```

---

## PART 4: Critical Missing Features

### 1. Instance-Specific Databases

**Claimed:** Each instance has separate database  
**Reality:** Bot code supports it, but WebUI always reads default paths

```python
# Bot creates: data/bot_events_BTCUSD_LONG.db
# WebUI reads: data/bot_events.db (hardcoded in some places)
```

### 2. Instance-Specific Monitoring Files

**Claimed:** monitoring_snapshot_{symbol}_{mode}.json  
**Reality:** Backend has `_get_monitoring_file()` but not all routes use it

### 3. Instance-Specific PnL

**Claimed:** Per-instance PnL tracking  
**Reality:** Global PnL file, no instance filtering

### 4. Instance-Specific Emergency Stop

**Claimed:** Can stop one instance without affecting others  
**Reality:** Guardian emergency stop affects ALL instances

---

## PART 5: Required Fixes (Priority Order)

### Priority 0 (BLOCKING)

| Fix | Files | Effort |
|-----|-------|--------|
| Switch PM2 to multi-symbol.config.js | ecosystem.config.js | 1 hour |
| Update all 13 components to use `useInstance` | 13 component files | 8 hours |
| Add `?instance=` param to all API calls | 13 component files | 4 hours |

### Priority 1 (Required for Basic Function)

| Fix | Files | Effort |
|-----|-------|--------|
| Update `/api/positions` to filter by instance | positions.py | 2 hours |
| Update `/api/guardian/status` for instance | guardian.py | 2 hours |
| Update `/api/bot/start|stop` for instance | bot_control.py | 2 hours |
| Update `/api/config/flat` for instance | yaml_config_api.py | 2 hours |

### Priority 2 (Required for Production)

| Fix | Files | Effort |
|-----|-------|--------|
| Per-instance guardian processes | guardian_bot.py | 4 hours |
| Per-instance health files | guardian_bot.py | 2 hours |
| Per-instance PnL tracking | pnl_history.py | 4 hours |
| Instance-specific emergency stop | bot_control.py | 2 hours |

### Priority 3 (Nice to Have)

| Fix | Files | Effort |
|-----|-------|--------|
| Portfolio overview with all instances | New component | 8 hours |
| Instance comparison view | New component | 4 hours |
| Batch instance controls | PM2Panel.js | 4 hours |

---

## PART 6: Migration Checklist

### Frontend Migration

```bash
# For each component that uses useSymbol:
1. Replace: import { useSymbol } from '../context/SymbolContext'
   With:    import { useInstance } from '../context/InstanceContext'

2. Replace: const { selectedSymbol } = useSymbol()
   With:    const { selectedInstance, withInstance } = useInstance()

3. Replace: fetch('/api/xyz?symbol=' + selectedSymbol)
   With:    fetch(withInstance('/api/xyz'))

4. Replace: apiClient.getXXX()
   With:    apiClient.getXXX({ instance: selectedInstance })
```

### Backend Migration

```python
# For each route:
1. Add: instance = request.args.get('instance')

2. Parse if needed:
   if instance:
       symbol, mode = instance.split('_')
   else:
       symbol = request.args.get('symbol', 'BTCUSD')
       mode = request.args.get('mode', 'LONG')
       instance = f"{symbol}_{mode}"

3. Use instance in:
   - Database paths: f"bot_events_{instance}.db"
   - Health files: f".guardian_health_{instance}"
   - Monitoring files: f"monitoring_snapshot_{instance}.json"
   - PnL files: f"pnl_history_{instance}.csv"
```

---

## Summary

**The V6.0 multi-instance architecture infrastructure was created but NEVER integrated into the working components.**

| Phase | Status | Reality |
|-------|--------|---------|
| Phase 1: Config Models | ✅ Complete | InstanceConfig exists |
| Phase 2: CLI Arguments | ✅ Complete | --instance argument works |
| Phase 3: Database Paths | ✅ Complete | Bot creates per-instance DBs |
| Phase 4: PM2 Config | ⚠️ Partial | Config exists but not used |
| Phase 5: Backend API | ⚠️ Partial | /api/instances exists, others not updated |
| Phase 6: Frontend | ❌ NOT DONE | Only 1/14 components migrated |
| Phase 7: Guardian RSI | ⚠️ Partial | Config exists, not all paths updated |
| Phase 8: Testing | ❌ NOT DONE | No real multi-instance testing |

**Estimated Remaining Work:** 40-50 hours to complete true multi-instance support
