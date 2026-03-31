# MMM Algorithm Safety Audit Report

## Core Question: Is the MMM algo being protected OR being choked?
**Conclusion**: The MMM algorithm is heavily "choked", specifically due to overlapping safety domains, redundant protections against the same risks, and sequential locking mechanisms that paralyze the adjustment engine when it most needs to reposition. While individual safety limits are sound, their *interaction* causes gridlock.

---

## 1. Safety Layer Mapping & Execution Flow

### Execution Sequence (`_heartbeat_inner`)
1. **Pre-Beat / Environmental Filters**:
   - Circuit Breaker Checks
   - Pending Orders Reconciliation (Fill sync)
   - Margin Guardian Check (assigns Green/Yellow/Orange/Red tiers)
2. **Price Fetching**:
   - `_fetch_premiums_with_fallback`
   - *Miss-Beat Guard*: If fetch fails, still runs `_process_close_at_5()` AND `run_all_checks()` using stale cached prices.
3. **Safety Engine (`self._safety.run_all_checks`)**:
   - Calculates Position Cap, Total Exposure, Max Adjustments, Max Loss, Whipsaw (Adaptive), Asymmetry, Near-Expiry, PNL Guardrail, Trailing Stop, Margin checks, Lot Velocity.
4. **Regime Controls (`_regime_engine`)**:
   - Calculates Volatility Regime, Gamma Cap, Trend Guard.
   - Translates to `ACTION_NORMAL`, `ACTION_PAUSE`, `ACTION_BLOCK_ALL_SELLS`, or `ACTION_FORCE_REDUCE`.
5. **Trigger Evaluation** (Skipped if `_skip_to_pnl` is True from Safety/Regime blocks):
   - Percentage-based threshold evaluation.
6. **Adjustment Engine (`_process_adjustment`)**:
   - Executes the required hedge. Contains internal blocks: ITM Guard, Pending Order Guard, Consec-Direction Cap, Reversal Cooldown.

---

## 2. Identified Over-Constraint Patterns (Redundancy & Conflict)

### A. The `_skip_to_pnl` Gridlock (Conflict)
When central safety checks (like **Position Cap** or **Trailing Stop**) return `stop_adjustments`, `_heartbeat_inner` sets `_skip_to_pnl = True`. This completely bypasses **Trigger Evaluation**. 
- **The Choke:** By bypassing trigger evaluation, the system is prevented from executing risk-reducing actions (liking closing frozen positions, or selling the *legitimate* light-side to fix asymmetry). 
- *Example:* If CE hits the position cap, `stop_adjustments` is fired. PE drops and *needs* to be sold to rebalance the delta. Because `_skip_to_pnl = True` is active, the PE sell trigger is never evaluated.

### B. ATM Protection Overlap (Redundancy)
There are FOUR mechanisms attempting to manage the exact same risk (Spot price approaching the strike zone):
1. **Close at ATM (`close_at_atm`)**: Emergency closes all positions if spot is within 0.5% of Active Strike.
2. **ATM Wind Down (`wind_down_on_atm`)**: Activates slow LIFO buyback if spot is within 0.5% of Active Strike.
3. **ATM Shield**: Deferral logic tries to preemptively shift strikes out of the way before the 0.5% threshold.
4. **Proactive Shift Scanner**: Tries to step the active strike back before it becomes ATM.
- **The Choke:** If the ATM Shield is active but fails an internal gate (e.g. margin tier or Gamma block), it passes control back. The rigid `close_at_atm` will immediately override the gentle `wind_down_on_atm` and force-close the entire strategy instantly on a transient wick, completely ignoring the designed wind-down logic.

### C. The Triple-Cooldown Thrashing Guard (Redundancy)
The system punishes the algorithm for "thrashing" three different times:
1. **Adaptive Whipsaw Guard (`mmm_safety.py`)**: Adds points for alternating adjustments within a time window. Reduces lot sizes by 50% or enforces a hard cooldown.
2. **Reversal Cooldown Guard (`_process_adjustment`)**: Enforces a strict time-based block immediately after ANY reversal.
3. **Consecutive Direction Limiter (`_process_adjustment`)**: Blocks after 5 same-direction adjustments.
- **The Choke:** The algorithm gets hit by the Whipsaw penalization (halving its lots), but then *also* gets blocked from acting on the next heartbeat by the Reversal Cooldown, rendering the engine unresponsive during high-volatility sideways chops where fast, small-lot adjustments are the exact intended behavior.

### D. The "Miss-Beat" Stale Price Danger (Critical Conflict)
On a "Miss Beat" (when exchange API fails to fetch prices), the system drops into a fallback block where it intentionally calculates `run_all_checks()` using **STALE cached prices** to ensure `auto_close` and `stop` mechanisms stay alive.
- **The Choke:** By running `check_max_loss` and `check_trailing_stop` on stale cached prices, a temporary UI unresponsiveness or exchange API hiccup can trigger a catastrophic `auto_close_all` at a ghost price level that no longer reflects reality.

### E. Margin Guardian vs Trigger Priority (Conflict)
The **Margin Guardian** sets `_margin_block_sells = True` at the YELLOW tier and `_margin_wind_down = True` at the ORANGE tier.
- **The Choke:** This logic is clean, but because it relies on the Adjustment Engine (`_process_adjustment`) to actually execute the wind-down buybacks, it is heavily dependent on Triggers actually firing. If Regime Controls block sells (`ACTION_BLOCK_ALL_SELLS`), or Position Cap blocks adjustments, the ORANGE tier wind-down cannot execute because the trigger loop was bypassed. 

---

## 3. Recommended Improvement Plan

### Phase 1: Untangle the `_skip_to_pnl` Gridlock
1. **Refactor `stop_adjustments`:** Instead of skipping trigger evaluation entirely (`_skip_to_pnl = True`), allow Triggers to evaluate but pass a highly restrictive "Safety State" object to `_process_adjustment`. 
2. **Targeted Blocks:** If Position Cap is hit on CE, only block CE sells. Let PE sells execute to naturally rebalance the ledger. The system already does exactly this for Asymmetry (`block_heavy_side_sells`), but fails to extend this targeted logic to Exposure/Cap checks.

### Phase 2: Consolidate Thrashing Defenses
1. **Deprecate Hard Cooldowns:** Remove the manual `Reversal Cooldown Guard` and `Consecutive Direction Limiter` from `_process_adjustment`.
2. Rely **exclusively** on the `Adaptive Whipsaw Guard`. It is smarter (accounts for actual spot movement and time decay) and provides a graduated response (warn -> halve lots -> cooldown) rather than a rigid blind block.

### Phase 3: Resolve ATM Overlap
1. **Enforce Hierarchy:** Make `atm_shield_enabled` the supreme authority. If the Shield decides it cannot act (e.g. failed gates), it should explicitly trigger `atm_wind_down`, NOT `close_at_atm`. 
2. **Remove `close_at_atm`:** `wind_down_on_atm` is significantly healthier for margin and slippage. `close_at_atm` acts as a panic button that often locks in peak losses during transient wicks.

### Phase 4: Protect Against Stale API Checks
1. **Miss-Beat Refactoring:** During a Miss-Beat, *bypass* P&L-based safety checks (`max_loss`, `trailing_stop`, `pnl_guardrail`). Only evaluate time-based limits (`near_expiry`, `close_at_5`) or static threshold limits (`whipsaw_decay`). Relying on stale prices to trigger a `critical` `auto_close_all` is highly unsafe.
