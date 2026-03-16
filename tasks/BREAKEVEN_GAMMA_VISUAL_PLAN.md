# Breakeven Engine + Gamma Detector — WebUI Visualization Upgrade Plan

**Status:** ✅ COMPLETED — 2026-03-15
**Priority:** P1 (critical gap: gamma settings inaccessible from UI)
**Estimated total effort:** ~7.75 hours
**Files touched:** 9 (4 modify, 5 new)
**Phases:** 9 total (1, 2, 3, 4, 5, 6, 6.5, 7, 8)
**New dependencies:** None — all uses Recharts 2.9.0 (already installed) + MUI + SVG

> **Implementation complete.** All 9 phases delivered in a single session. 436 sealed tests pass (0 regressions). Frontend build successful, all bundle sizes within budget. One backend restart required to activate the `/pnl-curve` endpoint (deferred — session `mmm16mar26-1` was RUNNING at time of implementation).

---

## Section 1: Executive Summary

The MMM algorithm's Breakeven Engine and Gamma Detector are fully implemented in the backend and wired into the monitor heartbeat cycle. However, the WebUI visualization is incomplete in several critical ways: gamma detector parameters cannot be configured from the settings dialog, there is no P&L landscape chart showing where the portfolio goes underwater, and the two panels have no unified view showing their concentric-ring relationship.

This plan delivers 8 implementation phases that transform the existing minimal panels into a production-quality risk visualization suite. The crown jewel is a live P&L curve chart (`MMMRiskProfileChart.js`) that answers the operator question "how bad could it get if BTC moves X%?" in one glance. Secondary deliverables include a settings dialog fix (30 min, zero risk), a combined zone widget, and a distance history timeline.

All backend computation already exists. The plan does not re-implement any backend logic — only adds one API endpoint (Phase 2) and builds the frontend visualization layer on top of existing data.

---

## Section 2: Current State Audit

### Backend — Fully Implemented

| Component | File | Status |
|---|---|---|
| BreakevenEngine class + all methods | `mmm_breakeven_engine.py` | DONE |
| GammaDetector class + all methods | `mmm_gamma_detector.py` | DONE |
| Monitor Step 5.7 (breakeven wired) | `mmm_monitor.py` | DONE |
| Monitor Step 5.8 (gamma wired) | `mmm_monitor.py` | DONE |
| Cache invalidation — 8 pairs | `mmm_monitor.py:3318/19, 3909/10, 4078/79, 4185/86, 4612/13, 4803/04, 4938/39` + `mmm_api.py:3458/59` | DONE |
| `emit_heartbeat` breakeven_data + gamma_data kwargs | `mmm_websocket.py` | DONE |
| `emit_breakeven()` + `emit_gamma()` functions | `mmm_websocket.py` | DONE |
| DEFAULT_PARAMS — 7 gamma params + 8 breakeven params | `mmm_state.py` | DONE |
| HOT_RELOAD_PARAMS configured | `mmm_state.py` | DONE |
| PARAM_RULES — 7 gamma entries | `mmm_config.py` | DONE |
| PARAM_RULES — 8 breakeven entries | `mmm_config.py` | DONE |
| ACTIVITY_TYPES — gamma + breakeven types | `mmm_activity.py` | DONE |
| `/session/<id>/breakeven` endpoint | `mmm_api.py` | DONE |
| `/session/<id>/gamma` endpoint | `mmm_api.py` | DONE |
| `_compute_pnl_at_spot()` method | `mmm_breakeven_engine.py` | DONE |

### Backend — Gap

| Component | File | Status |
|---|---|---|
| `/session/<id>/pnl-curve` endpoint | `mmm_api.py` | **MISSING — Phase 2** |

> Note: `gamma_scan_steps` should be verified at `mmm_config.py` line ~201. It is listed in DEFAULT_PARAMS (`mmm_state.py`) but confirm PARAM_RULES entry exists before Phase 1.

### Frontend — Partially Implemented

| Component | File | Status |
|---|---|---|
| MMMBreakevenPanel — collapsible panel, horizontal band bar | `MMMBreakevenPanel.js` | EXISTS but minimal |
| MMMGammaPanel — collapsible panel, distance text | `MMMGammaPanel.js` | EXISTS but minimal |
| Both panels imported + rendered | `MMMDashboard.js:2130-2141` | DONE |
| `breakevenEngine` param group in settings | `MMMSettingsDialog.js` | DONE |

### Frontend — Gaps

| Component | File | Status |
|---|---|---|
| `gammaDetector` param group in settings | `MMMSettingsDialog.js` | **MISSING — Phase 1 (P0)** |
| P&L landscape chart | `MMMRiskProfileChart.js` | **MISSING — Phase 3** |
| Scaled band bar with gamma markers | `MMMBreakevenPanel.js` | **MISSING — Phase 4** |
| Proximity meter in gamma panel | `MMMGammaPanel.js` | **MISSING — Phase 5** |
| Combined zone widget (concentric rings) | `MMMCombinedZoneWidget.js` | **MISSING — Phase 6** |
| Distance history timeline | `MMMDistanceHistoryChart.js` | **MISSING — Phase 7** |
| Risk tab in dashboard | `MMMDashboard.js` | **MISSING — Phase 8** |

---

## Section 3: ATM Shield Integration Context

### Three-Layer Defense Model

The MMM algorithm implements three defensive layers that fire in sequence as BTC moves toward a strike:

```
Layer 1 — Gamma Detector (earliest warning)
  Fires when: spot within gamma_warning_distance_pct (default 3%) of nearest strike
  Action: observation-only signal, qualitative zone change
  Visual: amber on gamma panel

Layer 2 — Breakeven Engine (lot multiplier escalation)
  Fires when: spot within breakeven_warning_pct (default 2%) of breakeven line
  Action: breakeven_mult increases (1.0x → 3.0x), more lots sold on next adjustment
  Visual: amber → red on breakeven panel, multiplier chip changes

Layer 3 — ATM Shield (position retreat)
  Fires when: spot reaches ~0.5% from strike (shield_otm_threshold)
  Action: close threatened leg, reopen at new OTM strike
  Visual: shield event marker on timeline chart
```

### Shield v5 Interaction Matrix

| Tier | Shield Active? | Breakeven/Gamma Effect |
|---|---|---|
| T1/T2 | Yes — full shield | Normal: both BE and gamma react |
| T3/T4 | Partial — BLOCK_CE or BLOCK_PE only (not BLOCK_ALL) | Shield fires on one side only |
| BLOCK_ALL regime | Shield blocked | BE/gamma still compute but no leg can be sold |

### Visual Cues After Shield Fires

When a shield fires (position closed + retreat to new OTM strike), the following should be immediately visible on the charts:

1. **P&L Curve (Phase 3)**: The curve reshapes — the loss slope on the retreated side flattens because the new strike has more extrinsic value. The breakeven line moves farther from spot (band widens).

2. **Distance History (Phase 7)**: A vertical event marker labeled "Shield↑" or "Shield↓" appears at the exact timestamp. After the marker, the distance line jumps upward (safer).

3. **Combined Zone Widget (Phase 6)**: Gamma boundary marker shifts to new strike location, expanding the safe green zone.

4. **Breakeven Band (Phase 4)**: Lower or upper BE marker moves outward — the colored warning bands retract from spot.

The key insight for operators: shield fires appear as a **visible improvement** on every chart simultaneously. This validates the shield is working.

---

## Section 4: MMM Algo Benefit Analysis

### 4.1 Early Warning Pipeline — Timing Analysis

At typical BTC volatility (30% annualized IV), BTC moves approximately $300–$600/min during active sessions. Using $450/min as a baseline:

| Event | Distance from Strike | Time Before Strike | Distance from Breakeven |
|---|---|---|---|
| Gamma WARNING fires | 3.0% (~$2,700 on $90k BTC) | ~6 min | BE still safe (~5%) |
| Gamma DANGER fires | 1.5% (~$1,350) | ~3 min | BE still safe (~3.5%) |
| Breakeven WARNING fires | 2.0% from BE (~$1,800) | ~4 min | — |
| Breakeven DANGER fires | 1.0% from BE (~$900) | ~2 min | — |
| Breakeven CRITICAL fires | 0.5% from BE (~$450) | ~1 min | — |
| ATM Shield fires | ~0.5% from strike (~$450) | ~1 min | — |

**Key finding**: Gamma DANGER (1.5% from strike) fires approximately 90 seconds before Breakeven WARNING (2% from breakeven), assuming a typical strangle where strikes are ~3-4% OTM. This is the advance warning buffer that allows the algorithm to pre-position.

**Without gamma**: The algorithm's first quantitative escalation signal is Breakeven WARNING at T-4min.
**With gamma**: The algorithm receives a qualitative zone signal at T-6min and DANGER at T-3min, giving ~2 extra minutes of context before lots are committed.

### 4.2 Multiplier Cascade Mechanics

The combined lot multiplier is computed as:

```
final_lots = ceil(base_lots × gamma_mult × breakeven_mult × trend_mult)
             capped at: base_lots × max_combined_lot_multiplier (default 3.0x)
```

Example scenario at Breakeven DANGER zone (1.1% from BE):

| Factor | Value | Source |
|---|---|---|
| base_lots | 5 | session config |
| gamma_mult | 1.3x | T3-T2 aggressor premium logic |
| breakeven_mult | 1.6x | DANGER zone ramp (1.0x at warning → 3.0x at critical) |
| trend_boost | 1.0x | neutral trend |
| Raw result | ceil(5 × 1.3 × 1.6 × 1.0) = ceil(10.4) = 11 lots | — |
| Combined ceiling | 5 × 3.0 = 15 lots max | max_combined_lot_multiplier |
| Final | **11 lots** (ceiling not hit) | — |

At CRITICAL zone (0.4% from BE):

| Factor | Value |
|---|---|
| breakeven_mult | 3.0x (maximum) |
| Raw result | ceil(5 × 1.3 × 3.0) = ceil(19.5) = 20 lots |
| Combined ceiling | 5 × 3.0 = 15 lots |
| Final | **15 lots** (ceiling applied) |

The ceiling prevents runaway lot escalation in extreme scenarios while still ensuring aggressive defense at critical distances.

### 4.3 Phase 9: gamma_severity_multiplier_enabled

Currently `gamma_severity_multiplier_enabled` defaults to `false` and is NOT hot-reloadable (requires restart). This is intentional — it gates Phase 9 where gamma severity scores directly modulate lot multipliers.

When enabled (future):
- `gamma_severity_lower` / `gamma_severity_upper` (negative float, more negative = worse) provide per-side severity
- Severity multiplier will give asymmetric lot boosting: if lower gamma is worse than upper, sell more PE puts
- This directional intelligence complements the existing trend_boost

**Current value**: Even with `gamma_severity_multiplier_enabled=false`, the severity scores are computed and visible in the UI. Operators can use them for manual judgment before Phase 9 automation is trusted.

### 4.4 P&L Curve Business Value

The P&L curve answers the most critical operator question — "if BTC moves X%, how much do I lose?" — without requiring mental interpolation from premium levels.

Without the chart: operator must mentally combine multiple positions' deltas, gammas, and time decay into a scenario estimate. Error rate is high. Response time is slow.

With the chart: the visual slope of the curve immediately shows where loss acceleration begins (gamma kinks), where the portfolio crosses into loss (breakeven lines), and how much total loss is possible at any given spot.

The chart also provides **post-hoc validation**: after a session closes, the operator can compare the actual P&L path against the theoretical curve to assess whether the breakeven estimates were accurate.

### 4.5 Combined Ceiling Protection

The `max_combined_lot_multiplier` (default 3.0x) prevents cascading lot escalation in compound-risk scenarios:

- Gamma DANGER fires → gamma_mult = 1.2x
- Breakeven DANGER fires simultaneously → breakeven_mult = 1.6x
- Trend strong → trend_boost = 1.5x
- Raw: 1.2 × 1.6 × 1.5 = 2.88x — under ceiling
- If all three hit maximum simultaneously: 1.3 × 3.0 × 2.0 = 7.8x — ceiling cuts to 3.0x

The ceiling is the capital protection backstop that prevents the algorithm from selling more contracts than the account can safely hold.

---

## Section 5: Gap Analysis (Prioritized)

| # | Gap | Impact | Effort | Phase |
|---|---|---|---|---|
| 1 | Gamma detector settings not configurable from UI | **Critical** — users cannot tune gamma thresholds | 30 min | Phase 1 |
| 2 | No P&L curve API endpoint | **High** — blocks the most valuable visualization | 45 min | Phase 2 |
| 3 | No P&L landscape chart | **High** — no visual answer to "how bad if X% move?" | 90 min | Phase 3 |
| 4 | Breakeven band bar not proportionally scaled | **High** — misleading: 10% band looks same as 1% band | 60 min | Phase 4 |
| 5 | No gamma markers on breakeven bar | **High** — concentric ring relationship is invisible | (part of Phase 4) | Phase 4 |
| 6 | No combined zone widget | **Medium** — must switch between two panels to see risk | 60 min | Phase 6 |
| 7 | No gamma proximity meter | **Medium** — severity scores not visualized | 45 min | Phase 5 |
| 8 | No distance history timeline | **Medium** — cannot see how risk evolved during session | 75 min | Phase 7 |
| 9 | No Risk tab in dashboard | **Lower** — existing tabs are overloaded | 30 min | Phase 8 |

---

## Section 6: Implementation Phases

### Phase 1: Settings Dialog — Gamma Detector Group

**Priority:** P0 Critical
**Effort:** 30 min
**File:** `webui/frontend/src/components/mmm/MMMSettingsDialog.js`
**Risk:** Zero — pure UI addition, no backend change

**Problem:** `gammaDetector` param group is completely absent from `MMMSettingsDialog.js`. The 7 gamma parameters exist in backend state and PARAM_RULES but there is no way to change them from the UI. `gamma_detector_enabled` cannot even be toggled without a raw API call.

**Pre-check:** Before editing, verify `gamma_scan_steps` is present in `mmm_config.py` PARAM_RULES (expected ~line 201). If missing, add it there first.

**Implementation:**

Locate the `PARAM_GROUPS` object in `MMMSettingsDialog.js` (where `breakevenEngine` group is defined). Add a `gammaDetector` entry immediately after `breakevenEngine`:

```javascript
gammaDetector: {
  title: 'Gamma Detector',
  color: '#ff6f00',  // deep amber — distinct from breakeven blue (#1565c0)
  blurb: 'Portfolio curvature scanning — detects the option strikes where P&L loss rate begins to accelerate. Fires ~90 seconds before Breakeven WARNING at typical BTC velocity. Currently observation-only; Phase 9 will use severity scores for directional lot weighting.',
  subgroups: [
    {
      header: 'Enable',
      params: ['gamma_detector_enabled'],
    },
    {
      header: 'Zone Thresholds (% distance from spot to nearest gamma boundary)',
      params: ['gamma_warning_distance_pct', 'gamma_danger_distance_pct'],
    },
    {
      header: 'Scan Parameters',
      params: ['gamma_step_pct', 'gamma_scan_steps', 'gamma_detect_epsilon'],
    },
    {
      header: 'Phase 9 Gate',
      params: ['gamma_severity_multiplier_enabled'],
    },
  ],
},
```

**Tooltip strings to add** (add to the tooltips/descriptions map):

| Param | Tooltip Text |
|---|---|
| `gamma_detector_enabled` | Master switch for gamma boundary detection. When disabled, no gamma data is computed or emitted. Start with this OFF for first 3 sessions, then enable observation mode. |
| `gamma_warning_distance_pct` | Spot must be within this % of the nearest option strike to enter gamma WARNING zone. Default 3.0%. At $90k BTC, this is $2,700 from the nearest short strike. Fires ~6 min before ATM shield at typical velocity. |
| `gamma_danger_distance_pct` | Spot must be within this % of the nearest strike for gamma DANGER zone. Default 1.5%. Fires ~3 min before ATM shield. Breakeven is still likely SAFE at this point — this is the advance warning window. |
| `gamma_step_pct` | Step size for the second-difference (curvature) scan. Default 0.5%. Smaller = finer detection of gamma kinks, but more CPU per heartbeat. Do not set below 0.2%. |
| `gamma_scan_steps` | Number of steps to scan outward from spot in each direction. Default 40. At gamma_step_pct=0.5%, this scans 20% outward. Increase only if strikes are unusually far OTM. |
| `gamma_detect_epsilon` | Minimum second-difference magnitude to count as a gamma kink. Default 0.3. Lower = more sensitive (may flag noise). Higher = only strong curvature changes detected. |
| `gamma_severity_multiplier_enabled` | Phase 9 gate — when enabled, gamma severity scores directly modulate lot multipliers directionally (more PE lots when lower gamma is worse). NOT hot-reloadable. Requires backend restart. Do not enable until 10+ sessions of observation data collected. |

**Warning chip for `gamma_severity_multiplier_enabled`:** This param requires a restart. Render a warning chip alongside it — use the same pattern already used for non-hot breakeven params (look for existing restart-required UI pattern in the breakevenEngine subgroup). The chip should say "Requires Backend Restart" in red/amber.

---

### Phase 2: Backend P&L Curve API Endpoint

**Priority:** P1 High
**Effort:** 45 min
**File:** `webui/backend/routes/mmm/mmm_api.py`
**Risk:** Low — additive endpoint, no change to existing logic

**New endpoint:** `GET /api/mmm/session/<session_id>/pnl-curve`

**Query parameters:**

| Param | Type | Default | Max | Description |
|---|---|---|---|---|
| `n_points` | int | 100 | 200 | Number of price sample points in the curve |
| `range_pct` | float | 15.0 | 50.0 | Scan range as % of current spot (centered on spot) |

