# Phase 1 — Task 5: Stale-Detection Feasibility

**Status**: Complete
**Date**: 2026-04-27
**Auditor**: Claude
**Scope**: Identify which arbiter-consumed signals already have timestamps, which don't, and what pattern to use for stale detection per Rule 6.

Rule 6 (Phase 2): "Stale data is dangerous — escalate one tier when a signal is older than the current beat."

---

## TL;DR

Inventory of signals the arbiter will consume:

| Signal | Has timestamp today? | Action needed |
|---|---|---|
| `_breakeven_zone` | ✅ Yes (`_breakeven_result.computed_at`) | Use existing field |
| `_breakeven_result` | ✅ Yes (`computed_at` inside dict) | Use existing field |
| `_gamma_regime` | ⚠️ Partial (`_gamma_regime_since` is transition-only, not refresh) | Add `_gamma_last_updated_at` |
| `_portfolio_dollar_gamma` | ❌ No | Add via shared timestamp |
| `_vol_regime` | ⚠️ Partial (`_vol_regime_since` is transition-only) | Add `_vol_last_updated_at` |
| `_trend_regime` | ❌ No | Add `_trend_last_updated_at` |
| `_regime_action` | ❌ No | Add `_regime_last_updated_at` |
| `_margin_tier` | ❌ No | Add `_margin_last_updated_at` |
| `_smart_ws_loss_velocity` | ❌ No | Add (computed in monitor at line 2557) |
| `_smart_ws_score` | ❌ No (smart whipsaw writes `_smart_ws_last_decision.ts`) | Use existing nested ts |
| `_smart_ws_mode` | ❌ Same as above | Use existing nested ts |

**5 new explicit timestamp writes needed** — minimal change. Centralize via helper function in `mmm_state.py`. Phase 3 task, ~20 lines + 1 sealed test.

---

## 1. The two timestamp patterns observed in the codebase

### Pattern A — "Since" (transition timestamp)

Used by gamma and vol engines:

```python
# mmm_gamma.py:299-300
if new_regime != current_regime:
    session['_gamma_regime_since'] = now  # only written on transition

# mmm_regime.py:224
session['_vol_regime_since'] = now
```

**Problem for Rule 6**: this records "when did the regime last change," not "when was the regime last refreshed." If the engine fails to run for 5 beats but the regime stayed the same, `_gamma_regime_since` is unchanged from beat 1. The arbiter cannot detect staleness from this field.

### Pattern B — "Computed at" (refresh timestamp)

Used by breakeven engine:

```python
# mmm_breakeven_engine.py:627
return {
    'zone': zone,
    'multiplier': round(multiplier, 4),
    ...
    'computed_at': datetime.now(timezone.utc).isoformat(),
}
```

**Correct for Rule 6**: this is written every time the engine produces a result, regardless of whether the value changed. Arbiter can detect staleness by comparing to current beat time.

---

## 2. The missing timestamps

For each arbiter-consumed signal, here's where it's written today and what to add:

### 2.1 `_gamma_regime` and `_portfolio_dollar_gamma`

