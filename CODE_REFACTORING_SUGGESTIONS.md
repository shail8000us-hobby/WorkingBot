# Code Refactoring Suggestions for Bulky Files

**Date**: January 31, 2026  
**Files**: `OptionsPanel.js` (6,159 lines), `App.js` (1,645 lines)  
**Total**: 7,804 lines

---

## 🔴 Problem: Why These Files Are Too Large

### `OptionsPanel.js` (6,159 lines)

This file has become a **"God Component"** containing:
- Position table rendering
- Order placement logic
- Max loss management
- SL/TP management
- Greeks display
- Multiple dialogs
- API calls
- State management
- Formatting utilities
- Sound effects
- Real-time updates

**Issues:**
- Hard to navigate
- Difficult to test
- Slow to edit (VS Code struggles)
- High cognitive load
- Merge conflicts in team work

### `App.js` (1,645 lines)

Contains too much for a root component:
- All route definitions
- Tab rendering logic
- Theme configuration
- Global state
- LazyLoad wrappers
- Navigation logic

---

## 🟢 Recommended Refactoring Strategy

### Phase 1: Extract Utility Functions (Low Risk)

Create `/utils/` directory for shared logic:

```
webui/frontend/src/utils/
├── formatters.js          # fmtFixed, fmtLocale, toFiniteNumber
├── priceUtils.js          # resolveBidAsk, calculateSpread
├── optionSymbolParser.js  # parseSymbol, getOptionType, getExpiry
├── pnlCalculator.js       # calculatePnL, calculateRoi
├── validationUtils.js     # isValidOrder, validateSize
└── dateUtils.js           # formatExpiry, daysToExpiry
```

**Effort**: Low (1-2 hours)  
**Risk**: Very Low  
**Impact**: -200 lines from OptionsPanel

---

### Phase 2: Extract Reusable Components (Medium Risk)

Create sub-components for OptionsPanel:

```
webui/frontend/src/components/options/
├── OptionsPanel.js         # Main container (reduced)
├── PositionTable/
│   ├── PositionTable.js    # Table wrapper
│   ├── PositionRow.js      # Single row rendering
│   ├── PositionActions.js  # Buy/Sell/Close buttons
│   └── index.js
├── OrderPlacement/
│   ├── OrderDialog.js      # Add position dialog
│   ├── CloseDialog.js      # Close position dialog
│   ├── SSROrderPanel.js    # SSR-specific UI
│   └── OrderTypeSelector.js
├── Indicators/
│   ├── SLTPIndicator.js    # Already exists ✓
│   ├── MaxLossIndicator.js # Already exists ✓
│   ├── PoPIndicator.js     # Probability of Profit
│   └── GreeksDisplay.js    # Delta, Gamma, Theta, Vega
└── Watchlist/
    ├── OptionsWatchlist.js
    └── WatchlistRow.js
```

**Effort**: Medium (4-6 hours)  
**Risk**: Medium  
**Impact**: -2000 lines from OptionsPanel

---

### Phase 3: Extract Custom Hooks (Medium Risk)

Move state logic to hooks:

```
webui/frontend/src/hooks/
├── useOptionsPositions.js   # Position fetching & state
├── useOrderPlacement.js     # Order execution logic
├── useSLTPManagement.js     # SL/TP settings
├── useMaxLossManagement.js  # Max loss settings
├── useRealTimePrices.js     # WebSocket price updates
├── useSSROrder.js           # SSR order tracking
└── useNotifications.js      # Sound & alerts
```

**Example - useOptionsPositions.js:**
```javascript
export const useOptionsPositions = () => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/options/positions');
      setPositions(response.data.positions);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000);
    return () => clearInterval(interval);
  }, [fetchPositions]);
  
  return { positions, loading, error, refetch: fetchPositions };
};
```

**Effort**: Medium (3-4 hours)  
**Risk**: Medium  
**Impact**: -1000 lines from OptionsPanel

---

### Phase 4: Refactor App.js (Low Risk)

**Current Structure:**
```
App.js
├── Theme configuration
├── Route definitions
├── Tab configuration
├── Tab rendering
└── Everything else
```

**Proposed Structure:**
```
App.js                      # Just provider wrapper
├── config/
│   ├── theme.js           # Theme configuration
│   └── routes.js          # Route definitions
├── components/layout/
│   ├── MainLayout.js      # Layout wrapper
│   ├── TabNavigation.js   # Tab bar
│   └── TabPanel.js        # Tab content
└── pages/
    ├── OptionsPage.js     # Options trading page
    ├── MVStraddlePage.js  # MV Straddle page
    └── ...
```

