# WebUI YAML Configuration Migration Guide
**Date**: November 15, 2025  
**Status**: 🔄 **IN PROGRESS**

---

## Overview

The WebUI currently uses a mix of `grid_config.env` file reading and `os.getenv()` calls. This needs to be migrated to use the centralized YAML configuration system.

---

## New Utility Created

### `webui/backend/utils/yaml_config.py`

Provides three main functions:

```python
from webui.backend.utils.yaml_config import get_config_value, get_yaml_config, update_yaml_config

# Get single value with fallback
value = get_config_value(
    yaml_path="safety.execute_orders",  # Dot notation in YAML
    env_var="EXECUTE_ORDERS",           # Fallback env var
    default=False                        # Final fallback
)

# Get entire config
config = get_yaml_config()  # Returns full config dict

# Update YAML config
updates = {
    "safety.execute_orders": True,
    "grid.limits.lot_size": 2
}
success = update_yaml_config(updates)
```

---

## Migration Pattern for Routes

### Before (Old Pattern):
```python
from flask import Blueprint
import os

# Direct env var access
value = os.getenv('EQUITY_FLOOR_INR', '0')
enabled = os.getenv('DRAWDOWN_CAP_ENABLED', 'true').lower() == 'true'
```

### After (New Pattern):
```python
from flask import Blueprint
import os

# Add YAML config integration
try:
    from webui.backend.utils.yaml_config import get_config_value
    YAML_CONFIG_AVAILABLE = True
except Exception:
    YAML_CONFIG_AVAILABLE = False
    def get_config_value(y, e, d): return os.getenv(e, str(d))

# Use with fallback
value = float(get_config_value(
    'capital_protection.equity_floor.floor_inr',
    'EQUITY_FLOOR_INR',
    0
))
enabled = get_config_value(
    'capital_protection.drawdown_cap.enabled',
    'DRAWDOWN_CAP_ENABLED',
    True
)
```

---

## Files Requiring Migration

### Priority 1 - Critical Safety Routes (5 files)

#### 1. ✅ `webui/backend/routes/capital.py` (UPDATED)
- `/api/capital/equity-floor/status` - Uses YAML config ✅
- `/api/capital/drawdown/status` - Needs update
- `/api/capital/exposure/status` - Needs update
- `/api/capital/update-config` - Needs update

#### 2. `webui/backend/routes/robustness.py`
- `/api/robustness/volatility` - Uses env vars
- `/api/robustness/volatility/config` - Writes to grid_config.env
- **Action**: Update to use `get_config_value()` and `update_yaml_config()`

#### 3. `webui/backend/routes/liquidation.py`
- `/api/liquidation/status` - Uses env vars
- `/api/liquidation/config` - Reads from env vars
- **Action**: Update to use YAML config

#### 4. `webui/backend/routes/monitoring.py`
- `/api/monitoring/safety-status` - Reads many safety flags
- **Action**: Update to use YAML config

#### 5. `webui/backend/routes/guardian.py`
- Guardian-related endpoints
- **Action**: Update to use YAML config

---

### Priority 2 - Configuration Management (3 files)

#### 6. `webui/backend/routes/config.py`
- `/api/config/get` - Reads grid_config.env
- `/api/config/update` - Writes to grid_config.env
- **CRITICAL**: Needs full rewrite to work with config.yaml

#### 7. `webui/backend/routes/system.py`
- `/api/system/mode` - Mode switching
- **Action**: Update to use YAML config

#### 8. `webui/backend/routes/grid_mode.py`
- `/api/grid-mode/get` - Grid mode management
- **Action**: Update to use YAML config

---

### Priority 3 - Utility Routes (5 files)

#### 9. `webui/backend/routes/positions.py`
- USD_TO_INR_RATE usage
- **Action**: Update to use YAML config

#### 10. `webui/backend/routes/bot_control.py`
- TRADING_MODE, TELEGRAM tokens
- **Action**: Update to use YAML config

#### 11. `webui/backend/routes/utility.py`
- Grid calculations using env vars
- **Action**: Update to use YAML config

#### 12. `webui/backend/routes/health.py`
- Config file checks
- **Action**: Update to reference config.yaml

#### 13. `webui/backend/routes/risk.py`
- Risk status checks
- **Action**: Update to use YAML config

---

### Priority 4 - Brain Analyzer (6 files)

#### 14-19. Brain analyzer modules
- `state_reader.py`
- `master_brain_reader.py`
- `interactive_simulator.py`
- `realtime_predictor.py`
- `robust_simulator.py`
- `file_monitor.py`
- **Action**: Update to work with config.yaml

---

## Complete YAML Path Reference

### Safety Parameters
```
safety.execute_orders                      → EXECUTE_ORDERS
safety.live_acknowledgment                 → I_UNDERSTAND_LIVE
safety.volatility.enabled                  → VOLATILITY_SAFETY_ENABLED
safety.volatility.max_iv                   → VOLATILITY_MAX_IV
safety.volatility.max_rv                   → VOLATILITY_MAX_RV
safety.volatility.max_spread               → VOLATILITY_MAX_SPREAD
safety.circuit_breaker.enabled             → CIRCUIT_BREAKER_ENABLED
safety.confirmation_guard.enabled          → CONFIRMATION_GUARD_ENABLED
```

