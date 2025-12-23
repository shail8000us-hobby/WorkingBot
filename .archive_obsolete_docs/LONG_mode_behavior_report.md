# GridBot Long Mode Behavior Report

## Configuration Context
- Source: `grid_config.env`
- Mode: `GRIDBOT_GRID_MODE=LONG`
- Symbol: `GRIDBOT_SYMBOL=BTCUSD`
- Lot Size: `GRIDBOT_LOT=1`
- Position Cap: `GRIDBOT_MAX_OPEN=5`
- Grid Bounds: `GRIDBOT_LOWER=99,000`, `GRIDBOT_UPPER=110,000`
- Grid Step: `GRIDBOT_STEP=500`
- Reference Level: `GRIDBOT_REF=103,800`
- Tick Size: `GRIDBOT_TICK_SIZE=0.5`
- Strict grid enforcement and snap mode `"below"` ensure all prices remain aligned with the configured ladder.

## Key Modules Involved
- `bot/strategy/gridbot.py`: Orchestrator wiring price updates, fills, volatility checks, and handlers.
- `bot/strategy/modules/grid_calculator.py`: Computes grid-aligned prices (next buy level, TP, bounds).
- `bot/strategy/modules/position_manager.py`: Tracks open positions, pending orders, and capacity with a shared state lock.
- `bot/strategy/modules/order_manager.py`: Places BUY/TP orders, enforces grid alignment, maker-only checks, monitoring stack approval, aggressive REST polling, and cancellation logic.
- `bot/strategy/modules/fill_detector.py`: Queues fills sequentially, deduplicates, and triggers handler callbacks under lock.
- `bot/strategy/modules/volatility_handler.py`: Cancels pending orders on halts and restores the grid after volatility recovers.
- `bot/strategy/handlers/long_handler.py`: Processes BUY fills and TP fills for LONG mode, manages next-order placement and TP/cancellation steps.

## Market Moves Down – BUY Flow
1. **Price Update**  
   - `GridBot._on_price_update` records `current_price`, runs price-health checks, and invokes `VolatilityHandler.check_pending_order_safety` each tick.  
   - If a volatility halt clears in LONG mode and no pending order exists, it recomputes `compute_next_buy_level` and posts the maker BUY via `OrderManager.place_buy_order`, provided `PositionManager.try_reserve_capacity` succeeds and the price is within bounds.

2. **Fill Detection**  
   - WebSocket or aggressive REST polling detects the BUY fill.  
   - `FillDetector` normalizes and enqueues the event; the worker calls `GridBot._on_fill_processed` under the position lock.  
   - The pending BUY order ID matches, so control is delegated to `LongFillHandler.handle_buy_fill`.

3. **Position & TP Creation**  
   - `handle_buy_fill` creates a position for the incremental fill slice, storing it through `PositionManager.add_position` (enforces grid alignment and persistence).  
   - Computes TP one grid step above (`GridCalculator.compute_tp_price`) and calls `OrderManager.place_tp_mandatory`, which retries until a reduce-only SELL TP posts, handling collision avoidance and starting REST polling on the TP order.

4. **Next Grid Placement**  
   - When the original order is fully filled (`is_complete=True`), the handler clears `pending_buy`, calculates the next level down (`GridCalculator.compute_next_level_down`), verifies bounds, and respects the global 30 s BUY throttle.  
   - If throttled, a delayed thread schedules the order once the gap expires; otherwise `_place_next_grid_order` calls `OrderManager.place_buy_order(post_only=True)` and immediately registers the new `pending_buy`.

## Market Moves Up – TP Flow
1. **TP Fill Routing**  
   - TP fills arrive via the same detection pipeline. `GridBot._on_fill_processed` recognises the `tp_id` and calls `LongFillHandler.handle_tp_fill`.

2. **Position Removal & Stale Order Cleanup**  
   - The handler removes the closed position (`PositionManager.remove_position`).  
   - If a resting BUY two steps below the TP price exists, it cancels it through `OrderManager.cancel_order(verify=True)` and clears `pending_buy`, logging any distance mismatches versus the expected 2-step offset.

3. **Re-entry Placement**  
   - After reserving capacity, it computes the next level down from the TP price, confirming bounds.  
   - `_check_order_throttle('BUY')` blocks placement if the 30 s gap has not elapsed.  
   - Volatility is checked via `vol_tracker.can_trade()`. On “safe”, it places the BUY (maker, post-only) and registers it; on “unsafe”, it logs and releases capacity without submitting. Any exceptions during the check fall back to placing the order regardless to keep the grid intact.

4. **Monitoring & Polling**  
   - Every order placement runs through `OrderManager.place_buy_order`: price quantization, duplicate prevention, strict grid enforcement, price-monitor freshness, pre-order decision logging, and anomaly tracking.  
   - Successful orders trigger aggressive REST polling (`_start_order_polling`) to ensure fills are processed even if WebSocket updates are missed.

## Additional Safeguards
- `PositionManager` guarantees exclusive state access via `state_lock`, immediate persistence on changes, and capacity accounting (`try_reserve_capacity` / `release_capacity`).  
- `VolatilityHandler.trigger_volatility_halt` cancels pending BUYs using bulk cancellation and records halt state; `execute_opportunistic_recovery` restores missed grid levels once trading resumes.  
- The monitoring stack (price health, pre-order logger, TP verification, anomaly detector) must be active, otherwise BUY placement is rejected for safety.

---

Premium requests remaining: _not provided_ (please share if you’d like this tracked explicitly).


