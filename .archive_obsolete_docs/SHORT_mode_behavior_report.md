# GridBot Short Mode Behavior Report

## Configuration Context
- Source: `grid_config.env`
- Mode flag: `GRIDBOT_GRID_MODE` (set to `LONG` in the file; switching to `SHORT` activates the behavior described here without altering any other parameters)
- Symbol: `GRIDBOT_SYMBOL=BTCUSD`
- Lot size: `GRIDBOT_LOT=1`
- Position cap: `GRIDBOT_MAX_OPEN=5`
- Grid bounds: `GRIDBOT_LOWER=99,000`, `GRIDBOT_UPPER=110,000`
- Grid step: `GRIDBOT_STEP=500`
- Reference level: `GRIDBOT_REF=103,800`
- Tick size: `GRIDBOT_TICK_SIZE=0.5`
- Enforcement: `GRIDBOT_STRICT_GRID=1`, `GRIDBOT_RUNG_SNAP_MODE=below`, ensuring all prices remain aligned to the configured ladder when the bot operates in SHORT mode.

## Key Modules Involved
- `bot/strategy/gridbot.py`: main orchestrator; routes price updates, fill events, volatility checks, and throttling logic, switching between LONG and SHORT branches by `self.grid_mode`.
- `bot/strategy/modules/grid_calculator.py` (`GridCalculator`):
  - `compute_next_sell_level`, `compute_next_level_up` for SHORT entries.
  - `compute_tp_price_short` for BUY-back TP targets.
  - `is_within_bounds`, `quantize_price`, `is_price_grid_aligned` guard ladder integrity.
- `bot/strategy/modules/position_manager.py` (`PositionManager`):
  - Maintains `open_tranches`, `pending_sell`, capacity counters protected by `state_lock`.
  - Provides `set_pending_sell`, `clear_pending_sell`, `try_reserve_capacity`, `release_capacity`, `schedule_tp_retry`, immediate persistence.
- `bot/strategy/modules/order_manager.py` (`OrderManager`):
  - `place_sell_order` for maker SHORT entries with grid alignment, price-monitor validation, duplicate prevention, and aggressive REST polling.
  - `safe_place_tp` / `place_tp_mandatory` (called with `side='short'` positions) to post BUY reduce-only TP orders.
  - Cancellation helpers (`cancel_order`, `cancel_all_orders_bulk`, verification routines).
- `bot/strategy/modules/fill_detector.py` (`FillDetector`): queues fills sequentially, deduplicates, and triggers feed-backed callbacks under the position lock; logs outcomes in `FillAuditLog`.
- `bot/strategy/modules/volatility_handler.py` (`VolatilityHandler`):
  - `check_pending_order_safety` halts/resumes trading, canceling `pending_sell` orders when volatility is unsafe and executing recovery once safe.
  - `trigger_volatility_halt`, `execute_opportunistic_recovery`, `calculate_missed_levels`, `validate_recovery_feasibility`.
- `bot/strategy/handlers/short_handler.py` (`ShortFillHandler`):
  - `handle_sell_fill` processes SELL fills (SHORT entries) with partial-fill support, TP placement, throttle gating, and next-grid SELL scheduling.
  - `handle_tp_fill_short` processes BUY TP fills, removes positions, cancels stale SELLs, and places the new one-step-up SELL.

## Market Moves Up – SELL Flow (SHORT Entry Sequence)
1. **Price Update & Volatility Gate**  
   - `GridBot._on_price_update` records `current_price`, updates the `PriceHealthMonitor`, and calls `VolatilityHandler.check_pending_order_safety` on every tick.  
   - When volatility recovers and `self.grid_mode == 'SHORT'`, the branch at lines 735–752 (in the same method) fetches `pending_order = self.position_mgr.get_pending_sell()`.  
   - If no pending order exists and `try_reserve_capacity()` succeeds, it requests the next SELL ladder level via `GridCalculator.compute_next_sell_level`, verifies bounds with `is_within_bounds`, and submits the maker SELL through `OrderManager.place_sell_order`. Successful placement registers the order via `PositionManager.set_pending_sell` and timestamps `self.bot.last_sell_order_time`.

2. **Fill Detection & Routing**  
   - SELL fills arrive either from WebSocket or `_start_order_polling`; all feeds pass through `FillDetector`, which serializes events and invokes `GridBot._on_fill_processed` while holding `PositionManager.state_lock`.  
   - Inside `_on_fill_processed`, a fill whose `order_id` matches `pending_sell` is delegated to `ShortFillHandler.handle_sell_fill`.

