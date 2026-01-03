# Frontend Symbol Integration Testing Guide
**Date:** January 1, 2026  
**Objective:** Verify symbol-aware API calls work correctly

---

## Pre-Test Setup ✅
- ✅ Backend running: Port 5557 (app_dev.py)
- ✅ Frontend running: Port 3001 (React dev server)
- ✅ Backend API tested: `?symbol=BTCUSD` works
- ✅ Browser opened: http://localhost:3001

---

## Testing Steps

### Step 1: Open Developer Tools (F12)
1. Press **F12** or **Cmd+Option+I** (Mac) to open DevTools
2. Click **Console** tab - check for errors
3. Click **Network** tab - prepare to monitor API calls

### Step 2: Check Initial Load
**Look for in Console:**
- ❌ `Error: useSymbol must be used within SymbolProvider`
- ❌ `Cannot read property 'selectedSymbol' of undefined`
- ❌ Any red error messages related to symbols

**Look for in Network tab:**
- ✅ `GET /api/config/flat?symbol=BTCUSD` (or ETHUSD)
- ✅ `GET /api/bot/status?symbol=BTCUSD`
- ✅ `GET /api/positions?symbol=BTCUSD`
- ❌ `GET /api/config/flat` (without symbol parameter = OLD BEHAVIOR)

### Step 3: Navigate to Configuration Page
1. Click **Configuration** in sidebar or main menu
2. Watch Network tab for new requests
3. Check Console for any errors

**Expected Network Calls:**
```
GET http://localhost:5557/api/config/flat?symbol=BTCUSD
Response: {"symbol": "BTCUSD", "config": {...}, "symbol_enabled": true}
```

**Expected Console:**
- No errors about missing symbol
- No "Hard refreshing" loops
- No null pointer exceptions

### Step 4: Test Symbol Switching (If Selector Exists)
1. Look for **Symbol Selector** dropdown (usually in header/topbar)
2. If found, click dropdown
3. Select different symbol (e.g., ETHUSD)
4. Watch what happens:

**GOOD Signs:**
- ✅ Config panel updates instantly (no page reload)
- ✅ Network shows: `GET /api/config/flat?symbol=ETHUSD`
- ✅ Lower bound changes from 85000 (BTC) to 3200 (ETH)
- ✅ Console: No errors

**BAD Signs:**
- ❌ Full page reload (window.location.reload)
- ❌ "Hard refreshing" messages
- ❌ Config doesn't change
- ❌ Network shows old symbol in requests

### Step 5: Check SymbolContext State
In Console, run:
```javascript
// Check if SymbolContext is available
window.React = require('react');
// Try to access symbol state (this might not work, depends on React DevTools)
```

Or install **React Developer Tools** extension and:
1. Click **Components** tab
2. Find `<SymbolProvider>` component
3. Check its state:
   - `selectedSymbol`: Should be "BTCUSD" or "ETHUSD"
   - `symbols`: Should be array with BTCUSD and ETHUSD
   - `loading`: Should be false after load

---

## Common Issues & Fixes

### Issue 1: "useSymbol must be used within SymbolProvider"
**Cause:** SymbolProvider not wrapping the app  
**Fix:** Check `App.js` - ensure `<SymbolProvider>` wraps all components

### Issue 2: API calls missing symbol parameter
**Cause:** useConfigManager not using fetchWithSymbol  
**Status:** ✅ Already fixed in our code
**Verify:** Check Network tab for `?symbol=` in URLs

### Issue 3: Null pointer: "Cannot read property 'name' of undefined"
**Cause:** SymbolSelector accessing symbol.name without null check  
**Fix:** Find the component and add: `symbol?.name ?? 'N/A'`

### Issue 4: Infinite refresh loop
**Cause:** useEffect dependencies incorrect  
**Status:** ✅ Should be fixed (removed selectedSymbol from loadSymbols deps)
**Verify:** Console should NOT spam "Hard refreshing" messages

### Issue 5: Backend returns 404 for /api/symbols
**Cause:** Endpoint doesn't exist yet in app_dev.py  
**Impact:** SymbolContext can't load symbols list
**Workaround:** Hardcode symbols for now:
```javascript
// In SymbolContext.js - temporary workaround
setSymbols([
  { name: 'BTCUSD', enabled: true },
  { name: 'ETHUSD', enabled: false }
]);
setSelectedSymbol('BTCUSD');
```

---

## Success Criteria

✅ **Pass** if ALL of these are true:
1. No console errors on page load
2. Network tab shows `?symbol=BTCUSD` in API calls
3. Config page loads without errors
4. Symbol parameter appears in all API requests
5. (Bonus) Symbol switching works without page reload

❌ **Fail** if ANY of these occur:
1. Console error: "useSymbol must be used within SymbolProvider"
2. Null pointer exceptions
3. API calls missing symbol parameter
4. Infinite refresh loops
5. Full page reload on symbol switch

---

## Next Steps After Testing

### If All Tests Pass ✅
1. Document results in plan
2. Proceed with Option B: Refactor more backend APIs
3. Update remaining frontend components

### If Tests Fail ❌
1. Screenshot console errors
2. Copy error stack traces
3. Check which component is failing
4. Fix null safety issues
5. Re-test

---

## Quick Reference

**Development Ports:**
- Frontend: http://localhost:3001
- Backend: http://localhost:5557
- Production (DO NOT TOUCH): 5555/5556

**Key Files:**
- SymbolContext: `webui/frontend/src/context/SymbolContext.js`
- useConfigManager: `webui/frontend/src/hooks/useConfigManager.js`
- ConfigPanel: `webui/frontend/src/components/ConfigPanel.js`

**Test APIs Directly:**
```bash
# Config API
curl "http://localhost:5557/api/config/all?symbol=BTCUSD" | python3 -m json.tool

# Positions API
curl "http://localhost:5557/api/positions?symbol=BTCUSD" | python3 -m json.tool

# Guardian API
curl "http://localhost:5557/api/guardian/status?symbol=BTCUSD" | python3 -m json.tool
```

---

**Ready to test!** Open DevTools and follow the steps above.
