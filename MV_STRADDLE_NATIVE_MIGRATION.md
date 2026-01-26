# MV Straddle Native Implementation - Complete Migration

**Date:** January 25, 2026  
**Status:** ✅ COMPLETE - Ready for Testing  
**Type:** Native Delta Exchange Product Integration

---

## Executive Summary

Successfully migrated MV Straddle from synthetic multi-leg strategy to **native Delta Exchange India product** integration.

### What Changed

**Before (WRONG):**
- ❌ MV Straddle built as synthetic strategy (separate Call + Put)
- ❌ Two separate orders to exchange
- ❌ Complex multi-leg execution logic
- ❌ Manual premium calculation from two options

**After (CORRECT):**
- ✅ MV Straddle as single Delta Exchange product (contract_type: `move_options`)
- ✅ One order to buy/sell complete straddle
- ✅ Native ticker with combined Greeks
- ✅ Simplified P&L calculation

---

## Technical Details

### Product Information

**Contract Type:** `move_options`  
**Symbol Format:** `MV-{UNDERLYING}-{STRIKE}-{EXPIRY}`  
**Example:** `MV-BTC-89400-250126`

**Key Characteristics:**
- Single tradeable instrument
- Combines ATM Call + Put premium
- Cash-settled in USD
- Daily expiries (typically 12:00 UTC)
- Contract value: 0.001 BTC

### API Endpoints

All endpoints under `/api/mv-straddle/`:

1. **GET /products** - List available MV Straddles
2. **GET /expirations** - Get expiry dates with labels
3. **GET /strikes** - Get strikes for specific expiry
4. **GET /ticker/{symbol}** - Get real-time ticker data
5. **POST /preview** - Preview order before placement
6. **POST /order** - Place MV Straddle order
7. **POST /pnl** - Calculate position P&L
8. **GET /health** - Health check

---

## Files Created

### Backend (3 NEW files)

1. **`webui/backend/options_strategy/mv_straddle_native.py`**
   - Main handler for MV Straddle operations
   - Product fetching, ticker data, order placement
   - P&L calculations
   - ~550 lines

2. **`webui/backend/routes/mv_straddle_routes.py`**
   - Flask blueprint with all API endpoints
   - Request validation and error handling
   - ~400 lines

3. **`webui/backend/app.py`** (MODIFIED)
   - Registered `mv_straddle_bp` blueprint
   - +7 lines

### Frontend (2 files)

1. **`webui/frontend/src/components/mvStraddle/MVStraddleNativeForm.js`**
   - Native MV Straddle trading form
   - Real-time preview, expiry/strike selection
   - Order placement interface
   - ~550 lines

2. **`webui/frontend/src/components/mvStraddle/MVStraddlePanel.js`** (MODIFIED)
   - Updated to import `MVStraddleNativeForm`
   - Removed synthetic strategy form
   - ~10 lines changed

---

## Architecture

```
MV Straddle Native Flow
=======================

Frontend:
  MVStraddleNativeForm
    ├─> Fetch expirations (GET /api/mv-straddle/expirations)
    ├─> Fetch strikes (GET /api/mv-straddle/strikes)
    ├─> Preview order (POST /api/mv-straddle/preview)
    └─> Place order (POST /api/mv-straddle/order)

Backend:
  mv_straddle_routes.py (Flask Blueprint)
    └─> MVStraddleNative (Handler)
        └─> UnifiedAPIClient
            └─> Delta Exchange API
                - GET /v2/products (contract_types=move_options)
                - GET /v2/tickers/{symbol}
                - POST /v2/orders
```

---

## Testing Checklist

### Backend Tests

```bash
# 1. Health check
curl http://localhost:5555/api/mv-straddle/health

# 2. Get products
curl http://localhost:5555/api/mv-straddle/products?underlying=BTC

# 3. Get expirations
curl http://localhost:5555/api/mv-straddle/expirations?underlying=BTC

# 4. Get strikes
curl "http://localhost:5555/api/mv-straddle/strikes?underlying=BTC&expiry=250126"

# 5. Get ticker
curl http://localhost:5555/api/mv-straddle/ticker/MV-BTC-89400-250126

# 6. Preview order
curl -X POST http://localhost:5555/api/mv-straddle/preview \
  -H "Content-Type: application/json" \
  -d '{"underlying":"BTC","expiry":"250126","side":"buy","quantity":1,"autoStrike":true}'
```

### Frontend Tests

