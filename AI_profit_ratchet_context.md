# Profit Ratchet — AI Context & Debug Guide

**Implemented**: 2026-04-28  
**Feature status**: OFF by default, hot-reloadable via WebUI

---

## What It Does (One Paragraph)

At each cumulative-P&L milestone (every `profit_ratchet_step_usd` dollars, e.g. $5→$10→$15...) the heartbeat calls `update_trigger_snapshots(session, ce_now, pe_now)` to re-anchor CE and PE trigger snapshots to current premium levels. Without this, a profitable session's triggers stay anchored at entry-level premiums — so after premiums have decayed to half their entry value, the market must reverse **all the way back past the entry premium** before an adjustment fires. With the ratchet, only a fresh move of `min_trigger_move`% above the **current** (decayed) premium is needed. The algo stays responsive to reversals as profit grows.

---

## Core Invariants

1. **HWM guard**: ratchet only fires on new profit highs. `_profit_ratchet_hwm` stores the highest milestone crossed. If P&L is $8 and HWM is $10 (drawdown), no ratchet fires. Next ratchet only fires at $15 (next step above $10).
2. **No time-based cooldown**: the dollar step is the natural cooldown. Earning $5→$10 takes real market time; ratchet cannot fire during a volatility spike (spikes reduce P&L, not increase it to a new milestone).
3. **No financial accounting change**: `realized_pnl`, `unrealized_pnl`, `total_fees`, `peak_pnl`, `max_loss` — all untouched. Ratchet is purely a trigger-snapshot sensitivity adjustment.
4. **Operator pin respected**: ratchet calls `update_trigger_snapshots()` which already respects `_trigger_pinned` flag. If operator has pinned a trigger, the ratchet honors it.
5. **Whipsaw guard active**: all whipsaw logic runs unchanged between milestones.
6. **All stale-monitor guards intact**: three-layer stale-monitor fix (CLAUDE.md §4) and all reverse mode invariants (CLAUDE.md §5) are untouched.

---

## File Map

| File | What changed |
|---|---|
| `webui/backend/routes/mmm/mmm_monitor.py` | Ratchet block inserted before `evaluate_triggers()` in `_heartbeat()`. Grep: `profit_ratchet_enabled`. |
| `webui/backend/routes/mmm/mmm_state.py` | 2 params added to `DEFAULT_PARAMS` and `HOT_RELOAD_PARAMS`. |
| `webui/backend/routes/mmm/mmm_config.py` | 2 params added to `PARAM_RULES` + descriptions. |
| `webui/backend/routes/mmm/mmm_activity.py` | `'profit_ratchet': 'Profit Ratchet'` added to `ACTIVITY_TYPES`. |
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | New `profitRatchet` section in `PARAM_GROUPS` (after `arbiter`, before `reverseMode`). |
| `webui/backend/routes/mmm/tests/test_sealed_audit_fixes.py` | 14 new sealed tests in 5 classes. |

---

## Session State Fields

| Field | Type | Meaning |
|---|---|---|
| `_profit_ratchet_hwm` | float | Highest milestone crossed so far (e.g. 15.0). Initialized to 0 on first beat. |
| `_profit_ratchet_count` | int | How many times ratchet fired this session. |
| `_profit_ratchet_last_pnl` | float | P&L at the time of the last ratchet (for operator reference in logs). |

---

## Config Params

| Param | Default | Range | Hot-reload |
|---|---|---|---|
| `profit_ratchet_enabled` | `False` | bool | YES |
| `profit_ratchet_step_usd` | `10.0` | 1.0–1000.0 | YES |

---

## Heartbeat Insertion Point

**File**: `mmm_monitor.py`  
**Method**: `_heartbeat()`  
**Location**: Inside `if not _skip_to_pnl:` block, **immediately before** `trigger_result = evaluate_triggers(session, ce_now, pe_now)`

**Why this location**:
- `params` is in scope (defined earlier in `_heartbeat()` at the `session.get('params', {})` call)
- `_pnl_total(session)` returns current P&L from session cache fields (same as safety checks use)
- Re-anchoring BEFORE `evaluate_triggers` means the fresh snapshot is used by the trigger evaluator on the same beat → after a ratchet, `evaluate_triggers` sees excess=0 (no trigger fires the same beat as a ratchet — natural one-beat grace period)
- Next beat: triggers are maximally sensitive to moves above the new anchor

**If `_skip_to_pnl=True`**: ratchet block is skipped (adjustments are blocked anyway — trailing stop, ATM shield, etc.). Since a drawdown causes `_skip_to_pnl`, and during a drawdown P&L is typically below the next milestone, the HWM guard would prevent firing anyway.

---

