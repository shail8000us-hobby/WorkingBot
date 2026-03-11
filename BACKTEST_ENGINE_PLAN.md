# Backtesting Engine — Complete Architecture Plan
**Date:** March 10, 2026  
**Status:** PLANNING — Awaiting Implementation  
**Scope:** MMM Algo (primary) + Generic framework for all future algos  
**Data Source:** Delta Exchange India Historical API  

---

## 0. Design Principles

1. **Fully independent** — Zero modifications to any live trading file. The backtesting engine is a self-contained module.
2. **Real data, not synthetic** — Uses Delta Exchange India's actual historical options data (OHLCV candles + expired chain snapshots).
3. **Reuse production logic** — MMM modules (`mmm_engine.py`, `mmm_trigger.py`, etc.) are imported in read-only mode via a thin adapter. Not rewritten, not duplicated.
4. **Generic framework** — The core pipeline (data collector → data store → backtester → reporter) is algo-agnostic. MMM plugs in as one concrete strategy adapter.
5. **Non-destructive file layout** — All new files live inside `backtesting/` (a new top-level directory). Nothing inside `webui/`, `bot/`, `backtest/`, or `backtest_ui/` is touched.
6. **Transparent slippage** — Execution is simulated using bid/ask from the chain snapshot, not theoretical mark price.

---

## 1. File Structure (New Module — `backtesting/`)

```
backtesting/                              ← NEW top-level module (does NOT touch anything else)
│
├── README.md                             ← Quick-start guide
├── requirements.txt                      ← pyarrow, pandas, requests, scipy, etc.
│
├── data_collector/                       ← Phase 1: Fetch & store historical data
│   ├── __init__.py
│   ├── delta_client.py                   ← REST API client for Delta Exchange India
│   ├── chain_collector.py                ← Fetch expired option chain snapshots
│   ├── candle_collector.py               ← Fetch 1-min OHLCV for each symbol
│   ├── expiry_resolver.py                ← Resolve past 0DTE expiry dates for BTC/ETH
│   ├── rate_limiter.py                   ← Token-bucket rate limiter (respect API limits)
│   └── collect_session.py                ← Orchestrator: run full data collection for a date range
│
├── data_store/                           ← Phase 2: Storage layer
│   ├── __init__.py
│   ├── schema.py                         ← Parquet column schema + validation
│   ├── store.py                          ← Read/write parquet files by date + underlying
│   ├── chain_index.py                    ← SQLite index: which expiries have been collected
│   └── integrity_check.py               ← Verify data completeness, flag missing candles
│
├── engine/                               ← Phase 3: Core simulation engine (algo-agnostic)
│   ├── __init__.py
│   ├── sim_clock.py                      ← Virtual clock: iterates timestamps from parquet data
│   ├── sim_chain.py                      ← Options chain view at any point in time
│   ├── sim_broker.py                     ← Simulated order executor (respects bid/ask slippage)
│   ├── sim_margin.py                     ← Margin calculator (Delta Exchange formulas)
│   ├── session_runner.py                 ← Generic session loop: clock tick → algo heartbeat → record
│   └── base_algo_adapter.py              ← Abstract base class all strategy adapters must implement
│
├── strategies/                           ← Phase 4: Strategy adapters (one per algo)
│   ├── __init__.py
│   ├── mmm/                              ← MMM strategy adapter
│   │   ├── __init__.py
│   │   ├── mmm_adapter.py                ← Implements base_algo_adapter.py for MMM
│   │   ├── mmm_state_factory.py          ← Creates a fresh/import MMM session state dict
│   │   ├── mmm_mock_executor.py          ← Replaces mmm_executor.py (routes to sim_broker)
│   │   ├── mmm_mock_client.py            ← Replaces delta REST calls (reads from sim_chain)
│   │   └── mmm_heartbeat_bridge.py       ← Calls existing mmm_monitor heartbeat logic in dry-run mode
│   └── future_algo/                      ← Template for next algo (SSR, Grid, etc.)
│       └── __init__.py
│
├── analytics/                            ← Phase 5: Results & reporting
│   ├── __init__.py
│   ├── metrics.py                        ← P&L, Sharpe, Sortino, Max Drawdown, Win Rate, etc.
│   ├── trade_log.py                      ← Per-trade log builder
│   ├── session_report.py                 ← Session summary report generator
│   ├── comparison.py                     ← Multi-session / multi-param comparison
│   └── exporter.py                       ← Export to CSV/JSON/HTML
│
├── optimizer/                            ← Phase 6: Parameter sweep & optimization
│   ├── __init__.py
│   ├── grid_search.py                    ← Exhaustive grid search over param space
│   ├── walk_forward.py                   ← Walk-forward optimization (IS/OOS windows)
│   ├── bayesian_optimizer.py             ← Bayesian optimization (scikit-optimize)
│   └── regime_classifier.py             ← Tag each day as trending/ranging/volatile
│
├── ui/                                   ← Phase 7: Web dashboard (port 5557)
│   ├── backend/
│   │   ├── app.py                        ← Flask + SocketIO server (port 5557)
│   │   ├── api_data.py                   ← API routes for data collection status
│   │   ├── api_backtest.py               ← API routes for running backtests
│   │   └── api_analytics.py             ← API routes for viewing results
│   └── frontend/
│       └── src/
│           └── components/
│               ├── DataCollectorPanel.js ← Trigger/status of data collection
│               ├── BacktestConfigPanel.js← MMM params, date range, entry time
│               ├── ResultsDashboard.js   ← Equity curve, greeks timeline, trade log
│               ├── OptimizerPanel.js     ← Grid search heatmap
│               └── ComparisonPanel.js   ← Side-by-side session comparison
│
├── scripts/                              ← CLI scripts for running without UI
│   ├── collect_data.py                   ← CLI: collect historical data for date range
│   ├── run_backtest.py                   ← CLI: run single backtest session
│   ├── sweep_params.py                   ← CLI: parameter sweep
│   └── analyze_results.py               ← CLI: print analytics summary
│
└── tests/                                ← Unit + integration tests  
    ├── test_delta_client.py
    ├── test_sim_broker.py
    ├── test_sim_chain.py
    ├── test_mmm_adapter.py
    └── test_metrics.py
```

