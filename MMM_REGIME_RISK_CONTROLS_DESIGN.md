# MMM Regime-Aware Risk Controls — System Design Document

> **Author:** AI Risk Architecture  
> **Date:** February 20, 2026  
> **Status:** Implementation Plan (no code)  
> **Goal:** Convert MMM from a reactive premium collector into a regime-aware risk-managed volatility system.

---

## Executive Summary

MMM currently responds to premium moves reactively: when one side's premium rises, it sells more of the opposite side. This short-gamma behavior increases exposure into adverse moves. The three controls below add **pre-adjustment regime sensing** — the system detects dangerous market conditions *before* they trigger the adjustment engine, and blocks or modifies behavior accordingly.

| Control | What It Detects | Primary Action |
|---------|----------------|----------------|
| **Volatility Regime Filter** | IV/RV spike, elevated vol environment | Block new sells, pause adjustments |
| **Portfolio Gamma Cap** | Excessive gamma exposure accumulation | Cap portfolio risk, force reduction |
| **Trend Detection Guard** | Strong directional move without retracement | Block exposure-increasing trades |

---

## SECTION A — VOLATILITY REGIME FILTER

### A.1 Metric Selection

Use a **two-layer composite** — fast detection + regime confirmation:

| Layer | Metric | Purpose |
|-------|--------|---------|
| **Fast** | IV Change Rate (ΔIV%) | Catches sudden spikes within a session |
| **Slow** | Realized Volatility Percentile (RV Rank) | Identifies sustained high-vol environment |

**Why not IV percentile alone?** BTC 0DTE IV has no deep historical term structure. The exchange provides live `mark_iv` per strike, but historical IV percentile requires a separate database. RV is computable from spot prices the system already fetches.

### A.2 Formulas

#### A.2.1 IV Change Rate (ΔIV%)

Track the `mark_iv` of the active CE and PE strikes. Store a rolling window of the last `N` IV observations (one per heartbeat).

$$\Delta IV\% = \frac{IV_{now} - IV_{anchor}}{IV_{anchor}} \times 100$$

Where:
- $IV_{now}$ = average of `mark_iv` for active CE and PE strikes (from Delta Exchange ticker, already fetched in heartbeat)
- $IV_{anchor}$ = IV at the time the session was started (or at last regime reset)
- The **rate** version uses $IV_{t-k}$ instead of anchor:

$$\Delta IV_{rate} = \frac{IV_{now} - IV_{t-k}}{IV_{t-k}} \times 100$$

Where $k$ = `vol_lookback_beats` (default: 5 beats). At 60s adaptive interval, this is a 5-minute lookback.

#### A.2.2 Realized Volatility (Yang-Zhang or Close-to-Close)

Compute using spot prices collected every heartbeat:

$$RV = \sigma_{CC} = \sqrt{\frac{1}{n-1} \sum_{i=1}^{n} \left(\ln\frac{S_i}{S_{i-1}}\right)^2} \times \sqrt{\frac{86400}{T_{avg}}} \times 100$$

Where:
- $S_i$ = spot price at heartbeat $i$
- $T_{avg}$ = average seconds between beats
- Annualization: $\sqrt{365}$ (crypto, 24/7)
- Window: last `rv_window` observations (default: 20 beats)

#### A.2.3 Composite Regime Score

$$R_{score} = w_1 \times \frac{\Delta IV_{rate}}{IV_{threshold}} + w_2 \times \frac{RV_{now}}{RV_{threshold}}$$

Default weights: $w_1 = 0.6$, $w_2 = 0.4$

Regime states:

| $R_{score}$ | State | Label |
|-------------|-------|-------|
| < 0.7 | NORMAL | `VOL_REGIME_NORMAL` |
| 0.7 – 1.0 | ELEVATED | `VOL_REGIME_ELEVATED` |
| > 1.0 | HIGH | `VOL_REGIME_HIGH` |

