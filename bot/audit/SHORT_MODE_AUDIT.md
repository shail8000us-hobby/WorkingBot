# Grid Bot SHORT Mode - Pre-Launch Audit Report

## Final Decision: NOT SAFE FOR DEPLOYMENT 🔴

While the core math, order execution, and PnL accounting for SHORT mode are perfectly symmetric and robust, a CRITICAL gap in the Guardian safety handler prevents the safe recovery of missed SHORT orders during market turbulence. 

Because Guardian handles extreme market volatility (which is naturally more dangerous for SHORT positions where risk is theoretically infinite), the broken recovery logic makes SHORT mode unsafe for live money until remediated.

### Audit Summary

- **Phase 1-2 (Architecture & Logic):** ✅ PASS. The multi-instance architecture (`Symbol + Mode`) properly isolates state to its own database. `GridCalculator` perfectly inverts the math `(compute_next_sell_level)` to correctly stack levels above the current price.
- **Phase 3 (Order Execution):** ✅ PASS. `FillProcessor` handles SELL entries and BUY Take-Profits accurately, utilizing distinct deterministic Sagas (`create_short_entry_saga`, `create_short_tp_saga`) to ensure atomic transaction safety and "Single Writer" adherence.
- **Phase 4-5 (State & Risk):** ✅ PASS. `PositionManagerActor` tracks open tranches symmetrically via length limits. `RiskDecisionEngine` evaluates safety by pulling native PnL (`unrealized_pnl` via Delta API), which inherently formats SHORT MTM correctly.
- **Phase 6 (PnL Accounting):** ✅ PASS. Delta manages SHORT PnL natively. The local FIFO PnL script accurately processes sequences of SELL -> BUY matching logic without errors.
- **Phase 8 (Config Validation):** ✅ PASS. `config.yaml` explicitly separates limits (`lot_size` vs `short_lot_size`) and restricts SHORT mode independently. Mode-aware RSI thresholds (`long_threshold`, `short_threshold`) are active.

### Critical Findings (Why it is NOT SAFE)

**1. Guardian Missed Order Recovery Skips SHORT Entries (High/Critical)**
- **Location:** `bot/strategy/modules/guardian_handler.py` -> `retry_missed_orders()`
- **Issue:** When Guardian halts trading via `STOP` and then resumes (`GO`), it traverses the `_missed_grid_orders` queue to gracefully repopulate the unfulfilled grid. However, the exact code hardcodes skipping SELL retries:
  ```python
  elif side == "sell":
      log.warning("   ⚠️  Skipping SELL - SELL retry not implemented")
      skipped += 1
  ```
- **Risk:** If Guardian halts during an upward spike (which triggers high IV or RSI breaches), the SHORT bot will miss placing its crucial upper grid entry limits. When it resumes via GO, these grid levels remain permanently unfilled, leaving enormous gaps in the grid structure.

**2. A3 Multi-Step Gap Detection Harcoded to LONG Only (High/Critical)**
- **Location:** `bot/strategy/modules/guardian_handler.py` -> `fill_multi_step_missed_grids()`
- **Issue:** The A3 safety mechanism detects if the market gapped >2 grid steps during a Guardian STOP phase, automatically back-filling the swept levels to stay anchored. This method explicitly short-circuits for SHORT mode:
  ```python
  # Only for LONG mode currently (SHORT would mirror with SELL levels)
  if self.mode != "LONG":
      return
  ```
- **Risk:** Rapid upward market rips (the deadliest scenario for a SHORT bot) will completely bypass the A3 catch-up logic. The grid will fail to follow the market structure aggressively, risking stagnation if the price does not fully retrace.

### Remediation Plan

Before enabling SHORT mode with live capital, apply the following minimal fixes:

1. **Implement `SELL` loop inside `GuardianHandler.retry_missed_orders()`:**
   - Instead of logging "SELL retry not implemented", mirror the logic from the `side == "buy"` block. Validate against `pending_sell`, verify `is_within_bounds`, call `PLACE_SELL`, and update `SET_PENDING_SELL`.
2. **Remove the `self.mode != "LONG"` block in `fill_multi_step_missed_grids()`:**
   - Branch the logic. For SHORT mode, compare `current_price` against `highest_entry` instead of `lowest_entry`.
   - Calculate missing steps upwards `highest_entry + (i * self.grid_step)`.
   - Assert `level <= current_price`, ensuring the skipped limits are beneath the immediate market action.
   - Fire `PLACE_SELL` and `SET_PENDING_SELL` loops precisely. 

Once these 2 GuardianHandler omissions are fixed, SHORT mode will be structurally and mathematically safe for production.
