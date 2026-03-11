# MMM Favorable Scale-Up (FSU) — Implementation Plan

> **Feature:** When both CE and PE premiums are decaying (market is flat/safe), automatically open new option positions at fresh OTM strikes to capture additional theta. Once created, these positions are fully integrated into MMM — loss calculations, adjustments, strike shifts, close-at-5, harvesting all apply identically.
>
> **Date:** March 11, 2026
> **Status:** Plan — ready for implementation

---

## 1. CONCEPT

### 1.1 What It Does

When the heartbeat detects **both CE and PE premiums have decayed significantly** from their trigger snapshots (Condition A — OUTCOME_NONE), the market is demonstrably flat. This is the safest possible moment to add exposure. FSU:

1. Scans the options chain for fresh OTM CE and PE strikes near a target premium
2. Sells `initial_lots × scale_lots_pct%` at these new strikes (both sides simultaneously)
3. Registers the new positions into the existing MMM session state via `activate_new_strike()` pattern
4. From that moment forward, MMM treats them identically to any other position — adjustments cover their losses, close-at-5 closes them, shifts can freeze them, harvesting can harvest them

### 1.2 Why It's Safe

- **Both premiums decaying** = BTC hasn't moved directionally. If it had, at least one side would be rising.
- Positions go through identical safety rails: position cap, total exposure ceiling, margin guardian, lot velocity, regime controls
- Max events cap prevents unbounded accumulation
- Cooldown prevents rapid stacking
- Session P&L must be positive (no scaling into a losing session)
- Wind-down and margin tiers block scaling

### 1.3 Key Design Decision

**Once created, positions ARE MMM positions.** The scaler's only job is to decide WHEN to create them and at WHAT strikes. After creation:
- Stored in `session['ce']['positions'][]` and `session['pe']['positions'][]` with `type='scale_up'`, **`status='shifted'`**
- Counted in `frozen_positions` / `frozen_total_lots` (NOT `active_lots`) — see §1.4 for why
- Included in `calculate_standard_loss()` frozen-position loop (per-strike premium fetch)
- Included in `calculate_reversal_loss()` (iterates ALL positions)
- Subject to total exposure ceiling, close-at-5, M1 harvesting, M2 recycling
- Trigger snapshots explicitly set for the new scale-up strikes (fill price = baseline)

### 1.4 Why `status='shifted'` Not `status='active'` — The Loss Calculation Architecture

**Critical discovery during code review:** `calculate_standard_loss()` in `mmm_engine.py` has TWO loops:
1. **Active strike loss:** `(premium_now - trigger) × active_lots` — ALL positions with `status='active'` contribute to `active_lots`, and the formula uses `premium_now` which is the premium AT THE ACTIVE STRIKE
2. **Frozen position loss:** iterates `frozen_positions[]` — each frozen position gets its OWN premium fetched at its OWN strike via `fetch_premium_fn(p_strike, option_type)`

If scale-up positions at a **different strike** had `status='active'`, their lots would be counted in `active_lots` and the loss formula would multiply them by the active strike's premium movement — **the wrong strike's premium**. This produces incorrect hedging quantities.

By using `status='shifted'`, scale-up positions:
- Appear in `frozen_positions[]` with their own per-strike premium lookup ✓
- Have correct loss = `(current_premium_at_their_strike - entry_premium) × lots` ✓
- Don't bloat `active_lots` with lots tracked at the wrong premium ✓
- Still count toward `total_lots` (total exposure, asymmetry, margin) ✓
- Are scanned by close-at-5 (scans ALL positions regardless of status) ✓
- Are eligible for M1 harvesting (scans `frozen_positions`) ✓
- Are eligible for M2 recycling (operates on frozen positions) ✓
- Wind-down closes ALL positions including shifted ones ✓

**Position cap impact:** Scale-up positions don't count against `max_lots_per_side` (which uses `active_lots`). They DO count against `max_total_exposure` (which uses `total_lots`). The eligibility check in `check_scale_eligibility()` uses `total_lots` + `max_total_exposure` for its headroom check.

---

## 2. ARCHITECTURE

### 2.1 New File

**`webui/backend/routes/mmm/mmm_scaler.py`** (~200 lines)

Single-responsibility module following the pattern of `mmm_harvester.py`. Contains:
- `check_scale_eligibility(session, ce_now, pe_now) → (eligible: bool, reason: str)`
- `find_scale_strikes(initializer, session, spot_price) → {ce: {strike, premium, symbol}, pe: {strike, premium, symbol}} | None`
- `record_scale_event(session, ce_result, pe_result) → None`

### 2.2 Integration Point

**One insertion in `mmm_monitor.py`** — inside the `OUTCOME_NONE` block (currently `pass` at ~line 1750):

```python
if outcome == OUTCOME_NONE:
    # FSU: Favorable Scale-Up — add positions when both sides are safe
    if not is_wind_down_active(session):
        await self._process_scale_up(ce_now, pe_now)
```

**One new method in `mmm_monitor.py`:**
`async def _process_scale_up(self, ce_now, pe_now)` (~150 lines)

### 2.3 Files Modified

| File | Change | Lines |
|------|--------|-------|
| `mmm_scaler.py` | **NEW** — eligibility check + strike finder + state recorder | ~200 |
| `mmm_monitor.py` | Insert `_process_scale_up()` call in OUTCOME_NONE + new method | ~160 |
| `mmm_state.py` | Add 7 params to `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS` | ~15 |
| `mmm_config.py` | Add 7 entries to `PARAM_RULES` + description strings | ~20 |
| `mmm_activity.py` | Add `'scale_up'` to `ACTIVITY_TYPES` + `ACTIVITY_CATEGORIES` | ~5 |
| `mmm_websocket.py` | Add `emit_scale_up()` function | ~15 |
| `mmm_constants.py` | No changes needed | 0 |
| `MMMSettingsDialog.js` | New settings section `favorableScaleUp` with 7 params + tooltips | ~40 |
| `MMMActivityFeed.js` | Add icon/color for `scale_up` activity type (if not auto-handled) | ~3 |

