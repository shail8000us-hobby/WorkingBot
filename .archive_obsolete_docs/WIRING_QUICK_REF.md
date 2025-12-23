# Grid Config Wiring - Quick Reference

## 🚨 CRITICAL FINDING

**AsyncGridBot is missing 15+ critical configuration parameters from grid_config.env**

---

## What's Working ✅

```python
# Grid Geometry (7 parameters)
GRIDBOT_LOWER=99000          ✅ Wired → lower_price
GRIDBOT_UPPER=112000         ✅ Wired → upper_price  
GRIDBOT_STEP=500             ✅ Wired → grid_step
GRIDBOT_REF=105000           ✅ Used in bot/run.py
GRIDBOT_LOT=1                ✅ Wired → lot_size
GRIDBOT_MAX_OPEN=5           ✅ Wired → max_positions
GRIDBOT_GRID_MODE=LONG       ✅ Wired → mode
```

**Result**: Bot places orders at correct prices ✅

---

## What's MISSING ❌

### 🔴 Priority 1: SAFETY FEATURES (PRODUCTION BLOCKER)

```bash
# Current: Bot has NO safety limits!
MAX_ACCOUNT_LOSS_INR=25000           ❌ NOT wired → Bot can lose ALL money
VOLATILITY_SAFETY_ENABLED=true       ❌ NOT wired → Trades in extreme volatility
CONFIRMATION_GUARD_ENABLED=true      ❌ NOT wired → No order fill confirmation
CIRCUIT_BREAKER_ENABLED=true         ❌ NOT wired → No API failure protection
LIQUIDATION_PROTECTION_ENABLED=true  ❌ NOT wired → No liquidation monitoring
```

**Risk**: Bot can wipe out account, trade dangerously, get liquidated.

**Status**: ❌ **NOT PRODUCTION READY**

---

### 🟠 Priority 2: ORDER TAGGING (HIGH)

```bash
# Current: Orders NOT tagged, bot can't identify them!
GRIDBOT_TAG_PREFIX=GBOT_             ❌ NOT wired → No order tagging
GRIDBOT_CANCEL_ALL_ON_START=0        ❌ NOT wired → Unpredictable startup
GRIDBOT_CANCEL_SCOPE=tagged          ❌ NOT wired → Can't target tagged orders
GRIDBOT_ADOPT_UNTAGGED=0             ❌ NOT wired → Can't adopt existing orders
```

**Risk**: Orphan orders on restart, can't distinguish bot vs manual orders.

---

### 🟡 Priority 3: POST-ONLY (MEDIUM)

```bash
# Current: Hardcoded to True, not configurable
GRIDBOT_POST_ONLY_MODE=auto          ⚠️  HARDCODED → Always True
```

**Risk**: Can't configure maker/taker behavior.

---

### 🟢 Priority 4: GRID BEHAVIOR (LOW)

```bash
# Current: Using defaults
GRIDBOT_STRICT_GRID=1                ❌ NOT wired → Grid enforcement not configurable
GRIDBOT_STRICT_START=1               ❌ NOT wired → First order not configurable
GRIDBOT_SEED_INITIAL_COUNT=0         ❌ NOT wired → Can't seed initial orders
SMART_GAP_FILL=false                 ❌ NOT wired → Gap fill not implemented
```

**Risk**: Minor - defaults are reasonable.

---

## Impact Assessment

### Current Bot Capabilities:
- ✅ Places orders at correct grid levels (99000, 99500, 100000...)
- ✅ Respects grid boundaries (99000-112000)
- ✅ Uses correct step size (500)
- ✅ Respects max positions (5)
- ❌ **NO safety limits** (can lose unlimited money)
- ❌ **NO order tagging** (orphan orders)
- ❌ **NO startup reconciliation**
- ❌ **NO volatility protection**

### Risk Level by Priority:

| Priority | Risk Level | Production Ready? | Time to Fix |
|----------|-----------|-------------------|-------------|
| P1: Safety | 🔴 CRITICAL | ❌ NO | 3-4 hours |
| P2: Tagging | 🟠 HIGH | ⚠️  PARTIAL | 1-2 hours |
| P3: Post-Only | 🟡 MEDIUM | ✅ YES* | 30 min |
| P4: Grid | 🟢 LOW | ✅ YES | 2-3 hours |

