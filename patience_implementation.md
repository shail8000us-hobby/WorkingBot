# PATIENCE — Phase-Wise Implementation Plan

**Based on:** PATIENCE_BLUEPRINT.md v2.2 FINAL
**Codebase research date:** March 14, 2026
**Principle:** Zero impact on any existing trading function. Every existing file is read-only except one line in `app.py` and one section in React nav.

---

## Codebase Research Findings (Pre-Implementation)

### Critical signatures locked in

| What | Where | Signature |
|------|-------|-----------|
| Place order | `routes/options/order_executor.py` | `async place_smart_order(client, symbol, size, side, order_preference, reduce_only, limit_price)` — already supports `'maker_only'` as `order_preference` |
| Cancel order | `routes/options/order_executor.py` | `async cancel_order_with_verification(client, order_id, max_retries=3)` |
| Autoloop | `services/auto_loop_service.py` | `start_loop(self, loop_id, orders, total_rounds, order_preference)` — accepts `'maker_first'` or `'market_only'` ONLY. **This is why patience_loop.py must be a copy.** |
| BTC price | `services/delta_price_websocket.py` | `get_price_websocket().get_price('BTC')` → `float \| None`. Staleness: check `is_connected()` |
| Portfolio Greeks | `options_strategy/position_greeks.py` | `enrich_positions_with_greeks(positions: List[Dict], spot_price: float)` → adds `pos_greeks` dict to each position. Sum delta/gamma across positions for portfolio total. |
| Telegram | `bot/options/notifications/options_notifier.py` | `get_options_notifier().send(text: str, skip_dedup: bool = False)` |
| Group create | `routes/options/groups_api.py` | POST `/api/options/groups/create` with `{expiry_key, group_id, name, color}` |
| SL/TP | `options_strategy/sl_tp_manager.py` | `SLTPManager(db_path)` — SQLite-backed. Set via its own methods. |
| Guardian | `data/guardian_signal.json` (may not exist) | Also checked via callable. Pattern: read JSON, check `signal == "STOP"`. If file absent → assume GO. |
| Payoff calc | `frontend/src/components/options/payoffCalculator.js` | `blackScholesPrice(S, K, T, r, sigma, type)`, `calculateImpliedVolatility(...)`, `getContractMultiplier(symbol)` — SEALED, import only |
| Nav structure | `frontend/src/App.js` | React Router v6, lazy-loaded pages, `buildSections` config in `src/config/navigationSections` |
| Polling pattern | `frontend/src/components/options/OptionsPanel.js` | `useVisibilityAwarePolling` hook — use the same pattern |
| Autoloop context | `frontend/src/context/AutoloopContext.js` | Context + Provider — Patience uses its own simpler polling, not this context |
| Blueprint pattern | `routes/mmm/mmm_api.py` | `mmm_bp = Blueprint('mmm', __name__, url_prefix='/api/mmm')`, `_run_async()` helper for async routes |

### Single-touch existing files

| File | Change | Risk |
|------|--------|------|
| `webui/backend/app.py` | Add `from .routes.patience import patience_bp` + `app.register_blueprint(patience_bp)` | Near-zero. Blueprint isolated. |
| `webui/frontend/src/App.js` | Add lazy import + route entry | Near-zero. New route only. |
| `webui/frontend/src/config/navigationSections.js` | Add Patience tab entry | Near-zero. Additive. |

**Everything else: new files only.**

---

## File Map — New Files to Create

```
webui/backend/routes/patience/
├── __init__.py                    # Blueprint export
├── patience_api.py                # All REST endpoints (card CRUD, templates, IV, perf, handoff)
└── patience_models.py             # SQLite data access layer (patience.db)

webui/backend/services/
├── patience_trigger.py            # Trigger engine daemon thread
├── patience_executor.py           # Card → GCD schedule → patience_loop handoff
├── patience_loop.py               # COPY of auto_loop_service.py, maker_only hardcoded
├── patience_iv.py                 # DVOL collector + percentile calc
└── gcd_batch.py                   # GCD lot-sizing utility (shared)

webui/frontend/src/components/patience/
├── PatienceDashboard.jsx          # List + chain tree view, live ticker, controls
├── CardBuilder.jsx                # Wizard: expiry → trigger → IV gate → legs → chain → preview → arm
├── CardDetail.jsx                 # Execution log + positions panel + payoff + MMM handoff
├── IVPanel.jsx                    # DVOL percentile chart
├── PnLDashboard.jsx               # Real-time capital summary across all cards
├── PerformanceHistory.jsx         # Win/loss tracking, card P&L history
├── TemplateManager.jsx            # Save/load card templates
├── ChainTreeView.jsx              # Visual parent-child dependency tree
└── patienceService.js             # API client (axios calls to /api/patience/*)

webui/frontend/src/pages/
└── PatiencePage.js                # Page wrapper (lazy-loaded route target)
```

---

## Phase 1 — Core Backend Engine

**Goal:** SQLite up, card CRUD works, trigger fires, GCD execution runs via patience_loop with real orders.
**Duration estimate:** 3–4 days
**Deliverable:** `POST /api/patience/cards` → arm → BTC hits trigger → patience_loop places maker_only orders in GCD rounds.

---

### Step 1.1 — SQLite schema + models (`patience_models.py`)

Create `patience.db` with these tables. All UUIDs generated in Python (`uuid.uuid4()`).

**Table: `scenario_cards`**
```sql
CREATE TABLE IF NOT EXISTS scenario_cards (
    card_id TEXT PRIMARY KEY,
    card_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    parent_card_id TEXT,
    trigger_price REAL NOT NULL,
    trigger_type TEXT NOT NULL,           -- TOUCH|CROSS_UP|CROSS_DOWN|SUSTAIN
    trigger_tolerance REAL DEFAULT 50,
    sustain_minutes INTEGER,
    iv_percentile_min REAL,
    iv_percentile_max REAL,
    iv_lookback_days INTEGER DEFAULT 30,
    created_at TEXT NOT NULL,
    triggered_at TEXT,
    completed_at TEXT,
    group_id TEXT,
    template_id TEXT
);
```

