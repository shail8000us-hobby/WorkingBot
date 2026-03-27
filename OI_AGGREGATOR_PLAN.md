# OI Aggregator — Implementation Plan

**Created:** 2026-03-27
**Status:** Planning (Audit-Revised)
**Scope:** Multi-exchange Open Interest collection, unified display (bar charts + table), spike alerts — integrated into the existing webUI.
**Audit:** Production audit completed 2026-03-27. 10 critical fixes integrated below (marked with 🔧).

---

## 1. Problem Statement

Open Interest data lives in silos across exchanges (Deribit, Binance, Delta Exchange Global, Delta Exchange India). There is no single view that:
- Aggregates OI across all sources per strike and expiry
- Shows OI change (delta between snapshots) alongside absolute OI
- Alerts on sudden spikes that may signal large directional positioning

---

## 2. Goals

| Goal | Scope |
|---|---|
| Collect OI from 4 exchanges via public REST APIs | Backend |
| Normalise to a single schema (exchange-agnostic) | Backend |
| Persist snapshots to SQLite for OI-change calculation | Backend |
| Detect spikes (configurable threshold) and broadcast via SocketIO | Backend |
| Bar chart: absolute OI by strike, grouped by Put/Call | Frontend |
| Bar chart: OI change by strike, grouped by Put/Call | Frontend |
| Strike table with PCR, OI change, per-exchange breakdown | Frontend |
| Spike log tab with real-time toasts | Frontend |
| New page in webUI with sidebar navigation entry | Frontend |

---

## 3. Open Questions (Must Resolve Before Phase 1)

1. **Underlying asset**: BTC only, or BTC + ETH + configurable?
2. **Market type**: Crypto options OI (Deribit/Binance/Delta) or Indian equity NIFTY OI (NSE)? The screenshots show NIFTY — clarify target market.
3. **Strike range**: Show all strikes, or ±N strikes around ATM (configurable N)?
4. **Spike threshold**: Default 15% OI change in 15 minutes — acceptable?
5. **Refresh interval**: 60 seconds default — acceptable? (Exchange rate limits constrain this.)
6. **Delta India API**: The existing `options_client.py` — does it already return OI per instrument, or only positions?

---

## 4. Exchange API Reference

### 4.1 Deribit (largest crypto options market)
- **Base URL:** `https://www.deribit.com/api/v2/public`
- **OI endpoint:** `GET /get_book_summary_by_currency?currency=BTC&kind=option`
- **Fields used:** `instrument_name`, `open_interest`, `volume`, `underlying_price`
- **Auth required:** No (public endpoint)
- **Rate limit:** 10 req/sec per IP
- **Instrument name format:** `BTC-29MAR24-65000-C` → parse to extract expiry, strike, type

### 4.2 Binance Options
- **Base URL:** `https://eapi.binance.com/eapi/v1`
- **OI endpoint:** `GET /openInterest?underlyingAsset=BTC&expiration=YYYYMMDD`
- **Fields used:** `symbol`, `sumOpenInterest`, `sumOpenInterestUSD`
- **Auth required:** No (public endpoint)
- **Note:** Thinner market than Deribit; may have fewer strikes available
- **Symbol format:** `BTC-241227-65000-C` → parse to extract expiry, strike, type
- 🔧 **Per-expiry calls required:** This endpoint needs one request per expiry date. Must pre-fetch expiry list and rate-limit (max 5 req/sec to stay safe).
- 🔧 **Deprecation risk:** Binance `eapi` has been shut down/relaunched before. Add startup health-check canary call; log response schema on first call; support feature-flag disable per exchange without code deploy.

### 4.3 Delta Exchange Global
- **Base URL:** `https://api.delta.exchange/v2`
- **Products endpoint:** `GET /products?contract_types=call_options,put_options&underlying_asset_symbol=BTC`
- **Ticker endpoint:** `GET /tickers?contract_types=call_options,put_options`
- **Fields used:** `symbol`, `open_interest`, `product_id`, `strike_price`, `expiry_time`
- **Auth required:** No (public market data)

### 4.4 Delta Exchange India
- **Existing client:** `webui/backend/routes/options/options_client.py`
- **Reuse:** Call `get_unified_client()` — already handles auth, retries, testnet flag
- **OI field:** Available in product tickers as `oi` or `open_interest`
- **Note:** Verify field name from existing client response before Phase 1

---

## 5. Normalised Schema