## The Milestone Math

```python
_pr_new_hwm = int(_pr_pnl / _pr_step) * _pr_step
```

`int()` truncates toward zero for positive numbers (same as `math.floor` for positive P&L). Examples:
- P&L=$5.10, step=$5 → `int(5.10/5)*5 = 1*5 = 5.0`
- P&L=$7.30, step=$5 → `int(7.30/5)*5 = 1*5 = 5.0`
- P&L=$18.0, step=$5 → `int(18.0/5)*5 = 3*5 = 15.0` (jumps three steps at once → one call to `update_trigger_snapshots`, HWM set to $15)

---

## Activity Log Event

Category: `profit_ratchet`  
Severity: `info`

Example message:
```
📈 PROFIT RATCHET #2: milestone $10 (P&L $10.23) — CE 185.00→95.00, PE 190.00→88.00
```

Details dict:
```json
{
  "milestone": 10.0,
  "pnl": 10.23,
  "ratchet_count": 2,
  "ce_before": 185.0,
  "ce_after": 95.0,
  "pe_before": 190.0,
  "pe_after": 88.0
}
```

---

## Sealed Tests (14 total in `test_sealed_audit_fixes.py`)

| Class | Tests | What it verifies |
|---|---|---|
| `TestProfitRatchetParamDefaults` | 3 | `profit_ratchet_enabled=False` by default, step=10.0, both hot-reloadable |
| `TestProfitRatchetFiresAtMilestone` | 3 | Fires at milestone, doesn't fire below, disabled → never fires |
| `TestProfitRatchetHWMGuard` | 2 | No re-fire at crossed milestone, no fire during drawdown |
| `TestProfitRatchetMultiStepJump` | 2 | Multi-step HWM math (`int(pnl/step)*step`) |
| `TestProfitRatchetNegativePnlNeverFires` | 1 | P&L negative → no ratchet |
| `TestProfitRatchetSourcePresence` | 3 | Static source guards: block in mmm_monitor.py exists, appears before evaluate_triggers, activity category registered |

---

## Debugging Guide

### Ratchet not firing when I expect it to

1. Check `profit_ratchet_enabled=True` in session params (WebUI → Settings → Profit Ratchet).
2. Check `profit_ratchet_step_usd` is set (e.g. $5 or $10, not $0).
3. Check `_profit_ratchet_hwm` in session state — is the current P&L less than `hwm + step`? That is the only condition that blocks it.
4. Is `_skip_to_pnl=True` this beat? That means a safety guard (trailing stop, ATM shield) is blocking all adjustments, so the ratchet block is also skipped. Check if trailing stop is active.
5. Is P&L negative? Ratchet will never fire for negative P&L.

### Ratchet firing too often (unexpected re-anchors)

1. The HWM guard prevents firing more than once per milestone. If you see multiple ratchets at the same milestone, check the `_profit_ratchet_hwm` field is being persisted correctly (session save/load).
2. If ratchets are firing at DIFFERENT milestones very rapidly, check if P&L is jumping (large fill confirmed, close-at-5 event). This is correct behavior.
3. Check `_profit_ratchet_count` in logs to see how many ratchets have fired.

### Trigger not more sensitive after ratchet

After a ratchet, `evaluate_triggers` on the same beat sees excess=0 (snapshots just re-anchored to current premiums). On the **next beat**, any premium move above `current_premium * (1 + min_trigger_move/100)` fires. If the trigger still isn't firing, verify `min_trigger_move` is not too high (check `_effective_min_trigger_move` in session).

### CE or PE snapshot not updated after ratchet

`update_trigger_snapshots()` respects `_trigger_pinned`. If the operator pinned a trigger (manual lock), the ratchet will NOT update that side's snapshot until the pin expires (after `_MAX_PIN_ADJ=3` adjustments). This is correct behavior.

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| P&L jumps $2→$18 (step=$5) | One ratchet fires, HWM=15, snapshot reset once to current premiums |
| P&L drops from $10 to $8 | No ratchet (8 < 10 + 5). Normal adjustment logic runs unchanged. |
| P&L recovers from $8 to $13 | Ratchet fires at $15 milestone (next above $10 HWM). Not at $10 (already crossed). |
| Strike shift happens same beat | Strike shift (later in heartbeat) calls `update_trigger_snapshots` again with fill price, which correctly overwrites ratchet's anchor. No conflict. |
| Operator trigger pin active | `update_trigger_snapshots` skips pinned side. Ratchet still records new HWM but pinned snapshot stays. |
| `_skip_to_pnl=True` (trailing stop) | Ratchet block skipped entirely. If P&L is below next milestone anyway (drawdown), HWM guard would have prevented it regardless. |