**Key constraint:** The only files from the production codebase that the backtesting engine imports are:
- `webui/backend/routes/mmm/mmm_engine.py` (adjustment calculations — pure math)
- `webui/backend/routes/mmm/mmm_trigger.py` (trigger evaluation — pure logic)
- `webui/backend/routes/mmm/mmm_safety.py` (safety checks — pure logic)
- `webui/backend/routes/mmm/mmm_close_at_5.py` (close-at-5 scan — pure logic)
- `webui/backend/routes/mmm/mmm_wind_down.py` (wind-down logic — pure logic)
- `webui/backend/routes/mmm/mmm_harvester.py` (M1/M3 logic — pure logic)
- `webui/backend/routes/mmm/mmm_recycler.py` (M2 logic — pure logic)
- `webui/backend/routes/mmm/mmm_constants.py` (constants)
- `webui/backend/routes/mmm/mmm_state.py` (state schema + DEFAULT_PARAMS)

These modules are stateless pure functions. **No live database, no REST calls, no SocketIO** from these imports.  
Everything that touches Delta Exchange API is replaced by `mmm_mock_client.py` and `mmm_mock_executor.py`.

---

## 2. Data Sources (Delta Exchange India)

### 2.1 Endpoints Used

| Endpoint | Purpose | Key Params |
|----------|---------|-----------|
| `GET /v2/tickers?contract_type=call_options&expiry_date=DD-MM-YYYY` | Expired options chain snapshot | `expiry_date`, `underlying_asset_symbol` |
| `GET /v2/history/candles?symbol=SYMBOL&from=TS&to=TS&resolution=1m` | 1-min OHLCV for any option symbol | `symbol`, `from`, `to`, `resolution` |
| `GET /v2/products?contract_type=call_options` | List of tradeable products (for symbol discovery) | `contract_type` |

