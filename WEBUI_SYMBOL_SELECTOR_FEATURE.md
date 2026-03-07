# Symbol Selector Feature - WebUI Configuration Panel

## Overview
Added a symbol selector to the Grid Geometry & Direction section that allows users to easily switch between BTCUSD and ETHUSD configurations in the webUI.

**Date:** January 3, 2026  
**Location:** [webui/frontend/src/components/ConfigPanel.js](webui/frontend/src/components/ConfigPanel.js)

## Features

### Symbol Selector Toggle
- **Location**: Top of Grid Geometry & Direction section
- **Options**: BTCUSD | ETHUSD
- **Style**: Segmented toggle buttons with visual highlighting
  - BTCUSD: Blue theme (#2196F3)
  - ETHUSD: Purple theme (#9C27B0)
- **Auto-load**: Switching symbols automatically loads that symbol's configuration

### Functionality

#### 1. **Symbol Switching**
- Click BTCUSD or ETHUSD to switch active configuration
- Shows loading indicator while fetching symbol config
- Warns if you have unsaved changes before switching
- Automatically updates `GRIDBOT_SYMBOL` field to match selected symbol

#### 2. **Configuration Loading**
- Fetches symbol-specific config from backend: `/api/config/symbols/{symbol}`
- Loads all grid parameters for the selected symbol:
  - Reference Price, Lower/Upper Bounds
  - Step Size, Lot Size, Max Positions
  - Grid Mode (LONG/SHORT)
  - All other symbol-specific settings

#### 3. **Independent Editing**
- Each symbol has its own configuration
- Changes to BTCUSD don't affect ETHUSD (and vice versa)
- Save button saves only the currently active symbol's config

#### 4. **Unsaved Changes Protection**
- Prompts before switching if you have unsaved changes
- Example: "You have unsaved changes for BTCUSD. Switch to ETHUSD anyway?"

## Usage

### Basic Workflow

1. **Select Symbol**
   - Click **BTCUSD** or **ETHUSD** button at top of Grid Geometry section
   - Wait for config to load (loading indicator appears)

2. **View Configuration**
   - All fields populate with symbol-specific values
   - Grid span shows range for selected symbol
   - Mode indicator shows LONG/SHORT for that symbol

3. **Edit Settings**
   - Modify any configuration field
   - Changes apply only to the active symbol
   - Changed fields highlight in orange

4. **Save**
   - Click **Save Configuration** button
   - Saves only the active symbol (BTCUSD or ETHUSD)
   - Success message confirms: "✅ Configuration for BTCUSD saved successfully!"

### Example: Configuring Both Symbols

**Step 1: Configure BTCUSD**
```
1. Select: BTCUSD
2. Set: Reference Price = 88500
3. Set: Lower = 85000, Upper = 95000
4. Set: Step = 500, Lot = 5
5. Set: Mode = LONG
6. Click: Save Configuration
```

**Step 2: Configure ETHUSD**
```
1. Select: ETHUSD
2. Set: Reference Price = 3500
3. Set: Lower = 3200, Upper = 3800
4. Set: Step = 50, Lot = 10
5. Set: Mode = LONG
6. Click: Save Configuration
```

## Technical Details

### State Management
```javascript
const [activeSymbol, setActiveSymbol] = useState('BTCUSD');
const [symbolConfig, setSymbolConfig] = useState({});
const [symbolConfigLoading, setSymbolConfigLoading] = useState(false);
```

### API Endpoint
```javascript
// GET symbol configuration
GET /api/config/symbols/BTCUSD
GET /api/config/symbols/ETHUSD

// Response format
{
  "success": true,
  "symbol": "BTCUSD",
  "config": {
    "GRIDBOT_REF": 88500,
    "GRIDBOT_LOWER": 85000,
    "GRIDBOT_UPPER": 95000,
    ...
  }
}

// POST symbol configuration
POST /api/config/symbols/BTCUSD
Body: { config values }
```

### Component Changes
- Added `activeSymbol` state for tracking selected symbol
- Added `handleSymbolChange()` callback with unsaved changes check
- Added symbol selector UI with toggle buttons
- Modified `fetchSymbolConfig()` to accept symbol parameter
- Modified `handleSave()` to use `activeSymbol` instead of `selectedSymbol`

## UI/UX

### Visual Design
```
┌─────────────────────────────────────────┐
│ Symbol                                  │
│ ┌─────────────┬─────────────┐          │
│ │  BTCUSD ✓   │   ETHUSD    │          │  ← Toggle buttons
│ └─────────────┴─────────────┘          │
│                                         │
│ Trading Direction                       │
│ ┌─────────────┬─────────────┐          │
│ │  LONG ✓     │   SHORT     │          │
│ └─────────────┴─────────────┘          │
│                                         │
│ Reference Price         Symbol          │
│ 88500 USD              BTCUSD           │
│                                         │
│ Lower Bound            Upper Bound      │
│ 85000 USD              95000 USD        │
│                                         │
│ Grid Span: 85,000 → 95,000 (10,000 USD)│
└─────────────────────────────────────────┘
```

### Color Scheme
- **BTCUSD**: Blue (#2196F3) - Associated with Bitcoin
- **ETHUSD**: Purple (#9C27B0) - Associated with Ethereum
- **LONG**: Green (#4CAF50) - Bullish
- **SHORT**: Red (#F44336) - Bearish

### Loading State
```
Symbol
┌─────────────┬─────────────┐
│  BTCUSD ✓   │   ETHUSD    │
└─────────────┴─────────────┘
[ Loading configuration... ]  ← Shown while fetching
```

## Backend Requirements

### Endpoints Used
1. **GET** `/api/config/symbols/{symbol_name}` - Fetch symbol config
2. **POST** `/api/config/symbols/{symbol_name}` - Save symbol config

### Config File Structure
Reads from [config.yaml](config.yaml):
```yaml
symbols:
  BTCUSD:
    enabled: true
    product_id: 27
    mode: LONG
    grid:
      geometry:
        reference: 88500
        lower: 85000
        upper: 95000
        step: 500
    ...
  ETHUSD:
    enabled: true
    product_id: 3136
    mode: LONG
    grid:
      geometry:
        reference: 3500
        lower: 3200
        upper: 3800
        step: 50
    ...
```

## Benefits

✅ **Easy Symbol Switching** - One click to switch between symbols  
✅ **Visual Clarity** - Clear indication of active symbol with color coding  
✅ **Safety** - Warns before losing unsaved changes  
✅ **Isolation** - Each symbol's config is independent  
✅ **Efficiency** - No need to navigate away or reload page  
✅ **Consistency** - GRIDBOT_SYMBOL field auto-updates to match selection  

## Future Enhancements

### Potential Additions
- Add more symbols (e.g., SOLUSD, ADAUSD)
- Show current market price for selected symbol
- Display symbol-specific trading status (online/offline)
- Add symbol performance metrics (PnL, positions count)
- Support custom symbol addition
- Multi-symbol side-by-side comparison view

### Code Location
File: `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/ConfigPanel.js`
Lines: ~68-85 (state), ~96-116 (symbol change handler), ~678-715 (UI component)

## Testing

### Manual Test Steps
1. Open webUI: http://localhost:5555
2. Navigate to Configuration panel
3. Check symbol selector appears at top of Grid Geometry
4. Click BTCUSD - verify config loads
5. Click ETHUSD - verify different config loads
6. Modify BTCUSD setting - click Save
7. Switch to ETHUSD - verify BTCUSD changes don't affect it
8. Modify ETHUSD setting without saving
9. Try switching to BTCUSD - verify warning appears
10. Confirm - verify switch happens and changes lost

### Expected Results
- ✅ Symbol selector renders correctly
- ✅ Config loads for each symbol
- ✅ Changes save independently
- ✅ Warning shows for unsaved changes
- ✅ Loading indicator appears during fetch
- ✅ GRIDBOT_SYMBOL field updates automatically

## Related Documentation
- [MULTI_SYMBOL_FIX_JAN3_2026.md](MULTI_SYMBOL_FIX_JAN3_2026.md) - Core multi-symbol system fixes
- [MULTI_SYMBOL_QUICK_REF.md](MULTI_SYMBOL_QUICK_REF.md) - Quick reference for multi-symbol trading
- [WEBUI_MULTI_SYMBOL_SETUP_JAN3_2026.md](WEBUI_MULTI_SYMBOL_SETUP_JAN3_2026.md) - WebUI integration guide
