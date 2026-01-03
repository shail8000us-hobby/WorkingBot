# Multi-Symbol WebUI Implementation Summary

**Date:** December 2025  
**Status:** ✅ Complete (Phase 1 - Core Infrastructure)

## Overview

This document summarizes the implementation of multi-symbol support for the GridBot WebUI, transforming it from a single-symbol control panel to a true multi-instrument trading platform.

---

## Backend API Changes

### 1. Guardian Routes (`webui/backend/routes/guardian.py`)

#### RSI Status API - Multi-Symbol Support
```
GET /api/guardian/rsi/status
GET /api/guardian/rsi/status?symbol=BTCUSD
```

- **No parameter:** Returns RSI data for all configured symbols
- **With symbol:** Returns RSI data for specific symbol
- Added `_get_rsi_for_symbol()` helper function
- Reads from symbol-specific RSI log files: `logs/rsi_analyzer_SYMBOL.log`

#### Guardian Status API - Multi-Symbol Support
```
GET /api/guardian/status
GET /api/guardian/status?symbol=BTCUSD
```

- Returns per-symbol data in `symbols` dictionary
- Returns global aggregates in `global` dictionary:
  - `total_capital_inr`: Sum of all symbol capitals
  - `total_pnl_inr`: Sum of all symbol P&Ls
  - `total_loss_inr`: Sum of all symbol losses
  - `enabled_symbols`: List of enabled symbols
- Added `_get_symbols_guardian_data()` and `_get_single_symbol_guardian_data()` helpers

---

### 2. Symbol Config API (`webui/backend/routes/yaml_config_api.py`)

#### Get Symbol-Specific Config
```
GET /api/config/symbols/<symbol>
```
Returns flattened config for specific symbol with field mappings:
- `GRIDBOT_REF` → `grid.geometry.reference`
- `GRIDBOT_STEP` → `grid.geometry.step`
- `GRIDBOT_LOWER` → `grid.geometry.lower`
- `GRIDBOT_UPPER` → `grid.geometry.upper`
- etc.

#### Update Symbol-Specific Config
```
POST /api/config/symbols/<symbol>
Content-Type: application/json
{
  "GRIDBOT_REF": "110000",
  "GRIDBOT_STEP": "1000"
}
```
Saves to correct YAML path: `symbols.<SYMBOL>.grid.geometry...`

#### Enable/Disable Symbol
```
POST /api/config/symbols/<symbol>/enable
POST /api/config/symbols/<symbol>/disable
```
Sets `symbols.<SYMBOL>.enabled` to `true` or `false`

---

### 3. Symbol Process Control (`webui/backend/routes/symbols.py`)

#### Start/Stop Symbol Trading
```
POST /api/symbols/<symbol>/process/start
POST /api/symbols/<symbol>/process/stop
GET /api/symbols/<symbol>/process/status
```

#### Start/Stop All Symbols
```
POST /api/symbols/all/start
POST /api/symbols/all/stop
```
Starts/stops all enabled symbols sequentially.

---

## Frontend Component Changes

### 1. RSIPanel.js - Complete Refactor

**New Features:**
- View mode toggle: "Current Symbol" vs "All Symbols"
- `useSymbol()` hook integration
- `SymbolBadge` component for visual indicator
- `RSISymbolCard` subcomponent for multi-symbol view
- API calls use `?symbol=` parameter

**Key State:**
```javascript
const [viewMode, setViewMode] = useState('current'); // 'current' | 'all'
const { selectedSymbol } = useSymbol();
```

---

### 2. GuardianPanel.js - Multi-Symbol Enhancement

**New Features:**
- Per-symbol loss tracking section
- Symbol-specific risk indicators (Safe/Warning/Critical)
- Global portfolio summary with aggregated totals
- `SymbolBadge` for each monitored symbol
- Uses new multi-symbol Guardian API response structure

**Key Display:**
- Individual symbol cards showing:
  - Position count
  - P&L (color-coded)
  - Loss vs Limit with progress bar
  - Risk status badge

---

### 3. PM2Panel.js - Symbol Grouping

**New Features:**
- "By Symbol" tab view (default)
- Groups processes by symbol (BTCUSD, ETHUSD)
- System processes shown separately
- Per-symbol Start/Stop controls
- "Start All Symbols" / "Stop All Symbols" buttons
- Visual symbol badges with distinct colors

**New Tab:** `activeTab = 'symbol'`

**Process Grouping Logic:**
```javascript
const extractSymbolFromProcess = (processName) => {
  const symbolMatch = processName.match(/-(BTCUSD|ETHUSD|[A-Z]{6})(?:-|$)/i);
  if (symbolMatch) return symbolMatch[1].toUpperCase();
  return null; // System process
};
```

---

### 4. ConfigPanel.js - Symbol-Specific Config

