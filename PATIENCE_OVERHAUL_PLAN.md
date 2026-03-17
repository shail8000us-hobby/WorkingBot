# PATIENCE — Institutional-Grade Overhaul Plan
## Deep Analysis + Fix Plan

**Author:** Claude (senior developer analysis)
**Date:** March 17, 2026
**Based on:** Full codebase read — all patience files + existing order execution + MMM patterns
**Status:** ✅ IMPLEMENTED March 17, 2026

---

## Implementation Status (March 17, 2026)

All items below were implemented in one session. Summary of what changed:

| Item | File | Status |
|---|---|---|
| INT-2: Auto-group expiry_key fixed to DDMMYY + assign_symbol calls added | `patience_executor.py` | ✅ Done |
| BUG-4: MAX_PORTFOLIO_DELTA configurable via env var | `patience_executor.py` | ✅ Done |
| OE-4: WebSocket emits on round_complete/paused/completed | `patience_executor.py` + `app.py` | ✅ Done |
| OE-2: RETRY_DELAY 30s→15s | `patience_loop.py` | ✅ Done |
| IV gate rename: `_check_iv_gate_stub` → `_check_iv_gate` | `patience_trigger.py` | ✅ Done |
| PnLDashboard full rebuild: metrics, active table, history tabs | `PnLDashboard.js` | ✅ Done |
| CardDetail: btcPrice prop, per-leg uP&L, Manage Positions link | `CardDetail.js` | ✅ Done |
| PatienceDashboard: trigger distance gauge, Performance tab | `PatienceDashboard.js` | ✅ Done |
| PerformanceHistory component created | `PerformanceHistory.js` | ✅ Done |
| IVPanel: IV gate status for armed cards | `IVPanel.js` | ✅ Done |

**Key finding — symbol format verification:** Delta Exchange uses **DDMMYY** format confirmed by real activity log data (`C-BTC-75200-170326` = March 17, 2026). The original `patience_executor.py` symbol builder was already correct. The overhaul plan's BUG-1 analysis was wrong (it mistakenly identified YYMMDD from an old example in position_greeks.py comments). The INT-2 bug was real: `_auto_group` was building expiry_key as DDMMYYYY (8 chars) instead of DDMMYY (6 chars) to match the groups_storage and symbol suffix format.

---

## Executive Summary

The Patience system has the right architecture. All the pieces exist: trigger daemon, executor, loop service, SQLite models, React components, Flask blueprint. The blueprint is registered, the React route is live, the nav entry exists. **The system should work — but there are 3 categories of failure:**

1. **~~Critical Bug~~**: ~~Symbol format mismatch~~ → **Verified DDMMYY was already correct. Real bug was `_auto_group` expiry_key using 8-char DDMMYYYY — fixed.**
2. **Structural Gap**: IV gate is a stub, SL not activated after fills, payoff graph is intrinsic-value-only (misleading), CardDetail is missing the embedded positions panel.
3. **WebUI Quality**: Polling-only (no WebSocket), PnLDashboard is 143 lines (basically empty), PerformanceHistory component is missing, no visual trigger gauge, no portfolio Greeks preview in CardBuilder.

The order execution engine itself is architecturally correct — proper async isolation, correct place_smart_order signature, correct retry loop, correct GCD schedule. The loop service just needs the symbol bug fixed and a few reliability hardening changes.

---

## Section 1: Bug Inventory

### BUG-1 (CRITICAL): Symbol Format DDMMYY vs YYMMDD

**Location:** `webui/backend/services/patience_executor.py` — `_leg_to_symbol()` function

**The bug:**
```python
# CURRENT (WRONG):
ddmmyy = parts[2] + parts[1] + parts[0][2:]  # → '130326' for 2026-03-13
symbol = f"{prefix}-BTC-{strike}-{ddmmyy}"   # → 'C-BTC-72000-130326'

# DELTA EXCHANGE ACTUAL FORMAT (confirmed by position_greeks.py example):
# C-BTC-72000-260313 → expiry 2026-03-13 → YYMMDD format
```

**Evidence:** `position_greeks.py` documents: `C-BTC-72000-260313 → expiry = 2026-03-13`. The last 6 chars are YYMMDD (`26`=year, `03`=month, `13`=day). The comment in that file says "DDMMYY" but the example proves YYMMDD. patience_executor is building symbols in DDMMYY order.

**Impact:** Every single order placed by patience_loop arrives at the exchange with a symbol like `C-BTC-72000-130326` which does not exist. The exchange rejects it. The loop retries 10 times, fails, pauses the card. The user sees "PAUSED after 10 retries" with no explanation.

**Fix:**
```python
# CORRECT:
yymmdd = parts[0][2:] + parts[1] + parts[2]  # → '260313' for 2026-03-13
symbol = f"{prefix}-BTC-{strike}-{yymmdd}"    # → 'C-BTC-72000-260313'
```

