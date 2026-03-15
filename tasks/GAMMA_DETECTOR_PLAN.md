# Gamma Detector Engine — Implementation Plan

> **Feature:** Portfolio curvature scanning — identify zones where losses begin to accelerate before breakeven
> **Author:** AI Plan — March 15, 2026
> **Status:** REVIEWED & CORRECTED — March 15, 2026
> **Review:** 9 code-verified findings against actual mmm_breakeven_engine.py, mmm_engine.py, mmm_monitor.py, mmm_state.py, mmm_config.py, mmm_websocket.py, mmm_activity.py, mmm_api.py
> **Depends on:** Breakeven Engine (fully implemented, `mmm_breakeven_engine.py`)

---

## REVIEW FINDINGS — CORRECTIONS TO ORIGINAL PLAN

The original plan had 9 errors found by auditing the actual codebase. Each is documented and corrected here before the implementation phases.

---

### Finding 1 — Phase 1 Eliminated (Method Rename Unnecessary)

**Original plan said:** Rename `_collect_open_positions` and `_compute_pnl_at_spot` to public methods in `mmm_breakeven_engine.py` via class-level aliases.

**Code reality:** Python's single-underscore convention is a naming convention only — it does not enforce access control. External callers can access `_method()` directly without any change to the defining class. The gamma detector can call `get_breakeven_engine()._collect_open_positions(session)`, `get_breakeven_engine()._compute_pnl_at_spot(...)`, and `get_breakeven_engine()._hash_positions(...)` directly.

**Verdict: Phase 1 eliminated.** Zero changes to `mmm_breakeven_engine.py`. This removes the only change to a sealed module, reducing risk significantly.

---

### Finding 2 — API URL Bug (Singular, Not Plural)

**Original plan said:** `GET /api/mmm/sessions/<id>/gamma`

**Code reality:** Every existing endpoint in mmm_api.py uses singular `/session/`:
```python
@mmm_bp.route('/session/<session_id>/breakeven', methods=['GET'])   # line 4343
```

**Correction:** Use `/session/<session_id>/gamma` — singular, matching all other MMM endpoints.

---

### Finding 3 — API Error Code Bug (404, Not 400)

**Original plan said:** Returns 400 on session not found.

**Code reality:** The breakeven endpoint at line 4355 returns `404`:
```python
return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404
```

**Correction:** Use 404, not 400. Also wrap response in `{'success': True/False, ...}` matching existing pattern.

---

### Finding 4 — Activity Category Misnamed

**Original plan said:** Gamma activity types belong to the `'warning'` set.

**Code reality:** There is no `'warning'` category in `ACTIVITY_CATEGORIES`. The four categories are: `'orders'`, `'adjustments'`, `'safety'`, `'system'`. Breakeven types belong to `'safety'` (confirmed at `mmm_activity.py` line 161).

**Correction:** Add gamma types to the `'safety'` category set.

---

### Finding 5 — Critical Algorithm Error: Threshold Defaults Are Wrong

**This is the most important finding. The original algorithm design produces a metric that is nearly always zero, making the default thresholds unreachable for typical sessions.**

**The math:** With the intrinsic-only piecewise-linear PnL model, the second-difference formula returns exactly zero everywhere EXCEPT within one step-width of a strike (the kink). The spike magnitude at any kink is:

```
spike = -(step_USD × N_lots_at_this_strike × LOT_SIZE_BTC)
      = -(step_USD × N × 0.001)
```

For `step_pct = 0.5%` at BTC=$90,000: `step_USD = $450`

| Session lots | Spike at kink |
|---|---|
| 10 lots | -4.5 USD |
| 50 lots | -22.5 USD |
| 100 lots | -45 USD |
| 500 lots | -225 USD |

**The original default thresholds: `gamma_warning_threshold: -100.0`, `gamma_danger_threshold: -300.0`**

These would require 222 lots just to trigger WARNING and 667 lots for DANGER. Most sessions run 10–100 lots. The detector would always report SAFE. Useless.

Additionally, the local severity score at the **current spot** is almost always zero unless the current spot is sitting exactly on top of a strike. Zone classification by severity-at-current-spot is conceptually wrong — it answers "is the market currently at a kink?" which is almost never true, rather than "how close is the market to a kink?"

**Root cause:** The plan conflated two separate concerns:
1. **Boundary detection** — walk outward and find where a kink (strike) exists
2. **Zone classification** — how dangerous is the current position relative to that boundary

The breakeven engine correctly uses distance-to-boundary for zone classification. The gamma detector should do the same.

**Correction: Redesign zone classification to distance-based (like breakeven engine)**

The corrected algorithm:
1. Walk outward from current spot, detecting the first kink (any non-trivial negative second-difference)
2. That kink IS the gamma boundary — because in this portfolio the kinks always occur at option strikes
3. Report the boundary price and the severity magnitude at that boundary
4. Classify zone by **distance from current spot to nearest boundary** (percentage), not by severity score

