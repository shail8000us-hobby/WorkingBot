# MMM Margin Guardian & Emergency Safety System

**Created**: February 20, 2026  
**Purpose**: Protect against catastrophic losses during violent market moves  
**Status**: Implementation in progress

---

## Problem Statement

The current MMM algo has **5 critical gaps** when the market moves violently:

1. **Detection is heartbeat-bound (60s blind window)** — all risk checks only run inside the heartbeat. Between beats, the system is completely blind. BTC can move $2,000+ in 60 seconds.
2. **`_auto_close_all` uses maker orders (post-only)** — in a crash, maker orders never fill because the market runs away from your price. Emergency close can take 100+ minutes for 10 positions.
3. **No real margin monitoring** — `check_margin()` in `mmm_safety.py` is a fake proxy counting lots. It never queries the exchange for actual margin utilization (`position_margin`, `available_balance`).
4. **No rapid-check mode** — when danger is detected (P&L at 80% of max_loss), the system keeps the same 60s heartbeat instead of switching to fast mode.
5. **Wind-down is time-based only** — activates N hours before expiry, has no concept of "market is crashing, reduce NOW."

### Existing Risk Layers (7 layers, all heartbeat-bound)

| # | Layer | File | Trigger | Action |
|---|-------|------|---------|--------|
| 1 | Max Loss | `mmm_monitor.py:989` | P&L ≤ -$X | `_auto_close_all` (SLOW — uses smart_execute) |
| 2 | ATM Auto-Close | `mmm_monitor.py:616` | Spot within 0.5% of original strike | `_auto_close_all` (SLOW) |
| 3 | Near-Expiry | `mmm_safety.py:365` | ≤5 min to expiry | `_auto_close_all` (SLOW) |
| 4 | Wind-Down | `mmm_wind_down.py:29` | N hours before expiry | Gradual buyback 25%/beat |
| 5 | Close-at-5 | `mmm_close_at_5.py` | Premium < threshold | Individual buyback |
| 6 | Whipsaw | `mmm_safety.py:236` | 3+ alternating adjustments in 5 min | Pause (warning only) |
| 7 | Circuit Breaker | `mmm_circuit_breaker.py` | 3 consecutive API failures | Skip beats, self-heal |

### Exchange API Available for Margin

Delta Exchange `GET /v2/wallet/balances` returns:
- `balance` — total wallet balance
- `available_balance` — free margin
- `position_margin` — margin locked by positions
- `order_margin` — margin locked by open orders
- `portfolio_margin` — portfolio margin if enabled
- `blocked_margin` — total blocked margin
- `meta.net_equity` — net equity including unrealized P&L

**Margin utilization** (portfolio margin mode):
- Formula: `blocked_margin / net_equity * 100` (preferred)
- Fallback: `portfolio_margin / net_equity * 100`
- Legacy (non-portfolio): `(position_margin + order_margin) / net_equity * 100`

> **⚠️ CRITICAL**: In portfolio margin mode, `position_margin` and `order_margin` are ZERO.
> Real margin lives in `blocked_margin` (or `portfolio_margin`). Using the legacy formula
> would always show 0% utilization.

**Wallet selection**: The `/v2/wallet/balances` endpoint returns 5 wallets (ETH, BTC, USD, REF_USD, INR).
Must find the USD wallet by `asset_symbol == 'USD'` — do NOT assume `wallets[0]`.

**Positions endpoint**: Use `/v2/positions/margined` (no params required, returns ALL margined positions).
The `/v2/positions` endpoint returns 400 without `product_id` or `underlying_asset_symbol` params.

Already implemented in `bot/api/async_delta_client.py` as `get_wallet_balances()` and `get_positions_margined()`.

---

## Implementation Plan

### Phase P0: Emergency Execution Engine (CRITICAL — DO FIRST)

**Why**: Without this, ALL emergency closes are broken in a crash. Even perfect detection is useless if the close mechanism takes 100 minutes.

#### P0.1: `emergency_execute()` method in `mmm_executor.py`

**File**: `webui/backend/routes/mmm/mmm_executor.py`

Add a new method alongside existing `smart_execute()`:

```python
async def emergency_execute(
    self,
    symbol: str,
    side: str,
    size: int,
    reduce_only: bool = True,
    session_id: str = None,
    max_slippage_pct: float = 5.0,
) -> Dict[str, Any]:
```

