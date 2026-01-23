# Phase 1: Quick Wins Implementation Plan
**Date:** January 23, 2026  
**Duration:** 5 days  
**Goal:** Maximum impact with minimum effort - Fix payoff calculations, improve panel usability

---

## 🎯 Day 1: Payoff Calculation Fixes (Thursday)

### Morning: Standardize Multipliers & Remove Dividends
**Files to modify:**
1. `webui/frontend/src/components/options/OptionsPayoffDiagram.js` (lines 200-400)
2. `webui/frontend/src/components/strategy/PayoffDiagram.js` (entire file)
3. `webui/frontend/src/components/strategy/StrategyBuilderPanel.js` (lines 500-700)

**Changes:**
- ✅ Replace all hardcoded `0.001` with constant `CONTRACT_VALUE = 0.001`
- ✅ Remove dividend yield (q=0 always for crypto)
- ✅ Verify ETH multiplier from Delta Exchange API

**Task Checklist:**
- [ ] Create `src/utils/constants.js` with `export const CONTRACT_MULTIPLIERS = { BTC: 0.001, ETH: 0.001 }`
- [ ] Replace Black-Scholes calls: remove `dividendYield` parameter
- [ ] Test payoff with 1 BTC option: should show ₹0.001 * price change
- [ ] Commit: "fix: standardize contract multipliers to 0.001"

### Afternoon: Use Exchange Greeks
**Files to modify:**
1. `webui/frontend/src/components/options/OptionsPayoffDiagram.js` (Black-Scholes section)
2. New file: `webui/frontend/src/utils/greeksFromAPI.js`

**Changes:**
- ✅ Fetch Greeks from ticker API instead of calculating
- ✅ Fallback to Black-Scholes only if API fails
- ✅ Cache Greeks to avoid recalculations

**Implementation:**
```javascript
// greeksFromAPI.js
export async function getGreeksFromAPI(symbol) {
  try {
    const response = await fetch(`/api/tickers/${symbol}`);
    const data = await response.json();
    if (data.greeks) {
      return {
        delta: parseFloat(data.greeks.delta),
        gamma: parseFloat(data.greeks.gamma),
        theta: parseFloat(data.greeks.theta),
        vega: parseFloat(data.greeks.vega),
        rho: parseFloat(data.greeks.rho)
      };
    }
  } catch (error) {
    console.warn('Failed to fetch Greeks from API, falling back to calculation');
    return null; // Trigger fallback
  }
}
```

**Task Checklist:**
- [ ] Create `greeksFromAPI.js` utility
- [ ] Modify `OptionsPayoffDiagram.js` to use API Greeks first
- [ ] Add loading state while fetching
- [ ] Test with live option (C-BTC-95000-310125)
- [ ] Commit: "feat: use Delta Exchange API Greeks for 5x speed improvement"

---

## 🎯 Day 2: Probability Overlay & Backend Consolidation (Friday)

### Morning: Simple Probability of Profit
**Files to modify:**
1. `webui/frontend/src/components/options/OptionsPayoffDiagram.js` (add overlay)
2. New file: `webui/frontend/src/utils/probabilityCalc.js`

**Implementation:**
```javascript
// probabilityCalc.js
export function calculatePoP(spotPrice, strike, timeToExpiry, volatility, optionType, side) {
  const d1 = (Math.log(spotPrice / strike) + (0.5 * volatility ** 2) * timeToExpiry) 
             / (volatility * Math.sqrt(timeToExpiry));
  const d2 = d1 - volatility * Math.sqrt(timeToExpiry);
  
  const N_d2 = normalCDF(d2);
  
  if (optionType === 'call') {
    return side === 'buy' ? N_d2 : (1 - N_d2);
  } else {
    return side === 'buy' ? (1 - N_d2) : N_d2;
  }
}
```

**Task Checklist:**
- [ ] Create `probabilityCalc.js` with PoP function
- [ ] Add PoP line to payoff chart (dotted green line)
- [ ] Display PoP percentage in tooltip
- [ ] Test with ATM call option (should show ~50%)
- [ ] Commit: "feat: add probability of profit overlay to payoff chart"

### Afternoon: Consolidate Backend Payoff
**Files to modify:**
1. New file: `webui/backend/options_strategy/payoff_engine.py`
2. Modify: `webui/backend/options_strategy/strategy_definitions.py` (use new engine)