**New Features:**
- Config mode toggle: "Global" vs symbol-specific
- Symbol-specific config fetching via `apiClient.getSymbolConfig()`
- Different save behavior based on mode
- Info banner explaining symbol-specific mode
- Different save button colors for visual distinction

**New State:**
```javascript
const [configMode, setConfigMode] = useState('global'); // 'global' | 'symbol'
const [symbolConfig, setSymbolConfig] = useState({});
```

**Save Logic:**
- Global mode: Uses `onUpdate()` (existing flow)
- Symbol mode: Uses `apiClient.updateSymbolConfig(symbol, values)`

---

### 5. API Client Updates (`webui/frontend/src/utils/apiClient.js`)

**New Methods:**
```javascript
async getSymbolConfig(symbol)
async updateSymbolConfig(symbol, updates)
async enableSymbol(symbol)
async disableSymbol(symbol)
```

---

## CSS Changes

### PM2Panel.css Additions

New styles for:
- `.pm2-notification` - Success/error notification banner
- `.pm2-symbol-view` - Container for symbol view
- `.pm2-all-controls` - Start All / Stop All buttons container
- `.pm2-symbol-groups` - Grid layout for symbol groups
- `.symbol-group` - Individual symbol card
- `.symbol-badge.btcusd` - BTC orange styling
- `.symbol-badge.ethusd` - ETH blue styling
- `.symbol-badge.system` - Purple styling for system processes
- `.mini-process-card` - Compact process display within symbol groups

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        WebUI Frontend                        │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   RSIPanel   │ GuardianPanel│   PM2Panel   │  ConfigPanel   │
│   (view all  │ (per-symbol  │ (group by    │ (global vs     │
│    symbols)  │  loss track) │  symbol)     │  symbol cfg)   │
└──────┬───────┴──────┬───────┴──────┬───────┴───────┬────────┘
       │              │              │               │
       ▼              ▼              ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                    SymbolContext Provider                     │
│              selectedSymbol, symbols[], setSymbol             │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                     Backend API Layer                         │
├────────────────┬─────────────────┬───────────────────────────┤
│  /api/guardian │  /api/config    │  /api/symbols             │
│  /rsi/status   │  /symbols/X     │  /X/process/start|stop    │
│  /status       │  /symbols/X/    │  /all/start|stop          │
│  ?symbol=X     │  enable|disable │                           │
└────────────────┴─────────────────┴───────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    config_v5.yaml                             │
│  symbols:                                                     │
│    BTCUSD:                                                    │
│      enabled: true                                            │
│      grid:                                                    │
│        geometry: { reference, step, lower, upper, ... }       │
│    ETHUSD:                                                    │
│      enabled: true                                            │
│      grid:                                                    │
│        geometry: { ... }                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## Testing Checklist

- [ ] RSI Panel shows all symbols when "All Symbols" view is selected
- [ ] RSI Panel shows only selected symbol when "Current Symbol" is selected
- [ ] Guardian Panel shows per-symbol loss tracking when running
- [ ] Guardian Panel aggregates totals correctly across symbols
- [ ] PM2 Panel "By Symbol" tab groups processes correctly
- [ ] PM2 Panel per-symbol start/stop works
- [ ] PM2 Panel "Start All" / "Stop All" works
- [ ] Config Panel toggle between Global and Symbol mode works
- [ ] Config Panel saves to correct path when in Symbol mode
- [ ] SymbolBadge appears correctly throughout the UI

---

## Files Modified

### Backend (Python)
1. `webui/backend/routes/guardian.py` - Multi-symbol RSI and Guardian status
2. `webui/backend/routes/yaml_config_api.py` - Symbol-specific config endpoints
3. `webui/backend/routes/symbols.py` - Process control endpoints

### Frontend (React/JavaScript)
1. `webui/frontend/src/components/RSIPanel.js` - Complete multi-symbol refactor
2. `webui/frontend/src/components/GuardianPanel.js` - Per-symbol loss tracking
3. `webui/frontend/src/components/PM2Panel.js` - Symbol grouping view
4. `webui/frontend/src/components/ConfigPanel.js` - Global vs symbol config mode
5. `webui/frontend/src/utils/apiClient.js` - Symbol config API methods
6. `webui/frontend/src/components/PM2Panel.css` - Symbol view styles

---

## Next Steps (Phase 2)

1. **Symbol Selector Enhancement**: Add quick-switch buttons in header
2. **Dashboard Multi-Symbol View**: Show all symbols on main dashboard
3. **Position Tracker Per-Symbol**: Separate position views per instrument
4. **Order History Per-Symbol**: Filter historical orders by symbol
5. **Performance Analytics**: Per-symbol P&L charts and metrics

---

*Implementation completed as part of MULTI_INSTRUMENT_CONCRETE_PLAN_DEC2025.md*
