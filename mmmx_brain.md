# MMMX Brain — Strategy Logic Document

> **Purpose:** This document defines the complete decision-making logic of MMMX. It is the "brain" — the rules that distinguish this strategy from ordinary premium-selling systems. Everything in `mmmx_plan.md` is the skeleton; this document is the mind.
>
> **Status:** Draft for review — not yet merged into mmmx_plan.md
>
> **Last updated:** 2026-04-04
>
> **Author:** Operator (5 years live options trading experience) + AI analysis

---

## 1. Philosophy

**Ordinary premium sellers** deploy all capital at entry and pray the market stays still.

**MMMX** treats the market like a negotiation:
- Enter small
- Let the market reveal its intentions
- Deploy more only when the market confirms an opportunity (elevated IV or confirmed directional move)
- Never let any position approach ATM without a response
- Hard stop is absolute and non-negotiable

The brain has exactly **two phases** and **three protection layers**:

```
PHASE 1: DEPLOYMENT
  Objective: Put capital to work intelligently as market creates opportunities
  Duration: Until 100-lot budget is fully deployed (may take 1 day or 5 days)
  Trigger: Spot move OR IV spike (each heartbeat)

PHASE 2: PROTECTION
  Objective: Protect deployed capital, let theta work
  Duration: Until DTE close or hard stop
  Mechanisms: ATM Shield (per-tranche), Hard Stop (session-wide)

ALWAYS ACTIVE:
  Hard Stop → absolute ceiling on total session loss
  Premium Listener → real-time circuit breaker for catastrophic moves
```

---

## 2. Capital Structure

```
┌─────────────────────────────────────────────────────┐
│  MMMX SESSION CAPITAL (per side)                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TRANCHE BUDGET      100 lots  (deployment budget)  │
│  ├── Tranche 1        10 lots  (10% — deployed day 1)│
│  ├── Tranche 2        10 lots  (10% — on trigger)   │
│  ├── ...                                            │
│  └── Tranche 10       10 lots  (10% — fully deployed)│
│                                                     │
│  ATM SHIELD RESERVE   30 lots  (protection budget)  │
│  └── Used ONLY for ATM protection loss recovery     │
│      Not used for regular deployment                │
│                                                     │
│  TOTAL MAX EXPOSURE  130 lots per side              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**The 30-lot ATM Shield Reserve is separate from the 100-lot tranche budget.**
These lots are only consumed during ATM protection events.
If the reserve is exhausted and ATM protection fires again → Telegram alert + operator decides.

---

## 3. Phase 1: Deployment Logic

### 3.1 Initial Entry (Tranche 1 — Manual Trigger)

The operator initiates the session manually via UI:

```
Step 1: Operator sets OTM distance (e.g., 10%) — hot-reloadable
Step 2: Operator clicks "Scan Chain"
        → System scans options chain
        → Displays available strikes at ~10% OTM from current ATM
        → Shows: strike price, current premium (USD), current delta, bid depth
Step 3: Operator reviews and clicks "Deploy Tranche 1"
        → 10 lots CE sold at CE_strike (10% above current spot)
        → 10 lots PE sold at PE_strike (10% below current spot)
        → Session status: RUNNING
        → Hard stop initialized: 2× premium_collected_so_far
```

**After Tranche 1:**
- `last_deployment_spot` = current spot at time of deployment
- `last_deployment_iv_rank` = current IV rank at deployment
- `tranches_deployed` = 1
- `tranches_remaining` = 9

---

### 3.2 Subsequent Tranche Deployment (Automatic, Every Heartbeat)

**Heartbeat runs every 1 hour.** At each beat, the system checks:

#### Deployment Conditions (OR logic — either alone is sufficient)

```python
CONDITION A — Market Move:
  spot_move_pct = abs(current_spot - last_deployment_spot) / last_deployment_spot × 100
  condition_a = spot_move_pct >= tranche_deploy_move_pct  # default 2%, hot-reloadable

CONDITION B — IV Spike:
  iv_delta = current_iv_rank - last_deployment_iv_rank
  condition_b = iv_delta >= tranche_deploy_iv_delta  # default 10 rank points, hot-reloadable

DEPLOY = (condition_a OR condition_b)
       AND tranches_remaining > 0
       AND margin_utilization < 80%
       AND NOT atm_protection_fired_this_beat  # ATM protection takes priority (see §4.4)
```

**Maximum one tranche per beat.** Even if BOTH conditions are met simultaneously, only one tranche is deployed. The next tranche is evaluated again at the next beat.

#### Deployment Eligibility Queue (NEW — Solution 1)

**Problem:** A 6% move in one beat should deploy multiple tranches (if they're all confirmed by the move), but the "one per beat" rule means only 1 tranche deploys. How do we capture the full move without violating the rule?

**Solution:** Populate a queue of eligible tranches when a large move is detected. Deploy them one per beat over subsequent beats, but clear the queue if the market retraces.

**How it works:**

When a deployment trigger fires:
```python
# 1. Calculate how many tranches this move justifies
spot_move_pct = abs(current_spot - last_deployment_spot) / last_deployment_spot × 100
num_tranches_eligible = floor(spot_move_pct / tranche_deploy_move_pct)
# Example: 6.4% move / 2% threshold = 3 tranches eligible

# 2. Populate queue
for i in range(1, num_tranches_eligible + 1):
    if tranches_remaining > 0:
        deployment_eligible_tranches.append(next_tranche_id)

# 3. Deploy first from queue this beat
deploy_tranche(deployment_eligible_tranches.pop(0))
```

When a retracement is detected:
```python
# Check if market has retraced > 0.5% from the spot that triggered the queue
retracement_pct = abs(
    current_spot - deployment_queue_triggered_spot
) / deployment_queue_triggered_spot × 100