1. Navigate to **📊 MV Straddle** panel
2. Check expiry dropdown populates
3. Check strike dropdown shows available strikes
4. Enable "Auto ATM Strike" - should select ATM
5. Change quantity, verify preview updates
6. Toggle Buy/Sell, verify preview changes
7. Check preview shows:
   - Symbol (e.g., MV-BTC-89400-250126)
   - Mark price
   - Spot price
   - Greeks (Delta, Gamma, Theta, Vega)
   - IV
   - Estimated cost
8. Test order placement (with 1 contract)

---

## User Guide

### How to Trade MV Straddle

1. **Navigate to MV Straddle Panel**
   - Click "📊 MV Straddle" in main navigation

2. **Select Parameters**
   - Underlying: BTC or ETH
   - Expiry: Choose from dropdown (auto-populated with available dates)
   - Strike: Enable "Auto ATM Strike" or select manually
   - Direction: Buy (Long) or Sell (Short)
   - Quantity: Number of contracts

3. **Review Preview**
   - Symbol shows the actual Delta Exchange product
   - Mark price is current fair value
   - Greeks are combined (Call + Put)
   - Estimated cost = Mark Price × Quantity

4. **Place Order**
   - Limit Order: Specify your price
   - Market Order: Execute immediately
   - Click "Buy MV Straddle" or "Sell MV Straddle"

5. **View Positions**
   - Switch to "Active Positions" tab
   - See real-time P&L
   - Manage positions

---

## Key Differences from Synthetic Strategy

| Aspect | Synthetic (OLD) | Native (NEW) |
|--------|-----------------|--------------|
| **Symbol** | C-BTC-89400-250126<br>P-BTC-89400-250126 | MV-BTC-89400-250126 |
| **Orders** | 2 separate orders | 1 single order |
| **Execution** | Multi-leg executor | Simple order placement |
| **Greeks** | Calculated from 2 legs | Combined from ticker |
| **P&L** | Sum of both legs | Single position P&L |
| **Margin** | Separate for each leg | Single margin requirement |

---

## Migration Notes

### Deprecated Files (Can Remove After Testing)

- ❌ `webui/backend/options_strategy/strategies/mv_straddle_strategy.py`
- ❌ `webui/backend/options_strategy/mv_straddle/volatility_analyzer.py`
- ❌ `webui/backend/options_strategy/mv_straddle/strike_selector.py`
- ❌ `webui/backend/options_strategy/mv_straddle/breakeven_calculator.py`
- ❌ `webui/backend/options_strategy/mv_straddle/position_adjuster.py`
- ❌ `webui/frontend/src/components/optionsStrategy/strategies/MVStraddleForm.js` (old synthetic form)

### Kept Files (Still Used)

- ✅ `webui/frontend/src/components/mvStraddle/MVStraddlePanel.js` - Main panel (updated)
- ✅ `webui/backend/options_strategy/strategies/base_strategy.py` - Used by other strategies
- ✅ All other strategy files (Straddle, Strangle, Iron Condor, etc.)

---

## Next Steps

1. **Restart Backend**
   ```bash
   lsof -ti:5555 | xargs kill -9
   cd /Users/ssr/Projects/WorkingBot
   /usr/bin/python3 webui/backend/app.py &
   ```

2. **Rebuild Frontend**
   ```bash
   cd /Users/ssr/Projects/WorkingBot/webui/frontend
   npm run build
   ```

3. **Test in Browser**
   - Navigate to http://localhost:5555
   - Click "📊 MV Straddle"
   - Test complete workflow

4. **Verify API**
   - Run backend test commands
   - Check logs for any errors
   - Verify Delta Exchange API responses

5. **Clean Up (Optional)**
   - Remove deprecated synthetic strategy files
   - Update documentation
   - Git commit changes

---

## Support

**If Issues Occur:**

1. Check backend logs:
   ```bash
   tail -f /tmp/mvstraddle_backend.log
   ```

2. Verify API connectivity:
   ```bash
   curl http://localhost:5555/api/mv-straddle/health
   ```

3. Check browser console for frontend errors

4. Verify Delta Exchange API credentials are configured

---

## Conclusion

✅ **MV Straddle is now correctly implemented as a native Delta Exchange product**

The new implementation:
- Trades MV Straddle as a single instrument
- Fetches real data from Delta Exchange API
- Provides accurate pricing and Greeks
- Simplifies order placement
- Matches Delta Exchange's actual product structure

**Ready for production testing with real MV Straddle products!** 🎯
