# Options Chain Development Plan

**Project:** Options Chain Market Data Scanner  
**Date:** January 5, 2026  
**Goal:** Build a completely isolated options chain viewer with real-time market data from Delta Exchange  
**Risk Level:** LOW (fully isolated from existing trading system)

---

## 🎯 Project Overview

Create a standalone options chain module that displays all available strikes, IVs, volumes, and OI for BTC/ETH options without interfering with existing position trading features.

---

## 📂 File Structure

```
webui/
├── backend/
│   ├── options/                     # EXISTING - Don't touch
│   │   └── options_routes.py
│   │
│   └── options_chain/               # NEW MODULE
│       ├── __init__.py
│       ├── chain_routes.py          # Flask routes for chain API
│       ├── chain_service.py         # Delta Exchange API integration
│       ├── chain_cache.py           # Cache layer (Redis or in-memory)
│       ├── chain_models.py          # Data models/schemas
│       └── chain_utils.py           # Helper functions
│
└── frontend/src/
    ├── components/
    │   ├── options/                 # EXISTING - Don't touch
    │   │   └── OptionsPanel.js
    │   │
    │   └── optionsChain/            # NEW MODULE
    │       ├── OptionsChainPanel.js    # Main container
    │       ├── ChainTable.js           # Strike table display
    │       ├── ChainFilters.js         # Expiry/underlying filters
    │       ├── ChainHeader.js          # Info bar (ATM, spot price)
    │       ├── ChainRow.js             # Single strike row
    │       └── services/
    │           ├── chainAPI.js         # API client (isolated)
    │           └── chainWebSocket.js   # Real-time updates (Phase 3)
    │
    └── utils/
        └── optionsChainHelpers.js   # Shared formatters (IV, Greeks)
```

---

## 🚀 Phase-wise Development

### **PHASE 1: Backend Foundation (4-6 hours)**

**Goal:** Create API endpoints to fetch options chain data from Delta Exchange

#### 1.1 Setup Module Structure (30 mins)
- [ ] Create `webui/backend/options_chain/` directory
- [ ] Add `__init__.py` with blueprint registration
- [ ] Register blueprint in main Flask app (with feature flag)

#### 1.2 Delta Exchange API Integration (2 hours)
**File:** `chain_service.py`

```python
class OptionsChainService:
    """
    Fetch all available option products from Delta Exchange
    """
    
    Methods needed:
    - get_all_products(underlying='BTC')           # Fetch all option contracts
    - get_chain_data(underlying, expiry)           # Get chain for specific expiry
    - get_market_data(symbols)                     # Batch fetch bid/ask/iv/volume
    - get_expirations(underlying)                  # List available expiries
    - parse_option_symbol(symbol)                  # Parse P-BTC-99000-30012026
```

**Delta Exchange API Endpoints:**
- `GET /products` - All available products
- `GET /orderbook/{symbol}` - Bid/Ask spreads
- `GET /tickers` - Volume, OI, mark price, IV

#### 1.3 Caching Layer (1 hour)
**File:** `chain_cache.py`

**Why:** Options chain has 100+ strikes, fetching every time is slow

```python
Strategy:
- Cache product list: 5 minutes TTL
- Cache chain data: 10 seconds TTL
- Cache market data: 5 seconds TTL
- Use in-memory dict or Redis
```

#### 1.4 API Routes (1 hour)
**File:** `chain_routes.py`

```python
Endpoints:
GET /api/options-chain/expirations?underlying=BTC
    Response: ["09/01/2026", "30/01/2026", "27/02/2026"]

GET /api/options-chain/data?underlying=BTC&expiry=30012026
    Response: {
        "spot_price": 93113,
        "atm_strike": 93000,
        "chains": [
            {
                "strike": 91000,
                "call": { bid, ask, iv, volume, oi, mark_price, delta, gamma },
                "put": { bid, ask, iv, volume, oi, mark_price, delta, gamma }
            },
            ...
        ]
    }

GET /api/options-chain/refresh?underlying=BTC&expiry=30012026
    Force cache refresh
```

#### 1.5 Testing (1 hour)
- [ ] Test with Postman/curl
- [ ] Verify Delta Exchange API responses
- [ ] Test caching behavior
- [ ] Error handling (API down, invalid expiry)

**Phase 1 Deliverables:**
- ✅ Working backend API
- ✅ Tested with real Delta Exchange data
- ✅ No frontend yet (safe)

---