### A.3 Threshold Logic

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vol_regime_enabled` | True | Master switch |
| `vol_iv_spike_pct` | 30 | ΔIV% threshold — if IV rises >30% from anchor → flag |
| `vol_rv_threshold` | 80 | Annualized RV % threshold |
| `vol_lookback_beats` | 5 | Beats to look back for IV rate calculation |
| `vol_rv_window` | 20 | Beats for RV computation |
| `vol_regime_action` | `block_sells` | Action: `block_sells`, `pause`, `wind_down` |
| `vol_regime_cooldown_beats` | 10 | Must stay below threshold for N beats before NORMAL |

### A.4 State Flags

```
session['_vol_regime'] = 'NORMAL' | 'ELEVATED' | 'HIGH'
session['_vol_regime_since'] = ISO timestamp
session['_vol_iv_history'] = [(timestamp, iv_avg), ...]  # ring buffer, max 60
session['_vol_spot_history'] = [(timestamp, spot), ...]   # ring buffer, max 60
session['_vol_regime_beats_below'] = 0  # counter for cooldown
```

### A.5 Integration Point

In the heartbeat loop, **after safety checks** and **before trigger evaluation**:

```
close-at-5 → wind-down → safety checks → ★ VOL REGIME CHECK ★ → trigger evaluation → adjustment
```

If `VOL_REGIME_HIGH`:
- Skip trigger evaluation entirely (no adjustments)
- Log activity: "🔥 HIGH VOL REGIME — adjustments blocked"
- Emit `mmm_safety` event with type `vol_regime` and level `alert`

If `VOL_REGIME_ELEVATED`:
- Allow close-at-5 (risk-reducing) — always runs before this check
- Allow wind-down buybacks (risk-reducing)
- Block new sell adjustments only — let safety and close logic continue
- Log: "⚠️ ELEVATED VOL — new sells blocked, close-at-5 active"

### A.6 Behavior During Wind-Down and Near Expiry

- Wind-down buybacks are **always allowed** regardless of vol regime (they reduce risk)
- Close-at-5 is **always allowed** (risk-reducing)
- Near-expiry auto-close (`auto_close_mins`) is **always allowed** (safety override)
- If `vol_regime_action` = `wind_down`, then HIGH regime **activates wind-down** in addition to blocking sells (sets `session['_vol_wind_down_triggered'] = True`, checked by `is_wind_down_active()`)

### A.7 Edge Cases

| Case | Handling |
|------|----------|
| **IV data missing** (ticker returns null) | Skip IV layer, use RV-only (set $w_1 = 0, w_2 = 1.0$) |
| **< 5 spot samples** (session just started) | Keep regime NORMAL until `vol_rv_window` fills |
| **Sudden IV spike then revert** | Cooldown counter (`vol_regime_cooldown_beats`) prevents premature NORMAL reset |
| **Both sides have different IVs** | Use max(CE_iv, PE_iv) as the conservative estimate |
| **API lag / stale IV** | If IV hasn't changed for 5+ beats AND spot has moved >1%, log stale-IV warning; use RV-only |

### A.8 Data Source

IV: Already available from the same Delta Exchange `/v2/tickers/{symbol}` call that the heartbeat uses for mark_price. The `mark_iv` field is already parsed in the greeks-iv endpoint. The heartbeat just needs to also read this field during premium fetch.

RV: Computed from spot prices already fetched via `_fetch_spot_price()`.

**No new API calls required.**

---

## SECTION B — PORTFOLIO GAMMA CAP

### B.1 Gamma Calculation

#### B.1.1 Per-Position Gamma

Delta Exchange provides per-contract gamma via `/v2/tickers/{symbol}` → `greeks.gamma`.

The existing `get_greeks_iv` endpoint already computes per-lot position Greeks:

$$\gamma_{position} = \gamma_{ticker} \times LOT\_SIZE\_BTC \times (-1) \times lots$$

The $(-1)$ accounts for short positions. For gamma:
- Short calls: **negative gamma** (you lose when spot moves either direction)
- Short puts: **negative gamma** (same)
- Because both sides are short, portfolio gamma is always **negative** (the risk)

#### B.1.2 Total Portfolio Gamma

$$\Gamma_{portfolio} = \sum_{all\ positions} \gamma_{ticker,i} \times LOT\_SIZE\_BTC \times lots_i$$

Note: no sign flip here — we want the **absolute** portfolio gamma exposure. We track this as a positive number representing total gamma risk. Higher = more dangerous.

#### B.1.3 Dollar Gamma (Gamma per $1 spot move)

For actionable limits, normalize to dollars:

$$\$\Gamma = \Gamma_{portfolio} \times S_{spot}^2 \times 0.01$$

This gives the P&L impact of a 1% spot move from gamma alone. This is the standard "dollar gamma" metric used by institutional desks.

**Why dollar gamma?** Raw gamma changes wildly with spot price. A gamma of 0.00001 at BTC $100K is very different from the same gamma at BTC $30K. Dollar gamma normalizes this.

### B.2 Risk Limits

| Level | Threshold | Action |
|-------|-----------|--------|
| **Soft** | `gamma_soft_limit` (default: portfolio $Γ > $50) | Warning log + WebSocket alert |
| **Hard** | `gamma_hard_limit` (default: portfolio $Γ > $100) | Block all new sell orders (adjustments + entries) |
| **Emergency** | `gamma_emergency_limit` (default: portfolio $Γ > $200) | Force wind-down buybacks to reduce gamma below hard limit |

Dollar values are examples — actual defaults should be calibrated based on account size. The user should set these relative to their max_loss_amount.

**Suggested rule of thumb:**
- `gamma_soft_limit` = `max_loss_amount × 0.01` (1% of max loss)
- `gamma_hard_limit` = `max_loss_amount × 0.02`
- `gamma_emergency_limit` = `max_loss_amount × 0.04`

### B.3 0DTE Gamma Behavior

This is the critical risk. For 0DTE options:

- Gamma **explodes** near ATM as expiry approaches — this is "gamma knife" territory
- OTM/ITM gamma decays toward zero
- The transition from OTM to ATM can cause gamma to 10x in minutes

**Implication:** The gamma cap becomes increasingly important in the final 2-3 hours. The system should:

1. Log gamma every heartbeat for trend monitoring
2. If wind-down is active AND gamma is above soft limit, **prioritize gamma reduction** — close highest-gamma positions first (typically the ones closest to ATM)
3. Near expiry (< 30 min), if gamma exceeds hard limit, treat as emergency regardless of dollar amount

### B.4 Integration Points

#### B.4.1 With Adjustment Engine (`mmm_engine.py`)

Before executing any sell order in `calculate_adjustment()`:

1. Compute **projected** portfolio gamma if the new position were added
2. If projected gamma > `gamma_hard_limit` → block the adjustment, return `GAMMA_BLOCKED`
3. If projected gamma > `gamma_soft_limit` → allow but add warning to adjustment log

**Projection formula:**
$$\Gamma_{projected} = \Gamma_{current} + \gamma_{new\_strike} \times lots_{new} \times LOT\_SIZE\_BTC$$

Where $\gamma_{new\_strike}$ is fetched from the ticker for the target strike.

#### B.4.2 With Strike Shift Logic (`mmm_strike_shift.py`)

When finding a new strike during a shift, **prefer strikes with lower gamma** if multiple candidates have similar premiums. Add gamma as a secondary sort criterion after premium proximity.

#### B.4.3 With Margin Guardian

If gamma emergency is triggered simultaneously with margin pressure:
- Gamma emergency takes **priority** for position selection (close highest-gamma positions first)
- Margin guardian's lot-count reduction may not reduce gamma optimally — gamma-aware reduction is better

### B.5 State Variables

```
session['_portfolio_gamma'] = float          # Updated every heartbeat
session['_portfolio_dollar_gamma'] = float   # $Γ
session['_gamma_regime'] = 'NORMAL' | 'SOFT' | 'HARD' | 'EMERGENCY'
session['_gamma_history'] = [(timestamp, dollar_gamma), ...]  # ring buffer, max 60
session['_gamma_blocked_count'] = 0          # Times adjustment was blocked by gamma
```

### B.6 Performance Considerations

**Calculation frequency:** Every heartbeat (same as premium fetch).

**Cost:** The gamma data comes from the **same** `/v2/tickers/{symbol}` API call already made for premium and mark_price. The `greeks.gamma` field is in the response but currently discarded by the heartbeat (only used in the on-demand `greeks-iv` endpoint). The change is to **also store gamma during premium fetch** — zero extra API calls.

**Computation:** Simple sum across all positions. Typically 2-10 positions, so < 1ms.

**Gamma staleness:** If the ticker API returns stale Greeks (detected by mark_price unchanged for 3+ beats, already tracked by stale-price detection), skip gamma check and log a warning. Do NOT block adjustments on stale gamma — that would create false safety triggers.

---

## SECTION C — TREND DETECTION GUARD

### C.1 Detection Method

Use a **two-signal confirmation** approach:

#### C.1.1 Signal 1: Percentage Move from Session Anchor

$$move\% = \frac{S_{now} - S_{anchor}}{S_{anchor}} \times 100$$

Where $S_{anchor}$ = spot price when the session was started (or last reset).

This is the simplest, most robust signal. No lagging indicators.

#### C.1.2 Signal 2: Maximum Adverse Excursion without Retracement

Track the highest high and lowest low since the last "calm" point:

$$max\_rally = \frac{S_{high} - S_{calm\_low}}{S_{calm\_low}} \times 100$$
$$max\_drop = \frac{S_{calm\_high} - S_{low}}{S_{calm\_high}} \times 100$$

Where:
- $S_{high}$ = highest spot seen since last calm reset
- $S_{low}$ = lowest spot seen since last calm reset
- "Calm point" resets when spot retraces at least `trend_retrace_pct` (default: 30%) of the move

**"No retracement" definition:**
A move is considered "unidirectional" if the maximum pullback from the move's extreme is less than `trend_retrace_pct`. For example, if BTC moved from $98K to $100K (+2.04%), and the maximum pullback from $100K was only $99.85K (0.15%), the retracement ratio is $0.15K / $2K = 7.5%$ — well below the 30% threshold. The trend is confirmed.

#### C.1.3 Signal 3 (Optional, lightweight): EMA Slope

$$EMA_{slope} = \frac{EMA_{now} - EMA_{prev}}{S_{spot}} \times 10000$$

Using a 10-beat EMA (~5-10 minutes at adaptive interval). This catches sustained drift that hasn't triggered the % move threshold yet.

Slope interpretation:
- $|slope| > 20$ → strong trend (BTC moved ~0.2% per beat on average)
- $|slope| > 40$ → very strong trend

### C.2 Default Thresholds for BTC 0DTE

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `trend_enabled` | True | Master switch |
| `trend_move_pct` | 1.5 | 1.5% move from anchor triggers guard (BTC ~$1,500 at $100K) |
| `trend_retrace_pct` | 30 | Retracement must be >30% of move to reset |
| `trend_ema_period` | 10 | 10-beat EMA (5-10 min at adaptive interval) |
| `trend_ema_slope_threshold` | 25 | EMA slope threshold for trend confirmation |
| `trend_action` | `block_sells` | Action: `block_sells`, `pause`, `wind_down` |
| `trend_reset_beats` | 5 | Must stay calm for 5 beats to reset to NORMAL |

**Why 1.5%?** For BTC 0DTE:
- At $100K, 1.5% = $1,500 — this is roughly a 1σ move for an 8-hour session with 60% annualized vol
- Below this threshold, normal adjustments handle the move
- Above this threshold, the adjustment engine starts fighting a trend — the danger zone

### C.3 State Flags

```
session['_trend_regime'] = 'NORMAL' | 'TREND_UP' | 'TREND_DOWN'
session['_trend_since'] = ISO timestamp
session['_trend_anchor_spot'] = float        # Spot at session start or last reset
session['_trend_high'] = float               # Highest spot since last calm reset
session['_trend_low'] = float                # Lowest spot since last calm reset  
session['_trend_calm_beats'] = 0             # Counter for reset cooldown
session['_trend_ema'] = float                # Current EMA value
session['_trend_ema_prev'] = float           # Previous EMA for slope
```

### C.4 Behavior When Triggered

| State | Behavior |
|-------|----------|
| `TREND_UP` | Block CE adjustment sells (adding short calls into a rally is suicidal). Allow PE adjustments (puts benefit from rally = stop moving against us). Allow all risk-reducing trades (close-at-5, wind-down). |
| `TREND_DOWN` | Block PE adjustment sells (adding short puts into a crash = suicidal). Allow CE adjustments (calls benefit from drop). Allow all risk-reducing trades. |

This is **directional blocking** — the key insight. A trend only makes one side dangerous. The opposite side is actually improving. This is much smarter than blocking everything.

If `trend_action` = `wind_down`: in addition to blocking the dangerous-side sells, also activate wind-down mode to start reducing the dangerous side.

### C.5 Reset Conditions

The trend guard resets to NORMAL when **all** of:
1. Spot has retraced at least `trend_retrace_pct` of the move (meaning the trend has stalled)
2. EMA slope has dropped below the threshold
3. Both conditions sustained for `trend_reset_beats` consecutive beats

On reset:
- $S_{anchor}$ updated to current spot
- $S_{high}$ and $S_{low}$ reset to current spot
- Calm counter reset to 0

---

## SECTION D — INTEGRATION WITH MMM

### D.1 Heartbeat Order (Updated)

```
1. Fetch premiums (CE, PE)           ← existing
2. Stale price detection             ← existing
3. Wind-down status logging          ← existing
4. Prefetch all premiums             ← existing
5. ATM checks (wind-down + close)    ← existing
6. Close-at-5 scan                   ← existing (always runs — risk-reducing)
7. Proactive wind-down buyback       ← existing (always runs — risk-reducing)
8. Compute fresh unrealized P&L      ← existing
9. Safety checks (§13-14)            ← existing
────────────────── NEW ──────────────────
10. Volatility Regime Check          ★ NEW — read IV from ticker, compute RV from spot history
11. Portfolio Gamma Cap Check        ★ NEW — read gamma from ticker, compute $Γ
12. Trend Detection Guard            ★ NEW — compute move%, EMA slope, retracement
────────────────────────────────────────
13. Trigger evaluation               ← existing (may be skipped by regime checks)
14. Adjustment execution             ← existing (may be blocked by regime checks)
```

**Why after safety, before triggers?** 
- Safety checks (max_loss, position_cap, etc.) are hard stops that must always fire first
- Regime checks are "soft intelligence" that modify the trigger/adjustment behavior
- If safety says STOP, regime checks are irrelevant
- If safety says CONTINUE, regime checks decide WHETHER to allow the adjustment

### D.2 Priority Between Controls

When multiple controls fire simultaneously:

```
Priority 1: Safety hard stops (max_loss, margin_critical)     → close all, stop
Priority 2: Gamma emergency                                    → force reduction
Priority 3: Vol regime HIGH + Trend detected                   → block sells, possible wind-down
Priority 4: Gamma hard limit                                   → block sells
Priority 5: Vol regime ELEVATED or Trend alone                 → block dangerous-side sells
Priority 6: Gamma soft limit                                   → warn only
```

### D.3 Conflict Resolution

| Scenario | Resolution |
|----------|-----------|
| Vol HIGH + Trend UP | Block ALL sells (vol overrides trend's directional logic). Wind-down both sides. |
| Vol HIGH + Gamma Emergency | Gamma emergency takes priority for *what to close*. Vol HIGH ensures no new sells. |
| Trend UP + Gamma Hard | Block CE sells (trend) + block all sells (gamma) = block all sells. |
| Vol ELEVATED + Gamma Soft | Block new sells (vol) + warn (gamma). Conservative approach wins. |
| Wind-down active + any regime block | Wind-down buybacks always proceed. Regime blocks only affect NEW sells. |

**Rule:** When controls conflict, **the more conservative action wins**. Risk reduction is always allowed.

### D.4 Aggregate Regime Computation

Each heartbeat produces a single `_regime_action` flag consumed by the trigger/adjustment logic:

```
session['_regime_action'] = 'NORMAL'          # All clear
                          | 'WARN'            # Soft limits — adjustments allowed, logging enhanced
                          | 'BLOCK_CE_SELLS'  # Trend DOWN or directional gamma risk
                          | 'BLOCK_PE_SELLS'  # Trend UP or directional gamma risk  
                          | 'BLOCK_ALL_SELLS' # Vol HIGH, gamma hard, or combined
                          | 'FORCE_REDUCE'    # Gamma emergency — close positions
                          | 'STOP'            # Handled by safety, listed for completeness