**New parameters replace the old thresholds:**
- Remove: `gamma_warning_threshold`, `gamma_danger_threshold`
- Add: `gamma_warning_distance_pct`, `gamma_danger_distance_pct`, `gamma_detect_epsilon`

The `gamma_detect_epsilon` is a small negative threshold (e.g., `-0.5`) used only for boundary detection: "is the second-difference meaningfully negative at this test point?" It needs to be small enough to detect any kink from even a 1-lot position at $450 step ($450 × 1 × 0.001 = $0.45), so `-0.3` is a safe floor.

This redesign makes gamma zone classification:
- Intuitive (percentage distance, same mental model as breakeven)
- Portfolio-size independent
- Consistent with the existing breakeven zone UX

---

### Finding 6 — `emit_heartbeat` Signature Must Be Updated

**Original plan said:** "Pass `gamma_data=session.get('_gamma_result')` into `emit_heartbeat(...)` call"

**Code reality:** `emit_heartbeat` currently ends with `breakeven_data: Dict = None` (verified at `mmm_websocket.py` line 106). There is no `gamma_data` parameter. Passing it as a keyword argument would raise a `TypeError`.

**Correction:** Phase 5 (WebSocket) must also add `gamma_data: Dict = None` to `emit_heartbeat`'s signature and add `if gamma_data: payload['gamma'] = gamma_data` in its body. This is an explicit required change.

---

### Finding 7 — Phase 10 `gamma_mult` Naming Collision

**In `mmm_engine.py`:** The variable `gamma_mult` already exists (lines 347–368) — it is the **T3-2 gamma-aware lot multiplier** that scales by aggressor premium excess percentage. This is completely different from the Phase 10 gamma severity multiplier.

**Risk:** If Phase 10 names the new variable `gamma_mult`, it shadows the existing one, silently breaking T3-2.

**The combined multiplier ceiling** (line 446–466):
```python
combined = gamma_mult * breakeven_mult * (boost_mult if session.get('_trend_boost_active') else 1.0)
```

Phase 10 must introduce a **distinctly named variable** (`gamma_severity_mult`) and include it in this formula:
```python
combined = gamma_mult * gamma_severity_mult * breakeven_mult * (boost_mult if ... else 1.0)
```

The ceiling trigger condition must also be updated to include `gamma_severity_mult > 1.0`.

---

### Finding 8 — `observation_only` Flag Needs Explicit Assignment Logic

**Original plan said:** Include `observation_only: bool` in GammaResult but didn't say where to compute it.

**Correction:** In `GammaDetector._build_result()`, set:
```python
'observation_only': not params.get('gamma_severity_multiplier_enabled', False)
```
This makes it `True` during all observation phases and `False` only when Phase 10 is explicitly enabled.

---

### Finding 9 — Monitor Step Numbering Confirmed

**Original plan said:** Insert Step 5.8 after Step 5.7 (Breakeven).

**Verified from code:** Step 5.7 (Breakeven) ends at line 1884. Step 6 (trigger evaluation) begins at line 1900 (after `_skip_to_pnl` gate). The gamma detector insertion point is correct: after line 1884, before the `_skip_to_pnl` check at line 1886. The comment in the plan should say "runs regardless of `_skip_to_pnl`" — which is also confirmed as the correct behavior by how Step 5.7 works.

---

## OVERVIEW

The Gamma Detector Engine identifies zones where the portfolio's loss rate begins to **accelerate** as BTC spot moves away from current price. It is a companion module to the Breakeven Engine.

- Breakeven Engine answers: **"Where does the portfolio lose money?"**
- Gamma Detector answers: **"Where does the portfolio start losing money faster?"**

Gamma danger zones appear **closer to current spot** than breakeven boundaries. This gives the operator two concentric warning rings:

```
Current Spot
     |
     |--- [gamma warning zone] --- [breakeven boundary]
     |
 [gamma warning zone] --- [breakeven boundary]
```

The gamma detector runs in **observation-only mode** initially. It logs zone transitions, stores results in session state, and pushes data to the dashboard. It has zero trading impact until explicitly enabled in Phase 10.

---

## ARCHITECTURE DECISIONS

### Decision 1: Direct Access to Breakeven Engine Private Methods

Python's `_method` convention is advisory. The gamma detector directly calls:
- `be_engine._collect_open_positions(session)` — get the same list of positions
- `be_engine._compute_pnl_at_spot(positions, spot_h, session)` — run PnL evaluation
- `be_engine._hash_positions(positions, session)` — compute identical position hash

**Zero changes to `mmm_breakeven_engine.py`.** The breakeven engine remains sealed.

### Decision 2: Corrected Algorithm — Boundary Detection + Distance-Based Zones

The second-difference formula correctly detects kinks in the piecewise-linear PnL curve. Kinks occur at option strikes. The detector scans outward from current spot and reports the first kink it encounters.