### **PHASE 2: Frontend UI (6-8 hours)**

**Goal:** Build beautiful, responsive options chain table

#### 2.1 Setup Component Structure (30 mins)
- [ ] Create `components/optionsChain/` directory
- [ ] Add to App.js as new tab (with feature flag)
- [ ] Basic layout scaffold

#### 2.2 Filters & Controls (1.5 hours)
**File:** `ChainFilters.js`

```javascript
Features:
- Underlying selector: BTC | ETH
- Expiry dropdown: Load from /api/options-chain/expirations
- Moneyness filter: All | ATM ±5% | ATM ±10% | Custom range
- Refresh button + auto-refresh toggle (5s/10s/30s)
- Show/hide: Volume, OI, Greeks, IV
```

#### 2.3 Chain Table (3 hours)
**File:** `ChainTable.js` + `ChainRow.js`

```javascript
Table Layout (Desktop):

┌─────────┬────────────────────────┬─────────┬────────────────────────┐
│         │     CALLS (BUY)        │ STRIKE  │     PUTS (BUY)         │
├─────────┼────────────────────────┼─────────┼────────────────────────┤
│  Delta  │  Bid  │  Ask  │   IV   │ $99,000 │   IV   │  Bid  │  Ask  │
│  0.85   │ $234  │ $238  │  68%   │         │  45%   │  $42  │  $45  │
│  ATM    │ $180  │ $184  │  70%   │ $93,000 │  70%   │ $180  │ $184  │
│  0.15   │  $38  │  $42  │  72%   │ $87,000 │  90%   │ $650  │ $660  │
└─────────┴────────────────────────┴─────────┴────────────────────────┘

Features:
- Highlight ATM row (yellow background)
- Color coding: ITM (green), OTM (gray)
- Click row to expand → Show Greeks, Volume, OI
- Hover tooltips for definitions
- Responsive design (mobile: stack calls/puts)
```

#### 2.4 Header Info Bar (1 hour)
**File:** `ChainHeader.js`

```javascript
Display:
┌──────────────────────────────────────────────────────┐
│ BTC Spot: $93,113  │  ATM Strike: $93,000           │
│ Expiry: 30 Jan 2026  │  DTE: 25 days                │
│ Total Calls OI: 1,234  │  Total Puts OI: 2,345      │
└──────────────────────────────────────────────────────┘
```

#### 2.5 API Integration (1.5 hours)
**File:** `services/chainAPI.js`

```javascript
class OptionsChainAPI {
    getExpirations(underlying)
    getChainData(underlying, expiry)
    refreshChain(underlying, expiry)
}

// Independent from options trading API
// No shared state with OptionsPanel.js
```

#### 2.6 State Management (1 hour)
```javascript
State structure:
{
    underlying: 'BTC',
    expiry: '30012026',
    chainData: [...],
    spotPrice: 93113,
    atmStrike: 93000,
    loading: false,
    error: null,
    filters: {
        moneynessRange: 0.05,  // ATM ±5%
        showGreeks: true,
        showVolume: true
    },
    autoRefresh: {
        enabled: true,
        interval: 10000  // 10s
    }
}
```

**Phase 2 Deliverables:**
- ✅ Working options chain UI
- ✅ Real-time data display
- ✅ Fully isolated from trading features
- ✅ Feature flag controlled

---

### **PHASE 3: Advanced Features (4-6 hours - OPTIONAL)**

#### 3.1 Real-time WebSocket Updates (2 hours)
**File:** `chainWebSocket.js`

```javascript
Features:
- Subscribe to ticker updates for visible strikes
- Update bid/ask/iv in real-time
- Flash animation on price changes
- Auto-reconnect on disconnect
```

#### 3.2 Quick Trade Integration (2 hours)
```javascript
Click on Bid/Ask → Open quick trade dialog
Pre-fill:
- Symbol
- Side (BUY)
- Price (bid/ask)
- Quantity (default 1)
- One-click execute
```

#### 3.3 Analytics & Visualization (2 hours)
```javascript
Features:
- IV Skew chart (strike vs IV)
- Volume distribution bars
- Put/Call Ratio indicator
- Greeks heatmap
```

---

## 🔧 Technical Requirements

### Backend Dependencies
```python
# Existing (reuse)
from delta_exchange_api import DeltaExchangeAPI

# New (if needed)
redis==4.5.0  # For caching (optional)
```

### Frontend Dependencies
```javascript
// Already available in package.json
@mui/material
@mui/icons-material
axios
react, react-router-dom
```