**Current**: `_update_gamma_cap` runs in [mmm_monitor.py:1418-1444](../../../webui/backend/routes/mmm/mmm_monitor.py#L1418-L1444) (called from `_compute_fill_timeout`?) — let me re-verify. Actually computed every beat at Step 5.8 via `gd.compute_gamma()`, then the regime is set inside `_update_gamma_cap` ([mmm_gamma.py:309](../../../webui/backend/routes/mmm/mmm_gamma.py#L309)).

**Add**: at the END of `_update_gamma_cap`, write:
```python
session['_gamma_last_updated_at'] = now  # already computed at line 191
```

### 2.2 `_vol_regime` and `_trend_regime`

**Current**: written by regime computation in `mmm_regime.py`. The "since" field exists but is transition-only.

**Add**: at end of vol/trend update functions:
```python
session['_vol_last_updated_at'] = now
session['_trend_last_updated_at'] = now
```

### 2.3 `_regime_action`

**Current**: written multiple places in [mmm_monitor.py:2816-3017](../../../webui/backend/routes/mmm/mmm_monitor.py#L2816-L3017) — at least 4 different code paths set it.

**Add**: a single helper at the end of the regime block:
```python
record_signal_update(session, 'regime_action')
```

### 2.4 `_margin_tier`

**Current**: written by `_check_margin_guardian` (line 1638). Stored in `_last_margin_snapshot` with no timestamp on the tier itself.

**Add**: timestamp the tier write:
```python
session['_margin_last_updated_at'] = now
```

### 2.5 `_smart_ws_loss_velocity`

**Current**: written at [mmm_monitor.py:2557](../../../webui/backend/routes/mmm/mmm_monitor.py#L2557) every beat unconditionally. So it's actually fresh by construction every beat — but no timestamp to confirm.

**Add**: same pattern, one line.

### 2.6 `_smart_ws_score` / `_smart_ws_mode`

**Current**: smart whipsaw writes `_smart_ws_last_decision` dict ([mmm_whipsaw_smart.py:748-762](../../../webui/backend/routes/mmm/mmm_whipsaw_smart.py#L748-L762)) which contains a `'ts'` field. So timestamp IS available, but it's nested.

**Action**: use `session.get('_smart_ws_last_decision', {}).get('ts')` for staleness check. No new write needed — just teach arbiter to read the nested ts.

---

## 3. Proposed Phase 3 implementation pattern

### 3.1 Helper function in `mmm_state.py`

```python
from datetime import datetime, timezone

def record_signal_update(session: dict, signal_name: str) -> None:
    """Mark a signal as freshly computed this beat.
    
    Phase 3 stale-detection: arbiter checks `_<signal>_last_updated_at`
    against current beat time. Stale signals are escalated one tier per Rule 6.
    """
    session[f'_{signal_name}_last_updated_at'] = datetime.now(timezone.utc).isoformat()


def is_signal_fresh(
    session: dict,
    signal_name: str,
    max_age_seconds: float,
) -> bool:
    """Return True if signal was updated within max_age_seconds.
    
    Reads `_<signal>_last_updated_at`. Returns False if missing (treat as stale).
    """
    ts_str = session.get(f'_{signal_name}_last_updated_at')
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
        return age_sec <= max_age_seconds
    except (ValueError, TypeError):
        return False
```

### 3.2 Arbiter usage

```python
# In arbiter Tier 1 evaluation:
beat_interval = float(session.get('params', {}).get('adjustment_interval', 300))
max_age = beat_interval * 1.5  # allow 1.5 beats grace

stale_signals = []
for sig in ('breakeven_zone', 'gamma', 'margin', 'vol', 'trend'):
    if not is_signal_fresh(session, sig, max_age):
        stale_signals.append(sig)

if stale_signals:
    log_stale_event(session, stale_signals)
    # Per Rule 6: escalate severity for arbiter purposes
    if 'breakeven_zone' in stale_signals and current_zone == 'WARNING':
        effective_zone = 'DANGER'  # escalate one tier
    # ... similar for other signals
```

### 3.3 Special handling for breakeven (already has timestamp)

The breakeven engine writes `computed_at` inside `_breakeven_result`. The arbiter can read this without any new infrastructure:

```python
be_result = session.get('_breakeven_result', {})
be_computed_at = be_result.get('computed_at')
# parse and check age
```

Either approach works. For consistency, Phase 3 can ALSO write `_breakeven_last_updated_at` so all arbiter signals follow the same pattern. Marginal cost — one line.

---

## 4. Where to insert the timestamp writes

| Signal | File | Line (approx) | Insert |
|---|---|---|---|
| breakeven_zone | mmm_monitor.py | 3298 (after `_breakeven_zone` write) | `record_signal_update(session, 'breakeven_zone')` |
| gamma | mmm_gamma.py | end of `_update_gamma_cap` (~314) | `record_signal_update(session, 'gamma')` |
| portfolio_dollar_gamma | (same as gamma) | shared timestamp | covered by gamma signal |
| vol | mmm_regime.py | end of vol regime update function | `record_signal_update(session, 'vol')` |
| trend | mmm_regime.py | end of trend regime update function | `record_signal_update(session, 'trend')` |
| regime_action | mmm_monitor.py | end of Step 3.5 (~3017) | `record_signal_update(session, 'regime_action')` |
| margin | mmm_monitor.py | end of margin guardian (~1689) | `record_signal_update(session, 'margin')` |
| smart_ws | mmm_whipsaw_smart.py | already has nested `_smart_ws_last_decision.ts` | (no change; arbiter reads nested) |
| loss_velocity | mmm_monitor.py | 2558 (after `_smart_ws_pnl_prev` write) | `record_signal_update(session, 'loss_velocity')` |

**Total**: 7 single-line insertions. No logic changes. Pure instrumentation.

---

## 5. Edge cases the arbiter must handle

### 5.1 Engine never ran (signal missing entirely)

Example: `gamma_cap_enabled = False` → `_gamma_regime` may not be set, `_gamma_last_updated_at` missing. Arbiter sees missing timestamp → treats as stale → escalates.

But escalating from "missing" to a higher tier is incorrect — the engine is intentionally disabled.

**Fix**: arbiter should check the enabled flag before requiring a timestamp. If `gamma_cap_enabled = False`, the arbiter does not consume gamma signal at all.

### 5.2 First beat after session start

Engine has not run yet → no timestamp. Arbiter sees stale on first beat.

**Fix**: arbiter requires N beats of warmup. During warmup, arbiter is no-op (Tier 2 rule applies). After warmup, missing timestamp = stale.

### 5.3 Engine error (try/except swallowed)

Several engines wrap their compute in `try/except`:
```python
try:
    gd_result = gd.compute_gamma(...)
    session['_gamma_result'] = gd_result
except Exception as e:
    log.warning(...)
```

If exception fires, no timestamp is written, and `_gamma_result` stays from prior beat. Stale detection will catch this — exactly the intended behaviour.

### 5.4 Heartbeat skipped (paused, kill-switch, etc.)

If heartbeat doesn't run, no timestamps update. When heartbeat resumes, all signals appear stale until each engine runs once. Arbiter behaviour: no-op for those beats (Rule 6 escalation only triggers if Tier 1 conditions fire, which would require fresh signals).

In practice: not a problem — the arbiter is gated on Tier 1 firing, and Tier 1 fires require fresh signals to evaluate the trigger condition itself.

---

## 6. Rule 6 escalation semantics

Per Phase 2 / G1:
> "Escalate the signal's severity to the next-higher tier (e.g., stale `_breakeven_zone='WARNING'` → treated as DANGER for arbiter purposes only; module's own state untouched)"

Implementation:

```python
def get_effective_breakeven_zone(session, beat_interval_sec):
    raw_zone = session.get('_breakeven_zone', 'SAFE')
    if not is_signal_fresh(session, 'breakeven_zone', beat_interval_sec * 1.5):
        # Escalate one tier
        escalation = {'SAFE': 'WARNING', 'WARNING': 'DANGER', 'DANGER': 'CRITICAL', 'CRITICAL': 'CRITICAL'}
        return escalation.get(raw_zone, raw_zone)
    return raw_zone
```

Same pattern for gamma (NORMAL → SOFT → HARD → EMERGENCY) and margin (GREEN → YELLOW → ORANGE → RED → CRITICAL).

The escalation is **for arbiter decision purposes only** — does not write back to session. The next beat the engine runs, the real value is restored.

---

## 7. Audit trail

Per Rule 7 (audit everything the arbiter changes), stale escalations must be logged:

```python
audit_entry['stale_signals'] = [
    {'signal': 'breakeven_zone', 'last_updated': '2026-04-27T...',
     'age_seconds': 612, 'raw_value': 'WARNING', 'effective_value': 'DANGER'},
]
```

Goes into the structured JSON audit trail per Rule 7. Operator can review which beat decisions were made under stale data.

---

## 8. Phase 3 Candidate List (additions)

- **C21**: Add `record_signal_update()` and `is_signal_fresh()` helpers in `mmm_state.py` (~30 lines).
- **C22**: Insert 7 single-line timestamp writes (per §4 table).
- **C23**: Add `get_effective_<signal>()` accessors in arbiter module that handle escalation per Rule 6.
- **C24**: Add `stale_signals` array to arbiter audit trail JSON.
- **C25**: Add sealed test `test_arbiter_escalates_stale_breakeven_zone` — given `_breakeven_zone='WARNING'` with age > 1.5 beats, arbiter treats as DANGER.
- **C26**: Add sealed test `test_arbiter_skip_when_first_beat_warmup` — given session age < 2 beats, arbiter is no-op even if signals look stale.

---

## 9. Verdict

Stale detection is **trivial to add**. The infrastructure is partially in place (breakeven already has the right pattern). Cost: 30-line helper + 7 one-liners + 2 sealed tests + 1 audit-trail addition.

The bigger Phase 3 win: the same helper is reusable for **any** future signal the arbiter needs to consume. Designing it well now = lasting value.

No engine redesign. No new dependencies. No timing changes. Just consistent timestamps.