**Table: `card_legs`**
```sql
CREATE TABLE IF NOT EXISTS card_legs (
    leg_id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES scenario_cards(card_id),
    leg_order INTEGER NOT NULL,
    direction TEXT NOT NULL,              -- BUY|SELL
    option_type TEXT NOT NULL,            -- CE|PE
    expiry_date TEXT NOT NULL,
    strike REAL,
    lots INTEGER NOT NULL,
    is_relative_strike INTEGER DEFAULT 0,
    relative_offset REAL,
    post_only INTEGER DEFAULT 1,
    order_mode TEXT DEFAULT 'maker_only', -- maker_only|ssr|ssr_aggressive
    stop_loss REAL,
    mmm_handoff_eligible INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING|EXECUTING|FILLED|FAILED|CANCELLED|HANDED_TO_MMM
    fill_price REAL,
    filled_at TEXT
);
```

**Table: `card_templates`**
```sql
CREATE TABLE IF NOT EXISTS card_templates (
    template_id TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_tolerance REAL DEFAULT 50,
    iv_percentile_min REAL,
    iv_percentile_max REAL,
    iv_lookback_days INTEGER DEFAULT 30,
    legs_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

**Table: `dvol_history`**
```sql
CREATE TABLE IF NOT EXISTS dvol_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    dvol_value REAL NOT NULL
);
```

**Table: `execution_log`**
```sql
CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    leg_id TEXT,
    event_type TEXT NOT NULL,  -- TRIGGER_HIT|IV_BLOCKED|GREEKS_BLOCKED|ROUND_START|LEG_FILL|LEG_FAIL|COMPLETE|PAUSE|MMM_HANDOFF
    message TEXT,
    data_json TEXT,
    created_at TEXT NOT NULL
);
```

**Table: `card_performance`**
```sql
CREATE TABLE IF NOT EXISTS card_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT,
    entry_premium REAL,
    exit_value REAL,
    pnl REAL,
    duration_hours REAL,
    card_type TEXT,
    legs_handed_to_mmm INTEGER DEFAULT 0,
    handoff_pnl REAL,
    closed_at TEXT
);
```

**`patience_models.py` public interface:**
```python
class PatienceDB:
    def __init__(self, db_path="data/patience.db"): ...

    # Cards
    def create_card(self, card: dict) -> str: ...           # returns card_id
    def get_card(self, card_id: str) -> dict | None: ...
    def get_cards_by_status(self, *statuses) -> list: ...
    def update_card(self, card_id: str, **fields) -> None: ...
    def delete_card(self, card_id: str) -> None: ...

    # Legs
    def create_leg(self, leg: dict) -> str: ...
    def get_legs(self, card_id: str) -> list: ...
    def update_leg(self, leg_id: str, **fields) -> None: ...

    # Templates
    def save_template(self, tpl: dict) -> str: ...
    def get_templates(self) -> list: ...
    def get_template(self, template_id: str) -> dict | None: ...
    def delete_template(self, template_id: str) -> None: ...

    # Execution log
    def log_event(self, card_id, leg_id, event_type, message, data=None) -> None: ...
    def get_log(self, card_id: str) -> list: ...

    # DVOL
    def insert_dvol(self, timestamp: str, value: float) -> None: ...
    def get_dvol_history(self, days: int = 30) -> list: ...

    # Performance
    def save_performance(self, perf: dict) -> None: ...
    def get_performance(self) -> list: ...

# Singleton
_db: PatienceDB | None = None
def get_db() -> PatienceDB: ...
```

---

### Step 1.2 — GCD utility (`gcd_batch.py`)

Pure math, no external dependencies. Shared utility.

```python
from math import gcd
from functools import reduce

def compute_gcd(numbers: list[int]) -> int:
    """GCD of a list of integers."""
    return reduce(gcd, numbers)