**Implementation:**

```python
@mmm_bp.route('/session/<session_id>/pnl-curve', methods=['GET'])
def get_pnl_curve(session_id: str):
    session = _get_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    n_points = min(int(request.args.get('n_points', 100)), 200)
    range_pct = min(float(request.args.get('range_pct', 15.0)), 50.0)

    engine = get_breakeven_engine()
    positions = engine._collect_open_positions(session)
    if not positions:
        return jsonify({
            'success': True,
            'spot': session.get('spot_price', 0),
            'points': [],
            'message': 'No positions to compute curve',
            'breakeven': None,
            'gamma': None,
            'positions_count': 0,
            'computed_at': datetime.utcnow().isoformat(),
        })

    spot = session.get('spot_price', 0)
    if not spot:
        return jsonify({'success': False, 'error': 'No spot price available'}), 422

    low = spot * (1 - range_pct / 100)
    high = spot * (1 + range_pct / 100)
    step = (high - low) / (n_points - 1)

    # Fetch current breakeven and gamma results (from cache or compute)
    be_result = engine.compute(session)  # returns BreakevenResult dict
    gamma_result = get_gamma_detector().compute(session)  # returns GammaResult dict

    # Build zone lookup from breakeven and gamma boundaries
    lower_be = be_result.get('lower_breakeven', 0)
    upper_be = be_result.get('upper_breakeven', float('inf'))
    lower_gamma = gamma_result.get('lower_gamma_boundary', 0)
    upper_gamma = gamma_result.get('upper_gamma_boundary', float('inf'))

    critical_pct = session.get('breakeven_critical_pct', 0.5) / 100
    danger_pct = session.get('breakeven_danger_pct', 1.0) / 100
    warning_pct = session.get('breakeven_warning_pct', 2.0) / 100

    def classify_zone(test_spot: float) -> str:
        if lower_gamma and test_spot < lower_gamma:
            return 'lower_gamma'
        if upper_gamma and test_spot > upper_gamma:
            return 'upper_gamma'
        if lower_be and test_spot < lower_be:
            # below breakeven — classify how far
            dist_pct = (lower_be - test_spot) / lower_be
            if dist_pct >= warning_pct: return 'below_lower_be'
            if dist_pct >= danger_pct: return 'lower_be_warning'
            if dist_pct >= critical_pct: return 'lower_be_danger'
            return 'lower_be_critical'
        if upper_be and test_spot > upper_be:
            dist_pct = (test_spot - upper_be) / upper_be
            if dist_pct >= warning_pct: return 'above_upper_be'
            if dist_pct >= danger_pct: return 'upper_be_warning'
            if dist_pct >= critical_pct: return 'upper_be_danger'
            return 'upper_be_critical'
        # Inside breakeven — classify proximity
        lower_dist = (test_spot - lower_be) / test_spot if lower_be else 1.0
        upper_dist = (upper_be - test_spot) / test_spot if upper_be else 1.0
        nearest_dist = min(lower_dist, upper_dist)
        if nearest_dist < critical_pct: return 'lower_be_critical' if lower_dist < upper_dist else 'upper_be_critical'
        if nearest_dist < danger_pct: return 'lower_be_danger' if lower_dist < upper_dist else 'upper_be_danger'
        if nearest_dist < warning_pct: return 'lower_be_warning' if lower_dist < upper_dist else 'upper_be_warning'
        return 'safe'

    points = []
    for i in range(n_points):
        test_spot = low + i * step
        pnl = engine._compute_pnl_at_spot(positions, test_spot, session)
        points.append({
            'spot': round(test_spot, 2),
            'pnl': round(pnl, 4),
            'zone': classify_zone(test_spot),
        })

    return jsonify({
        'success': True,
        'spot': spot,
        'points': points,
        'breakeven': be_result,
        'gamma': gamma_result,
        'positions_count': len(positions),
        'computed_at': datetime.utcnow().isoformat(),
    })
```

**Zone field values** (all valid values for the `zone` field in each point):

- `"below_lower_be"` — well below lower breakeven (spot < lower_be by > warning_pct)
- `"lower_be_warning"` — within warning zone of lower BE
- `"lower_be_danger"` — within danger zone of lower BE
- `"lower_be_critical"` — within critical zone of lower BE
- `"safe"` — inside breakeven band, not near any threshold
- `"upper_be_warning"` — within warning zone of upper BE
- `"upper_be_danger"` — within danger zone of upper BE
- `"upper_be_critical"` — within critical zone of upper BE
- `"above_upper_be"` — well above upper breakeven
- `"lower_gamma"` — below lower gamma boundary
- `"upper_gamma"` — above upper gamma boundary

**Error handling:**
- Session not found → 404 with `{'success': false, 'error': 'Session not found'}`
- No spot price → 422 with error message
- No positions → 200 with empty points array and `message` field
- `_compute_pnl_at_spot` exception → log error, return 500

**Performance note:** 100 points × typical position count (~6-12) = ~600-1200 `_compute_pnl_at_spot` calls per request. This is on-demand only (not streaming). Acceptable for a UI button click. Do not add to heartbeat.

---

### Phase 3: MMMRiskProfileChart.js — P&L Landscape

**Priority:** P1 High
**Effort:** 90 min
**File:** `webui/frontend/src/components/mmm/MMMRiskProfileChart.js` (NEW)
**Depends on:** Phase 2 (pnl-curve endpoint)

**Purpose:** The crown jewel visualization. Shows the full P&L landscape of the portfolio across a range of BTC prices, with breakeven and gamma boundaries marked.

**Props:**

```jsx
MMMRiskProfileChart({
  sessionId,       // string — used to fetch curve data
  breakeven,       // BreakevenResult dict from heartbeat
  gamma,           // GammaResult dict from heartbeat
  session,         // session object (for param access)
})
```

**Chart library:** Recharts (already used throughout the dashboard — do not add new dependencies).

**Chart spec:**

- Height: 400px
- X-axis: BTC spot price (format: `$XX,XXX`)
- Y-axis: Portfolio P&L in USD (format: `$X.XX` with sign)
- Chart type: `ComposedChart` with `Area` and `ReferenceLine`/`ReferenceArea` overlays

**Area layers (stacked):**
```
Area 1: pnl > 0 → fill='#4caf50' opacity=0.3 (green profit zone)
Area 2: pnl < 0 → fill='#f44336' opacity=0.3 (red loss zone)
```
Use two separate `Area` components with `baseValue={0}` — one for positive values only, one for negative values only. The Recharts `<Area>` component supports this via a `type="monotone"` with the data filtered or using two separate datasets.

Alternative: single dataset with two colored areas using Recharts `defs` and `linearGradient` — evaluate during implementation.

**Reference lines (vertical):**

| Element | Color | Style | Label |
|---|---|---|---|
| Lower breakeven | `#f44336` | solid | `BE↓` at top |
| Upper breakeven | `#f44336` | solid | `BE↑` at top |
| Lower gamma boundary | `#ff9800` | dashed | `γ↓` at top |
| Upper gamma boundary | `#ff9800` | dashed | `γ↑` at top |
| Current spot | `#ffffff` | solid, strokeWidth=2 | `●SPOT` animated |

**Reference areas (zone shading):**

| Zone | X Range | Fill | Opacity |
|---|---|---|---|
| Gamma safe zone | `[lower_gamma, upper_gamma]` | `#ff9800` (amber) | 0.04 |
| Lower danger zone | `[lower_be, lower_gamma]` | `#ff5722` (deep orange) | 0.06 |
| Upper danger zone | `[upper_gamma, upper_be]` | `#ff5722` (deep orange) | 0.06 |

**Zero reference line:** Horizontal `ReferenceLine y={0}` with `stroke='#ffffff'` `strokeDasharray='4 4'` `opacity=0.5`.

**Custom tooltip:**
```jsx
const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const { spot, pnl, zone } = payload[0].payload;
  return (
    <Box sx={{ bgcolor: '#1e1e2e', p: 1, border: '1px solid #444', borderRadius: 1 }}>
      <Typography variant="caption">Spot: ${spot.toLocaleString()}</Typography>
      <Typography variant="caption" sx={{ color: pnl >= 0 ? '#4caf50' : '#f44336', display: 'block' }}>
        P&L: {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
      </Typography>
    </Box>
  );
};
```

**Data loading logic:**

```javascript
const [curveData, setCurveData] = useState(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);

const fetchCurve = useCallback(async () => {
  if (!sessionId) return;
  setLoading(true);
  try {
    const res = await fetch(`/api/mmm/session/${sessionId}/pnl-curve?n_points=100&range_pct=15`);
    const data = await res.json();
    if (data.success) setCurveData(data);
    else setError(data.error || 'Failed to load curve');
  } catch (e) {
    setError(e.message);
  } finally {
    setLoading(false);
  }
}, [sessionId]);
```

**Refresh triggers:** Listen to socket events `mmm_adjustment`, `mmm_shift`, `mmm_breakeven` (these indicate positions changed). On each event, call `fetchCurve()`. Also fetch on mount and when `sessionId` changes.

