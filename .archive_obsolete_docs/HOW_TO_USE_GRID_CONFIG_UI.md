# How to Use Grid Configuration UI

## Quick Guide to Grid Configuration in WebUI

### Accessing Grid Configuration

1. **Open WebUI:**
   ```
   http://localhost:5555
   ```
   Or via Tailscale (mobile):
   ```
   http://100.107.230.67:5555
   ```

2. **Navigate to Configuration Panel:**
   - Click the **⚙️ Configuration** icon in the sidebar
   - Or click the **gear icon** in the top navigation

3. **Select Essential Tab:**
   - The Essential tab opens by default
   - Grid Geometry & Direction is the first section

---

## Grid Geometry & Direction Section

### Visual Layout

```
┌─────────────────────────────────────────────────────────┐
│  🎯 Grid Geometry & Direction                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Trading Direction:                                      │
│  ┌──────────────┬──────────────┐                       │
│  │ 📈 LONG      │   SHORT      │  ← Toggle button       │
│  └──────────────┴──────────────┘                       │
│                                                          │
│  ┌──────────────┬──────────────┐                       │
│  │ Reference    │ Symbol       │                        │
│  │ 94500 USD    │ BTCUSD       │                        │
│  ├──────────────┼──────────────┤                       │
│  │ Lower Bound  │ Upper Bound  │                        │
│  │ 90000 USD    │ 110000 USD   │                        │
│  ├──────────────┴──────────────┤                       │
│  │ Grid Span: 90,000 → 110,000 (20,000 USD)           │
│  ├──────────────┬──────────────┤                       │
│  │ Step Size    │ Lot Size     │                        │
│  │ 500 USD      │ 1 units      │                        │
│  ├──────────────┼──────────────┤                       │
│  │ Max Open     │ [Advanced ▼] │                        │
│  │ 5 positions  │              │                        │
│  └──────────────┴──────────────┘                       │
│                                                          │
│  [Advanced Options - Collapsed]                         │
│  ┌──────────────────────────────┐                      │
│  │ Heartbeat Interval: 20 sec   │                      │
│  └──────────────────────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

---

## Field Descriptions

### 1. Trading Direction (LONG/SHORT)
- **Visual Toggle:** Green for LONG, Red for SHORT
- **LONG Mode:** Buy low, sell high (profit from price increases)
- **SHORT Mode:** Sell high, buy low (profit from price decreases)
- **Indicator:** Glowing effect on selected mode

### 2. Reference Price
- **Purpose:** Starting point for grid calculations
- **Format:** USD (e.g., 94500)
- **Usage:** Bot places first order relative to this price
- **Tip:** Set to current market price or desired entry point

### 3. Symbol
- **Default:** BTCUSD
- **Format:** Trading pair symbol
- **Note:** Currently supports Bitcoin perpetual futures only

### 4. Lower Bound
- **Purpose:** Minimum price for grid
- **Format:** USD (e.g., 90000)
- **LONG Mode:** Lowest buy order price
- **SHORT Mode:** Lowest sell order price
- **Validation:** Must be less than upper bound

### 5. Upper Bound
- **Purpose:** Maximum price for grid
- **Format:** USD (e.g., 110000)
- **LONG Mode:** Highest sell (TP) price
- **SHORT Mode:** Highest buy (TP) price
- **Validation:** Must be greater than lower bound

### 6. Grid Span (Auto-Calculated)
- **Display:** Shows range and total span
- **Example:** "90,000 → 110,000 (20,000 USD)"
- **Color:** Green for LONG, Red for SHORT
- **Purpose:** Visual confirmation of grid range

### 7. Step Size
- **Purpose:** Distance between grid levels
- **Format:** USD (e.g., 500)
- **Example:** With step=500, grid levels are: 90000, 90500, 91000, 91500...
- **Tip:** Smaller steps = more frequent trades, higher fees

### 8. Lot Size
- **Purpose:** Quantity per order
- **Format:** Units (e.g., 1)
- **Example:** lot_size=1 means 1 BTC contract per order
- **Note:** Total capital = lot_size × price × max_open_positions

### 9. Max Open Positions
- **Purpose:** Maximum simultaneous positions
- **Format:** Number (e.g., 5)
- **Risk:** Higher = more capital required
- **Example:** 5 positions × $95000/position × 1 lot = ~$475k notional

### 10. Heartbeat Interval (Advanced)
- **Purpose:** Bot health check frequency
- **Format:** Seconds (e.g., 20)
- **Default:** 20 seconds
- **Note:** Collapsed by default, click "Advanced" to show

---

## Visual Indicators

### Change Tracking
- **Orange Background:** Field has been modified but not saved
- **White Background:** Field matches saved configuration
- **Hover Effect:** Slight highlight on mouse over

### Validation
- **Red Border:** Invalid value (e.g., lower > upper)
- **Green Checkmark:** Valid configuration
- **Warning Icon:** Potential issue (e.g., very small step size)

### Help Icons
- **ℹ️ Icon:** Hover to see detailed help text
- **Tooltip:** Shows parameter description and valid range
- **Example:** "Grid step size in USD. Smaller = more trades. Range: 0.5 - 10000"

---

## Example Configurations

### Conservative (Low Risk)
```yaml
Mode: LONG
Reference: 95000
Lower: 90000
Upper: 100000
Step: 1000
Lot Size: 1
Max Open: 3

