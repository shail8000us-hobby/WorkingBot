# Risk & Safety Configuration Audit - November 15, 2025

## Executive Summary

**CRITICAL FINDING**: Multiple risk/safety components are still using `os.getenv()` instead of YAML configuration, creating inconsistent configuration management and potential safety gaps.

**Status**: 🔴 **REQUIRES IMMEDIATE REBUILD**

---

## Components Using `os.getenv()` (NOT YAML-integrated)

### 1. **bot/safety/loss_limits.py** ❌
- `MAX_ACCOUNT_LOSS_INR` → needs `risk_limits.max_account_loss_inr`
- `GUARDIAN_MAX_ACCOUNT_LOSS_INR` → needs `guardian.max_account_loss_inr`

### 2. **bot/safety/gatekeeper.py** ❌
- `EXECUTE_ORDERS` → needs `safety.execute_orders`
- `TRADING_MODE` → already in root `trading_mode` ✅
- `I_UNDERSTAND_LIVE` → needs `safety.live_acknowledgment`
- `MAX_PENDING_NOTIONAL_INR` → already in `capital_protection.pending_budget.max_notional_inr` ✅
- `PENDING_BUDGET_BUFFER_PCT` → already in `capital_protection.pending_budget.buffer_pct` ✅
- `GRIDBOT_REF`, `GRIDBOT_LOWER`, `GRIDBOT_LOT` → already in `grid.*` ✅

### 3. **bot/safety/exposure_limiter.py** ❌
- `EXPOSURE_GROWTH_ENABLED` → already in `capital_protection.exposure_growth.enabled` ✅
- `MAX_NEW_TRANCHES_PER_MINUTE` → already in `capital_protection.exposure_growth.max_tranches_per_minute` ✅
- `MAX_NOTIONAL_INR_PER_MINUTE` → already in `capital_protection.exposure_growth.max_notional_inr_per_minute` ✅
- `EXPOSURE_GROWTH_QUEUE_ENABLED` → already in `capital_protection.exposure_growth.queue_enabled` ✅

### 4. **bot/safety/order_confirmation_guard.py** ✅ (Partially)
- `CONFIRMATION_GUARD_ENABLED` → already in `safety.confirmation_guard.enabled` ✅
- `CONFIRMATION_POLL_INTERVAL` → already in `safety.confirmation_guard.poll_interval` ✅
- `CONFIRMATION_CHAOS_THRESHOLD` → already in `safety.confirmation_guard.chaos_threshold` ✅

### 5. **bot/safety/config_guard.py** ❌
- `TWO_MAN_RULE_ENABLED` → already in `capital_protection.two_man_rule.enabled` ✅
- `TWO_MAN_RULE_TIMEOUT_SEC` → already in `capital_protection.two_man_rule.timeout_seconds` ✅
- `TWO_MAN_RULE_AUTO_REVERT` → already in `capital_protection.two_man_rule.auto_revert` ✅

### 6. **bot/capital/equity_floor.py** ❌
- `EQUITY_FLOOR_INR` → already in `capital_protection.equity_floor.floor_inr` ✅
- `EQUITY_FLOOR_CHECK_INTERVAL` → already in `capital_protection.equity_floor.check_interval` ✅
- `USD_TO_INR_RATE` → needs `risk_limits.usd_to_inr_rate` (already exists ✅)

### 7. **bot/capital/equity_tracker.py** ❌
- `TRADING_MODE` → already in root `trading_mode` ✅
- `DRAWDOWN_CAP_ENABLED` → already in `capital_protection.drawdown_cap.enabled` ✅
- `DRAWDOWN_MAX_PCT` → already in `capital_protection.drawdown_cap.max_pct` ✅
- `DRAWDOWN_WINDOW_DAYS` → already in `capital_protection.drawdown_cap.window_days` ✅
- `DRAWDOWN_HYSTERESIS_PCT` → already in `capital_protection.drawdown_cap.hysteresis_pct` ✅

### 8. **bot/capital/pending_budget.py** ❌
- `MAX_PENDING_NOTIONAL_INR` → already in `capital_protection.pending_budget.max_notional_inr` ✅
- `PENDING_BUDGET_BUFFER_PCT` → already in `capital_protection.pending_budget.buffer_pct` ✅

### 9. **bot/volatility/iv_rv_tracker.py** ✅ (FIXED)
- Already migrated to YAML config ✅

---

## Missing from config.yaml

### Critical Safety Parameters:
1. **`safety.execute_orders`** ❌ - Controls dry-run vs real trading
2. **`safety.live_acknowledgment`** ❌ - Explicit live mode confirmation
3. **`capital_protection.equity_floor.require_acknowledgment`** ✅ - Already present

### Risk Limits Parameters:
All present in config.yaml ✅

---

## YAML Config Coverage Analysis