if retracement_pct > 0.5:
    # Move confirmation broken, clear queue
    deployment_eligible_tranches.clear()
    log.info(f"Deployment queue cleared: {retracement_pct:.1f}% retracement")
```

**Example with numbers:**
```
Beat 0: BTC $67,500 → Deploy Tr1 manually
Beat 1: BTC $70,500 (+4.4% from $67,500)
  → spot_move_pct = 4.4%
  → num_eligible = floor(4.4 / 2.0) = 2 tranches
  → Queue: [Tr2, Tr3]
  → Deploy Tr2 this beat
  → Queue becomes: [Tr3]
  → deployment_queue_triggered_spot = $70,500

Beat 2: BTC $71,500 (+1.5% from $70,500)
  → Retracement check: abs(71,500 - 70,500) / 70,500 = 1.4%
  → 1.4% < 0.5%? NO, so queue is STILL VALID
  → Deploy Tr3 from queue
  → Queue now empty

Beat 3: BTC $69,000 (-3.5% from $71,500)
  → Retracement check: abs(69,000 - 70,500) / 70,500 = -2.1%
  → 2.1% > 0.5%? YES, market retraced!
  → Clear queue (if any tranches remained)
  → Do NOT deploy

Beat 4: BTC $72,000 (+4.3% from $69,000)
  → NEW move detected from $69,000
  → spot_move_pct = (72,000 - 69,000) / 69,000 = 4.3%
  → num_eligible = floor(4.3 / 2.0) = 2 tranches
  → NEW Queue: [Tr4, Tr5]
  → Deploy Tr4 this beat
```

**Result:** Instead of losing the 4.4% move confirmation after just 1 tranche, we deploy 2 tranches (Tr2, Tr3) across 2 beats. The retracement at Beat 3 correctly clears the queue (good capital preservation). The new move at Beat 4 starts a fresh queue.

**Session state fields needed:**
- `deployment_eligible_tranches: []` — Queue of tranche IDs
- `deployment_queue_triggered_at: None` — When queue was populated
- `deployment_queue_triggered_spot: None` — Spot price that triggered queue (used for retracement check)

#### New Tranche Strike Selection

Strikes for each new tranche are calculated from the **CURRENT spot**, not the original entry spot.

**Strike selection must use the live exchange strike ladder — do NOT hardcode step sizes.**

Delta Exchange's strike intervals vary by asset price level and DTE (daily options may have $100–$500 steps; monthly options may have $1,000–$2,500 steps). These can change. The correct approach:

```python
# 1. Calculate the raw target price
raw_ce_target = current_spot × (1 + otm_distance_pct / 100)
raw_pe_target = current_spot × (1 - otm_distance_pct / 100)

# 2. Query live available strikes from Delta Exchange API
available_strikes = fetch_available_strikes(
    asset='BTC',
    contract_type='call_options',   # or put_options
    expiry_date=session['expiry_date']  # format: DD-MM-YYYY
)
# API: GET /v2/tickers?contract_types=call_options,put_options
#               &underlying_asset_symbols=BTC&expiry_date=DD-MM-YYYY

# 3. Snap to nearest available strike on the live ladder
ce_strike = min(available_strikes, key=lambda s: abs(s - raw_ce_target))
pe_strike = min(available_strikes, key=lambda s: abs(s - raw_pe_target))

# 4. Build symbol using Delta Exchange symbology: {Type}-BTC-{Strike}-{DDMMYY}
# Example: C-BTC-78000-280326
ce_symbol = f"C-BTC-{ce_strike}-{expiry_ddmmyy}"
pe_symbol = f"P-BTC-{pe_strike}-{expiry_ddmmyy}"
```

**Why live query, not hardcoded steps:** Delta can and does adjust strike ladders. A hardcoded 1000-step assumption may miss the actual nearest strike or select an illiquid one. The live API call is cheap (cached at session start and refreshed on each beat).

**Strike cache:** At session start and on each heartbeat, MMMX fetches and caches the full options chain for the session's expiry. Strike selection reads from this cache — no per-order API call needed.

**Old tranches are NOT touched.** Tranche 1's CE at the original strike stays open. It is now deeper OTM — that is intentional. It continues collecting theta with reduced delta risk.

#### After Deployment

```python
last_deployment_spot = current_spot
last_deployment_iv_rank = current_iv_rank
tranches_deployed += 1
tranches_remaining -= 1
total_premium_collected += new_tranche_premium
hard_stop_usd = hard_stop_multiplier × total_premium_collected  # recalculate
```

---

### 3.3 Deployment Phase End

Deployment ends when `tranches_remaining == 0` (all 100 lots deployed).

The system transitions to **pure protection mode**:
- Deployment trigger no longer evaluates
- Only ATM Shield and Hard Stop remain active
- All 10 tranches collect theta independently

---

## 4. Phase 2: Protection Logic

### 4.1 Hard Stop (Session-Wide — Absolute)

**This is the ultimate safety net. No exceptions. No overrides.**

```python
hard_stop_usd = hard_stop_multiplier × total_premium_collected
# Default multiplier: 2.0 (hot-reloadable, minimum 1.0)

# Updated after every:
#   - New tranche deployment
#   - Operator hot-reload of multiplier

# Checked at EVERY heartbeat before any other evaluation
total_pnl = realized_pnl + unrealized_pnl  # ALL positions: all tranches + all recovery lots
if total_pnl <= -hard_stop_usd:
    execute_close_all_immediately()
    send_telegram(CRITICAL, "HARD STOP HIT — All positions closed")
    session_status = COMPLETE
    return  # Nothing else runs