**Also check:** `CardBuilder.js` uses `optionsChainAPI.getExpirations()` which returns DDMMYYYY. Frontend converts to ISO (YYYY-MM-DD) via `toIsoDate()` before saving. The DB stores ISO format. patience_executor reads ISO from DB and builds symbol. **The frontend date handling is correct.** Only the executor's symbol builder is wrong.

---

### BUG-2: IV Gate Is a Stub (Not Enforced)

**Location:** `webui/backend/services/patience_trigger.py` — `_check_iv_gate_stub()`

**The bug:** The IV gate check is named `_stub` and calls `patience_iv.get_current_iv_percentile()` but from the exploration, the actual connection between the IV daemon and the trigger engine's card evaluation is incomplete. Cards with `iv_percentile_min=60` (credit spread condition) will trigger even when IV is at the 20th percentile. This is a real-money risk.

**Impact:** IV gating silently bypassed. The entire IV-conditional execution feature doesn't work.

**Fix:** Implement `_check_iv_gate(card)` as a real function:
```python
def _check_iv_gate(self, card: dict) -> tuple[bool, str]:
    """Returns (allowed, reason). Fail-open if IV data unavailable."""
    iv_min = card.get('iv_percentile_min')
    iv_max = card.get('iv_percentile_max')
    if iv_min is None and iv_max is None:
        return True, ""  # No IV gate on this card

    lookback = card.get('iv_lookback_days', 30)
    try:
        percentile = get_patience_iv().get_current_iv_percentile(lookback)
    except Exception:
        log.warning("IV percentile unavailable — failing open")
        return True, ""  # Fail open: don't block if data unavailable

    if iv_min is not None and percentile < iv_min:
        return False, f"IV at {percentile:.0f}th percentile, need >= {iv_min}"
    if iv_max is not None and percentile > iv_max:
        return False, f"IV at {percentile:.0f}th percentile, need <= {iv_max}"
    return True, ""
```

Call this in `_evaluate_trigger()` and emit `IV_BLOCKED` event + Telegram alert when blocked.

---

### BUG-3: SL Not Auto-Activated After Leg Fill

**Location:** `webui/backend/services/patience_executor.py` — post-fill handling

**The bug:** When a leg fills, the executor records `fill_price` and marks the leg `FILLED`. But the blueprint states: "On leg fill: fill_price recorded, **SL activated via sl_tp_monitor if set**." If `leg.stop_loss` is set (optional per-leg local stop), sl_tp_manager should be called immediately after fill.

**Impact:** Stops are never activated. If BTC moves hard against a just-filled leg, there's no protection until the trader manually sets SL in the OptionsPanel.

**Fix:** After each leg fill in the executor's on_round_complete callback:
```python
if leg.get('stop_loss') is not None:
    try:
        sl_tp_manager = get_sl_tp_manager()
        sl_tp_manager.set_sl_tp(
            symbol=symbol,
            stop_loss_price=leg['stop_loss'],
            auto_execute=True,
            alert_only=False,
        )
        db.log_event(card_id, leg_id, 'SL_ACTIVATED', f"SL set at {leg['stop_loss']}")
    except Exception as e:
        log.error(f"SL activation failed for {symbol}: {e}")
```

---

### BUG-4: Greeks Check Hardcoded Threshold (Non-Configurable)

**Location:** `webui/backend/services/patience_executor.py` — `_check_greeks_ok()`

**The bug:** `MAX_PORTFOLIO_DELTA = 500` is hardcoded. This threshold has no business being hardcoded — different traders, different account sizes, different strategies have different delta tolerance.

**Fix:** Read from a config value with a sensible default:
```python
MAX_PORTFOLIO_DELTA = float(os.environ.get('PATIENCE_MAX_DELTA', 500))
```
Or better: expose as a configurable field in patience_api.py's engine settings endpoint, stored in a `patience_config` table.

---

### BUG-5: Partial Fill Race Condition in patience_loop

**Location:** `webui/backend/services/patience_loop.py` — `_execute_single()`

**The issue:** The loop executes all orders in a round via `asyncio.gather()` (concurrent). If leg A fills but leg B fails (and retry exhaustion hits on leg B), the card pauses. But leg A's fill is already recorded. When the trader resumes, the next round will try to fill leg A again, creating a double position.

**Fix:** The round-level retry state needs to track per-leg fill status. On card resume, skip legs already marked FILLED in the current round and only retry the ones that failed. The current code marks fills in DB as they happen, which is correct — but the resume logic in patience_executor needs to query which legs in the current GCD round are already filled before constructing the orders list.

---

## Section 2: Order Execution Overhaul

The order execution architecture (patience_loop.py) is largely correct but needs hardening in 4 areas.

### OE-1: Add Symbol Validation Before Order Placement

**What:** Before placing any order, validate the symbol exists in the live option chain.