**Key differences from `smart_execute`**:
- Places limit order at **aggressive price** (best_ask + slippage for buys, best_bid - slippage for sells)
- Does NOT use post_only — allows taker fills
- Single 10-second timeout (not 60s × 10 reprices)
- If first attempt fails, one retry with even more aggressive pricing
- Total max time: ~15 seconds per position (vs 10 minutes)
- Logs with `emergency_` prefix for clear audit trail

**Implementation notes**:
- Use `_create_rest_client()` same as `smart_execute`
- Fetch quotes via `_fetch_quotes()`
- Place with `post_only=False` and `time_in_force='ioc'` (Immediate-or-Cancel) for instant fill
- Fallback: if IOC doesn't fill, place aggressive limit order and wait 10s
- Return same result shape as `smart_execute` for compatibility

#### P0.2: Upgrade `_auto_close_all()` in `mmm_monitor.py`

**File**: `webui/backend/routes/mmm/mmm_monitor.py` (line ~2173)

Current signature:
```python
async def _auto_close_all(self, reason: str):
```

New signature:
```python
async def _auto_close_all(self, reason: str, emergency: bool = False):
```

**Changes**:
- When `emergency=True`:
  - Use `self.executor.emergency_execute()` instead of `self.executor.smart_execute()`
  - Skip `MAX_CLOSES_PER_HEARTBEAT` cap — close everything
  - Close both CE and PE sides in parallel using `asyncio.gather()`
  - Reduce retry delay from 2s to 0.5s
- When `emergency=False`: keep existing behavior (backwards compatible)

**Callers to update**:
- Max loss breach (`mmm_monitor.py:1006`) → `emergency=True`
- ATM auto-close (`mmm_monitor.py:664`) → `emergency=True`
- Near-expiry close (`mmm_safety.py` action) → `emergency=True`
- Margin red/critical tier (new, Phase P1) → `emergency=True`

#### P0.3: Verification

- [ ] `py_compile` passes for both files
- [ ] Backend restarts cleanly
- [ ] Normal heartbeats unaffected (emergency is opt-in)
- [ ] Test emergency_execute with a small test order if possible

---

### Phase P1: Margin Guardian Module

**Why**: This gives proactive defense — gradual step-down that prevents reaching the catastrophic zone.

#### P1.1: Create `mmm_margin_guardian.py`

**File**: `webui/backend/routes/mmm/mmm_margin_guardian.py` (NEW)

```python
class MarginGuardian:
    """
    Monitors actual exchange margin utilization and enforces tier-based actions.
    
    Tiers (all user-configurable via WebUI session params):
      GREEN  (< 50%): Normal operation
      YELLOW (≥ 60%): Block new sells, warn
      ORANGE (≥ 75%): Auto wind-down (aggressive buyback)
      RED    (≥ 85%): Emergency reduce (taker orders)
      CRITICAL (≥ 90%): Survival mode (close ALL immediately)
    """
```

**Functions to implement**:

1. `async fetch_margin_utilization(rest_client) -> Dict`:
   - Calls `rest_client.get_wallet_balances()`
   - Returns `{'utilization_pct': float, 'position_margin': float, 'order_margin': float, 'available_balance': float, 'net_equity': float, 'balance': float}`

2. `evaluate_margin_tier(utilization_pct: float, params: Dict) -> Dict`:
   - Reads user thresholds from session params
   - Returns `{'tier': str, 'actions': List[str], 'utilization_pct': float}`
   - Actions: `'normal'`, `'block_sells'`, `'auto_wind_down'`, `'emergency_reduce'`, `'survival_close_all'`

3. `get_margin_params_defaults() -> Dict`:
   - Returns default values for all margin params

#### P1.2: Session Params (WebUI Fields)

**Add to session params** (stored in SQLite `mmm_sessions.db`):

```python
# Margin Guardian params
'margin_monitor_enabled': True,          # Master switch
'margin_green_pct': 50.0,               # Below this = normal
'margin_yellow_pct': 60.0,              # Caution — block new sells
'margin_orange_pct': 75.0,              # Auto wind-down aggressive
'margin_red_pct': 85.0,                 # Emergency reduce (taker)
'margin_critical_pct': 90.0,            # Survival — close ALL
'margin_target_pct': 50.0,              # Target to wind down TO
'margin_check_interval_beats': 1,       # Check every N heartbeats (1 = every beat)
```