Do NOT refresh on every heartbeat — the curve is expensive and heartbeat is every 2s. Refresh only on structural position changes.

**Loading state:** MUI `Skeleton` component at 400px height with chart-like shimmer.

**Error state:** Centered text "Unable to load P&L curve — {error}" with a Retry button.

**No positions state:** Centered text "No open positions — P&L curve unavailable" with a muted chart icon.

**Header:**
```jsx
<Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
  <Typography variant="subtitle2">P&L Risk Profile</Typography>
  <Chip size="small" label={breakeven?.zone || 'UNKNOWN'} color={zoneColor(breakeven?.zone)} />
  <Typography variant="caption" sx={{ color: '#888', ml: 'auto' }}>
    {curveData?.positions_count || 0} positions
  </Typography>
  <IconButton size="small" onClick={fetchCurve} title="Refresh curve">
    <RefreshIcon fontSize="small" />
  </IconButton>
</Box>
```

---

### Phase 4: Enhanced MMMBreakevenPanel.js Redesign

**Priority:** P1 High
**Effort:** 60 min
**File:** `webui/frontend/src/components/mmm/MMMBreakevenPanel.js` (MODIFY)

**Problem with current design:** The horizontal band bar uses fixed 10%/90% positions for breakeven markers regardless of actual price ratios. A session with BE boundaries 1% from spot looks identical to one with BE boundaries 10% from spot. This makes the visualization misleading.

**Fix:** Replace the fixed-position bar with a properly proportional linear scale.

**Props update:**
```jsx
MMMBreakevenPanel({ breakeven, gamma })
// gamma is optional — pass from parent; gamma markers shown only if gamma.enabled is true
```

**Update parent `MMMDashboard.js`** to pass `gamma` prop when rendering `MMMBreakevenPanel`.

**New scaled band bar specification (280px wide):**

The full bar represents the price range `[spot × (1 - view_range), spot × (1 + view_range)]` where `view_range = max(band_width_pct × 2, 10%) / 100`.

Price-to-position mapping:
```javascript
const priceToPos = (price) => {
  const pct = (price - rangeMin) / (rangeMax - rangeMin);
  return Math.max(0, Math.min(100, pct * 100)); // clamp to 0-100%
};
```

**Background color bands (CSS linear-gradient):**

Compute pixel positions for: `lower_be`, `upper_be`, and the critical/danger/warning offsets from each.

```
Left → Right:
  [0% → lower_be_critical_pos]:     #b71c1c (deep red, below BE)
  [lower_be_critical_pos → lower_be_danger_pos]:   #d32f2f (critical zone)
  [lower_be_danger_pos → lower_be_warning_pos]:    #e64a19 (danger zone)
  [lower_be_warning_pos → lower_be_pos]:           #f57c00 (warning zone)
  [lower_be_pos → upper_be_pos]:    #2e7d32 (safe zone, green)
  [upper_be_pos → upper_be_warning_pos]:           #f57c00
  [upper_be_warning_pos → upper_be_danger_pos]:    #e64a19
  [upper_be_danger_pos → upper_be_critical_pos]:   #d32f2f
  [upper_be_critical_pos → 100%]:   #b71c1c
```

All positions are in % of bar width, computed dynamically from actual prices.

**Marker overlays (absolute-positioned within bar container):**

- Lower BE: red `|` line at `priceToPos(lower_be)%`, 2px wide, full height + label `BE↓` below
- Upper BE: red `|` line at `priceToPos(upper_be)%`
- Lower gamma: orange dashed `|` at `priceToPos(lower_gamma_boundary)%` (only if gamma provided and gamma.enabled)
- Upper gamma: orange dashed `|` at `priceToPos(upper_gamma_boundary)%`
- Current spot: white filled circle (8px diameter) at `priceToPos(spot)%`, vertically centered, with colored border matching current breakeven zone color

**New header row:**
```
🎯 Breakeven Band     [SAFE]   [1.0x multiplier]   [▼ expand]
```

Zone badge: MUI `Chip` with color mapping:
- SAFE → success (green)
- WARNING → warning (amber)
- DANGER → error (orange-red)
- CRITICAL → error (red, pulsing animation)

Multiplier chip: shows `breakeven.multiplier + 'x'`, color matches zone.

**Distance labels below bar:**
```
↙ Lower: {distance_lower_pct}% (${(spot - lower_be).toFixed(0)})    ↗ Upper: {distance_upper_pct}% (${(upper_be - spot).toFixed(0)})
```

**Narrow band warning:** If `breakeven.is_narrow_band === true`, show an amber alert below the bar: "Band narrowing — breakeven boundaries converging".

**Collapsed state (default):** Show only the header row with the zone badge and multiplier chip. Expand button shows the full bar.

---

### Phase 5: Enhanced MMMGammaPanel.js Redesign

**Priority:** P2 Medium
**Effort:** 45 min
**File:** `webui/frontend/src/components/mmm/MMMGammaPanel.js` (MODIFY)

**New design additions (keep existing collapsed panel skeleton, add inside it):**

**Proximity meter:** A symmetric horizontal bar (240px) showing:
- Left side: lower gamma distance %
- Center: SPOT (labeled)
- Right side: upper gamma distance %
- Color: green (SAFE) → amber (WARNING) → red (DANGER) for each side independently

The meter has two halves. Each half's fill color is determined by whether that side's distance is within `gamma_danger_distance_pct`, `gamma_warning_distance_pct`, or beyond.

```
Left half (lower side):        Right half (upper side):
 ◄────────── 2.1% ──────[SPOT]────── 2.3% ──────────►
   [green/amber/red fill]           [green/amber/red fill]
```

**Severity indicator:**

The `gamma_severity_lower` and `gamma_severity_upper` values are negative floats (more negative = worse curvature). Normalize for display:

```javascript
// Severity bar: 0 to 100% width where -1000 = 100% width
const severityToWidth = (s) => Math.min(100, Math.abs(s) / 10);
```

Show as two small horizontal bars labeled "Lower Curvature" and "Upper Curvature" — wider = worse. Color matches gamma zone for that side.

**"Leading Indicator" badge:**

```jsx
<Tooltip title="Gamma boundaries are CLOSER to spot than breakeven boundaries. Gamma DANGER fires ~90 seconds before Breakeven WARNING at typical BTC velocity — giving the algorithm advance context before lot multipliers engage.">
  <Chip size="small" label="Leading Indicator" icon={<ElectricBoltIcon />} sx={{ bgcolor: '#ff6f00', color: '#fff', fontSize: '0.65rem' }} />
</Tooltip>
```

Show this badge only when `gamma.enabled === true` and `gamma.observation_only === true`.

**Phase 9 indicator:** When `gamma_severity_multiplier_enabled === false` (default), show a muted chip "Phase 9: Inactive" with a tooltip explaining what Phase 9 will do.

**Observation-only mode visual:** When `gamma.observation_only === true`, show a subtle banner: "Observation mode — severity scores computed, not yet used for lot sizing".

---

### Phase 6: MMMCombinedZoneWidget.js — Concentric Risk Rings

**Priority:** P2 Medium
**Effort:** 60 min
**File:** `webui/frontend/src/components/mmm/MMMCombinedZoneWidget.js` (NEW)

**Purpose:** A compact widget that shows both breakeven and gamma boundaries in a single horizontal scale — the concentric ring mental model rendered as a 1D visualization.

**Props:**
```jsx
MMMCombinedZoneWidget({ breakeven, gamma })
```

**Dimensions:** 100% width × 120px height (responsive).

**Layout:**

```
[BE lower]──[γ lower]──────────────[SPOT]──────────────[γ upper]──[BE upper]

◄──RED──────►◄──AMBER──►◄────────GREEN────────►◄──AMBER──►◄──RED──────►

  ←5.4%←      ←2.1%←                                →2.3%→     →4.8%→
```

**Zone color regions** (using absolute-positioned divs or SVG):

| Region | Color | Hex |
|---|---|---|
| Beyond lower BE (leftmost) | Deep red | `#b71c1c` |
| Lower BE to lower gamma | Amber warning | `#f57c00` |
| Lower gamma to SPOT | Green safe | `#2e7d32` |
| SPOT to upper gamma | Green safe | `#2e7d32` |
| Upper gamma to upper BE | Amber warning | `#f57c00` |
| Beyond upper BE (rightmost) | Deep red | `#b71c1c` |

**Markers:**

- `[BE lower]` `[BE upper]`: solid red vertical lines with price labels above
- `[γ lower]` `[γ upper]`: dashed orange vertical lines with price labels above
- `[SPOT]`: white filled circle, 10px diameter, with current price label below

**Distance labels:**

Row of 4 percentage labels below the bar, positioned at their respective markers:
```
5.4%     2.1%          ●          2.3%     4.8%
```