---

## 🧪 Testing Strategy

### Backend Testing
```bash
# Test chain API
curl http://localhost:5555/api/options-chain/expirations?underlying=BTC

# Test chain data
curl http://localhost:5555/api/options-chain/data?underlying=BTC&expiry=30012026

# Test caching (should be faster second time)
time curl http://localhost:5555/api/options-chain/data?underlying=BTC&expiry=30012026
```

### Frontend Testing
- [ ] Load different expiries (9/1/2026, 30/1/2026, 27/2/2026)
- [ ] Switch between BTC/ETH
- [ ] Test filters (moneyness, Greeks visibility)
- [ ] Test auto-refresh (watch network tab)
- [ ] Mobile responsive layout
- [ ] Error states (backend down, invalid expiry)

---

## 🚦 Feature Flags & Rollout

```python
# backend/config.py
FEATURE_FLAGS = {
    'options_chain': os.getenv('ENABLE_OPTIONS_CHAIN', 'false') == 'true'
}
```

```javascript
// frontend/src/utils/featureFlags.js
export const FEATURES = {
    OPTIONS_CHAIN: process.env.REACT_APP_ENABLE_OPTIONS_CHAIN === 'true'
};
```

**Rollout Plan:**
1. Deploy backend with flag OFF
2. Test on staging/dev
3. Enable for internal testing
4. Production rollout

---

## 📊 Performance Considerations

### Data Volume
- BTC options: ~100 strikes per expiry
- ETH options: ~80 strikes per expiry
- Total API calls per refresh: 1 (with proper caching)

### Optimization Strategies
1. **Caching:** Reduce Delta Exchange API calls
2. **Virtualization:** Render only visible rows (react-window)
3. **Debouncing:** Limit filter change updates
4. **Lazy loading:** Load Greeks/Volume on demand
5. **WebSocket:** Replace polling in Phase 3

---

## ✅ Success Criteria

**Phase 1 (Backend):**
- [ ] Can fetch all BTC/ETH option products
- [ ] Chain data returns in <500ms
- [ ] Caching reduces API calls by 90%

**Phase 2 (Frontend):**
- [ ] Display full chain for any expiry
- [ ] Update every 10 seconds
- [ ] No interference with existing options trading
- [ ] Mobile responsive

**Phase 3 (Advanced):**
- [ ] Real-time updates via WebSocket
- [ ] Quick trade integration
- [ ] Analytics visualizations

---

## 🔗 Integration Points (Minimal)

### What to share:
- ✅ Delta Exchange API client (connection only)
- ✅ Notification service (alerts)
- ✅ Material-UI theme
- ✅ Utils (formatters)

### What NOT to share:
- ❌ Position state management
- ❌ Trading execution logic
- ❌ Automation monitor
- ❌ Order executor

---

## 📝 API Documentation

### Delta Exchange API References
```
Products API: https://docs.delta.exchange/#get-products
Tickers API: https://docs.delta.exchange/#get-tickers
Orderbook API: https://docs.delta.exchange/#get-l2-orderbook
```

---

## 🎯 Next Steps

1. **Review this plan** - Adjust phases if needed
2. **Phase 1 implementation** - Backend API (4-6 hours)
3. **Backend testing** - Verify Delta Exchange integration
4. **Phase 2 implementation** - Frontend UI (6-8 hours)
5. **Integration testing** - End-to-end workflow
6. **Phase 3 (optional)** - Advanced features

---

## 🚨 Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Delta Exchange rate limits | Implement aggressive caching (10s TTL) |
| Large data volume | Paginate or limit to ATM ±20% by default |
| Breaking existing features | Complete module isolation + feature flags |
| Performance issues | Virtualized table, lazy loading |
| API changes | Version lock, error handling, fallbacks |

---

## 📈 Future Enhancements (Post-Launch)

- [ ] Options screener (filter by IV, volume, OI)
- [ ] Historical IV charts
- [ ] Unusual activity alerts
- [ ] Strategy builder integration (link to Option_strategy.md)
- [ ] Export chain to CSV
- [ ] Compare multiple expiries side-by-side
- [ ] Greeks scenarios (what-if analysis)

---

**Estimated Total Time:** 10-14 hours (Basic), 14-20 hours (Advanced)  
**Complexity:** MEDIUM  
**Risk to Production:** LOW (isolated module)  
**Priority:** HIGH (valuable market data tool)