**Zone classification** uses distance from current spot to the detected boundary — identical to how the breakeven engine classifies zones. This is intuitive, portfolio-size-independent, and consistent.

```
Boundary Detection:
  Walk outward from current spot in step increments
  At each test_spot: compute second_difference = PnL(test-step) - 2×PnL(test) + PnL(test+step)
  If second_difference < -gamma_detect_epsilon: kink detected → gamma_boundary = test_spot
  Report: location of first kink in each direction + severity at that kink location

Zone Classification (at current spot):
  nearest_distance_pct = min(distance_lower, distance_upper)
  SAFE     if nearest_distance_pct > gamma_warning_distance_pct
  WARNING  if nearest_distance_pct > gamma_danger_distance_pct (and ≤ warning)
  DANGER   if nearest_distance_pct ≤ gamma_danger_distance_pct
```

**Severity score** at the detected boundary is stored for diagnostics. It is normalized by `total_lots × LOT_SIZE_BTC` to remove portfolio-size dependence:
```python
normalized_severity = raw_second_diff / (total_lots * LOT_SIZE_BTC)
```
This makes severity scale-invariant: the same strike profile with 10 lots vs 100 lots gives the same normalized severity score, because both carry the same proportional loss acceleration per unit of portfolio risk.

### Decision 3: Caching Strategy

Gamma boundary **locations** depend on position layout (strikes, lots, entry premiums) — same as breakeven cache. The distance from spot to boundary updates every heartbeat (trivial subtraction).

```
On position change (same invalidation events as breakeven engine):
  → Collect positions via be_engine._collect_open_positions(session)
  → Run full outward boundary scan → cache boundary prices + positions_hash

Every heartbeat (cache hit):
  → Reuse cached boundary prices
  → Recompute distances, severity at boundaries, zone (trivial arithmetic)
```

### Decision 4: Observation-Only Default

The gamma detector must not influence trading until the operator has validated its behavior in live sessions. `_gamma_result` in session state is purely informational.

Phase 10 (gated by `gamma_severity_multiplier_enabled: False`) will add a trading multiplier. This parameter defaults to `False` and is NOT in HOT_RELOAD_PARAMS until Phase 10 is validated.

---

## FILES OVERVIEW

### New Files

| File | Purpose |
|------|---------|
| `webui/backend/routes/mmm/mmm_gamma_detector.py` | GammaDetector class — all gamma logic |
| `webui/frontend/src/components/mmm/MMMGammaPanel.js` | React visualization |

### Modified Files

| File | Changes |
|------|---------|
| `webui/backend/routes/mmm/mmm_monitor.py` | Step 5.8: run detector, store result, emit; pair 8× cache invalidation |
| `webui/backend/routes/mmm/mmm_state.py` | Add 6 new params to DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| `webui/backend/routes/mmm/mmm_config.py` | Add PARAM_RULES entries for 6 new params |
| `webui/backend/routes/mmm/mmm_websocket.py` | Add `emit_gamma()`; add `gamma_data` kwarg to `emit_heartbeat` |
| `webui/backend/routes/mmm/mmm_activity.py` | Add 2 ACTIVITY_TYPES + 'safety' category entries |
| `webui/backend/routes/mmm/mmm_api.py` | Add GET `/session/<id>/gamma` endpoint |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | Import + render MMMGammaPanel |

**NOT modified in any phase:**
- `mmm_breakeven_engine.py` — no changes needed (Finding 1)
- `mmm_engine.py` — no trading impact until Phase 10 (future, gated)
- `mmm_close_at_5.py`, `mmm_harvester.py`, `mmm_recycler.py` — gamma cache invalidation handled centrally in `mmm_monitor.py`

---

## GammaResult Data Structure

Every call to `GammaDetector.compute_gamma()` returns this dict. Never raises — returns safe defaults on error.

```python
{
    'enabled': bool,                         # gamma_detector_enabled param
    'spot_price': float,                     # spot used for this computation
    'lower_gamma_boundary': float | None,    # spot price of nearest kink going down (≈ nearest put strike below spot)
    'upper_gamma_boundary': float | None,    # spot price of nearest kink going up (≈ nearest call strike above spot)
    'gamma_severity_lower': float | None,    # normalized severity at lower boundary (negative = concave)
    'gamma_severity_upper': float | None,    # normalized severity at upper boundary
    'gamma_zone': str,                       # 'SAFE' / 'WARNING' / 'DANGER'
    'lower_distance_pct': float | None,      # % distance from spot to lower gamma boundary
    'upper_distance_pct': float | None,      # % distance from spot to upper gamma boundary
    'nearest_distance_pct': float | None,    # min of the two
    'nearest_side': str,                     # 'lower' / 'upper' / 'none'
    'from_cache': bool,                      # True if boundary prices came from cache
    'positions_included': int,               # number of option positions scanned
    'perp_included': bool,                   # whether perp hedge was included in PnL
    'observation_only': bool,                # True until gamma_severity_multiplier_enabled=True
    'computed_at': str,                      # ISO UTC timestamp
}
```

