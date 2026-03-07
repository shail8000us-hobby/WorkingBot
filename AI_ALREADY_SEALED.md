# AI_ALREADY_SEALED.md — Sealed Function Registry
> Last Updated: March 5, 2026
> Protocol Reference: See [AI_SEAL.md](AI_SEAL.md) for the sealing process.

---

## HOW TO READ THIS FILE

| Column | Meaning |
|---|---|
| Function Name | Exact function name in code |
| File Path | Relative path from project root |
| Version | Bumped every time function is unsealed + changed |
| Sealed On | Date sealed was confirmed working |
| Test File | Where the contract test lives |
| Status | SEALED / UNSEALED (in progress) |
| Notes | Anything important about this function |

---

## RUN ALL SEALED TESTS — ONE COMMAND

```bash
python3 -m pytest webui/ bot/ -m sealed -v
```

> This runs every sealed function test across the entire project automatically.
> Every new sealed function is tagged with `@pytest.mark.sealed` — no manual path tracking needed.
> Run this before every deployment, every morning, and after any code change.

---

## SEALED FUNCTIONS REGISTRY

| # | Function Name | File Path | Version | Sealed On | Test File | Status | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `get_expirations` | `webui/backend/options_chain/chain_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/options_chain/tests/test_sealed_get_expirations.py` | **SEALED** | Returns sorted DDMMYYYY list of active expiries for BTC/ETH. Filters past + 5:30PM IST expired. Mocked tests only. |
| 2 | `get_chain_data` | `webui/backend/options_chain/chain_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/options_chain/tests/test_sealed_get_chain_data.py` | **SEALED** | Returns full options chain dict with spot_price, atm_strike, chain list, summary counts for BTC/ETH + expiry. Mocked tests only. |
| 3 | `_calculate_rsi` | `bot/guardian/collectors/rsi_collector.py` | v1.0.0 | Mar 4, 2026 | `bot/guardian/collectors/tests/test_sealed_calculate_rsi.py` | **SEALED** | Pure Wilder's smoothing RSI. Input: list of close prices + period. Output: float 0-100 or None. No external calls — pure math. |
| 4 | `create_group` | `webui/backend/routes/options/groups_storage.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_create_group.py` | **SEALED** | Creates a named position group in SQLite. Returns dict with name/color/note/symbols. Adds group_id to group_order in metadata. |
| 5 | `get_expiry` | `webui/backend/routes/options/groups_storage.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_get_expiry.py` | **SEALED** | Returns full group data (groups, collapsed, order, groupOrder) for one expiry key. Returns empty structure for unknown keys. |
| 6 | `get_all` | `webui/backend/routes/options/groups_storage.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_get_all.py` | **SEALED** | Returns all group data across all expiry keys. Empty dict when DB is empty. Keys isolated from each other. |
| 7 | `delete_group` | `webui/backend/routes/options/groups_storage.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_delete_group.py` | **SEALED** | Removes a group from DB and strips its ID from group_order in metadata. Silently no-ops on missing group. |
| 8 | `update_group` | `webui/backend/routes/options/groups_storage.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_update_group.py` | **SEALED** | Updates allowed fields (name/color/note/symbols) on a group. Ignores unknown fields. Empty updates dict is a no-op. |
| 9 | `assign_symbol` | `webui/backend/routes/options/groups_storage.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_assign_symbol.py` | **SEALED** | Moves a symbol to a target group — removes from all current groups first. target_group_id=None unassigns. Scoped to one expiry key. |
| 10 | `get_contract_multiplier` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_get_contract_multiplier.py` | **SEALED** | Returns Delta Exchange contract multiplier (BTC/ETH = 0.001). Defaults to 0.001 for unknown assets. Never crashes on empty string. |
| 11 | `determine_close_side` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_determine_close_side.py` | **SEALED** | Returns 'sell' for long (positive size), 'buy' for short or zero. Controls close-order direction. |
| 12 | `calculate_unrealized_pnl` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_calculate_unrealized_pnl.py` | **SEALED** | (mid − entry) × size × multiplier. Short profits when price drops. Handles string values from API. |
| 13 | `calculate_pnl_percentage` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_calculate_pnl_percentage.py` | **SEALED** | PnL% using mid price. Short positions: sign inverted so profit shows as positive. Zero entry returns 0.0. |
| 14 | `check_expiry_warning` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_check_expiry_warning.py` | **SEALED** | Returns warning level: expired / critical (<1hr) / warning (<24hr) / normal. Never crashes on bad timestamp. |
| 15 | `check_liquidity` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_check_liquidity.py` | **SEALED** | Returns is_liquid=True when spread_pct < 10%. Zero mark price → illiquid. Never throws. |
| 16 | `enrich_position_data` | `bot/options/utils/options_helper.py` | v1.0.0 | Mar 4, 2026 | `bot/options/utils/tests/test_sealed_enrich_position_data.py` | **SEALED** | Enriches API position with mid_price, unrealized_pnl, cashflow, pnl_percentage, return_on_cashflow, greeks, expiry_warning. |
| 17 | `calculate_portfolio_greeks` | `webui/backend/routes/options/dashboard.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_calculate_portfolio_greeks.py` | **SEALED** | Aggregates delta/gamma/theta/vega across all positions. Delta signed, gamma always positive. Splits btcDelta/ethDelta. |
| 18 | `probability_of_profit` | `webui/backend/options_strategy/probability_analyzer.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/options_strategy/tests/test_sealed_probability_of_profit.py` | **SEALED** | Lognormal PoP for options strategies. At time=0: pop=1 if profitable, pop=0 if not. Returns pop/expected_value/VaR/CVaR. |
| 19 | `execute_single_order` | `webui/backend/routes/options/batch_add_endpoint.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_execute_single_order.py` | **SEALED** | Executes a single order from a batch. Always returns dict with success key. On error: preserves symbol/side/index/error. On success: includes execution_type, fill_price, order_id. |
| 20 | `place_smart_order` | `webui/backend/routes/options/options_control.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_place_smart_order.py` | **SEALED** | Smart order routing: market_only → immediate fill, maker_first → mid-price post-only. size=int(abs(float(size))). Returns dict with execution_type. |
| 21 | `start_loop` | `webui/backend/services/auto_loop_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/services/tests/test_sealed_auto_loop_start_loop.py` | **SEALED** | Starts a new auto-loop. Returns state dict with status='running', current_round=0, stop_requested=False. Raises ValueError if loop already running with live thread. |
| 22 | `stop_loop` | `webui/backend/services/auto_loop_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/services/tests/test_sealed_auto_loop_stop_loop.py` | **SEALED** | Signals a running loop to stop. Returns True on success, False if loop not found or not running. Sets stop_requested=True and status='stopping'. |
| 23 | `get_status` | `webui/backend/services/auto_loop_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/services/tests/test_sealed_auto_loop_get_status.py` | **SEALED** | Returns state dict for known loop_id; {exists: False} for unknown; all loops dict when no loop_id given. |
| 24 | `clear_finished` | `webui/backend/services/auto_loop_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/services/tests/test_sealed_auto_loop_clear_finished.py` | **SEALED** | Removes loops with status completed/stopped/error. Keeps running/stopping. Returns count of removed loops. |
| 25 | `get_pending_orders` | `webui/backend/routes/positions.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/tests/test_sealed_get_pending_orders.py` | **SEALED** | Fetches all open orders from Delta Exchange. Returns {success, orders, count}. None limit_price → 0.0. 503 on circuit open, 500 on exception. |
| 26 | `fetch_pending_orders_data` | `webui/backend/routes/options/dashboard_service.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_fetch_pending_orders_data.py` | **SEALED** | Service wrapper for pending orders. Always returns dict. On exception: {success: False, orders: [], error: str}. Never raises. |
| 27 | `cancel_order_with_verification` | `webui/backend/routes/options/options_control.py` | v1.0.0 | Mar 4, 2026 | `webui/backend/routes/options/tests/test_sealed_cancel_order_with_verification.py` | **SEALED** | Cancels order with retry+verify. filled→safe=False, cancelled→safe=True, all-retries-fail→state=unknown safe=False. |
| 28 | `get_spot_price` | `webui/backend/routes/market.py` | v1.0.0 | Mar 2026 | `webui/backend/routes/tests/test_sealed_get_spot_price.py` | **SEALED** | BTC/ETH SPOT price endpoint. Returns {symbol, price, source}. Fallback: WS->cache->Delta API->guardian->hardcoded. Invalid symbol->400. Never raises. |
| 29 | `update_yaml_config` | `webui/backend/utils/yaml_config.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/utils/tests/test_sealed_update_yaml_config.py` | **SEALED** | Persists grid parameters (reference, step, lower/upper bounds) to config.yaml using dot-notation paths. Returns True on success, False on failure. Never raises. Creates missing parent keys. |
| 30 | `compute_next_buy_level` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | LONG mode core: computes next BUY price. No positions→ref−step (or nearest below market if below ref). With positions→lowest_entry−step. Returns None if out of bounds. Quantized to tick. |
| 31 | `compute_tp_price` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | LONG mode TP = entry + step. Always returns entry_price + self.step. Never None, never negative step. |
| 32 | `is_within_bounds` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns True if lower ≤ price ≤ upper. Accepts optional custom lower/upper override. Safety gate for all order placement. |
| 33 | `quantize_price` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Floors price to exact tick_size multiple using Decimal for precision. Idempotent. Raises ValueError on NaN/Infinity. |
| 34 | `get_grid_levels` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns sorted list of all grid levels from lower to upper, all quantized and within bounds, spaced exactly by step. |
| 35 | `is_price_grid_aligned` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns True if price is on a grid step boundary (within tolerance 0.01). Used for off-grid detection and emergency correction. |
| 36 | `find_nearest_grid_level` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns nearest grid level (rounded, not floored) to given price. Uses Python banker's rounding. Result is quantized. |
| 37 | `find_nearest_grid_below` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns highest grid level strictly below price. Returns None if price is at or below lower bound. LONG strict-grid MAKER placement. |
| 38 | `get_startup_maker_buy_level` | `bot/strategy/modules/grid_calculator.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | LONG startup: if calculated buy level is above market, finds nearest level below market (MAKER). If already below market, returns as-is. |
| 39 | `is_cooldown_ready` | `bot/strategy/modules/grid_engine.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns True if cooldown elapsed or cooldown≤0. Returns False with debug log if still in cooldown. Never raises. |
| 40 | `is_fill_seen` | `bot/strategy/modules/fill_processor.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Fill deduplication check. Returns True if fill_id already in seen set. Pure O(1) set lookup. |
| 41 | `mark_fill_seen` | `bot/strategy/modules/fill_processor.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Adds fill_id to dedup set with timestamp. Idempotent. Paired with is_fill_seen — never skip a fill, never process twice. |
| 42 | `calculate_next_grid_level` | `bot/strategy/modules/fill_processor.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Returns next BUY level below current price (LONG) or SELL level above (SHORT), skipping recovered grids. Returns None if out of bounds. Never raises. |
| 43 | `get_current_mode` | `bot/strategy/modules/mode_state_manager.py` | v1.0.0 | Mar 5, 2026 | `bot/strategy/modules/tests/test_sealed_gridbot_long_mode.py` | **SEALED** | Reads mode from config.yaml and returns uppercase string ('LONG'/'SHORT'). Never returns None for valid config. |
| 44 | `getOpenPositions` | `webui/frontend/src/components/optionsChain/services/chainAPI.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/optionsChain/services/__tests__/test_sealed_getOpenPositions.test.js` | **SEALED** | Fetches live options positions → symbol lookup map. Red=short(sold), Green=long(bought), absent=no trade. Keys always UPPERCASE, side always lowercase. Returns {} on any error, never throws. **Jest test** — run: `cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_getOpenPositions` |
| 45 | `getContractMultiplier` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | BTC=0.001, ETH=0.01. Validates symbol parsing. Part of 12-function Payoff Graph batch seal. |
| 46 | `normalCDF` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Abramowitz & Stegun 5-term approximation (~1e-7 accuracy). Pure math. |
| 47 | `normalPDF` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Standard normal density function. Pure math. |
| 48 | `blackScholesPrice` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | BS model with crypto standard r=0. Handles T<=0 intrinsic value safely. |
| 49 | `calculateImpliedVolatility` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Newton-Raphson solver with bisection fallback. Returns 0.8 on error edge cases. |
| 50 | `calculatePortfolioDelta` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Extracted from UI logic. Aggregates delta for open positions. |
| 51 | `calculatePortfolioTheta` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Aggregates daily theta decay in USD terms. |
| 52 | `calculatePortfolioGamma` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Aggregates portfolio gamma. |
| 53 | `calculateProbabilityOfProfit` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Integrates expiry payoff against lognormal density to compute PoP 0-100%. |
| 54 | `createPriceDistribution` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Curried function returning P(price) lognormal density for chart overlays. |
| 55 | `calculateWeightedIV` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Notional-weighted portfolio IV. Fallback 0.8. |
| 56 | `formatDate` | `webui/frontend/src/components/options/payoffCalculator.js` | v1.0.0 | Mar 5, 2026 | `webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js` | **SEALED** | Custom formatting string builder. |
| 57 | `AlertsDB.create_alert` | `webui/backend/db/alerts_db.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/services/tests/test_sealed_price_alerts.py` | **SEALED** | Creates a price alert row in SQLite. Returns full dict. Default status=active, symbol=BTCUSD. ID is 8-char UUID fragment. |
| 58 | `AlertsDB.get_all_alerts` | `webui/backend/db/alerts_db.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/services/tests/test_sealed_price_alerts.py` | **SEALED** | Returns list of alert dicts. Optional filters: status and/or expiry_date. Empty DB → []. All results are dicts. |
| 59 | `AlertsDB.delete_alert` | `webui/backend/db/alerts_db.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/services/tests/test_sealed_price_alerts.py` | **SEALED** | Deletes alert by ID. Returns True if deleted, False if not found. Silently no-ops missing IDs. |
| 60 | `AlertsDB.trigger_alert` | `webui/backend/db/alerts_db.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/services/tests/test_sealed_price_alerts.py` | **SEALED** | One-time alerts → status=triggered. Repeating alerts → stay active, increment trigger_count. Returns None for missing ID. |
| 61 | `PriceAlertMonitor._is_in_cooldown` | `webui/backend/services/price_alert_monitor.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/services/tests/test_sealed_price_alerts.py` | **SEALED** | Returns True if alert is within cooldown window. No last_triggered_at → False. Bad timestamp → False (never raises). |
| 62 | `PriceAlertMonitor._format_alert_message` | `webui/backend/services/price_alert_monitor.py` | v1.0.0 | Mar 5, 2026 | `webui/backend/services/tests/test_sealed_price_alerts.py` | **SEALED** | Builds human-readable alert notification string. Includes price, direction, expiry, P&L, note when present. Never raises. |

---

## UNSEAL HISTORY LOG
> Every time a sealed function is modified, log it here permanently.

| Date | Function Name | Reason | Old Version | New Version | Re-sealed On |
|---|---|---|---|---|---|
| — | *no unseal events yet* | — | — | — | — |


---

## QUICK STATS

- Total Sealed : 62
- Total Unsealed (ever modified) : 0
- Last Activity : Mar 5, 2026 — Price Alerts sealed (6 functions: create_alert, get_all_alerts, delete_alert, trigger_alert, _is_in_cooldown, _format_alert_message)

> ⚠️ Entry #44 uses **Jest** (not pytest). Run its test separately:
> `cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_getOpenPositions`

> ⚠️ Entries #45-56 use **Jest** (not pytest). Run their tests separately:
> `cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_payoffCalculator`

---

## FOR THE AI — INSTRUCTIONS ON THIS FILE

- **On every new seal:** Add one row to the Sealed Functions Registry table. Set Status = SEALED.
- **On UNSEAL command:** Change Status to UNSEALED, add a row to Unseal History Log, then after re-sealing set Status back to SEALED with new version.
- **On Status command:** Read this file and report the full registry to user in clean format.
- **Never delete rows.** Only update Status column. History must be permanent.
- **Update "Last Activity" and "Total Sealed" in Quick Stats after every operation.**