**Merge alert:** If lower gamma boundary is closer to spot than breakeven CRITICAL zone threshold (i.e., gamma boundary has merged with or passed the critical zone), show a red pulsing alert:

```jsx
{gammaCloserThanCritical && (
  <Alert severity="error" sx={{ mt: 0.5, py: 0, fontSize: '0.7rem' }}>
    Gamma boundary inside critical zone — extreme caution
  </Alert>
)}
```

**Combined zone summary chip:** Single chip showing the worst zone across both systems:
```jsx
const worstZone = pickWorst(breakeven?.zone, gamma?.gamma_zone);
<Chip label={`Combined: ${worstZone}`} color={zoneChipColor(worstZone)} size="small" />
```

**When gamma is disabled:** Render only the breakeven boundaries with a muted note "Gamma: disabled".

---

### Phase 6.5: MMMHealthRadar.js — Portfolio Health Spider Chart

**Priority:** P2 Medium
**Effort:** 45 min
**File:** `webui/frontend/src/components/mmm/MMMHealthRadar.js` (NEW)
**Depends on:** Nothing — all data already in heartbeat payload
**Risk:** Zero — uses Recharts `RadarChart` (already in recharts 2.9.0, no new dependencies)

#### Design Analysis: Why Concentric Circles Were Rejected

The originally proposed "Risk Radar" (concentric circles: center=spot, inner ring=gamma, outer ring=breakeven) was analyzed and rejected for the following reasons:

1. **Dimensionality mismatch**: BTC options risk is 1-dimensional — price moves up or down on a number line. Mapping 1D linear data to 2D polar coordinates wastes the entire angular (θ) dimension. The circle becomes a semicircle with a dot, which carries no more information than a horizontal bar. Phase 6 (CombinedZoneWidget) already shows the same spatial relationship more accurately and readably on a linear scale.

2. **Exact distance is harder to read radially**: Humans compare lengths more accurately on linear scales than on arcs. The concentric-circle design makes it harder, not easier, to judge "how close is spot to the gamma ring?"

3. **Redundant with Phase 6**: Both designs answer the question "where is spot relative to gamma and breakeven?" Phase 6 answers it on a linear scale; the concentric-circle design answers it on an arc. Same information, Phase 6 is more readable.

4. **Custom SVG vs. Recharts convention**: Concentric circles require custom SVG/Canvas. The rest of the dashboard uses Recharts. Breaking this convention adds maintenance burden.

#### What IS Worth Adding: A True 5-Axis Health Spider Chart

A Recharts `RadarChart` with 5 independent axes — each representing a different risk dimension — adds genuinely NEW information that no other panel shows:

| Axis | Data Source | Normalization | 0.0 = worst | 1.0 = best |
|---|---|---|---|---|
| **Breakeven Safety** | `breakeven.nearest_distance_pct` / `breakeven_warning_pct` | clamped 0-1 | spot at BE | spot far from BE |
| **Gamma Safety** | `gamma.nearest_distance_pct` / `gamma_warning_distance_pct` | clamped 0-1 | spot at γ boundary | spot far from γ |
| **Margin Health** | `(100 - margin.utilization_pct) / 100` | direct | margin at 100% | margin at 0% |
| **Band Width** | `breakeven.band_width_pct` / `breakeven_narrow_band_threshold` | clamped 0-1 | band width = 0 | band width ≥ threshold |
| **Regime Health** | mapped from `regime.action` string | see below | BLOCK_ALL | NORMAL |

**Regime health mapping:**
```javascript
const REGIME_SCORE = {
  'NORMAL': 1.0,
  'ACTION_BLOCK_DANGEROUS_SIDE': 0.65,
  'ACTION_BOOST_SAFE_SIDE': 0.85,
  'BLOCK_CE_SELLS': 0.6,
  'BLOCK_PE_SELLS': 0.6,
  'BLOCK_ALL_SELLS': 0.15,
};
```

**The value of this design**: When all 5 axes are healthy, the spider web polygon is large and symmetric (a "fat pentagon"). When any single dimension is stressed, that axis collapses — the polygon becomes asymmetric/lopsided. Operators immediately see WHICH dimension is under stress without reading any numbers.

**Example visual states:**

```
ALL SAFE: fat symmetric pentagon  MARGIN STRESS: lopsided on Margin axis
  Breakeven                          Breakeven
   1.0                                  0.9
   ╱───╲                              ╱───╲
  ╱     ╲                            ╱     ╲
Regime  Gamma                    Regime  Gamma
 0.9    0.8                       0.8    0.7
  ╲     ╱                            ╲   ╱
   ╲───╱                              ╲╱ ← Margin collapsed
Margin  Band                      Margin  Band
 0.9    0.8                        0.1    0.8
```

#### Component Spec

**Props:**
```jsx
MMMHealthRadar({ breakeven, gamma, heartbeat, session })
// heartbeat: full heartbeat object (for margin and regime data)
// session: for param defaults when heartbeat is unavailable
```

**Chart library:** Recharts `RadarChart` (zero new dependencies — recharts 2.9.0 already installed).

**Chart dimensions:** 200 × 200px. Compact — designed to sit beside other widgets in a 2-column layout.

**Data shape for Recharts:**
```javascript
const radarData = [
  { subject: 'Breakeven', value: beSafetyScore, fullMark: 1 },
  { subject: 'Gamma',     value: gammaSafetyScore, fullMark: 1 },
  { subject: 'Margin',    value: marginHealthScore, fullMark: 1 },
  { subject: 'BandWidth', value: bandHealthScore, fullMark: 1 },
  { subject: 'Regime',    value: regimeHealthScore, fullMark: 1 },
];
```

**Color logic:** The filled polygon changes color based on the MINIMUM score (weakest axis):
```javascript
const minScore = Math.min(...radarData.map(d => d.value));
const fillColor = minScore > 0.7 ? '#4caf50'   // green — all healthy
               : minScore > 0.4 ? '#ff9800'    // amber — stressed
               : '#f44336';                     // red — critical
```

**Recharts component structure:**
```jsx
<RadarChart cx="50%" cy="50%" outerRadius="80%" width={200} height={200} data={radarData}>
  <PolarGrid stroke="rgba(255,255,255,0.12)" />
  <PolarAngleAxis dataKey="subject" tick={{ fill: '#9e9e9e', fontSize: 10 }} />
  <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
  <Radar name="Health" dataKey="value" stroke={fillColor} fill={fillColor} fillOpacity={0.3} />
</RadarChart>
```

**Update strategy:** Every heartbeat (Recharts re-renders in ~0.1ms for a 5-point polygon — negligible cost).

**Header:**
```
🕸 Portfolio Health    [Overall: SAFE / WARNING / CRITICAL]
```
Show the overall health as a single chip (worst of all 5 axes).

**Edge cases:**
- Gamma disabled (`gamma.enabled === false`): set `gammaSafetyScore = 0.5` (neutral, not penalizing) and show a muted label "Gamma: off"
- No breakeven data: `beSafetyScore = 0.5` neutral
- No margin data: `marginHealthScore = 0.5` neutral
- No positions: all scores = 0.5, show "No positions — health unavailable" overlay

**What to NOT do:**
- Do not replace Phase 6 (CombinedZoneWidget) with this — they show different things. CombinedZoneWidget shows WHERE spot is spatially relative to boundaries; HealthRadar shows HOW HEALTHY each risk dimension is on a normalized scale.
- Do not animate the polygon — Recharts handles smooth transitions automatically via React re-renders.

**Placement in Risk tab:** Render side-by-side with the CombinedZoneWidget in a 2-column Grid layout (each 50% width on desktop, 100% on mobile). This keeps the top of the Risk tab compact before the full P&L chart.

---

### Phase 7: MMMDistanceHistoryChart.js — Zone Timeline

**Priority:** P2 Medium
**Effort:** 75 min
**File:** `webui/frontend/src/components/mmm/MMMDistanceHistoryChart.js` (NEW)

**Purpose:** Time-series chart showing how risk proximity evolved throughout the session. Answers "was the portfolio safe all session, or did it come close?" without needing to read activity logs.

**Props:**
```jsx
MMMDistanceHistoryChart({ sessionId, breakeven, gamma, heartbeatHistory })
// heartbeatHistory: array of historical heartbeat snapshots, managed by parent
```

**Data management:**

The parent component (MMMDashboard or the Risk tab) maintains a rolling buffer:

```javascript
const [heartbeatHistory, setHeartbeatHistory] = useState([]);
const MAX_HISTORY = 200;

// On each mmm_heartbeat socket event:
const onHeartbeat = (data) => {
  if (!data.breakeven || !data.gamma) return;
  setHeartbeatHistory(prev => {
    const entry = {
      time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
      timestamp: Date.now(),
      lower_be_pct: data.breakeven.distance_lower_pct,
      upper_be_pct: data.breakeven.distance_upper_pct,
      lower_gamma_pct: data.gamma.lower_distance_pct,
      upper_gamma_pct: data.upper_distance_pct,
      be_zone: data.breakeven.zone,
      gamma_zone: data.gamma.gamma_zone,
    };
    const next = [...prev, entry];
    return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
  });
};
```