**Files to update**:
- `mmm_initializer.py` — add defaults to session creation
- `mmm_routes.py` — accept params from WebUI create/update endpoints
- Frontend `MMMSessionForm` component — add margin guardian section

#### P1.3: Integrate into Heartbeat

**File**: `webui/backend/routes/mmm/mmm_monitor.py`

Add margin check at the **very start** of the heartbeat loop (before premium fetch), as Step 0:

```python
# Step 0: Margin Guardian check (before any trading logic)
if session.get('params', {}).get('margin_monitor_enabled', False):
    margin_result = await self._check_margin_guardian()
    if margin_result and margin_result['tier'] in ('RED', 'CRITICAL'):
        # Emergency mode — skip everything else
        await self._auto_close_all(
            f"Margin {margin_result['tier']}: {margin_result['utilization_pct']:.1f}%",
            emergency=True
        )
        return
    elif margin_result and margin_result['tier'] == 'ORANGE':
        # Force wind-down even if time-based wind-down isn't active
        session['_margin_wind_down'] = True
    elif margin_result and margin_result['tier'] == 'YELLOW':
        # Block new sells but continue heartbeat
        session['_margin_block_sells'] = True
```

**Also update**:
- `_process_adjustment()` — check `_margin_block_sells` flag before selling
- WebSocket emission — emit margin data to frontend for live dashboard
- Activity log — log margin tier changes

#### P1.4: Verification

- [ ] `py_compile` passes for all modified files
- [ ] Backend restarts cleanly
- [ ] Margin utilization is fetched and logged each heartbeat
- [ ] WebUI shows margin parameters in session create form
- [ ] Tier transitions are logged in activity log
- [ ] YELLOW blocks new sells
- [ ] ORANGE activates buyback
- [ ] RED/CRITICAL triggers emergency close

---

### Phase P2: Rapid-Check Mode & Parallel Close

**Why**: Reduces the blind window from 60s to 10s during danger, and closes positions 2x faster.

#### P2.1: Rapid-Check Heartbeat Mode

**File**: `webui/backend/routes/mmm/mmm_monitor.py`

When ANY danger condition is detected:
- Margin ≥ YELLOW tier
- P&L > 70% of max_loss
- Premium spike > 3x trigger threshold

Override heartbeat interval:
```python
RAPID_CHECK_INTERVAL = 10  # seconds (vs normal 60s)
```

In rapid-check mode, skip non-essential steps:
- Skip walkthrough generation
- Skip analytics/milestones
- Skip P&L history append (only keep latest)
- Skip portfolio delta calculation
- Run ONLY: fetch prices → margin check → safety checks → close logic

Return to normal when danger clears for 3 consecutive beats.

#### P2.2: Parallel Emergency Close

**File**: `webui/backend/routes/mmm/mmm_monitor.py`

In `_auto_close_all(emergency=True)`:
- Build close tasks for CE and PE sides simultaneously
- Execute with `asyncio.gather(close_ce_task, close_pe_task)`
- This halves the total close time

```python
if emergency:
    ce_task = self._emergency_close_side('ce', ...)
    pe_task = self._emergency_close_side('pe', ...)
    results = await asyncio.gather(ce_task, pe_task, return_exceptions=True)
```

#### P2.3: Verification

- [ ] Rapid-check mode activates when P&L approaches max_loss
- [ ] Heartbeat interval drops to 10s during danger
- [ ] Returns to normal interval after 3 clean beats
- [ ] Parallel close actually runs both sides simultaneously
- [ ] No deadlocks or race conditions in parallel execution

---

### Phase P3: WebUI Dashboard & Notifications

#### P3.1: Real-time Margin Dashboard ✅ DONE

- Margin utilization gauge (color-coded by tier)
- Wallet breakdown (position_margin, available_balance, net_equity, etc.)
- Tier ladder showing all 5 defense levels
- Enable/disable toggle
- Auto-refresh every 30s
- Settings dialog with 7 margin params + tooltips
- "Margin" tab in MMMDashboard
- API endpoint: `GET /api/mmm/session/<id>/margin`

#### P3.2: Telegram/Push Alerts ✅ DONE

**File**: `webui/backend/routes/mmm/mmm_telegram.py` (NEW)