**Implementation:**
```python
# payoff_engine.py
class PayoffEngine:
    @staticmethod
    def calculate_payoff(positions, price_range, use_mark_price=True):
        """
        Single source of truth for all payoff calculations
        
        Args:
            positions: List of position dicts with {symbol, side, size, strike, option_type, entry_price}
            price_range: List of spot prices to calculate for
            use_mark_price: Whether to use mark price from API
            
        Returns:
            {prices: [...], payoffs: [...], greeks: {...}}
        """
        CONTRACT_VALUE = 0.001  # BTC/ETH on Delta Exchange
        
        total_payoffs = [0] * len(price_range)
        
        for position in positions:
            for i, spot in enumerate(price_range):
                intrinsic = calculate_intrinsic(spot, position['strike'], position['option_type'])
                pnl = (intrinsic - position['entry_price']) * position['size'] * CONTRACT_VALUE
                
                if position['side'] == 'sell':
                    pnl *= -1
                    
                total_payoffs[i] += pnl
        
        return {
            'prices': price_range,
            'payoffs': total_payoffs,
            'contract_value': CONTRACT_VALUE
        }
```

**Task Checklist:**
- [ ] Create `payoff_engine.py` with single calculator
- [ ] Migrate `strategy_definitions.py` to use PayoffEngine
- [ ] Update all 3 frontend components to call new backend endpoint
- [ ] Test: compare old vs new payoff (should match exactly)
- [ ] Commit: "refactor: consolidate payoff calculation into single engine"

---

## 🎯 Day 3: Options Panel Visual Improvements (Saturday)

### Morning: Visual Hierarchy & Grouping
**Files to modify:**
1. `webui/frontend/src/components/trading/OptionsPanel.js` (lines 400-800)

**Changes:**
- ✅ Group columns visually with borders/spacing
- ✅ Make Greeks section collapsible
- ✅ Add color coding for P&L

**CSS Changes:**
```css
/* Group 1: Identity */
.column-group-identity {
  border-right: 2px solid #e0e0e0;
  padding-right: 16px;
}

/* Group 2: Pricing */
.column-group-pricing {
  border-right: 2px solid #e0e0e0;
  padding: 0 16px;
}

/* Group 3: Greeks (collapsible) */
.column-group-greeks {
  background-color: #f5f5f5;
  border-radius: 4px;
}

/* Group 4: Actions */
.column-group-actions {
  border-left: 2px solid #e0e0e0;
  padding-left: 16px;
}

/* P&L Colors */
.pnl-positive {
  color: #4caf50;
  font-weight: bold;
}

.pnl-negative {
  color: #f44336;
  font-weight: bold;
}

.near-max-loss {
  background-color: #fff3cd;
}
```

**Task Checklist:**
- [ ] Add CSS classes for column groups
- [ ] Wrap Greek columns in collapsible `<Collapse>` component
- [ ] Add "Show/Hide Greeks" toggle button
- [ ] Apply color classes to P&L cells
- [ ] Highlight rows within 5% of max loss
- [ ] Commit: "ui: improve visual hierarchy in Options panel"

### Afternoon: Quick Filters
**Files to modify:**
1. `webui/frontend/src/components/trading/OptionsPanel.js` (add filter bar)

**Implementation:**
```javascript
// Add at top of OptionsPanel
const [filters, setFilters] = useState({
  expiry: 'all',
  pnl: 'all',  // 'profit', 'loss', 'all'
  moneyness: 'all'  // 'itm', 'atm', 'otm', 'all'
});

const filteredPositions = positions.filter(pos => {
  // Expiry filter
  if (filters.expiry !== 'all' && pos.expiry !== filters.expiry) return false;
  
  // P&L filter
  if (filters.pnl === 'profit' && pos.unrealized_pnl <= 0) return false;
  if (filters.pnl === 'loss' && pos.unrealized_pnl >= 0) return false;
  
  // Moneyness filter
  const moneyness = getMoneyness(pos.strike, spotPrice, pos.option_type);
  if (filters.moneyness !== 'all' && moneyness !== filters.moneyness) return false;
  
  return true;
});

function getMoneyness(strike, spot, type) {
  const diff = Math.abs(strike - spot) / spot;
  if (diff < 0.02) return 'atm';  // Within 2%
  if (type === 'call') {
    return strike > spot ? 'otm' : 'itm';
  } else {
    return strike < spot ? 'otm' : 'itm';
  }
}
```

