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
Example: Target = $20, Current P&L = $15 → Wait (not reached yet)
```

**For Loss Limits (negative):**
```
IF current_pnl >= target_profit THEN trigger
Example: Target = -$50, Current P&L = -$100 → Wait (loss still too bad)
Example: Target = -$50, Current P&L = -$49 → TRIGGER ✅ (loss improved to target!)
Example: Target = -$50, Current P&L = -$30 → TRIGGER ✅ (loss improved past target!)
```

**Key Insight**: For negative targets, the system triggers when the **loss IMPROVES** to the target level or better, not when it gets worse. This allows you to exit partial positions as losses recover, or take partial profits at specific levels.

---

## Detailed Mechanics — How It Works Internally

This section explains the internal computations, decision flow, and safeguards used by the Target P&L system so developers and auditors can understand and reproduce behavior.

### P&L Calculation
- P&L is computed per-strike using the exchange-provided mark or mid price for the underlying and the position's average entry price. The monitor uses the most recent per-position P&L snapshot from the positions cache.
- P&L currency is the account quote currency (e.g., USD). All comparisons to targets use the same currency and numeric scale.

### Trigger Evaluation
- For each active target the monitor evaluates:
   - Read target_profit (float) and exit_quantity (int) from `strike_take_profit`.
   - Read current_pnl (float) for the symbol from positions cache.
   - If target_profit > 0 (profit target): trigger when current_pnl >= target_profit.
   - If target_profit < 0 (loss limit): trigger when current_pnl >= target_profit (i.e., loss has improved to target or better).
- The monitor runs these checks every configured interval (default 3s). Targets are only evaluated for symbols with an active position greater than zero.

### Order Construction and Placement
- When a target is reached the monitor builds a limit order to close `exit_quantity`:
   1. Determine side: if position is long → sell; if short → buy to cover.
   2. Determine limit price: prefer maker-friendly price using top-of-book (best bid for sells, best ask for buys) and possible slight improvement step to increase fill likelihood.
   3. Set client order id and metadata linking to the `strike_take_profit` row for traceability.
- The order is submitted via the exchange client using rate-limited calls. If the order would exceed position size due to concurrent fills/changes, the order is adjusted or canceled.

### Idempotency, Cooldown, and Duplicate Prevention
- Each target has a `triggered` flag and `triggered_at` timestamp. When an order is placed the system marks the target as triggered to prevent immediate re-triggers.
- A short cooldown window (default 60s) is tracked in-memory to avoid duplicate submissions caused by monitor restarts or race conditions.
- Orders include unique client IDs tied to the target row so re-submissions are detectable by the backend.

### Retry & Backoff
- If order submission fails due to transient network or rate-limit errors, monitor retries up to the configured attempts (default 3) with exponential backoff (1s, 2s, 4s).
- Permanent errors (invalid params, insufficient margin) will log and mark the target as failed; operator intervention is required.

### Rate Limiting
- The manager uses a token-bucket style limiter (configured for 8 calls/sec by default) to keep within exchange rate limits. All API calls for order submission and status checks pass through the limiter.

### Database State Changes
- On successful order submission the system writes an entry to `take_profit_history` with actual_profit, exit_quantity, and timestamp.
- The `strike_take_profit` row is updated: `triggered` set to true and `triggered_at` saved. The target remains in the DB for audit and can be re-enabled or removed via API.

### Concurrency & Position Changes
- Before placing an order the monitor re-reads current position size; if the requested `exit_quantity` is larger than the current size, it adjusts the order quantity down to the available amount.
- If the position is zero (closed) the monitor clears the target or marks it failed depending on config.

### Edge Cases & Failure Modes
- Rapid price moves may cause limit orders to never fill; these are visible in activity logs and require manual follow-up or reconfiguration to a more aggressive price.
- Partial fills: the system records actual executed quantity and, if a partial fill leaves a remaining target, the `strike_take_profit` row is updated to the remaining exit quantity or marked completed depending on policy.

### Testing & Verification
- Unit tests cover trigger evaluation for positive and negative targets, P&L boundary conditions, and the idempotency logic.
- Integration tests simulate the monitor loop, rate limiter, and order submission with a mocked exchange client to validate retry/backoff and database state transitions.

This detailed mechanics section is intended to make behavior explicit for maintainers, QA, and users who want to audit or extend the system.


## Usage Examples

### Example 1: Profit Taking
**Scenario**: You have 50 lots of P-BTC-72000-050226 with current P&L of $5

**Action**:
- Set Target P&L: `$30`
- Set Quantity: `25` lots

**Result**: When position P&L reaches $30, system automatically places limit order to close 25 lots. Remaining 25 lots stay open.

---

### Example 2: Loss Limiting
**Scenario**: You have 71 lots of P-BTC-72000-050226 with current P&L of -$100 (significant loss)

**Action**:
- Set Target P&L: `-$50` (to exit when loss improves to -$50)
- Set Quantity: `35` lots

**Result**: When position P&L **improves** to -$50 or better (like -$49, -$30, etc.), system automatically places limit order to close 35 lots. Remaining 36 lots stay open.

**Important**: Target will NOT trigger if loss gets worse (e.g., goes to -$120). It only triggers when loss improves to the target level.

---

### Example 3: Averaging Down Recovery
**Scenario**: You have a losing position that you're averaging down on

**Starting Point**: 
- Position: 100 lots
- Current P&L: -$200 (bad situation)

**Strategy - Set Multiple Recovery Targets**:
1. First Recovery Target: `-$150` → Exit 30 lots when loss improves to -$150
2. After first trigger (now 70 lots remaining, P&L at -$150):
   - Set Second Target: `-$100` → Exit 30 lots when loss improves to -$100
3. After second trigger (40 lots remaining, P&L at -$100):
   - Set Third Target: `-$50` → Exit remaining 40 lots when loss improves to -$50

**Result**: Systematic position reduction as losses recover, managing risk while giving the position room to improve.

---

### Example 4: Sequential Scaling Out
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
    target_reached = pnl >= target_profit
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
7. ✅ Corrected backend logic to trigger loss limits only when loss improves to the target level

**Backward Compatibility**: ✅ Fully compatible with existing profit targets

---

### February 5, 2026 - Deployment & Hotfixes

**What Happened**:
- Frontend was not reflecting recent UI/logic changes due to a caching issue; rebuilt frontend assets and cleared caches.
- Fixed `TakeProfitIndicator` so negative (loss limit) values display correctly in the UI and tooltips.
- Restarted backend daemon to ensure monitor logic and cooldown state were reloaded.
- Committed and pushed fixes to the `SSR` branch and redeployed the frontend.

**Why It Matters**:
- Ensures UI accurately reflects the new negative-target behavior so users can see and configure loss limits.
- Removes stale assets that caused confusion during manual testing.
- Guarantees the corrected backend logic is active in production, preventing incorrect triggers for loss limits.

**Verification**:
- Frontend rebuilt and deployed; backend restarted. Activity logs show monitor running and recent trigger events.
- Updated unit/integration checks and documentation to reflect corrected behavior.


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