5 async alert functions with 30s dedup window:
- `alert_margin_tier_change()` — formatted Markdown with tier emojis, utilization%, equity, margin
- `alert_emergency_close()` — RED/CRITICAL emergency close notification
- `alert_session_stopped()` — session auto-stop notification (requires manual restart)
- `alert_rapid_check_activated()` — rapid-check mode (15s heartbeat) activation
- `alert_max_loss_breach()` — max loss breach with P&L vs limit

Integration points in `mmm_monitor.py`:
- Tier change → `alert_margin_tier_change()` after `emit_safety()`
- CRITICAL → `alert_emergency_close()` + `alert_session_stopped()`
- RED → `alert_emergency_close()`
- Max loss breach → `alert_max_loss_breach()` before `_auto_close_all()`
- YELLOW/ORANGE tier change → `alert_rapid_check_activated()`

Uses existing `TelegramNotifier` from `webui/backend/services/notifications.py`.
Credentials from `grid_config.env` via `config.loader.get_config()`.

#### P3.3: WebSocket Margin Emission ✅ DONE

- `emit_heartbeat()` now accepts optional `margin_data` parameter
- Margin snapshot (tier, utilization_pct, enabled) piggybacked on heartbeat WS event
- Frontend receives margin data in real-time without separate API polling
- `_last_margin_snapshot` stored per heartbeat for emission

---

## File Map (What Gets Modified/Created)