### 2.2 Data Model Per Candle Row

Each row in the parquet store represents one 1-minute candle for one option strike:

| Column | Type | Source |
|--------|------|--------|
| `timestamp` | int64 (Unix ms) | `candle.time` |
| `date` | str | Derived from expiry |
| `underlying` | str | `BTC` / `ETH` |
| `expiry_date` | str | `DD-MM-YYYY` |
| `symbol` | str | Full option symbol |
| `strike` | float | `product.strike_price` |
| `option_type` | str | `CE` or `PE` |
| `open` | float | `candle.open` |
| `high` | float | `candle.high` |
| `low` | float | `candle.low` |
| `close` | float | `candle.close` (mark price) |
| `volume` | float | `candle.volume` |
| `bid` | float | Chain snapshot `best_bid` |
| `ask` | float | Chain snapshot `best_ask` |
| `oi` | float | Chain snapshot `oi` |
| `delta` | float | Chain snapshot `greeks.delta` |
| `gamma` | float | Chain snapshot `greeks.gamma` |
| `theta` | float | Chain snapshot `greeks.theta` |
| `vega` | float | Chain snapshot `greeks.vega` |
| `iv` | float | Chain snapshot `ask_iv` |

**Note:** Greeks and IV come from the chain snapshot (once per expiry) and are held static per strike per session. Candle data (OHLCV) provides the minute-by-minute mark price movement.

### 2.3 Storage Layout

```
backtesting/
└── historical_data/
    ├── btc/
    │   ├── 10-03-2026.parquet            ← All strikes, all minutes for BTC expiry
    │   ├── 11-03-2026.parquet
    │   └── ...
    ├── eth/
    │   └── ...
    └── index.db                          ← SQLite index: expiry → status (collected/partial/missing)
```

Each parquet file is ~50–200 MB for one full 0DTE session (depending on number of strikes × minutes).

---

## 3. Data Collection Pipeline

### Step 1 — Resolve Expiries

`expiry_resolver.py` generates the list of all past 0DTE BTC (or ETH) expiry dates.  
For BTC: Daily expiries (every day at ~08:00 UTC on Delta India).

```
Input: start_date, end_date, underlying="BTC"
Output: List of "DD-MM-YYYY" strings
```

### Step 2 — Fetch Chain Snapshot

`chain_collector.py` calls:
```
GET /v2/tickers?contract_type=call_options&expiry_date=10-03-2026&underlying_asset_symbol=BTC
GET /v2/tickers?contract_type=put_options&expiry_date=10-03-2026&underlying_asset_symbol=BTC
```
Returns: All CE and PE strikes with Greeks, IV, OI, bid/ask for that expiry.

### Step 3 — Fetch Candles Per Strike

`candle_collector.py` iterates each strike symbol and calls:
```
GET /v2/history/candles?symbol=C-BTC-92000-100326&from=1741564800&to=1741593600&resolution=1m
```
Returns: OHLCV 1-minute candles from 00:00 UTC to 08:00 UTC (expiry).

### Step 4 — Merge and Store

Candle data + chain snapshot static fields → merged into one DataFrame → written as parquet.

### Rate Limiting

Delta Exchange India rate limits: ~30 requests/sec (REST).  
`rate_limiter.py` implements a token-bucket limiter capped at 20 req/sec to stay safe.

### Collection Time Estimate

For 30 days of BTC 0DTE data:
- ~30 expiries × ~200 strikes = 6,000 symbol-level candle fetches
- At 1 fetch per 50ms: ~5 minutes total
- Storage: ~30 × 100 MB = ~3 GB