**Chart specification (Recharts `LineChart`):**

- Height: 250px
- X-axis: `time` field (HH:mm), every 10th tick shown
- Y-axis: % distance (0–15%), labeled as `{v}%`

**Lines:**

| Line | Data key | Color | Style |
|---|---|---|---|
| Lower BE distance | `lower_be_pct` | `#f44336` | dashed |
| Upper BE distance | `upper_be_pct` | `#f44336` | solid |
| Lower γ distance | `lower_gamma_pct` | `#ff9800` | dashed |
| Upper γ distance | `upper_gamma_pct` | `#ff9800` | solid |

**Threshold reference lines (horizontal):**

| Line | Y value | Color | Style | Label |
|---|---|---|---|---|
| BE warning | `breakeven_warning_pct` (2.0) | `#f57c00` | dashed | `Warning` |
| BE danger | `breakeven_danger_pct` (1.0) | `#f44336` | dashed | `Danger` |
| Gamma warning | `gamma_warning_distance_pct` (3.0) | `#ff9800` | dotted | `γ Warning` |

These thresholds should be read from the `session` params — they may be non-default.

**Event markers (vertical reference lines):**

Listen for these socket events and record their timestamps in a separate `events` array:

| Socket Event | Label | Color |
|---|---|---|
| `mmm_shield_fired` | `Shield↑` or `Shield↓` | `#e91e63` (pink) |
| `mmm_shift` | `Shift` | `#9c27b0` (purple) |
| `mmm_adjustment` | (no label, too frequent) | — |

Render events as `ReferenceLine x={timestamp}` with a rotated label at the top.

**Empty state:** "Collecting data — distance history populates from session heartbeats." Show after mount if history is empty.

**Note:** This component does NOT fetch historical data from the backend. It only accumulates data during the current browser session. If the page is refreshed, history resets. This is intentional — adding backend persistence is a future enhancement.

---

### Phase 8: Dashboard Layout Integration

**Priority:** P3 Lower
**Effort:** 30 min
**File:** `webui/frontend/src/components/mmm/MMMDashboard.js` (MODIFY)

**Approach:** Add a new "Risk" tab to the session detail tab strip alongside Overview, P&L, Activity (and Settings if present).

**Tab strip change:**

Locate the `<Tabs>` component in the session detail section. Add:
```jsx
<Tab label="Risk" value="risk" />
```

**Risk tab content:**

```jsx
{activeTab === 'risk' && (
  <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
    <MMMCombinedZoneWidget breakeven={session.breakeven} gamma={session.gamma} />
    <Divider />
    <MMMRiskProfileChart
      sessionId={session.session_id}
      breakeven={session.breakeven}
      gamma={session.gamma}
      session={session}
    />
    <Divider />
    <MMMDistanceHistoryChart
      sessionId={session.session_id}
      breakeven={session.breakeven}
      gamma={session.gamma}
      heartbeatHistory={heartbeatHistory}
    />
  </Box>
)}
```

**Overview tab:** Keep existing MMMBreakevenPanel and MMMGammaPanel, but:
1. Update `MMMBreakevenPanel` call to also pass `gamma`:
   ```jsx
   <MMMBreakevenPanel breakeven={session.breakeven} gamma={session.gamma} />
   ```
2. The gamma panel remains standalone on Overview.

**Heartbeat history state:** Add `heartbeatHistory` state at the dashboard level (or session detail level) and wire the `mmm_heartbeat` socket event to populate it. Pass `heartbeatHistory` down to `MMMDistanceHistoryChart`.

**Imports:** Add imports for all 3 new components at the top of `MMMDashboard.js`:
```javascript
import MMMRiskProfileChart from './MMMRiskProfileChart';
import MMMCombinedZoneWidget from './MMMCombinedZoneWidget';
import MMMDistanceHistoryChart from './MMMDistanceHistoryChart';
```

---

## Section 7: Consolidated Visual Layout Specification

```
SESSION DETAIL VIEW
════════════════════

TABS: [Overview] [Risk ← NEW] [P&L] [Positions] [Activity] [Settings]

══ OVERVIEW TAB ══════════════════════════════════════════════════════

 [Trigger Gauges — existing]

 ┌─ Enhanced MMMBreakevenPanel ─────────────────────────────────────┐
 │  🎯 Breakeven Band    [🟢 SAFE]   [1.0x]          [▼ expand]    │
 │  ┌──────────────────────────────────────────────────────────┐    │
 │  │ ░░░░░░[─BE─][──γ──────────────●──────────────γ──][─BE─]░ │    │
 │  │   BE↓   γ↓                 $90k               γ↑   BE↑  │    │
 │  │  $82k  $87k                                  $93k  $98k  │    │
 │  └──────────────────────────────────────────────────────────┘    │
 │   ↙ Lower: 5.4% ($4,860)              ↗ Upper: 5.3% ($4,770)    │
 └──────────────────────────────────────────────────────────────────┘

 ┌─ Enhanced MMMGammaPanel ─────────────────────────────────────────┐
 │  ⚡ Gamma Boundaries  [🟢 SAFE] [Leading Indicator] [▼ expand]  │
 │  ├─────────── 2.1% ────────[●SPOT]──────── 2.3% ───────────┤    │
 │  Lower curvature: ██░░░░░░░░  Upper curvature: ███░░░░░░░░  │    │
 │  [Observation mode — severity scores not yet used for sizing]    │
 └──────────────────────────────────────────────────────────────────┘

══ RISK TAB (NEW) ════════════════════════════════════════════════════

 ┌─ Row 1: 2-column layout ───────────────────────────────────────────────────────┐
 │                                                                                  │
 │  ┌─ Combined Zone Rings ─────────────────┐  ┌─ Portfolio Health ─────────────┐  │
 │  │ [BE↓]─[γ↓]──────[●]──────[γ↑]─[BE↑] │  │  🕸 Portfolio Health [🟢 SAFE]  │  │
 │  │ ◄─RED─►◄AMBER►◄─GREEN──►◄AMBER►◄─RED►│  │         Breakeven               │  │
 │  │  5.4%   2.1%           2.3%   4.8%   │  │          1.0                    │  │
 │  │        [Combined: 🟢 SAFE]            │  │   Regime ╱──────╲ Gamma         │  │
 │  └───────────────────────────────────────┘  │     0.9 ╱        ╲ 0.8         │  │
 │                                             │         ╲        ╱             │  │
 │  NOTE: Left = spatial "WHERE is spot"       │   Band   ╲──────╱ Margin       │  │
 │  Right = dimensional "HOW HEALTHY is each"  │     0.8              0.9        │  │
 │  These answer complementary questions.      │  [fat pentagon = all healthy]   │  │
 │                                             └────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────────────┘

 ┌─ P&L Risk Profile ───────────────────────────────────────────────┐
 │  📈 P&L Risk Profile    [🟢 SAFE]    6 positions    [↻ Refresh]   │
 │                                                                    │
 │  $20 ─                                                             │
 │  $10 ─  ╔════════╗                             ╔════════╗          │
 │   $5 ─  ║        ╚═══════════━━━━━━━━━━━═══════╝        ║          │
 │   $0 ─ ─╫───────────────────────────────────────────────╫─ - - - │
 │  -$5 ─  ║               ●SPOT                            ║          │
 │ -$15 ─  ╚════╗                                     ╔════╝          │
 │ -$25 ─       ╚════════╗                   ╔════════╝               │
 │       $75k  $80k  $85k BE↓ γ↓ $90k γ↑ BE↑ $95k  $100k  $105k    │
 └──────────────────────────────────────────────────────────────────┘

 ┌─ Distance History ───────────────────────────────────────────────┐
 │  15% ····γ Warning············································     │
 │  10%    ─────────────────────────────────────────────────────     │
 │   5% BE upper ──────────────────────────────────                  │
 │       ────────────────────────────────────────── Warning──        │
 │   3% γ upper ─────────────────────────────────                    │
 │   2%                                          ───Danger──         │
 │   1%    BE lower ────────────────────────────              ↑Shield│
 │   0% ────────────────────────────────────────────────────────     │
 │      10:00  10:15  10:30  10:45  11:00  11:15  11:30  11:45       │
 └──────────────────────────────────────────────────────────────────┘
```

**Color reference for all new UI elements:**

| Element | Hex | Usage |
|---|---|---|
| Breakeven SAFE | `#2e7d32` | Safe zone band, SAFE chip |
| Breakeven WARNING | `#f57c00` | Warning band, threshold line |
| Breakeven DANGER | `#e64a19` | Danger band, threshold line |
| Breakeven CRITICAL | `#d32f2f` | Critical band, pulsing chip |
| Breakeven beyond | `#b71c1c` | Leftmost/rightmost bar regions |
| Gamma boundary | `#ff9800` | Gamma markers (dashed), gamma panel color |
| Gamma DANGER | `#ff6f00` | Deep amber, settings group accent |
| Shield event | `#e91e63` | Shield timeline markers |
| Strike shift event | `#9c27b0` | Shift timeline markers |
| Spot marker | `#ffffff` | Current spot circle on all bars |