### Capital Protection Parameters
```
capital_protection.equity_floor.enabled    → EQUITY_FLOOR_INR (>0)
capital_protection.equity_floor.floor_inr  → EQUITY_FLOOR_INR
capital_protection.drawdown_cap.enabled    → DRAWDOWN_CAP_ENABLED
capital_protection.drawdown_cap.max_pct    → DRAWDOWN_MAX_PCT
capital_protection.exposure_growth.enabled → EXPOSURE_GROWTH_ENABLED
capital_protection.pending_budget.max_notional_inr → MAX_PENDING_NOTIONAL_INR
```

### Guardian Parameters
```
guardian.enabled                           → GUARDIAN_ENABLED
guardian.max_account_loss_inr             → GUARDIAN_MAX_ACCOUNT_LOSS_INR
```

### Liquidation Protection Parameters
```
liquidation_protection.enabled                    → LIQUIDATION_PROTECTION_ENABLED
liquidation_protection.margin_utilization_max     → MARGIN_UTILIZATION_MAX
liquidation_protection.liquidation_distance_min   → LIQUIDATION_DISTANCE_MIN
```

---

## Implementation Steps

### Step 1: Create Utility (DONE ✅)
- [x] Created `webui/backend/utils/yaml_config.py`
- [x] Added `get_config_value()` function
- [x] Added `get_yaml_config()` function
- [x] Added `update_yaml_config()` function
- [x] Added complete CONFIG_MAP

### Step 2: Update Priority 1 Routes (IN PROGRESS ⏳)
- [x] Started `capital.py` - equity floor endpoints updated
- [ ] Complete remaining `capital.py` endpoints
- [ ] Update `robustness.py`
- [ ] Update `liquidation.py`
- [ ] Update `monitoring.py`
- [ ] Update `guardian.py`

### Step 3: Rewrite Config Management (TODO 📋)
- [ ] Rewrite `config.py` to read/write config.yaml
- [ ] Update `system.py` for mode switching
- [ ] Update `grid_mode.py`

### Step 4: Update Utility Routes (TODO 📋)
- [ ] Update all remaining route files
- [ ] Update brain analyzer modules

### Step 5: Frontend Updates (TODO 📋)
- [ ] Update frontend to call new API endpoints
- [ ] Update config editing UI
- [ ] Add YAML validation UI

### Step 6: Testing & Validation (TODO 📋)
- [ ] Test all API endpoints
- [ ] Verify config reading/writing
- [ ] Test WebUI config editor
- [ ] Validate backward compatibility

---

## Breaking Changes

### None Expected ✅
- All route updates include fallback to env vars
- Graceful degradation if YAML unavailable
- Existing API contracts preserved
- Frontend requires no changes (yet)

---

## Benefits After Migration

1. **Single Source of Truth**: Config.yaml instead of grid_config.env
2. **Type Safety**: Pydantic validation on config writes
3. **Better UI**: Can show real-time config validation
4. **Easier Auditing**: YAML is more human-readable
5. **Consistent**: Bot and WebUI use same config
6. **Version Control Friendly**: YAML diffs better than .env

---

## Example: Complete Route Update

### Before:
```python
@capital_bp.route('/api/capital/equity-floor/status', methods=['GET'])
def get_equity_floor_status():
    floor_inr = float(os.getenv('EQUITY_FLOOR_INR', '0'))
    enabled = floor_inr > 0
    check_interval = int(os.getenv('EQUITY_FLOOR_CHECK_INTERVAL', '60'))
    require_ack = os.getenv('EQUITY_FLOOR_REQUIRE_ACK', 'true').lower() == 'true'
```

### After:
```python
# At top of file
try:
    from webui.backend.utils.yaml_config import get_config_value
    YAML_CONFIG_AVAILABLE = True
except Exception:
    YAML_CONFIG_AVAILABLE = False
    def get_config_value(y, e, d): return os.getenv(e, str(d))

@capital_bp.route('/api/capital/equity-floor/status', methods=['GET'])
def get_equity_floor_status():
    floor_inr = float(get_config_value(
        'capital_protection.equity_floor.floor_inr', 'EQUITY_FLOOR_INR', 0))
    enabled = get_config_value(
        'capital_protection.equity_floor.enabled', 'EQUITY_FLOOR_INR', floor_inr > 0)
    check_interval = int(get_config_value(
        'capital_protection.equity_floor.check_interval', 'EQUITY_FLOOR_CHECK_INTERVAL', 60))
    require_ack = get_config_value(
        'capital_protection.equity_floor.require_acknowledgment', 'EQUITY_FLOOR_REQUIRE_ACK', True)
```

---

## Next Steps

1. **Complete Priority 1 routes** (5 files, ~2-3 hours)
2. **Rewrite config.py** (Major work, ~4-6 hours)
3. **Update remaining routes** (~4-6 hours)
4. **Test thoroughly** (~2-3 hours)
5. **Update documentation** (~1 hour)

**Total Estimated Time**: 13-19 hours of development work

---

## Rollout Strategy

### Phase 1: Backend Only (Current)
- Update all routes to use YAML config
- Maintain env var fallbacks
- No frontend changes needed
- Deploy and monitor

### Phase 2: Config Editor
- Add config.yaml editor in WebUI
- Real-time validation UI
- Diff viewer for changes
- Deploy and gather feedback

### Phase 3: Deprecation
- Add warnings for env var usage
- Document migration path
- Remove grid_config.env support (6+ months)

---

**Status**: Created utility, started migration. Need user approval to continue with full WebUI migration.