### 2.4 Files NOT Modified

These correctly handle scale-up positions automatically because they operate on the unified position ledger:

| File | Why No Change Needed |
|------|---------------------|
| `mmm_engine.py` | `calculate_standard_loss()` iterates `frozen_positions[]` — scale_up positions (status='shifted') get per-strike premium lookup. Loss = `(current - entry) × lots` per position. |
| `mmm_engine.py` | `calculate_lots_to_sell()` checks `active_lots` — scale_up lots are NOT in `active_lots` (correct: they're at different strikes) |
| `mmm_engine.py` | `execute_adjustment()` sells at `active_strike` — unchanged |
| `mmm_close_at_5.py` | Scans ALL positions regardless of type/status — scale_up included |
| `mmm_strike_shift.py` | `freeze_current_positions()` freezes `status='active'` only — scale_up positions already `status='shifted'`, unaffected |
| `mmm_harvester.py` | Scans `frozen_positions` — scale_up positions ARE in `frozen_positions` (status='shifted') → eligible for harvesting |
| `mmm_recycler.py` | Operates on frozen positions → scale_up positions included |
| `mmm_safety.py` | `check_asymmetry()` and `check_margin()` use `total_lots` → includes scale_up. `check_position_cap()` uses `active_lots` → excludes scale_up (correct: different strike) |
| `mmm_perp_hedge.py` | Delta calculation reads ALL positions → scale_up included |
| `mmm_wind_down.py` | Close logic reads ALL positions → scale_up included |

---

## 3. DETAILED IMPLEMENTATION

### 3.1 `mmm_scaler.py` — New Module

```python
"""
MMM Favorable Scale-Up (FSU)

When both CE and PE premiums are decaying significantly (OUTCOME_NONE),
opens new positions at fresh OTM strikes to capture additional theta.

Once created, positions become standard MMM positions — fully tracked
by the unified ledger, included in all loss calculations, adjustments,
close-at-5, harvesting, and recycling.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)


def check_scale_eligibility(
    session: Dict,
    ce_now: float,
    pe_now: float,
) -> Tuple[bool, str]:
    """
    Check whether the session is eligible for a scale-up event.

    Returns:
        (eligible, reason) — reason explains why eligible or why not.
    """
    params = session.get('params', {})

    # 1. Master switch
    if not params.get('scale_enabled', False):
        return False, 'scale_enabled=False'

    # 2. Session must be RUNNING
    if session.get('strategy_status') != 'RUNNING':
        return False, f"status={session.get('strategy_status')}"

    # 3. Max events cap
    scale_count = session.get('scale_count', 0)
    max_events = params.get('scale_max_events', 3)
    if scale_count >= max_events:
        return False, f'max_events reached ({scale_count}/{max_events})'

    # 4. Cooldown check
    last_scale_at = session.get('_last_scale_at')
    if last_scale_at:
        try:
            last_dt = datetime.fromisoformat(last_scale_at)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            cooldown = params.get('scale_cooldown_mins', 30) * 60
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                return False, f'cooldown ({remaining}s remaining)'
        except (ValueError, TypeError):
            pass

    # 5. Session P&L must be positive
    realized = session.get('realized_pnl', 0)
    unrealized = session.get('unrealized_pnl', 0)
    total_pnl = realized + unrealized
    if total_pnl <= 0:
        return False, f'session P&L negative (${total_pnl:.2f})'

    # 6. Margin tier must be GREEN
    margin_block = session.get('_margin_block_sells', False)
    margin_wind_down = session.get('_margin_wind_down', False)
    if margin_block or margin_wind_down:
        return False, 'margin tier not GREEN'

    # 7. Regime must not block sells
    from .mmm_regime import ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE
    regime_action = session.get('_regime_action', 'normal')
    if regime_action in (ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE):
        return False, f'regime blocks sells ({regime_action})'

    # 8. P&L must not be incomplete (stale data guard)
    if session.get('_pnl_calculation_incomplete', False):
        return False, 'P&L calculation incomplete'

    # 9. Near-expiry guard — don't scale into positions that will immediately
    #    enter wind-down. Block if minutes_to_expiry < scale_cooldown_mins * 1.5
    #    or less than 60 minutes (hard floor). Wind-down blocks via
    #    is_wind_down_active() at wind_down_hours_before_expiry (default 2h),
    #    but between that boundary and ~60 min there's a gap where scaling
    #    could open positions that immediately face wind-down buyback.
    expiry_str = params.get('expiry', '')
    if expiry_str:
        try:
            from .mmm_initializer import expiry_to_utc_datetime
            expiry_iso = expiry_to_utc_datetime(expiry_str)
            expiry_dt = datetime.fromisoformat(expiry_iso)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            minutes_remaining = (expiry_dt - datetime.now(timezone.utc)).total_seconds() / 60.0
            cooldown_mins = params.get('scale_cooldown_mins', 30)
            min_minutes = max(cooldown_mins * 1.5, 60)
            if minutes_remaining < min_minutes:
                return False, f'too close to expiry ({minutes_remaining:.0f}m < {min_minutes:.0f}m floor)'
        except Exception:
            pass  # If parsing fails, let other guards handle it

    # 10. Both premiums must have decayed by scale_min_decay_pct from snapshot
    min_decay = params.get('scale_min_decay_pct', 35.0)

    ce_state = session.get('ce', {})
    pe_state = session.get('pe', {})
    ce_active_strike = ce_state.get('active_strike', 0)
    pe_active_strike = pe_state.get('active_strike', 0)

    from .mmm_constants import strike_key
    ce_snap = ce_state.get('trigger_snapshot', {}).get(strike_key(ce_active_strike), 0)
    pe_snap = pe_state.get('trigger_snapshot', {}).get(strike_key(pe_active_strike), 0)

    if ce_snap <= 0 or pe_snap <= 0:
        return False, 'trigger snapshot zero/missing'

    ce_decay_pct = ((ce_snap - ce_now) / ce_snap) * 100.0
    pe_decay_pct = ((pe_snap - pe_now) / pe_snap) * 100.0

    if ce_decay_pct < min_decay:
        return False, f'CE decay {ce_decay_pct:.1f}% < {min_decay}%'
    if pe_decay_pct < min_decay:
        return False, f'PE decay {pe_decay_pct:.1f}% < {min_decay}%'

    # 11. Total exposure ceiling check (Split Ledger)
    #     Scale-up positions use status='shifted' so they don't count against
    #     max_lots_per_side (active_lots). But they DO count against
    #     max_total_exposure (total_lots). Check headroom there.
    initial_lots = params.get('initial_lots', 5)
    scale_lots = max(1, int(initial_lots * params.get('scale_lots_pct', 50.0) / 100.0))
    max_lots = params.get('max_lots_per_side', 100)
    max_total = params.get('max_total_exposure', 0) or (max_lots * 2)
    ce_total = ce_state.get('total_lots', 0)
    pe_total = pe_state.get('total_lots', 0)
    if ce_total + scale_lots > max_total:
        return False, f'CE total exposure ceiling ({ce_total}+{scale_lots} > {max_total})'
    if pe_total + scale_lots > max_total:
        return False, f'PE total exposure ceiling ({pe_total}+{scale_lots} > {max_total})'

    return True, (
        f'eligible: CE decay {ce_decay_pct:.1f}%, '
        f'PE decay {pe_decay_pct:.1f}%, '
        f'lots={scale_lots}, P&L=${total_pnl:.2f}'
    )


def find_scale_strikes(
    initializer,
    session: Dict,
    spot_price: float,
) -> Optional[Dict]:
    """
    Find fresh OTM strikes for scale-up on both CE and PE sides.

    Uses the same chain scan logic as strike shifting (find_new_strike)
    but targets the scale_target_premium parameter.

    Returns:
        {
            'ce': {'strike': float, 'premium': float, 'symbol': str},
            'pe': {'strike': float, 'premium': float, 'symbol': str},
            'lots': int,
        }
        or None if no suitable strikes found.
    """
    params = session.get('params', {})
    expiry = params.get('expiry', '')
    target_premium = params.get('scale_target_premium', 100.0)
    min_premium = params.get('scale_min_premium', 30.0)
    initial_lots = params.get('initial_lots', 5)
    scale_lots = max(1, int(initial_lots * params.get('scale_lots_pct', 50.0) / 100.0))

    try:
        chain_data = initializer.get_full_chain(expiry)
        if not chain_data or not chain_data.get('chain'):
            log.warning("Scale-up: No chain data available")
            return None

        chain = chain_data['chain']

        # Collect existing strikes to avoid duplicates
        ce_existing = set()
        pe_existing = set()
        for pos in session.get('ce', {}).get('positions', []):
            if pos.get('lots', 0) > 0:
                ce_existing.add(int(round(pos.get('strike', 0))))
        for pos in session.get('pe', {}).get('positions', []):
            if pos.get('lots', 0) > 0:
                pe_existing.add(int(round(pos.get('strike', 0))))

        # Also exclude the current active strikes
        ce_active = int(round(session.get('ce', {}).get('active_strike', 0)))
        pe_active = int(round(session.get('pe', {}).get('active_strike', 0)))
        ce_existing.add(ce_active)
        pe_existing.add(pe_active)

        ce_candidates = []
        pe_candidates = []

        for entry in chain:
            strike = entry.get('strike', 0)
            if strike <= 0:
                continue

            # CE candidates: CALL, OTM (strike > spot)
            call_data = entry.get('call', {})
            if call_data and strike > spot_price:
                bid = call_data.get('best_bid', 0) or 0
                mark = call_data.get('mark_price', 0) or 0
                premium = bid if bid > 0 else mark
                symbol = call_data.get('symbol', '')
                strike_int = int(round(strike))

                if premium > 0 and strike_int not in ce_existing:
                    if premium < min_premium:
                        continue  # Below scale_min_premium floor
                    ce_candidates.append({
                        'strike': strike,
                        'premium': premium,
                        'symbol': symbol,
                        'distance': abs(premium - target_premium),
                    })

            # PE candidates: PUT, OTM (strike < spot)
            put_data = entry.get('put', {})
            if put_data and strike < spot_price:
                bid = put_data.get('best_bid', 0) or 0
                mark = put_data.get('mark_price', 0) or 0
                premium = bid if bid > 0 else mark
                symbol = put_data.get('symbol', '')
                strike_int = int(round(strike))

                if premium > 0 and strike_int not in pe_existing:
                    if premium < min_premium:
                        continue  # Below scale_min_premium floor
                    pe_candidates.append({
                        'strike': strike,
                        'premium': premium,
                        'symbol': symbol,
                        'distance': abs(premium - target_premium),
                    })

        # Sort by proximity to target premium (closest first)
        ce_candidates.sort(key=lambda c: c['distance'])
        pe_candidates.sort(key=lambda c: c['distance'])

        if not ce_candidates or not pe_candidates:
            log.info(
                f"Scale-up: No strikes found "
                f"(CE candidates={len(ce_candidates)}, PE candidates={len(pe_candidates)})"
            )
            return None

        best_ce = ce_candidates[0]
        best_pe = pe_candidates[0]

        # Reject if best premium is too far from target (> 3x or < 0.2x)
        for label, best in [('CE', best_ce), ('PE', best_pe)]:
            ratio = best['premium'] / target_premium if target_premium > 0 else 0
            if ratio > 3.0 or ratio < 0.2:
                log.info(
                    f"Scale-up: {label} best premium ${best['premium']:.2f} "
                    f"too far from target ${target_premium:.2f} (ratio={ratio:.2f})"
                )
                return None

        return {
            'ce': {'strike': best_ce['strike'], 'premium': best_ce['premium'], 'symbol': best_ce['symbol']},
            'pe': {'strike': best_pe['strike'], 'premium': best_pe['premium'], 'symbol': best_pe['symbol']},
            'lots': scale_lots,
        }

    except Exception as e:
        log.exception(f"Scale-up strike scan failed: {e}")
        return None


def record_scale_event(session: Dict, ce_info: Dict, pe_info: Dict, lots: int):
    """Record a scale-up event in session state."""
    session['scale_count'] = session.get('scale_count', 0) + 1
    session['_last_scale_at'] = datetime.now(timezone.utc).isoformat()
    session.setdefault('scale_history', []).append({
        'event_number': session['scale_count'],
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'ce_strike': ce_info['strike'],
        'ce_premium': ce_info['premium'],
        'pe_strike': pe_info['strike'],
        'pe_premium': pe_info['premium'],
        'lots_per_side': lots,
    })
    # Cap history size
    if len(session['scale_history']) > 50:
        session['scale_history'] = session['scale_history'][-50:]
```

### 3.2 `mmm_monitor.py` — OUTCOME_NONE Insertion

**Location:** ~line 1750, replace `pass` in `if outcome == OUTCOME_NONE:` block.

```python
if outcome == OUTCOME_NONE:
    # FSU: Favorable Scale-Up — add positions when both sides are decaying
    if not is_wind_down_active(session):
        await self._process_scale_up(ce_now, pe_now)
```

### 3.3 `mmm_monitor.py` — New Method `_process_scale_up()`

Insert near other lifecycle methods (e.g., after `_process_harvest` around line 3730):

```python
async def _process_scale_up(self, ce_now: float, pe_now: float):
    """
    Favorable Scale-Up: When both premiums are decaying, open new
    positions at fresh OTM strikes to capture additional theta.

    Positions are registered in the unified ledger and become standard
    MMM positions — subject to all loss calculations, adjustments,
    close-at-5, strike shifts, harvesting, and recycling.
    """
    session = self.session
    sid = self.session_id

    from .mmm_scaler import check_scale_eligibility, find_scale_strikes, record_scale_event

    # Step 1: Check eligibility
    eligible, reason = check_scale_eligibility(session, ce_now, pe_now)
    if not eligible:
        return

    log.info(f"[{sid}] Scale-up eligible: {reason}")

    # Step 2: Find strikes
    spot_price = await self._fetch_spot_price()
    if spot_price <= 0:
        log.warning(f"[{sid}] Scale-up: Could not fetch spot price")
        return

    scale_info = find_scale_strikes(self.initializer, session, spot_price)
    if not scale_info:
        log_activity('scale_up_no_strikes',
                    f'📈 Scale-up eligible but no suitable strikes found',
                    sid, 'info', {'reason': reason})
        return

    lots = scale_info['lots']
    ce_target = scale_info['ce']
    pe_target = scale_info['pe']

    log_activity('scale_up_triggered',
                f'📈 Scale-Up Triggered: Selling {lots} lots each — '
                f'CE @ {ce_target["strike"]} (${ce_target["premium"]:.2f}), '
                f'PE @ {pe_target["strike"]} (${pe_target["premium"]:.2f})',
                sid, 'info',
                {
                    'lots': lots,
                    'ce_strike': ce_target['strike'],
                    'ce_premium': ce_target['premium'],
                    'pe_strike': pe_target['strike'],
                    'pe_premium': pe_target['premium'],
                    'reason': reason,
                    'scale_event': session.get('scale_count', 0) + 1,
                })

    # Step 3: Execute CE sell
    params = session.get('params', {})
    expiry = params.get('expiry', '')
    _reprice_max = params.get('max_reprice_attempts', None)

    ce_symbol = ce_target.get('symbol') or self.initializer.build_symbol(
        'call', 'BTC', ce_target['strike'], expiry
    )
    pe_symbol = pe_target.get('symbol') or self.initializer.build_symbol(
        'put', 'BTC', pe_target['strike'], expiry
    )

    # Register pending orders
    from .mmm_pending_orders import register_pending, clear_pending
    try:
        register_pending(sid, 'ce', 'pending', ce_symbol, lots, ce_target['strike'], 'scale_up')
    except Exception:
        pass

    ce_result = await self.executor.smart_execute(
        symbol=ce_symbol, side='sell', size=lots,
        max_reprice_attempts=_reprice_max,
    )

    try:
        if ce_result.get('success'):
            register_pending(sid, 'ce', str(ce_result.get('order_id', '')),
                           ce_symbol, lots, ce_target['strike'], 'scale_up')
        else:
            clear_pending(sid, 'ce')
    except Exception:
        pass

    if not ce_result.get('success'):
        log_activity('scale_up_failed',
                    f'❌ Scale-up CE sell FAILED @ {ce_target["strike"]}: '
                    f'{ce_result.get("error", "unknown")}',
                    sid, 'error',
                    {'side': 'CE', 'strike': ce_target['strike'], 'error': ce_result.get('error')})
        clear_pending(sid, 'ce')
        return  # Abort — don't sell PE without CE (keeps balance)

    ce_fill = ce_result.get('fill_price', 0)

    # Step 4: Execute PE sell
    try:
        register_pending(sid, 'pe', 'pending', pe_symbol, lots, pe_target['strike'], 'scale_up')
    except Exception:
        pass

    pe_result = await self.executor.smart_execute(
        symbol=pe_symbol, side='sell', size=lots,
        max_reprice_attempts=_reprice_max,
    )

    try:
        if pe_result.get('success'):
            register_pending(sid, 'pe', str(pe_result.get('order_id', '')),
                           pe_symbol, lots, pe_target['strike'], 'scale_up')
        else:
            clear_pending(sid, 'pe')
    except Exception:
        pass

    if not pe_result.get('success'):
        log_activity('scale_up_failed',
                    f'❌ Scale-up PE sell FAILED @ {pe_target["strike"]}: '
                    f'{pe_result.get("error", "unknown")} '
                    f'(CE was filled @ {ce_fill:.2f} — positions will be asymmetric)',
                    sid, 'error',
                    {'side': 'PE', 'strike': pe_target['strike'], 'error': pe_result.get('error')})
        # CE already filled — must still register it. Continue below.

    pe_fill = pe_result.get('fill_price', 0) if pe_result.get('success') else 0

    # Step 5: Register positions in the unified ledger
    from .mmm_constants import strike_key, LOT_SIZE_BTC
    from .mmm_state import recompute_side_lots
    from .mmm_trigger import update_trigger_snapshots

    now = datetime.now(timezone.utc).isoformat()

    # Register CE position
    ce_state = session.get('ce', {})
    counter = ce_state.get('_pos_counter', 0) + 1
    ce_state['_pos_counter'] = counter
    ce_state.setdefault('positions', []).append({
        'id': f"ce_scale_{counter:03d}",
        'strike': ce_target['strike'],
        'lots': lots,
        'entry_premium': ce_fill,
        'premium': ce_fill,
        'type': 'scale_up',
        'status': 'shifted',          # NOT 'active' — see §1.4 for rationale
        'created_at': now,
        'shifted_at': now,            # frozen from birth (different strike)
        'closed_at': None,
        'realized_pnl': None,
        'timestamp': now,
    })

    # If CE active_strike differs from scale strike, the scale position
    # lives at a different strike. Using status='shifted' ensures it appears
    # in frozen_positions[] and gets its own per-strike premium lookup in
    # the loss calculation (calculate_standard_loss). This is architecturally
    # critical — see §1.4.
    recompute_side_lots(ce_state)
    session['ce'] = ce_state

    # Register PE position (only if filled)
    if pe_result.get('success'):
        pe_state = session.get('pe', {})
        counter = pe_state.get('_pos_counter', 0) + 1
        pe_state['_pos_counter'] = counter
        pe_state.setdefault('positions', []).append({
            'id': f"pe_scale_{counter:03d}",
            'strike': pe_target['strike'],
            'lots': lots,
            'entry_premium': pe_fill,
            'premium': pe_fill,
            'type': 'scale_up',
            'status': 'shifted',          # NOT 'active' — see §1.4
            'created_at': now,
            'shifted_at': now,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,
        })
        recompute_side_lots(pe_state)
        session['pe'] = pe_state

    # Step 6: Set trigger snapshots for the new scale-up strikes.
    #
    # CRITICAL: update_trigger_snapshots() only writes ce_now/pe_now against
    # the ACTIVE strike keys, and then iterates frozen_positions to snapshot
    # their strikes via fetch_premium_fn. But the scale-up positions were
    # JUST created — their strikes may not be in the premium cache yet
    # (the cache was built at heartbeat start, before these positions existed).
    #
    # We must EXPLICITLY set trigger_snapshot for the new strikes to the
    # fill price. This serves as the loss baseline: if the premium at the
    # scale-up strike rises above this fill price, the loss calculation
    # computes (current - entry_premium) correctly. The trigger_snapshot
    # for frozen positions is used for incremental loss tracking after
    # adjustments ("already hedged up to here").
    ce_state = session.get('ce', {})
    ce_state.setdefault('trigger_snapshot', {})[strike_key(ce_target['strike'])] = ce_fill
    session['ce'] = ce_state

    if pe_result.get('success'):
        pe_state = session.get('pe', {})
        pe_state.setdefault('trigger_snapshot', {})[strike_key(pe_target['strike'])] = pe_fill
        session['pe'] = pe_state

    # Now call update_trigger_snapshots for the active strikes + other frozen.
    # The explicit sets above won't be overwritten because:
    # (a) update_trigger_snapshots writes ce_now to active_strike key (different)
    # (b) the frozen loop uses fetch_premium_fn which may return None for
    #     just-created strikes (cache miss) — None values are skipped.
    # EVEN IF the fetch succeeds, the correct value is the fill price
    # (the adjustment hasn't happened yet), so we force-set AFTER the call.
    update_trigger_snapshots(session, ce_now, pe_now,
                            fetch_premium_fn=self._make_fetch_fn())

    # Force-set AGAIN after update_trigger_snapshots to prevent overwrite
    # (same pattern as BUG-1 fix in _process_strike_shift)
    ce_state = session.get('ce', {})
    ce_state.setdefault('trigger_snapshot', {})[strike_key(ce_target['strike'])] = ce_fill
    session['ce'] = ce_state
    if pe_result.get('success'):
        pe_state = session.get('pe', {})
        pe_state.setdefault('trigger_snapshot', {})[strike_key(pe_target['strike'])] = pe_fill
        session['pe'] = pe_state

    # Step 7: Update session tracking
    premium_collected_ce = ce_fill * lots * LOT_SIZE_BTC
    premium_collected_pe = pe_fill * lots * LOT_SIZE_BTC if pe_result.get('success') else 0
    total_premium = premium_collected_ce + premium_collected_pe
    session['total_premium_collected'] = session.get('total_premium_collected', 0) + total_premium

    record_scale_event(session, ce_target, pe_target, lots)

    # Clear pending orders
    try:
        clear_pending(sid, 'ce')
        clear_pending(sid, 'pe')
    except Exception:
        pass

    # Step 8: Emit events
    from .mmm_websocket import emit_scale_up
    emit_scale_up(
        sid, lots,
        ce_target['strike'], ce_fill,
        pe_target['strike'], pe_fill if pe_result.get('success') else 0,
        session.get('scale_count', 0),
    )

    sessions_filled = 2 if pe_result.get('success') else 1
    pe_status_str = f'${pe_fill:.2f}' if pe_result.get('success') else 'FAILED'
    log_activity('scale_up_complete',
                f'\u2705 Scale-Up #{session.get("scale_count", 0)}: '
                f'{sessions_filled}/2 sides filled \u2014 '
                f'CE {lots}L @ {ce_target["strike"]} (${ce_fill:.2f}), '
                f'PE {lots}L @ {pe_target["strike"]} ({pe_status_str})',
                sid, 'success',
                {
                    'scale_event': session.get('scale_count', 0),
                    'ce_strike': ce_target['strike'],
                    'ce_premium': ce_fill,
                    'pe_strike': pe_target['strike'],
                    'pe_premium': pe_fill if pe_result.get('success') else 0,
                    'lots': lots,
                    'sides_filled': sessions_filled,
                    'premium_collected': total_premium,
                })

    session['updated_at'] = datetime.now(timezone.utc).isoformat()
```

---

## 4. PARAMETER DEFINITIONS

### 4.1 `mmm_state.py` — DEFAULT_PARAMS

Add after the M3 Asymmetry Rebalancing block (~line 432):

```python
# FSU: Favorable Scale-Up
'scale_enabled': False,               # master switch — disabled until user opts in
'scale_min_decay_pct': 35.0,          # both CE and PE must have decayed this % from trigger snapshot
'scale_lots_pct': 50.0,               # lots per side = initial_lots × this% (e.g., 50% of 10 = 5 lots)
'scale_max_events': 3,                # max scale-up events per session
'scale_cooldown_mins': 30,            # minutes between scale-up events
'scale_target_premium': 100.0,        # target premium for new strikes (same unit as shift_target_premium)
'scale_min_premium': 30.0,            # reject strikes with premium below this (liquidity/theta floor)
```

### 4.2 `mmm_state.py` — HOT_RELOAD_PARAMS

Add to the set:

```python
# FSU: Favorable Scale-Up
'scale_enabled', 'scale_min_decay_pct', 'scale_lots_pct',
'scale_max_events', 'scale_cooldown_mins', 'scale_target_premium',
'scale_min_premium',
```

### 4.3 `mmm_config.py` — PARAM_RULES

```python
# FSU: Favorable Scale-Up
'scale_enabled':          {'type': bool,  'min': None, 'max': None,   'hot': True},
'scale_min_decay_pct':    {'type': float, 'min': 10,   'max': 90,     'hot': True},
'scale_lots_pct':         {'type': float, 'min': 10,   'max': 100,    'hot': True},
'scale_max_events':       {'type': int,   'min': 1,    'max': 20,     'hot': True},
'scale_cooldown_mins':    {'type': int,   'min': 5,    'max': 240,    'hot': True},
'scale_target_premium':   {'type': float, 'min': 10,   'max': 5000,   'hot': True},
'scale_min_premium':      {'type': float, 'min': 5,    'max': 1000,   'hot': True},
```

### 4.4 `mmm_config.py` — PARAM_DESCRIPTIONS

```python
'scale_enabled': 'Master switch for Favorable Scale-Up. When market is flat (both premiums decaying), automatically sell new OTM options to capture extra theta.',
'scale_min_decay_pct': 'Minimum % both CE and PE premiums must have decayed from trigger snapshot before scale-up triggers. Higher = more conservative (requires deeper decay before adding exposure).',
'scale_lots_pct': 'Lots to sell per side as % of initial_lots. E.g., 50% with initial_lots=10 → sell 5 lots per side.',
'scale_max_events': 'Maximum scale-up events per session. Caps total additional exposure. After this many scale-ups, no more are allowed.',
'scale_cooldown_mins': 'Minimum minutes between consecutive scale-up events. Prevents rapid stacking.',
'scale_target_premium': 'Target premium for finding new OTM strikes. The algo picks strikes closest to this premium level. Same concept as shift_target_premium.',
'scale_min_premium': 'Reject strikes with premium below this value. Ensures minimum theta capture and liquidity.',
```

---

## 5. ACTIVITY & WEBSOCKET

### 5.1 `mmm_activity.py`

Add to `ACTIVITY_TYPES`:
```python
'scale_up_triggered': 'Scale-Up Triggered',
'scale_up_complete': 'Scale-Up Complete',
'scale_up_failed': 'Scale-Up Failed',
'scale_up_no_strikes': 'Scale-Up No Strikes',
```

Add `'scale_up_triggered'`, `'scale_up_complete'`, `'scale_up_failed'`, `'scale_up_no_strikes'` to `ACTIVITY_CATEGORIES['adjustments']` set.

### 5.2 `mmm_websocket.py`

Add new emit function:

```python
def emit_scale_up(session_id: str, lots: int,
                  ce_strike: float, ce_premium: float,
                  pe_strike: float, pe_premium: float,
                  scale_count: int):
    """Emit scale-up event."""
    _emit('mmm_scale_up', {
        'session_id': session_id,
        'lots': lots,
        'ce_strike': ce_strike,
        'ce_premium': ce_premium,
        'pe_strike': pe_strike,
        'pe_premium': pe_premium,
        'scale_count': scale_count,
    })
```

---

## 6. FRONTEND CHANGES

### 6.1 `MMMSettingsDialog.js` — New Section

Add a new section after `balanceControl`:

```javascript
favorableScaleUp: {
    title: '📈 Favorable Scale-Up',
    color: '#8bc34a',
    blurb: 'When both CE and PE premiums are decaying (market is flat), automatically open new OTM option positions to capture additional theta. Positions become standard MMM positions with full protection.',
    params: [
      'scale_enabled',
      'scale_min_decay_pct', 'scale_lots_pct',
      'scale_max_events', 'scale_cooldown_mins',
      'scale_target_premium', 'scale_min_premium',
    ],
},
```

Add tooltips to `PARAM_TOOLTIPS`:

```javascript
scale_enabled: 'Master switch for Favorable Scale-Up (FSU). When enabled and both premiums have decayed significantly, the algo opens new positions at fresh OTM strikes. Positions become standard MMM positions — included in adjustments, loss calculations, close-at-5, etc. Disabled by default — enable when you want the algo to compound gains in flat markets.',
scale_min_decay_pct: 'Both CE and PE premiums must have decayed by at least this percentage from the trigger snapshot before a scale-up event fires. Higher = more conservative. Default 35% means premiums must have dropped by a third — confirming the market has been flat for a meaningful period.',
scale_lots_pct: 'Lots per side as a percentage of initial_lots. With initial_lots=10 and scale_lots_pct=50, each scale-up sells 5 lots CE + 5 lots PE. Lower = more conservative. Default 50%.',
scale_max_events: 'Maximum number of scale-up events per session. After this many, no more scale-ups occur. With initial_lots=10, scale_lots_pct=50, max_events=3: up to 15 extra lots per side (10 initial + 15 scaled = 25 total). Default 3.',
scale_cooldown_mins: 'Minimum minutes between consecutive scale-up events. Prevents rapid stacking even when conditions remain favorable. Default 30 minutes.',
scale_target_premium: 'Target premium when scanning for new OTM strikes. The algo picks the OTM strike with premium closest to this value. Higher = further OTM (safer, less theta). Same concept as shift_target_premium. Default $100.',
scale_min_premium: 'Minimum premium threshold for scale-up strikes. Strikes below this premium are rejected — too little theta to justify the risk. Default $30.',
```

### 6.2 `MMMActivityFeed.js` — Activity Icon (if needed)

Check if the ActivityFeed auto-derives icons from activity type names or has an explicit map. If explicit map exists, add:

```javascript
'scale_up_triggered': { icon: '📈', color: '#8bc34a' },
'scale_up_complete': { icon: '✅', color: '#4caf50' },
'scale_up_failed': { icon: '❌', color: '#f44336' },
'scale_up_no_strikes': { icon: '🔍', color: '#ff9800' },
```

---

## 7. HOW MMM HANDLES SCALE-UP POSITIONS AUTOMATICALLY

This is the critical design guarantee. After `_process_scale_up()` appends positions to the unified ledger, every existing module handles them without any code changes:

### 7.1 Loss Calculation
`mmm_engine.py → calculate_standard_loss()` has a TWO-LOOP architecture:
1. **Active loop**: `(premium_now - trigger) × active_lots × LOT_SIZE_BTC` — uses the active_strike premium.
2. **Frozen loop**: iterates `frozen_positions[]`, fetches premium PER-STRIKE via `fetch_premium_fn(strike, option_type)`.

Scale-up positions use `status='shifted'`, so `recompute_side_lots()` places them into `frozen_positions[]`. The frozen loop in `calculate_standard_loss()` then fetches the correct premium at the scale-up strike (not the active_strike). This is WHY `status='shifted'` is mandatory — see §1.4.

Their trigger_snapshot is explicitly set to the fill price at creation (see Step 6 in §3.3), so the loss baseline is accurate from the first heartbeat.

### 7.2 Adjustments
When a trigger fires and hedge lots are calculated, the loss from scale-up positions is included in the total. The adjustment sells at the `active_strike` — which hasn't changed. The hedge covers ALL positions including scale-ups.

### 7.3 Close-at-5
`mmm_close_at_5.py → scan_closeable_positions()` iterates ALL positions. Scale-up positions at their strike will have their premium checked against threshold. When premium ≤ 5 → bought back.

### 7.4 Strike Shifting
If the active_strike's premium drops below shift_threshold, `freeze_current_positions()` freezes ALL positions with `status='active'` at the active_strike. Scale-up positions already have `status='shifted'` and live at a different strike — they are **unaffected** by the freeze operation. After the shift completes and a new active_strike is selected, the scale-up positions remain in `frozen_positions[]` at their original strike, continuing to be tracked by the per-strike frozen loop in loss calculation. No special handling needed.

### 7.5 Wind-Down
`mmm_wind_down.py` closes positions in LIFO order. Scale-up positions have later `created_at` timestamps → they get closed first. This is the correct behavior.

### 7.6 Harvesting (M1)
If a scale-up position gets frozen (via strike shift at its strike), it becomes eligible for M1 harvesting just like any frozen position.

### 7.7 Position Cap & Total Exposure
Scale-up positions use `status='shifted'`, so `recompute_side_lots()` counts them in `frozen_total_lots` (not `active_lots`). They contribute to `total_lots = active_lots + frozen_total_lots`. The eligibility check in `mmm_scaler.py` verifies headroom against `max_total_exposure` (the overall cap on `total_lots`), NOT against `max_lots_per_side` (which only caps `active_lots`). This means scale-up lots don't block future adjustments at the active strike.

### 7.8 Margin Guardian
Reads `total_lots` from session state. Scale-up lots are included after `recompute_side_lots()`.

### 7.9 Perp Delta Hedge
`_calculate_portfolio_delta()` iterates all positions. Scale-up positions contribute to delta → hedged by perp.

---

## 8. POSITION LIFECYCLE DIAGRAM

```
Scale-Up creates positions (status='shifted' from birth)
        │
        ▼
   ┌──────────┐     close-at-5     ┌──────────┐
   │  SHIFTED  │  ──────────────►  │  CLOSED   │
   │ scale_up  │   (premium ≤ 5)   │ (P&L ✓)  │
   │ (frozen)  │                   └──────────┘
   └──────────┘
        │
        │  M1 harvest (profit ≥ 40%)
        ▼
   ┌──────────┐
   │  CLOSED   │  (P&L ✓ — realized_pnl set)
   └──────────┘
        │
        │  or M2 recycle
        ▼
   ┌──────────┐
   │ RECYCLED │  → new lots at better strike
   └──────────┘

Note: Scale-up positions skip the ACTIVE→SHIFTED transition.
They are born 'shifted' because they live at a different strike
than the active_strike. The frozen loop in calculate_standard_loss()
handles them correctly from the first heartbeat.
```

---

## 9. IMPLEMENTATION ORDER

| Step | File | Task | Est. Lines |
|------|------|------|------------|
| 1 | `mmm_state.py` | Add 7 params to `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS` | 15 |
| 2 | `mmm_config.py` | Add `PARAM_RULES` + description strings | 20 |
| 3 | `mmm_activity.py` | Add 4 activity types + category | 5 |
| 4 | `mmm_websocket.py` | Add `emit_scale_up()` | 15 |
| 5 | `mmm_scaler.py` | Create module: eligibility + strike finder + recorder | 200 |
| 6 | `mmm_monitor.py` | OUTCOME_NONE insertion + `_process_scale_up()` method | 160 |
| 7 | `MMMSettingsDialog.js` | New section + tooltips | 40 |
| 8 | `MMMActivityFeed.js` | Activity type icons (if needed) | 3 |
| 9 | Testing | Manual verification with live session | — |

**Total: ~460 lines of new code across 7 files + 1 new file.**

---

## 10. EDGE CASES HANDLED

| Scenario | Handling |
|----------|----------|
| CE fills, PE fails | CE position registered; PE skipped. Session becomes asymmetric but safe — asymmetry checks will flag it |
| No suitable strikes | `find_scale_strikes()` returns None → no action |
| Both premiums decay but regime blocks | Eligibility check reads `_regime_action` → rejects |
| Scale during wind-down | Guard: `if not is_wind_down_active(session)` before calling |
| Position cap reached | Eligibility check pre-verifies headroom for both sides |
| API failure mid-execution | Pending order guard + circuit breaker handle it |
| Multiple scale events too fast | `scale_cooldown_mins` enforces gap |
| Session P&L goes negative | Eligibility requires `total_pnl > 0` |
| Stale premium data | `_pnl_calculation_incomplete` flag blocks scale-up |
| Margin tier escalates after scale | Margin guardian detects via next heartbeat, blocks further sells |
| Scale positions at same strike as active | `ce_existing` / `pe_existing` sets exclude active + all open strikes |
| Scale-up near expiry | Near-expiry guard blocks if `minutes_remaining < max(scale_cooldown_mins * 1.5, 60)` — prevents selling into wind-down |

---

## 11. TESTING PLAN

### 11.1 Manual Testing
1. Start an MMM session with `scale_enabled=True`, `scale_min_decay_pct=20` (easier trigger for testing)
2. Wait for both premiums to decay 20%+
3. Verify scale-up fires: activity log shows `📈 Scale-Up Triggered` + `✅ Scale-Up Complete`
5. Verify new positions appear in Positions table with type=`scale_up`, status=`shifted`
6. Verify `frozen_total_lots` increased (NOT `active_lots` — scale positions are frozen from birth)
7. Verify trigger_snapshot has entries for the new scale-up strikes
8. Verify loss calculation includes scale-up positions via the frozen loop (per-strike premium fetch)
9. Verify close-at-5 can close scale-up positions
10. Verify `scale_count` increments and `scale_max_events` cap works
11. Test cooldown: verify second scale-up doesn't fire within `scale_cooldown_mins`
12. Test with `scale_enabled=False` — verify no scale-up occurs
13. Test near-expiry: verify scale-up blocked when <60 min to expiry

### 11.2 Safety Verification
1. Manually move to wind-down → verify scale-up does not fire
2. Set margin tier to YELLOW → verify scale-up blocked
3. Set `scale_max_events=1` → verify only 1 scale-up occurs
4. Set `max_total_exposure` low → verify position cap prevents scale-up
5. Verify Settings dialog shows all 7 params correctly
6. Verify hot-reload works: change `scale_cooldown_mins` while running

---

## 12. FUTURE ENHANCEMENTS (NOT IN THIS IMPLEMENTATION)

- **Telegram notification** on scale-up events
- **Analytics panel** showing scale-up ROI per session
- **Auto-adjust scale_target_premium** based on current IV levels
- **Scale-down**: reverse FSU — close scale-up positions first when conditions deteriorate (already handled by close-at-5 and LIFO wind-down)
