# Take Profit System - Complete Documentation

**Created:** February 5, 2026  
**Status:** ✅ Enhanced to support both Profit Targets and Loss Limits

---

## Overview

The Take Profit system allows automatic partial position closing when a P&L target is reached. This feature works for **BOTH profit and loss scenarios**:

- **Profit Targets (Positive Values)**: Automatically reduce position size when reaching a profit goal
- **Loss Limits (Negative Values)**: Automatically reduce position size when reaching a loss threshold

---

## Key Features

### ✅ Dual-Mode Operation
- **Profit Mode**: Set positive target (e.g., $20) to exit when position is in profit
- **Loss Mode**: Set negative target (e.g., -$10) to exit when position reaches loss limit

### ✅ Partial Position Closing
- Specify exact quantity to exit (in lots/contracts)
- Remaining position stays open for further management
- Can set new targets on remaining position after partial close

### ✅ Automatic Execution
- Background monitor checks positions every 3 seconds
- Automatic limit order placement when target is reached
- No manual intervention required

### ✅ Smart Order Execution
- Uses limit orders (maker-first) for better fills
- Rate limiting to respect exchange API limits
- Retry logic with exponential backoff
- Prevents duplicate orders with cooldown mechanism

---

## How It Works

### Setting a Target

1. **Open Position**: You must have an active options position
2. **Click TP Icon**: Open the Target P&L Settings dialog
3. **Enter Target P&L**:
   - Positive value (e.g., `20`) = Exit when profit reaches $20
   - Negative value (e.g., `-10`) = Exit when loss reaches -$10
4. **Enter Quantity**: Number of lots/contracts to exit (max = current position size)
5. **Set Target**: Click "Set Target" button

### Monitoring & Execution

The background monitor:
1. Checks all positions with active targets every 3 seconds
2. Compares current P&L against target
3. When target is reached:
   - Places a limit order to close the specified quantity
   - Marks the target as "triggered" in database
   - Logs the event and shows in activity log
   - Remaining position stays open

### Target Logic

**For Profit Targets (positive):**
```
IF current_pnl >= target_profit THEN trigger
Example: Target = $20, Current P&L = $21 → TRIGGER ✅
```

**For Loss Limits (negative):**
```
IF current_pnl <= target_profit THEN trigger
Example: Target = -$10, Current P&L = -$11 → TRIGGER ✅
```

---

## Usage Examples

### Example 1: Profit Taking
**Scenario**: You have 50 lots of P-BTC-72000-050226 with current P&L of $5

**Action**:
- Set Target P&L: `$30`
- Set Quantity: `25` lots

**Result**: When position P&L reaches $30, system automatically places limit order to close 25 lots. Remaining 25 lots stay open.

---

### Example 2: Loss Limiting
**Scenario**: You have 71 lots of P-BTC-72000-050226 with current P&L of -$56.53

**Action**:
- Set Target P&L: `-$10` (to reduce exposure if loss worsens)
- Set Quantity: `35` lots

**Result**: When position P&L reaches -$10 or worse, system automatically places limit order to close 35 lots. Remaining 36 lots stay open.

---

### Example 3: Sequential Scaling Out
**Scenario**: You have 100 lots with profit building

**Strategy**:
1. First Target: $50 → Exit 30 lots  
   *(Remaining: 70 lots)*
2. After first trigger, set Second Target: $100 → Exit 30 lots  
   *(Remaining: 40 lots)*
3. After second trigger, set Third Target: $150 → Exit 40 lots  
   *(Position fully closed)*

---

## Technical Implementation

### Frontend Components

**File**: `webui/frontend/src/components/options/TakeProfitDialog.js`

- Target P&L input (allows negative values)
- Quantity input with validation
- Dynamic example box (shows profit/loss based on target sign)
- Color-coded feedback (green for profit, red for loss)

### Backend API

**File**: `webui/backend/routes/options/options_control.py`

**Endpoints**:
- `POST /api/options/take-profit/strike/set` - Set target for a strike
- `POST /api/options/take-profit/strike/remove` - Remove target
- `GET /api/options/take-profit/strike/all` - Get all targets
- `GET /api/options/take-profit/strike/{symbol}` - Get target for specific strike

**Validation**:
- Target P&L must be non-zero (can be positive or negative)
- Quantity must be positive integer
- Quantity cannot exceed current position size

### Background Monitor

**File**: `webui/backend/options_strategy/take_profit_manager.py`

**Class**: `TakeProfitMonitor`

**Features**:
- Runs in background daemon thread
- Check interval: 3 seconds (configurable)
- Rate limiting: 8 calls/second (Delta Exchange limit)
- Recently closed tracking: 60-second cooldown to prevent duplicates
- Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)

**Monitoring Logic**:
```python
# For profit targets (positive)
if target_profit > 0:
    target_reached = pnl >= target_profit

# For loss limits (negative)  
else:
    target_reached = pnl <= target_profit
```

### Database Schema