---

## 4. Simulation Engine

### 4.1 Virtual Clock (`sim_clock.py`)

Iterates minute-by-minute through the parquet data for a given expiry date.

```
For each timestamp T in sorted(parquet.timestamp.unique()):
    → yields a "tick" to the session runner
    → tick contains: timestamp T, all options premiums at T
```

The clock allows:
- **Jump**: Skip to a specific timestamp (e.g., entry at 09:15 IST)
- **Pause**: Simulate adaptive heartbeat intervals (60–1200s)
- **Expiry detection**: Auto-stop at `08:00 UTC` (Delta India BTC 0DTE expiry)

### 4.2 Simulated Chain View (`sim_chain.py`)

At any virtual timestamp T, `sim_chain.py` reconstructs the options chain:

```python
chain.get_premium(strike, side)    → close price from candle at timestamp T
chain.get_bid(strike, side)        → bid from chain snapshot (or interpolated)
chain.get_ask(strike, side)        → ask from chain snapshot (or interpolated)
chain.get_greeks(strike, side)     → delta, gamma, theta, vega at T
chain.get_oi(strike, side)         → open interest
chain.scan_chain(target_premium)   → find closest strike to target premium
```

### 4.3 Simulated Broker (`sim_broker.py`)

Handles all order execution in backtest mode:

| Action | Simulation Rule |
|--------|----------------|
| **Sell option** (short) | Execute at `bid - slippage_bps` |
| **Buy back option** (close) | Execute at `ask + slippage_bps` |
| **Market close** | Use `ask` (taker, conservative) |
| **OI filter** | If `oi < min_oi_lots`, reject order (liquidity check) |
| **Fill record** | Includes `fill_price`, `lots`, `timestamp`, `slippage_cost` |

Default slippage: 2 bps (configurable). Adjustable per simulation.

### 4.4 Margin Simulator (`sim_margin.py`)

Replicates Delta Exchange India's options margin formula:
- Short options margin = `mark_price × lots × lot_size × margin_rate`
- Tracks `available_margin` throughout session
- Blocks new sells when margin falls below threshold

### 4.5 Session Runner (`session_runner.py`)

The generic loop:

```
1. Initialize session via algo_adapter.init_session(params)
2. For each tick from sim_clock:
   a. Update sim_chain to current timestamp
   b. Call algo_adapter.on_heartbeat(timestamp, chain)
   c. Record trade log entry (P&L, positions, greeks)
   d. Check termination: algo says STOPPED or timestamp ≥ expiry
3. Compute final analytics
4. Return session_result dict
```

---

## 5. MMM Strategy Adapter

### 5.1 Architecture

The MMM adapter is a **thin shim** between the session runner and the existing MMM modules:

```
session_runner.on_heartbeat()
    ↓
mmm_adapter.on_heartbeat()
    ↓ injects mock dependencies
mmm_heartbeat_bridge.run_beat()       ← reuses mmm_monitor heartbeat logic
    ↓ calls
    ├── mmm_close_at_5.scan_closeable_positions()
    ├── mmm_harvester.run_harvest()
    ├── mmm_trigger.evaluate_triggers()
    ├── mmm_engine.calculate_adjustment() / calculate_standard_loss()
    ├── mmm_safety.run_all_checks()
    ├── mmm_wind_down.is_wind_down_active()
    └── mmm_recycler.execute_recycle() (if M2 triggered)
    ↓ all exchange calls routed to
mmm_mock_client.py                    ← reads from sim_chain, records to sim_broker
```

### 5.2 Mock Dependency Injection

Two files replace the live exchange interface in backtest mode:

**`mmm_mock_client.py`** replaces calls normally going to `rest_client`:
- `get_option_mark_price(symbol)` → reads `sim_chain.get_premium(strike, side)`
- `get_option_chain(expiry)` → returns full chain from `sim_chain`
- `get_margin()` → returns `sim_margin.get_margin_state()`
- `get_spot_price()` → reads BTC spot from data store
- `place_order(...)` → delegates to `sim_broker.place_order(...)`
- `cancel_order(...)` → delegates to `sim_broker.cancel_order(...)`