```

**Hard stop progression example:**

| State | Premium Collected | Hard Stop |
|-------|-------------------|-----------|
| After Tranche 1 (10 lots) | $10 | -$20 |
| After Tranche 3 (30 lots) | $30 | -$60 |
| After Tranche 5 (50 lots) | $50 | -$100 |
| After Tranche 10 (100 lots) | $100 | -$200 |

The hard stop is **a session-level number**. It covers unrealized losses from ALL tranche positions AND all ATM protection recovery lots combined.

**Hot-reload:** The operator can adjust `hard_stop_multiplier` via WebUI while the session is running. The hard stop amount recalculates immediately on the next beat.

---

### 4.2 ATM Shield — Core Logic

**The ATM Shield is the strategy brain for directional moves.** It monitors every open tranche position independently and ensures no position is allowed to approach near-ATM territory without a defensive response.

#### Trigger Condition (Per Position)

```python
# For each ACTIVE position in each tranche:
for tranche in session['tranches']:
    for side in ['ce', 'pe']:
        position = tranche[side]
        if position['status'] != 'ACTIVE':
            continue

        if side == 'ce':
            remaining_otm_pct = (position['strike'] - current_spot) / current_spot × 100
        else:  # pe
            remaining_otm_pct = (current_spot - position['strike']) / current_spot × 100

        if remaining_otm_pct < atm_protect_threshold:  # default 5%, hot-reloadable
            trigger_atm_shield(tranche, side, current_spot)
            break  # Only one shield per beat (see §4.4)
```

**Example:**
```
CE strike: $75,000
Current spot: $71,500
Remaining OTM: (75,000 - 71,500) / 71,500 × 100 = 4.9%
Threshold: 5%
4.9% < 5% → SHIELD TRIGGERS
```

---

### 4.3 ATM Shield — Execution Sequence

When the shield triggers on a tranche position:

#### Step 1: Calculate the Loss

```python
buyback_premium = current_market_premium  # current ask price
entry_premium = position['entry_premium']
lots = position['lots']

loss_usd = (buyback_premium - entry_premium) × lots × LOT_SIZE_BTC
# loss_usd is positive (it costs more to buy back than we sold for)
```

**Example:**
```
CE sold at: $100 premium, 10 lots
CE now at:  $200 premium
Loss = (200 - 100) × 10 × 0.001 = $1.00
```

#### Step 2: Buy Back the Endangered Position

Buyback follows the same battle-tested pattern as MMM's `close_position()` in `mmm_close_at_5.py`, with one difference: **10 reprice attempts instead of 4**, because 30-DTE monthly options have thinner books than 0DTE — mid-price orders sit unfilled longer.

**Pre-order: set `_being_closed` guard** (MMM pattern — prevents double-close if the state mutation crashes after the fill):
```python
position['_being_closed'] = True
position['_being_closed_at'] = time.monotonic()
# Auto-clears after 180s TTL if stuck (crash recovery)
```

**Execution loop** — `smart_execute()` with `max_reprice_attempts=10`:
```python
# smart_execute already handles the reprice loop internally.
# Pass max_reprice_attempts=10 to override the default of 4.
# Each reprice attempt waits FILL_TIMEOUT (60s) — but MMMX overrides to 30s per attempt.
# First half (attempts 1–5): limit at mid-price
# Second half (attempts 6–10): limit at best_bid (more aggressive, queue priority)
# Total worst-case: 10 × 30s = 5 minutes

result = await executor.smart_execute(
    symbol=position['symbol'],
    side='buy',
    size=position['lots'],
    reduce_only=True,
    max_reprice_attempts=10,   # vs MMM default of 4
    session_id=session_id,
    use_bid_entry=True,        # start at best_bid — cheaper maker fill (same as MMM close_at_5)
)
```

**If smart_execute fails** — verify on exchange before giving up (MMM pattern):
```python
if not result.get('success'):
    # Check if position was already closed externally (e.g. manual close, liquidation)
    open_positions = await rest_client.get('/v2/positions/margined')
    position_still_open = any(p['symbol'] == position['symbol'] for p in open_positions)

    if not position_still_open:
        # Already gone — mark closed in state, estimate P&L from last known premium
        _remove_position_from_state(session, position)
        log.warning(f"ATM Shield: {position['symbol']} already closed externally — marked closed")
        # continue to Step 3 (reposition) since position is gone
    else:
        # Still open and we can't close it — escalate to emergency_execute (IOC, aggressive price)
        result = await executor.emergency_execute(
            symbol=position['symbol'],
            side='buy',
            size=position['lots'],
            reduce_only=True,
            session_id=session_id,
        )
        emit_safety(f"ATM Shield: emergency buyback after 10 smart attempts — {position['symbol']}")
        telegram_alert(f"⚠️ ATM Shield escalated to emergency buyback on {position['symbol']}")

        if not result.get('success'):
            # Cannot close — ABORT entire shield, do NOT proceed to Steps 3–5
            # Clear in-flight flag so next heartbeat can retry
            position.pop('_being_closed', None)
            emit_safety(f"ATM Shield ABORTED — buyback failed completely: {position['symbol']}")
            telegram_alert(f"🚨 ATM Shield ABORTED — buyback failed. Manual intervention required.")
            return  # leave position open, state unchanged
```

**On fill** — stamp estimated P&L BEFORE state mutation (MMM FillSyncer pattern — prevents double-booking):
```python
actual_lots = result.get('filled_size', position['lots'])  # handle partial fills
close_price = result.get('fill_price', 0)

# Stamp so FillSyncer correction = (actual − estimated) not (actual − 0)
position['_estimated_pnl_booked'] = (position['entry_premium'] - close_price) * actual_lots * LOT_SIZE_BTC