**New App.js (simplified):**
```javascript
import { ThemeProvider } from './providers/ThemeProvider';
import { MainLayout } from './components/layout/MainLayout';
import routes from './config/routes';

function App() {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <MainLayout routes={routes} />
      </ErrorBoundary>
    </ThemeProvider>
  );
}
```

**Effort**: Medium (2-3 hours)  
**Risk**: Low  
**Impact**: -800 lines from App.js

---

## 📋 Recommended Order of Execution

### Sprint 1 (This Week) - Low Risk
1. ✅ Extract `formatters.js` utility
2. ✅ Extract `priceUtils.js` utility
3. ✅ Extract `optionSymbolParser.js` utility
4. ✅ Move theme config to separate file

### Sprint 2 (Next Week) - Medium Risk
1. Extract `PositionRow.js` component
2. Extract `OrderDialog.js` component
3. Extract `useOptionsPositions` hook
4. Extract `useOrderPlacement` hook

### Sprint 3 (Week After) - Higher Impact
1. Full PositionTable extraction
2. App.js route/layout refactor
3. Custom hooks for all state

---

## ⚠️ Refactoring Rules (CRITICAL)

### DO:
1. **One change at a time**: Extract one utility/component, test, commit
2. **Keep functionality identical**: No feature changes during refactor
3. **Write tests first**: Cover existing behavior before extracting
4. **Git commit after each extraction**: Small, atomic commits
5. **Test after each change**: Run full test suite

### DON'T:
1. ❌ Don't refactor during active trading hours
2. ❌ Don't change trading logic while extracting
3. ❌ Don't combine multiple extractions in one commit
4. ❌ Don't rename variables during extraction
5. ❌ Don't "improve" code while extracting

---

## 🔧 Quick Wins (Can Do Now)

### 1. Extract formatters (15 minutes)

Create `/utils/formatters.js`:
```javascript
// Move from OptionsPanel.js lines ~100-150
export const toFiniteNumber = (v) => { ... };
export const fmtFixed = (v, decimals = 2) => { ... };
export const fmtLocale = (v) => { ... };
```

### 2. Extract price utilities (15 minutes)

Create `/utils/priceUtils.js`:
```javascript
// Move from OptionsPanel.js lines ~150-200
export const resolveBidAskFromTicker = (ticker) => { ... };
export const calculateSpread = (bid, ask) => { ... };
```

### 3. Move theme to config (10 minutes)

Create `/config/theme.js`:
```javascript
// Move from App.js lines ~50-100
export const darkTheme = createTheme({ ... });
```

---

## 📊 Expected Results After Refactoring

| File | Before | After Phase 1 | After Phase 3 |
|------|--------|---------------|---------------|
| OptionsPanel.js | 6,159 | 5,800 (-350) | 2,500 (-3,659) |
| App.js | 1,645 | 1,500 (-145) | 800 (-845) |
| **New files created** | 0 | 5 | 15+ |
| **Total lines** | 7,804 | 7,800 | 8,500 |

Note: Total lines increase because of boilerplate (imports, exports), but each file is smaller and more focused.

---

## 🎯 Target Architecture

```
src/
├── App.js                    # 200 lines (just providers)
├── config/
│   ├── theme.js              # 100 lines
│   ├── routes.js             # 50 lines
│   └── constants.js          # API URLs, etc.
├── hooks/
│   ├── useOptionsPositions.js
│   ├── useOrderPlacement.js
│   └── ...                   # 10-15 hooks
├── utils/
│   ├── formatters.js
│   ├── priceUtils.js
│   └── ...                   # 5-10 utilities
├── components/
│   ├── layout/               # App shell
│   ├── options/              # ~1500 lines total (split into 10 files)
│   ├── mvStraddle/           # ~1000 lines total (already ok)
│   └── shared/               # Reusable components
└── pages/
    ├── OptionsPage.js
    └── ...
```

---

## 💡 Summary

**Don't do everything at once!** Start with:

1. **Today**: Extract formatters.js (15 min)
2. **Tomorrow**: Extract priceUtils.js (15 min)
3. **This week**: Extract theme.js (10 min)
4. **Next week**: Start on PositionRow.js

Each small extraction reduces cognitive load and makes future work easier.

**Rule of thumb**: If a file is over 500 lines, it's doing too much.

---

**Priority**: Medium (not urgent, but will pay dividends)  
**Estimated Total Effort**: 15-20 hours over 2-3 weeks  
**Risk**: Low if done incrementally