**`mmm_mock_executor.py`** replaces `mmm_executor.py` (smart execution):
- All smart execution logic stripped out (no retries, no mid-price reprice)
- Direct fill via `sim_broker.fill_at_bid_or_ask()`
- Records fill in session state identically to production

### 5.3 Session State Initialization (`mmm_state_factory.py`)

Creates a fresh MMM `session` dict using the exact same schema as `mmm_state.py`:
- `DEFAULT_PARAMS` used as parameter base
- User overrides applied on top
- Entry strike selection reuses `mmm_initializer.find_entry_strikes()` logic (against sim_chain)
- Supports all 3 modes: Fresh, Import, Adopt

### 5.4 Heartbeat Bridge (`mmm_heartbeat_bridge.py`)

Extracts the pure heartbeat logic from `mmm_monitor.py` (the ~300-line monolithic beat function) and runs it in backtest mode:

1. Set `os.environ['BACKTEST_MODE'] = 'true'` before imports
2. Replace all SocketIO `emit()` calls with no-ops (emits are logged to trade_log instead)
3. Replace `time.sleep()` with virtual clock advance
4. All Telegram alerts → no-ops in backtest mode
5. Adaptive heartbeat interval: simulated by skipping ticks in the virtual clock

---

## 6. Analytics & Metrics

### 6.1 Per-Session Metrics

| Metric | Formula |
|--------|---------|
| **Total P&L** | `realized_pnl + unrealized_pnl` |
| **Premium Collected** | Sum of all sell fills × lots × lot_size |
| **Total Fees** | Taker fee × total volume traded |
| **Net P&L** | Total P&L - Total Fees |
| **Sharpe Ratio** | `mean(daily_returns) / std(daily_returns) × √252` |
| **Sortino Ratio** | `mean(daily_returns) / std(downside_returns) × √252` |
| **Max Drawdown** | Max peak-to-trough decline in P&L timeline |
| **Calmar Ratio** | `annualized_return / max_drawdown` |
| **Win Rate** | `sessions_profitable / total_sessions` |
| **Adjustment Count** | Total # of adjustment events |
| **Avg Adjustment P&L** | Avg P&L contribution per adjustment |
| **Strike Shift Count** | # of times strike was shifted |
| **Harvest Count** | # of M1 harvests |
| **Recycle Count** | # of M2 recycles |
| **Perp Hedge P&L** | If enabled: delta-hedge contribution |
| **Slippage Cost** | Total bid/ask slippage paid |
| **Margin Utilization Peak** | Max margin% during session |
| **Close-at-5 Count** | # of close-at-5 fires |
| **Wind-down Triggered** | Bool: did wind-down activate? |

### 6.2 Weakness Probes (Built-in Test Cases)

These are automatically run during any backtest to flag specific MMM vulnerabilities:

| Probe | What It Tests | Pass Condition |
|-------|-------------|----------------|
| **Liquidity Crunch** | When OI < `min_oi_lots` on adjustment target | No fill attempted on illiquid strike |
| **Slippage Impact** | P&L diff between mark_price fills vs bid/ask fills | Log slippage cost per session |
| **Gamma Explosion** | Days where BTC moved >5% in 1 hour | Session survived (no max_loss breach) |
| **Strike Shift Timing** | Adjust `shift_threshold` across param sweep | Optimal threshold for Sharpe |
| **Both-Sides-Up** | Frequency + avg loss when both triggers fire | Quantify expected loss per occurrence |
| **Frozen Position Drag** | Margin tied to frozen positions vs active | Compare M1 on/off |
| **Perp Hedge Effectiveness** | Drawdown with/without perp hedge | Hedge reduces max_drawdown by X% |
| **Whipsaw Days** | Days with >3 alternating adjustments | Identify market regimes to avoid |

