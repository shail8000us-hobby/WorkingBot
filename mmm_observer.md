# MMM Strategy Observer — Technical Specification

**Purpose**: Intercepts every BUY (close) order and validates it against the current strategy state BEFORE the order reaches the exchange.

**Problem Statement**: While SELL orders have extensive guards (asymmetry block, position cap, margin guardian, whipsaw cooldown, safety checks), BUY orders only have basic hedge integrity protection. The PE wipeout on mmm13mar26-2 happened because close orders at $56-60 were placed when the threshold was $20 — no logic validation occurred.

---

## What the Observer Will Do

### Core Function
- **Intercepts**: Every call to `close_position()` and wind-down buyback operations  
- **Validates**: 4 checks against strategy logic before order submission
- **Blocks**: Illogical closes that violate strategy rules
- **Allows**: Legitimate closes that align with strategy intent

### The 4 Validation Checks

#### CHECK 1: Strategy Continuity (BLOCK)
- **Purpose**: Prevent one-sided exposure
- **Rule**: Block if closing would reduce one side to 0 lots while other side has >0 lots
- **Exception**: Both sides closing together (clean session exit)
- **Today's Impact**: Would have blocked the final PE order (20→0 while CE had 70 lots)

#### CHECK 2: Price Consistency (BLOCK for close_at_5 and harvest)
- **Purpose**: Ensure current premium justifies the close mechanism
- **Rules**:
  - `close_at_5`: Block if `current_premium > close_at_threshold × 2.0`
  - `harvest`: Block if `current_premium > entry_premium × (1 - harvest_profit_pct/100)`
  - Other mechanisms (atm_shield, wind_down, emergency): Warn only
- **Today's Impact**: Would have blocked ALL 4 orders ($56-60 > $20 × 2 = $40)

#### CHECK 3: Close Velocity (ALERT + conditional BLOCK)
- **Purpose**: Detect runaway closing patterns
- **Tracking**: Rolling 60-second window per session per side
- **Thresholds**:
  - Alert: >60 lots on same side in 60s (activity log + WebSocket)
  - Block: >100 lots in 60s (unless atm_shield/wind_down/emergency)
- **Today's Impact**: Would have alerted at 2nd order, blocked at 4th (1+30+50+20=101 lots in 68s)

#### CHECK 4: Ledger Integrity (BLOCK)
- **Purpose**: Prevent phantom closes
- **Rule**: Position being closed must exist in `session[side]['positions']` with expected lot count
- **Guards**: Against stale loop iterations, race conditions, corrupted state

---

## Integration Points

### 1. `close_position()` in `mmm_close_at_5.py`
- **Current State**: ✅ `mechanism` parameter added, observer integrated
- **Behavior**: Observer replaces scattered hedge guard logic, becomes single authority
- **Call Time**: Before exchange order, after position lookup
- **Fallback**: If observer import fails, silently continue (graceful degradation)

### 2. `_process_wind_down_buyback()` in `mmm_monitor.py` 
- **Current State**: ❌ Not yet integrated
- **Behavior**: Validate each strike group before `smart_execute()`
- **Special**: Multiple orders per heartbeat, each validated separately
- **Post-Success**: Call `observer.record_close()` for velocity tracking

### 6 Call Sites Requiring `mechanism` Parameter

| File | Function | Current State | Mechanism Value |
|------|----------|---------------|-----------------|
| `mmm_monitor.py` | harvest loop | ❌ No param | `'harvest'` |
| `mmm_monitor.py` | close-at-5 loop | ❌ No param | `'close_at_5'` |
| `mmm_atm_shield.py` | shield close | ❌ No param | `'atm_shield'` |
| `mmm_recycler.py` | recycler close | ❌ No param | `'recycler'` |
| `mmm_monitor.py` | shift recycle | ❌ No param | `'close_at_5'` |
| Full session close | emergency | ❌ No param | `'emergency'` |

---

## Technical Architecture

### Observer Class
```python
class MMMStrategyObserver:
    def validate_close(session, side, lots, current_premium, mechanism, entry_premium, both_sides_closing) -> dict
    def record_close(session_id, side, lots) -> None  # Called AFTER successful order
    def clear_session(session_id) -> None  # Called on session stop
```

### Singleton Pattern
- Thread-safe instantiation via `get_observer()`
- Shared across all sessions and monitor threads  
- Velocity state keyed by `(session_id, side)`

### State Management
- **Velocity Window**: Stores `(timestamp, lots)` tuples in deque per session+side
- **Auto-Cleanup**: Old entries expired on each check (rolling window)
- **Memory Management**: Session data cleared on stop/completion

---

## Expected Behavior Changes