### ✅ **Fully Covered in config.yaml**:
- `grid.*` - All grid parameters
- `capital_protection.equity_floor.*`
- `capital_protection.drawdown_cap.*`
- `capital_protection.two_man_rule.*`
- `capital_protection.exposure_growth.*`
- `capital_protection.pending_budget.*`
- `safety.volatility.*`
- `safety.circuit_breaker.*`
- `safety.confirmation_guard.*`
- `guardian.*`
- `liquidation_protection.*`
- `risk_limits.usd_to_inr_rate`

### ❌ **Missing from config.yaml**:
1. `safety.execute_orders` (boolean)
2. `safety.live_acknowledgment` (string: "YES" or "")

---

## Components That Need Code Updates

### Priority 1 - Critical Safety:
1. **bot/safety/gatekeeper.py**
   - Add YAML config loader
   - Replace `os.getenv('EXECUTE_ORDERS')` with `yaml_config.safety.execute_orders`
   - Replace `os.getenv('I_UNDERSTAND_LIVE')` with `yaml_config.safety.live_acknowledgment`

2. **bot/safety/loss_limits.py**
   - Add YAML config loader
   - Replace `os.getenv('MAX_ACCOUNT_LOSS_INR')` with `yaml_config.risk_limits.max_account_loss_inr`
   - Replace `os.getenv('GUARDIAN_MAX_ACCOUNT_LOSS_INR')` with `yaml_config.guardian.max_account_loss_inr`

### Priority 2 - Capital Protection:
3. **bot/capital/equity_floor.py**
   - Add YAML config loader
   - Replace all `os.getenv()` with `yaml_config.capital_protection.equity_floor.*`

4. **bot/capital/equity_tracker.py**
   - Add YAML config loader
   - Replace all `os.getenv()` with `yaml_config.capital_protection.drawdown_cap.*`

5. **bot/capital/pending_budget.py**
   - Add YAML config loader
   - Replace all `os.getenv()` with `yaml_config.capital_protection.pending_budget.*`

### Priority 3 - Safety Systems:
6. **bot/safety/exposure_limiter.py**
   - Add YAML config loader
   - Replace all `os.getenv()` with `yaml_config.capital_protection.exposure_growth.*`

7. **bot/safety/config_guard.py**
   - Add YAML config loader
   - Replace all `os.getenv()` with `yaml_config.capital_protection.two_man_rule.*`

---

## Recommended config.yaml Additions

```yaml
# Add to safety section:
safety:
  # Existing...
  execute_orders: false           # CRITICAL: Controls real trading
  live_acknowledgment: ""         # Must be "YES" for live trading
  
  # Existing sections remain...
  flash_move: {}
  spread_guard: {}
  volatility: {...}
  circuit_breaker: {...}
  confirmation_guard: {...}
```

---

## Implementation Plan

### Phase 1: Update config.yaml
1. Add `safety.execute_orders: false`
2. Add `safety.live_acknowledgment: ""`

### Phase 2: Update Components (in order)
1. ✅ bot/volatility/iv_rv_tracker.py (ALREADY DONE)
2. bot/safety/gatekeeper.py
3. bot/safety/loss_limits.py
4. bot/capital/equity_floor.py
5. bot/capital/equity_tracker.py
6. bot/capital/pending_budget.py
7. bot/safety/exposure_limiter.py
8. bot/safety/config_guard.py

### Phase 3: Testing
1. Verify all components load YAML config
2. Test fallback behavior (YAML → env vars)
3. Validate safety systems still work
4. Check WebUI integration

### Phase 4: Deprecation
1. Add warnings for env var usage
2. Document migration path
3. Update all documentation

---

## Risk Assessment

**Current State**: 🔴 **HIGH RISK**
- Inconsistent configuration sources
- Some safety checks use YAML, others use env vars
- Potential for missed safety parameters during configuration changes

**Post-Migration**: 🟢 **LOW RISK**
- Single source of truth (config.yaml)
- Type-safe Pydantic validation
- Easier configuration auditing
- WebUI can directly edit safety parameters

---

## Files Requiring Updates

### Code Files (8 files):
1. `/Users/ssr/Projects/WorkingBot/bot/safety/gatekeeper.py`
2. `/Users/ssr/Projects/WorkingBot/bot/safety/loss_limits.py`
3. `/Users/ssr/Projects/WorkingBot/bot/capital/equity_floor.py`
4. `/Users/ssr/Projects/WorkingBot/bot/capital/equity_tracker.py`
5. `/Users/ssr/Projects/WorkingBot/bot/capital/pending_budget.py`
6. `/Users/ssr/Projects/WorkingBot/bot/safety/exposure_limiter.py`
7. `/Users/ssr/Projects/WorkingBot/bot/safety/config_guard.py`
8. `/Users/ssr/Projects/WorkingBot/bot/safety/blocker_tracker.py` (comprehensive update)

### Config Files (1 file):
1. `/Users/ssr/Projects/WorkingBot/config.yaml`

---

## Next Steps

1. **Review and approve** this audit
2. **Update config.yaml** with missing parameters
3. **Systematically migrate** each component to YAML
4. **Test thoroughly** after each migration
5. **Deploy** with confidence

---

**Generated**: November 15, 2025  
**Status**: Ready for Implementation