def compute_gcd_schedule(legs: list[dict]) -> dict:
    """
    Input:  legs = [{'leg_id': ..., 'lots': 20, ...}, ...]
    Output: {
        'gcd': 10,
        'total_rounds': 2,
        'per_round': [
            {'leg_id': ..., 'lots_this_round': 2, ...},
            ...
        ]
    }
    """
    lots_list = [leg['lots'] for leg in legs]
    g = compute_gcd(lots_list)
    ratios = [l // g for l in lots_list]
    total_rounds = max(lots_list) // g
    per_round = [
        {**leg, 'lots_this_round': ratios[i]}
        for i, leg in enumerate(legs)
    ]
    return {
        'gcd': g,
        'total_rounds': total_rounds,
        'per_round': per_round
    }
```

No imports from existing code. Fully self-contained.

---

### Step 1.3 — `patience_loop.py` (copy of `auto_loop_service.py`)

**Source:** `webui/backend/services/auto_loop_service.py` — copy verbatim, then apply these diffs only:

1. Rename class: `AutoLoopService` → `PatienceLoopService`
2. Rename singleton getter: `get_auto_loop_service()` → `get_patience_loop_service()`
3. Change `start_loop()` signature: remove `order_preference` parameter — hardcode `maker_only`
4. Inside `_run_loop()`: wherever `order_preference` is passed to `place_smart_order`, replace with `'maker_only'`
5. Change default `post_only=True` for every order placed (pass through existing `limit_price` parameter in `place_smart_order` — already supports this)
6. On 10 retry exhaustion (not present in original? check): add PAUSE card logic + Telegram alert instead of falling back to market
7. Module docstring: `"PatienceLoopService — maker_only execution engine for PATIENCE. Copy of AutoLoopService v[date]. Original untouched."`

**Original file stays sealed and untouched.**

Import in `patience_executor.py`: `from .patience_loop import get_patience_loop_service`

---

### Step 1.4 — Trigger engine daemon (`patience_trigger.py`)

Daemon thread, Flask app context, singleton. Same architecture as `AutoLoopService`.

```python
class PatienceTrigger:
    POLL_INTERVAL = 1.0          # seconds
    STALE_THRESHOLD = 30         # seconds before price considered stale

    def start(self): ...          # start daemon thread
    def stop(self): ...
    def _run(self): ...           # main loop

    def _check_armed_cards(self, cards): ...
    def _evaluate_trigger(self, card, current_price, prev_price) -> bool: ...
    def _check_iv_gate(self, card, current_percentile) -> bool: ...
    def _check_price_freshness(self) -> bool: ...
    def _queue_for_execution(self, card): ...

def get_patience_trigger() -> PatienceTrigger: ...   # singleton
```

**Main loop logic:**
```
every 1 second:
  1. get current price from get_price_websocket().get_price('BTC')
  2. if price is None or stale (check is_connected()):
       if not already paused: Telegram "Feed disconnected. Monitoring paused."
       set _feed_paused = True; prev_price = None; continue
  3. if _feed_paused:
       Telegram "Feed recovered. Monitoring resumed."
       _feed_paused = False
  4. WAITING cards: if parent exists and parent.status == COMPLETED → set to ARMED
  5. ARMED cards: evaluate trigger conditions
       if trigger met: check IV gate
         if IV gate blocks: Telegram IV_BLOCKED alert; skip
         if IV gate passes: → TRIGGERED, add to execution queue
  6. execution queue: if nothing currently EXECUTING, pop earliest (by created_at), hand to patience_executor
  7. prev_price = current_price
```

**Trigger type evaluation (from blueprint Section 5.3):**
```python
def _evaluate_trigger(self, card, current, prev):
    t = card['trigger_price']
    tol = card['trigger_tolerance']
    typ = card['trigger_type']

    if typ == 'TOUCH':
        return abs(current - t) <= tol
    elif typ == 'CROSS_UP':
        return prev is not None and prev < t and current >= t
    elif typ == 'CROSS_DOWN':
        return prev is not None and prev > t and current <= t
    elif typ == 'SUSTAIN':
        # price beyond trigger_price for sustain_minutes continuously
        # use _sustain_tracker dict: card_id → first_time_in_zone
        ...
```

**Imports from existing code (read-only):**
```python
from ..services.delta_price_websocket import get_price_websocket
from ..services.patience_iv import get_current_iv_percentile
from ..services.patience_executor import execute_card
from ..routes.patience.patience_models import get_db
from ...bot.options.notifications.options_notifier import get_options_notifier
```

---

### Step 1.5 — Card executor (`patience_executor.py`)

Bridge between trigger engine and patience_loop. Handles pre-fire checks and GCD scheduling.

```python
async def execute_card(card_id: str) -> None:
    db = get_db()
    card = db.get_card(card_id)
    legs = db.get_legs(card_id)

    # Pre-fire check 1: Guardian
    if _check_guardian() != 'GO':
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'PAUSE', 'Guardian signal is STOP')
        notifier.send(f"Patience: [{card['card_name']}] blocked by Guardian.")
        return

    # Pre-fire check 2: Portfolio Greeks
    if not _check_greeks_ok(card, legs):
        db.update_card(card_id, status='PAUSED')
        db.log_event(card_id, None, 'GREEKS_BLOCKED', ...)
        notifier.send(f"Patience: [{card['card_name']}] would push portfolio delta to X. Paused.")
        return

    # Pre-fire check 3: Price freshness (already done in trigger, double-check)

    # Resolve relative strikes
    legs = await _resolve_strikes(legs)

    # Build GCD schedule
    schedule = compute_gcd_schedule(legs)

    # Build orders list for patience_loop (same format as autoloop orders)
    orders = _build_orders(legs, schedule)

    db.update_card(card_id, status='EXECUTING')
    db.log_event(card_id, None, 'TRIGGER_HIT', f"Executing {len(legs)} legs, {schedule['total_rounds']} GCD rounds")
    notifier.send(f"Patience: [{card['card_name']}] TRIGGERED. Executing {len(legs)} legs, {schedule['total_rounds']} GCD rounds.")

    # Start patience_loop
    loop_svc = get_patience_loop_service()
    loop_svc.start_loop(
        loop_id=card_id,
        orders=orders,
        total_rounds=schedule['total_rounds']
    )

    # Monitor loop in background thread
    threading.Thread(target=_monitor_loop, args=(card_id,), daemon=True).start()
```

**Guardian check:**
```python
def _check_guardian() -> str:
    """Read guardian_signal.json. Return 'GO' if absent or signal != STOP."""
    path = Path('data/guardian_signal.json')
    if not path.exists():
        return 'GO'
    try:
        data = json.loads(path.read_text())
        return 'STOP' if data.get('signal') == 'STOP' else 'GO'
    except Exception:
        return 'GO'  # fail open — guardian file corrupt, don't block trading
```

**Portfolio Greeks check:**
```python
def _check_greeks_ok(card, legs) -> bool:
    """
    Import position_greeks.py, get current positions, add card's theoretical positions,
    check total portfolio delta is within configured limit.
    Returns True if safe to proceed.
    """
    from ..options_strategy.position_greeks import enrich_positions_with_greeks
    from ..services.delta_price_websocket import get_price_websocket

    spot = get_price_websocket().get_price('BTC')
    if spot is None:
        return False  # can't check, don't execute

    # Get current open positions via internal DB or positions endpoint
    # Build synthetic positions for card's legs
    # Call enrich_positions_with_greeks(all_positions, spot)
    # Sum delta across all positions
    # Compare against configured PATIENCE_MAX_PORTFOLIO_DELTA (stored in patience.db or config)
    ...
```

**Relative strike resolution:**
```python
async def _resolve_strikes(legs: list) -> list:
    """
    For legs with is_relative_strike=True: fetch current ATM strike from option chain,
    add relative_offset to get absolute strike.
    GET /api/options/chain or /api/options/expiry/<date> → find ATM.
    """