---

## Section 8: MMM Algo Deep Benefit Analysis

### 8.1 Early Warning Pipeline — Detailed Scenario

```
Scenario: BTC at $90,000. Short CE strike at $93,000 (3.3% OTM). BTC rising at $450/min.

T-0: Start. Both panels green. Combined widget shows all-green.
  BE boundaries: $82,500 / $98,000  (8.3% / 8.9% from spot)
  γ boundaries:  $86,700 / $93,000  (3.7% / 3.3% from spot)

T-3min: BTC reaches $91,350 ($450 × 3min). γ upper distance = 1.65% → DANGER fires.
  → MMMGammaPanel turns red-amber.
  → Distance history shows γ upper line crossing the danger threshold.
  → Breakeven is still SAFE (upper BE at $98,000, still 7.3% away).
  → Algorithm: NO lot change yet. Operator has advance context.

T-5min: BTC reaches $92,250. γ upper distance = 0.81% → well inside DANGER.
  BE upper distance dropping: $98,000 - $92,250 = $5,750 = 6.2%. Still SAFE.
  → Risk tab combined widget: γ = DANGER, BE = SAFE. Combined = WARNING.

T-7min: BTC reaches $93,150. Upper BE: $98,000 - $93,150 = $4,850 = 5.2%. Still SAFE.
  ATM Shield: ~0.5% from $93,000 strike → Shield fires.
  → Close CE leg at $93,000. Reopen CE at $94,500 (+1.5% OTM).
  → Cache invalidated. New curve computed.

T-7.5min (post-shield): New γ upper boundary = $94,500. Distance = 1.45% from $93,150.
  BE upper recalculated with new OTM premium → widens to $100,000 (7.3%).
  → Risk tab P&L chart RESHAPES. The right side slope flattens visibly.
  → Distance history shows a "Shield↑" vertical marker, then γ line jumps outward.
  → Both panels return to green/amber from red.

NET RESULT: The visual timeline tells the complete story. No log parsing needed.
```

### 8.2 Multiplier Cascade — Detailed Mechanics

The lot size formula in `mmm_engine.py`:

```
final_lots = min(
  ceil(base_lots × gamma_mult × breakeven_mult × trend_mult),
  base_lots × max_combined_lot_multiplier
)
```

Zones and their multiplier ramps:

| BE Zone | Distance | breakeven_mult range |
|---|---|---|
| SAFE | > warning_pct | 1.0x |
| WARNING | danger_pct to warning_pct | 1.0x → 1.5x (linear ramp) |
| DANGER | critical_pct to danger_pct | 1.5x → 2.5x (linear ramp) |
| CRITICAL | < critical_pct | 2.5x → 3.0x (linear ramp to min distance) |

The P&L chart directly shows WHY multipliers escalate: the visible slope of the loss curve steepens as spot approaches BE. The algorithm is responding to that slope.

### 8.3 P&L Curve as Operator Decision Tool

The P&L curve provides answers to questions operators currently cannot easily answer:

| Question | Without chart | With chart |
|---|---|---|
| "If BTC drops 5%, what's my loss?" | Mental math over 6+ positions | Read Y-axis at spot-5% |
| "Is the portfolio symmetric?" | Compare upper/lower BE distances | Visual — does curve have equal slopes? |
| "Is loss acceleration starting?" | Not detectable without gamma | See the kink where γ boundary is |
| "Did the shield improve my situation?" | Check activity log | Chart reshapes visibly after shield |
| "How much buffer before critical?" | Compute from each position | Distance from current spot to red zone |

### 8.4 Phase 9 Readiness Signal

When `gamma_severity_multiplier_enabled` is enabled (Phase 9), the gamma severity scores:

- `gamma_severity_lower` ≈ second derivative of P&L at lower boundary (negative)
- `gamma_severity_upper` ≈ second derivative of P&L at upper boundary (negative)

The score magnitude tells how FAST the loss accelerates at each boundary. A severity of -800 means $800 of additional loss per 1% of additional price movement, per unit of portfolio size.

Phase 9 will use the severity asymmetry: if `abs(gamma_severity_lower) >> abs(gamma_severity_upper)`, the lower side has worse curvature, meaning more PE lot selling is warranted. This is directional intelligence that goes beyond the current symmetric lot sizing.

**Phase 9 prerequisites (not in this plan — future work):**
1. 10+ sessions of severity data to calibrate thresholds
2. Severity normalization per portfolio size
3. A/B testing framework to compare P&L with/without severity multiplier

The severity bars in the gamma panel (Phase 5) begin collecting operator intuition for these values before Phase 9 is automated.

---

## Section 9: File Change Map

| File | Change Type | Priority | Phase | Effort |
|---|---|---|---|---|
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | Modify — add gammaDetector param group | P0 Critical | 1 | 30 min |
| `webui/backend/routes/mmm/mmm_api.py` | Modify — add `/pnl-curve` endpoint | P1 High | 2 | 45 min |
| `webui/frontend/src/components/mmm/MMMRiskProfileChart.js` | New file | P1 High | 3 | 90 min |
| `webui/frontend/src/components/mmm/MMMBreakevenPanel.js` | Modify — scaled bar + gamma markers | P1 High | 4 | 60 min |
| `webui/frontend/src/components/mmm/MMMGammaPanel.js` | Modify — proximity meter + severity bars | P2 Medium | 5 | 45 min |
| `webui/frontend/src/components/mmm/MMMCombinedZoneWidget.js` | New file | P2 Medium | 6 | 60 min |
| `webui/frontend/src/components/mmm/MMMHealthRadar.js` | New file — 5-axis spider chart | P2 Medium | 6.5 | 45 min |
| `webui/frontend/src/components/mmm/MMMDistanceHistoryChart.js` | New file | P2 Medium | 7 | 75 min |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | Modify — Risk tab + new component wiring | P3 Lower | 8 | 30 min |

**Total estimated effort:** ~7.75 hours (single focused session)

**New dependency added:** None. `RadarChart`, `PolarGrid`, `PolarAngleAxis`, `PolarRadiusAxis`, `Radar` are all in recharts 2.9.0 (already installed). Import them from `'recharts'` — same as other chart components.

**No backend files other than `mmm_api.py` need changes.** All computation already exists. The backend work is purely one additive endpoint.

---

## Section 10: Implementation Sequencing Rules

1. **Phase 1 first** (Settings dialog): Standalone, zero risk, 30 min. Unblocks operators from tuning gamma params. No dependency on any other phase.

2. **Phase 2 second** (API endpoint): Standalone backend change. No frontend dependency. Do before any chart work.

3. **Phase 3 after Phase 2** (P&L chart): Depends on the `/pnl-curve` endpoint existing. Can be built with a mock endpoint during development but should be tested against the real endpoint.

4. **Phases 4 and 5 in parallel with Phase 3**: Panel redesigns have no dependency on the new API endpoint. Can be developed independently and merged.

5. **Phase 6 after Phase 4** (Combined widget): Needs the price-to-position scaling logic to be stable — extract it as a shared utility `priceToBarPct(price, rangeMin, rangeMax)` during Phase 4 so Phase 6 can reuse it.

5.5. **Phase 6.5 in parallel with Phase 6** (Health Radar): Has zero dependency on any other phase. All data comes from the heartbeat payload. The only imports needed are Recharts components. Can be built, tested, and merged completely independently.

6. **Phase 7 in parallel with Phases 6/6.5**: Distance history chart has no dependency on Phases 4-6. Only needs socket data.

7. **Phase 8 last** (Dashboard layout): Wires all new components together. Must be done after all components are built and tested individually.

**Shared utility to extract during Phase 4:**

```javascript
// webui/frontend/src/components/mmm/mmmChartUtils.js (NEW — small utility)
export const priceToBarPct = (price, rangeMin, rangeMax) => {
  if (rangeMax <= rangeMin) return 50;
  return Math.max(0, Math.min(100, ((price - rangeMin) / (rangeMax - rangeMin)) * 100));
};

export const zoneToColor = (zone) => ({
  SAFE: '#2e7d32',
  WARNING: '#f57c00',
  DANGER: '#e64a19',
  CRITICAL: '#d32f2f',
}[zone] || '#888');

export const zoneToMuiColor = (zone) => ({
  SAFE: 'success',
  WARNING: 'warning',
  DANGER: 'error',
  CRITICAL: 'error',
}[zone] || 'default');
```

Both Phase 4 (MMMBreakevenPanel) and Phase 6 (MMMCombinedZoneWidget) use `priceToBarPct`. Extracting it prevents code duplication.

---

## Section 11: Open Questions for Operator

These questions should be answered before or during Phase 8 to avoid rework:

**Q1: Risk tab vs. Overview coexistence**