# Register pending close verification — 3-beat grace window
# Prevents reconciliation from raising UNTRACKED_EXCHANGE_POSITION on the next beat
session.setdefault('_pending_close_verification', {})[position['symbol']] = {
    'lots_closed': actual_lots,
    'grace_beats': 3,
}

# Remove (or reduce if partial fill) from tranche position list
if actual_lots < position['lots']:
    position['lots'] -= actual_lots  # partial fill — reduce in place
    position.pop('_being_closed', None)
else:
    session['_tranches'][tranche_idx]['positions'].remove(position)  # full fill — remove
```

**Total worst-case buyback window: 10 × 30s = 5 min smart + emergency_execute fallback.**
Mirrors MMM's `close_position()` logic exactly — same guards, same partial fill handling, same FillSyncer stamp.

#### Step 3: Sell New Position at Fresh Strike

```python
# Recalculate strike from CURRENT spot (same OTM distance as session default)
raw_target = current_spot × (1 + otm_distance_pct / 100)
new_ce_strike = nearest_available_strike(raw_target, available_strikes_cache)
new_symbol = build_symbol('call', 'BTC', new_ce_strike, session['expiry_ddmmyy'])

# Sell original lot count at new strike — standard smart_execute (default 4 reprice attempts)
# No need for 10 attempts here: we are SELLING (selling into any bid is easier than buying)
result = await executor.smart_execute(
    symbol=new_symbol,
    side='sell',
    size=position['lots'],   # same original lots, repositioned
    reduce_only=False,
    session_id=session_id,
)

if not result.get('success'):
    # CRITICAL: buyback succeeded but new sell failed — position is now NAKED (no hedge)
    # Pause session immediately, do NOT proceed to recovery lots
    session['status'] = 'paused'
    emit_safety(f"ATM Shield: NAKED POSITION — buyback filled but reposition sell failed: {new_symbol}")
    telegram_alert(f"🚨 NAKED POSITION — ATM Shield buyback filled but sell failed. Session PAUSED. Manual reposition required.")
    return

# On fill — add new position to tranche with fresh entry_premium
new_position = {
    'id': generate_position_id(),
    'symbol': new_symbol,
    'strike': new_ce_strike,
    'side': 'ce',
    'lots': position['lots'],
    'entry_premium': result['fill_price'],
    'entry_time': utc_now(),
    'type': 'repositioned',              # distinguishes from original tranche sell
    'shield_shift_count': position.get('shield_shift_count', 0) + 1,
    'shield_history': position.get('shield_history', []) + [{
        'old_strike': position['strike'],
        'old_entry_premium': position['entry_premium'],
        'buyback_premium': close_price,
        'loss_usd': loss_usd,
        'shifted_at': utc_now(),
    }],
}
session['_tranches'][tranche_idx]['positions'].append(new_position)
```

#### Step 4: Calculate Recovery Lots (30/70 Split)

```python
# 30% of loss recovered via additional CE lots at new CE strike
ce_recovery_usd = loss_usd × 0.30  # hot-reloadable: atm_shield_ce_recovery_pct
new_ce_premium = fetch_premium(new_ce_symbol)
ce_recovery_lots = ceil(ce_recovery_usd / (new_ce_premium × LOT_SIZE_BTC))

# 70% of loss recovered via additional PE lots at 10% OTM from spot
pe_recovery_usd = loss_usd × 0.70  # = 1 - atm_shield_ce_recovery_pct
raw_target = current_spot × (1 - otm_distance_pct / 100)
new_pe_strike = nearest_available_strike(raw_target, available_strikes_cache)
new_pe_premium = fetch_premium(new_pe_symbol)
pe_recovery_lots = ceil(pe_recovery_usd / (new_pe_premium × LOT_SIZE_BTC))
```

**Example with numbers:**
```
Loss = $1.00
New CE premium at new strike: $100
New PE premium at 10% OTM: $80

CE recovery (30% = $0.30):
  lots = ceil(0.30 / (100 × 0.001)) = ceil(0.30 / 0.10) = ceil(3.0) = 3 lots

PE recovery (70% = $0.70):
  lots = ceil(0.70 / (80 × 0.001)) = ceil(0.70 / 0.08) = ceil(8.75) = 9 lots

Total recovery lots = 3 CE + 9 PE = 12 lots from ATM Shield Reserve
```

#### Step 5: Sell Recovery Lots

```python
# CE: additional lots at the SAME new CE strike (alongside repositioned position)
# Total CE at new strike = original_lots + ce_recovery_lots = 10 + 3 = 13 lots

# Check ATM shield reserve budget
if ce_recovery_lots + pe_recovery_lots > atm_shield_reserve_remaining:
    # Partial recovery — sell what budget allows, Telegram warning
    scale_recovery_lots_to_available_reserve()

await executor.smart_execute(symbol=new_ce_symbol, side='sell', size=ce_recovery_lots)
await executor.smart_execute(symbol=new_pe_symbol, side='sell', size=pe_recovery_lots)
```

#### Step 6: Update State

```python
# Close old position record
position['status'] = 'CLOSED'
position['realized_pnl'] = -loss_usd

# Add new CE record to tranche (original lots repositioned)
tranche['ce'] = {
    '_pos_id': new_uuid(),
    'strike': new_ce_strike,
    'lots': original_lots,  # same count, new strike
    'entry_premium': new_ce_premium,
    'origin': 'shield_reposition',
    'shield_count': position['shield_count'] + 1,
    ...
}

# Add recovery CE to ATM shield recovery positions
session['atm_recovery_positions'].append({
    'side': 'CE',
    'strike': new_ce_strike,
    'lots': ce_recovery_lots,
    'from_shield_event': shield_event_id,
    ...
})