Note: No `'gamma_severity_score'` at current spot — this was removed because it is nearly always zero (Finding 5). Severity is only reported at the detected boundary locations where it is meaningful.

---

## NEW PARAMETERS

To be added to `DEFAULT_PARAMS` in `mmm_state.py` after the existing breakeven block:

```python
# Gamma Detector Engine — portfolio curvature scanning (observation-only until Phase 10)
'gamma_detector_enabled': False,        # master switch
'gamma_step_pct': 0.5,                 # step size as % of spot for second-difference
'gamma_scan_steps': 40,                # steps to scan outward in each direction (20% scan at 0.5% step)
'gamma_warning_distance_pct': 3.0,     # nearest gamma boundary within 3% → WARNING zone
'gamma_danger_distance_pct': 1.5,      # nearest gamma boundary within 1.5% → DANGER zone
'gamma_detect_epsilon': 0.3,           # abs threshold for detecting a kink (USD, small)
'gamma_severity_multiplier_enabled': False,  # Phase 10 gate — requires restart when toggled
```

Hot-reloadable (add to `HOT_RELOAD_PARAMS`):
- `gamma_detector_enabled`
- `gamma_step_pct`
- `gamma_scan_steps`
- `gamma_warning_distance_pct`
- `gamma_danger_distance_pct`
- `gamma_detect_epsilon`

**NOT hot-reloadable:**
- `gamma_severity_multiplier_enabled` — trading impact change requires deliberate restart

To be added to `PARAM_RULES` in `mmm_config.py`:
```python
'gamma_detector_enabled':          {'type': bool,  'min': None, 'max': None,  'hot': True},
'gamma_step_pct':                  {'type': float, 'min': 0.1,  'max': 5.0,   'hot': True},
'gamma_scan_steps':                {'type': int,   'min': 10,   'max': 200,   'hot': True},
'gamma_warning_distance_pct':      {'type': float, 'min': 0.1,  'max': 20.0,  'hot': True},
'gamma_danger_distance_pct':       {'type': float, 'min': 0.1,  'max': 10.0,  'hot': True},
'gamma_detect_epsilon':            {'type': float, 'min': 0.01, 'max': 50.0,  'hot': True},
'gamma_severity_multiplier_enabled': {'type': bool, 'min': None, 'max': None, 'hot': False},
```

---

## PHASE-BY-PHASE IMPLEMENTATION

---

### PHASE 1 — New File: `mmm_gamma_detector.py`

*(Phase numbering restarts at 1 since old Phase 1 is eliminated)*

**File:** `webui/backend/routes/mmm/mmm_gamma_detector.py`

**Class:** `GammaDetector`

**Module singleton:** `get_gamma_detector() → GammaDetector`

#### Public Methods

```
compute_gamma(session, spot_price, be_engine=None) → GammaResult dict
invalidate_cache(session_id) → None
```

`be_engine` is optional — pass from monitor to avoid double singleton lookup.

#### Internal Structure

```python
class GammaDetector:

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def compute_gamma(self, session, spot_price, be_engine=None) → Dict:
        # Entry point: check enabled, collect positions, check cache, run scan or use cache
        ...

    def invalidate_cache(self, session_id) → None:
        with self._lock:
            self._cache.pop(session_id, None)

    def _run_boundary_scan(self, positions, session, spot, step, scan_steps, epsilon, be_engine) → Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        # Returns: (lower_boundary, upper_boundary, severity_at_lower, severity_at_upper)
        # Walk outward from spot, detect first kink in each direction
        ...

    def _compute_second_diff(self, positions, session, test_spot, step, be_engine) → float:
        # Three PnL evaluations at (test_spot - step, test_spot, test_spot + step)
        # Returns: PnL_left - 2×PnL_center + PnL_right
        ...

    def _classify_zone(self, nearest_distance_pct, params) → str:
        # SAFE / WARNING / DANGER based on gamma_warning_distance_pct and gamma_danger_distance_pct
        ...

    def _build_result(self, lower, upper, sev_lower, sev_upper, spot_price, session, positions, from_cache) → Dict:
        ...

    def _empty_result(self, spot_price, enabled=True) → Dict:
        ...
```

#### Boundary Scan Algorithm

```
step = spot × (gamma_step_pct / 100.0)
epsilon = params.get('gamma_detect_epsilon', 0.3)

For direction in (lower, upper):
    boundary = None
    severity_at_boundary = None

    For i in range(gamma_scan_steps):
        test_spot = spot − (i × step)    # going lower
        test_spot = spot + (i × step)    # going upper

        second_diff = _compute_second_diff(positions, session, test_spot, step, be_engine)

        If second_diff < −epsilon:
            boundary = test_spot
            # Normalize severity by total lot exposure to remove portfolio-size dependence
            total_lots = sum(pos['lots'] for pos in positions)
            total_lot_exposure = max(total_lots × LOT_SIZE_BTC, 1e-6)
            severity_at_boundary = second_diff / total_lot_exposure
            break

Return (lower_boundary, upper_boundary, severity_at_lower, severity_at_upper)
```