```

The adjustment engine checks `_regime_action` before executing any sell. If blocked, it logs the reason and skips the sell.

### D.5 Required Changes

#### D.5.1 Session State Model (`mmm_state.py`)

Add state variables listed in A.4, B.5, C.3 to the session dict. These are **runtime state** (not persisted in DEFAULT_PARAMS, but stored in the session JSON for crash recovery).

Add parameters from A.3, B.2, C.2 to `DEFAULT_PARAMS` and `HOT_RELOAD_PARAMS` and `PARAM_RULES` in `mmm_config.py`.

#### D.5.2 New Backend Module

Create `mmm_regime.py` (~400-500 lines) containing:
- `class MMMRegimeEngine`
  - `update_vol_regime(session, iv_data, spot_price)` → updates state, returns regime
  - `update_gamma_cap(session, gamma_data, spot_price)` → updates state, returns regime
  - `update_trend_guard(session, spot_price)` → updates state, returns regime
  - `compute_regime_action(session)` → aggregates all three into `_regime_action`
  - `get_regime_status(session)` → returns full status dict for WebSocket/API

This module does **no I/O** — it receives data and returns decisions. The monitor heartbeat calls it.

#### D.5.3 WebSocket Events

New event: `mmm_regime`

```python
emit('mmm_regime', {
    'session_id': sid,
    'vol_regime': 'NORMAL' | 'ELEVATED' | 'HIGH',
    'gamma_regime': 'NORMAL' | 'SOFT' | 'HARD' | 'EMERGENCY',  
    'trend_regime': 'NORMAL' | 'TREND_UP' | 'TREND_DOWN',
    'regime_action': 'NORMAL' | 'WARN' | 'BLOCK_*' | 'FORCE_REDUCE',
    'details': {
        'iv_change_pct': float,
        'rv_annualized': float,
        'dollar_gamma': float,
        'spot_move_pct': float,
        'ema_slope': float,
    }
})
```

Emitted every heartbeat (included in heartbeat data, not a separate event — avoids extra socket traffic).

#### D.5.4 REST API

New endpoint: `GET /api/mmm/session/<id>/regime`

Returns full regime status for the session including all three control states, history arrays (last 20 data points), current action, and when each regime was last triggered.

#### D.5.5 WebUI Indicators

Add a **Regime Status Bar** to the MMMDashboard, similar to the existing status banner:

| Regime | Color | Icon | Text |
|--------|-------|------|------|
| All NORMAL | Green | 🟢 | "Regime: Normal — all controls clear" |
| Any ELEVATED/SOFT | Yellow | 🟡 | "Regime: Elevated — [vol/gamma/trend details]" |
| Any HIGH/HARD/TREND | Orange | 🟠 | "Regime: Restricted — [sells blocked/details]" |
| EMERGENCY/FORCE_REDUCE | Red | 🔴 | "Regime: Emergency — reducing positions" |

Add to MMMSettingsDialog: New section **"Regime Controls"** with all parameters from A.3, B.2, C.2.

---

## SECTION E — FAILURE MODES & EDGE CASES

### E.1 Flash Crash

**Scenario:** BTC drops 5% in 60 seconds.

**What fires:**
1. Trend guard → TREND_DOWN (within 1-2 beats)
2. Vol regime → HIGH (RV spikes, IV spikes)
3. Gamma cap → may hit hard/emergency (puts go ATM)
4. Existing safety: max_loss may trigger, ATM wind-down may fire

**Resolution:** The regime controls will block PE sells within 1-2 beats. If it's bad enough, gamma emergency forces buybacks. Meanwhile, close-at-5 continues harvesting profitable CE positions. The existing max_loss hard stop remains the ultimate safety net.

**Key:** No regime control should DELAY the max_loss hard stop. Safety hard stops always execute first.

### E.2 IV Spike + Trend Together

**Scenario:** CPI announcement causes BTC to rally 2% while IV spikes 50%.

**What fires:**
1. Trend → TREND_UP (blocks CE sells)
2. Vol → HIGH (blocks all sells)
3. Combined: all sells blocked

**Correct behavior:** This is the safest response. The algo waits. When vol drops and trend stalls, controls progressively release — first trend may clear (directional blocking), then vol clears (full blocking). Recovery is gradual, not sudden.

### E.3 Both-Sides-Up During High Volatility

**Scenario:** Both CE and PE premiums exceed triggers while vol regime is HIGH.

**Current behavior:** Pause, show both-sides-up modal, wait for user decision.

**New behavior:** The both-sides-up check happens in trigger evaluation (step 13). If vol regime is HIGH, trigger evaluation is skipped entirely — so both-sides-up never fires. This is correct: in high vol, we don't want ANY sells.

If vol is only ELEVATED and one-side adjustment would be blocked by trend, the trigger evaluation runs but the adjustment is blocked. Both-sides-up logic still needs to check regime action before presenting options to user.

### E.4 Missing Greeks Data

**Scenario:** Delta Exchange ticker returns `null` for gamma on some positions.

**Handling:**
- If gamma is null for **any** position, set `_gamma_data_incomplete = True`
- Use last known gamma for that position (stale-gamma fallback, max age 5 minutes)
- If no gamma data at all, skip gamma cap check entirely and log warning
- Do NOT block adjustments on missing data — that creates false safety triggers

### E.5 API Lag / Stale Prices

**Scenario:** Ticker API takes 2+ seconds to respond, or returns unchanged data for multiple beats.

**Handling:**
- Stale-price detection (already exists) sets `_stale_price_detected`
- When stale: vol regime uses last known values (no update)
- When stale: gamma cap uses last known values (no update)
- When stale: trend guard uses last known spot (marks it stale)
- None of the regime controls should trigger on stale data — only on confirmed fresh data
- Log: "⚠️ Regime checks using stale data (N beats old)"

### E.6 Session Recovery After Crash

**Scenario:** Backend crashes and restarts mid-session.

**Handling:**
- Regime state is stored in the session JSON via `mmm_storage.py` (same as all other session state)
- On reload, restore `_vol_regime`, `_gamma_regime`, `_trend_regime` from saved state
- History buffers (`_vol_iv_history`, `_vol_spot_history`, `_gamma_history`) are restored if present
- If buffers are empty after crash, regime starts as NORMAL and refills over the first `N` beats
- This is acceptable: the first few beats after crash are "warm-up" — better to be permissive than overly restrictive

### E.7 Parameter Hot-Reload Interaction

**Scenario:** User changes `trend_move_pct` from 1.5 to 3.0 while TREND_UP is active.

**Handling:** The new threshold is applied on the very next heartbeat. If the current move (e.g., 2%) is now below the new threshold (3%), the regime immediately transitions to NORMAL. This is the intended behavior — the user is explicitly saying they're comfortable with larger moves.

---

## SECTION F — PARAMETER DESIGN

### F.1 Volatility Regime Filter Parameters

| Parameter | Default | Range | Hot-Reload | Description |
|-----------|---------|-------|------------|-------------|
| `vol_regime_enabled` | True | bool | **Yes** | Master switch for vol regime filter |
| `vol_iv_spike_pct` | 30 | 5 – 200 | **Yes** | IV change % threshold to trigger ELEVATED/HIGH |
| `vol_rv_threshold` | 80 | 20 – 300 | **Yes** | Annualized RV % threshold |
| `vol_lookback_beats` | 5 | 2 – 30 | **Yes** | Beats for IV rate calculation |
| `vol_rv_window` | 20 | 5 – 60 | **Yes** | Beats for RV window |
| `vol_regime_action` | `block_sells` | str | **Yes** | Action: block_sells / pause / wind_down |
| `vol_regime_cooldown_beats` | 10 | 3 – 60 | **Yes** | Beats below threshold before NORMAL |

### F.2 Portfolio Gamma Cap Parameters

| Parameter | Default | Range | Hot-Reload | Description |
|-----------|---------|-------|------------|-------------|
| `gamma_cap_enabled` | True | bool | **Yes** | Master switch for gamma cap |
| `gamma_soft_limit` | 50.0 | 1 – 10000 | **Yes** | Dollar gamma soft limit (warning) |
| `gamma_hard_limit` | 100.0 | 1 – 10000 | **Yes** | Dollar gamma hard limit (block sells) |
| `gamma_emergency_limit` | 200.0 | 1 – 10000 | **Yes** | Dollar gamma emergency (force reduce) |
| `gamma_near_expiry_multiplier` | 0.5 | 0.1 – 1.0 | **Yes** | Reduce limits by this factor in last 30 min (tighter control when gamma explodes) |

### F.3 Trend Detection Parameters

| Parameter | Default | Range | Hot-Reload | Description |
|-----------|---------|-------|------------|-------------|
| `trend_enabled` | True | bool | **Yes** | Master switch for trend guard |
| `trend_move_pct` | 1.5 | 0.5 – 10 | **Yes** | % move from anchor to trigger |
| `trend_retrace_pct` | 30 | 10 – 80 | **Yes** | % retracement required to reset |
| `trend_ema_period` | 10 | 5 – 50 | **Yes** | EMA period in beats |
| `trend_ema_slope_threshold` | 25 | 5 – 100 | **Yes** | EMA slope threshold |
| `trend_action` | `block_sells` | str | **Yes** | Action: block_sells / pause / wind_down |
| `trend_reset_beats` | 5 | 2 – 30 | **Yes** | Beats calm required before reset |

### F.4 All Parameters Are Hot-Reloadable

All regime parameters are hot-reloadable because:
1. Market conditions change mid-session — user needs to adjust thresholds live
2. No parameter requires structural changes to the session
3. New values take effect on the next heartbeat, which is safe for all cases

---

## SECTION G — TEST PLAN

### G.1 Unit Tests

#### G.1.1 Volatility Regime Filter

| Test | Input | Expected |
|------|-------|----------|
| IV spike detection | IV goes from 60% to 85% (Δ=41.7%) | State → HIGH |
| IV within threshold | IV goes from 60% to 70% (Δ=16.7%) | State → NORMAL |
| RV spike detection | 20 spot samples with 100% annualized RV | State → HIGH (RV-only) |
| Cooldown prevents premature reset | Regime HIGH, IV drops for 3 beats (need 10) | Stays HIGH |
| Cooldown allows reset | Regime HIGH, IV drops for 10 beats | State → NORMAL |
| Missing IV data | IV = null for both strikes | Skip IV, use RV-only |
| Session startup (few samples) | Only 3 spot samples | State → NORMAL (insufficient data) |

#### G.1.2 Portfolio Gamma Cap

| Test | Input | Expected |
|------|-------|----------|
| Below soft limit | $Γ = $30 | State → NORMAL |
| Soft limit breach | $Γ = $60 | State → SOFT, warning logged |
| Hard limit blocks sell | $Γ = $110, adjustment requested | Adjustment blocked |
| Emergency triggers reduction | $Γ = $250 | State → EMERGENCY, wind-down forced |
| Near-expiry multiplier | $Γ = $40, < 30 min to expiry, multiplier 0.5 | Effective hard limit = $50, state → SOFT |
| Missing gamma data | gamma = null for 2/4 positions | Use stale, log warning |
| Projected gamma check | Current $Γ = $80, adding 5 lots would make $Γ = $105 | Block the 5-lot sell |

#### G.1.3 Trend Detection Guard

| Test | Input | Expected |
|------|-------|----------|
| Rally detection | Spot moves +1.8% from anchor | State → TREND_UP |
| Drop detection | Spot moves -2.0% from anchor | State → TREND_DOWN |
| Below threshold | Spot moves +1.0% | State → NORMAL |
| Retracement resets | Spot +2%, then retraces 40% of move | State → NORMAL (>30% retrace) |
| No retracement, no reset | Spot +2%, only 10% retrace | Stays TREND_UP |
| Directional blocking (up) | TREND_UP active, CE adjustment requested | CE adjustment blocked, PE allowed |
| Directional blocking (down) | TREND_DOWN active, PE adjustment requested | PE adjustment blocked, CE allowed |
| Reset needs sustained calm | Retrace > 30%, but only 2 beats calm (need 5) | Stays in TREND state |
| EMA slope confirmation | Spot barely crosses % threshold, EMA slope < 25 | State → NORMAL (need both signals for HIGH) |

#### G.1.4 Integration Tests

| Test | Setup | Expected |
|------|-------|----------|
| Safety overrides regime | max_loss breach + vol HIGH | Safety closes all (priority 1) |
| Regime blocks before trigger | vol HIGH | Trigger evaluation skipped |
| Wind-down allowed under regime | vol HIGH + wind-down active | Wind-down buybacks proceed |
| Close-at-5 immune to regime | gamma HARD + positions at premium 3 | Close-at-5 fires normally |
| Multiple regimes combined | vol ELEVATED + TREND_UP + gamma SOFT | Action = BLOCK_CE_SELLS (most conservative) |
| Both-sides-up under regime | vol HIGH, both triggers would fire | Neither fires — vol blocks evaluation |

### G.2 Simulation Scenarios

#### Scenario 1: Trend Day (Sustained Rally)
- BTC rallies from $100K to $103K over 4 hours (+3%)
- Expected: Trend guard fires at ~+1.5%. CE sells blocked. PE adjustments (if triggered) still allowed. Close-at-5 harvests profitable PEs. Result: significantly lower loss than current system.

#### Scenario 2: Volatility Spike (CPI-style)
- IV jumps from 55% to 90% in 10 minutes. Spot whipsaws ±$1K.
- Expected: Vol regime → HIGH within 2-3 beats. All sells blocked. Both-sides-up never fires. System sits on hands until vol subsides. Result: avoids selling cheap premium into a spike.

#### Scenario 3: Mean Reversion Day (Choppy Range)
- BTC oscillates between $99.5K and $100.5K. Normal adjustments.
- Expected: No regime triggers. All controls stay NORMAL. System behaves exactly as current production. Result: no degradation in normal conditions.

#### Scenario 4: Flash Crash
- BTC drops 5% in 2 minutes.
- Expected: Trend → TREND_DOWN instantly. Vol → HIGH within 1-2 beats. Gamma may hit emergency if puts go deep ATM. Max_loss likely triggers. System closes all within 2 beats. Result: faster than current system (which would try to sell more CEs into the crash).

#### Scenario 5: Slow Grind (Overnight Drift)
- BTC drifts 0.8% over 3 hours.
- Expected: Below trend threshold (1.5%). All controls NORMAL. Normal adjustments. Result: unchanged behavior.

### G.3 Metrics to Evaluate Improvement

| Metric | How to Measure | Target |
|--------|---------------|--------|
| **Max drawdown reduction** | Compare max unrealized loss with vs without regime controls (backtest) | ≥ 30% reduction |
| **Adjustment count on trend days** | Count sells made during trend days with/without controls | ≥ 50% fewer sells on trend days |
| **False trigger rate** | % of regime activations that were unnecessary (spot reverted within 2 beats) | < 15% |
| **P&L impact on normal days** | Compare profits on mean-reversion days with controls vs without | < 5% degradation (should be ~0%) |
| **Time-to-detection** | Beats from event start to regime activation | ≤ 2 beats for trend, ≤ 3 for vol |
| **Recovery time** | Beats from event end to NORMAL restoration | ≤ cooldown parameter (no artificial delays) |

---

## Appendix: Implementation Order

Recommended phased rollout:

| Phase | What | Effort | Risk |
|-------|------|--------|------|
| **Phase 1** | Trend Detection Guard | ~300 lines backend + ~100 lines frontend | Lowest — uses only spot price, already fetched |
| **Phase 2** | Volatility Regime Filter | ~350 lines backend + ~100 lines frontend | Medium — needs IV from ticker (already available but not stored) |
| **Phase 3** | Portfolio Gamma Cap | ~250 lines backend + ~50 lines frontend | Highest — needs gamma from ticker, projection logic for pre-trade check |
| **Phase 4** | Integration, conflict resolution, WebUI regime bar | ~200 lines backend + ~200 lines frontend | Low — aggregation logic |

Phase 1 alone delivers the most impactful improvement: blocking sells into a trend. This is where the current system loses the most money.