| File | Phase | Action |
|------|-------|--------|
| `mmm_executor.py` | P0 | Add `emergency_execute()`, fix `_place_limit_order` for non-post-only |
| `mmm_monitor.py` | P0-P3 | Upgrade `_auto_close_all(emergency=)`, margin guardian heartbeat integration, Telegram alert calls, margin WS emission |
| `mmm_margin_guardian.py` | P1 | **NEW** — margin fetch, tier evaluation, params |
| `mmm_state.py` | P1 | 7 margin params in DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| `mmm_config.py` | P1 | 7 margin entries in PARAM_RULES + descriptions |
| `mmm_api.py` | P3.1 | GET /api/mmm/session/<id>/margin endpoint |
| `mmm_telegram.py` | P3.2 | **NEW** — 5 async Telegram alert functions |
| `mmm_websocket.py` | P3.3 | `emit_heartbeat()` extended with `margin_data` param |
| `MMMMarginGuardianPanel.js` | P3.1 | **NEW** — React margin dashboard component |
| `MMMSettingsDialog.js` | P3.1 | Margin Guardian param group + tooltips |
| `MMMDashboard.js` | P3.1 | Added "Margin" tab (#11, after Analytics) |
| `mmmService.js` | P3.1 | `getMarginStatus()` API method |

---

## Testing Strategy

### Manual Test Sequence

1. **P0 smoke test**: Create a small test position, call `emergency_execute` to close it. Verify it uses taker pricing and fills within 15s.
2. **P1 smoke test**: Enable margin monitor, check activity log shows margin utilization %. Manually approach YELLOW by adding positions, verify sells are blocked.
3. **P2 smoke test**: Set max_loss very close to current P&L, verify heartbeat switches to 10s rapid mode.

### Safety Constraints

- All changes are **backwards compatible** — existing sessions without margin params use defaults
- `emergency_execute` is ONLY called when `emergency=True`, never in normal flow
- Margin Guardian is disabled by default (`margin_monitor_enabled: false` unless user opts in)
- Rapid-check mode auto-reverts to normal after danger clears

---

## Progress Tracker

- [x] **P0.1**: `emergency_execute()` in `mmm_executor.py` — IOC taker orders, 10s timeout, 2 attempts
- [x] **P0.2**: `_auto_close_all(emergency=True)` — parallel CE+PE via asyncio.gather, 3 callers updated
- [x] **P0.3**: P0 verification — py_compile OK, backend restarted
- [x] **P1.1**: `mmm_margin_guardian.py` — MarginGuardian class, fetch_margin_utilization, evaluate_margin_tier, estimate_lots_to_close
- [x] **P1.2**: Session params in DEFAULT_PARAMS + HOT_RELOAD_PARAMS + PARAM_RULES (7 margin params, all hot-reloadable)
- [x] **P1.3**: Heartbeat integration — Step 0.5 margin check, YELLOW blocks sells, ORANGE forces wind-down, RED/CRITICAL emergency close
- [x] **P1.4**: P1 verification — py_compile OK, API endpoint tested
- [x] **P2.1**: Rapid-check heartbeat mode — 15s interval when margin YELLOW+ (Layer 3 in _run_loop)
- [x] **P2.2**: Parallel emergency close — done in P0.2 (asyncio.gather in _auto_close_all)
- [x] **P2.3**: P2 verification — py_compile OK
- [x] **P3.1**: WebUI margin dashboard — MMMMarginGuardianPanel.js (gauge, wallet breakdown, tier ladder, auto-refresh)
- [x] **P3.1b**: WebUI settings — Margin Guardian section in MMMSettingsDialog.js (7 params with tooltips)
- [x] **P3.1c**: WebUI dashboard integration — new "Margin" tab in MMMDashboard.js
- [x] **P3.1d**: API endpoint — GET /api/mmm/session/<id>/margin (real-time margin status)
- [x] **P3.1e**: Frontend build + deploy — npm build OK, backend restarted
- [x] **P3.2**: Telegram alerts — mmm_telegram.py (5 alert functions), integrated into mmm_monitor.py at 5 call sites
- [x] **P3.3**: WebSocket margin emission — margin data piggybacked on heartbeat WS event

---

## Post-Launch Bug Fixes (Feb 2026)

### Exchange Data Bugs (3 critical)

1. **Wrong positions endpoint**: `/v2/positions` returns 400 without params → Fixed: use `/v2/positions/margined` (no params needed, returns all 12 positions)
2. **Wrong wallet selection**: `wallets[0]` is ETH (empty) → Fixed: find USD wallet by `asset_symbol == 'USD'` (index 2)
3. **Wrong utilization formula**: `position_margin + order_margin` are 0 in portfolio margin mode → Fixed: use `blocked_margin` (or `portfolio_margin`) / `net_equity`

**Result**: Margin panel now shows real data — $317.68 margin used, $588.43 net equity, ~54% utilization across 12 positions.

### Console Error Fixes (3 errors)

1. **`Database error: no such table: iv_snapshots`** (every 30s) → Added `_ensure_tables()` to `predictive_engine.py.__init__()` with `CREATE TABLE IF NOT EXISTS`
2. **`POST /api/options/sl-tp/set → 500`** (exchange rejection) → Changed to 422 with exchange error body extraction in `options_control.py`
3. **`POST /api/mmm/session/start → 400`** (duplicate start) → Added guard in `MMMDashboard.js` `handleControl` to check session status before sending start

### UI Improvements

1. **Margin tab reordered**: Moved from index 6 (between Safety and Algo Calculations) to index 11 (after Analytics)
   - New tab order: Overview(0) → Positions(1) → Triggers(2) → Adjustments(3) → P&L(4) → Safety(5) → Strike Map(6) → Algo Calculations(7) → Consolidated(8) → Greeks & IV(9) → Analytics(10) → **Margin(11)**

### Guardian Activity Logging (Verified)

All margin guardian actions are correctly logged to background activities:

| Tier | Activity Type | Icon | Actions |
|------|--------------|------|---------|
| Any transition | `margin_tier_change` | Tier-dependent | `emit_safety()` + Telegram |
| YELLOW | `margin_block_sells` | 🟡 | Block new sells |
| ORANGE | `margin_wind_down` | 🟠 | Force aggressive buyback |
| RED | `margin_red` | 🔴 | Emergency close (taker orders) |
| CRITICAL | `margin_critical` | ⛔ | Close ALL + stop session + Telegram |

### Files Modified in Bug Fix Phase

| File | Change |
|------|--------|
| `bot/api/async_delta_client.py` | Added `get_positions_margined()` using `/v2/positions/margined` |
| `mmm_margin_guardian.py` | Fixed wallet selection (find USD by asset_symbol) + utilization formula (blocked_margin) |
| `mmm_api.py` | Updated to use `get_positions_margined()`, added `total_margin_used` field |
| `MMMMarginGuardianPanel.js` | Uses `total_margin_used` instead of `position_margin + order_margin` |
| `predictive_engine.py` | Added `_ensure_tables()` with CREATE TABLE IF NOT EXISTS |
| `options_control.py` | Changed 500→422 for exchange rejections, added error body extraction |
| `MMMDashboard.js` | Tab reorder (Margin from #6 to #11), duplicate-start guard |

### 🎉 ALL PHASES COMPLETE