#### Zone Classification

```python
def _classify_zone(self, nearest_distance_pct, params):
    if nearest_distance_pct is None:
        return 'SAFE'
    warning = params.get('gamma_warning_distance_pct', 3.0)
    danger  = params.get('gamma_danger_distance_pct',  1.5)
    if nearest_distance_pct > warning:
        return 'SAFE'
    elif nearest_distance_pct > danger:
        return 'WARNING'
    else:
        return 'DANGER'
```

#### Cache Design

```python
# On cache miss:
positions = be_engine._collect_open_positions(session)
pos_hash  = be_engine._hash_positions(positions, session)
# Run boundary scan → cache lower, upper, severities, pos_hash

# On cache hit (same pos_hash):
lower = cached['lower_boundary']
upper = cached['upper_boundary']
sev_lower = cached['severity_lower']
sev_upper = cached['severity_upper']
# Then recompute distances and zone from cached boundaries (trivial arithmetic)
```

#### `_compute_second_diff` Implementation

```python
def _compute_second_diff(self, positions, session, test_spot, step, be_engine):
    pnl_left   = be_engine._compute_pnl_at_spot(positions, test_spot - step, session)
    pnl_center = be_engine._compute_pnl_at_spot(positions, test_spot,        session)
    pnl_right  = be_engine._compute_pnl_at_spot(positions, test_spot + step, session)
    return pnl_left - 2.0 * pnl_center + pnl_right
```

#### Error Handling

`compute_gamma()` wraps everything in `try/except Exception`. On any exception: log warning, return `_empty_result(spot_price)`. Never raises.

---

### PHASE 2 — Config Params

**File:** `webui/backend/routes/mmm/mmm_state.py`

Add 7 entries to `DEFAULT_PARAMS` (after the breakeven block):
- See "NEW PARAMETERS" section above

Add 6 entries to `HOT_RELOAD_PARAMS`:
- `gamma_detector_enabled`, `gamma_step_pct`, `gamma_scan_steps`, `gamma_warning_distance_pct`, `gamma_danger_distance_pct`, `gamma_detect_epsilon`

**File:** `webui/backend/routes/mmm/mmm_config.py`

Add 7 entries to `PARAM_RULES` (see "NEW PARAMETERS" section above). This ensures the Settings dialog validates and displays these parameters correctly.

---

### PHASE 3 — Activity Log Types

**File:** `webui/backend/routes/mmm/mmm_activity.py`

Add two entries to `ACTIVITY_TYPES` (after the existing breakeven entries):

```python
'gamma_zone_change':     'Gamma Zone Change',
'gamma_danger_detected': 'Gamma Danger Detected',
```

Add both to the `'safety'` set in `ACTIVITY_CATEGORIES` (NOT 'warning' — there is no 'warning' category):

```python
'safety': {...existing..., 'gamma_zone_change', 'gamma_danger_detected'},
```

---

### PHASE 4 — WebSocket Emission

**File:** `webui/backend/routes/mmm/mmm_websocket.py`

**Change 1:** Update `emit_heartbeat` signature — add `gamma_data: Dict = None` parameter at the end (after `breakeven_data`), and add the corresponding payload entry:

```python
# In emit_heartbeat signature:
def emit_heartbeat(..., breakeven_data: Dict = None, gamma_data: Dict = None):
    ...
    if breakeven_data:
        payload['breakeven'] = breakeven_data
    if gamma_data:
        payload['gamma'] = gamma_data    # ← add this
```

**Change 2:** Add `emit_gamma` function after `emit_breakeven`:

```python
def emit_gamma(session_id: str, gamma_data: Dict):
    """Emit gamma detector result as standalone event."""
    _emit('mmm_gamma', {
        'session_id': session_id,
        **gamma_data,
    })
```

This mirrors the exact structure of `emit_breakeven` (line 470–475).

---

### PHASE 5 — Monitor Integration

**File:** `webui/backend/routes/mmm/mmm_monitor.py`

#### 5a. Imports

Add near the `mmm_breakeven_engine` import:
```python
from .mmm_gamma_detector import get_gamma_detector
```

Add `emit_gamma` to the existing websocket imports line.

#### 5b. Step 5.8 — Insert after Step 5.7 (breakeven block ends at line 1884)