```

**Loop monitor (background thread):**
```python
def _monitor_loop(card_id: str):
    """Poll patience_loop status every 2s. On completion → COMPLETED. On error → PAUSED."""
    loop_svc = get_patience_loop_service()
    while True:
        time.sleep(2)
        status = loop_svc.get_status(card_id)
        if status['status'] == 'completed':
            _on_card_completed(card_id)
            break
        elif status['status'] == 'error':
            _on_card_failed(card_id, status.get('error'))
            break
```

---

### Step 1.6 — REST API (`patience_api.py`)

Flask Blueprint. Uses `_run_async()` helper (same pattern as `mmm_api.py`).

```python
patience_bp = Blueprint('patience', __name__, url_prefix='/api/patience')

# ── Cards ──────────────────────────────────────────────────────────
GET    /api/patience/cards              # list all cards (optional ?status=)
POST   /api/patience/cards              # create card + legs (DRAFT or ARMED)
GET    /api/patience/cards/<card_id>    # get card + legs
PUT    /api/patience/cards/<card_id>    # update card/legs (allowed for ARMED)
DELETE /api/patience/cards/<card_id>    # cancel + delete

# ── Card lifecycle ─────────────────────────────────────────────────
POST   /api/patience/cards/<card_id>/arm       # DRAFT/PAUSED → ARMED
POST   /api/patience/cards/<card_id>/disarm    # ARMED → DRAFT
POST   /api/patience/cards/<card_id>/pause     # pause monitoring
POST   /api/patience/cards/<card_id>/resume    # resume → ARMED
POST   /api/patience/cards/<card_id>/cancel    # terminal cancel

# ── MMM handoff ────────────────────────────────────────────────────
POST   /api/patience/cards/<card_id>/legs/<leg_id>/handoff
# Mark leg HANDED_TO_MMM, record handoff price, Telegram alert

# ── Execution log ──────────────────────────────────────────────────
GET    /api/patience/cards/<card_id>/log       # execution event log

# ── Templates ──────────────────────────────────────────────────────
GET    /api/patience/templates                 # list all
POST   /api/patience/templates                 # save new
GET    /api/patience/templates/<id>            # get one
DELETE /api/patience/templates/<id>            # delete

# ── IV percentile ─────────────────────────────────────────────────
GET    /api/patience/iv/current                # current percentile + DVOL value
GET    /api/patience/iv/history?days=30        # historical DVOL for chart

# ── Dashboard / status ─────────────────────────────────────────────
GET    /api/patience/status                    # engine running, feed status, armed count, BTC price
GET    /api/patience/pnl                       # real-time P&L across all active cards

# ── Engine controls ────────────────────────────────────────────────
POST   /api/patience/arm-all                   # arm all DRAFT cards
POST   /api/patience/disarm-all                # disarm all ARMED cards
POST   /api/patience/kill-switch               # cancel all ARMED + WAITING

# ── Performance history ────────────────────────────────────────────
GET    /api/patience/performance               # historical card performance

# ── Trigger engine control ─────────────────────────────────────────
GET    /api/patience/engine/status             # is trigger daemon running
POST   /api/patience/engine/start
POST   /api/patience/engine/stop
```

**Wiring to app.py (single line addition):**
```python
# In webui/backend/app.py, in the blueprint imports block (~line 80):
from .routes.patience import patience_bp
# In the register_blueprint section:
app.register_blueprint(patience_bp)
```

---

### Phase 1 Integration Test

```
1. curl POST /api/patience/cards  → create card with 2 legs (BUY + SELL, fixed strikes)
2. curl POST /api/patience/cards/<id>/arm
3. curl GET  /api/patience/status  → verify ARMED count = 1, engine running
4. Move BTC price manually (or use test card with current price as trigger)
5. curl GET  /api/patience/cards/<id>  → status = TRIGGERED → EXECUTING
6. curl GET  /api/patience/cards/<id>/log  → see round fills
7. Verify positions appear in existing /api/options/positions
8. curl GET  /api/patience/cards/<id>  → status = COMPLETED
```

---

## Phase 2 — IV Gate + Greeks Check + Templates

**Goal:** IV percentile gating works, portfolio Greeks pre-check works, templates save/load.
**Duration estimate:** 2–3 days
**Deliverable:** Card with IV max 35 stays ARMED when IV > 35, fires when IV drops. Greeks check pauses card if delta would breach limit.

---

### Step 2.1 — IV percentile module (`patience_iv.py`)

```python
DVOL_API_ENDPOINT = "https://www.deribit.com/api/v2/public/get_index_price_names"
DVOL_HISTORY_ENDPOINT = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
# BTC DVOL symbol: "dvol_btc"

class PatienceIV:
    POLL_INTERVAL = 900  # 15 minutes

    def start(self): ...   # daemon thread
    def _run(self): ...    # poll loop

    def _fetch_dvol(self) -> float | None: ...
    def _backfill(self, days: int = 30) -> None: ...   # called on first run

    def get_current_percentile(self, lookback_days: int = 30) -> float | None:
        """
        1. Get recent dvol_value from dvol_history (last lookback_days)
        2. Get current dvol_value
        3. percentile = count(values < current) / total * 100
        """

    def get_current_dvol(self) -> float | None: ...
    def get_history(self, days: int = 30) -> list[dict]: ...

_iv: PatienceIV | None = None
def get_patience_iv() -> PatienceIV: ...
def get_current_iv_percentile(lookback_days=30) -> float | None: ...
```

**Deribit API (public, no auth):**
- Current DVOL: `GET https://www.deribit.com/api/v2/public/get_index_price?index_name=dvol_btc`
- Historical: `GET https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name=DVOL-BTC&start_timestamp=...&end_timestamp=...&resolution=1440`
- Backfill 30 days on first start. After that, poll every 15 min and append.

**No auth needed. Public endpoint. Use `requests` (already in requirements).**

---

### Step 2.2 — IV gate in trigger engine

Already wired in `patience_trigger.py` (`_check_iv_gate()`). In Phase 1 this returned `True` always (stub). Now implement:

```python
def _check_iv_gate(self, card, current_percentile) -> bool:
    if current_percentile is None:
        return True   # IV data unavailable → don't block (fail open)

    min_pct = card.get('iv_percentile_min')
    max_pct = card.get('iv_percentile_max')

    if min_pct is not None and current_percentile < min_pct:
        return False  # credit strategy needs high IV, IV too low
    if max_pct is not None and current_percentile > max_pct:
        return False  # debit strategy needs low IV, IV too high
    return True
```

---

### Step 2.3 — Greeks pre-check in executor

Already stubbed in `patience_executor.py` (`_check_greeks_ok()`). Implement fully:

```python
def _check_greeks_ok(card: dict, legs: list) -> bool:
    from ..options_strategy.position_greeks import enrich_positions_with_greeks
    from ..services.delta_price_websocket import get_price_websocket

    spot = get_price_websocket().get_price('BTC')
    if not spot:
        return False

    # 1. Get current positions from /api/positions (internal call to positions module)
    current_positions = _get_current_positions()

    # 2. Build synthetic positions from card legs (estimated greeks at current spot)
    synthetic = _build_synthetic_positions(legs, spot)

    # 3. Enrich all
    all_pos = enrich_positions_with_greeks(current_positions + synthetic, spot)

    # 4. Sum portfolio delta
    total_delta = sum(
        p.get('pos_greeks', {}).get('delta', 0) for p in all_pos
    )

    # 5. Compare against limit (stored in patience.db settings table or hardcoded config)
    MAX_PORTFOLIO_DELTA = 500  # configurable, phase 3 adds UI for this

    if abs(total_delta) > MAX_PORTFOLIO_DELTA:
        db.log_event(card['card_id'], None, 'GREEKS_BLOCKED',
                     f"Portfolio delta would be {total_delta:.0f}, limit {MAX_PORTFOLIO_DELTA}")
        return False
    return True
```

---

### Step 2.4 — Templates API (already in `patience_api.py`)

Routes already defined in Phase 1 (`GET/POST /api/patience/templates`). In Phase 1 these were stubs returning 501. Now implement:

- `POST /api/patience/templates` — save `{template_name, trigger_type, trigger_tolerance, iv_*, legs_json}`
- Template `legs_json` stores direction, option_type, lots, order_mode, mmm_handoff_eligible, relative strikes. NOT absolute strikes (those change each cycle).
- `POST /api/patience/cards` — accept `template_id` param: loads template, pre-fills legs, user only sets trigger_price and expiry_date.

---

### Phase 2 Integration Test

```
1. Start PatienceIV daemon, wait for backfill
2. curl GET /api/patience/iv/current → verify percentile is calculated
3. Create card with iv_percentile_max=35, set trigger to current BTC price
4. Arm card
5. With IV > 35: trigger fires price condition → log shows IV_BLOCKED, card stays ARMED
6. Manually insert low DVOL into dvol_history → IV percentile drops to 20
7. Same trigger → now fires → EXECUTING
8. Create card that would push delta over limit → verify GREEKS_BLOCKED in log, card PAUSED
9. Save template, reload → verify legs pre-populated
```

---

## Phase 3 — React Web UI

**Goal:** Full card builder with live payoff preview, dashboard with live ticker, card detail with execution log + positions + MMM handoff.
**Duration estimate:** 4–5 days
**Deliverable:** Complete UI cycle — build card from template, arm, watch trigger, see execution, verify fills, hand leg to MMM.

---

### Step 3.1 — Page + Nav wiring

**New file:** `webui/frontend/src/pages/PatiencePage.js`
```jsx
import React from 'react';
import PatienceDashboard from '../components/patience/PatienceDashboard';
export default function PatiencePage() {
    return <PatienceDashboard />;
}
```

**Modify** `webui/frontend/src/App.js` (lazy import + route):
```javascript
const PatiencePage = React.lazy(() => import('./pages/PatiencePage'));
// In routes: <Route path="/patience" element={<PatiencePage />} />
```

**Modify** `webui/frontend/src/config/navigationSections.js`:
```javascript
{ key: 'patience', label: 'Patience', path: '/patience', icon: <HourglassEmptyIcon /> }
```

**These are the only 3 lines added/changed in existing files.**

---

### Step 3.2 — API service (`patienceService.js`)

Thin wrapper around axios. All backend calls go through here. Pattern matches `mmmService.js`.

```javascript
const BASE = '/api/patience';

export const patienceAPI = {
  // Cards
  getCards: (status) => axios.get(`${BASE}/cards`, { params: { status } }),
  createCard: (data) => axios.post(`${BASE}/cards`, data),
  getCard: (id) => axios.get(`${BASE}/cards/${id}`),
  updateCard: (id, data) => axios.put(`${BASE}/cards/${id}`, data),
  deleteCard: (id) => axios.delete(`${BASE}/cards/${id}`),

  // Lifecycle
  armCard: (id) => axios.post(`${BASE}/cards/${id}/arm`),
  disarmCard: (id) => axios.post(`${BASE}/cards/${id}/disarm`),
  cancelCard: (id) => axios.post(`${BASE}/cards/${id}/cancel`),
  resumeCard: (id) => axios.post(`${BASE}/cards/${id}/resume`),

  // Handoff
  handoffLeg: (cardId, legId) => axios.post(`${BASE}/cards/${cardId}/legs/${legId}/handoff`),

  // Log
  getLog: (id) => axios.get(`${BASE}/cards/${id}/log`),

  // Templates
  getTemplates: () => axios.get(`${BASE}/templates`),
  saveTemplate: (data) => axios.post(`${BASE}/templates`, data),
  deleteTemplate: (id) => axios.delete(`${BASE}/templates/${id}`),

  // IV
  getIVCurrent: () => axios.get(`${BASE}/iv/current`),
  getIVHistory: (days) => axios.get(`${BASE}/iv/history`, { params: { days } }),

  // Status + P&L
  getStatus: () => axios.get(`${BASE}/status`),
  getPnL: () => axios.get(`${BASE}/pnl`),

  // Engine
  killSwitch: () => axios.post(`${BASE}/kill-switch`),
  armAll: () => axios.post(`${BASE}/arm-all`),
  disarmAll: () => axios.post(`${BASE}/disarm-all`),

  // Performance
  getPerformance: () => axios.get(`${BASE}/performance`),
};
```