> Should the enhanced breakeven/gamma panels on Overview be replaced by a link to the Risk tab, or should both exist?
>
> Recommendation: Keep Overview panels for quick glance (compact, always visible), keep Risk tab for deep analysis (full charts). The Overview panels become the "summary" and the Risk tab becomes the "detail view". Implement this way unless operator prefers otherwise.

**Q2: P&L curve refresh strategy**

> Should the P&L curve auto-refresh on every adjustment event (`mmm_adjustment`, `mmm_shift`), or should it be manual (Refresh button only)?
>
> Recommendation: Auto-refresh on `mmm_shift` and `mmm_breakeven` events (structural position changes), but NOT on `mmm_adjustment` (too frequent). Add a visible "Stale — click to refresh" indicator if last fetch was > 60 seconds ago. Manual refresh button always available.

**Q3: Gamma DANGER → ATM Shield modulation (Phase 9 precursor)**

> Could gamma DANGER zone eventually be used to modulate ATM Shield sensitivity — e.g., when gamma is in DANGER, lower the shield OTM threshold from 0.5% to 0.3% (fire earlier)?
>
> This is a Phase 9 question. The current plan does not implement this. But Phase 5's severity display and Phase 7's distance history will provide the empirical data needed to decide. Recommend: collect 10 sessions of data showing gamma-to-shield timing, then decide.

**Q4: gamma_detector_enabled default change**

> Currently `gamma_detector_enabled = false` in DEFAULT_PARAMS. After 3 sessions with observation data confirming the detector works, should the default be changed to `true`?
>
> Recommendation: Yes, but only after:
> - Phase 1 is deployed (so it can be toggled from UI)
> - 3 complete sessions with gamma enabled manually
> - Severity scores reviewed for reasonableness
> - No unexpected performance impact on heartbeat cycle observed

**Q5: Historical curve data persistence**

> The MMMDistanceHistoryChart currently only accumulates data within the current browser session (no backend persistence). Should backend persistence be added later?
>
> Recommendation: Defer. The activity log already records zone transitions. A future enhancement could rebuild the history chart from activity log data on component mount. Not in scope for this plan.

---

---

## Section 12: Risk Radar Design Analysis (Concentric Circle Concept — Full Evaluation)

This section documents the complete feasibility analysis of the proposed "Risk Radar" (concentric circles), explains why it was rejected in its original form, and documents the adapted design (Phase 6.5 Health Radar) that was adopted instead.

### 12.1 Feasibility Assessment

**Can it be implemented with existing heartbeat data?** Yes — all fields are already in the payload:
- `breakeven.distance_lower_pct`, `breakeven.distance_upper_pct` → outer ring radii
- `gamma.lower_distance_pct`, `gamma.upper_distance_pct` → inner ring radii
- `breakeven.zone`, `gamma.gamma_zone` → ring colors

No new backend work needed for either design.

### 12.2 Mathematical Mapping — Concentric Circle Design

For the concentric-circle design, the radial mapping would be:

```
inner_ring_radius = f(gamma_distance_pct)
outer_ring_radius = f(breakeven_distance_pct)

f(pct) = BASE_RADIUS × min(pct / MAX_DISPLAY_PCT, 1.0)

where BASE_RADIUS ≈ 80px (outer ring) and inner = 0.5 × outer
```

**The problem**: Both directions (lower and upper) collapse to a single ring radius, losing the asymmetry information. A 2.1% lower gamma distance and 2.3% upper gamma distance map to the same ring, hiding that the lower side is slightly more dangerous. To show asymmetry, you'd need a half-ring per side — at which point you have a bar chart drawn as a semicircle, which is harder to read than just a bar.

### 12.3 Rendering Approach Comparison

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| Pure SVG | Full control, crisp at any size, no dependencies | 150-200 lines of manual SVG code, breaks Recharts convention | ❌ Reject |
| Canvas | Fastest for animation | Complex React integration, accessibility issues, no MUI theming | ❌ Reject |
| Recharts `PolarRadiusAxis` | Native integration | Recharts polar API is designed for spider charts, NOT concentric circles — would require workarounds | ❌ Reject |
| Recharts `RadarChart` (5 axes) | Native integration, zero new deps, already in recharts 2.9.0 | Only for multi-dimensional data, NOT concentric circles | ✅ **Adopt (adapted design)** |

### 12.4 Why the Concentric Circle Design Was Rejected

**Core reason: Dimensionality mismatch**

BTC options risk is **strictly 1-dimensional**. BTC spot price can only go up or down — there is no second spatial dimension. The gamma boundary and breakeven boundary are both points on a number line (price axis), not rings around a center in 2D space.

Mapping 1D → 2D polar coordinates:
- The radius dimension (r) carries information: distance from spot to boundary
- The angular dimension (θ) carries **no information** for this data
- The result is a semicircle with markers — equivalent visual information to a horizontal bar, harder to read

This is not a design preference — it's a mathematical property of the data. Any circular visualization of 1D options risk must either waste the angular dimension (misleading) or map a non-existent second dimension (fabricated).

**Specific problems:**

1. **Can't compare distances accurately in radial form**: Given inner ring at r=40px and outer ring at r=80px, humans cannot accurately judge that inner=50% of outer. On a linear bar, this is immediately apparent.

2. **Angular positioning is arbitrary**: Would the lower gamma boundary be at 180° (left) and upper at 0° (right)? Or both at 270°/90°? Any choice is arbitrary because angle has no meaning in the model.

3. **Strike markers as angles**: The proposal mentions showing option strikes as "angular markers." This would require mapping a strike price to an angle — but angle represents nothing in the model, so this mapping would be completely arbitrary and potentially confusing.

4. **Redundant with Phase 6**: CombinedZoneWidget already shows spatial proximity on a linear scale, which is the correct representation for 1D data.

### 12.5 Why the Health Radar (Phase 6.5) Was Adopted

The adopted design turns the "radar" metaphor into a genuine **multi-dimensional health monitor** — which is exactly what spider charts are designed for.

**5 dimensions that are genuinely independent:**
1. Breakeven safety — distance to portfolio loss
2. Gamma safety — distance to loss acceleration zone
3. Margin health — exchange margin utilization
4. Band width health — convergence of breakeven boundaries
5. Regime health — algo's current trading restrictions

These 5 dimensions can be stressed or healthy independently:
- A session can have good breakeven safety but poor margin health (over-capitalized position)
- A session can have good gamma safety but a BLOCK_ALL regime (vol spike)
- A session can have narrow band width but still be far from breakeven (low net premium collected)

The spider chart shows all 5 simultaneously. The "lopsided polygon" pattern tells operators which dimension is the bottleneck. This genuinely cannot be seen from any other panel.

### 12.6 Update Strategy

Health Radar: every heartbeat (~0.1ms Recharts re-render for 5-point polygon, negligible).

Concentric circle design (if it were adopted): same — every heartbeat for distance recalculation.

No performance difference between the two designs. Both are safe for heartbeat-rate updates.

### 12.7 Potential Pitfalls of Phase 6.5 Health Radar

1. **Normalization sensitivity**: If `breakeven_warning_pct` is set to a very large value (e.g., 15%), the Breakeven Safety axis is almost always near 1.0 (safe), giving a false impression. Mitigation: cap the normalization denominator at a reasonable value (e.g., 10%).

2. **Neutral defaults for missing data**: When gamma is disabled, setting `gammaSafetyScore = 0.5` is correct but could be confusing — a user might think gamma=0.5 is a real measurement. Mitigation: show a muted "γ: off" label on the Gamma axis tick.

3. **Regime string matching**: The `regime.action` strings must match exactly. If backend adds new action strings, the `REGIME_SCORE` mapping will return `undefined → 0.5`. The `?? 0.5` fallback handles this gracefully.

4. **Band width when one breakeven is missing**: `band_width_pct` is `null` when only one boundary exists. Use `0.5` as neutral in this case (not penalizing a healthy one-sided portfolio).

5. **Spider chart with 5 axes is unfamiliar to some operators**: Add a "?" icon with a tooltip explaining each axis and its meaning. This is especially important for the Band Width and Regime axes which are less intuitive.

### 12.8 Summary Verdict

| Concept | Feasibility | Information Value | Implementation Cost | Verdict |
|---|---|---|---|---|
| Concentric circle radar | ✅ Feasible | ❌ Redundant with Phase 6 | Medium (custom SVG) | **REJECTED** |
| Portfolio threat gauge (speedometer) | ✅ Feasible | ⚠️ Marginal (collapses 5D to 1D) | Low (SVG arc) | Not adopted |
| 5-axis health spider chart | ✅ Feasible | ✅ Genuinely new information | Low (Recharts, 120 lines) | **ADOPTED as Phase 6.5** |

---

*Plan updated 2026-03-15 with Risk Radar analysis and Phase 6.5 Health Radar adoption.*
*Total phases: 9 (Phases 1, 2, 3, 4, 5, 6, 6.5, 7, 8). Total new/modified files: 9.*