Grid Span: 10,000 USD
Grid Levels: 10 levels
Capital Required: ~$285k
```

### Balanced (Medium Risk)
```yaml
Mode: LONG
Reference: 94500
Lower: 90000
Upper: 110000
Step: 500
Lot Size: 1
Max Open: 5

Grid Span: 20,000 USD
Grid Levels: 40 levels
Capital Required: ~$475k
```

### Aggressive (High Risk)
```yaml
Mode: LONG
Reference: 95000
Lower: 85000
Upper: 115000
Step: 250
Lot Size: 2
Max Open: 10

Grid Span: 30,000 USD
Grid Levels: 120 levels
Capital Required: ~$1.9M
```

---

## Saving Configuration

### Save Process
1. **Modify Fields:** Change any grid parameters
2. **Visual Feedback:** Modified fields show orange background
3. **Validation:** System checks for errors (red borders if invalid)
4. **Save Button:** Click "Save Configuration" at bottom
5. **Confirmation:** Green success message appears
6. **Hot Reload:** Guardian bot detects changes automatically (no restart needed)

### What Happens on Save
1. ✅ Configuration saved to `config.yaml`
2. ✅ Backup created automatically
3. ✅ File system watcher detects change
4. ✅ Guardian bot reloads configuration
5. ✅ New parameters take effect immediately
6. ✅ Event logged to database for audit trail

### Verification
```bash
# Check Guardian logs for hot reload
pm2 logs guardian-live --lines 20

# Should see:
# 📝 Config file changed - reloading risk parameters...
# ⚠️  RISK PARAMETERS CHANGED (WebUI update detected)
# ✅ Config change logged to database for audit trail
```

---

## Common Workflows

### 1. Adjust Grid Range
```
1. Change Lower Bound (e.g., 90000 → 88000)
2. Change Upper Bound (e.g., 110000 → 112000)
3. Grid Span updates automatically
4. Click Save
5. Guardian reloads (no restart needed)
```

### 2. Increase Trading Frequency
```
1. Decrease Step Size (e.g., 500 → 250)
2. Note: More grid levels = more trades
3. Check capital requirements
4. Click Save
```

### 3. Switch Trading Direction
```
1. Click SHORT toggle (or LONG toggle)
2. Visual indicator changes color
3. All logic reverses automatically
4. Click Save
5. ⚠️ WARNING: Close existing positions first!
```

### 4. Adjust Risk Exposure
```
1. Change Max Open Positions (e.g., 5 → 3)
2. Change Lot Size (e.g., 1 → 2)
3. Calculate new capital requirement
4. Click Save
```

---

## Tips & Best Practices

### ✅ DO:
- Set reference price near current market price
- Use step size that matches your risk tolerance
- Start with lower max_open_positions for testing
- Save configuration before starting bot
- Monitor first few trades to verify behavior
- Use hot reload to adjust parameters during trading

### ❌ DON'T:
- Set lower bound above upper bound (validation will prevent this)
- Use very small step sizes (< $100) without understanding fee impact
- Change mode (LONG/SHORT) while bot is running with open positions
- Set max_open_positions higher than your capital allows
- Ignore validation warnings (red borders)

---

## Troubleshooting

### Issue: Changes not saving
**Solution:** Check for validation errors (red borders), fix them, then save

### Issue: Grid span shows 0 or negative
**Solution:** Ensure lower bound < upper bound

### Issue: Can't see Advanced options
**Solution:** Click "Advanced ▼" button to expand

### Issue: Hot reload not working
**Solution:** 
1. Check Guardian is running: `pm2 list | grep guardian`
2. Check Guardian logs: `pm2 logs guardian-live`
3. Verify watchdog is installed: `pip list | grep watchdog`
4. Run test: `python3 test_hot_reload.py`

### Issue: Orange background won't clear
**Solution:** Click "Save Configuration" to persist changes

---

## Advanced Features

### Grid Span Calculator
- Automatically calculates: `upper_bound - lower_bound`
- Updates in real-time as you type
- Color-coded by mode (green=LONG, red=SHORT)

### Change Tracking
- Tracks every field modification
- Shows unsaved changes count
- Prevents accidental navigation away

### Inline Help
- Every field has contextual help
- Hover over ℹ️ icon to see details
- Shows valid ranges and examples

### Responsive Design
- Works on desktop, tablet, and mobile
- 2-column grid on desktop
- Single column on mobile
- Touch-friendly controls

---

## Related Documentation

- **Configuration Reference:** `CONFIG_QUICK_REF.md`
- **Hot Reload Guide:** `HOT_RELOAD_FIX_NOV18_2025.md`
- **Backend API:** `backend_frontend.md`
- **Grid Calculator:** `bot/strategy/modules/grid_calculator.py`

---

**Last Updated:** November 18, 2025  
**WebUI Version:** 5.0 (Hot Reload Enabled)  
**Status:** ✅ Production Ready