**Table**: `strike_take_profit`

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Strike symbol (primary key) |
| target_profit | REAL | Target P&L (positive or negative) |
| exit_quantity | INTEGER | Quantity to exit when triggered |
| enabled | BOOLEAN | Whether target is active |
| triggered | BOOLEAN | Whether target has been triggered |
| created_at | TEXT | ISO timestamp of creation |
| updated_at | TEXT | ISO timestamp of last update |
| triggered_at | TEXT | ISO timestamp when triggered |

**Table**: `take_profit_history`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment primary key |
| symbol | TEXT | Strike symbol |
| target_profit | REAL | Target that was set |
| actual_profit | REAL | Actual P&L when triggered |
| exit_quantity | INTEGER | Quantity that was closed |
| timestamp | TEXT | ISO timestamp of trigger |

---

## User Interface

### Position Table Columns

**TP Column**: Shows Take Profit indicator with:
- 🎯 Icon when target is active
- Target amount displayed
- Click to configure/modify target
- Color-coded: Green for profit targets, Red for loss limits

### Target P&L Settings Dialog

**Fields**:
1. **Position Info Box**
   - Symbol name
   - Total Quantity (lots)
   - Current P&L (color-coded: green for profit, red for loss)

2. **Target P&L Input**
   - Accepts positive or negative numbers
   - Placeholder: "e.g., 20 or -10"
   - Helper text: "Exit when position P&L reaches this (positive for profit, negative for loss)"

3. **Quantity to Exit Input**
   - Accepts positive integers only
   - Max validation against current position size
   - Helper text: "Number of contracts to close (max: X lots)"

4. **Example Box**
   - Dynamic color (green for profit, red for loss)
   - Shows exact scenario based on inputs
   - Warns if partial close (remaining lots message)

**Buttons**:
- Remove TP (if existing target)
- Cancel
- Set Target

---

## Best Practices

### ✅ Recommended Usage

1. **Set Profit Targets Early**: Configure targets right after entering position
2. **Use Loss Limits**: Protect downside with negative targets
3. **Scale Out Gradually**: Use multiple targets to scale out of winning positions
4. **Monitor Activity Log**: Check system activity to verify triggers
5. **Adjust as Needed**: Can modify target anytime before trigger

### ⚠️ Important Warnings

1. **Not a Stop-Loss**: This uses limit orders, not stop orders. May not execute in fast-moving markets.
2. **Cooldown Period**: 60-second cooldown prevents duplicate triggers
3. **Partial Fills**: Order may partially fill if liquidity is low
4. **Remove After Trigger**: Target is marked as triggered but not removed - you can set a new one
5. **API Rate Limits**: System respects Delta Exchange rate limits (max 10 req/sec)

### 🚫 Limitations

1. **Single Target Per Strike**: Can only have one active target per strike at a time
2. **Requires Position**: Cannot set target without active position
3. **Quantity Cap**: Cannot exit more than current position size
4. **No Pre-Configuration**: Must have position first before setting target
5. **Limit Order Only**: Not guaranteed execution (uses limit orders)

---

## Troubleshooting

### Target Not Triggering

**Check**:
1. Is monitor running? (Check backend logs for "Take Profit Monitor started")
2. Is target correct? (Positive for profit, negative for loss)
3. Has P&L actually reached target?
4. Is target marked as triggered already? (Check database)

### Order Not Placed

**Check**:
1. Backend logs for error messages
2. API rate limiting (may be delayed)
3. Position still exists (check current positions)
4. Cooldown period (60 seconds between attempts)

### Target Removed But Still Active

**Solution**: Restart backend to clear any cached state

---

## File Locations

### Frontend
- Dialog Component: `webui/frontend/src/components/options/TakeProfitDialog.js`
- Indicator Component: `webui/frontend/src/components/options/TakeProfitIndicator.js`
- Main Panel: `webui/frontend/src/components/options/OptionsPanel.js`

### Backend
- Manager: `webui/backend/options_strategy/take_profit_manager.py`
- API Routes: `webui/backend/routes/options/options_control.py`
- Database: `data/options_take_profit.db`

### Documentation
- This file: `TAKE_PROFIT_SYSTEM_EXPLAINED.md`

---

## Recent Changes

### February 5, 2026 - Enhanced for Loss Limits

**What Changed**:
1. ✅ Allow negative target P&L values
2. ✅ Updated validation (frontend & backend) to accept non-zero values
3. ✅ Enhanced monitoring logic to handle both profit and loss scenarios
4. ✅ Updated UI text and examples to clarify dual functionality
5. ✅ Changed dialog title from "Take Profit Settings" to "Target P&L Settings"
6. ✅ Added color-coding (green for profit, red for loss)

**Backward Compatibility**: ✅ Fully compatible with existing profit targets

---

## Summary

The Take Profit system is now a comprehensive **Target P&L** system that handles both profit-taking and loss-limiting scenarios. It provides:

- Flexible targeting (profit or loss)
- Automatic execution
- Partial position management
- Real-time monitoring
- Detailed activity logging

Whether you want to lock in profits or limit losses, this system provides automated, hands-free position management.

---

**For Questions or Issues**: Check backend logs (`webui/backend/logs/`) and activity log in the WebUI.