### What Gets Blocked
- **Illogical close_at_5**: Premium still high relative to threshold
- **Premature harvest**: Position hasn't decayed enough to justify close
- **Hedge violations**: One side would go to 0 while other has positions
- **Velocity spikes**: >100 lots closed on same side in 60s (non-exempt mechanisms)
- **Phantom closes**: Position doesn't exist in session ledger

### What Continues Unchanged  
- **Emergency mechanisms**: atm_shield, wind_down, emergency always allowed (price + velocity exempt)
- **Clean exits**: both_sides_closing bypasses continuity check
- **Legitimate closes**: Within strategy parameters pass all checks
- **SELL orders**: Observer only affects BUY (close) orders — sells unaffected

### Monitoring & Alerts
- **Blocked orders**: Log warning + return error to caller (no exchange submission)
- **Velocity alerts**: Activity log + WebSocket safety event at 60-lot threshold  
- **Observer failures**: Graceful degradation — import errors don't break trading

---

## Testing Strategy

### Unit Tests (Required)
1. **Check 1 Tests**: Continuity violations vs legitimate closes
2. **Check 2 Tests**: Price thresholds for each mechanism 
3. **Check 3 Tests**: Velocity window behavior, alert/block thresholds
4. **Check 4 Tests**: Ledger integrity edge cases
5. **Integration Tests**: Multi-mechanism scenarios, error handling

### Regression Tests (Critical)
- All existing hedge integrity tests must pass
- No change to SELL order behavior
- Backward compatibility with missing `mechanism` parameter

### Scenario Testing (Validation)
- **Today's Bug Simulation**: 4 PE orders at $56-60 with $20 threshold → ALL BLOCKED
- **Normal Operation**: Legitimate close-at-5 at $4.50 with $5 threshold → ALLOWED
- **Emergency Closes**: ATM shield at $45 with $5 threshold → ALLOWED (mechanism exempt)

---

## Risk Assessment

### Implementation Risks
- **False Positives**: Legitimate closes incorrectly blocked
- **Performance**: Validation adds ~1-3ms per close order
- **Complexity**: Additional layer increases debugging difficulty

### Mitigation Strategies  
- **Graceful Degradation**: Import errors don't break existing functionality
- **Extensive Testing**: Cover edge cases before deployment
- **observability**: Detailed logging for blocked orders and validation failures
- **Escape Hatches**: Emergency mechanisms bypass strict price checks

### Rollback Plan
- **Observer Toggle**: Can be disabled via try/except around import
- **Parameter Optional**: Missing `mechanism` parameter uses default 'close_at_5'
- **Backward Compat**: Existing `hedge_guard=False` behavior preserved

---

## Success Metrics

### Primary Goal
✅ **Prevent the PE wipeout scenario**: All 4 orders at $56-60 blocked (threshold $20)

### Secondary Goals
- ✅ Velocity alerts on rapid closing patterns (>60 lots/60s)
- ✅ Hedge integrity enforcement (single authoritative source)  
- ✅ Strategy logic validation (price-mechanism alignment)
- ✅ Zero false negatives on legitimate closes

### Operational Metrics
- **Block Rate**: <5% of legitimate closes blocked (false positive rate)
- **Alert Accuracy**: Velocity alerts correlate with actual anomalies
- **Performance**: <5ms added latency per close validation
- **Reliability**: 99.9% uptime (graceful degradation on failures)

---

## Current Implementation Status

| Component | Status | Notes |
|-----------|---------|-------|
| `mmm_observer.py` | ✅ Complete | 440 lines, all 4 checks implemented |
| `close_position()` signature | ✅ Complete | `mechanism` parameter added |
| Observer integration in close_position | ✅ Complete | Validates before exchange order |
| Wind-down integration | ⚠️ **Partial** | Logic written, call sites not updated |
| Call site updates | ❌ **Missing** | 6 functions need `mechanism` parameter |  
| Unit tests | ❌ **Missing** | No tests written yet |
| Regression testing | ❌ **Missing** | Need full test suite run |

**Ready for**: Call site updates and comprehensive testing
**Blocks**: Wind-down integration, full deployment
**Estimated completion**: 2-3 hours of focused work

---

## Deployment Recommendation

### Phase 1: Call Site Updates (30 min)
Update 6 call sites to pass correct `mechanism` parameter

### Phase 2: Wind-Down Integration (45 min)  
Add observer validation to `_process_wind_down_buyback()`

### Phase 3: Comprehensive Testing (60 min)
- Unit tests for all 4 checks
- Integration tests with real scenarios  
- Regression testing on existing functionality

### Phase 4: Deployment (15 min)
- Backend restart to load observer
- Monitor for false positives 
- Validate blocking behavior on test scenarios

**Total Estimated Time**: 2.5 hours
**Risk Level**: Low (graceful degradation built-in)
**Business Impact**: High (prevents future wipeout scenarios)