Every fetcher outputs rows in this exact format. No exchange-specific fields leak past the fetcher layer.

```
OIRow {
    exchange    : str       # "deribit" | "binance" | "delta_global" | "delta_india"
    underlying  : str       # "BTC" | "ETH"
    expiry      : str       # ISO date "YYYY-MM-DD"  (must match ^\d{4}-\d{2}-\d{2}$)
    strike      : float     # 🔧 float not int — some exchanges use decimal strikes
    type        : str       # "call" | "put"
    oi          : float     # open interest in contract/coin units
    oi_usd      : float     # 🔧 notional USD value — see per-exchange rules below
    timestamp   : str       # ISO datetime UTC — 🔧 use exchange's own timestamp, not fetch time
}
```

🔧 **OI USD Calculation Rules (per exchange):**
- **Deribit:** `oi_usd = oi × underlying_price` (from same API response's `underlying_price` field). OI is in BTC (coin-margined).
- **Binance:** Use the native `sumOpenInterestUSD` field directly. Do NOT multiply `sumOpenInterest × price` (double-counts).
- **Delta Global & India:** Check contract multiplier. Add `contract_multiplier` field to BaseOIFetcher; default 1.0.

🔧 **Row Validation (in BaseOIFetcher, before returning):**
- `oi >= 0`, `strike > 0`, `expiry` is a valid future or current-day date
- `oi_usd >= 0`
- Drop and log any invalid rows

Derived fields computed by the store (not stored raw):
```
oi_change       : float     # oi_now - oi_prev_snapshot
oi_change_pct   : float     # (oi_change / oi_prev) × 100
```

---

## 6. File Structure

### 6.1 New Files

```
webui/backend/routes/oi/
    __init__.py              # export oi_bp
    oi_fetchers.py           # one class per exchange + base class
    oi_store.py              # in-memory store, SQLite persistence, spike detector
    oi_api.py                # Flask blueprint, background refresh thread

webui/frontend/src/components/oi/
    OIPanel.js               # top-level panel: expiry selector, exchange filter, 3 tabs
    OIBarChart.js            # Recharts BarChart — absolute OI view (screenshot 2)
    OIChangeChart.js         # Recharts BarChart — OI change view (screenshot 1)
    OITable.js               # strike table with per-exchange breakdown
    OISpikeLog.js            # real-time spike event feed + toast trigger

webui/frontend/src/pages/
    OIPage.js                # page wrapper (CollapsibleCard pattern)
```

### 6.2 Modified Files

```
webui/backend/routes/__init__.py     # add: from .oi import oi_bp
webui/backend/app.py                 # add: app.register_blueprint(oi_bp)
webui/frontend/src/App.js            # add lazy import + Route for /oi
webui/frontend/src/pages/index.js    # export OIPage
webui/frontend/src/config/navigationSections.js   # add sidebar entry
```

**Total: 8 new files, 5 file edits.**

---

## 7. Component Architecture

### 7.1 Backend

```
oi_fetchers.py
│
├── class BaseOIFetcher (ABC)
│     fetch() → list[OIRow]      # must implement
│     _parse_instrument()        # shared symbol parsing helper (regex with named capture groups)
│     _validate_row(row)         # 🔧 validate oi>=0, strike>0, expiry format
│     _http_get()                # shared retry + timeout helper
│     │                          # 🔧 connect_timeout=3s, read_timeout=10s (not flat 5s)
│     │                          # 🔧 exponential backoff: 1s, 2s, 4s between retries
│     _session: requests.Session # 🔧 persistent connection pool per exchange
│     contract_multiplier: float # 🔧 default 1.0 — override per exchange if needed
│     enabled: bool              # 🔧 feature flag — disable exchange without code deploy
│
├── class DeribitOIFetcher(BaseOIFetcher)
├── class BinanceOIFetcher(BaseOIFetcher)
│     │  🔧 Must pre-fetch expiry list, then loop per-expiry with rate limiting
│     │  🔧 Uses native sumOpenInterestUSD (no manual oi × price calculation)
├── class DeltaGlobalOIFetcher(BaseOIFetcher)
└── class DeltaIndiaOIFetcher(BaseOIFetcher)   # wraps existing options_client


oi_store.py
│
├── class OIStore
│     _snapshots: dict           # (exchange, underlying, expiry, strike, type) → deque[OIRow]
│     │                          # 🔧 maxlen=20 (15min window ÷ 60s interval + safety margin)
│     _db_path: str              # 🔧 NO shared _sqlite_conn — use per-thread connections
│
│     _get_conn()                # 🔧 thread-local sqlite3.connect() with WAL mode
│     merge_snapshot(rows)       # ingest one exchange's fresh data
│     get_aggregated(expiry, underlying, window_min) → AggregatedOI
│     get_expiries(underlying)   → list[str]
│     get_spike_log(last_n)      → list[SpikeEvent]
│
└── class OISpikeDetector
      threshold_pct: float       # configurable, default 15%
      window_minutes: int        # lookback window, default 15
      min_oi_usd: float          # 🔧 default 500_000 (not 100K — too noisy for BTC)
      min_oi_change_usd: float   # 🔧 NEW: absolute change filter, default 200_000
      _cooldown: dict            # 🔧 NEW: (exch, strike, type) → last_fire_ts
      cooldown_minutes: int      # 🔧 NEW: suppress repeat spikes, default 30
      check(prev, curr) → SpikeEvent | None
      check_aggregate(rows)      # 🔧 NEW: detect aggregate spike across all exchanges
      SpikeEvent: {strike, type, exchange, oi_prev, oi_now, change_pct, severity, ts}
      severity: "medium" (15–40%) | "high" (>40%)


oi_api.py
│
├── Blueprint: oi_bp  prefix=/api/oi
│   Logger: logging.getLogger('oi_aggregator')   # 🔧 dedicated logger, not root
│
├── GET  /snapshot          params: underlying, expiry
│                           returns: aggregated rows per strike (call+put)
│
├── GET  /change            params: underlying, expiry, window_min (default 60)
│                           returns: oi_change per strike
│
├── GET  /expiries          params: underlying
│                           returns: list of available expiry dates
│
├── GET  /spikes            params: last_n (default 20)
│                           returns: recent SpikeEvent list
│
├── GET  /config            returns: current thresholds
├── POST /config            body: {threshold_pct, window_minutes, refresh_interval_sec}
│
├── GET  /health            🔧 NEW: per-exchange status (last_fetch_ts, avg_latency, up/down)
│
└── 🔧 Background thread (daemon) — MUST use eventlet-safe real OS thread
      Pattern: eventlet.patcher.original('threading').Thread (same as ssdh_monitor.py)
      DO NOT use ThreadPoolExecutor (monkey-patched under eventlet → greenlets → blocks hub)
      Runs every refresh_interval_sec (default 60)
      🔧 Lazy start: only begins fetching when first client joins SocketIO room 'oi'
      Fetches all enabled exchanges using eventlet.spawn() for cooperative concurrency
      Calls store.merge_snapshot() for each
      🔧 Emits socketio 'oi_update' with DELTA rows only (changed rows, not full snapshot)
      🔧 Emits to namespace '/oi' (not default '/') to avoid flooding MMM/IC clients
      Emits socketio 'oi_spike' for each SpikeEvent detected
```

> 🔧 **CRITICAL — Eventlet Threading Pattern:**
> This codebase runs under gunicorn + eventlet. `threading.Thread` is monkey-patched to greenlets.
> Using `ThreadPoolExecutor` for HTTP fetches WILL block the eventlet hub, freezing ALL Flask
> request handling, SocketIO heartbeats, and the MMM trading loop.
>
> **Proven safe pattern** (from `options_client.py`, `ssdh_monitor.py`):
> ```python
> from eventlet.patcher import original as _ep_original
> _RealThread = _ep_original('threading').Thread
> t = _RealThread(target=_oi_refresh_loop, daemon=True, name='oi-refresh')
> t.start()
> ```

### 7.2 Frontend

```
OIPage.js
└── CollapsibleCard (title="Open Interest Aggregator")
    └── OIPanel.js
        ├── Controls row
        │     Underlying selector (BTC / ETH)
        │     Expiry selector (populated from /api/oi/expiries)
        │     Exchange multi-select (All / Deribit / Binance / Delta Global / Delta India)
        │     Strike range input (ATM ± N)
        │     Refresh button + "Last updated" timestamp
        │
        ├── Summary strip (like screenshot 2 footer)
        │     Total Call OI | Total Put OI | PCR | Underlying Price | Active Exchanges
        │
        └── Tabs
            ├── Tab 1: "OI Change"     → OIChangeChart.js   (screenshot 1)
            ├── Tab 2: "Open Interest" → OIBarChart.js       (screenshot 2)
            ├── Tab 3: "Table"         → OITable.js
            └── Tab 4: "Spike Log"     → OISpikeLog.js


OIChangeChart.js  (replicates screenshot 1 exactly)
    Recharts <BarChart>
      X-axis: strike prices
      Y-axis: OI change (positive up, negative down)
      Two <Bar> series:
        Put OI Change  → green  (#4caf50)
        Call OI Change → red    (#f44336)
      <ReferenceLine y=0> (zero baseline)
      <ReferenceLine x=atmStrike> (dotted vertical, "NIFTY / BTC XXXX" tooltip)
      <Legend> bottom
      Exchange breakdown in <Tooltip> on hover


OIBarChart.js  (replicates screenshot 2 exactly)
    Same structure as OIChangeChart but Y-axis shows absolute OI (all positive)
    Same colour scheme
    Same ATM reference line


OITable.js
    MUI <DataGrid> or manual table
    🔧 Default columns (6): Strike | Put OI | Call OI | PCR | Put Chg | Call Chg
    🔧 Per-exchange breakdown is a toggle/expand row — NOT shown by default (16 columns = overload)
      Expandable: Deribit Put | Deribit Call | Binance Put | Binance Call | DeltaG Put | DeltaG Call | DeltaIN Put | DeltaIN Call
    Sorted by strike ascending (default)
    🔧 Default range: ATM ± 20 strikes (configurable N). Use react-window for virtualised scrolling.
    Row colour intensity = heatmap of OI magnitude (CSS opacity on background)
    ATM row highlighted with border
    🔧 Per-exchange staleness indicator in header: "Deribit: 45s ✅ | Binance: 180s ⚠️"


OISpikeLog.js
    Real-time list of SpikeEvent objects (newest first)
    Columns: Time | Exchange | Underlying | Expiry | Strike | Type | Prev OI | Curr OI | Chg% | Severity
    Severity badge: orange (medium) / red (high)
    On SocketIO 'oi_spike' event: push to list + fire MUI Snackbar toast
    Max 200 rows displayed (virtualised with react-window)
```

---

## 8. Data Flow (End-to-End)

```
[Background Thread — real OS thread via eventlet.patcher.original('threading').Thread]
[Runs every 60s — 🔧 lazy-starts on first SocketIO room join]
    │
    ├── DeribitOIFetcher.fetch()      ──┐
    ├── BinanceOIFetcher.fetch()      ──┤  🔧 concurrent via eventlet.spawn() (NOT ThreadPoolExecutor)
    ├── DeltaGlobalOIFetcher.fetch()  ──┤
    └── DeltaIndiaOIFetcher.fetch()   ──┘
                │
                ▼
        OIStore.merge_snapshot(rows_per_exchange)
                │
                ├── Write to SQLite oi_snapshots table
                ├── Update in-memory deque per (exchange, expiry, strike, type)
                └── OISpikeDetector.check(prev, curr) for each row
                        │
                        └── if spike → socketio.emit('oi_spike', SpikeEvent, namespace='/oi')
                │
                ├── 🔧 OISpikeDetector.check_aggregate() for cross-exchange net spikes
                │
                └── socketio.emit('oi_update', delta_rows_only, namespace='/oi')
                        │                    🔧 only changed rows, not full snapshot
                        ▼
            [Frontend — OIPanel.js]
                        │
                        ├── on 'oi_update' → merge delta into state → re-render charts + table
                        └── on 'oi_spike'  → push to spike log + show toast


[User action — expiry/exchange filter change]
    │
    └── GET /api/oi/snapshot?underlying=BTC&expiry=YYYY-MM-DD
                │
                └── OIStore.get_aggregated() → filtered rows → React state → charts
```

---

## 9. SQLite Schema

🔧 **Database Pragmas (set on every connection open):**
```sql
PRAGMA journal_mode=WAL;       -- mandatory for concurrent read/write
PRAGMA busy_timeout=5000;       -- wait up to 5s on lock instead of failing
PRAGMA synchronous=NORMAL;      -- safe with WAL, better write performance
```

🔧 **Connection Pattern:** Per-thread connections via `threading.local()`. No shared `_sqlite_conn`.

**Table: `oi_snapshots`**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `ts` | TEXT | ISO datetime UTC |
| `exchange` | TEXT | |
| `underlying` | TEXT | |
| `expiry` | TEXT | ISO date |
| `strike` | REAL | 🔧 REAL not INTEGER — some exchanges use decimal strikes |
| `type` | TEXT | "call" \| "put" |
| `oi` | REAL | |
| `oi_usd` | REAL | |

🔧 **Indexes (create on init):**
```sql
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON oi_snapshots(ts);  -- for retention DELETE
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON oi_snapshots(underlying, expiry, strike, type, ts);  -- for spike lookups
```

🔧 **Write strategy:** Use `executemany()` in a single transaction per merge cycle. ~1600 rows/cycle.

**Table: `oi_spike_events`**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `ts` | TEXT | ISO datetime UTC |
| `exchange` | TEXT | 🔧 "aggregate" for cross-exchange spikes |
| `underlying` | TEXT | |
| `expiry` | TEXT | |
| `strike` | REAL | 🔧 REAL not INTEGER |
| `type` | TEXT | |
| `oi_prev` | REAL | |
| `oi_curr` | REAL | |
| `change_pct` | REAL | |
| `severity` | TEXT | "medium" \| "high" |

**Retention:** Auto-delete `oi_snapshots` rows older than 7 days (run on startup + daily). 🔧 Run `VACUUM` after retention delete to reclaim space.
**Location:** `webui/backend/data/oi_data.db`

---

## 10. Spike Detection Logic

### 10.1 Per-Exchange Spike Detection
```
For each (exchange, underlying, expiry, strike, type):

    prev_oi = most recent snapshot older than window_minutes
    curr_oi = latest snapshot

    if prev_oi is None or prev_oi == 0:
        skip (no baseline)

    🔧 Check cooldown: if (exchange, strike, type) fired within cooldown_minutes → skip

    change_pct = (curr_oi - prev_oi) / prev_oi × 100
    change_usd = |curr_oi_usd - prev_oi_usd|   # 🔧 absolute USD change

    if |change_pct| >= threshold_pct
       AND curr_oi_usd >= min_oi_usd            # percentage filter
       AND change_usd >= min_oi_change_usd:     # 🔧 absolute filter (prevents small OI noise)
        severity = "high"   if |change_pct| > 40
                   "medium"  otherwise
        emit SpikeEvent
        🔧 record cooldown timestamp for (exchange, strike, type)
```

### 10.2 🔧 Aggregate Spike Detection (NEW)
```
For each (underlying, expiry, strike, type):
    sum prev_oi across all exchanges
    sum curr_oi across all exchanges

    Same threshold logic as above, but exchange = "aggregate"

    Purpose: detects net OI changes that matter for trading.
    A whale moving OI from Deribit → Binance fires per-exchange spikes
    but net-zero aggregate — the aggregate detector suppresses this noise.
```

### 10.3 Configuration
```
Configurable via POST /api/oi/config:
    threshold_pct       default: 15
    window_minutes      default: 15
    min_oi_usd          default: 500_000   🔧 raised from 100K (1.67 BTC too noisy)
    min_oi_change_usd   default: 200_000   🔧 NEW: absolute change filter
    cooldown_minutes    default: 30        🔧 NEW: suppress repeat spikes
```

🔧 **Known limitation:** 60s sampling interval means intra-minute OI movements are invisible. A block trade that opens and partially closes within the same 60s interval will not be detected.

---

## 11. Error Handling

| Failure | Behaviour |
|---|---|
| Exchange fetch fails (timeout / 5xx) | Log warning, skip that exchange for this cycle, continue with others. 🔧 Track per-exchange failure count; expose via `GET /health`. |
| All exchanges fail | Emit `oi_update` with `{error: "all fetchers failed"}`, frontend shows stale-data banner |
| SQLite write fails | Log error, continue with in-memory data only |
| Frontend WebSocket disconnects | Auto-reconnect (existing SocketIO client handles this); fallback to polling `/api/oi/snapshot` |
| Spike detector: division by zero | Guard: skip if `prev_oi == 0` |
| 🔧 Exchange returns invalid data | Validate each OIRow: `oi >= 0`, `strike > 0`, `expiry` is valid date. Drop and log invalid rows. |
| 🔧 Exchange returns wrong schema | Log full response on first call per startup; alert if schema changes |
| 🔧 Refresh cycle overlaps (prev cycle still running) | Skip this cycle, log warning. Never run two fetch cycles concurrently. |

---

## 12. Phase Execution Order

| Phase | What | Files Touched | Dependency |
|---|---|---|---|
| **1** | Exchange fetchers + base class + normalised schema | `oi_fetchers.py` | None |
| **2** | OI store (in-memory + SQLite) + spike detector | `oi_store.py` | Phase 1 schema |
| **3** | Flask blueprint + background thread + REST endpoints | `oi_api.py`, `__init__.py` | Phases 1 + 2 |
| **4** | Wire blueprint into app | `routes/__init__.py`, `app.py` | Phase 3 |
| **5** | OIBarChart + OIChangeChart (Recharts) | `OIBarChart.js`, `OIChangeChart.js` | None (mock data) |
| **6** | OITable | `OITable.js` | Phase 5 shape |
| **7** | OISpikeLog + toast | `OISpikeLog.js` | Phase 5 shape |
| **8** | OIPanel — wires tabs, controls, SocketIO | `OIPanel.js` | Phases 5–7 |
| **9** | Page + route + nav | `OIPage.js`, `App.js`, `pages/index.js`, `navigationSections.js` | Phase 8 |

Phases 1–4 are backend-only. Phases 5–7 can be built in parallel with 1–4 using mock data. Phase 8 connects them. Phase 9 is pure wiring.

---

## 13. Testing Checklist (Before Marking Done)

### Backend
- [ ] Each fetcher returns valid `OIRow` list when called against live exchange
- [ ] `merge_snapshot()` correctly computes `oi_change` vs prior snapshot
- [ ] Spike fires correctly when OI jumps by more than threshold
- [ ] Spike does NOT fire on first snapshot (no baseline)
- [ ] `/api/oi/snapshot` returns correct aggregated data filtered by expiry
- [ ] `/api/oi/expiries` returns deduplicated list
- [ ] Background thread survives one exchange being down
- [ ] SQLite retention delete runs without error
- [ ] 🔧 Expiry parser unit tests: 20+ real instrument names per exchange
- [ ] 🔧 OI USD calculation verified per exchange (Binance uses native field, not oi × price)
- [ ] 🔧 Background thread uses real OS thread (not eventlet greenlet) — verify with `threading.current_thread()`
- [ ] 🔧 Deque maxlen=20 confirmed — memory stable after 24h soak test
- [ ] 🔧 SQLite WAL mode confirmed (`PRAGMA journal_mode` returns `wal`)
- [ ] 🔧 Spike cooldown works — same strike does NOT re-fire within 30 minutes
- [ ] 🔧 Aggregate spike detection fires when net OI across exchanges changes
- [ ] 🔧 Row validation drops invalid data (negative OI, zero strike) and logs warning
- [ ] 🔧 Fetch cycle overlap guard: second cycle skips if first is still running
- [ ] 🔧 MMM algo unaffected: confirm heartbeat latency does not increase when OI fetching is active

### Frontend
- [ ] Bar chart renders with correct green/red colouring
- [ ] ATM reference line appears at correct strike
- [ ] Exchange filter correctly hides/shows data from that source
- [ ] OI table PCR = Put OI / Call OI (not reversed)
- [ ] Spike toast appears within 2s of socket event
- [ ] Stale data banner shows if no `oi_update` in > 120s
- [ ] 🔧 Per-exchange staleness indicator shows individual exchange freshness
- [ ] 🔧 Table defaults to 6 columns; per-exchange breakdown is toggle/expand
- [ ] 🔧 Default strike range ATM ± 20 (not all 200+ strikes)
- [ ] Works on mobile (responsive layout)

---

## 14. Out of Scope (This Plan)

- NSE / NIFTY equity OI (different data source entirely — separate plan if needed)
- OI-based trading signals or automated actions
- Authentication for the config endpoint (inherits whatever the app uses globally)

---

## 15. 🔧 Phase 2 Roadmap (Post-Launch)

Features deferred from the audit but high-value for future iterations:

| Feature | Value | Effort |
|---|---|---|
| Historical OI time-series chart per strike | Most-requested OI feature. Data already in SQLite (7-day retention). | Medium |
| Max pain calculation + display on charts | Trivially computed from aggregated data. High signal. | Low |
| PCR trend sparkline in summary strip | PCR *change* over time is more actionable than point-in-time PCR. | Low |
| OI vs Price correlation overlay | OI without price context is incomplete. Overlay underlying price on OI change chart. | Medium |
| Cross-exchange OI divergence signal (HHI) | Flag single-venue risk concentration. Herfindahl index per strike. | Medium |
| Liquidity-weighted aggregation | Weight each exchange's OI by bid-ask spread or volume for truthful picture. | High |
| Telegram/ntfy spike alerts | Spikes are time-critical; browser may be closed. Wire to existing Telegram service. | Low |
| Exchange health status dashboard | Small indicator per exchange: ✅ Live / ⚠️ Stale / ❌ Down with latency. | Low |

---

## 16. 🔧 Production Hardening Notes

### 16.1 Time Synchronization

All exchange snapshots are bucketed into a 60-second epoch window:
```
fetch_epoch = timestamp // 60 * 60   (UTC epoch seconds)
```

Rules:
- Aggregation only combines rows sharing the **same** `fetch_epoch`
- If an exchange's latest snapshot is >120s behind the current epoch, it is flagged **stale** and excluded from aggregation totals (still displayed separately)
- UI shows per-exchange age indicator: ✅ <60s | ⚠️ 60–120s | ❌ >120s

### 16.2 Memory Safety

| Dimension | Hard Cap | Eviction Strategy |
|---|---|---|
| Strikes per (underlying, expiry) | 300 | Drop far-OTM strikes with zero OI across all exchanges |
| Active expiries tracked | 12 | Auto-evict expired expiries on every merge cycle |
| Deque entries per key | 20 | Oldest snapshot auto-dropped (deque `maxlen`) |
| **Worst-case total** | 300 × 12 × 4 × 2 × 20 = 576,000 entries | ~115MB ceiling (acceptable) |

On every merge cycle: prune keys where all deque entries show `oi == 0` across all exchanges.

### 16.3 Data Quality Guardrails

| Scenario | Guardrail |
|---|---|
| Exchange sends OI=0 for a previously-active strike | **2-cycle confirmation:** Hold the zero for 2 consecutive cycles before accepting. Prevents API glitch flash-drops. |
| Duplicate rows in single fetch batch | Deduplicate by `(exchange, expiry, strike, type)` — keep latest timestamp |
| OI change >500% in one cycle | Flag as **"unverified"** severity in spike log. Require 2 consecutive readings to upgrade to "high" |
| Exchange returns negative OI or negative strike | Drop row immediately, log as data corruption warning |

### 16.4 Failure Mode Simulation

| Scenario | System Behaviour | User Impact |
|---|---|---|
| Deribit lags 5 minutes | Epoch bucketing excludes stale Deribit data. UI shows ❌ next to Deribit. Aggregation proceeds with 3 exchanges. | Slightly lower OI totals; clearly labeled. |
| Binance sends garbage data | Row validation drops invalid rows. Log warning with full response. Aggregation continues without Binance. | Spike log may show "data quality" warning entry. |
| Background thread takes 90s (>60s interval) | Overlap guard detects running cycle, skips this tick. Next tick proceeds normally. | "Last updated" timestamp ages to 90s then refreshes. |
| SocketIO lag 10s to frontend | Delta update queued by engine.io. Client receives burst of updates. Stale banner does NOT trigger (120s threshold). | Brief visual stutter as charts update with batched data. |
| Backend crash + restart | Deques are empty (lost). SQLite has historical data. Spike detector has no baseline for 1 cycle. | 60s blind window for spikes. OI data rebuilds within 1 cycle. |

### 16.5 MMM Isolation Safety Guarantee

This system **CANNOT** affect the MMM trading loop. Here is why:

1. **Thread isolation:** OI uses `eventlet.patcher.original('threading').Thread` — a real OS thread. MMM greenlets run on the eventlet hub. Different scheduling domains. OI cannot block the hub.

2. **Network isolation:** OI fetchers use their own `requests.Session` instances hitting external exchanges (Deribit, Binance, Delta Global). MMM uses `UnifiedAPIClient` singleton hitting Delta India. No shared HTTP connections.

3. **SocketIO isolation:** OI emits on namespace `/oi`. MMM emits on namespace `/`. Different event buses. A flood of OI updates cannot backpressure MMM heartbeats.

4. **No shared state:** OI has its own `OIStore` and `oi_data.db`. MMM has its own `mmm_state.py` and session files. Zero data coupling.

5. **Fail-safe registration:** Blueprint registered with `try/except`. If OI import fails (missing dependency, syntax error), the app starts normally without OI. MMM is unaffected.

6. **Lazy initialization:** Background thread starts only when first client connects to `/oi` namespace. If no one opens the OI page, zero CPU/memory/network overhead.