3. **Position Creation & TP Posting (`ShortFillHandler.handle_sell_fill`)**  
   - Constructs a SHORT position record (with `'side': 'short'`) for the incremental fill and persists it via `PositionManager.add_position` (grid alignment enforced, state saved).  
   - Computes the BUY-back TP using `GridCalculator.compute_tp_price_short` and attempts to post it through `OrderManager.safe_place_tp`.  
   - On success: marks `position['protected'] = True`, runs `tp_verifier.verify_tp_placement`, and tracks the TP in the anomaly detector.  
   - On failure: schedules retries with `PositionManager.schedule_tp_retry`, logs a critical alert, and notifies via `TelegramNotifier`.

4. **Next GRID SELL Placement**  
   - When the SELL order finishes filling (`is_complete=True`), the handler checks the SELL throttle before clearing `pending_sell`.  
   - If the last SELL was within `self.bot.min_order_gap_seconds`, it exits early (without clearing) to let reconciliation retry later.  
   - Otherwise, it clears `pending_sell`, reserves capacity, computes the next ladder level above the fill (`GridCalculator.compute_next_level_up`), checks bounds, re-tests the throttle, and evaluates volatility (`vol_tracker.can_trade()`).  
   - If trading is permitted, it posts the SELL via `OrderManager.place_sell_order` and immediately records the order in `PositionManager.set_pending_sell`, updating `last_sell_order_time`.  
   - Unsafe volatility or errors log warnings; a fallback path still attempts order placement while preserving capacity accounting.

## Market Moves Down – TP Flow (SHORT Exit Sequence)
1. **TP Fill Detection**  
   - BUY TP fills propagate through `FillDetector` into `GridBot._on_fill_processed`, which recognises a TP via `position_mgr.find_position_by_order_id(order_id)` and the stored `tp_id`.  
   - For SHORT positions (`position.get('side') == 'short'`), control routes to `ShortFillHandler.handle_tp_fill_short`.

2. **Position Removal & Stale SELL Cancellation**  
   - `handle_tp_fill_short` computes realized profit `(entry - fill_price) * size` and removes the position via `PositionManager.remove_position`.  
  - If a `pending_sell` remains, it expects that SELL to sit two grid steps above the TP price; it logs the distance, cancels the order using `OrderManager.cancel_order(verify=True)`, and clears `pending_sell`.

3. **Re-entry SELL Placement**  
   - With capacity reserved (`try_reserve_capacity()`), the handler calculates the next SELL level one step above the TP (`GridCalculator.compute_next_level_up`), ensures the price falls within the configured bounds, and checks the SELL throttle with `_check_order_throttle('SELL')`.  
   - Upon passing the throttle, it assesses volatility through `get_volatility_tracker().can_trade()`. Safe conditions trigger `OrderManager.place_sell_order`, with the resulting order registered immediately in `PositionManager.set_pending_sell` and a fresh `last_sell_order_time`.  
   - Unsafe volatility merely logs the block and releases capacity; exceptions fall back to placing the SELL regardless, keeping state tracking consistent.  
   - `PositionManager.release_capacity()` concludes the sequence once placement (or a blocking condition) is resolved.

## Additional Safeguards
- **State Concurrency**  
  - `PositionManager.state_lock` serializes all access to open positions and pending orders; `GridBot._on_fill_processed` acquires the lock before delegating to handlers.  
  - `FillDetector` processes fills sequentially via a single worker thread (`_process_fill_queue`), preventing race conditions and integrating `FillAuditLog` for permanent tracing.
- **Capacity Controls**  
  - `PositionManager.try_reserve_capacity` counts open, pending, and reserved slots before allowing new orders; `release_capacity` ensures reservations are cleared on failure/placement.
- **Throttle Enforcement**  
  - `ShortFillHandler._check_order_throttle` and in-line SELL checks enforce the global `self.bot.min_order_gap_seconds` spacing, blocking or delaying duplicate placements.  
  - `GridBot` maintains `last_sell_order_time` to coordinate throttling across modules.
- **Volatility Management**  
  - `VolatilityHandler.check_pending_order_safety` cancels existing `pending_sell` orders if `vol_tracker.can_trade()` returns false, invoking `trigger_volatility_halt` and using bulk cancel APIs plus verification.  
  - Recovery logic (`execute_opportunistic_recovery`) replays missed ladder levels with respect to capacity and configured limits once conditions normalize.
- **Order Placement Safety**  
  - `OrderManager.place_sell_order` validates grid alignment, enforces maker pricing (SELL must be above market), runs the monitoring stack (price freshness, decision logging, anomaly detection), and rejects placements if prerequisites fail.  
  - Aggressive REST polling (`_start_order_polling`) ensures fills are captured even if WebSocket updates lag, feeding back into `FillDetector`.
- **Error Handling & Alerts**  
  - TP placement failures queue retries (`schedule_tp_retry`) and send Telegram alerts; cancellation routines verify exchange state to avoid stale orders.  
  - Unknown fills in `_on_fill_processed` trigger critical reconciliation (`reconciler.reconcile_positions_with_exchange`) and Telegram notifications.

---

Premium requests remaining: _not provided_ (please share if you’d like this tracked explicitly).


