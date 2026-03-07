# MV Straddle Incremental Implementation Plan

## Current Status
✅ **Phase 0: Minimal Panel** - Panel loads without crashing the app

## Backend (Already Complete)
✅ `/webui/backend/options_strategy/mv_straddle_native.py` - Handler ready
✅ `/webui/backend/routes/mv_straddle_routes.py` - 8 endpoints ready
- `/api/mv-straddle/health`
- `/api/mv-straddle/products`
- `/api/mv-straddle/expirations`
- `/api/mv-straddle/strikes`
- `/api/mv-straddle/ticker`
- `/api/mv-straddle/preview`
- `/api/mv-straddle/order`
- `/api/mv-straddle/pnl`

## Frontend Implementation Phases

### Phase 1: Backend Health Check (5 min)
**Goal**: Verify backend connectivity
- [ ] Add useEffect to call `/api/mv-straddle/health`
- [ ] Display backend status (operational/error)
- [ ] Show timestamp
- [ ] Test: Navigate to MV Straddle tab, see green "Backend operational" message

### Phase 2: Basic Form Layout (10 min)
**Goal**: Static form with no API calls
- [ ] Add Paper container with form
- [ ] Add TextField for quantity (default: 1)
- [ ] Add ToggleButton for Buy/Sell
- [ ] Add static Select for underlying (BTC hardcoded)
- [ ] Add disabled "Place Order" button
- [ ] Test: Form renders with all fields visible

### Phase 3: Load Expirations (10 min)
**Goal**: Fetch and display available expiries
- [ ] Add state: `availableExpiries`
- [ ] Add useEffect to call `/api/mv-straddle/expirations?underlying=BTC`
- [ ] Populate expiry Select dropdown
- [ ] Test: Dropdown shows real expirations from API

### Phase 4: Load Strikes (10 min)
**Goal**: Fetch strikes when expiry changes
- [ ] Add state: `availableStrikes`, `selectedExpiry`
- [ ] Add useEffect that triggers when expiry changes
- [ ] Call `/api/mv-straddle/strikes?underlying=BTC&expiry={expiry}`
- [ ] Populate strike Select dropdown
- [ ] Test: Change expiry, see strikes update

### Phase 5: Simple Order Placement (15 min)
**Goal**: Place market order (no preview)
- [ ] Add state: `selectedStrike`, `quantity`, `side`
- [ ] Enable "Place Order" button when strike selected
- [ ] Add onClick handler: POST `/api/mv-straddle/order`
- [ ] Show success/error message
- [ ] Test: Place order, verify it appears on exchange

### Phase 6: Add Market Data (15 min)
**Goal**: Show current price and mark price
- [ ] Add state: `tickerData`
- [ ] Add useEffect to call `/api/mv-straddle/ticker?symbol={symbol}`
- [ ] Display mark price, last price, bid/ask
- [ ] Test: See live prices update

### Phase 7: Add Preview Panel (20 min)
**Goal**: Show order preview before placing
- [ ] Add 2-column Grid layout (form left, preview right)
- [ ] Add preview Card component
- [ ] Call `/api/mv-straddle/preview` when form changes (debounced)
- [ ] Display estimated cost, Greeks (if available)
- [ ] Test: Change form values, see preview update

### Phase 8: Add Limit Orders (10 min)
**Goal**: Support limit_order type
- [ ] Add ToggleButton for Market/Limit
- [ ] Add TextField for limit price (conditional render)
- [ ] Auto-fill limit price from preview
- [ ] Test: Place limit order at specific price

### Phase 9: Polish UI (10 min)
**Goal**: Clean up layout and styling
- [ ] Add loading spinners
- [ ] Add error boundaries
- [ ] Add tooltips for fields
- [ ] Improve spacing and colors
- [ ] Test: UI looks polished and professional

### Phase 10: Add Active Positions Tab (Optional - 15 min)
**Goal**: View existing MV Straddle positions
- [ ] Add Tabs: "Create New" | "Active Positions"
- [ ] Call `/api/options/positions` and filter MV-* symbols
- [ ] Display position cards with P&L
- [ ] Test: See active positions

## Testing Strategy

After each phase:
1. **Build**: `npm run build`
2. **Hard refresh**: Cmd+Shift+R in browser
3. **Navigate**: Click "MV Straddle" tab
4. **Verify**: Phase goal achieved
5. **Console**: No errors in browser console

If phase fails:
- Check browser console for errors
- Check network tab for API errors
- Check backend logs: `tail -f /Users/ssr/Projects/WorkingBot/logs/launchagent_webui_error.log`
- Revert to previous working phase if needed

## Rollback Strategy

Each phase has backup:
- `/webui/frontend/src/components/mvStraddle/MVStraddlePanel.backup.js` - Full version
- `/webui/frontend/src/components/mvStraddle/MVStraddleForm.backup.js` - Full form
- `/webui/frontend/src/components/mvStraddle/MVStraddlePanel.minimal.js` - Minimal version

To rollback to working state:
```bash
cd /Users/ssr/Projects/WorkingBot/webui/frontend/src/components/mvStraddle
cp MVStraddlePanel.minimal.js MVStraddlePanel.js
npm run build
```

## Current Files
- ✅ `MVStraddlePanel.minimal.js` - Working minimal version (currently active)
- ✅ `MVStraddlePanel.backup.js` - Full version backup
- ✅ `MVStraddleForm.backup.js` - Full form backup

## Next Steps
1. Start with Phase 1 (Backend Health Check)
2. Build and test after each phase
3. Only proceed to next phase if current phase works
4. Document any issues encountered
