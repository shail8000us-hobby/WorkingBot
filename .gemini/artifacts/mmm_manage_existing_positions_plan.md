# MMM: Plan to Manage Already-Existing Open Positions

> **Goal:** Allow MMM to adopt and manage BTC 0DTE options positions that **already exist on Delta Exchange** — positions that were opened manually, by another algo, or by a previous MMM session that crashed/stopped — without requiring the user to manually type in every detail.

> **Status:** PLAN ONLY — no code changes.

---

## 1. Problem Statement

### Current Limitations

Today, MMM has two entry modes:

| Mode | How It Works | Limitation |
|------|-------------|------------|
| **Fresh** | User specifies desired premium → algo auto-finds strikes → sells new positions | Only works for new positions. Cannot adopt existing ones. |
| **Import** | User manually types CE strike, PE strike, fill price, lots | **1 CE strike + 1 PE strike only**. Same lot count on both sides. User must know exact fill prices. No auto-discovery. |

**Real-world scenarios Import mode cannot handle:**

1. **Multi-strike positions:** User has CE positions at 98000 AND 99000 (from prior adjustments or manual sells) — Import only accepts one CE strike.
2. **Asymmetric lots:** User has 10 CE lots and 25 PE lots — Import forces same lot count on both sides.
3. **Unknown fill prices:** User sold at market, doesn't remember exact fill — must guess, leading to wrong P&L tracking.
4. **Crashed sessions:** An MMM session was running, the backend crashed, and on restart, `init_mmm()` can't restore because the session JSON was corrupted or the session was STOPPED. The positions are still open on exchange but orphaned.
5. **Multiple frozen positions:** User has positions at 3-4 different strikes from prior adjustments. Import gives no way to capture these — they'd be invisible to loss calculations.

### Desired Outcome

A new **"Adopt Existing Positions"** mode that:
- **Auto-discovers** open BTC options positions from Delta Exchange
- Lets the user **select which positions** to bring under MMM management
- Handles **multiple strikes per side** (mapping to active + frozen)
- Handles **asymmetric lots** (different lot counts CE vs PE)
- Uses **actual exchange entry prices** (no guessing)
- Sets up correct **trigger snapshots** using current premiums
- Produces a **valid, running MMM session** identical to one that had been running all along

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   NEW COMPONENTS                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Backend:                                                │
│    mmm_api.py      → GET  /api/mmm/exchange-positions    │
│                    → POST /api/mmm/session/<id>/adopt     │
│    mmm_adopter.py  → NEW MODULE (~300 lines)             │
│      • fetch_exchange_btc_options()                      │
│      • classify_positions(positions, expiry)             │
│      • build_session_state(classified, params)           │
│      • validate_adoptable(classified)                    │
│                                                          │
│  Frontend:                                               │
│    MMMAdoptPanel.js → NEW COMPONENT (~400 lines)         │
│      • Exchange position browser                         │
│      • Side assignment (CE/PE)                           │
│      • Active vs frozen designation                      │
│      • Preview & confirm flow                            │
│    MMMConfigPanel.js → Add "Adopt" as 4th mode           │
│    mmmService.js     → Add 2 new API calls               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Plan

### Phase 1: Backend — Exchange Position Discovery

**File: `mmm_api.py`** — New endpoint

#### 3.1 `GET /api/mmm/exchange-positions`

**Purpose:** Fetch all open BTC options positions from Delta Exchange, formatted for the adopt UI.

**Query Params:**
- `expiry` (optional) — filter to a specific expiry (DDMMYYYY)
- `underlying` (optional, default `BTC`)

**Logic:**
1. Call Delta Exchange `GET /v2/positions/margined` (same as existing `_get_positions_from_delta()` in `routes/positions.py`)
2. Filter to options only (symbol contains `C-` or `P-`)
3. Filter to BTC only
4. Filter to SHORT positions only (`size < 0`) — MMM only sells
5. Optionally filter by expiry
6. For each position, fetch current mark price from `/v2/tickers/{symbol}`
7. Return structured data:

```json
{
  "success": true,
  "positions": [
    {
      "symbol": "C-BTC-98000-180226",
      "product_id": 123456,
      "side": "CE",
      "strike": 98000,
      "expiry": "18022026",
      "size": -15,
      "lots": 15,
      "entry_price": 245.50,
      "mark_price": 180.30,
      "unrealized_pnl": 0.98,
      "iv": 62.5,
      "delta": -0.35,
      "theta": 12.5
    },
    {
      "symbol": "P-BTC-92000-180226",
      "side": "PE",
      "strike": 92000,
      "expiry": "18022026",
      "size": -20,
      "lots": 20,
      "entry_price": 310.00,
      "mark_price": 280.00,
      "unrealized_pnl": 0.60,
      "iv": 58.2,
      "delta": 0.28,
      "theta": 15.0
    }
  ],
  "spot_price": 96500.00,
  "expiries_with_positions": ["18022026", "19022026"]
}
```

**Key decisions:**
- Only show **short** positions (MMM is a premium-selling algo)
- Show ALL open short options, not just 0DTE — user picks the expiry
- Include Greeks and IV so user has full context
- Group/sort by expiry → side → strike for easy browsing

---

### Phase 2: Backend — Position Classification & State Building

**File: `mmm_adopter.py`** — New module (~300 lines)

#### 3.2 `classify_positions(selected_positions, user_config)`

**Purpose:** Take the user's selected positions and classify them into the MMM state model.

**Input:**
```python
selected_positions = [
    {"symbol": "C-BTC-98000-...", "strike": 98000, "lots": 15, "entry_price": 245.50, "role": "active"},
    {"symbol": "C-BTC-99000-...", "strike": 99000, "lots": 5, "entry_price": 120.00, "role": "frozen"},
    {"symbol": "P-BTC-92000-...", "strike": 92000, "lots": 20, "entry_price": 310.00, "role": "active"},
    {"symbol": "P-BTC-91000-...", "strike": 91000, "lots": 8, "entry_price": 180.00, "role": "frozen"},
]
user_config = {
    "expiry": "18022026",
    "params": { ... }
}
```

**Logic:**

