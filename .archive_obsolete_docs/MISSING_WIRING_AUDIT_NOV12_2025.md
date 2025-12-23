# Missing Grid Config Wiring Audit - November 12, 2025

## Executive Summary

**Status**: ⚠️ **CRITICAL GAPS FOUND** - AsyncGridBot is missing wiring for 15+ critical configuration parameters from grid_config.env

**Impact**: Bot will run with hardcoded defaults instead of user configuration, causing:
- Safety features disabled (loss limits, volatility protection)
- Order tagging disabled (orphan orders on restart)
- Post-only mode not configurable
- Startup behavior not configurable
- Grid strictness not configurable

## Critical Missing Parameters

### 1️⃣ **SAFETY FEATURES** (CRITICAL - PRODUCTION BLOCKER)

| Parameter | Value in Config | Currently Wired | Impact |
|-----------|----------------|-----------------|--------|
| `MAX_ACCOUNT_LOSS_INR` | 25000 | ❌ NO | Loss limits NOT enforced |
| `VOLATILITY_SAFETY_ENABLED` | true | ❌ NO | Trading in extreme volatility |
| `CONFIRMATION_GUARD_ENABLED` | true | ❌ NO | No order fill confirmation |
| `CIRCUIT_BREAKER_ENABLED` | true | ❌ NO | No API failure protection |
| `LIQUIDATION_PROTECTION_ENABLED` | true | ❌ NO | No liquidation monitoring |

**Risk**: Bot can lose unlimited money, trade in dangerous conditions, and get liquidated.

---

### 2️⃣ **ORDER MANAGEMENT** (HIGH PRIORITY)

| Parameter | Value in Config | Currently Wired | Impact |
|-----------|----------------|-----------------|--------|
| `GRIDBOT_TAG_PREFIX` | "GBOT_" | ❌ NO | Orders not tagged, can't identify bot orders |
| `GRIDBOT_POST_ONLY_MODE` | "auto" | ⚠️ PARTIAL | Hardcoded to `True`, not configurable |
| `GRIDBOT_CANCEL_ALL_ON_START` | 0 | ❌ NO | Startup behavior not configurable |
| `GRIDBOT_CANCEL_SCOPE` | "tagged" | ❌ NO | Cancel scope not respected |
| `GRIDBOT_ADOPT_UNTAGGED` | 0 | ❌ NO | Can't adopt existing orders |

**Risk**: 
- Orphan orders on restart (no tagging)
- Can't distinguish bot orders from manual orders
- Unpredictable startup behavior

---

### 3️⃣ **GRID BEHAVIOR** (MEDIUM PRIORITY)

| Parameter | Value in Config | Currently Wired | Impact |
|-----------|----------------|-----------------|--------|
| `GRIDBOT_GRID_MODE` | "LONG" | ✅ YES | ✓ Passed to AsyncGridBot |
| `GRIDBOT_STRICT_GRID` | 1 | ❌ NO | Grid enforcement not configurable |
| `GRIDBOT_STRICT_START` | 1 | ❌ NO | First order placement not configurable |
| `GRIDBOT_SEED_INITIAL_COUNT` | 0 | ❌ NO | Initial seeding not implemented |
| `SMART_GAP_FILL` | false | ❌ NO | Gap fill strategy not implemented |

**Risk**: Grid behavior doesn't match user expectations.

---

### 4️⃣ **TIMING & RETRIES** (LOW PRIORITY)

| Parameter | Value in Config | Currently Wired | Impact |
|-----------|----------------|-----------------|--------|
| `GRIDBOT_MAX_RETRIES` | 3 | ⚠️ PARTIAL | Hardcoded in OrderActor (default 3) |
| `GRIDBOT_RETRY_DELAY` | 2.0 | ❌ NO | Uses exponential backoff instead |
| `GRIDBOT_COOLDOWN_SECONDS` | 30 | ❌ NO | No cooldown between orders |
| `GRIDBOT_HB_SEC` | 20 | ❌ NO | Heartbeat uses fixed 5s interval |

**Risk**: Minor - defaults are reasonable.

---

## Current Wiring Status (AsyncGridBot Constructor)

### ✅ **Successfully Wired** (7 parameters)
```python
AsyncGridBot(
    api_key=api_key,           # ✅ From env
    api_secret=api_secret,     # ✅ From env
    symbol=symbol,             # ✅ From GRIDBOT_SYMBOL
    product_id=product_id,     # ✅ From env
    mode=mode,                 # ✅ From GRIDBOT_GRID_MODE
    lower_price=lower,         # ✅ From GRIDBOT_LOWER
    upper_price=upper,         # ✅ From GRIDBOT_UPPER
    grid_step=step,            # ✅ From GRIDBOT_STEP
    tp_offset=step,            # ✅ Uses GRIDBOT_STEP
    max_positions=max_open,    # ✅ From GRIDBOT_MAX_OPEN
    testnet=testnet            # ✅ From env
)
```

### ❌ **NOT Wired** (15+ parameters)

**Safety Features**:
- MAX_ACCOUNT_LOSS_INR
- VOLATILITY_SAFETY_ENABLED + thresholds
- CONFIRMATION_GUARD_ENABLED + settings
- CIRCUIT_BREAKER_ENABLED + settings
- LIQUIDATION_PROTECTION_ENABLED + settings