**UI Mockup:**
```
[Expiry: All ▼] [P&L: All ▼] [Moneyness: All ▼] [Clear Filters]
```

**Task Checklist:**
- [ ] Add filter state and dropdown components
- [ ] Implement filter logic for expiry/P&L/moneyness
- [ ] Add "Clear Filters" button
- [ ] Show filter count badge (e.g., "3 filters active")
- [ ] Test with 20+ positions
- [ ] Commit: "feat: add quick filters to Options panel"

---

## 🎯 Day 4: Futures Panel Improvements (Sunday)

### Morning: Leverage Indicator & Liquidation Warning
**Files to modify:**
1. `webui/frontend/src/components/trading/FuturesPanel.js`
2. New file: `webui/frontend/src/components/indicators/LeverageIndicator.js`

**LeverageIndicator Component:**
```javascript
import { Chip } from '@mui/material';

export function LeverageIndicator({ leverage }) {
  const getColor = () => {
    if (leverage < 3) return 'success';
    if (leverage < 5) return 'warning';
    return 'error';
  };
  
  const getLabel = () => {
    if (leverage < 3) return 'Safe';
    if (leverage < 5) return 'Medium Risk';
    return 'High Risk';
  };
  
  return (
    <div>
      <Chip 
        label={`${leverage}x ${getLabel()}`}
        color={getColor()}
        size="small"
        sx={{ fontWeight: 'bold' }}
      />
    </div>
  );
}
```

**Liquidation Progress Bar:**
```javascript
import { LinearProgress, Box, Typography } from '@mui/material';

export function LiquidationProximity({ currentPrice, liquidationPrice, side }) {
  const distance = side === 'long' 
    ? ((currentPrice - liquidationPrice) / currentPrice) * 100
    : ((liquidationPrice - currentPrice) / currentPrice) * 100;
  
  const normalizedDistance = Math.max(0, Math.min(100, distance * 10)); // 0-10% mapped to 0-100%
  
  const getColor = () => {
    if (distance > 20) return 'success';
    if (distance > 10) return 'warning';
    return 'error';
  };
  
  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="caption">Distance to Liquidation</Typography>
        <Typography variant="caption" fontWeight="bold">{distance.toFixed(2)}%</Typography>
      </Box>
      <LinearProgress 
        variant="determinate" 
        value={normalizedDistance} 
        color={getColor()}
        sx={{ height: 8, borderRadius: 1 }}
      />
    </Box>
  );
}
```

**Task Checklist:**
- [ ] Create `LeverageIndicator.js` component
- [ ] Create `LiquidationProximity.js` component
- [ ] Add to each row in FuturesPanel
- [ ] Show warning alert if distance < 10%
- [ ] Test with high leverage position (10x+)
- [ ] Commit: "feat: add leverage indicator and liquidation warnings to Futures panel"

### Afternoon: Group by Asset
**Files to modify:**
1. `webui/frontend/src/components/trading/FuturesPanel.js`

**Implementation:**
```javascript
import { Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

// Group positions by underlying asset
const groupedPositions = positions.reduce((groups, pos) => {
  const asset = pos.symbol.replace('USD', ''); // BTCUSD -> BTC
  if (!groups[asset]) groups[asset] = [];
  groups[asset].push(pos);
  return groups;
}, {});

// Render
{Object.entries(groupedPositions).map(([asset, positions]) => (
  <Accordion key={asset} defaultExpanded>
    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
      <Typography variant="h6">
        {asset} ({positions.length} positions)
        <Chip 
          label={`Total P&L: ${calculateTotalPnL(positions).toFixed(2)}`}
          color={calculateTotalPnL(positions) > 0 ? 'success' : 'error'}
          sx={{ ml: 2 }}
        />
      </Typography>
    </AccordionSummary>
    <AccordionDetails>
      {/* Render positions table */}
    </AccordionDetails>
  </Accordion>
))}
```