---

### Step 3.3 — `PatienceDashboard.jsx`

**State:** polls `GET /api/patience/status` every 3s (use `useVisibilityAwarePolling` — same hook as OptionsPanel).

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ BTC: $73,042   │   IV Percentile: 28%   │  [ARM ALL] [DISARM ALL] [KILL SWITCH] │
├─────────────────────────────────────────────────────────┤
│ [List View] [Chain Tree]   [+ New Card] [From Template] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Card tiles (list or tree depending on toggle)          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Card tile (compact):**
```
┌──────────────────────────────────────────┐
│ [●ARMED] Bull Swing Layer                │
│ Trigger: BTC ≥ 72,000 (cross up)         │
│ IV gate: ≤ 35%    Distance: +1,042 pts   │
│ Legs: 3 │ GCD: 10 rounds │ [MMM] flag   │
│ [Edit] [Disarm] [Cancel]                 │
└──────────────────────────────────────────┘
```

**Status colors:** DRAFT=gray, ARMED=blue, TRIGGERED=orange, EXECUTING=yellow (pulse), COMPLETED=green, PAUSED=red, CANCELLED=muted.

**Chain tree view (`ChainTreeView.jsx`):**
- Renders parent-child using simple indented tree (no external graph lib needed — just CSS indent)
- Root cards at top, children indented
- Arrows showing dependency direction
- Each node is a compact card tile

---

### Step 3.4 — `CardBuilder.jsx` (wizard, 6 steps)

**Step 1 — Expiry Selection**
- Dropdown: fetch available expiries from `GET /api/options/expiries` (existing endpoint)
- Multi-expiry: legs can each have their own expiry (calendar spreads)
- "Load from template" button → skips to Step 6 with pre-filled data

**Step 2 — Trigger**
- Trigger price (number input with live BTC price reference)
- Trigger type (TOUCH / CROSS_UP / CROSS_DOWN / SUSTAIN) — toggle buttons
- Tolerance (TOUCH only): slider, default 50
- Sustain minutes (SUSTAIN only): number input

**Step 3 — IV Gate**
- Show current IV percentile (from `GET /api/patience/iv/current`)
- iv_percentile_min: optional, for credit strategies ("IV must be above X%")
- iv_percentile_max: optional, for debit strategies ("IV must be below X%")
- Visual: colored range bar showing current IV position within 0–100

**Step 4 — Build Legs**
- Live option chain table: `GET /api/options/chain/<expiry>` — shows strikes with bid/ask
- Click a row → adds leg. Set: direction (BUY/SELL), lots, order_mode, post_only, SL (optional), MMM handoff flag
- Relative strike toggle: instead of absolute strike, use ATM offset (+3000 = 3000 above ATM)
- Reorder legs (drag or up/down arrows) — sets leg_order
- GCD preview: shown live as legs are added. E.g. "GCD=10, 2 rounds, max unhedged = 1 lot per round"

**Step 5 — Chain (Optional)**
- Parent card dropdown (from list of ARMED/COMPLETED cards)
- Visual: "This card will WAIT until [parent name] completes"

**Step 6 — Payoff Preview + Review**
- Payoff graph: import `payoffCalculator.js` functions + existing `OptionsPayoffDiagram` component (read-only import)
- Compute payoff from current leg structure with estimated fills at mid-price
- Show: max profit, max loss, breakeven(s), R:R, estimated Greeks impact on portfolio
- GCD schedule table: round 1 → [BUY 2 PE, SELL 1 CE], round 2 → same
- Net debit/credit estimate
- [Save as Template] button → `POST /api/patience/templates`
- [ARM Card] → `POST /api/patience/cards` + `POST /api/patience/cards/<id>/arm`

**Armed card editing:** CardBuilder used for both create and edit. If editing ARMED card: same wizard, PUT on save, no cancel-recreate needed.

---

### Step 3.5 — `CardDetail.jsx`

Three-section layout (collapsible):

**Section 1: Execution Log**
- `GET /api/patience/cards/<id>/log` — poll every 5s while EXECUTING
- Table: timestamp, event_type, message, data (expandable JSON)
- Filter: ALL / FILLS / ERRORS / ROUNDS

