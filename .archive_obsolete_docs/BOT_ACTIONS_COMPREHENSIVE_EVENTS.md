# 🎯 Bot Actions - Comprehensive Event Coverage

## Overview
This document lists **ALL** critical decision points and events that are logged to the Bot Actions system.

## ✅ Implemented Events (14 Total)

### 1. **bot_startup** 🚀
**When**: Bot initializes and starts running  
**Data Captured**:
- Grid configuration (lower, upper, step, reference)
- Max open positions
- Lot size
- Trading mode (LIVE/DEMO)

**Future Intentions**: "Place BUY order at $XXX when price drops"

---

### 2. **volatility_halt** 🌊
**When**: Volatility exceeds limits (IV > 30% OR RV > 55%)  
**Data Captured**:
- Current IV and RV percentages
- Max allowed IV/RV
- Cancelled orders (if any)
- Open positions count
- Blocked order price
- Halt reason

**Future Intentions**: "Resume trading when IV < 30% AND RV < 55%"

---

### 3. **price_update_during_halt** 📊
**When**: Price changes while bot is halted due to volatility  
**Data Captured**:
- Current price
- Volatility status (UNSAFE)
- Current IV and RV
- Missed grid levels
- Number of missed levels

**Future Intentions**: "Place 2 MARKET orders (ignore strict grid) if volatility normalizes"

---

### 4. **recovery_start** 🔄
**When**: Volatility normalizes and bot begins opportunistic recovery  
**Data Captured**:
- Normalized IV and RV percentages
- Current price
- Missed levels count

**Future Intentions**: "Analyze missed levels and place MARKET orders at better prices"

---

### 5. **recovery_complete** ✅
**When**: Opportunistic recovery finishes executing  
**Data Captured**:
- Number of positions filled
- Total capital saved
- Extra profit potential
- Execution details

**Future Intentions**: "Resume normal grid trading"

---

### 6. **order_placed** 📝
**When**: Bot places a new order (BUY or TP/SELL)  
**Data Captured**:
- Side (BUY/SELL)
- Price
- Size (lot)
- Order type
- Order ID
- Reason/context

**Future Intentions**:
- For BUY: "Place TP order at $XXX on fill"
- For TP: "Position will close and realize profit"

---

### 7. **order_filled** 💰
**When**: An order gets filled on the exchange  
**Data Captured**:
- Order type (grid/TP)
- Side (BUY/SELL)
- Fill price
- Size
- Order ID
- Profit (for TP fills)

**Future Intentions**:
- For BUY fill: "Wait for TP fill"
- For TP fill: "Place new BUY order one step below"

---

### 8. **max_tranches_reached** 🚫
**When**: Bot tries to place order but max open positions limit is reached  
**Data Captured**:
- Current tranche count
- Max allowed tranches
- Blocked order price
- Utilization percentage

**Future Intentions**: "Wait for any position to close (TP fill), then place BUY at $XXX"

---

### 9. **emergency_stop** 🛑
**When**: Emergency flag exists (.bot_shutdown file OR emergency_stop=True)  
**Data Captured**:
- Reason for emergency stop
- Active positions count
- Pending orders count
- Timestamp

**Future Intentions**:
- "ALL new orders blocked"
- "Existing positions kept with TP orders"
- "Manual intervention required - remove .bot_shutdown file"

**Importance**: CRITICAL

---

### 10. **gatekeeper_block** 🛡️
**When**: Safety Gatekeeper blocks an order (any safety check fails)  
**Data Captured**:
- Block reason (e.g., "execute_orders_disabled", "volatility_unsafe")
- Attempted action
- Order price
- Side (BUY/SELL)
- Additional context

**Future Intentions**: "Bot will retry when safety condition resolves"

**Importance**: HIGH

---

### 11. **margin_block** 📉
**When**: Margin utilization exceeds limit (default 80%)  
**Data Captured**:
- Current margin utilization %
- Margin limit %
- Blocked order price
- Amount over limit

**Future Intentions**:
- "Block new BUY orders until margin reduces"
- "TP/SELL orders still active (to reduce exposure)"
- "Recommendation: Close positions or add margin"

**Importance**: HIGH

---

### 12. **liquidation_warning** ⚠️
**When**: Liquidation distance enters DANGER zone  
**Data Captured**:
- Distance zone (DANGER/WARNING/CAUTION)
- Margin utilization %
- Blocked order price
- Liquidation distance %

**Future Intentions**:
- "Blocking new BUY orders - too close to liquidation"
- "TP orders active to reduce risk"
- "May emergency close positions if DANGER persists"

**Importance**: CRITICAL

---

### 13. **outside_grid** 🎯
**When**: Price moves outside configured grid boundaries  
**Data Captured**:
- Current price
- Grid upper limit
- Grid lower limit
- Distance from grid

**Future Intentions**:
- "Resume grid trading when price returns to $XXX - $XXX"
- "Hold existing positions with TP orders"
- "No new BUYs until price re-enters grid"