---

## 7. Parameter Optimization Framework

### 7.1 Grid Search

Defines a parameter space grid and runs one backtest per combination:

```python
PARAM_SPACE = {
    'min_trigger_move_pct': [2.0, 3.0, 4.0, 5.0],
    'shift_threshold':      [30, 50, 75, 100],
    'shift_target_premium': [75, 100, 125],
    'close_at_threshold':   [3, 5, 8],
    'premium_buffer_pct':   [3.0, 5.0, 7.0],
}
# Total: 4 × 4 × 3 × 3 × 3 = 432 combinations
```

Results stored in `backtesting/results/sweeps/` as JSON.

### 7.2 Walk-Forward Optimization

Prevents overfitting by using in-sample (IS) / out-of-sample (OOS) windows:

```
Total Period: 90 days
IS Window:    60 days → Optimize params
OOS Window:   30 days → Validate on unseen data
```

Rolling forward weekly: generates multiple IS/OOS pairs.

### 7.3 Bayesian Optimization

Uses `scikit-optimize` (Gaussian Process surrogate) to find optimal params in fewer iterations than grid search. Targets: maximize Sharpe ratio while constraining max drawdown < user-defined threshold.

### 7.4 Regime Classifier

Tags each historical session into one of:
- **Ranging**: BTC moved < 1.5% during session
- **Trending Up / Down**: BTC moved > 3% in one direction
- **Volatile / Whipsaw**: BTC reversed direction ≥ 2× with magnitude > 2%
- **Gamma Explosion**: BTC moved > 5% in any 1-hour window

Allows optimization per regime:
> "What params work best on trending days?"  
> "What's the MMM max loss expectation on volatile days?"

---

## 8. Web UI (Port 5557)

Running alongside the live trading UI (5555) and existing backtest UI (5556), port **5557** is dedicated to the new options backtesting engine.

### 8.1 Pages / Panels

| Panel | Function |
|-------|---------|
| **Data Collector** | Select date range + underlying → view collection status per expiry → progress bar |
| **Backtest Config** | Choose expiry/expiries, entry time, MMM params (pre-filled from DEFAULT_PARAMS) → Run |
| **Live Progress** | Real-time WebSocket stream: current timestamp, P&L, positions, last event |
| **Session Results** | Equity curve (Recharts), P&L timeline, trade log table, Greeks timeline, weakness probe results |
| **Parameter Sweep** | Grid search config → progress → Sharpe heatmap → best params auto-filled |
| **Session Comparison** | Select 2+ past sessions → overlay equity curves → diff metrics table |
| **Regime Analysis** | Distribution of results by regime tag |

### 8.2 Port Assignment

| Port | Service |
|------|---------|
| 5555 | Live Trading WebUI |
| 5556 | Grid Backtest UI (existing) |
| 5557 | Options Backtest UI (NEW) |

---

## 9. Implementation Phases

### Phase 1 — Data Infrastructure (1 week)

**Goal:** Be able to collect and store 30 days of historical BTC 0DTE data.

**Deliverables:**
- `data_collector/delta_client.py` — authenticated REST client
- `data_collector/expiry_resolver.py` — BTC daily expiry list
- `data_collector/chain_collector.py` — fetch expired chain snapshot
- `data_collector/candle_collector.py` — fetch 1-min candles per symbol
- `data_collector/rate_limiter.py` — 20 req/sec token bucket
- `data_collector/collect_session.py` — orchestrator
- `data_store/schema.py` — parquet schema + validation
- `data_store/store.py` — read/write parquet by date
- `data_store/chain_index.py` — SQLite collection status
- `scripts/collect_data.py` — CLI runner

**Verification:** Run `scripts/collect_data.py --days 3 --underlying BTC` → 3 parquet files created, verified with `integrity_check.py`.