**Order Management**:
- GRIDBOT_TAG_PREFIX
- GRIDBOT_POST_ONLY_MODE (hardcoded True)
- GRIDBOT_CANCEL_ALL_ON_START
- GRIDBOT_CANCEL_SCOPE
- GRIDBOT_ADOPT_UNTAGGED

**Grid Behavior**:
- GRIDBOT_STRICT_GRID
- GRIDBOT_STRICT_START
- GRIDBOT_SEED_INITIAL_COUNT
- SMART_GAP_FILL + settings
- GRIDBOT_RUNG_SNAP_MODE

---

## Recommended Fix Priority

### 🔴 **PRIORITY 1: SAFETY FEATURES** (Production Blocker)
Must be fixed before live trading with real money.

**Action Required**:
1. Add safety parameters to AsyncGridBot.__init__()
2. Implement loss limit checks before each order
3. Integrate volatility monitor
4. Implement confirmation guard
5. Implement circuit breaker

**Estimated Work**: 3-4 hours

---

### 🟠 **PRIORITY 2: ORDER TAGGING** (High Priority)
Critical for production reliability.

**Action Required**:
1. Add `tag_prefix` parameter to AsyncGridBot
2. Generate order tags: `{prefix}{side}_{price}_{timestamp}`
3. Pass tags to order placement
4. Implement tag-based order identification on restart

**Estimated Work**: 1-2 hours

---

### 🟡 **PRIORITY 3: POST-ONLY CONFIGURATION** (Medium Priority)
Currently hardcoded, should be configurable.

**Action Required**:
1. Add `post_only_mode` parameter to AsyncGridBot
2. Implement "auto" mode (maker for BUY, taker for TP)
3. Pass configuration to OrderActor

**Estimated Work**: 30 minutes

---

### 🟢 **PRIORITY 4: GRID BEHAVIOR** (Low Priority)
Nice to have, not blocking.

**Action Required**:
1. Add strict_grid, strict_start parameters
2. Implement initial seeding (if seed_count > 0)
3. Consider smart gap fill implementation

**Estimated Work**: 2-3 hours

---

## Testing Recommendations

### Before Production Deployment:
1. ✅ Test with current wiring (99000-112000 grid) - **PASSED**
2. ⚠️ Test with safety limits (set MAX_ACCOUNT_LOSS_INR=1000)
3. ⚠️ Test order tagging (verify tags in Delta Exchange)
4. ⚠️ Test restart behavior (bot should recognize existing orders)
5. ⚠️ Test volatility protection (simulate high IV/RV)

### Production Readiness Checklist:
- [ ] Priority 1 (Safety) - **REQUIRED**
- [ ] Priority 2 (Tagging) - **REQUIRED**
- [ ] Priority 3 (Post-Only) - Recommended
- [ ] Priority 4 (Grid Behavior) - Optional

---

## Impact Analysis

### Current State (Without Missing Wiring):
- ✅ Bot can place orders at correct grid levels
- ✅ Bot respects grid boundaries (99000-112000)
- ✅ Bot uses correct step size (500)
- ✅ Bot respects max positions (5)
- ❌ Bot has NO safety limits
- ❌ Bot has NO order tagging
- ❌ Bot has NO startup reconciliation
- ❌ Bot has NO volatility protection

### Risk Assessment:
**Without Priority 1 Fixes**:
- Bot can lose ALL account balance
- Bot will trade in extreme volatility
- Bot has no circuit breaker for API failures
- **VERDICT**: ❌ **NOT PRODUCTION READY**

**With Priority 1 + 2 Fixes**:
- Bot has hard loss limits
- Bot has order identification
- Bot has basic safety features
- **VERDICT**: ✅ **PRODUCTION READY (Minimum Viable)**

**With All Priorities Fixes**:
- Bot is fully featured
- Bot matches grid_config.env specification
- Bot is professional-grade
- **VERDICT**: ✅ **PRODUCTION READY (Complete)**

---

## Next Steps

### Immediate (Before Next Trading Session):
1. **Implement Priority 1**: Safety features (loss limits, volatility)
2. **Implement Priority 2**: Order tagging
3. **Test all features** with 1000 INR test capital
4. **Verify configuration** loads correctly
5. **Monitor first 5 minutes** of live trading

### Short Term (This Week):
1. Implement Priority 3 (Post-Only)
2. Add comprehensive logging for all safety checks
3. Create safety feature test suite
4. Document all safety thresholds

### Long Term (Next Week):
1. Implement Priority 4 (Grid Behavior)
2. Add WebUI integration for safety status
3. Create real-time safety dashboard
4. Implement automated safety testing

---

## Conclusion

**Current Status**: AsyncGridBot has correct grid geometry wiring ✅ but is missing critical safety and management features ❌.

**Production Ready?**: NO - Requires Priority 1 + 2 fixes.

**Time to Production**: 4-6 hours of development + testing.

**Recommendation**: 
1. DO NOT trade with real money until Priority 1 is fixed
2. Implement loss limits as FIRST priority
3. Test extensively with 1000 INR before full capital
4. Monitor first trading session very closely

---

**Generated**: November 12, 2025
**Bot Version**: AsyncGridBot v1.0
**Config Version**: grid_config.env v3.3.0