1. **Separate by side:** CE (calls) vs PE (puts)
2. **Identify active strike per side:**
   - If user designated one strike as "active" → use that
   - If auto-mode → pick the strike **closest to ATM** as active (it's the one most likely being monitored)
   - Rule: Exactly ONE active strike per side; all others become frozen
3. **Build per-side state:**

   For CE side with active strike 98000 and frozen at 99000:
   ```python
   ce_state = {
       'original_lots': 15,          # Lots at active strike
       'original_premium': 245.50,   # Entry price at active strike
       'original_strike': 98000,
       'active_strike': 98000,
       'adjustment_fills': [],        # No adjustments yet (these are "original" adopted lots)
       'adjustment_total_lots': 0,
       'adjustment_avg': 0,
       'frozen_positions': [
           {'strike': 99000, 'lots': 5, 'entry_premium': 120.00}
       ],
       'frozen_total_lots': 5,
       'active_lots': 15,
       'total_lots': 20,
       'trigger_snapshot': {
           '98000': <current_mark_price>   # Set to CURRENT premium, not entry
       },
       'symbol': 'C-BTC-98000-180226',
   }
   ```

4. **Set trigger snapshots to current premiums:**
   - This is critical. Setting triggers to current prices means: "everything up to NOW is accepted as the starting state."
   - The algo will only trigger adjustments if premiums **rise further** from the adoption point.
   - Alternative (rejected): Setting triggers to entry prices would cause immediate triggering if premiums have already risen significantly.

5. **Calculate initial P&L:**
   - `total_premium_collected = sum(entry_price × lots × LOT_SIZE_BTC)` for all positions
   - `unrealized_pnl` = computed from entry_price vs current mark_price

#### 3.3 `validate_adoptable(classified)`

**Purpose:** Run sanity checks before allowing adoption.

**Checks:**
- [ ] At least 1 CE and 1 PE position selected (MMM requires both sides)
- [ ] All positions are SHORT (size < 0)
- [ ] All positions share the same expiry
- [ ] No position is already managed by another active MMM session (cross-reference `mmm_sessions.json`)
- [ ] Active strike lots > 0 on both sides
- [ ] Total lots per side ≤ `max_lots_per_side` parameter
- [ ] Positions actually exist on exchange (re-verify before committing)

**Returns:**
```python
{
    "valid": True/False,
    "warnings": [
        "CE lots (15) ≠ PE lots (20) — asymmetric position",
        "Frozen CE position at 99000 has only 5 lots — low hedge value",
    ],
    "errors": [
        "Position C-BTC-98000-... is already managed by session mmm18feb26-1",
    ],
    "summary": {
        "ce_total_lots": 20,
        "pe_total_lots": 28,
        "ce_strikes": [98000, 99000],
        "pe_strikes": [92000, 91000],
        "total_premium_collected": 12.45,
        "current_unrealized_pnl": 3.21,
    }
}
```

---

### Phase 3: Backend — Adopt Endpoint

**File: `mmm_api.py`** — New endpoint

#### 3.4 `POST /api/mmm/session/<id>/adopt`

**Purpose:** Adopt exchange positions into an existing IDLE session.

**Request Body:**
```json
{
  "positions": [
    {
      "symbol": "C-BTC-98000-180226",
      "strike": 98000,
      "lots": 15,
      "entry_price": 245.50,
      "role": "active",
      "side": "CE"
    },
    {
      "symbol": "C-BTC-99000-180226",
      "strike": 99000,
      "lots": 5,
      "entry_price": 120.00,
      "role": "frozen",
      "side": "CE"
    },
    {
      "symbol": "P-BTC-92000-180226",
      "strike": 92000,
      "lots": 20,
      "entry_price": 310.00,
      "role": "active",
      "side": "PE"
    }
  ],
  "expiry": "18022026",
  "trigger_mode": "current_prices"
}
```

**`trigger_mode` options:**
| Mode | Behavior | When to use |
|------|----------|-------------|
| `current_prices` (default) | Triggers set to current mark prices | Position just opened or user wants a clean slate |
| `entry_prices` | Triggers set to original entry prices | Position opened recently, premiums haven't moved much |
| `custom` | User provides custom trigger values | Advanced — user knows what baseline they want |

**Logic:**
1. Validate session exists and is IDLE
2. Call `classify_positions()` to build the state
3. Call `validate_adoptable()` — reject if any errors
4. Fetch current premiums for all strikes (for trigger snapshots)
5. Build the full session state using `build_session_state()`
6. Set `session['entry_mode'] = 'adopt'`
7. Set `session['adopted_at'] = datetime.utcnow().isoformat()`
8. Store a snapshot of what was adopted (for audit):
   ```python
   session['adoption_snapshot'] = {
       'positions_adopted': [...],
       'trigger_mode': 'current_prices',
       'premiums_at_adoption': {'98000_call': 180.3, '92000_put': 280.0},
       'spot_at_adoption': 96500.0,
   }
   ```
9. Save session, emit WebSocket events
10. Return success — session is now IDLE and ready to START

**Response:**
```json
{
  "success": true,
  "session_id": "mmm18feb26-1",
  "adopted": {
    "ce_active": {"strike": 98000, "lots": 15},
    "ce_frozen": [{"strike": 99000, "lots": 5}],
    "pe_active": {"strike": 92000, "lots": 20},
    "pe_frozen": [],
    "total_premium_collected": 12.45,
    "trigger_mode": "current_prices"
  },
  "warnings": ["CE lots (20) ≠ PE lots (20) — asymmetric position"]
}
```

---

### Phase 4: Backend — State Model Adjustments

**File: `mmm_state.py`**

#### 3.5 Changes needed

1. **`initialize_side_from_entry()`** — Currently sets `original_lots` and a single trigger snapshot. For adopt mode, we need a new function:

   **New function: `initialize_side_from_adoption(session, side, active_position, frozen_positions, trigger_premium)`**

   ```python
   def initialize_side_from_adoption(
       session: Dict,
       side: str,           # 'ce' or 'pe'
       active_strike: float,
       active_lots: int,
       active_entry_premium: float,
       frozen_positions: List[Dict],  # [{'strike': ..., 'lots': ..., 'entry_premium': ...}]
       trigger_premium: float,        # Current premium for trigger snapshot
       symbol: str,
   ) -> Dict:
   ```

   This function:
   - Creates the side state via `create_side_state()`
   - Sets `original_lots`, `original_premium`, `original_strike`, `active_strike`
   - Populates `frozen_positions` list directly
   - Sets `trigger_snapshot` to the provided trigger premium
   - Calls `recompute_side_lots()` to compute `active_lots`, `total_lots`
   - Sets `symbol`

2. **`create_session()`** — Add `mode='adopt'` as a valid option (cosmetic, for logging)

3. **No changes to the heartbeat loop, engine, trigger, safety, or any runtime modules** — Once the state is correctly populated, adopt-mode sessions behave identically to import-mode sessions. This is the key insight: all we need is correct state initialization.

---

### Phase 5: Frontend — Adopt Panel UI

**File: `MMMAdoptPanel.js`** — New component (~400 lines)

#### 3.6 UI Flow

```
Step 1: [Fetch Exchange Positions]
   └── Click "Scan Exchange" button
   └── Endpoint: GET /api/mmm/exchange-positions?expiry=...
   └── Show a table of all open short BTC options positions

Step 2: [Select Positions]
   └── Table columns: ☑ | Side | Strike | Lots | Entry$ | Mark$ | P&L | IV | Delta
   └── User checks the positions they want MMM to manage
   └── Dropdown per row: "Active" or "Frozen"
   └── Auto-suggest: closest-to-ATM CE = active, closest-to-ATM PE = active

Step 3: [Review & Configure]
   └── Show adoption summary:
       ┌──────────────────────────────────────────────┐
       │  CE Side                                     │
       │    Active: 98000 × 15 lots @ $245.50 entry   │
       │    Frozen: 99000 × 5 lots  @ $120.00 entry   │
       │                                              │
       │  PE Side                                     │
       │    Active: 92000 × 20 lots @ $310.00 entry   │
       │                                              │
       │  Trigger Mode: [Current Prices ▾]            │
       │  Total Premium Collected: $12.45             │
       │  Current Unrealized P&L:  +$3.21             │
       │                                              │
       │  ⚠ CE lots (20) ≠ PE lots (20)              │
       └──────────────────────────────────────────────┘

Step 4: [Confirm & Adopt]
   └── Click "Adopt Positions" button
   └── Endpoint: POST /api/mmm/session/<id>/adopt
   └── Session transitions to IDLE (initialized, ready to START)
   └── User clicks START → heartbeat begins managing the adopted positions
```

#### 3.7 Auto-classification Heuristics

When user selects multiple positions on the same side, the UI should **auto-suggest** active vs frozen:

| Heuristic | Rule |
|-----------|------|
| **Closest to ATM** | Strike nearest to current BTC spot → **Active** |
| **Most lots** | If ambiguous, the one with more lots → **Active** |
| **Highest premium** | If still ambiguous, highest current premium → **Active** (more liquid, more meaningful to monitor) |
| **User override** | User can always override with the dropdown |

Rationale: The "active" strike is what MMM monitors for triggers and adjusts against. It should be the one with the most exposure and closest to the action.

---

### Phase 6: Frontend — Integration

**File: `MMMConfigPanel.js`**

#### 3.8 Add 4th Mode

Currently has 3 modes: Auto-Find / Manual Select / Import Existing.

Add: **"Adopt from Exchange"** as the 4th mode.

```
Mode selector: [Auto-Find] [Manual Select] [Import Existing] [Adopt from Exchange]
```

When "Adopt from Exchange" is selected:
- Render `<MMMAdoptPanel sessionId={...} />`
- Expiry dropdown should still be shown (to filter exchange positions)

**File: `mmmService.js`**

#### 3.9 New API Methods

```javascript
// Fetch open short BTC options from exchange
getExchangePositions(expiry = null) {
    const params = expiry ? { expiry } : {};
    return axios.get('/api/mmm/exchange-positions', { params });
}

// Adopt selected positions into a session
adoptPositions(sessionId, positions, expiry, triggerMode = 'current_prices') {
    return axios.post(`/api/mmm/session/${sessionId}/adopt`, {
        positions, expiry, trigger_mode: triggerMode,
    });
}
```

---

### Phase 7: Edge Cases & Safety

#### 3.10 Edge Cases to Handle

| Edge Case | Handling |
|-----------|----------|
| **Position closed between scan and adopt** | Re-verify all positions exist on exchange during `adopt` endpoint, before committing. Return error with details on which positions vanished. |
| **Position partially closed** | Compare lot count at scan vs adopt time. If lots decreased, warn user and use current lot count. |
| **Only CE or only PE positions** | Reject — MMM requires both sides. Show error: "MMM requires at least one CE and one PE position." |
| **All positions at same strike** | Valid — set it as active, no frozen needed. This is the simplest case. |
| **Multiple expiries selected** | Reject — MMM manages one expiry at a time. UI should filter by expiry before adoption. |
| **Position already in another MMM session** | Check all active sessions for overlap. Reject with: "Position at strike X is already managed by session Y." |
| **Session already initialized** | Only allow adopt for IDLE sessions. If already initialized (has positions), require the user to delete and recreate, or add a "re-adopt" confirmation. |
| **Very large lot count** | Warn if total lots exceed `max_lots_per_side` parameter. Allow adoption but set the safety cap. |
| **LONG positions found** | Filter out during scan; don't show them. MMM only manages short positions. |
| **Zero entry price from exchange** | Rare but possible for old positions. Flag as warning, let user manually enter. |

#### 3.11 Cross-Session Safety

**Critical:** Prevent two MMM sessions from managing the same position.

Implementation:
1. On adopt, iterate all sessions in `mmm_sessions.json`
2. For each RUNNING/PAUSED session, collect all managed symbols (active + frozen)
3. If any selected position's symbol matches → **reject** with clear error
4. Store `managed_symbols` set in session state for fast lookup

---

### Phase 8: Trigger Initialization Strategy

This is the most important design decision for adopt mode.

#### 3.12 Options Analysis

| Strategy | Trigger Value | Effect | Risk |
|----------|--------------|--------|------|
| **A: Current Prices** | `trigger_snapshot = current_mark_price` | Algo monitors from NOW. Any further premium increase triggers adjustment. | None — conservative. Like starting fresh at this moment. |
| **B: Entry Prices** | `trigger_snapshot = entry_fill_price` | Algo treats all movement since entry as "already happened." Only triggers if premium rises above entry. | If premium has ALREADY risen significantly, the algo immediately triggers, causing a potentially large adjustment on the very first heartbeat. **Dangerous.** |
| **C: Custom** | User-provided values | Full control. Advanced users can set exactly where they want the trigger threshold. | Requires deep understanding of the algo. |
| **D: Auto-Balanced** | `trigger_snapshot = midpoint(entry, current)` | Compromise between A and B. | Somewhat arbitrary; doesn't map to any real "covered up to here" level. |

**Recommended default: Strategy A (Current Prices)**

Rationale:
- The user is telling MMM: "Take over management from this point."
- Current prices represent the truth: the user accepted all P&L up to this moment.
- The trigger system means "losses above this level need to be hedged." Setting it to current prices means "no losses above this level yet."
- Strategy B is dangerous because a position that's already 100 points underwater would immediately fire a massive adjustment.

Provide Strategy B and C as options for advanced users via the `trigger_mode` parameter.

---

### Phase 9: Files Changed Summary

| File | Change Type | Estimated Lines |
|------|------------|----------------|
| `mmm_adopter.py` | **NEW FILE** | ~300 |
| `mmm_api.py` | Add 2 endpoints | ~150 |
| `mmm_state.py` | Add `initialize_side_from_adoption()` | ~50 |
| `MMMAdoptPanel.js` | **NEW FILE** | ~400 |
| `MMMConfigPanel.js` | Add 4th mode tab | ~20 |
| `mmmService.js` | Add 2 API methods | ~15 |
| `mmm/index.js` | Export new component | ~2 |
| `AI_MMM_CONTEXT.md` | Document adopt mode | ~50 |

**Total: ~990 lines of new/modified code**

**Zero changes to:**
- `mmm_monitor.py` (heartbeat loop)
- `mmm_engine.py` (adjustment math)
- `mmm_trigger.py` (trigger evaluation)
- `mmm_safety.py` (safety checks)
- `mmm_close_at_5.py` (close logic)
- `mmm_wind_down.py` (wind-down)
- `mmm_reversal.py` (reversal detection)
- `mmm_strike_shift.py` (strike shifting)
- `mmm_executor.py` (order execution)
- `mmm_websocket.py` (WebSocket events)

This is possible because **all runtime behavior depends only on session state**, not on how the state was created. Once adopt mode produces a correctly structured session state dict, all existing runtime modules work unchanged.

---

## 4. Implementation Order

```
1. mmm_adopter.py          ← Pure logic, no dependencies, testable in isolation
2. mmm_state.py changes    ← Small, initialize_side_from_adoption()
3. mmm_api.py endpoints    ← Wire up backend
4. mmmService.js           ← Wire up frontend API
5. MMMAdoptPanel.js        ← Build the UI
6. MMMConfigPanel.js       ← Add 4th mode tab
7. Testing                 ← Unit tests + manual E2E test
8. AI_MMM_CONTEXT.md       ← Document
```

---

## 5. Testing Plan

### Unit Tests (`test_mmm_adopter.py`)
- [ ] `test_classify_single_ce_single_pe` — simplest case
- [ ] `test_classify_multi_strike_ce` — 2 CE strikes, auto-classifies active/frozen
- [ ] `test_classify_asymmetric_lots` — different CE/PE lot counts
- [ ] `test_validate_missing_ce_side` — error when no CE selected
- [ ] `test_validate_mixed_expiry` — error when positions span expiries
- [ ] `test_validate_duplicate_session` — error when position already managed
- [ ] `test_trigger_mode_current_prices` — verifies trigger = current, not entry
- [ ] `test_trigger_mode_entry_prices` — verifies trigger = entry fill price
- [ ] `test_full_adoption_produces_valid_state` — adopted session matches schema expected by monitor

### Manual E2E Test
1. Have 2+ short BTC options open on Delta Exchange
2. Create new MMM session
3. Go to Config Panel → "Adopt from Exchange"
4. See positions listed, select them, assign active/frozen
5. Confirm adoption
6. Click START — heartbeat begins
7. Verify:
   - Premiums are fetched correctly for all strikes
   - Trigger gauges show correct baselines
   - Consolidated positions table shows all adopted positions
   - P&L tracking is accurate from adoption point
   - Safety checks run on the full position (including frozen)
   - If a trigger fires, adjustment executes correctly

---

## 6. Future Enhancements (Out of Scope for v1)

| Enhancement | Description |
|-------------|-------------|
| **Auto-adopt on crash recovery** | When `init_mmm()` finds a RUNNING session with no active monitor, auto-scan exchange and reconcile state |
| **Partial adoption** | Adopt only CE side, let algo auto-find PE, or vice versa |
| **Live sync** | Periodically reconcile adopted positions with exchange (already exists in `_reconcile_exchange_positions`, just needs better error recovery) |
| **Adopt from order history** | Look at filled orders to reconstruct entry prices if positions endpoint doesn't have them |
| **Multi-session adopt** | Split a large portfolio across multiple MMM sessions for different risk profiles |