---

### Phase 2 — Simulation Engine (1 week)

**Goal:** A generic, tested simulation clock + chain + broker.

**Deliverables:**
- `engine/sim_clock.py`
- `engine/sim_chain.py`
- `engine/sim_broker.py`
- `engine/sim_margin.py`
- `engine/base_algo_adapter.py`
- `tests/test_sim_broker.py` — unit tests for fill logic
- `tests/test_sim_chain.py` — unit tests for chain view

**Verification:** Run `pytest backtesting/tests/` — all tests pass.

---

### Phase 3 — MMM Adapter (1 week)

**Goal:** Be able to run a complete simulated MMM session on 1 day's data.

**Deliverables:**
- `strategies/mmm/mmm_adapter.py`
- `strategies/mmm/mmm_state_factory.py`
- `strategies/mmm/mmm_mock_client.py`
- `strategies/mmm/mmm_mock_executor.py`
- `strategies/mmm/mmm_heartbeat_bridge.py`
- `engine/session_runner.py`
- `scripts/run_backtest.py` — CLI runner
- `tests/test_mmm_adapter.py`

**Verification:** 
```bash
python backtesting/scripts/run_backtest.py \
  --date 08-03-2026 \
  --entry-time 09:15 \
  --desired-ce-premium 150 \
  --desired-pe-premium 150 \
  --initial-lots 10
```
Outputs session result JSON with P&L, adjustment log, trade log.

---

### Phase 4 — Analytics (3 days)

**Goal:** All key metrics computable from any session result.

**Deliverables:**
- `analytics/metrics.py`
- `analytics/trade_log.py`
- `analytics/session_report.py`
- `analytics/comparison.py`
- `analytics/exporter.py`
- `tests/test_metrics.py`
- `scripts/analyze_results.py`

---

### Phase 5 — Parameter Optimizer (4 days)

**Goal:** Run a grid search over MMM params on last 30 days.

**Deliverables:**
- `optimizer/grid_search.py`
- `optimizer/walk_forward.py`
- `optimizer/bayesian_optimizer.py`
- `optimizer/regime_classifier.py`
- `scripts/sweep_params.py`

---

### Phase 6 — Web UI (1 week)

**Goal:** Visual interface for running backtests, viewing results, running sweeps.

**Deliverables:**
- `ui/backend/app.py` (Flask, port 5557)
- `ui/backend/api_data.py`
- `ui/backend/api_backtest.py`
- `ui/backend/api_analytics.py`
- `ui/frontend/` — React app with all panels

---

## 10. Critical Design Decisions

### 10.1 Why Parquet?

- Columnar format → extremely fast column-level reads (e.g., fetch all close prices for one strike)
- PyArrow + Pandas integration is first-class
- ~5× compression vs CSV
- Can read a single day's data into memory in milliseconds

### 10.2 Why Not Modify Existing `backtest/` Module?

The existing `backtest/` module is designed for the **Grid Bot** (futures perpetuals — price candles only). MMM needs:
- Options chain (multiple strikes × CE/PE)
- Greeks, IV, OI data
- Different session lifecycle (entry → heartbeat loop → expiry)
- Slippage on options bid/ask (not futures orderbook)

Modifying the existing module would either break the Grid Bot backtest or create unmanageable coupling.

### 10.3 Why Import Production MMM Modules Instead of Rewriting?

- Guaranteed **behavior parity**: the same exact trigger, engine, and safety logic runs in backtest
- If MMM is fixed in production, the fix is automatically tested in backtest
- Avoids the classic "backtest uses a different formula than production" bug

### 10.4 Slippage Model

| Scenario | Slippage Source |
|----------|----------------|
| **Entry sell** | `best_bid` from chain snapshot |
| **Adjustment sell** | `best_bid` from chain snapshot |
| **Close-at-5 buy** | `best_ask` from chain snapshot |
| **Market close (wind-down)** | `best_ask + 2%` (conservative) |
| **OI filter** | Skip strike if `oi < 50 lots` |