```python
# Step 5.8: Gamma Detector — portfolio curvature scanning
# Runs regardless of _skip_to_pnl so UI data stays fresh.
# Observation-only: stored in session, does NOT influence lot sizing (Phases 1-9).
if params.get('gamma_detector_enabled', False):
    try:
        gd = get_gamma_detector()
        gd_spot = session.get('_regime_spot_price', 0) or 0
        if gd_spot > 0:
            gd_result = gd.compute_gamma(
                session, gd_spot,
                be_engine=get_breakeven_engine()
            )
            session['_gamma_result'] = gd_result

            # Log zone transitions
            prev_gamma_zone = session.get('_gamma_zone_prev', 'SAFE')
            new_gamma_zone = gd_result.get('gamma_zone', 'SAFE')
            if new_gamma_zone != prev_gamma_zone:
                log_activity(
                    'gamma_zone_change',
                    f'Gamma zone: {prev_gamma_zone} → {new_gamma_zone} | '
                    f'nearest={gd_result.get("nearest_distance_pct") or "N/A"}% | '
                    f'lower_boundary={gd_result.get("lower_gamma_boundary")} | '
                    f'upper_boundary={gd_result.get("upper_gamma_boundary")}',
                    sid,
                    'warning' if new_gamma_zone == 'DANGER' else 'info',
                    {'prev_zone': prev_gamma_zone, 'new_zone': new_gamma_zone,
                     'nearest_pct': gd_result.get('nearest_distance_pct'),
                     'lower_boundary': gd_result.get('lower_gamma_boundary'),
                     'upper_boundary': gd_result.get('upper_gamma_boundary')},
                )
                if new_gamma_zone == 'DANGER':
                    log_activity(
                        'gamma_danger_detected',
                        f'Gamma DANGER — losses will accelerate rapidly near '
                        f'lower={gd_result.get("lower_gamma_boundary")} / '
                        f'upper={gd_result.get("upper_gamma_boundary")}',
                        sid, 'warning', gd_result,
                    )
            session['_gamma_zone_prev'] = new_gamma_zone
    except Exception as _gd_err:
        log.warning(f'[{sid}] Gamma detector error (non-fatal): {_gd_err}')
```

#### 5c. Emit in `_emit_heartbeat_data`

In the method that calls `emit_heartbeat(...)` (at line ~7093), add `gamma_data=` alongside the existing `breakeven_data=`:

```python
emit_heartbeat(
    ...,
    breakeven_data=session.get('_breakeven_result'),
    gamma_data=session.get('_gamma_result'),   # ← add this
)
```

After the existing `emit_breakeven` block (lines 7110–7116), add:
```python
gd_result = session.get('_gamma_result')
if gd_result:
    try:
        emit_gamma(self.session_id, gd_result)
    except Exception:
        pass
```

#### 5d. Cache Invalidation (8 locations)

**Every existing `get_breakeven_engine().invalidate_cache(sid)` call must gain a paired gamma call.**

Exact locations (verified by grep):

| Line | Event | Required Addition |
|------|-------|-------------------|
| 3273 | Adjust fill | `get_gamma_detector().invalidate_cache(sid)` |
| 3863 | Strike shift | `get_gamma_detector().invalidate_cache(sid)` |
| 4031 | Close-at-5 | `get_gamma_detector().invalidate_cache(sid)` |
| 4142 | M1 harvest | `get_gamma_detector().invalidate_cache(sid)` |
| 4568 | M2 recycle | `get_gamma_detector().invalidate_cache(sid)` |
| 4758 | Operator inject | `get_gamma_detector().invalidate_cache(sid)` |
| 4967 | Perp fill | `get_gamma_detector().invalidate_cache(sid)` |
| mmm_api.py:3457 | Adopt | `get_gamma_detector().invalidate_cache(session_id)` |

Pattern: every existing `get_breakeven_engine().invalidate_cache(sid)` becomes two lines.

---

### PHASE 6 — API Endpoint

**File:** `webui/backend/routes/mmm/mmm_api.py`

Add after the existing `get_breakeven` endpoint. Use `/session/<session_id>/gamma` (singular — matches all existing MMM endpoints):