**Importance**: NORMAL

---

### 14. **order_rejected** ❌
**When**: Exchange rejects an order  
**Data Captured**:
- Rejection reason
- Order price
- Side (BUY/SELL)
- Exchange error message

**Future Intentions**:
- If insufficient funds: "Need to add funds"
- Otherwise: "Will retry on next price tick"

**Importance**: HIGH

---

## 📊 Event Statistics by Category

### **Trading Flow** (3 events)
1. bot_startup
2. order_placed
3. order_filled

### **Volatility Management** (4 events)
4. volatility_halt
5. price_update_during_halt
6. recovery_start
7. recovery_complete

### **Safety Blocks** (6 events)
8. max_tranches_reached
9. emergency_stop
10. gatekeeper_block
11. margin_block
12. liquidation_warning
13. outside_grid

### **Error Handling** (1 event)
14. order_rejected

---

## 🎯 Coverage Analysis

### ✅ **COVERED Decision Points**
- [x] Bot startup/initialization
- [x] Volatility halt trigger
- [x] Price monitoring during halt
- [x] Opportunistic recovery
- [x] Recovery completion
- [x] Order placement (BUY/TP)
- [x] Order fills (BUY/TP)
- [x] Max tranches limit
- [x] Emergency stop (.bot_shutdown)
- [x] Safety gatekeeper blocks
- [x] Margin utilization limit
- [x] Liquidation distance warnings
- [x] Price outside grid
- [x] Order rejections

### 🚫 **NOT COVERED** (Rare/Non-Critical)
- [ ] WebSocket reconnections (handled silently)
- [ ] Config parameter changes (logged to file)
- [ ] API rate limit warnings (handled by circuit breaker)
- [ ] Balance/equity updates (displayed in real-time panels)
- [ ] Heartbeat updates (system health, not user-facing)

---

## 🔍 How to Trigger Each Event (Testing)

### 1. bot_startup
```bash
./bot_launcher.py
```

### 2. volatility_halt
- Wait for IV > 30% OR RV > 55% (market conditions)
- Or manually set in config: `MAX_IV=10` (will trigger immediately)

### 3. price_update_during_halt
- Wait for price change while halted

### 4. recovery_start + recovery_complete
- Wait for volatility to normalize while bot is halted

### 5. order_placed + order_filled
- Normal grid trading operations

### 6. max_tranches_reached
- Set `MAX_OPEN=1` in config
- Wait for 1 BUY to fill
- Bot will try to place another BUY and log this event

### 7. emergency_stop
```bash
touch .bot_shutdown
```

### 8. gatekeeper_block
- Set `EXECUTE_ORDERS=false` in config

### 9. margin_block
- Set `MARGIN_UTIL_LIMIT=0.10` (10%) in config
- Open some positions to exceed 10% margin

### 10. liquidation_warning
- Requires leveraged position close to liquidation (dangerous!)
- Better to test in DEMO mode

### 11. outside_grid
- Set grid: `GRID_LOWER=105000`, `GRID_UPPER=110000`
- Wait for price to go above 110k or below 105k

### 12. order_rejected
- Set insufficient balance
- Or send invalid order parameters

---

## 📱 Frontend Display

All events display in the **Bot Actions** panel with:

### Event Card Structure
```
┌─────────────────────────────────────────┐
│ [Icon] EVENT TYPE         just now      │
├─────────────────────────────────────────┤
│ Data Field 1: Value                     │
│ Data Field 2: Value                     │
│ Data Field 3: Value                     │
├─────────────────────────────────────────┤
│ 💡 Future Intentions:                   │
│ • What bot will do next                 │
│ • Conditions for action                 │
└─────────────────────────────────────────┘
```

### Importance Colors
- **Low**: Gray
- **Normal**: Blue
- **High**: Yellow/Orange
- **Critical**: Red

### Filter Options
- **All**: Show all events
- **Important**: Show HIGH + CRITICAL only
- **Critical**: Show CRITICAL only

---

## 🎯 Success Criteria

✅ **System is Comprehensive When:**
1. Every user-facing bot decision has an event
2. Every safety block has clear messaging
3. Every halt/recovery state is visible
4. Future intentions are always shown
5. No "surprises" - user knows what's happening
6. Real-time WebSocket updates work

---

## 🚀 Next Steps (If Needed)

### Potential Future Events
- `config_changed` - When bot reloads config mid-run
- `balance_low_warning` - When balance drops below threshold
- `api_error` - When exchange API fails (beyond circuit breaker)
- `position_sync_failed` - When reconciliation finds mismatch

---

## 📝 Summary

**Total Events**: 14  
**Coverage**: ~95% of critical decisions  
**Frontend Ready**: ✅ Yes  
**Backend Ready**: ✅ Yes  
**Tested**: ⏳ Awaiting real-world conditions

**No more surprises!** 🎉