# Add recovery PE to ATM shield recovery positions
session['atm_recovery_positions'].append({
    'side': 'PE',
    'strike': new_pe_strike,
    'lots': pe_recovery_lots,
    ...
})

# Update reserve
session['atm_shield_reserve_remaining'] -= (ce_recovery_lots + pe_recovery_lots)
session['atm_shield_reserve_used'] += (ce_recovery_lots + pe_recovery_lots)

# Update premium collected (recovery lots add new premium)
new_premium_from_recovery = (ce_recovery_lots × new_ce_premium + pe_recovery_lots × new_pe_premium) × LOT_SIZE_BTC
session['total_premium_collected'] += new_premium_from_recovery
session['hard_stop_usd'] = hard_stop_multiplier × session['total_premium_collected']
```

---

### 4.4 ATM Shield — Constraints and Guards

#### Max Shifts Per Position: Hot-Reloadable

```python
# Configured in session params — hot-reloadable (operator can raise/lower mid-session)
# Default: 3 shifts per position
params['atm_shield_max_shifts'] = 3  # HOT_RELOAD_PARAM

# Tracked per tranche position (not session-wide)
position['shield_shift_count'] = 0  # increments on each shift

if position['shield_shift_count'] >= params.get('atm_shield_max_shifts', 3):
    # Max shifts exhausted — cannot reposition again
    # Evaluated below: what to do depends on whether further OTM strikes exist
    ...
```

**Why hot-reloadable?** A market can trend persistently for days on a 30-DTE position. An operator who has been watching may want to raise the limit to 5 mid-session without restarting. Equally, during a known event (earnings, FOMC) they may lower it to 1 to force early hard-stop review. The default of 3 is a reasonable starting point, not a fixed ceiling.

---

#### No Further OTM Strike Available

This is a real scenario: if spot has moved so far in one direction that no strikes exist beyond the current position's strike on the exchange ladder, a reposition is impossible regardless of the shift count.

**Detection** (checked before the shift count guard — pointless to count if we can't shift anyway):

```python
raw_target = current_spot × (1 + otm_distance_pct / 100)
candidate_strike = nearest_available_strike(raw_target, available_strikes_cache)

# "No further OTM" condition: the best available strike is AT or INSIDE the current strike
# (i.e., we'd be moving toward ATM, not away from it)
if candidate_strike <= position['strike']:  # CE side — new must be HIGHER
    no_further_otm = True

if candidate_strike >= position['strike']:  # PE side — new must be LOWER
    no_further_otm = True
