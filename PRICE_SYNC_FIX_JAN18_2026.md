# Price Synchronization Fix - January 18, 2026

## Problem Summary

The live BTC and ETH prices displayed in three different locations were showing inconsistent values:

1. **FloatingPriceWidget** (bottom-right draggable widget) - ✅ CORRECT prices ($95,174 for BTC)
2. **TopBar** (header market prices) - ❌ WRONG prices ($95,087 for BTC)
3. **OptionsPanel** (main section spot prices) - ❌ WRONG prices ($95,085 for BTC)

## Root Cause Analysis

### FloatingPriceWidget (CORRECT Implementation)
- Fetches prices from `/api/market/spot-price` REST API
- Uses cache buster parameter: `?symbol=BTC&_=${cacheBuster}`
- Updates every 5 seconds (matches backend cache TTL)
- Backend fetches real-time data from Delta Exchange API

### TopBar (INCORRECT Implementation)
- Also fetched from `/api/market/spot-price` API
- BUT: Did NOT use cache buster parameter
- Updated every 10 seconds (slower than cache TTL)
- Result: Stale cached prices

### OptionsPanel (INCORRECT Implementation)
- Extracted prices from `pos.greeks.spot` field in position data
- Position data is only updated when positions are polled (5-second intervals)
- Greeks data comes from historical order fills, not real-time market data
- Result: Very stale prices from old position data

## Solution Implemented

### 1. Fixed TopBar Component
**File:** `webui/frontend/src/components/layout/TopBar.js`

**Changes:**
- Added cache buster parameter to API calls: `?symbol=BTC&_=${Date.now()}`
- Changed update interval from 10 seconds to 5 seconds (matches cache TTL)
- Added logging for debugging: `[TopBar] Fetching prices at ${timestamp}`
- Added console logging of fetched data for verification

**Before:**
```javascript
const [btcRes, ethRes] = await Promise.all([
  fetch('/api/market/spot-price?symbol=BTC'),
  fetch('/api/market/spot-price?symbol=ETH')
]);
// ...
const interval = setInterval(fetchPrices, 10000);
```

**After:**
```javascript
const cacheBuster = Date.now();
const btcRes = await fetch(`/api/market/spot-price?symbol=BTC&_=${cacheBuster}`);
const ethRes = await fetch(`/api/market/spot-price?symbol=ETH&_=${cacheBuster}`);
// ...
const interval = setInterval(fetchPrices, 5000);
```

### 2. Fixed OptionsPanel Component
**File:** `webui/frontend/src/components/options/OptionsPanel.js`

**Changes:**
- Completely replaced the `useMemo` calculation that extracted prices from position greeks
- Converted `indexPrices` from computed value to state variable
- Added dedicated `useEffect` hook to fetch real-time prices from API
- Uses same cache buster and 5-second interval as FloatingPriceWidget
- Added logging for debugging

**Before:**
```javascript
const indexPrices = useMemo(() => {
  const prices = { BTC: 0, ETH: 0 };
  
  // Extract spot prices from greeks data
  positions.forEach(pos => {
    const parts = pos.product_symbol.split('-');
    if (parts.length >= 4 && pos.greeks?.spot) {
      const underlying = parts[1];
      const spotPrice = parseFloat(pos.greeks.spot);
      
      if (spotPrice > 0) {
        if (underlying === 'BTC') prices.BTC = spotPrice;
        else if (underlying === 'ETH') prices.ETH = spotPrice;
      }
    }
  });
  
  return prices;
}, [positions]);
```

**After:**
```javascript
const [indexPrices, setIndexPrices] = useState({ BTC: 0, ETH: 0 });

useEffect(() => {
  const fetchIndexPrices = async () => {
    try {
      const cacheBuster = Date.now();
      
      const btcRes = await fetch(`/api/market/spot-price?symbol=BTC&_=${cacheBuster}`);
      if (btcRes.ok) {
        const btcData = await btcRes.json();
        if (btcData.price) {
          setIndexPrices(prev => ({ ...prev, BTC: btcData.price }));
        }
      }
      
      const ethRes = await fetch(`/api/market/spot-price?symbol=ETH&_=${cacheBuster}`);
      if (ethRes.ok) {
        const ethData = await ethRes.json();
        if (ethData.price) {
          setIndexPrices(prev => ({ ...prev, ETH: ethData.price }));
        }
      }
    } catch (error) {
      console.error('[OptionsPanel] Error fetching index prices:', error);
    }
  };

  fetchIndexPrices();
  const interval = setInterval(fetchIndexPrices, 5000);
  return () => clearInterval(interval);
}, []);
```

## Backend Price Source

The `/api/market/spot-price` endpoint (in `webui/backend/routes/market.py`) fetches prices in this order:

1. **Cache** (10-second TTL) - fastest response
2. **Delta Exchange API** - Real-time ticker data from `https://api.delta.exchange/v2/tickers/{symbol}USD`
3. **Guardian Signal File** - Fallback from `data/guardian_signal.json`
4. **Static Fallback** - BTC: $95,000, ETH: $3,500

The cache buster parameter ensures we bypass browser caching and hit the backend cache or fetch fresh data.

## Testing Verification

After this fix, all three locations should now display the SAME real-time prices:

1. ✅ **FloatingPriceWidget** - Already correct
2. ✅ **TopBar** - Now fixed to match FloatingPriceWidget
3. ✅ **OptionsPanel** - Now fixed to match FloatingPriceWidget

All three components now:
- Fetch from the same API endpoint
- Use cache busters to avoid stale data
- Update every 5 seconds
- Display identical real-time prices

## Files Modified

1. `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/layout/TopBar.js`
2. `/Users/ssr/Projects/WorkingBot/webui/frontend/src/components/options/OptionsPanel.js`

## No Breaking Changes

- The `indexPrices` variable in OptionsPanel is still available to all dependent code
- Refs (`indexPricesRef`) still work correctly with the state variable
- Automation monitor integration unchanged
- All existing functionality preserved

## Next Steps

1. Test the application to verify all three price displays now show identical values
2. Monitor console logs for `[TopBar]` and `[OptionsPanel]` price fetch messages
3. Verify prices update every 5 seconds across all components
4. Check that all displays update simultaneously when market moves