```python
@mmm_bp.route('/session/<session_id>/gamma', methods=['GET'])
def get_gamma(session_id: str):
    """
    GET /api/mmm/session/<session_id>/gamma
    Returns latest gamma detector result for the session.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        result = session.get('_gamma_result')
        if result is None:
            return jsonify({
                'success': True,
                'gamma': None,
                'message': 'No gamma data yet — session may not have started heartbeats',
            })

        return jsonify({'success': True, 'gamma': result})

    except Exception as e:
        log.exception(f"Failed to get gamma for session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

Note: Returns 404 (not 400) on session-not-found — consistent with all other MMM endpoints.

---

### PHASE 7 — Frontend: `MMMGammaPanel.js`

**File:** `webui/frontend/src/components/mmm/MMMGammaPanel.js`

Mirrors `MMMBreakevenPanel.js` structure. Collapsible panel.

**Props:**
```jsx
MMMGammaPanel({ gamma })
// gamma: GammaResult dict from session._gamma_result
// Returns null if !gamma || !gamma.enabled
```

**Always-visible header:**
- Gamma zone badge (SAFE=green, WARNING=orange, DANGER=red)
- "Observation Only" badge (gray chip, always shown — Phase 10 removes it)
- Nearest boundary distance (`X.X%`)

**Expanded details:**
- Lower gamma boundary price (`$XX,XXX`)
- Upper gamma boundary price
- Distance to lower boundary (`X.X% ($XXX)`)
- Distance to upper boundary
- Nearest side indicator
- Normalized severity at lower boundary (with tooltip: "Negative = losses accelerate rapidly near this price")
- Normalized severity at upper boundary
- Positions scanned count
- Explanation: "Gamma boundaries show where option strikes cause loss acceleration"

**Zone colors:** Three levels only (no CRITICAL — gamma has SAFE/WARNING/DANGER).

**Data source:** `gamma` key from `mmm_heartbeat` WebSocket event, or standalone `mmm_gamma` event. Subscribe the same way `MMMBreakevenPanel` subscribes to breakeven data.

---

### PHASE 8 — Dashboard Integration

**File:** `webui/frontend/src/components/mmm/MMMDashboard.js`

1. Import `MMMGammaPanel` at the top (next to existing `MMMBreakevenPanel` import)
2. Extract `gamma` from the heartbeat/session state (wherever `breakeven` is extracted)
3. Render `<MMMGammaPanel gamma={gamma} />` directly below `<MMMBreakevenPanel>`

The gamma key is embedded in the heartbeat payload at `heartbeat.gamma` — same path as `heartbeat.breakeven`. Replicate exactly how breakeven state is populated.

---

### PHASE 9 — Trading Integration (Future, Permanently Gated)

**DO NOT implement until:**
- At least 3 complete live sessions ran with gamma in observation mode
- Gamma zone classifications manually reviewed against actual market behavior
- `gamma_severity_multiplier_enabled` explicitly set to `True` by operator

**What Phase 9 adds:**

**File:** `webui/backend/routes/mmm/mmm_engine.py`

In `calculate_lots_to_sell()`, after the existing Breakeven Multiplier block (line ~384) and before the IMP-2 Trend Boost block:

```python
# ── Gamma Severity Multiplier (Phase 9 — requires gamma_severity_multiplier_enabled=True) ──
# NOTE: gamma_mult already exists above (T3-2 gamma-aware multiplier). This is DIFFERENT.
# Use gamma_severity_mult as the variable name to avoid shadowing gamma_mult.
gamma_severity_mult = 1.0
gamma_result = session.get('_gamma_result', {})
if (params.get('gamma_severity_multiplier_enabled', False) and
        gamma_result.get('gamma_zone') == 'DANGER'):
    gamma_severity_mult = params.get('gamma_severity_max_multiplier', 1.5)
    pre_gsev = lots_to_sell
    lots_to_sell = max(math.ceil(lots_to_sell * gamma_severity_mult), 1)
    gsev_msg = (
        f'Gamma Severity {gamma_severity_mult:.1f}x (DANGER zone, '
        f'nearest={gamma_result.get("nearest_distance_pct", 0):.1f}%): '
        f'{pre_gsev} → {lots_to_sell} lots'
    )
    constraint_msg = f'{constraint_msg}; {gsev_msg}' if constraint_msg else gsev_msg
# ── END Gamma Severity Multiplier ─────────────────────────────────────────────
```

**Critical: Update combined ceiling (line ~451):**

```python
# Before:
combined = gamma_mult * breakeven_mult * (boost_mult if session.get('_trend_boost_active') else 1.0)

# After (Phase 9):
combined = gamma_mult * gamma_severity_mult * breakeven_mult * (boost_mult if session.get('_trend_boost_active') else 1.0)
```

Also update the ceiling trigger condition to include `gamma_severity_mult > 1.0`.

Also add to `DEFAULT_PARAMS`:
```python
'gamma_severity_max_multiplier': 1.5,  # max multiplier in Phase 9 (DANGER zone only)
```
This goes in HOT_RELOAD_PARAMS.

---

## INTEGRATION MAP

```
mmm_breakeven_engine.py
  └── No changes — gamma detector accesses _private methods directly (Finding 1)

mmm_gamma_detector.py              ← NEW FILE
  └── uses get_breakeven_engine()._collect_open_positions()
  └── uses get_breakeven_engine()._compute_pnl_at_spot()
  └── uses get_breakeven_engine()._hash_positions()
  └── get_gamma_detector()         ← singleton

mmm_state.py
  └── DEFAULT_PARAMS               ← 7 new params
  └── HOT_RELOAD_PARAMS            ← 6 new (excluding gamma_severity_multiplier_enabled)

mmm_config.py
  └── PARAM_RULES                  ← 7 new entries