Chain snapshot Greek/bid/ask data is available at the **daily** granularity (from the expired chain endpoint). Intraday bid/ask is approximated using:
- `bid ≈ close × (1 - iv × bid_ask_half_spread_factor)`
- Or: interpolate from open/close range

### 10.5 Perp Hedge in Backtest

The perp hedge component (`mmm_perp_hedge.py`) requires BTC perpetual candle data. This is available from:
```
GET /v2/history/candles?symbol=BTCUSD&resolution=1m&from=...&to=...
```
This data is collected alongside options data in Phase 1.

---

## 11. Data Limitations & Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Greeks only from chain snapshot (not intraday) | Greeks treated as static per session | Acceptable for 0DTE — Greeks don't change drastically within one day |
| Bid/ask from chain snapshot (not intraday) | Slippage approximated | Use conservative `ask × 1.02` for buybacks |
| Rate limit: ~6,000 requests per 30-day collection | ~5 min collection time | Token-bucket limiter; retry on 429 |
| Missing candle data (API gaps) | Tick gaps in virtual clock | `integrity_check.py` flags, candle interpolated from prev/next |
| No Level 2 orderbook depth | Cannot simulate partial fills | Assume fills up to OI limit; flag low-OI strikes |

---

## 12. Known MMM Weaknesses to Validate in Backtest

From the user-provided analysis and MMM documentation:

| Weakness | Test Design |
|---------|------------|
| Liquidity crunch during adjustment | Count sessions where target strike had OI < 100 lots |
| Slippage on close-at-5 | Compare mark_price fills vs ask fills → P&L delta |
| Gamma explosion in fast markets | Flag sessions where BTC moved >5% in 1hr; measure survival rate |
| Strike shift timing | Sweep `shift_threshold` from 30→150; optimize for Sharpe |
| Both-sides-up frequency | Count occurrences; log avg P&L impact per occurrence |
| Frozen position drag | Compare sessions: M1 harvest ON vs OFF |
| Perp hedge effectiveness | Compare max_drawdown: perp ON vs OFF |
| Whipsaw / reversal cascade | Count sessions hitting whipsaw_limit; log params that triggered it |

---

## 13. Files That Are NOT Modified

These existing files remain completely untouched:

- `webui/backend/routes/mmm/*.py` (all production MMM modules)
- `webui/backend/app.py`
- `backtest/*.py` (Grid bot backtest)
- `backtest_ui/*` (Grid backtest UI)
- `bot/*.py`
- `config.yaml`
- `data/*.db`
- Any live trading configuration

---

## 14. Future Algo Extension Points

When a new algo (e.g., SSR straddle, turbo-theta) needs backtesting:

1. Create `backtesting/strategies/new_algo/`
2. Implement `new_algo_adapter.py` extending `base_algo_adapter.py`
3. Create `new_algo_mock_client.py` for exchange call mocking
4. The entire `engine/`, `data_collector/`, `data_store/`, `analytics/`, `optimizer/` infrastructure is immediately reusable

---

## 15. Summary Timeline

| Phase | Duration | Outcome |
|-------|---------|---------|
| Phase 1: Data Infrastructure | 1 week | 30 days of real BTC options data collected |
| Phase 2: Simulation Engine | 1 week | Generic clock/broker/chain tested |
| Phase 3: MMM Adapter | 1 week | Full MMM session replay on real data |
| Phase 4: Analytics | 3 days | All metrics + export working |
| Phase 5: Optimizer | 4 days | Grid search + walk-forward + Bayesian |
| Phase 6: Web UI | 1 week | Visual dashboard at port 5557 |
| **Total** | **~5 weeks** | **Production-grade backtesting engine** |

---

*This plan was created on March 10, 2026. Awaiting implementation approval.*