**Task Checklist:**
- [ ] Group positions by underlying asset (BTC, ETH, SOL, etc.)
- [ ] Use Accordion component for each group
- [ ] Show total P&L per asset group
- [ ] Make groups collapsible
- [ ] Save collapse state to localStorage
- [ ] Commit: "feat: group futures positions by underlying asset"

---

## 🎯 Day 5: WebSocket Integration & Testing (Monday)

### Morning: Real-time Greeks via WebSocket
**Files to create:**
1. `webui/frontend/src/hooks/useWebSocketGreeks.js`

**Implementation:**
```javascript
import { useEffect, useState } from 'react';

export function useWebSocketGreeks(symbols) {
  const [greeksData, setGreeksData] = useState({});
  const [connected, setConnected] = useState(false);
  
  useEffect(() => {
    const ws = new WebSocket('wss://socket.india.delta.exchange');
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
      
      // Subscribe to v2/ticker channel
      ws.send(JSON.stringify({
        type: 'subscribe',
        payload: {
          channels: [{
            name: 'v2/ticker',
            symbols: symbols
          }]
        }
      }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'v2/ticker' && data.greeks) {
        setGreeksData(prev => ({
          ...prev,
          [data.symbol]: {
            delta: parseFloat(data.greeks.delta),
            gamma: parseFloat(data.greeks.gamma),
            theta: parseFloat(data.greeks.theta),
            vega: parseFloat(data.greeks.vega),
            rho: parseFloat(data.greeks.rho),
            timestamp: Date.now()
          }
        }));
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };
    
    return () => {
      ws.close();
    };
  }, [symbols]);
  
  return { greeksData, connected };
}
```

**Task Checklist:**
- [ ] Create `useWebSocketGreeks` hook
- [ ] Integrate into OptionsPanel to update Greeks live
- [ ] Add connection status indicator (green dot = connected)
- [ ] Throttle updates to max 1/second to avoid UI lag
- [ ] Test with 10+ option positions
- [ ] Commit: "feat: real-time Greeks updates via WebSocket"

### Afternoon: Testing & Documentation
**Tasks:**
1. **Manual Testing**
   - [ ] Test payoff graph with 5 different option strategies
   - [ ] Test filters with 20+ positions
   - [ ] Test leverage indicator with various leverage levels
   - [ ] Test WebSocket reconnection after disconnect
   - [ ] Test with slow network (throttle to 3G)

2. **Unit Tests** (if time permits)
   - [ ] Test `probabilityCalc.js` - PoP calculation
   - [ ] Test `PayoffEngine` - various strategies
   - [ ] Test filter logic

3. **Documentation**
   - [ ] Update README with new features
   - [ ] Add inline comments to complex functions
   - [ ] Create CHANGELOG entry

4. **Commit & Push**
   - [ ] Final commit: "feat: Phase 1 complete - payoff fixes and panel improvements"
   - [ ] Push to branch `feature/payoff-phase1`
   - [ ] Create tag `phase1-complete`

---

## ✅ Success Metrics

**Before Phase 1:**
- ⏱️ Payoff calculation: ~200ms (frontend Black-Scholes)
- 📊 No probability analysis
- 🎨 Cluttered table UI with 15+ columns
- ❌ No risk indicators

**After Phase 1:**
- ⏱️ Payoff calculation: ~40ms (API Greeks)
- 📊 Probability of Profit displayed
- 🎨 Organized columns with visual groups
- ✅ Leverage & liquidation warnings
- 📡 Real-time Greeks updates
- 🔍 Quick filters for fast navigation

---

## 🚀 Next Steps (Phase 2 - Week 2)

1. Add VaR and CVaR calculations
2. Monte Carlo simulation for Expected Value
3. Multi-time horizon payoff curves
4. Greeks evolution chart
5. Scenario analysis tool

---

## 📝 Notes

**Removed from original plan (not needed for Delta Exchange):**
- ❌ Dividend yield calculations (crypto has no dividends)
- ❌ Binomial Tree model (European options only)
- ❌ American option early exercise logic
- ❌ Market hours handling (crypto trades 24/7)
- ❌ Complex IV surface modeling (use exchange's mark_iv)

**Simplified:**
- ✅ Risk-free rate = 0% (crypto standard)
- ✅ Use exchange's Greeks primarily, calculate only as fallback
- ✅ Settlement price = 30-minute TWAP (from exchange)