mmm_activity.py
  └── ACTIVITY_TYPES               ← 2 new types
  └── ACTIVITY_CATEGORIES['safety'] ← 2 new entries (NOT 'warning' — that category doesn't exist)

mmm_websocket.py
  └── emit_gamma()                 ← new function
  └── emit_heartbeat()             ← add gamma_data kwarg + payload entry

mmm_monitor.py
  └── Step 5.8                     ← new step after existing Step 5.7 (~line 1884)
  └── 8 × invalidate_cache pairs   ← paired with breakeven invalidation calls
  └── _emit_heartbeat_data()       ← gamma_data= kwarg + emit_gamma() call

mmm_api.py
  └── GET /session/<id>/gamma      ← new endpoint (singular 'session', 404 on not-found)

MMMGammaPanel.js                   ← NEW FILE
MMMDashboard.js                    ← import + render MMMGammaPanel
```

---

## SEQUENCING RULES

1. **Phase 1 (GammaDetector class) is standalone** — write and test it in isolation before wiring into the monitor. It requires no other phase.
2. **Phases 2 and 3 are independent** (config + activity) — do in parallel with Phase 1.
3. **Phase 4 (WebSocket) must complete before Phase 5** — monitor imports `emit_gamma`.
4. **Phase 5 (Monitor integration) is the highest-risk phase** — it touches `mmm_monitor.py` which runs the live heartbeat. Confirm no live session in critical position before restarting.
5. **Phases 6–8 (API + frontend) are independent of each other** — do in any order after Phase 5.
6. **Phase 9 is permanently gated** — do not implement until operator approves after live observation.

---

## SAFETY RULES

1. Gamma detector must never call `execute_adjustment()`, `close_position()`, or any exchange API.
2. All exceptions in `compute_gamma()` are caught internally — returns safe empty dict on error.
3. In the monitor, the Step 5.8 block is wrapped in its own `try/except` — a gamma failure never stops the heartbeat.
4. Session state writes limited to `_gamma_result` and `_gamma_zone_prev`. Nothing else.
5. `_gamma_result` is read by the engine only in Phase 9 (when `gamma_severity_multiplier_enabled=True`). During Phases 1–8, the engine reads only `_breakeven_multiplier`.
6. Backend restart required after Phase 5. Confirm with operator first.

---

## SEALED TESTS PLAN

Check sealed test count before any phase:
```bash
python3 -m pytest webui/ bot/ -m sealed -v 2>&1 | tail -5
```

Write and seal these tests **before Phase 5** (monitor integration):

| Test | What to verify |
|------|---------------|
| `test_gamma_empty_session` | No positions → SAFE zone, no boundaries |
| `test_gamma_boundary_detection` | Position at known strike → boundary found near that strike |
| `test_gamma_zone_safe` | Spot far from all strikes → SAFE |
| `test_gamma_zone_warning` | Spot within gamma_warning_distance_pct of nearest strike → WARNING |
| `test_gamma_zone_danger` | Spot within gamma_danger_distance_pct of nearest strike → DANGER |
| `test_gamma_cache_hit` | Identical positions hash → `from_cache=True` |
| `test_gamma_cache_invalidation` | `invalidate_cache()` → next call runs full scan |
| `test_gamma_error_resilience` | Exception in _compute_second_diff → returns empty result |
| `test_gamma_observation_only` | `gamma_severity_multiplier_enabled=False` → `observation_only=True` |
| `test_gamma_second_diff_zero_flat` | Flat region (spot far from strike) → second_diff ≈ 0 |
| `test_gamma_second_diff_at_kink` | Test spot at a short call strike → second_diff < -epsilon |

---

## OPEN QUESTIONS FOR OPERATOR

1. **Distance thresholds:** Defaults `gamma_warning_distance_pct=3.0` and `gamma_danger_distance_pct=1.5` mean WARNING triggers when nearest option strike is within 3% of spot, DANGER within 1.5%. At $90k BTC: WARNING at $2,700 from nearest strike, DANGER at $1,350. Are these the right sensitivities?

2. **Dashboard placement:** Gamma panel above or below breakeven panel? Conceptually gamma is a leading indicator (fires before breakeven), so above may be more natural.

3. **Default enabled state:** `gamma_detector_enabled: False`. Should existing sessions auto-enable on the next restart via DEFAULT_PARAMS backfill, or should the operator manually enable per-session?

---

## CONTEXT: WHAT IS ALREADY DONE

| Module | Status |
|--------|--------|
| BreakevenEngine — core PnL model | Complete in `mmm_breakeven_engine.py` |
| Breakeven cache + all invalidation | Complete |
| `_breakeven_multiplier` in lot sizing | Complete in `mmm_engine.py` lines 371–384 |
| `emit_breakeven()` WebSocket | Complete in `mmm_websocket.py` line 470 |
| `MMMBreakevenPanel.js` | Complete |
| Combined multiplier ceiling | Complete in `mmm_engine.py` lines 446–466 |

The gamma detector builds on top of all of the above. It does not replace any of it.
