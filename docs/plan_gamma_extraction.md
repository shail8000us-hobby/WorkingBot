# Gamma Extraction — Completed + Remaining Cleanup
**Status:** Extraction DONE (April 3, 2026). Remaining items are cleanup only.

---

## What Was Done (April 3, 2026)

`mmm_gamma.py` was created and the extraction was completed in session `mmm03apr26-1`.

**Moved to `mmm_gamma.py`:**
- `GammaData` TypedDict — raw gamma struct (`portfolio_gamma`, `positions`)
- `build_position_map(session)` — builds `{(strike, opt): lots}` from ce/pe session state
- `compute_gamma_data(ticker_results, position_map)` — raw gamma aggregation; single canonical location for `'call'→'C'` / `'put'→'P'` opt_char mapping
- `_update_gamma_cap(session, gamma_data, spot_price, minutes_to_expiry)` — gamma cap regime logic; computes dollar gamma, sets session state, returns regime string
- `compute_projected_gamma(session, new_strike_gamma, new_lots, spot_price)` — pre-trade projection check
- `_safe_greek(val)` — safe float conversion for exchange greek values
- `GAMMA_NORMAL / GAMMA_SOFT / GAMMA_HARD / GAMMA_EMERGENCY` constants (canonical source)

**`mmm_regime.py`:**
- GAMMA constants removed, imported from `mmm_gamma`
- `_update_gamma_cap` and `compute_projected_gamma` removed, imported from `mmm_gamma`
- `MMMRegimeEngine.update_gamma_cap()` is a thin try/except wrapper calling `mmm_gamma._update_gamma_cap`

**`mmm_monitor.py`:**
- `_calculate_portfolio_delta()` calls `build_position_map` and `compute_gamma_data` from `mmm_gamma`
- `_safe_greek` local redefinition removed; imported from `mmm_gamma` instead

**`test_sealed_mmm_gamma.py`:** 8 sealed tests covering `build_position_map`, `compute_gamma_data`, `_update_gamma_cap`.

---

## Bugs Found and Fixed During Audit (same session)

### Bug 1 — `compute_gamma_data` had `spot_price` parameter it couldn't use correctly
**Problem:** Called as `compute_gamma_data(ticker_results, position_map, 0.0)` — spot was hardcoded to 0. The function computed `ce_dollar_gamma`/`pe_dollar_gamma` inside the struct using `if spot_price > 0` — always 0. Meanwhile `_update_gamma_cap` recomputed them correctly from positions using its own spot_price. Two computations, one always wrong, one correct.

**Fix:** Removed `spot_price` parameter from `compute_gamma_data`. Function now returns only raw data (`portfolio_gamma`, `positions`). Dollar gamma computation belongs exclusively in `_update_gamma_cap` which has spot_price in scope.

### Bug 2 — `GammaData` TypedDict had `ce_dollar_gamma`/`pe_dollar_gamma` fields that were always 0
**Problem:** Struct fields existed but were vestigial — always 0 because of Bug 1. Any code reading `gamma_data['ce_dollar_gamma']` got 0.

**Fix:** Removed both fields from `GammaData`. TypedDict now accurately represents what `compute_gamma_data` actually produces.

### Bug 3 — GAMMA constants defined in two files
**Problem:** `mmm_gamma.py` and `mmm_regime.py` both defined `GAMMA_NORMAL = 'NORMAL'` etc independently. Same values, but fragile if one drifted.

**Fix:** Removed from `mmm_regime.py`. Added `from .mmm_gamma import GAMMA_NORMAL, GAMMA_SOFT, GAMMA_HARD, GAMMA_EMERGENCY` to `mmm_regime.py`. Single source of truth: `mmm_gamma.py`.

### Bug 4 — `_safe_greek` defined in two places
**Problem:** Module-level in `mmm_gamma.py` and redefined as inner function inside `_calculate_portfolio_delta` in `mmm_monitor.py`.

**Fix:** Removed from monitor. Imported from `mmm_gamma` alongside the other imports at the top of the try block.

---

## Remaining Cleanup (do when no session running)

These are cosmetic/structural — no correctness impact.

### 1. `fetch_all()` inner function still lives in `mmm_monitor.py`

`_calculate_portfolio_delta` still has an embedded `async def fetch_all()` that builds and fires ticker API requests. This is the API layer — it belongs in `mmm_gamma` conceptually but pulling it out requires passing `initializer`, `client`, and `expiry` which are monitor-local. Not worth extracting unless the function grows.

**Leave as-is** unless `_calculate_portfolio_delta` grows further.

### 2. `MMMRegimeEngine.update_gamma_cap()` wrapper has try/except but inner function also has guards

The wrapper catches exceptions and returns last-known regime. `_update_gamma_cap` has its own `if not params.get('gamma_cap_enabled')` early return. Two layers is fine, but worth noting if you refactor.

### 3. `test_sealed_mmm_regime.py` still has `test_c_ugc_opt_string_call_put_produces_per_side_gamma`

This test was added to `mmm_regime` tests before `test_sealed_mmm_gamma.py` was created. The equivalent test now lives in `test_sealed_mmm_gamma.py` as `test_c_ugc_opt_string_produces_per_side_gamma`. The regime version tests `_update_gamma_cap` directly (same function, just imported differently). Not a problem — both pass — but if you want to clean up, remove from `test_sealed_mmm_regime.py` and keep only in `test_sealed_mmm_gamma.py`.

---

## Architecture After Extraction

```
mmm_gamma.py  (canonical gamma module)
  ├── GAMMA_NORMAL / SOFT / HARD / EMERGENCY  ← constants
  ├── GammaData (TypedDict)                   ← portfolio_gamma, positions
  ├── _safe_greek(val)                         ← safe float conversion
  ├── build_position_map(session)             ← ce/pe lots from session
  ├── compute_gamma_data(ticker_results, position_map)  ← raw gamma, no spot needed
  ├── _update_gamma_cap(session, gamma_data, spot, minutes_to_expiry)  ← regime + dollar gamma
  └── compute_projected_gamma(session, gamma, lots, spot)  ← pre-trade check

mmm_regime.py  (imports GAMMA constants + two functions from mmm_gamma)
  └── MMMRegimeEngine.update_gamma_cap()  ← thin wrapper with try/except

mmm_monitor.py
  └── _calculate_portfolio_delta()
        ├── build_position_map()       ← from mmm_gamma
        ├── fetch_all()                ← still local (API client is monitor-owned)
        ├── compute_gamma_data()       ← from mmm_gamma (no spot arg)
        └── _safe_greek()              ← from mmm_gamma (for delta parsing)
```