**Section 2: Open Positions Panel**
- Embed existing `OptionsPanel.js` component filtered to card's `group_id`
- Read existing positions from `/api/positions` (existing endpoint), filter by group_id
- All existing SL/TP, max loss, batch bar functions work as-is (they're existing components)
- **Additional:** "Hand to MMM" button on each leg where `mmm_handoff_eligible=true` and status != HANDED_TO_MMM
  - On click: confirm dialog → `POST /api/patience/cards/<id>/legs/<leg_id>/handoff`
  - After handoff: leg row shows "Managed by MMM" badge, no more P&L tracking in Patience

**Section 3: Payoff Graph**
- Use existing `OptionsPayoffDiagram.js` component (SEALED — import only)
- Toggle: "This card" vs "All Patience cards combined"
- Live mark prices from existing position data

---

### Step 3.6 — `IVPanel.jsx`

- Current DVOL value + percentile prominently displayed
- Line chart of last 30 days DVOL history (use `recharts` — already in `package.json` likely, else add)
- Percentile distribution: show where current value sits in the distribution (colored bar)
- Auto-refreshes every 15 min (matches collection interval)

---

### Step 3.7 — `PnLDashboard.jsx`

- Poll `GET /api/patience/pnl` every 5s
- Cards: Total premium deployed | Current value | Unrealized P&L | Active cards count
- Table: one row per active card — card name, entry premium, current value, unrealized P&L, status
- MMM-handed legs shown separately with "Managed by MMM" label + P&L recorded at handoff price

**Backend `/api/patience/pnl` implementation:**
```python
# For each EXECUTING/COMPLETED card:
# 1. Get legs and their fill_prices
# 2. Get current mark prices from /api/positions or direct ticker calls
# 3. entry_premium = sum(fill_price * lots * direction_sign for each filled leg)
# 4. current_value = sum(mark_price * lots * direction_sign for each active leg)
# 5. unrealized_pnl = current_value - entry_premium
```

---

### Step 3.8 — `TemplateManager.jsx`

Simple list + management UI. Embedded in CardBuilder Step 1 (load) and Step 6 (save).

Can also be standalone panel in dashboard sidebar:
- List templates with name, legs count, trigger type
- Click to preview leg structure
- Delete button
- "Use this template" → opens CardBuilder pre-filled

---

### Phase 3 Integration Test

```
Full cycle test:
1. Open Patience tab in UI
2. Check: BTC price shows live, IV percentile shows
3. Click "From Template" → select template → trigger price only needed → ARM
4. Watch dashboard: card shows ARMED with distance from trigger
5. BTC crosses trigger price → card shows TRIGGERED → EXECUTING → fills round by round
6. Open CardDetail: execution log shows fills, positions panel shows filled positions
7. Click "Hand to MMM" on eligible leg → confirm → leg shows "Managed by MMM"
8. P&L dashboard updates in real-time
9. Chain tree: create parent + child card → child shows WAITING → parent completes → child auto-ARMs
```

---

## Phase 4 — Hardening + Performance History

**Goal:** Production reliability. State recovery, execution lock, SL auto-activation, kill switch, edge case handling.
**Duration estimate:** 2–3 days
**Deliverable:** System survives restarts, handles simultaneous triggers, feed disconnects, multi-expiry cards correctly.

---

### Step 4.1 — State recovery on restart

`patience_trigger.py` → `start()` method:

```python
def start(self):
    # On startup: recover any cards that were EXECUTING when server restarted
    db = get_db()

    # Cards stuck in EXECUTING → they need to resume or pause
    executing = db.get_cards_by_status('EXECUTING')
    for card in executing:
        # Check if patience_loop still has state for this card
        loop_svc = get_patience_loop_service()
        loop_status = loop_svc.get_status(card['card_id'])
        if loop_status is None:
            # Loop was lost in restart → mark PAUSED, alert trader
            db.update_card(card['card_id'], status='PAUSED')
            db.log_event(card['card_id'], None, 'PAUSE', 'Server restart: execution state lost')
            notifier.send(f"Patience: [{card['card_name']}] was EXECUTING on restart — PAUSED. Review and resume manually.")
        # If loop still running (daemon threads don't survive restart) → will always be None
        # This handles gracefully: trader sees PAUSED card, can resume

    # Cards in TRIGGERED → move back to ARMED (re-evaluate on next cycle)
    triggered = db.get_cards_by_status('TRIGGERED')
    for card in triggered:
        db.update_card(card['card_id'], status='ARMED')

    # ARMED + WAITING cards → resume monitoring normally (already in DB)
    self._thread = threading.Thread(target=self._run, daemon=True)
    self._thread.start()
```

---

### Step 4.2 — Execution lock (one card at a time)

In `patience_trigger.py`, maintain `_executing_card_id` instance variable:

```python
def _queue_for_execution(self, card):
    if self._executing_card_id is not None:
        # Another card is executing → queue this one (priority by created_at)
        self._execution_queue.append(card)
        self._execution_queue.sort(key=lambda c: c['created_at'])
        return
    self._executing_card_id = card['card_id']
    threading.Thread(target=self._execute_and_advance, args=(card,), daemon=True).start()

def _execute_and_advance(self, card):
    try:
        asyncio.run(execute_card(card['card_id']))
    finally:
        self._executing_card_id = None
        # Pop next from queue if any
        if self._execution_queue:
            next_card = self._execution_queue.pop(0)
            self._queue_for_execution(next_card)
```

---

### Step 4.3 — Auto-grouping on completion

In `patience_executor.py`, `_on_card_completed()`:

```python
def _on_card_completed(card_id: str):
    db = get_db()
    card = db.get_card(card_id)
    legs = db.get_legs(card_id)

    # Auto-group via existing groups_api
    import requests
    group_id = f"patience_{card_id[:8]}"
    expiry_key = _get_primary_expiry(legs)
    requests.post('http://localhost:5555/api/options/groups/create', json={
        'expiry_key': expiry_key,
        'group_id': group_id,
        'name': f"Patience: {card['card_name']}",
        'color': '#7c3aed'
    })

    db.update_card(card_id, status='COMPLETED', group_id=group_id, completed_at=now())
    db.log_event(card_id, None, 'COMPLETE', f"All legs filled. Grouped as {group_id}")
    notifier.send(f"Patience: [{card['card_name']}] COMPLETED. All legs filled. Grouped. Verify in UI.")

    # Arm waiting children
    waiting = db.get_cards_by_status('WAITING')
    for child in waiting:
        if child.get('parent_card_id') == card_id:
            db.update_card(child['card_id'], status='ARMED')
            notifier.send(f"Patience: [{child['card_name']}] auto-ARMED (parent completed).")
```

---

### Step 4.4 — SL auto-activation

In `patience_executor.py`, per-leg fill handler (called by loop monitor):

```python
def _on_leg_filled(card_id: str, leg_id: str, fill_price: float):
    db = get_db()
    leg = db.get_leg(leg_id)

    db.update_leg(leg_id, status='FILLED', fill_price=fill_price, filled_at=now())
    db.log_event(card_id, leg_id, 'LEG_FILL', f"Filled @ {fill_price}")

    # Activate local SL if set
    if leg.get('stop_loss') is not None:
        from ..options_strategy.sl_tp_manager import SLTPManager
        sl_mgr = SLTPManager()
        sl_mgr.set_stop_loss(
            symbol=_leg_to_symbol(leg),
            stop_loss_price=leg['stop_loss'],
            auto_execute=True
        )
        db.log_event(card_id, leg_id, 'SL_ACTIVATED', f"Local SL set at {leg['stop_loss']}")
```

---

### Step 4.5 — `PerformanceHistory.jsx` + backend

**Backend:** `GET /api/patience/performance` returns `card_performance` table rows enriched with card names.

**Frontend:** Table + summary cards:
- Win rate: profitable / total closed cards
- Average P&L per card
- Total P&L all time
- P&L by card type (debit / credit / mixed)
- P&L chart over time (recharts line chart)
- Legs handed to MMM: count + P&L at handoff price (separate row)

**Populating performance:** On card COMPLETED + manually closed by trader:
```python
# POST /api/patience/cards/<id>/close
def close_card(card_id):
    card = db.get_card(card_id)
    legs = db.get_legs(card_id)
    # Calculate entry_premium from leg fill_prices
    # Get current mark prices for exit_value
    # Insert into card_performance
    db.save_performance({...})
    db.update_card(card_id, status='CANCELLED')  # remove from active monitoring
```

---

### Step 4.6 — Kill switch

`POST /api/patience/kill-switch`:

```python
def kill_switch():
    db = get_db()
    cancelled = 0
    for card in db.get_cards_by_status('ARMED', 'WAITING', 'TRIGGERED'):
        db.update_card(card['card_id'], status='CANCELLED')
        db.log_event(card['card_id'], None, 'PAUSE', 'Kill switch activated')
        cancelled += 1
    # Stop trigger engine from evaluating anything
    get_patience_trigger().pause_monitoring()
    notifier.send(f"Patience KILL SWITCH activated. {cancelled} cards cancelled.")
    return jsonify({'cancelled': cancelled})
```

Does NOT close positions. Does NOT touch EXECUTING cards (they're mid-fill — let them complete their current round, then the trigger won't fire new ones).

---

### Step 4.7 — Edge case handling

| Edge case | Handling |
|-----------|----------|
| Simultaneous triggers (2 cards both trigger at same millisecond) | Execution queue + created_at priority. Second card queues behind first. |
| Parent PAUSED, children WAITING | Children stay WAITING. Only parent COMPLETED arms children. |
| Card triggers, relative strike not in chain (e.g. chain only has ATM ± 5 strikes) | PAUSE card, log "Strike XXXXX not available in chain", Telegram alert |
| Multi-expiry card: one expiry has no liquidity | Per-leg retry → 10 retries → leg FAILED → card PAUSED |
| Feed disconnect mid-execution | Already executing card continues (patience_loop runs independently). Monitoring paused for new triggers only. |
| Duplicate trigger (TOUCH: price bounces in tolerance zone) | TOUCH triggers once then card → TRIGGERED. No re-trigger. |
| GCD = lot count (e.g. all legs have 1 lot) | total_rounds = 1. Normal single-round execution. |
| Greeks check not possible (position_greeks.py fails) | Log warning, proceed with execution (fail open — greeks check is advisory, not hard block) |

---

## What Is Absolutely NOT Touched

| File | Status |
|------|--------|
| `routes/options/order_executor.py` | SEALED — called, never modified |
| `services/auto_loop_service.py` | SEALED — copied to patience_loop.py, original untouched |
| `options_strategy/position_greeks.py` | Read-only import |
| `bot/options/notifications/options_notifier.py` | Read-only import |
| `routes/options/groups_api.py` | Called via internal HTTP, never modified |
| `options_strategy/sl_tp_manager.py` | Read-only import |
| `frontend/src/components/options/payoffCalculator.js` | SEALED — import only |
| `frontend/src/components/options/OptionsPayoffDiagram.js` | SEALED — embed only |
| `frontend/src/components/options/OptionsPanel.js` | Embedded in CardDetail, never modified |
| All MMM files | Zero coupling — MMM detects handed-off legs through its own position scanning |
| All GridBot files | No relation |
| `webui/backend/app.py` | One `register_blueprint` line ONLY |
| `webui/frontend/src/App.js` | One lazy import + one route entry ONLY |

---

## Deployment Notes

- **Backend restart required** after adding blueprint to app.py. Check for live MMM sessions first.
- **Frontend build required** after any React change: `cd webui/frontend && npm run build`
- **patience.db** auto-created on first API call. No migration scripts needed (SQLite `CREATE TABLE IF NOT EXISTS`).
- **Trigger daemon** auto-starts when first `/api/patience/*` call is made (lazy init) OR on app startup via `app.py` hook.
- **DVOL backfill** runs once on first `PatienceIV.start()`. Takes ~2s. Non-blocking.

---

## Summary: Build Order

```
Phase 1 (core engine):
  patience_models.py    → schema + DB access
  gcd_batch.py          → GCD utility (pure math)
  patience_loop.py      → copy auto_loop_service, hardcode maker_only
  patience_trigger.py   → daemon, stubs for IV gate + Greeks (Phase 2)
  patience_executor.py  → pre-fire checks, GCD → loop, completion handler
  patience_api.py       → all REST routes (templates = 501 stub for now)
  __init__.py           → Blueprint export
  ← one line in app.py

Phase 2 (gates):
  patience_iv.py        → DVOL + percentile (real implementation)
  patience_trigger.py   → fill in _check_iv_gate() (was stub)
  patience_executor.py  → fill in _check_greeks_ok() (was stub)
  patience_api.py       → implement template routes (was 501)

Phase 3 (UI):
  patienceService.js    → API client
  PatiencePage.js       → page wrapper
  PatienceDashboard.jsx → list + tree view
  CardBuilder.jsx       → 6-step wizard
  CardDetail.jsx        → log + positions + handoff
  IVPanel.jsx           → DVOL chart
  PnLDashboard.jsx      → real-time P&L
  TemplateManager.jsx   → template list
  ChainTreeView.jsx     → parent-child tree
  ← 3 lines in App.js + navigationSections.js

Phase 4 (hardening):
  patience_trigger.py   → state recovery, execution lock, queue
  patience_executor.py  → auto-group, SL activation, edge cases
  patience_api.py       → close-card, kill-switch, performance endpoints
  PerformanceHistory.jsx → card history UI
```

---

*Plan based on codebase research: March 14, 2026. Ready to implement phase by phase.*