```

**What to do when no further OTM strike exists:**

This is a structural market condition — the exchange has run out of OTM strikes for this expiry. On monthly BTC options this implies spot has moved so far that even the outermost listed strikes are now near or ITM.

```
Decision tree:
  1. Check delta of current position
     └─ delta < 0.35 → still relatively safe; no action needed this beat
                        emit info event, Telegram once per session
                        re-check next beat (exchange may list new strikes as spot moves further)

     └─ 0.35 ≤ delta < 0.55 → reduce position by 50% (same as delta-gate REPOSITION but no roll)
                               use smart_execute(side='buy', size=lots//2)
                               emit warning, Telegram

     └─ 0.55 ≤ delta < 0.70 → reduce position by 75%
                               emit warning HIGH, Telegram

     └─ delta ≥ 0.70 → execute hard stop (close ALL — same as hard_stop trigger)
                        this is the terminal condition; no further logic needed
```

**Refresh the strikes cache first:** Before concluding no further OTM strike exists, force-refresh the available strikes from the API (don't rely on the cached version from beat start). Delta may have listed new strikes since then.

```python
# Force-refresh strike cache before giving up
available_strikes_cache = await fetch_available_strikes(
    asset='BTC',
    contract_type=option_type,
    expiry_date=session['expiry_date']
)
candidate_strike = nearest_available_strike(raw_target, available_strikes_cache)
# Re-evaluate — if new strikes appeared, proceed with normal shield
```

**The key insight:** When no further OTM strike exists, the *position itself is the risk*. We cannot reposition. The only lever left is reducing size (reduces delta exposure proportionally) or closing entirely (hard stop). The delta-gate table above maps exactly to that.

---

#### Max Shifts Exhausted (shifts available, but limit reached)

```python
if position['shield_shift_count'] >= params.get('atm_shield_max_shifts', 3):
    # Same delta-gate decision as "no further OTM" above — the logic is identical:
    # we cannot shield further, so delta determines the response.
    # The only difference: operator CAN raise atm_shield_max_shifts via hot-reload
    # to unblock the shield without restarting — Telegram message should mention this.

    emit('mmmx_safety', type='shield_exhausted',
         tranche_id=tranche['id'], side=side,
         shift_count=position['shield_shift_count'],
         delta=current_delta)
    telegram_alert(
        f"⚠️ ATM Shield exhausted — {side.upper()} tranche {tranche['id']} "
        f"has shifted {position['shield_shift_count']}× "
        f"(limit={params['atm_shield_max_shifts']}). "
        f"Delta={current_delta:.2f}. "
        f"Raise atm_shield_max_shifts to allow more shifts, or let hard stop manage."
    )
    # Then apply delta-gate (same as no-further-OTM above)
```

#### Priority: ATM Shield Before Deployment

In any given beat, if the ATM Shield fires, deployment is skipped for that beat:

```
Beat execution order:
  1. Check Hard Stop → if hit, STOP (nothing else runs)
  2. Check ATM Shield (each tranche, each side)
     → If ANY shield fires:
         execute shield
         skip deployment this beat
         done
  3. Check Deployment Conditions
     → If conditions met AND budget available:
         deploy next tranche
  4. Update P&L, recompute hard stop
  5. Save, emit events, Telegram if action taken
  6. Schedule next beat
```

**Why ATM Shield before Deployment?** An existing position is in danger. Fixing the danger takes priority over adding new capital. Deploying a new tranche in the same beat as an ATM shift would add positions when the system is already stressed — wrong direction.

#### Reserve Exhaustion Guard

```python
if session['atm_shield_reserve_remaining'] <= 0:
    # Reserve is depleted — no more recovery lots available
    # Shield can still REPOSITION the original lots (steps 1-3)
    # But recovery lots (steps 4-5) are skipped
    # Telegram: "ATM Shield reserve depleted — repositioning only, no recovery lots"
    skip_recovery_lots = True
```

---

### 4.5 ATM Shield — Full Example

```
Session: BTC @ $67,500, otm_distance_pct = 10%
Tranche 1: CE @ $74,250 (10% OTM), PE @ $60,750 (10% OTM), 10 lots each
Reserve: 30 lots available

Hour 6: BTC rises to $70,875
  CE remaining OTM: (74,250 - 70,875) / 70,875 × 100 = 4.76%
  Threshold: 5%
  4.76% < 5% → SHIELD TRIGGERS on Tranche 1 CE

  ── Shield Execution ──

  Step 1: Loss
    buyback_premium = $200 (CE now worth $200, was $100)
    loss = (200 - 100) × 10 × 0.001 = $1.00

  Step 2: Buy back Tranche 1 CE @ $74,250
    → Filled at $200 (cost: $2.00, sold for $1.00 → net -$1.00)

  Step 3: Sell new CE @ 10% OTM from $70,875
    raw_target = 70,875 × 1.10 = $77,963
    new_ce_strike = nearest_available_strike($77,963, cache) → $78,000  (nearest on exchange ladder)
    → Sold 10 lots at $100 premium (new strike, elevated IV)

  Step 4: Recovery lots
    ce_recovery = ceil(0.30 / (100 × 0.001)) = ceil(3.0) = 3 lots
    pe_recovery = ceil(0.70 / (85 × 0.001)) = ceil(8.24) = 9 lots
    Total from reserve: 12 lots

  Step 5: Sell recovery lots
    → 3 CE @ $78,000 (alongside the 10 repositioned CE lots)
    → 9 PE @ $63,788 (10% below $70,875, current PE OTM level)

  ── State After Shield ──

  Tranche 1 CE: repositioned from $74,250 → $77,963 (10 lots, shield_count=1)
  Recovery CE: 3 lots @ $77,963 (now total 13 CE lots at $77,963)
  Recovery PE: 9 lots @ $63,788
  Reserve remaining: 30 - 12 = 18 lots
  New premium from recovery: (3 × 100 + 9 × 85) × 0.001 = $1.065
  Total premium collected: +$1.065 (partially offsets the $1.00 loss)

  Telegram:
  "⚠️ MMMX ATM SHIELD
  Session abc123: Tranche 1 CE shifted
  Old strike: $74,250 → New strike: $77,963
  Loss covered: $1.00
  Recovery lots: 3 CE + 9 PE
  Reserve remaining: 18/30 lots
  Hard stop updated: $X"

  → Deployment SKIPPED this beat
  → Next beat in 1 hour
```

---

### 4.6 ATM Shield — What Happens to Recovery Positions After Shift?

Recovery positions (the additional CE/PE lots sold during an ATM Shield event) are **independent from tranche positions** in terms of monitoring:

- They are tracked in `session['atm_recovery_positions']` — a flat list
- They are included in `total_unrealized_pnl` for hard stop calculation
- They are NOT eligible for ATM Shield triggering themselves (recovery positions are always OTM at time of placement — the next shift of the original position handles re-centering)
- They DO close when a hard stop fires or DTE_CLOSE fires
- They are NOT closed during tranche reduces unless operator explicitly chooses

---

## 5. Beat Execution Order (Complete)

Every 1-hour heartbeat:

```
┌─────────────────────────────────────────────────────────────┐
│  MMMX BEAT (every 1 hour)                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  0. SAFETY GATE                                             │
│     ├── Circuit breaker OPEN? → skip beat (fast-fail)      │
│     ├── Generation stale? → stop monitor                   │
│     └── Session COMPLETE/STOPPED? → stop monitor           │
│                                                             │
│  1. FETCH LIVE DATA                                         │
│     ├── Current spot price                                  │
│     ├── Current DVOL + IV rank                             │
│     ├── Current DTE                                         │
│     └── Current premiums + deltas for ALL open positions   │
│         (all tranche positions + all recovery positions)    │
│                                                             │
│  2. HARD STOP CHECK (ABSOLUTE PRIORITY)                    │
│     total_pnl = sum(all_realized) + sum(all_unrealized)    │
│     IF total_pnl <= -hard_stop_usd:                        │
│         close_all_immediately()                            │
│         STOP — nothing else runs                           │
│                                                             │
│  3. DTE CHECK                                               │
│     IF current_dte <= close_at_dte (default 7):            │
│         close_all_immediately()                            │
│         STOP                                               │
│                                                             │
│  4. UPDATE P&L                                              │
│     ├── Compute unrealized P&L per position                │
│     ├── Compute portfolio delta (all positions combined)   │
│     └── Check _pnl_calculation_incomplete flag             │
│                                                             │
│  5. ATM SHIELD CHECK (per tranche, per side)               │
│     FOR each tranche:                                       │
│       FOR each side (CE, PE):                               │
│         remaining_otm = compute_remaining_otm(position)    │
│         IF remaining_otm < atm_protect_threshold:          │
│           IF shield_count < 3:                             │
│             execute_atm_shield(tranche, side)              │
│             shield_fired = True                            │
│             BREAK (only one shield per beat)               │
│           ELSE:                                             │
│             emit shield_exhausted warning                   │
│                                                             │
│  6. DEPLOYMENT CHECK (skipped if shield fired this beat)   │
│     IF NOT shield_fired AND tranches_remaining > 0:        │
│       check_tranche_deploy_conditions()                    │
│       IF conditions met:                                   │
│         execute_tranche_deploy()                           │
│                                                             │
│  7. RECOMPUTE HARD STOP                                     │
│     hard_stop_usd = multiplier × total_premium_collected   │
│                                                             │
│  8. SAVE + EMIT                                             │
│     ├── Save session to mmmx_sessions.db                   │
│     ├── Emit mmmx_beat_update WebSocket event              │
│     └── Telegram if any action taken this beat             │
│                                                             │
│  9. SCHEDULE NEXT BEAT                                      │
│     next_beat = now + adjustment_interval_hours × 3600     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Premium Listener — Tier-0 Circuit Breakers (Real-Time)

**Runs in parallel to heartbeat.** Monitors all open positions in real-time (not hourly). Fires immediately on catastrophic moves without waiting for next beat.

Tier-0 actions are limited:
- `CB_NEAR_ITM` (any position delta >= 0.72): immediate 50% reduce on that position + wake heartbeat
- All other CBs: wake heartbeat only (no position action taken by listener)

The heartbeat then evaluates whether to shield / reduce / close based on delta gates.

**Critical rule:** CB_NEAR_ITM reduces the specific position, not the whole session. The heartbeat evaluates the full picture after wakeup.

---

## 7. Complete Decision Tree

```
EVERY BEAT:

  total_pnl <= -hard_stop?
  YES → close_all, COMPLETE, Telegram CRITICAL
  NO ↓

  current_dte <= close_at_dte?
  YES → close_all, COMPLETE, Telegram
  NO ↓

  Any position remaining_otm < atm_protect_threshold?
  YES → execute_atm_shield (shift + recovery lots)
        skip_deployment_this_beat
        Telegram ⚠️
  NO ↓

  tranches_remaining > 0 AND (spot_move >= X% OR iv_delta >= Y%)?
  YES → execute_tranche_deploy (10% lots at current spot ± OTM%)
        update hard_stop
        Telegram ✅
  NO ↓

  DO NOTHING (theta working, all positions safe)
  Log beat health, save session, schedule next
```

---

## 8. Parameter Reference

All hot-reloadable unless marked (No).

| Parameter | Default | Range | Hot Reload | Description |
|-----------|---------|-------|-----------|-------------|
| `total_budget_lots` | 100 | 10–1000 | No | Max lots per side for deployment tranches |
| `atm_shield_reserve_lots` | 30 | 0–200 | No | Extra lots reserved for ATM shield recovery |
| `tranche_pct` | 10 | 5–50 | No | % of budget per tranche (10% = 10 lots) |
| `otm_distance_pct` | 10.0 | 5.0–30.0 | **Yes** | Distance from ATM for new strikes (both deploy and shield) |
| `tranche_deploy_move_pct` | 2.0 | 0.5–10.0 | **Yes** | Min spot move % from last deployment to deploy next tranche |
| `tranche_deploy_iv_delta` | 10 | 1–50 | **Yes** | Min IV rank point increase from last deployment |
| `hard_stop_multiplier` | 2.0 | 1.0–10.0 | **Yes** | hard_stop = multiplier × total_premium_collected |
| `atm_protect_threshold` | 5.0 | 1.0–15.0 | **Yes** | Remaining OTM % that triggers ATM shield |
| `atm_shield_ce_recovery_pct` | 30 | 0–100 | **Yes** | % of shield loss recovered via CE lots |
| `atm_shield_max_shifts` | 3 | 1–10 | **Yes** | Max ATM shield fires per tranche position |
| `adjustment_interval_hours` | 1 | 1–24 | **Yes** | Heartbeat cadence (1h recommended) |
| `close_at_dte` | 7 | **7**–45 | **Yes** | DTE at which all positions close (hard minimum 7) |
| `entry_dte_min` | 20 | 10–60 | No | Minimum DTE to start a session |
| `entry_dte_max` | 45 | 20–90 | No | Maximum DTE to start a session |
| `entry_iv_rank_min` | 50 | 0–100 | No | Minimum IV rank to start a session |
| `profit_target_pct` | 50 | 10–100 | **Yes** | Close all when this % of premium collected is locked |
| `profit_target_enabled` | False | bool | **Yes** | Enable profit target |
| `near_itm_delta` | 0.55 | 0.30–0.80 | **Yes** | CB_NEAR_ITM threshold (reduce position) |
| `alert_on_adjustment` | True | bool | **Yes** | Telegram on every action |

---

## 9. Scenarios Walkthrough

### Scenario A: Smooth Market (No Triggers)

```
Day 1, 10:00: Tranche 1 deployed, CE @ $74,250, PE @ $60,750
  Premium: $10. Hard stop: -$20.

Day 1, 11:00: BTC $67,620 (+0.2%), IV rank same
  Spot move: 0.2% < 2% threshold → no deploy
  ATM shield: CE remaining OTM = 9.8%, PE = 10.1% → both > 5% → no shield
  RESULT: do nothing. Theta working.

Day 2, 10:00 (24 beats later): BTC still ~$68,000
  CE remaining OTM: still ~8.5% → safe
  No deploy conditions met
  RESULT: Still do nothing. $10 premium collecting daily theta.
```

### Scenario B: Sustained Upward Move (ATM Shield + Continued Deploy)

```
Day 1, 10:00: Tranche 1 deployed at BTC $67,500
  CE @ $74,250, PE @ $60,750, 10 lots each
  Premium: $10. Hard stop: -$20.

Day 1, 11:00: BTC $69,225 (+2.6%)
  Spot move: 2.6% >= 2% → DEPLOY Tranche 2
  Tranche 2: CE @ $76,148 (10% from $69,225), PE @ $62,303
  Premium: +$11. Total: $21. Hard stop: -$42.

Day 1, 12:00: BTC $70,000 (+1.1% from last deploy)
  Spot move: 1.1% < 2% → no deploy
  ATM shield: Tranche 1 CE remaining OTM = (74,250-70,000)/70,000 = 6.1% → safe
  RESULT: do nothing.

Day 1, 14:00: BTC $71,500 (+2.1% from Tranche 2 deployment)
  Spot move: 2.1% >= 2% → DEPLOY Tranche 3
  CE @ $78,650, PE @ $64,350
  Premium: +$12. Total: $33. Hard stop: -$66.

Day 1, 15:00: BTC $72,900 (+2.0%)
  CE Tranche 1: (74,250 - 72,900) / 72,900 = 1.85% < 5% → SHIELD TRIGGERS
  
  ── ATM Shield: Tranche 1 CE ──
  Buyback: CE @ $74,250 at $380 (was $100)
  Loss: (380-100) × 10 × 0.001 = $2.80

  New CE strike: nearest_available_strike(72,900 × 1.10 = $80,190, cache) → $80,000
  New PE recovery strike: nearest_available_strike(72,900 × 0.90 = $65,610, cache) → $66,000

  CE recovery: ceil(0.30 × 2.80 / (120 × 0.001)) = ceil(0.84 / 0.12) = 7 lots
  PE recovery: ceil(0.70 × 2.80 / (90 × 0.001)) = ceil(1.96 / 0.09) = 22 lots
  Total reserve used: 29 lots. Reserve remaining: 1 lot.

  Telegram: "⚠️ ATM Shield fired Tranche 1 CE — Loss $2.80 covered by 7 CE + 22 PE recovery lots"

  DEPLOYMENT SKIPPED this beat.
```

### Scenario C: Hard Stop Hit

```
5 tranches deployed, total premium collected = $50
Hard stop = -$100

Market crashes 12% in 3 hours.
Total unrealized loss (all tranches) = -$140

Beat fires:
  total_pnl = $50 - $140 = -$90 ← not yet at -$100
  Next hour: loss widens to -$170
  total_pnl = $50 - $170 = -$120 <= -$100 → HARD STOP

RESULT: close_all_immediately()
  All tranche positions closed (5 CE + 5 PE)
  All recovery positions closed
  Session COMPLETE
  Telegram CRITICAL: "HARD STOP HIT. Total loss: -$120 on $50 premium collected."
```

### Scenario D: Reserve Exhausted

```
3 ATM shield events used 28 of 30 reserve lots.
4th shield fires, needs 15 lots recovery.
Reserve remaining: 2 lots.

System behavior:
  Reposition original lots (steps 1-3) → executed normally
  Recovery lots: 2 lots available (not 15 needed)
  Scale: sell only 2 lots (partial recovery)
  Telegram: "⚠️ ATM Shield reserve near exhausted (2/30 remaining). Partial recovery only."
  
5th shield fires with 0 reserve remaining:
  Reposition original lots → executed
  Recovery lots: skipped entirely
  Telegram: "🚨 ATM Shield reserve DEPLETED. No recovery lots available. Manual review needed."
```

---

## 10. What This Strategy Is NOT

| ❌ NOT This | ✅ This Instead |
|-------------|----------------|
| Deploy all capital at entry | 10% at a time, on confirmation |
| Close everything when market moves | ATM Shield repositions, never panics |
| Fixed max loss | Dynamic hard stop that grows with premium collected |
| Roll losing side, keep winning side | Reposition the endangered position, keep all deep OTM |
| 24h blind periods | 1h heartbeat + real-time CB listener |
| Ignore IV spikes | IV spike = opportunity to deploy next tranche |
| Treat all positions identically | Each tranche monitored independently |

---

## 11. Open Questions (Resolve Before Plan Update)

These need operator confirmation before merging into `mmmx_plan.md`:

| # | Question | Current Assumption | Status |
|---|----------|-------------------|--------|
| Q1 | When reserve is exhausted mid-shift, should the original lots reposition be attempted anyway (without recovery) or abort the whole shift? | Currently: reposition anyway, skip recovery | ⏳ Needs approval |
| Q2 | Large moves (6%+) deploy only 1 tranche per beat, missing deployment opportunity. How to capture full move? | ✅ **RESOLVED (2026-04-05)**: Deployment Eligibility Queue (Solution 1). 6% move queues 3 tranches, deployed one per beat, queue clears on >0.5% retracement. See Section 3.2. | ✅ Confirmed |
| Q3 | If market moves 2% AND IV spikes 10% in same beat — still only ONE tranche deployed, or multiple? | ✅ **CLARIFIED**: One per beat, BUT queued tranches continue deploying next beats. See Section 3.2 queue logic. | ✅ Confirmed |
| Q4 | Profit target: when enabled, does it close ALL positions (all tranches + all recovery) or just the profitable tranches? | Currently: closes all (same as hard stop behavior) | ⏳ Needs approval |
| Q5 | When Tranche 1 CE is repositioned via ATM Shield, its `entry_premium` updates. Should the original premium be preserved somewhere for analytics? | Currently: original preserved in `shield_history` array on position | ✅ Confirmed |
| Q6 | After 6% move—are missed tranches never deployed? | ✅ **RESOLVED (2026-04-05)**: Queue mechanism ensures they ARE deployed over next 2–3 beats (one per beat), assuming no >0.5% retracement. See Section 3.2. | ✅ Confirmed |