*Works but not configurable

---

## Immediate Action Required

### Before Trading with Real Money:

```bash
# 1. DO NOT START BOT until P1 is fixed
❌ python3 -m bot.run  # DON'T DO THIS YET!

# 2. Implement Priority 1 (Safety Features)
# - Add max_account_loss_inr parameter
# - Add loss limit check before orders
# - Add safety halt mechanism

# 3. Implement Priority 2 (Order Tagging)  
# - Add tag_prefix parameter
# - Generate tags: GBOT_BUY_99000_1699876543
# - Wire to order placement

# 4. Test with small capital
MAX_ACCOUNT_LOSS_INR=1000  # Test with 1000 INR limit
python3 -m bot.run

# 5. Verify safety features work
# - Check loss limit triggers
# - Check orders are tagged
# - Check restart behavior
```

---

## Quick Fix Script

Create this script to validate wiring:

```bash
#!/bin/bash
# check_wiring.sh

echo "🔍 Checking grid_config.env wiring..."

# Check if safety parameters are set
grep -q "MAX_ACCOUNT_LOSS_INR" grid_config.env && echo "✅ MAX_ACCOUNT_LOSS_INR found" || echo "❌ MAX_ACCOUNT_LOSS_INR missing"

# Check if bot is using them
grep -q "max_account_loss_inr" bot/strategy/async_gridbot.py && echo "✅ Bot uses max_account_loss_inr" || echo "❌ Bot DOES NOT use max_account_loss_inr"

# Check tag prefix
grep -q "GRIDBOT_TAG_PREFIX" grid_config.env && echo "✅ TAG_PREFIX found" || echo "❌ TAG_PREFIX missing"
grep -q "tag_prefix" bot/strategy/actors/order_actor.py && echo "✅ OrderActor uses tag_prefix" || echo "❌ OrderActor DOES NOT use tag_prefix"

echo ""
echo "📋 Summary:"
echo "  Grid Geometry: ✅ WIRED"
echo "  Safety Features: ❌ NOT WIRED"
echo "  Order Tagging: ❌ NOT WIRED"
echo ""
echo "⚠️  Production Status: NOT READY"
```

---

## Files to Edit

### To Fix Priority 1 (Safety):
1. `bot/strategy/async_gridbot.py` - Add safety parameters
2. `bot/run.py` - Wire safety parameters from env
3. Add `_check_safety_limits()` method

### To Fix Priority 2 (Tagging):
1. `bot/strategy/actors/order_actor.py` - Add tag generation
2. `bot/strategy/async_gridbot.py` - Pass tag_prefix to actor
3. `bot/run.py` - Wire GRIDBOT_TAG_PREFIX

---

## Testing Commands

```bash
# 1. Test with current wiring (works but no safety)
python3 -m bot.run

# 2. After implementing P1+P2, test with small capital
MAX_ACCOUNT_LOSS_INR=1000 python3 -m bot.run

# 3. Verify tags on Delta Exchange
# Check order client_order_id field: should be "GBOT_BUY_99000_1699876543"

# 4. Test restart behavior
pkill -f "python3 -m bot.run"
python3 -m bot.run  # Should recognize existing orders

# 5. Test loss limit
# Let bot accumulate -1000 INR loss
# Verify: Bot stops placing new orders
# Verify: Telegram alert sent
```

---

## Success Criteria

### After P1+P2 Implementation:
- ✅ Bot stops trading when loss limit hit
- ✅ All orders have tags (GBOT_BUY_99000_...)
- ✅ Bot recognizes own orders on restart
- ✅ Safety halt logged and alerted
- ✅ Bot resumes when loss recovers

### Production Ready Checklist:
- [ ] P1 implemented and tested
- [ ] P2 implemented and tested  
- [ ] Tested with 1000 INR limit
- [ ] Verified tags on exchange
- [ ] Tested restart behavior
- [ ] Monitored for 1 hour with real money
- [ ] Loss limit triggered and recovered

---

## Contact for Implementation

**See detailed implementation plan**: `WIRING_FIX_IMPLEMENTATION_PLAN.md`

**Estimated time**: 4-6 hours development + testing

**Priority order**: P1 → P2 → P3 → P4

---

**Generated**: November 12, 2025
**Status**: ⚠️  Configuration audit complete - Implementation required