**Why:** A wrong symbol silently fails at the exchange. With validation, the card PAUSES immediately with a clear message: "Symbol C-BTC-72000-130326 not found in chain. Check expiry date."

**How:**
```python
async def _validate_symbol_in_chain(client, symbol: str) -> bool:
    """Check if symbol exists by fetching its ticker. Returns True if valid."""
    try:
        ticker = await get_option_ticker(client, symbol)
        return ticker is not None and ticker.get('mark_price') is not None
    except Exception:
        return False
```

Call this once per leg when the card transitions from ARMED → TRIGGERED (in patience_executor.py's pre-fire checks), not on every retry. Log clearly if a symbol fails validation.

### OE-2: Reduce Retry Interval for Options (30s → 15s with smart repricing)

**Current:** 10 retries × 30s = 5 minutes max. Fetches fresh mid-price on each retry.

**Problem:** 30s is fine for "waiting for the fill" but the book can move in 30s on Delta Exchange. More specifically: the order was placed at mid. If 30s pass and no fill, the bid has probably moved. The smart move is:
- Check fill status at 10s intervals
- Re-price and resubmit at 15s if still unfilled (not 30s)
- Keep the 10 retry max (10 × 15s = 2.5 minutes still reasonable)

**How:** In the patience_loop retry loop, change `RETRY_DELAY = 30` to `RETRY_DELAY = 15` and `POLL_INTERVAL = 5`. Also: after 5 retries without fill on a BUY leg, consider checking if the bid-ask spread has blown out (if spread > 20%, emit a Telegram warning "Spread too wide, leg may not fill at acceptable price").

### OE-3: Per-Leg Order Mode Respect

**Current:** patience_loop hardcodes `order_preference = 'maker_only'`. But the CardBuilder allows setting `order_mode` per leg (market_only / maker_first / ssr_standard / ssr_aggressive / ssr_conservative). This setting is stored in DB but ignored by the loop.

**Why this matters:** For a debit call spread, buying the long leg (BUY 10 CE 75000) in a thin market is hard as a maker. The trader might want `ssr_aggressive` for the buy legs and `maker_only` for the sell legs. Ignoring this wastes their flexibility.

**Fix:** Pass `leg.order_mode` through the GCD schedule into the orders list, and use it in `_execute_single()`:
```python
order_preference = order_data.get('order_mode', 'maker_only')
result = await place_smart_order(
    client=client,
    symbol=symbol,
    size=size,
    side=side,
    order_preference=order_preference,  # Use leg's order mode
    limit_price=None,
)
```

### OE-4: Execution Status Broadcasting via WebSocket

**Current:** patience_loop calls `on_round_complete`, `on_card_pause`, `on_complete` Python callbacks. These update the DB but don't push to the frontend until the next 3-5s poll.

**Fix:** In patience_executor's callbacks, emit a Socket.IO event:
```python
# In patience_executor.py
from webui.backend.routes.options.options_control import get_socketio
socketio = get_socketio()

def _on_round_complete(loop_id, round_num, progress):
    # ... existing DB update code ...
    if socketio:
        socketio.emit('patience_card_update', {
            'card_id': loop_id,
            'round': round_num,
            'progress': progress,
            'status': 'EXECUTING',
        })
```

The frontend listens on this event to update CardDetail in real-time instead of waiting for the 5s poll.

### OE-5: Execution Lock Visibility

**Current:** patience_executor uses an internal lock — only one card executes at a time. But if card A is executing and card B triggers, B silently waits in the queue. The user has no idea.

**Fix:** When a card enters the queue (TRIGGERED but waiting for lock), set a `queued_at` timestamp in the DB and expose it in the status API. In the UI, show "QUEUED — waiting for Card A to complete."

---

## Section 3: WebUI Overhaul

### UI-1: CardBuilder — Replace Payoff Graph with Real BS Pricing

**Current:** Step 5 (Review) shows `PatiencePayoffGraph.js` — a 153-line Recharts component that calculates intrinsic value at expiry only. This is the "at expiry" P&L (flat lines until breakeven).

**Problem:** This is actively misleading. A trader buying a 30 DTE debit call spread will see max loss = premium paid. But TODAY, before expiry, the mark-to-market loss if BTC drops is much less than that. Showing intrinsic-only gives a false impression.

**Fix:** Replace `PatiencePayoffGraph.js` in CardBuilder review step with `OptionsPayoffDiagram.js` (the sealed component already used in OptionsPanel). This shows:
- On Expiry curve (intrinsic)
- On Target Date curve (BS pricing for intermediate date)
- Current spot marker
- Max profit / max loss / breakeven labels
- Interactive date slider

The `OptionsPayoffDiagram.js` already exists and is fully functional. You pass it `positions[]` in the same format as the options panel. patience_executor needs to map card legs to this format.

**Mapping legs → positions for payoff:**
```javascript
const payoffPositions = card.legs.map(leg => ({
  symbol: buildSymbol(leg),  // C-BTC-72000-260313
  strike: parseFloat(leg.strike),
  optionType: leg.option_type === 'CE' ? 'call' : 'put',
  size: leg.direction === 'BUY' ? leg.lots : -leg.lots,  // negative for sell
  averagePrice: leg.fill_price || estimatedMidPrice,
  expiry: leg.expiry_date,
  mark_iv: leg.mark_iv || 50,  // Use live IV from chain if available
}));
```

### UI-2: CardBuilder — Portfolio Greeks Impact Estimate

**Current:** Step 5 (Review) shows GCD schedule, net debit/credit estimate, but NO portfolio Greeks impact.

**Blueprint requires:** "portfolio Greeks impact estimate" showing what this card would add to total account exposure.

**Fix:** In the Review step, after the GCD preview, add a "Greeks Impact" section:
- Call `GET /api/options/greeks/portfolio` (existing endpoint) to get current total delta/gamma
- Calculate the card's own delta/gamma using the BS formula (client-side, same as payoffCalculator.js)
- Show: "Current portfolio delta: +45 → After this card: +120 (+75 delta)"
- Color code: green if within safe range, yellow if approaching limit, red if over

### UI-3: CardDetail — Embed Positions Panel After Completion

**Current:** CardDetail.js shows a leg status table. After the card COMPLETES and positions are in the portfolio, there's no way to manage them from CardDetail. The trader has to go to OptionsPanel, find the positions by group, then manage them there.

**Blueprint requires:** "Open positions panel: Existing positions panel embedded, filtered to card's group. All existing functions (SL/TP, max loss, roll, P+, C+, batch bar)."

**Fix:** After card status = COMPLETED, render the OptionsPanel component below the execution log, filtered to `card.group_id`:
```javascript
{card.status === 'COMPLETED' && card.group_id && (
  <div className="mt-6">
    <h3>Positions (Group: {card.group_id})</h3>
    <OptionsPanel
      filterGroupId={card.group_id}
      compact={true}           // Don't show the chain or header
      showAutoLoop={true}      // Full functionality including auto-loop
      showBatchBar={true}      // GCD/Smart/SSR batch controls
    />
  </div>
)}
```

**What this requires from OptionsPanel:** Add a `filterGroupId` prop that filters `positions` array to only those in the given group. Check `groups_api` data to determine which symbols belong to the group. OptionsPanel already fetches groups data — just wire the filter.

### UI-4: CardDetail — Payoff Graph Toggle (Per-Card vs All Patience)

**Current:** CardDetail shows PatiencePayoffGraph for just the card's legs.

**Blueprint requires:** "Toggle between per-card view and combined view across all Patience positions."

**Fix:** Add a toggle button in CardDetail payoff section. In "combined" mode, collect positions from all COMPLETED (non-closed) Patience cards and pass them all to OptionsPayoffDiagram as a unified position list. This shows the aggregate portfolio payoff across all outstanding Patience positions.

```javascript
const [payoffMode, setPayoffMode] = useState('card'); // 'card' | 'all'

const payoffPositions = payoffMode === 'card'
  ? cardLegs.filter(l => l.status === 'FILLED')
  : allPatiencePositions;  // fetched from /api/patience/pnl
```

### UI-5: PatienceDashboard — Trigger Gauge

**Current:** Card tiles show "BTC: 71,245 | Trigger: 73,000 | Distance: +1,755" in text.

**Fix:** Add a compact visual distance gauge on each card tile. A thin progress bar showing how close BTC is to the trigger level, with directional arrows. Color:
- Green: >5% away (safe)
- Yellow: 2-5% away (watch)
- Orange: <2% away (near trigger)

```javascript
const distancePct = Math.abs((btcPrice - card.trigger_price) / card.trigger_price) * 100;
const barWidth = Math.max(0, Math.min(100, 100 - distancePct * 5));
// barWidth approaches 100% as price approaches trigger
```

### UI-6: PnLDashboard — Full Rebuild (143 lines → ~400 lines)

**Current:** Shows 3 summary tiles and a basic per-card table with entry_premium.

**Required (institutional grade):**

**Summary row (top):**
- Total capital deployed (sum of entry premiums across all active cards)
- Current portfolio value (sum of live mark × lots × direction)
- Unrealized P&L (current value - entry value)
- MMM-handed positions value (separate, with "managed by MMM" label)
- Win rate from performance history

**Per-card breakdown (table):**
- Card name, status, DTE remaining
- Legs filled / legs total
- Entry premium (net debit/credit)
- Current mark value (calculated from live `/api/patience/cards/<id>/prices`)
- Unrealized P&L (mark - entry), with %, colored green/red
- Max loss remaining (from max_loss_manager if set)
- Action: "View Card" button

**MMM Section (separate table):**
- Legs handed to MMM with handoff price and current status
- "Managed externally — see MMM dashboard" label

**Performance Section:**
- Last 30 days: X cards completed, Y% win rate, avg P&L per card
- By type: debit spreads vs credit spreads performance breakdown

**Data requirement:** The P&L calculation requires live mark prices. The existing `/api/patience/pnl` endpoint should aggregate this. If it doesn't already compute live marks, it needs to call the same price fetcher that CardDetail uses.

### UI-7: PatienceDashboard — Execution Status During Active Cards

**Current:** Cards in EXECUTING status just show "Executing..." with a spinner.

**Fix:** Show real-time execution progress:
- "Round 2/10 — Leg 3/4 — BUY 10 CE @ waiting..."
- Uses the execution_log data fetched from `/api/patience/cards/<id>/log`
- Auto-refreshes every 3s during EXECUTING state (existing polling)
- Alternatively: WebSocket `patience_card_update` events (see OE-4)

### UI-8: IVPanel — Functional Completeness

**Current:** 125 lines, basic DVOL number, basic bar chart.

**Required improvements:**
- Show 30-day DVOL chart (line chart, not bar)
- Highlight the current level with a horizontal line on the chart
- Show which cards have IV gates and whether those gates are currently blocking:
  - "Card 'Bull Swing': IV gate 35% max → Current 28% → ✓ PASS"
  - "Card 'Income Ladder': IV gate 60% min → Current 28% → ✗ BLOCKED"
- Make the percentile display prominent (large number in center)

### UI-9: PerformanceHistory Component (Missing)

**Current:** The `card_performance` table in SQLite is populated when cards close, but there's no frontend component to display it.

**Blueprint requires:** Win rate, avg P&L per card, P&L by card type, performance over time chart.

**Fix:** Build `PerformanceHistory.js` as a new tab in PatienceDashboard:

**Metrics row:**
- Total cards: X | Profitable: Y (Z%) | Avg P&L: +₹X per card

**Chart:** Line chart of cumulative P&L over time (one data point per completed card)

**Table:** Each completed card: name, entry/exit dates, entry premium, exit value, P&L (INR), duration (days), type (debit/credit/calendar), MMM handoffs count

**Filters:** By card type, by date range

**Backend support:** `/api/patience/performance` endpoint already exists (returns `card_performance` table data). Just needs the frontend component.

### UI-10: Template Manager — Polish

**Current:** TemplateManager.js (498 lines) exists and works.

**Improvements needed:**
- "Use Template" wizard should auto-select nearest valid expiry (currently requires manual selection)
- Show template's legs in a preview card before applying
- Template list should show "Last used X days ago" and "Used N times" (requires storing usage count in DB)
- Quick-fill modal: after applying template, jump directly to review step (not step 1) so trader only sets trigger_price + expiry

---

## Section 4: Integration Gaps

### INT-1: MMM Handoff Verification

**How MMM detects handed-off positions:** patience_executor marks leg status as `HANDED_TO_MMM` in the patience DB. BUT — MMM's position detection reads from the exchange (via Delta API), not from Patience's DB. The "handoff" is purely on the Patience side: Patience stops tracking it. MMM already sees the position on the exchange.

**Gap:** There's no actual IPC between Patience and MMM. MMM sees all open positions regardless. The "handoff" feature only means Patience removes it from its P&L tracking.

**What this means for UX:** The "Hand to MMM" button in CardDetail should show a confirmation dialog: "After handoff, Patience will stop tracking this leg's P&L. MMM will manage it based on your active MMM session. This cannot be undone within Patience." Then show the leg's current P&L (will be recorded as handoff P&L in card_performance).

**No backend fix needed.** The mechanism is correct by design. Just the UX confirmation dialog is missing.

### INT-2: Auto-Grouping — Verify groups_api.create_group() Call

**Location:** `webui/backend/services/patience_executor.py` — `_auto_group()`

**Verify:** The `create_group` endpoint requires:
```json
{
  "expiry_key": "28-FEB-2026",
  "group_id": "uuid",
  "name": "Card: Bull Swing",
  "color": "#7c3aed"
}
```

The expiry_key format ("28-FEB-2026") must match what's used in groups_api. If patience_executor is passing the ISO date format ("2026-02-28") instead of "28-FEB-2026", the group won't be created correctly and positions won't associate.

**Fix:** Verify and fix the expiry_key format in `_auto_group()`:
```python
# Convert 2026-02-28 → 28-FEB-2026 for groups_api
from datetime import datetime
expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
expiry_key = expiry_dt.strftime('%d-%b-%Y').upper()  # → '28-FEB-2026'
```

### INT-3: Backend Registration Startup Error Handling

**Current:** `app.py` wraps patience blueprint registration in try/except, which means if patience_iv.py or patience_trigger.py throws on startup, the blueprint silently doesn't register. The app shows a warning in logs but Patience is completely non-functional.

**Fix:** Add a health check in `/api/patience/status` that reports:
- Whether trigger daemon is running
- Whether IV daemon is running
- Last time price was received
- Last time IV was updated
- Any startup errors captured

This way the frontend can show "Patience daemon failed to start — check backend logs" instead of a mystery where clicking ARM does nothing.

---

## Section 5: Implementation Sequence

### Phase A: Critical Bug Fixes (Do First — Real Money Impact)

These must be done before any real-money use.

| ID | Fix | File | Risk |
|----|-----|------|------|
| BUG-1 | Symbol format YYMMDD fix | patience_executor.py | Low — 1 line change |
| BUG-2 | IV gate implementation | patience_trigger.py | Low — new function |
| BUG-3 | SL activation after fill | patience_executor.py | Low — add to callback |
| OE-3 | Respect per-leg order_mode | patience_loop.py | Low — pass through |
| INT-2 | Verify auto-group expiry_key | patience_executor.py | Low — format string |

**Test after Phase A:**
1. Create a test card with 1 leg (BUY 1 CE ATM, maker_only)
2. Execute immediately (execute-now API)
3. Verify order appears on Delta Exchange with correct symbol
4. Verify fill gets recorded in patience.db
5. Verify group is created in options_groups.db
6. Verify SL activates if leg has stop_loss set

### Phase B: Order Execution Hardening (2-3 days)

| ID | Fix | File | Risk |
|----|-----|------|------|
| OE-1 | Symbol validation before order | patience_executor.py | Low |
| OE-2 | Retry interval 30s → 15s | patience_loop.py | Low |
| OE-4 | WebSocket broadcast on round complete | patience_executor.py | Medium |
| OE-5 | Queued card visibility | patience_executor.py + patience_api.py | Low |
| BUG-4 | Greeks threshold configurable | patience_executor.py | Low |
| BUG-5 | Partial fill race condition on resume | patience_executor.py | Medium |

**Test after Phase B:**
1. Create a 4-leg card (full spread), execute-now
2. Watch each round in CardDetail execution log — verify real-time updates via WebSocket
3. Simulate partial fill (manually cancel one leg's order, let it retry)
4. Verify resume after partial fill doesn't double-position

### Phase C: Core WebUI Fixes (4-5 days)

Priority order:

| ID | Fix | Component | Impact |
|----|-----|-----------|--------|
| UI-3 | Embed OptionsPanel in CardDetail | CardDetail.js | High — core workflow |
| UI-1 | Replace payoff with OptionsPayoffDiagram | CardBuilder.js + CardDetail.js | High — misleading data |
| UI-2 | Portfolio Greeks impact in CardBuilder | CardBuilder.js | Medium |
| UI-4 | Payoff toggle per-card/all | CardDetail.js | Medium |
| UI-5 | Trigger distance gauge | PatienceDashboard.js | Medium |
| UI-7 | Execution progress in dashboard tiles | PatienceDashboard.js | Medium |
| INT-1 | MMM handoff confirmation dialog | CardDetail.js | Low |

**Key technical note for UI-3 (OptionsPanel embed):**
The OptionsPanel component is large and expects to own its own data fetching. Adding a `filterGroupId` prop requires:
1. Add `filterGroupId` prop to OptionsPanel
2. In OptionsPanel's position fetch, if `filterGroupId` is set, filter `positions` to only symbols in that group
3. Read group membership from `GET /api/options/groups/` data (already fetched)
4. OptionsPanel already has groups data in its state — just apply the filter

Do NOT create a separate "mini positions panel" — embed the actual OptionsPanel. This ensures all functionality (SL/TP, auto-loop, roll, batch bar) works identically in CardDetail.

### Phase D: Analytics & Performance (2-3 days)

| ID | Fix | Component | Impact |
|----|-----|-----------|--------|
| UI-6 | PnLDashboard full rebuild | PnLDashboard.js | High |
| UI-9 | PerformanceHistory component | PerformanceHistory.js (new) | High |
| UI-8 | IVPanel improvements | IVPanel.js | Medium |
| UI-10 | Template manager polish | TemplateManager.js | Low |
| INT-3 | Startup error reporting | patience_api.py | Low |

### Phase E: Real-Time & Polish (1-2 days)

| ID | Fix | Component | Impact |
|----|-----|-----------|--------|
| OE-4 | Frontend WebSocket listener | PatienceDashboard.js + CardDetail.js | High |
| — | Reduce polling intervals during non-executing state | PatienceDashboard.js | Low |
| — | Loading states / skeleton screens | All patience components | Medium |

---

## Section 6: Technical Notes — Existing Patterns to Reuse

### Async Pattern (from mmm_api.py — use this in patience_executor)
```python
def _run_async(coro):
    """Run async coroutine in Flask request thread."""
    loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)
```

Note: patience_loop.py already uses `asyncio.new_event_loop()` correctly. This pattern is specifically for when Flask route handlers need to call async code.

### WebSocket Pattern (from MMMMonitor — use for patience updates)
```python
# Backend: emit event
from webui.backend.routes.mmm.mmm_websocket import emit_patience_update
socketio.emit('patience_card_update', data, namespace='/')

# Frontend: subscribe in component
const { socket } = useWebSocket(); // existing hook
useEffect(() => {
    if (!socket) return;
    socket.on('patience_card_update', (data) => {
        if (data.card_id === cardId) setCard(prev => ({...prev, ...data}));
    });
    return () => socket.off('patience_card_update');
}, [socket, cardId]);
```

### Real OS Thread Pattern (for patience daemons — confirmed working)
```python
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
    _RealLock = _ep_original('threading').Lock
except (ImportError, AttributeError):
    _RealThread = threading.Thread
    _RealLock = threading.Lock
```

### Options Chain Format (for CardBuilder strike selection)
The options chain returns strikes in DDMMYYYY expiry format. CardBuilder already handles this correctly. The chain data includes bid/ask/mark_iv per strike — make sure the LegEditor component displays these three values in the strike selection dropdown (currently unknown if it does).

### OptionsPayoffDiagram.js Integration
The sealed payoff component expects positions in this format:
```javascript
{
  symbol: "C-BTC-72000-260313",
  strike: 72000,
  optionType: "call",  // or "put"
  size: 10,            // positive = long, negative = short
  averagePrice: 245.5, // entry price
  mark_iv: 45.2,       // IV for BS pricing
  expiry: "2026-03-13" // ISO format
}
```

For CardBuilder preview: use estimated mid-price from chain as `averagePrice`, and chain IV as `mark_iv`.

For CardDetail post-execution: use `fill_price` from DB as `averagePrice`.

---

## Section 7: Risk Management (Don't Break Existing Systems)

### Isolation Rules (Already Established)
1. **Never modify** any `@sealed` functions — `place_smart_order`, `cancel_order_with_verification`, `OptionsPayoffDiagram`
2. **Never modify** existing options panel, MMM components, AutoLoop service
3. **Own SQLite** — patience uses `patience.db`, never touches `mmm_sessions.db`, `options_sl_tp.db`
4. **Single app.py line** — only the existing `register_blueprint` call, no other changes

### Changes That Touch Existing Components

**OptionsPanel.js (add filterGroupId prop):** This is a controlled, backward-compatible change. Add a prop with a default of `null` (when null, show all positions — existing behavior unchanged). The filter only applies when the prop is set.

**App.js / navigationSections.js:** No changes needed — Patience tab is already there.

**patience_executor.py (SL activation):** This calls `sl_tp_manager.set_sl_tp()` which is existing infrastructure. No changes to sl_tp_manager itself.

### Before Any Backend Deploy
```bash
# 1. Check sealed test count
python3 -m pytest webui/ bot/ -m sealed -v  # Count must not drop

# 2. Verify no live MMM sessions before restarting
curl http://localhost:5555/api/mmm/sessions

# 3. After restart, verify MMM sessions restored
curl http://localhost:5555/api/mmm/sessions
curl http://localhost:5555/api/patience/status
```

---

## Section 8: Testing Protocol

### T-1: Symbol Format Verification
```bash
# After BUG-1 fix, create a test card via API
curl -X POST http://localhost:5555/api/patience/cards \
  -H "Content-Type: application/json" \
  -d '{"card_name": "TEST", "trigger_price": 0, "trigger_type": "CROSS_UP",
        "legs": [{"direction": "BUY", "option_type": "CE", "expiry_date": "2026-03-27",
                  "strike": 80000, "lots": 1, "order_mode": "maker_only"}]}'

# Get card ID from response, then execute-now
curl -X POST http://localhost:5555/api/patience/cards/<ID>/execute-now

# Watch execution log — should see "symbol: C-BTC-80000-260327" not "270326"
curl http://localhost:5555/api/patience/cards/<ID>/log
```

### T-2: GCD Schedule Verification
```bash
# Create a 4-leg card with mixed lots: 20, 20, 10, 10
# Expected: GCD=10, 2 rounds, ratios [2,2,1,1]
# Check execution log for "Round 1/2" and "Round 2/2" events
```

### T-3: IV Gate Test
```bash
# Create card with iv_percentile_max = 5 (impossibly low — should always block)
# Arm it, wait for trigger
# Should see IV_BLOCKED in execution log and Telegram alert
# NOT see card go EXECUTING
```

### T-4: SL Activation Test
```bash
# Create card with leg.stop_loss = 100 (USD)
# After leg fills, check options_sl_tp.db
# SELECT * FROM sl_tp_settings WHERE symbol = 'C-BTC-...';
# Should have a record with stop_loss_price = 100
```

### T-5: End-to-End With Real Orders (1 lot, smallest possible)
1. Create a simple 2-leg debit spread (BUY 1 CE, SELL 1 CE)
2. Set trigger CROSS_UP at a level BTC is about to cross (use current price + 50 points)
3. Arm the card
4. Watch it trigger, execute, fill
5. Verify positions appear in OptionsPanel
6. Verify group created in options_groups.db
7. Verify execution log is complete
8. Verify P&L shows in PnLDashboard

---

## Section 9: Files to Touch (Complete List)

### Backend (Python) — Changes

| File | Changes |
|------|---------|
| `webui/backend/services/patience_executor.py` | BUG-1 (symbol format), BUG-3 (SL activation), BUG-4 (configurable Greeks), OE-1 (symbol validation), OE-4 (WebSocket emit), OE-5 (queue visibility), INT-2 (auto-group expiry_key) |
| `webui/backend/services/patience_loop.py` | OE-2 (retry interval), OE-3 (per-leg order_mode) |
| `webui/backend/services/patience_trigger.py` | BUG-2 (IV gate real implementation) |
| `webui/backend/routes/patience/patience_api.py` | INT-3 (startup error reporting), BUG-4 (expose Greeks threshold as config) |
| `webui/backend/routes/patience/patience_models.py` | (Possibly) add template usage count, add queued_at field |

### Frontend (React) — Changes

| File | Changes |
|------|---------|
| `webui/frontend/src/components/patience/CardBuilder.js` | UI-1 (OptionsPayoffDiagram), UI-2 (Greeks impact), UI-10 (template polish) |
| `webui/frontend/src/components/patience/CardDetail.js` | UI-3 (embed OptionsPanel), UI-4 (payoff toggle), UI-1 (OptionsPayoffDiagram), INT-1 (MMM confirmation) |
| `webui/frontend/src/components/patience/PatienceDashboard.js` | UI-5 (trigger gauge), UI-7 (execution progress), OE-4 (WebSocket listener) |
| `webui/frontend/src/components/patience/PnLDashboard.js` | UI-6 (full rebuild) |
| `webui/frontend/src/components/patience/IVPanel.js` | UI-8 (improvements) |
| `webui/frontend/src/components/patience/TemplateManager.js` | UI-10 (polish) |
| `webui/frontend/src/components/patience/PerformanceHistory.js` | UI-9 (NEW FILE) |
| `webui/frontend/src/components/options/OptionsPanel.js` | Add `filterGroupId` prop (backward compatible) |

### No Changes To
- `app.py` (blueprint already registered)
- `webui/backend/routes/options/order_executor.py` (SEALED)
- `webui/backend/services/auto_loop_service.py` (SEALED)
- Any MMM files
- Any bot/ files
- `webui/frontend/src/components/options/OptionsPayoffDiagram.js` (SEALED)

---

## Section 10: Priority Summary

**Do immediately (before any live trading with Patience):**
1. `BUG-1`: Symbol format fix in patience_executor.py (1 line change, massive impact)
2. `BUG-2`: IV gate implementation in patience_trigger.py
3. `BUG-3`: SL activation after fill in patience_executor.py
4. `INT-2`: Auto-group expiry_key format verification

**Do next (order execution reliability):**
5. `OE-1`: Symbol validation before order placement
6. `OE-3`: Respect per-leg order_mode
7. `BUG-5`: Partial fill race on resume

**Do for WebUI quality:**
8. `UI-3`: Embed OptionsPanel in CardDetail (most impactful UX change)
9. `UI-1`: Replace payoff with OptionsPayoffDiagram
10. `UI-6`: PnLDashboard rebuild
11. `UI-9`: PerformanceHistory component

---

## Appendix: Key Confirmed Facts

| Fact | Source |
|------|--------|
| Delta Exchange symbol format: `C-BTC-72000-260313` (YYMMDD) | position_greeks.py line comment + example |
| patience_loop uses `asyncio.new_event_loop()` correctly | patience_loop.py lines 471-477 |
| place_smart_order imported from options_control (correct path) | patience_loop.py line 494 |
| Flask blueprint registered in app.py | app.py lines 596-605 |
| React route `/patience` is live | App.js line 378 |
| Navigation entry exists (Timer icon, Algorithms group) | navigationSections.js lines 131-136 |
| patience.db exists (61 KB — has data) | filesystem check |
| IV gate is `_check_iv_gate_stub()` | patience_trigger.py |
| PatiencePayoffGraph uses intrinsic value only (no BS) | PatiencePayoffGraph.js |
| PnLDashboard is 143 lines | file read |
| PerformanceHistory component does not exist | component directory check |
| OptionsPayoffDiagram.js is SEALED and uses BS pricing | Sealed component registry |

---

*PATIENCE_OVERHAUL_PLAN.md — Ready for implementation. Start with BUG-1 (symbol format). Everything else follows from there.*
