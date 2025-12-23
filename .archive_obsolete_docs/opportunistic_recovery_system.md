# Opportunistic Recovery System - Complete Guide
**Last Updated:** November 19, 2025 | **Status:** ✅ Production Ready

---

## 🎯 What Is It?

**Opportunistic Recovery** turns volatility halts and price gaps into profit opportunities by filling missed grid levels at better prices.

### Key Benefits
- ✅ Extra profit from better entry prices
- ✅ Perfect grid alignment maintained
- ✅ Compatible with single pending order rule
- ✅ Comprehensive safety checks

---

## 📊 The Problem It Solves

**Scenario:** Bot halted, price drops $2,200

**Without Recovery:**
- Miss grid levels at $99k, $98k, $97k
- Resume normal trading
- No benefit from price drop

**With Recovery:**
- Fill all 3 missed grids at $96.8k
- Save $2,200 + $1,200 + $200 = $3,600
- Perfect grid alignment maintained

---

## 🔧 How It Works

### Two Scenarios

**1. Startup Recovery**
- Bot starts, price moved while offline
- Fills missed grids at current better price

**2. Runtime Recovery**
- Guardian halts trading (high volatility)
- Price moves during halt
- Guardian resumes, fills missed grids

### Dual Pricing System

Each position tracks TWO prices:
- `entry_price`: Grid level (for TP calculation)
- `actual_entry`: Real fill (for PnL tracking)
- `saved_capital`: Difference = extra profit

---

## ⚙️ Configuration

```yaml
safety:
  volatility:
    opportunistic_recovery:
      enabled: true
      max_orders_startup: 5       # Startup recovery limit
      max_orders_volatility: 5    # Runtime recovery limit
      execution_delay_ms: 300     # Delay between orders
      min_profit_margin: 500      # Minimum profit (INR)
      cooldown_seconds: 60        # Cooldown between recoveries
```

---

## 🏗️ Architecture

### Code Locations
- **Main Logic:** `bot/strategy/async_gridbot.py`
  - `_check_startup_opportunistic_recovery()` (lines 945-1002)
  - `_check_runtime_opportunistic_recovery()` (lines 1222-1288)
  - `_execute_startup_recovery()` (lines 1064-1220)
  - `_place_recovery_tp()` (lines 1004-1062)

### Execution Flow
```
1. DETECTION → Missed grids identified
2. SAFETY CHECKS → Comprehensive validation
3. RECOVERY MODE → Suspend normal operations
4. ORDER EXECUTION → MARKET orders + TPs
5. RESUME NORMAL → Immediate grid placement
```

---

## 🛡️ Safety Integration

**Multi-Layer Checks:**
1. Pre-recovery comprehensive check
2. Per-order safety validation
3. Cooldown enforcement
4. Price movement validation
5. Guardian signal verification

---

## 🔄 Single Pending Order Compatibility

**Why No Conflict:**
- MARKET orders execute instantly (never "pending")
- Sequential execution (one at a time)
- TP orders are reduce_only (different category)
- Recovery mode suspends normal operations

---

## 🐛 Race Condition Prevention

**Problem:** WebSocket and recovery both try to place TP

**Solution:**
```python
# Pre-register with processed=True IMMEDIATELY
self._recovery_orders[order_id] = {
    'processed': True,  # Blocks WebSocket saga
    'tp_placed': False
}

# WebSocket checks and skips
if order_id in self._recovery_orders:
    return  # Skip saga processing
```

---

## ✅ Testing

### Startup Recovery Test
```bash
# 1. Stop bot
pm2 stop gridbot-live

# 2. Wait for price to move past grids

# 3. Start bot
pm2 start gridbot-live

# 4. Check logs
pm2 logs gridbot-live | grep -i "recovery"
```

### Expected Output
```
🔄 OPPORTUNISTIC RECOVERY MODE ACTIVATED
🎯 Processing 3 missed grid level(s)
🎯 Recovery 1/3: Placing BUY MARKET order
✅ Recovery order FILLED at $97,000 (grid: $99,000)
💰 Saved $2,000
🔄 RECOVERY MODE DEACTIVATED
📍 Placing next grid order to resume normal trading
```

---

## 🔍 Troubleshooting

### Recovery Not Triggering
**Check:**
1. `enabled: true` in config.yaml
2. `max_orders_startup > 0`
3. Price actually moved past grids
4. Safety checks passing

### Duplicate TPs
✅ **FIXED** Nov 19, 2025
- Pre-registration prevents race condition

### Normal Trading Not Resuming
✅ **FIXED** Nov 19, 2025
- Immediate grid placement after recovery

---

## 📈 Examples

### Example 1: Startup (LONG)
```
Price: $100k → $97k (bot offline)
Missed: $99k, $98k
Recovery: 2 MARKET BUYs at $97k
TPs: $100k, $99k
Saved: $2k + $1k = $3k
```

### Example 2: Runtime (SHORT)
```
Halt at $95k, price rises to $98k
Missed: $96k, $97k
Recovery: 2 MARKET SELLs at $98k
TPs: $95k, $96k
Saved: $2k + $1k = $3k
```

---

## 📝 Key Files

1. **OPPORTUNISTIC_RECOVERY_SYSTEM.md** (deleted - merged here)
2. **RECOVERY_SYSTEM_RESTORED_NOV19_2025.md** (deleted - merged here)
3. **VOLATILITY_RECOVERY_IMPLEMENTATION_COMPLETE_NOV16_2025.md** (deleted - merged here)
4. **This file** - Single source of truth

---

## 🎓 Summary

**What:** Fills missed grids at better prices  
**When:** Startup or runtime (Guardian resume)  
**How:** MARKET orders with dual pricing  
**Why:** Extra profit + grid alignment  
**Status:** ✅ Production ready

**Configuration:** `config.yaml` → `safety.volatility.opportunistic_recovery`  
**Code:** `bot/strategy/async_gridbot.py` lines 945-1320  
**Testing:** `pm2 logs gridbot-live | grep recovery`

---

**Last Updated:** November 19, 2025  
**All Known Issues:** FIXED  
**Production Status:** ✅ READY
