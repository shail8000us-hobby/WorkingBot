# SSR ALGO — Phase-Wise Development Plan

**Created:** February 20, 2026  
**Last Updated:** February 20, 2026  
**Status:** COMPLETE — All 10 Phases Implemented  
**Maintained By:** Update this document after EVERY phase/sub-task completion  

---

## DOCUMENT MAINTENANCE RULES (READ FIRST)

> **CRITICAL FOR ANY AI CODING AGENT:**  
> 1. **Before starting ANY task**, read this entire document to understand context.  
> 2. **After completing each sub-task**, update the checkbox `[ ]` → `[x]` in this document.  
> 3. **After completing each phase**, add a "Phase X Completion Notes" section at the bottom with:
>    - Date completed
>    - Files created/modified (full paths)
>    - Any deviations from plan
>    - Any new bugs discovered
>    - Updated dependencies or imports
> 4. **If context window is exhausted mid-phase**, the next AI session should:
>    - Read this document first
>    - Check which sub-tasks have `[x]` vs `[ ]`
>    - Resume from the first unchecked `[ ]` item
>    - Read the "Phase X Completion Notes" at bottom for context from prior sessions
> 5. **Never skip a sub-task** — each builds on the previous.
> 6. **Always run the test command** listed at the end of each phase before marking complete.

---

## TABLE OF CONTENTS

- [Current State Audit](#current-state-audit)
- [Phase 1: Live Greeks & MTM P&L Engine](#phase-1-live-greeks--mtm-pl-engine)
- [Phase 2: Profit Target, Stop Loss & Time-Based Exits](#phase-2-profit-target-stop-loss--time-based-exits)
- [Phase 3: Delta-Based Continuous Hedging](#phase-3-delta-based-continuous-hedging)
- [Phase 4: IV Rank Entry Filter & Volatility Context](#phase-4-iv-rank-entry-filter--volatility-context)
- [Phase 5: Leg-by-Leg Adjustment (Surgical Rolls)](#phase-5-leg-by-leg-adjustment-surgical-rolls)
- [Phase 6: DTE Lifecycle Management & Theta Schedule](#phase-6-dte-lifecycle-management--theta-schedule)
- [Phase 7: Market Regime Detection Integration](#phase-7-market-regime-detection-integration)
- [Phase 8: Execution Quality & Slippage Optimization](#phase-8-execution-quality--slippage-optimization)
- [Phase 9: Frontend Dashboard Upgrade](#phase-9-frontend-dashboard-upgrade)
- [Phase 10: RV/IV Ratio, Roll Logic & Advanced Signals](#phase-10-rviv-ratio-roll-logic--advanced-signals)
- [Phase Completion Notes](#phase-completion-notes)

---

## CURRENT STATE AUDIT

### What Exists (Working)

| File | Path | Lines | Purpose | Status |
|------|------|-------|---------|--------|
| Engine | `webui/backend/routes/ssr_algo/ssr_algo_engine.py` | 651 | Strike selection using premium % from ATM | WORKING — selects ATM, OTM buy (45-49%), far OTM sell (20-30%) |
| Executor | `webui/backend/routes/ssr_algo/ssr_algo_executor.py` | 464 | Calls `batch_add` API for order placement | WORKING — executes rounds, waits for fills |
| Monitor | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | 1097 | Background thread checking price every 5s | WORKING — but only checks payoff zone, nothing else |
| Payoff | `webui/backend/routes/ssr_algo/ssr_algo_payoff.py` | 587 | Calculates EXPIRY payoff and max loss points | WORKING — but only expiry payoff, NOT live MTM |
| Storage | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | 556 | JSON file persistence with file locking | WORKING |
| API | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | 1322 | REST endpoints for all operations | WORKING |
| Init | `webui/backend/routes/ssr_algo/__init__.py` | 59 | Module init + monitor restore on startup | WORKING |

### What Exists in Other Modules (Can Be Reused)

| Existing Module | Path | What It Has | How SSR Algo Can Use It |
|-----------------|------|-------------|------------------------|
| **Pricing Engine** | `webui/backend/options_strategy/pricing_engine.py` | Full Black-Scholes-Merton with Greeks (delta, gamma, theta, vega, rho) + Binomial tree + Monte Carlo | **REUSE** for live Greeks calculation — call `OptionPricingEngine.black_scholes_merton()` |
| **Payoff Engine** | `webui/backend/options_strategy/payoff_engine.py` | Black-Scholes pricing, OptionLeg dataclass, contract multipliers (BTC=0.001, ETH=0.01), risk-free rate = 0% | **REUSE** constants + `black_scholes_price()` function |
| **Regime Detector** | `webui/backend/options_strategy/regime_detector.py` | `MarketRegimeDetector` class — trend, volatility, momentum, support/resistance classification | **REUSE** for Phase 7 — call `detect_regime()` |
| **Volatility Analyzer** | `webui/backend/options_strategy/mv_straddle/volatility_analyzer.py` | `VolatilityAnalyzer` class — IV rank, IV percentile calculation | **REUSE** for Phase 4 — call `analyze()` to get IV rank |
| **Chain Service** | `webui/backend/options_chain/chain_service.py` | Full options chain from Delta Exchange — each strike has `delta`, `gamma`, `theta`, `vega`, `iv`, `bid_iv`, `ask_iv`, `mark_price`, `bid`, `ask`, `volume`, `oi` | **REUSE** — chain data ALREADY includes live Greeks from exchange! |
| **SL/TP Manager** | `webui/backend/options_strategy/sl_tp_manager.py` | SQLite-based stop-loss and take-profit manager with auto-execution | **REFERENCE** pattern for Phase 2 exit rules |
| **Max Loss Manager** | `webui/backend/options_strategy/max_loss_manager.py` | Per-strike max loss with auto square-off, warning at 80% threshold, Telegram alerts | **REFERENCE** pattern for circuit breakers |
| **Delta Fetcher** | `webui/backend/options_strategy/delta_fetcher.py` | Authenticated API calls to Delta Exchange, trade history, HMAC signing | **REUSE** for any authenticated API calls |

### What's Broken (Root Causes)

1. **No live awareness**: Monitor only checks `is_price_in_max_loss_zone()` using expiry payoff — has ZERO awareness of current P&L, Greeks, or time decay
2. **No exits besides premium=3**: The only exit mechanism is limit buy at $3 for sell legs — no profit targets, no stop losses, no time exits
3. **No delta management**: Algo watches payoff zone (a TERMINAL construct) instead of managing delta (a LIVE construct) — this means the algo never reacts until catastrophic loss zone
4. **No IV context on entry**: Algo deploys blindly regardless of whether premium is rich or cheap
5. **All-or-nothing adjustment**: When triggered, deploys an ENTIRE new 8-leg butterfly (~$600-1000 premium) instead of surgically adjusting the offending leg (~$100-200)
6. **No DTE awareness**: Algo has no concept of time decay acceleration or expiry gamma risk

### Critical Numbers to Know

```
Exchange: Delta Exchange India
API Base: https://api.india.delta.exchange
Contract Multipliers: BTC = 0.001, ETH = 0.01
Risk-Free Rate: 0% (crypto)
Dividend Yield: 0% (crypto)
Option Style: European (no early exercise)
Backend Port: 5555
Price Check Interval: 5 seconds
API Rate Limit: ~100 requests/minute (be conservative)
Symbol Format: C-BTC-82000-06022026 (type-underlying-strike-expiry)
Expiry Time: 5:30 PM IST
```

---

## PHASE 1: Live Greeks & MTM P&L Engine

**Goal:** Give the algo EYES — it must know its current Greeks and live P&L at all times.  
**Impact:** Enables ALL subsequent phases. Nothing works without this.  
**Estimated Time:** 3-4 hours  
**Dependencies:** None (uses existing infrastructure)  

### Background: Why This Is Phase 1

Currently the monitor loop in `ssr_algo_monitor.py` (line ~494, method `_monitor_loop`) only does:
1. Get current price
2. Calculate expiry payoff → find max loss zones
3. Check if price is in zone → dwell timer → trigger adjustment

After Phase 1, the monitor loop will ALSO:
1. Fetch live Greeks for each open position
2. Calculate mark-to-market P&L (not just expiry intrinsic)
3. Store both in session data for frontend display and decision-making

### Sub-Tasks

#### 1.1 Create `ssr_algo_greeks.py` — Live Greeks Fetcher
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_greeks.py`

**Purpose:** Fetch live Greeks for all positions in an SSR Algo session from the exchange chain data, and calculate portfolio-level aggregated Greeks.

**What this file must contain:**

```python
# CLASS: SSRGreeksFetcher
# 
# METHODS:
#
# 1. fetch_position_greeks(session: Dict) -> Dict
#    - Input: SSR Algo session data (from storage)
#    - For each position group in session['positions']:
#      - For each leg (atm_ce, atm_pe, otm_ce_buy, otm_pe_buy, far_otm_ce, far_otm_pe):
#        - Extract symbol from leg data
#        - Call chain_service.get_chain_data(underlying, expiry) — ALREADY caches for 10s
#        - Find the matching strike in chain data
#        - Read the exchange-provided Greeks: delta, gamma, theta, vega from strike data
#        - Read the exchange-provided mark_price (this IS the live option price)
#        - Read the exchange-provided iv (implied vol)
#    - Return per-leg Greeks + mark_price + iv
#
# 2. calculate_portfolio_greeks(position_greeks: List[Dict]) -> Dict
#    - Sum up: net_delta = Σ(leg_delta × leg_size × contract_multiplier)
#    - Sum up: net_gamma = Σ(leg_gamma × abs(leg_size) × contract_multiplier)
#    - Sum up: net_theta = Σ(leg_theta × leg_size × contract_multiplier)
#    - Sum up: net_vega = Σ(leg_vega × leg_size × contract_multiplier)
#    - Return {net_delta, net_gamma, net_theta, net_vega}
#
# 3. calculate_mtm_pnl(session: Dict, position_greeks: List[Dict]) -> Dict
#    - For each leg:
#      - entry_price = leg['entry_price'] or leg['fill_price']
#      - current_price = position_greeks[leg_symbol]['mark_price']
#      - leg_pnl = (current_price - entry_price) × size × contract_multiplier
#        (note: for sells, size is negative, so loss on price increase is automatic)
#    - total_unrealized_pnl = sum of all leg P&Ls
#    - Include realized_pnl from session['closed_positions']
#    - Return {unrealized_pnl, realized_pnl, total_pnl, per_leg_pnl: [...]}

# SINGLETON: get_greeks_fetcher() -> SSRGreeksFetcher
```

**Key implementation details:**
- Import `OptionsChainService` from `webui.backend.options_chain.chain_service`
- The chain data ALREADY contains `delta`, `gamma`, `theta`, `vega`, `iv`, `mark_price` for each option — see `chain_service.py` lines 393-404
- Contract multipliers: BTC=0.001, ETH=0.01 (use `ssr_algo_payoff.py` constants)
- Size convention: negative = short, positive = long (already used throughout)
- **Cache chain data:** `chain_service` already caches for 10s, so calling it per-cycle is fine
- **Handle missing data:** If exchange returns 0 for delta (happens for deep OTM near expiry), fall back to Black-Scholes calculation using `OptionPricingEngine.black_scholes_merton()` from `webui/backend/options_strategy/pricing_engine.py`
- To use BSM fallback, you need: spot_price, strike, time_to_expiry (calculate from expiry date string), IV (from chain or default 0.60), risk_free_rate=0.0, dividend_yield=0.0

**Expiry date parsing for time_to_expiry:**
```python
# Session stores expiry as DDMMYYYY (8 digits) or DDMMYY (6 digits)
# Normalize with ssr_algo_engine.normalize_expiry_format(expiry) → DDMMYYYY
# Parse: datetime.strptime(normalized, '%d%m%Y')
# Expiry time: 5:30 PM IST = 12:00 UTC (IST = UTC+5:30)
# time_to_expiry_years = (expiry_datetime - now) / timedelta(days=365.25)
```

#### 1.2 Add Greeks & MTM to Monitor Loop
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

**What to change in `_monitor_loop()` method (around line 520):**

After the existing line `self.last_price = current_price`, add a new block:

```python
# === NEW: Live Greeks & MTM Calculation ===
try:
    from .ssr_algo_greeks import get_greeks_fetcher
    greeks_fetcher = get_greeks_fetcher()
    
    # Fetch live Greeks for all positions
    position_greeks = greeks_fetcher.fetch_position_greeks(session)
    
    # Calculate portfolio-level Greeks
    portfolio_greeks = greeks_fetcher.calculate_portfolio_greeks(position_greeks)
    
    # Calculate mark-to-market P&L
    mtm_pnl = greeks_fetcher.calculate_mtm_pnl(session, position_greeks)
    
    # Store in session for frontend and decision-making (every cycle)
    self.update_session(self.session_id, {
        'live_greeks': portfolio_greeks,
        'live_pnl': mtm_pnl,
        'greeks_updated_at': datetime.utcnow().isoformat()
    })
    
except Exception as e:
    log.debug(f"Greeks/MTM calculation skipped: {e}")
# === END NEW ===
```

**Important:** This runs every 5 seconds (same as price check). The chain service caches for 10s, so effectively Greeks update every 10s. This is fine — institutional desks update Greeks every 1-30 seconds.

**Do NOT call `update_session` inside this block if session has no positions** — check `if session.get('positions')` first to avoid unnecessary file I/O.

#### 1.3 Add MTM Fields to Session Storage Schema
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_storage.py`

In `create_session()` method (around line 200), add these new fields to the session dict:

```python
# New fields for live Greeks & MTM (Phase 1)
'live_greeks': {
    'net_delta': 0.0,
    'net_gamma': 0.0,
    'net_theta': 0.0,
    'net_vega': 0.0
},
'live_pnl': {
    'unrealized_pnl': 0.0,
    'realized_pnl': 0.0,
    'total_pnl': 0.0,
    'per_leg_pnl': []
},
'greeks_updated_at': None,
```

#### 1.4 Expose Greeks & MTM in API
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

In the `get_session()` endpoint (line ~167), the session data already includes all fields from storage, so `live_greeks` and `live_pnl` will automatically be returned. No changes needed to existing endpoints.

**Add NEW endpoint** for explicit Greeks refresh:

```python
@ssr_algo_bp.route('/session/<session_id>/greeks', methods=['GET'])
def get_session_greeks(session_id):
    """Get live Greeks and MTM P&L for a session (forces fresh fetch)."""
    # Implementation:
    # 1. Get session from storage
    # 2. Call greeks_fetcher.fetch_position_greeks(session)
    # 3. Call greeks_fetcher.calculate_portfolio_greeks(...)
    # 4. Call greeks_fetcher.calculate_mtm_pnl(...)
    # 5. Update session storage with fresh values
    # 6. Return the fresh Greeks + MTM data
```

#### 1.5 Update `__init__.py` Exports
- [x] **Modify:** `webui/backend/routes/ssr_algo/__init__.py`

Add import for the new greeks module:
```python
from .ssr_algo_greeks import SSRGreeksFetcher, get_greeks_fetcher
```

#### 1.6 Add Frontend Service Method
- [x] **Modify:** `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js`

Add:
```javascript
async getSessionGreeks(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/greeks`);
    return data;
},
```

### Phase 1 Verification

```bash
# Test 1: Start backend and call Greeks endpoint
curl http://localhost:5555/api/ssr_algo/session/<session_id>/greeks

# Expected: JSON with live_greeks (net_delta, net_gamma, etc.) and live_pnl (unrealized, realized, total)

# Test 2: Check that monitor loop is storing Greeks
# Wait 15 seconds after starting a session, then:
curl http://localhost:5555/api/ssr_algo/session/<session_id> | python3 -m json.tool | grep -A5 live_greeks

# Expected: non-zero delta/gamma/theta/vega values

# Test 3: Verify MTM P&L makes sense
# If you sold ATM options, unrealized_pnl should move with BTC price
```

### Phase 1 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_greeks.py` | New file ~200 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | Add ~20 lines in `_monitor_loop()` |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | Add 12 lines in `create_session()` |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Add 1 new endpoint (~30 lines) |
| MODIFY | `webui/backend/routes/ssr_algo/__init__.py` | Add 1 import line |
| MODIFY | `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js` | Add 1 method (~4 lines) |

---

## PHASE 2: Profit Target, Stop Loss & Time-Based Exits

**Goal:** Give the algo EXITS — it must close positions when profitable, when losing too much, or when expiry is too close.  
**Impact:** +20-30% P&L improvement. Prevents sitting in losing positions until max loss.  
**Estimated Time:** 3-4 hours  
**Dependencies:** Phase 1 (needs `live_pnl` data)  

### Background

Currently the algo has only ONE exit: limit buy orders at premium=3 for sell legs. This is a "hope and pray" exit. The algo needs:
1. **Profit target**: Close at 50% of net premium received (configurable)
2. **Stop loss**: Close if unrealized loss exceeds 200% of net premium (configurable)
3. **DTE exit**: Close everything when days-to-expiry ≤ 3 (configurable)

Tastytrade research on iron butterflies shows closing at 50% profit with 200% stop loss improves annual returns by ~25% vs holding to expiry.

### Sub-Tasks

#### 2.1 Create `ssr_algo_exit_manager.py` — Exit Rules Engine
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py`

**What this file must contain:**

```python
# CLASS: SSRExitManager
#
# CONFIGURATION (stored in session):
# {
#   'exit_rules': {
#     'profit_target_enabled': True,
#     'profit_target_percent': 50,       # Close when P&L >= 50% of net premium
#     'stop_loss_enabled': True,
#     'stop_loss_percent': 200,          # Close when loss >= 200% of net premium
#     'dte_exit_enabled': True,
#     'dte_exit_days': 3,                # Close when DTE <= 3
#     'dte_exit_time': '14:00',          # IST time to close on DTE threshold day
#     'trailing_profit_enabled': False,
#     'trailing_profit_percent': 20,     # Trail by 20% from peak profit
#   }
# }
#
# METHODS:
#
# 1. check_exit_conditions(session: Dict) -> Dict
#    - Input: session data (must have live_pnl from Phase 1)
#    - Checks ALL exit rules in priority order:
#      a. DTE EXIT (highest priority — gamma risk):
#         - Parse session['expiry'] (DDMMYYYY)
#         - Calculate DTE = (expiry_date - now).days
#         - If DTE <= exit_rules['dte_exit_days']:
#           return {'should_exit': True, 'reason': 'DTE_EXIT', 'dte': dte}
#      b. STOP LOSS:
#         - net_premium = session.get('net_premium', 0) — stored during initial deployment
#         - unrealized_loss = session['live_pnl']['unrealized_pnl']
#         - If unrealized_loss < 0 and abs(unrealized_loss) >= net_premium * stop_loss_percent / 100:
#           return {'should_exit': True, 'reason': 'STOP_LOSS', 'loss': unrealized_loss}
#      c. PROFIT TARGET:
#         - unrealized_pnl = session['live_pnl']['unrealized_pnl']
#         - If unrealized_pnl >= net_premium * profit_target_percent / 100:
#           return {'should_exit': True, 'reason': 'PROFIT_TARGET', 'profit': unrealized_pnl}
#    - If no condition met: return {'should_exit': False}
#
# 2. execute_full_exit(session_id: str, reason: str) -> Dict
#    - Closes ALL open positions for the session:
#      - For each position group in session['positions']:
#        - For each leg with a symbol:
#          - Determine exit side: if size < 0 (short), exit side = 'buy'; if size > 0, exit side = 'sell'
#          - Place market order via batch_add API (same as executor)
#    - Update session status to 'STOPPED'
#    - Store stop_reason = reason
#    - Log the exit with full details
#    - Return {success, orders_placed, total_exit_pnl}
#
# 3. calculate_dte(expiry: str) -> float
#    - Parse DDMMYYYY format
#    - Return fractional days to expiry (e.g., 3.5)
#    - Account for IST timezone (expiry at 5:30 PM IST)

# SINGLETON: get_exit_manager() -> SSRExitManager
```

**Key implementation details:**
- For market exit orders, use the same `executor.execute_rounds()` with `rounds=1` and the appropriate exit orders
- Or call the batch_add API directly (simpler for exits): POST to `http://localhost:5555/api/options/batch_add` with exit orders
- Net premium is already stored in session during initial deployment (see `ssr_algo_api.py` line ~665: `'net_premium': payoff_data.get('net_premium', 0)`)
- **Stop the monitor** after exit via `stop_session_monitor(session_id)`
- Log every exit with full details: reason, P&L, positions closed, time

#### 2.2 Add Exit Rules to Session Schema
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_storage.py`

In `create_session()`, add default exit_rules to the session dict:

```python
'exit_rules': {
    'profit_target_enabled': True,
    'profit_target_percent': 50,
    'stop_loss_enabled': True,
    'stop_loss_percent': 200,
    'dte_exit_enabled': True,
    'dte_exit_days': 3,
    'dte_exit_time': '14:00',
    'trailing_profit_enabled': False,
    'trailing_profit_percent': 20,
},
```

Also add `exit_rules` as an accepted parameter in `create_session()` method signature.

#### 2.3 Integrate Exit Checks into Monitor Loop
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

In `_monitor_loop()`, AFTER the Greeks/MTM block from Phase 1, add:

```python
# === NEW: Exit Condition Checks (Phase 2) ===
try:
    from .ssr_algo_exit_manager import get_exit_manager
    exit_mgr = get_exit_manager()
    
    # Only check exits if we have valid P&L data
    if session.get('live_pnl') and session['live_pnl'].get('unrealized_pnl') is not None:
        exit_check = exit_mgr.check_exit_conditions(session)
        
        if exit_check.get('should_exit'):
            reason = exit_check['reason']
            log.warning(f"[{self.session_id}] EXIT TRIGGERED: {reason}")
            add_session_log(self.session_id, 
                f"🚪 EXIT TRIGGERED: {reason}", 'trigger')
            
            # Execute full exit
            exit_result = exit_mgr.execute_full_exit(self.session_id, reason)
            
            if exit_result.get('success'):
                add_session_log(self.session_id,
                    f"✅ All positions closed. Reason: {reason}. PnL: ${exit_result.get('total_exit_pnl', 0):.2f}",
                    'success')
                # Stop the monitor
                self._running = False
                break
            else:
                add_session_log(self.session_id,
                    f"⚠️ Exit attempted but had issues: {exit_result.get('error')}",
                    'error')
except Exception as e:
    log.debug(f"Exit check skipped: {e}")
# === END NEW ===
```

**CRITICAL PLACEMENT:** This block MUST be BEFORE the existing payoff zone trigger logic. Exits take priority over adjustments. The flow should be:
1. Fetch price ✓
2. Calculate Greeks & MTM (Phase 1) 
3. **Check exit conditions (Phase 2) ← NEW**
4. Check payoff zone triggers (existing)

#### 2.4 Add Exit Rules to API Create Session Endpoint
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

In `create_session()` endpoint (line ~201), add parsing of exit_rules from request body:

```python
exit_rules = data.get('exit_rules', None)
```

Pass it to `storage.create_session(..., exit_rules=exit_rules)`.

#### 2.5 Add Manual Exit API Endpoint
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

Add new endpoint:

```python
@ssr_algo_bp.route('/session/<session_id>/exit', methods=['POST'])
def exit_session(session_id):
    """Manually trigger full position exit for a session."""
    # 1. Validate session exists and is in MONITORING state
    # 2. Call exit_mgr.execute_full_exit(session_id, 'MANUAL_EXIT')
    # 3. Stop monitor
    # 4. Return result
```

#### 2.6 Add Exit Rules to Frontend Config Panel
- [x] **Modify:** `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` (done in Phase 9 — Algo Features section)

Add input fields for exit rules in the config form:
- Profit Target %: number input (default 50)
- Stop Loss %: number input (default 200)
- DTE Exit Days: number input (default 3)
- Enable toggles for each

#### 2.7 Add Frontend Service Method for Manual Exit
- [x] **Modify:** `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js`

```javascript
async exitSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/exit`);
    return data;
},
```

#### 2.8 Update `__init__.py`
- [x] **Modify:** `webui/backend/routes/ssr_algo/__init__.py`

Add import:
```python
from .ssr_algo_exit_manager import SSRExitManager, get_exit_manager
```

### Phase 2 Verification

```bash
# Test 1: Create session with exit rules
curl -X POST http://localhost:5555/api/ssr_algo/session/create \
  -H "Content-Type: application/json" \
  -d '{"underlying":"BTC","expiry":"060326","exit_rules":{"profit_target_percent":50,"stop_loss_percent":200}}'

# Test 2: Check exit_rules are stored
curl http://localhost:5555/api/ssr_algo/session/<id> | python3 -m json.tool | grep -A10 exit_rules

# Test 3: Manual exit
curl -X POST http://localhost:5555/api/ssr_algo/session/<id>/exit

# Test 4: Verify DTE calculation
# Call the endpoint on a session with expiry tomorrow — should trigger DTE exit
```

### Phase 2 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py` | New file ~250 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | Add ~25 lines in `_monitor_loop()` |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | Add exit_rules to schema (~15 lines) |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Add 1 endpoint + modify create (~40 lines) |
| MODIFY | `webui/backend/routes/ssr_algo/__init__.py` | Add 1 import line |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` | Add exit rule inputs |
| MODIFY | `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js` | Add 1 method |

---

## PHASE 3: Delta-Based Continuous Hedging

**Goal:** Replace the blunt "payoff zone + 10 minute dwell" trigger with intelligent, continuous delta-based hedging. This is the SINGLE BIGGEST transformation — it changes the algo from "place and pray" to actively managed.  
**Impact:** +40-60% P&L improvement. Prevents reaching max loss zone at all.  
**Estimated Time:** 4-5 hours  
**Dependencies:** Phase 1 (needs `live_greeks.net_delta`)  

### Background: What Changes

**BEFORE (current):** Algo monitors price → waits for max loss zone → waits 10 minutes → deploys entire new butterfly ($600-1000)

**AFTER:** Algo monitors delta → small hedge when delta drifts past ±0.20 → medium adjustment when delta past ±0.50 → full restructure only at ±1.0. The small hedges cost $50-150 and PREVENT ever reaching the max loss zone.

### How Institutional Delta Hedging Works

```
Hedge Type        | Delta Threshold | Action                           | Cost
─────────────────│─────────────────│──────────────────────────────────│──────
Micro-hedge       | |delta| > 0.20 | Roll the OTM sell leg closer     | ~$50-100
Standard hedge    | |delta| > 0.40 | Roll the tested side ATM leg     | ~$100-200
Emergency hedge   | |delta| > 0.80 | Full butterfly adjustment         | ~$500-1000
```

The key insight: by hedging at ±0.20, you spend $50 to prevent a $500 problem.

### Sub-Tasks

#### 3.1 Create `ssr_algo_delta_hedger.py` — Delta Management Engine
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py`

**What this file must contain:**

```python
# CLASS: SSRDeltaHedger
#
# CONFIGURATION (stored in session):
# {
#   'delta_hedge_config': {
#     'enabled': True,
#     'micro_hedge_threshold': 0.20,     # |delta| for small adjustments
#     'standard_hedge_threshold': 0.40,   # |delta| for medium adjustments
#     'emergency_hedge_threshold': 0.80,  # |delta| for full restructure
#     'hedge_cooldown_minutes': 5,        # Min time between hedges
#     'max_hedges_per_day': 15,           # Cap daily hedge count
#     'hedge_method': 'roll_leg',         # 'roll_leg' or 'add_position'
#   }
# }
#
# METHODS:
#
# 1. check_delta_hedge_needed(session: Dict) -> Dict
#    - Read session['live_greeks']['net_delta']
#    - Compare against thresholds
#    - Check cooldown (session['last_hedge_time'])
#    - Check daily hedge count (session['daily_hedge_count'])
#    - Return:
#      {
#        'hedge_needed': bool,
#        'hedge_type': 'micro' | 'standard' | 'emergency' | None,
#        'current_delta': float,
#        'threshold_breached': float,
#        'direction': 'bullish' | 'bearish'  # which way delta drifted
#      }
#
# 2. execute_micro_hedge(session: Dict, direction: str) -> Dict
#    - direction = 'bullish' (delta > +0.20) or 'bearish' (delta < -0.20)
#    - IF BULLISH (delta positive = price rallied, CE side losing):
#      a. Find the far OTM PE sell leg (the one with least premium remaining)
#      b. Buy it back (close)
#      c. Sell a new PE closer to current ATM (capture more premium, reduce delta)
#      d. This is called "rolling up the untested side"
#    - IF BEARISH (delta negative = price dropped, PE side losing):
#      a. Find the far OTM CE sell leg
#      b. Buy it back
#      c. Sell a new CE closer to current ATM
#    - Return {success, orders_placed, new_delta_estimate, cost}
#
# 3. execute_standard_hedge(session: Dict, direction: str) -> Dict
#    - Bigger adjustment — roll the ATM sell leg on the TESTED side
#    - IF BULLISH (delta positive):
#      a. Buy back ATM CE sell (it's losing money)
#      b. Sell new CE at current ATM (higher strike, captures fresh premium)
#      c. Optionally roll OTM CE buy higher too
#    - IF BEARISH:
#      a. Buy back ATM PE sell
#      b. Sell new PE at current ATM (lower strike)
#    - Return {success, orders_placed, new_delta_estimate, cost}
#
# 4. execute_emergency_hedge(session: Dict, direction: str) -> Dict
#    - This IS the current full adjustment logic (deploy new butterfly)
#    - Reuse existing _trigger_adjustment() logic from ssr_algo_monitor.py
#    - But now it only fires at extreme delta, not at a static payoff zone
#    - Return {success, orders_placed}
#
# 5. _place_roll_orders(session_id, close_symbol, close_size, 
#                        new_symbol, new_size, new_side) -> Dict
#    - Helper: places close order + new order
#    - Uses batch_add API (same as executor)
#    - Tracks as adjustment orders in storage
#    - Returns success/failure

# SINGLETON: get_delta_hedger() -> SSRDeltaHedger
```

**Key implementation details:**
- For "rolling a leg" you need to:
  1. Buy back the existing position (reverse the original trade)
  2. Sell a new position at the desired strike
  3. Both orders should be placed via `batch_add` in a single call
- To find the "new strike to sell at", use the existing `StrikeSelector` but with a narrower search — you're looking for a specific premium level, not the full butterfly structure
- After any hedge, the position group in storage must be updated to reflect the changed legs
- **Create a new method in storage:** `update_position_leg(session_id, trigger_id, leg_key, new_leg_data)` — to update a single leg within a position group without replacing the whole group

#### 3.2 Add Delta Hedge Config to Session Schema
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_storage.py`

Add to `create_session()`:
```python
'delta_hedge_config': {
    'enabled': True,
    'micro_hedge_threshold': 0.20,
    'standard_hedge_threshold': 0.40,
    'emergency_hedge_threshold': 0.80,
    'hedge_cooldown_minutes': 5,
    'max_hedges_per_day': 15,
    'hedge_method': 'roll_leg',
},
'last_hedge_time': None,
'daily_hedge_count': 0,
'hedge_history': [],
```

Also add `delta_hedge_config` as parameter to `create_session()`.

Add new method:
```python
def update_position_leg(self, session_id, trigger_id, leg_key, new_leg_data):
    """Update a single leg within a specific position group."""
    # Find position group by trigger_id
    # Update the specific leg_key with new_leg_data
    # Persist
```

#### 3.3 Integrate Delta Hedging into Monitor Loop
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

In `_monitor_loop()`, AFTER the exit checks (Phase 2) and BEFORE the existing payoff zone trigger logic, add:

```python
# === NEW: Delta-Based Hedging (Phase 3) ===
try:
    from .ssr_algo_delta_hedger import get_delta_hedger
    delta_hedger = get_delta_hedger()
    
    hedge_config = session.get('delta_hedge_config', {})
    if hedge_config.get('enabled', False) and session.get('live_greeks'):
        hedge_check = delta_hedger.check_delta_hedge_needed(session)
        
        if hedge_check.get('hedge_needed'):
            hedge_type = hedge_check['hedge_type']
            direction = hedge_check['direction']
            current_delta = hedge_check['current_delta']
            
            add_session_log(self.session_id,
                f"📐 Delta hedge triggered: {hedge_type} ({direction}) — delta={current_delta:.3f}",
                'trigger')
            
            if hedge_type == 'micro':
                result = delta_hedger.execute_micro_hedge(session, direction)
            elif hedge_type == 'standard':
                result = delta_hedger.execute_standard_hedge(session, direction)
            elif hedge_type == 'emergency':
                # Emergency = existing full adjustment
                result = delta_hedger.execute_emergency_hedge(session, direction)
            
            if result.get('success'):
                add_session_log(self.session_id,
                    f"✅ {hedge_type} hedge completed. Cost: ${result.get('cost', 0):.2f}",
                    'success')
                # Record hedge
                self.update_session(self.session_id, {
                    'last_hedge_time': datetime.now().isoformat(),
                    'daily_hedge_count': session.get('daily_hedge_count', 0) + 1
                })
except Exception as e:
    log.debug(f"Delta hedge check skipped: {e}")
# === END NEW ===
```

**IMPORTANT:** If delta hedging is enabled, the EXISTING payoff zone trigger (dwell timer) should still run as a BACKSTOP, but only for emergency cases. Add a check: if `delta_hedge_config.enabled`, increase the dwell time to 20 minutes (the delta hedger should catch it first). If delta hedging is disabled, use the original 10-minute dwell.

#### 3.4 Modify Existing Payoff Zone Trigger to Act as Backstop
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

In the existing dwell threshold logic (around line 560-580), add a condition:

```python
# If delta hedging is enabled, the payoff zone trigger is a BACKSTOP only
# Use longer dwell time (the delta hedger should catch issues first)
if session.get('delta_hedge_config', {}).get('enabled', False):
    effective_dwell = max(
        self.dwell_tracker.dwell_threshold.total_seconds() / 60,
        20  # Minimum 20 minutes when delta hedging is on
    )
    if time_in_zone < effective_dwell * 60:
        # Not long enough for backstop trigger
        continue
```

#### 3.5 Add Delta Hedge Config to API & Frontend
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py` — parse `delta_hedge_config` from request body in create endpoint
- [x] **Modify:** `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` — added delta hedge toggle and threshold inputs in Algo Features section (completed in Phase 9)

### Phase 3 Verification

```bash
# Test 1: Create session with delta hedging enabled
curl -X POST http://localhost:5555/api/ssr_algo/session/create \
  -H "Content-Type: application/json" \
  -d '{"underlying":"BTC","expiry":"060326","delta_hedge_config":{"enabled":true,"micro_hedge_threshold":0.20}}'

# Test 2: After session starts, verify live_greeks show delta
curl http://localhost:5555/api/ssr_algo/session/<id> | python3 -m json.tool | grep net_delta

# Test 3: Check logs for delta hedge activity
curl http://localhost:5555/api/ssr_algo/session/<id>/logs | python3 -m json.tool | grep -i delta
```

### Phase 3 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py` | New file ~400 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | Add ~40 lines + modify backstop logic |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | Add delta config + `update_position_leg()` method |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Parse delta_hedge_config |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` | Add delta hedge UI |

---

## PHASE 4: IV Rank Entry Filter & Volatility Context

**Goal:** Only deploy the butterfly when premium is truly rich (IV is elevated). Prevents entering when options are cheap and the credit received doesn't compensate for risk.  
**Impact:** +15-25% P&L improvement by avoiding unfavorable entries.  
**Estimated Time:** 2-3 hours  
**Dependencies:** Phase 1 (for context), but can be developed independently  

### Background

Selling premium (which the butterfly does) is only profitable when implied volatility is high relative to its historical range. When IV is low, three problems occur:
1. Less premium collected → smaller profit potential
2. If IV rises → position loses on vega → immediate MTM loss
3. Wider bid-ask spreads in low-vol environments → worse execution

### Sub-Tasks

#### 4.1 Create `ssr_algo_vol_analyzer.py` — Volatility Context Engine
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_vol_analyzer.py`

```python
# CLASS: SSRVolAnalyzer
#
# METHODS:
#
# 1. get_iv_context(underlying: str, expiry: str) -> Dict
#    - Fetch current ATM IV from chain data
#      (chain_service returns 'iv' and 'bid_iv', 'ask_iv' per strike)
#    - Calculate IV Rank:
#      a. Use VolatilityAnalyzer from webui.backend.options_strategy.mv_straddle.volatility_analyzer
#         (already has iv_percentile calculation)
#      b. OR calculate manually: fetch 30-day IV history, rank current IV
#    - Calculate IV context metrics:
#      - current_atm_iv: float (ATM option IV)
#      - iv_rank: float (0-100 percentile)
#      - iv_classification: 'very_low' | 'low' | 'normal' | 'high' | 'very_high'
#      - skew: float (ATM PE IV - ATM CE IV; positive = put skew)
#      - term_structure: 'contango' | 'backwardation' | 'flat'
#        (compare near-expiry IV vs far-expiry IV if possible)
#    - Return {current_atm_iv, iv_rank, iv_classification, skew, term_structure, recommendation}
#
# 2. get_entry_recommendation(iv_context: Dict) -> Dict
#    - Based on IV rank:
#      - iv_rank < 20: REFUSE entry ('IV too low, premium not sufficient')
#      - iv_rank 20-30: WARN ('Low IV, consider reduced size')
#      - iv_rank 30-50: ALLOW with standard size
#      - iv_rank 50-70: RECOMMENDED ('Good premium environment')
#      - iv_rank > 70: STRONGLY RECOMMENDED ('IV elevated, ideal for premium selling')
#    - Return {should_enter: bool, confidence: float, reason: str, 
#              recommended_size_multiplier: float}
#
# 3. adjust_strikes_for_skew(strikes: Dict, skew: float) -> Dict
#    - If put skew > 5%: narrow PE buy range slightly (40-45% instead of 45-49%)
#      because puts are expensive → OTM puts have more premium per strike
#    - If call skew > 5%: narrow CE buy range similarly
#    - Return modified strike selection ranges

# SINGLETON: get_vol_analyzer() -> SSRVolAnalyzer
```

**Key implementation details:**
- For IV Rank calculation WITHOUT historical data: use the existing `VolatilityAnalyzer.analyze()` method which returns `iv_percentile` and `iv_rank`
- For skew: at the ATM strike, compare `call['iv']` vs `put['iv']` from chain data
- For term structure: compare ATM IV across different expiries (call `chain_service.get_chain_data` for 2 expiries)
- If chain data returns IV=0 for some quotes, fall back to mark_price-based IV calculation using the pricing engine

#### 4.2 Add IV Pre-Check to Session Start Flow
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

In `start_session()` endpoint (line ~390), BEFORE strike selection, add:

```python
# === NEW: IV Context Check (Phase 4) ===
from .ssr_algo_vol_analyzer import get_vol_analyzer
vol_analyzer = get_vol_analyzer()

iv_context = vol_analyzer.get_iv_context(
    session['underlying'], session['expiry']
)
entry_recommendation = vol_analyzer.get_entry_recommendation(iv_context)

# Store IV context in session
storage.update_session(session_id, {
    'iv_context_at_entry': iv_context,
    'entry_recommendation': entry_recommendation
})
storage.add_log(session_id, 
    f"📊 IV Rank: {iv_context.get('iv_rank', 'N/A')}% — {iv_context.get('iv_classification', 'unknown')}",
    'info')

# Block entry if IV is too low (configurable)
iv_filter_config = session.get('iv_filter_config', {})
if iv_filter_config.get('enabled', False):
    min_iv_rank = iv_filter_config.get('min_iv_rank', 20)
    if iv_context.get('iv_rank', 50) < min_iv_rank:
        storage.add_log(session_id, 
            f"🚫 Entry blocked: IV Rank {iv_context['iv_rank']}% < minimum {min_iv_rank}%",
            'error')
        storage.update_session(session_id, {
            'status': 'IDLE',
            'started_at': None
        })
        return jsonify({
            'success': False,
            'error': f"IV Rank too low ({iv_context['iv_rank']}%). Minimum: {min_iv_rank}%",
            'iv_context': iv_context
        }), 400
# === END NEW ===
```

#### 4.3 Add IV Filter Config to Session Schema
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_storage.py`

Add to session creation:
```python
'iv_filter_config': {
    'enabled': False,         # Disabled by default (opt-in)
    'min_iv_rank': 20,        # Minimum IV rank to allow entry
    'warn_iv_rank': 30,       # Warn but allow at this level
    'ideal_iv_rank': 50,      # Ideal entry threshold
},
'iv_context_at_entry': None,
'entry_recommendation': None,
```

#### 4.4 Add IV Display to Frontend
- [x] **Modify:** `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` — IV filter toggle + min rank input (done in Phase 9)
- [x] **Modify:** `webui/frontend/src/components/ssrAlgo/SSRAlgoSessionCard.js` — Show IV rank badge/indicator + DTE phase badge + live P&L badge

#### 4.5 Add IV Preview to Strike Preview Endpoint
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

In `preview_strikes()` endpoint (line ~340), also fetch and return IV context:
```python
vol_analyzer = get_vol_analyzer()
iv_context = vol_analyzer.get_iv_context(underlying, expiry)
# Include in response alongside strikes
```

### Phase 4 Verification
```bash
# Test 1: Get IV context for BTC
curl http://localhost:5555/api/ssr_algo/preview_strikes \
  -X POST -H "Content-Type: application/json" \
  -d '{"underlying":"BTC","expiry":"060326"}'
# Should include iv_context in response

# Test 2: Try starting with IV filter enabled and very high min_iv_rank
# Should block entry if current IV is below threshold
```

### Phase 4 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_vol_analyzer.py` | New file ~200 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Add IV check to start + preview (~30 lines) |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | Add iv_filter_config (~10 lines) |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` | Add IV filter UI |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoSessionCard.js` | Show IV rank badge |

---

## PHASE 5: Leg-by-Leg Adjustment (Surgical Rolls)

**Goal:** When the current full-butterfly adjustment fires (from Phase 3 emergency hedge or existing logic), make it smarter — only adjust the legs that are in trouble.  
**Impact:** -50% adjustment cost. A $600 full adjustment becomes a $200 surgical roll.  
**Estimated Time:** 3-4 hours  
**Dependencies:** Phase 1 (Greeks), Phase 3 (delta hedger uses similar API)  

### Background

Currently when `_trigger_adjustment()` fires in `ssr_algo_monitor.py`, it:
1. Selects 6 new strikes (full butterfly)
2. Places 8 orders (same as initial deployment)
3. Cost: full premium for the new structure

A smarter approach:
- If delta is positive (price rallied): only the CALL side is in trouble
  - Buy back ATM CE sell + far OTM CE sell (closing losing side)
  - Sell new CE at higher strikes (collecting fresh premium)
  - Leave the PUT side completely alone (it's profitable)
- If delta is negative (price dropped): only the PUT side is in trouble
  - Same logic, mirrored for puts

### Sub-Tasks

#### 5.1 Add Surgical Roll Logic to Delta Hedger
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py`

Add new method `execute_surgical_adjustment()`:

```python
# METHOD: execute_surgical_adjustment(session: Dict, direction: str) -> Dict
#
# LOGIC:
# 1. Identify which side is under pressure:
#    - direction='bullish' → CALL side is under pressure (price went up)
#    - direction='bearish' → PUT side is under pressure (price went down)
#
# 2. Close ONLY the troubled side legs:
#    IF direction == 'bullish':
#      - Close: ATM CE sell, Far OTM CE sell  (buy them back)
#      - Keep:  ATM PE sell, Far OTM PE sell   (leave alone)
#      - Keep:  Both OTM buys                  (leave alone)
#    IF direction == 'bearish':
#      - Close: ATM PE sell, Far OTM PE sell  (buy them back)  
#      - Keep:  ATM CE sell, Far OTM CE sell  (leave alone)
#      - Keep:  Both OTM buys                 (leave alone)
#
# 3. Open NEW legs on the closed side at CURRENT ATM:
#    - Use StrikeSelector to find new ATM (current spot)
#    - Only select strikes for the troubled side
#    - Place orders for new sell legs + new OTM buy leg
#    - The untested side's OTM buy remains as protection
#
# 4. Update position group:
#    - Mark closed legs in old position group
#    - Add realized P&L for closed legs to closed_positions
#    - Create new position group with only the new legs
#
# 5. Recalculate max loss zones from combined positions
#
# COMPARISON:
# Full adjustment (current):  8 orders ($600-1000)
# Surgical adjustment (new):  4-5 orders ($200-400)
```

#### 5.2 Replace Emergency Hedge Implementation
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py`

In `execute_emergency_hedge()`, instead of calling the old full `_trigger_adjustment()` logic, call the new `execute_surgical_adjustment()` method. Keep the full butterfly deployment as a configurable fallback.

#### 5.3 Add Position Leg Close Tracking to Storage
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_storage.py`

Add method:
```python
def close_position_leg(self, session_id: str, trigger_id: int, leg_key: str, 
                       close_price: float, realized_pnl: float) -> Optional[Dict]:
    """Mark a specific leg as closed and record realized P&L."""
    # Find position group by trigger_id
    # Set leg['closed'] = True, leg['close_price'] = close_price
    # Add to closed_positions
    # Return updated session
```

### Phase 5 Verification
```bash
# Test: Simulate by manually calling surgical adjustment
# (Requires running session with positions)
# Check logs for "surgical" adjustment vs "full" adjustment
# Verify only 4-5 orders placed instead of 8
```

### Phase 5 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py` | Add surgical roll (~150 lines) |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | Add `close_position_leg()` method |

---

## PHASE 6: DTE Lifecycle Management & Theta Schedule

**Goal:** Make the algo aware of time — different DTE ranges require different behavior. Near-expiry gamma is dangerous; mid-life theta is where money is made.  
**Impact:** +10% P&L improvement by optimizing for time decay phases.  
**Estimated Time:** 2-3 hours  
**Dependencies:** Phase 1 (Greeks), Phase 2 (exit manager), Phase 3 (delta hedger)  

### Sub-Tasks

#### 6.1 Create `ssr_algo_dte_manager.py` — DTE Lifecycle Engine
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_dte_manager.py`

```python
# CLASS: SSRDTEManager
#
# DTE LIFECYCLE PHASES:
#
# Phase 1: EARLY LIFE (DTE > 21)
#   delta_hedge_threshold: 0.15 (tighter)
#   profit_target_multiplier: 1.0 (no change)
#   behavior: "Build position, tight risk management"
#   notes: "Theta is minimal, position is mostly vega play. Keep tight delta."
#
# Phase 2: PEAK THETA (DTE 7-21) ← THIS IS WHERE MONEY IS MADE
#   delta_hedge_threshold: 0.30 (relaxed — let theta work)
#   profit_target_multiplier: 0.8 (lower target — take money sooner)
#   behavior: "Relax delta, let theta decay work for you"
#   notes: "Theta accelerates. Widening delta band reduces unnecessary hedging costs."
#
# Phase 3: GAMMA DANGER (DTE 3-7)
#   delta_hedge_threshold: 0.10 (very tight)
#   profit_target_multiplier: 0.5 (take any profit)
#   behavior: "Tighten everything, prepare for exit"
#   notes: "Gamma dominates. Small price moves cause big delta changes."
#
# Phase 4: EXIT ZONE (DTE < 3)
#   action: FORCE EXIT (via Phase 2 exit manager)
#   reason: "Gamma too high, pin risk, settlement risk"
#
# METHODS:
#
# 1. get_dte_phase(session: Dict) -> Dict
#    - Calculate DTE from session['expiry']
#    - Determine which phase
#    - Return {dte, phase, phase_name, recommended_delta_threshold, 
#              recommended_profit_target_multiplier, description}
#
# 2. apply_dte_adjustments(session: Dict, dte_phase: Dict) -> Dict
#    - Dynamically adjust session parameters based on DTE phase:
#      - Override delta_hedge_config thresholds for the current cycle
#      - Override profit target for the current cycle
#    - Return modified config (does NOT persist — applied per-cycle)
#
# 3. should_close_far_otm_near_expiry(session: Dict) -> List[Dict]
#    - If DTE < 5 and far OTM sell legs have premium < $5:
#      → Recommend buying them back (they're worthless but have gamma risk)
#    - Return list of legs to consider closing

# SINGLETON: get_dte_manager() -> SSRDTEManager
```

#### 6.2 Integrate DTE Manager into Monitor Loop
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

At the TOP of `_monitor_loop()` (before Greeks fetch), add DTE phase calculation:

```python
# === NEW: DTE Phase Check (Phase 6) ===
from .ssr_algo_dte_manager import get_dte_manager
dte_mgr = get_dte_manager()
dte_phase = dte_mgr.get_dte_phase(session)

# Log phase transitions
current_phase = session.get('current_dte_phase')
if current_phase != dte_phase.get('phase'):
    add_session_log(self.session_id,
        f"📅 DTE Phase: {dte_phase['phase_name']} (DTE={dte_phase['dte']:.1f})",
        'info')
    self.update_session(self.session_id, {
        'current_dte_phase': dte_phase['phase']
    })

# Apply DTE-based threshold adjustments for this cycle
cycle_config = dte_mgr.apply_dte_adjustments(session, dte_phase)
# Use cycle_config.delta_threshold instead of static config for delta hedging
# === END NEW ===
```

**Pass `cycle_config` to delta hedger** so it uses the DTE-adjusted threshold:
```python
hedge_check = delta_hedger.check_delta_hedge_needed(session, 
    override_threshold=cycle_config.get('delta_threshold'))
```

This requires modifying `check_delta_hedge_needed()` to accept an optional override threshold.

#### 6.3 Add DTE Info to Session Status API
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Added current_dte_phase, live_greeks, live_pnl, and current_regime to /status endpoint session data

In the `get_session()` response, automatically include DTE phase. Or add it to the `/status` endpoint.

### Phase 6 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_dte_manager.py` | New file ~200 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | Add ~15 lines DTE check at top |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py` | Accept override_threshold param |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Include DTE phase in status |

---

## PHASE 7: Market Regime Detection Integration

**Goal:** Adjust butterfly structure based on whether market is trending or range-bound. Butterflies profit in ranges and lose in trends.  
**Impact:** +10-15% P&L improvement by adapting to market conditions.  
**Estimated Time:** 2-3 hours  
**Dependencies:** None (uses existing `regime_detector.py`)  

### Sub-Tasks

#### 7.1 Create `ssr_algo_regime.py` — Regime-Aware Configuration
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_regime.py`

```python
# CLASS: SSRRegimeAdapter
#
# Uses existing MarketRegimeDetector from:
#   webui/backend/options_strategy/regime_detector.py
#
# METHODS:
#
# 1. get_regime_adjustments(underlying: str, current_price: float) -> Dict
#    - Call MarketRegimeDetector.detect_regime(symbol, current_price)
#    - Based on regime, return adjustments:
#
#    RANGING MARKET (trend='neutral', volatility='normal'):
#      - Standard butterfly (no changes)
#      - Full position size
#      - Normal delta threshold
#      → {'position_size_multiplier': 1.0, 'wing_width_multiplier': 1.0,
#          'delta_threshold_multiplier': 1.0, 'regime': 'ranging'}
#
#    TRENDING MARKET (trend='strong_up' or 'strong_down'):
#      - WIDEN wings (move OTM buys further out for more room)
#        → Change OTM buy range from 45-49% to 35-42% of ATM
#      - REDUCE size (50% of normal)
#      - TIGHTEN delta threshold (hedge more aggressively)
#      → {'position_size_multiplier': 0.5, 'wing_width_multiplier': 0.8,
#          'delta_threshold_multiplier': 0.7, 'regime': 'trending'}
#
#    HIGH VOLATILITY (volatility='elevated' or 'extreme'):
#      - WIDEN wings (more premium available at wider strikes)
#      - INCREASE size (premium is rich — sell more)
#      - Keep delta threshold normal
#      → {'position_size_multiplier': 1.5, 'wing_width_multiplier': 0.7,
#          'delta_threshold_multiplier': 1.0, 'regime': 'high_vol'}
#
#    LOW VOLATILITY (volatility='low'):
#      - NARROW wings (less premium → need tighter structure)
#      - REDUCE size (premium is thin)
#      → {'position_size_multiplier': 0.5, 'wing_width_multiplier': 1.2,
#          'delta_threshold_multiplier': 1.0, 'regime': 'low_vol'}
#
# 2. adjust_strike_config(base_config: Dict, adjustments: Dict) -> Dict
#    - Apply wing_width_multiplier to OTM buy percent ranges
#    - Return modified strike_config for this deployment

# SINGLETON: get_regime_adapter() -> SSRRegimeAdapter
```

#### 7.2 Integrate Regime Check at Entry
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

In `start_session()`, BEFORE strike selection, add regime check:
```python
# Get regime-based adjustments
regime_adapter = get_regime_adapter()
regime_adjustments = regime_adapter.get_regime_adjustments(
    session['underlying'], spot_price
)
# Adjust strike_config based on regime
adjusted_config = regime_adapter.adjust_strike_config(
    session['strike_config'], regime_adjustments
)
# Use adjusted_config for strike selection instead of raw config
```

#### 7.3 Integrate Regime Check During Monitoring
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

Check regime periodically (every 5 minutes, not every cycle — it's expensive):
```python
# Check regime every 5 minutes
if not hasattr(self, '_last_regime_check') or \
   (datetime.now() - self._last_regime_check).total_seconds() > 300:
    # Fetch regime and apply delta threshold multiplier
    self._last_regime_check = datetime.now()
```

### Phase 7 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_regime.py` | New file ~150 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Add regime check before entry |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | Add periodic regime check |

---

## PHASE 8: Execution Quality & Slippage Optimization

**Goal:** Improve order execution to reduce slippage and save 2-5% per trade.  
**Impact:** Compounds across all trades — significant over time.  
**Estimated Time:** 2-3 hours  
**Dependencies:** None  

### Sub-Tasks

#### 8.1 Create `ssr_algo_smart_executor.py` — Smart Order Router
- [x] **Create new file:** `webui/backend/routes/ssr_algo/ssr_algo_smart_executor.py`

```python
# CLASS: SSRSmartExecutor (wraps existing SSRAutoLoopExecutor)
#
# METHODS:
#
# 1. execute_with_smart_routing(orders: List[Dict], urgency: str) -> Dict
#    - urgency = 'low' | 'medium' | 'high' | 'critical'
#    - For each order:
#      a. Fetch current bid/ask from chain data
#      b. Calculate spread = (ask - bid) / mid_price * 100
#      c. Route based on spread and urgency:
#
#         LOW urgency (regular entry):
#           IF spread < 1%: market order
#           IF spread 1-3%: limit at mid-price, wait 30s
#           IF spread > 3%: limit at 25th percentile, wait 60s
#           IF not filled: adjust to 50th percentile
#           IF not filled: market order (only after 2 minutes)
#
#         MEDIUM urgency (delta hedge):
#           IF spread < 2%: market order
#           ELSE: limit at 40th percentile, wait 15s, then market
#
#         HIGH urgency (exit):
#           Market order immediately
#
#         CRITICAL urgency (stop loss):
#           Market order immediately, retry up to 3 times
#
# 2. log_execution_quality(order_result: Dict, intended_price: float) -> None
#    - Calculate slippage: (fill_price - mid_price) / mid_price * 100
#    - Store in session for analytics
#    - Log: "Order filled at $X, mid was $Y, slippage: Z%"
```

#### 8.2 Integrate Smart Executor
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_executor.py`

Add `execute_smart_round()` method that wraps `_execute_single_round()` with smart routing. Existing `execute_rounds()` gains an optional `urgency` parameter.

#### 8.3 Track Slippage in Session
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_storage.py`

Add to session:
```python
'execution_stats': {
    'total_orders': 0,
    'total_slippage_pct': 0.0,
    'avg_slippage_pct': 0.0,
    'maker_fills': 0,
    'taker_fills': 0,
},
```

### Phase 8 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_smart_executor.py` | New file ~250 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_executor.py` | Add smart routing option |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_storage.py` | Add execution_stats |

---

## PHASE 9: Frontend Dashboard Upgrade

**Goal:** Display all the new data (live Greeks, MTM P&L, DTE phase, IV rank, delta hedge history) on the dashboard in real-time.  
**Impact:** Operational visibility — can't manage what you can't see.  
**Estimated Time:** 4-5 hours  
**Dependencies:** Phases 1-6  

### Sub-Tasks

#### 9.1 Greeks Dashboard Panel
- [x] **Create or modify:** `webui/frontend/src/components/ssrAlgo/SSRAlgoGreeksPanel.js`

Display:
- Four horizontal bars: Delta (green/red), Gamma (blue), Theta (positive=green), Vega (purple)
- Color coding: Delta bar turns yellow at 0.20, orange at 0.40, red at 0.80
- Numeric values with direction arrows
- Last updated timestamp

```
Delta:  ████████░░░░ +0.23 ↑  [WARN]
Gamma:  ██░░░░░░░░░ -0.08    [OK]
Theta:  ██████████░ +12.5    [GOOD — earning $12.50/day]
Vega:   ███░░░░░░░░ -340     [OK]
```

#### 9.2 Live P&L Panel
- [x] **Integrated into SSRAlgoGreeksPanel.js** — P&L section with total/unrealized/realized and per-leg breakdown

Already has `PnLCard` component with `unrealizedPnl` — wire it to `session.live_pnl`:
- Show unrealized P&L prominently (big number, green/red)
- Show realized P&L below it
- Show total P&L
- Per-leg breakdown expandable

#### 9.3 DTE Phase Indicator
- [x] **Added to:** SSRAlgoGreeksPanel.js (color-coded DTE phase badge) and metrics ribbon in SSRAlgoDashboardRefactored.js

Show current DTE phase as a badge:
```
DTE: 15 days | Phase: PEAK THETA 🟢 | "Let theta work"
```

Color scheme:
- EARLY LIFE (>21 DTE): Blue
- PEAK THETA (7-21 DTE): Green (money zone)
- GAMMA DANGER (3-7 DTE): Orange
- EXIT ZONE (<3 DTE): Red (flashing)

#### 9.4 IV Rank Display at Entry
- [x] **Added:** IV filter config UI in SSRAlgoConfigPanel.js (Algo Features section)

Show IV rank badge:
```
IV Rank: 65% [HIGH] 🟢   Skew: +3.2% (put)   Entry: RECOMMENDED
```

#### 9.5 Delta Hedge Activity Log
- [x] **Covered by:** SSRAlgoGreeksPanel.js shows hedge count badge + delta hedge ON status. Activity tab (SSRAlgoLogPanel) already captures all hedge events from backend logs.

Currently shows adjustment history. Extend to show ALL activity:
- Delta micro-hedges (with cost)
- Delta standard hedges
- Exit triggers
- DTE phase transitions

#### 9.6 Hook Updates for New Data
- [x] **Dashboard wiring:** SSRAlgoDashboardRefactored.js now reads `live_greeks`, `live_pnl`, `current_dte_phase` from session data in the metrics ribbon. SSRAlgoGreeksPanel.js auto-fetches from `/session/<id>/greeks` every 10s with session cached data as fallback.

#### 9.7 Auto-Refresh Greeks
- [x] **SSRAlgoGreeksPanel.js** auto-polls Greeks via `ssrAlgoService.getSessionGreeks()` every 10s. Falls back to session cached data when API unavailable.

### Phase 9 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE/MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoGreeksPanel.js` | Greeks visualization |
| MODIFY | `webui/frontend/src/components/ssrAlgo/shared/MetricCard.js` | Wire live P&L |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoStatusBanner.js` | DTE phase badge |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoSessionCard.js` | IV rank badge |
| MODIFY | `webui/frontend/src/components/ssrAlgo/SSRAlgoTriggerHistory.js` | Hedge activity |
| MODIFY | `webui/frontend/src/components/ssrAlgo/hooks/useSSRAlgoSession.js` | New state fields |
| MODIFY | `webui/frontend/src/components/ssrAlgo/hooks/useSSRAlgoMonitor.js` | Greeks refresh |

---

## PHASE 10: RV/IV Ratio, Roll Logic & Advanced Signals

**Goal:** Add advanced signals used by institutional desks — realized vs implied vol tracking, roll-to-next-expiry logic, and correlation monitoring.  
**Impact:** Institutional-grade decision-making.  
**Estimated Time:** 4-5 hours  
**Dependencies:** All previous phases  

### Sub-Tasks

#### 10.1 Realized vs Implied Volatility Tracker
- [x] **Create:** `webui/backend/routes/ssr_algo/ssr_algo_rv_tracker.py`

```python
# Track realized volatility (actual price movement) vs implied volatility
# rv_iv_ratio < 0.7: IV is expensive → GREAT for selling premium
# rv_iv_ratio > 1.2: Realized exceeds implied → DANGER for short gamma
#
# Calculate RV: standard deviation of log returns over rolling window
# Use 5-day RV and 20-day RV
# Compare to ATM IV from chain data
#
# Store history: keep last 30 data points for dashboard chart
```

#### 10.2 Roll-to-Next-Expiry Logic
- [x] **Add to:** `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py`

```python
# New method: execute_roll(session_id, next_expiry) -> Dict
# 
# WHEN: DTE <= 7 AND unrealized_pnl > 0
# WHAT:
#   1. Close all current positions (market orders)
#   2. Record realized P&L
#   3. Create NEW session at next_expiry with same config
#   4. Auto-start the new session
#   5. Link sessions: old_session['rolled_to'] = new_session_id
#   6. new_session['rolled_from'] = old_session_id
#   7. Carry forward realized P&L chain
# 
# This extends the profitable butterfly into the next cycle
# without a gap in theta collection
```

#### 10.3 Multi-Session Correlation Monitor
- [x] **Add to:** `webui/backend/routes/ssr_algo/ssr_algo_monitor.py`

```python
# If running BTC + ETH simultaneously:
# Track BTC-ETH price correlation (rolling 30 data points)
# If correlation > 0.95: WARN — portfolio risk is doubled
# If correlation < 0.60: GOOD — diversification benefit
# Log correlation changes to both sessions
```

#### 10.4 Session Analytics & Reporting
- [x] **Create:** `webui/backend/routes/ssr_algo/ssr_algo_analytics.py`

```python
# Per-session metrics:
# - Total P&L (realized + unrealized)
# - Sharpe ratio (daily returns / std dev)
# - Max drawdown (peak to trough)
# - Win rate (sessions closed profitably / total)
# - Average holding period
# - Average theta collected per day
# - Average slippage cost per adjustment
# - Delta hedge count vs full adjustment count
# - Premium collected vs premium paid (efficiency)
```

#### 10.5 Add Analytics API
- [x] **Modify:** `webui/backend/routes/ssr_algo/ssr_algo_api.py`

New endpoint:
```python
@ssr_algo_bp.route('/analytics', methods=['GET'])
@ssr_algo_bp.route('/session/<session_id>/analytics', methods=['GET'])
```

### Phase 10 Files Summary
| Action | File | What Changes |
|--------|------|-------------|
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_rv_tracker.py` | ~150 lines |
| CREATE | `webui/backend/routes/ssr_algo/ssr_algo_analytics.py` | ~200 lines |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py` | Add roll logic |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` | Correlation tracking |
| MODIFY | `webui/backend/routes/ssr_algo/ssr_algo_api.py` | Analytics endpoint |

---

## COMPLETE FILE INVENTORY

### New Files to Create (Total: 8)

| # | File | Phase | Lines (est) | Purpose |
|---|------|-------|-------------|---------|
| 1 | `webui/backend/routes/ssr_algo/ssr_algo_greeks.py` | Phase 1 | ~200 | Live Greeks + MTM P&L |
| 2 | `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py` | Phase 2 | ~250 | Profit target, stop loss, DTE exit |
| 3 | `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py` | Phase 3 | ~400 | Continuous delta management |
| 4 | `webui/backend/routes/ssr_algo/ssr_algo_vol_analyzer.py` | Phase 4 | ~200 | IV rank, skew, term structure |
| 5 | `webui/backend/routes/ssr_algo/ssr_algo_dte_manager.py` | Phase 6 | ~200 | DTE lifecycle phases |
| 6 | `webui/backend/routes/ssr_algo/ssr_algo_regime.py` | Phase 7 | ~150 | Market regime adaptation |
| 7 | `webui/backend/routes/ssr_algo/ssr_algo_smart_executor.py` | Phase 8 | ~250 | Smart order routing |
| 8 | `webui/backend/routes/ssr_algo/ssr_algo_rv_tracker.py` | Phase 10 | ~150 | RV/IV ratio tracking |
| 9 | `webui/backend/routes/ssr_algo/ssr_algo_analytics.py` | Phase 10 | ~200 | Session analytics |

### Existing Files to Modify

| # | File | Phases | Key Changes |
|---|------|--------|-------------|
| 1 | `ssr_algo_monitor.py` | 1,2,3,6,7 | Add Greeks fetch, exit checks, delta hedge, DTE phase, regime check to `_monitor_loop()` |
| 2 | `ssr_algo_storage.py` | 1,2,3,4 | Add new schema fields + helper methods |
| 3 | `ssr_algo_api.py` | 1,2,3,4,5,10 | New endpoints + modify create/start |
| 4 | `ssr_algo_executor.py` | 8 | Smart routing option |
| 5 | `ssr_algo_engine.py` | 7 | Accept regime-adjusted config |
| 6 | `__init__.py` | 1,2 | New imports |
| 7 | `ssrAlgoService.js` | 1,2 | New API methods |
| 8 | `SSRAlgoConfigPanel.js` | 2,3,4 | New config inputs |
| 9 | `SSRAlgoSessionCard.js` | 4,9 | IV rank display |
| 10 | Multiple frontend | 9 | Dashboard upgrade |

### Monitor Loop — Final Execution Order After All Phases

```python
def _monitor_loop(self):
    while not self._stop_event.is_set():
        # 0. Standard checks (paused? session exists? time window?)
        
        # 1. Get current price                          ← EXISTING
        
        # 2. DTE Phase check                            ← Phase 6
        #    → Determine EARLY/PEAK_THETA/GAMMA_DANGER/EXIT
        #    → Adjust thresholds for this cycle
        
        # 3. Live Greeks + MTM P&L                      ← Phase 1
        #    → Fetch exchange Greeks for all positions
        #    → Calculate portfolio net delta/gamma/theta/vega
        #    → Calculate mark-to-market unrealized P&L
        #    → Store in session
        
        # 4. Exit condition checks                      ← Phase 2
        #    → Profit target hit? → CLOSE ALL
        #    → Stop loss hit? → CLOSE ALL
        #    → DTE too low? → CLOSE ALL
        #    → If exit triggered → stop monitor, break
        
        # 5. Delta-based hedging                        ← Phase 3
        #    → |delta| > micro_threshold? → Roll untested OTM
        #    → |delta| > standard_threshold? → Roll ATM tested side
        #    → |delta| > emergency_threshold? → Full surgical adjustment ← Phase 5
        #    → Check cooldown, max hedges/day
        
        # 6. Regime check (every 5 min)                 ← Phase 7
        #    → Trending? → Tighten delta, reduce next entry size
        #    → Ranging? → Normal behavior
        
        # 7. Max loss zone backstop (FALLBACK)          ← EXISTING (modified Phase 3)
        #    → Only fires if delta hedging missed it
        #    → Longer dwell time (20 min if hedging enabled)
        #    → Full butterfly adjustment (last resort)
        
        # 8. Sleep 5 seconds                            ← EXISTING
```

---

## TOTAL ESTIMATED TIMELINE

| Phase | Description | Effort | Running Total |
|-------|-------------|--------|---------------|
| Phase 1 | Live Greeks + MTM P&L | 3-4 hours | 3-4 hours |
| Phase 2 | Exits (profit/loss/DTE) | 3-4 hours | 6-8 hours |
| Phase 3 | Delta hedging | 4-5 hours | 10-13 hours |
| Phase 4 | IV Rank filter | 2-3 hours | 12-16 hours |
| Phase 5 | Surgical rolls | 3-4 hours | 15-20 hours |
| Phase 6 | DTE lifecycle | 2-3 hours | 17-23 hours |
| Phase 7 | Regime detection | 2-3 hours | 19-26 hours |
| Phase 8 | Execution quality | 2-3 hours | 21-29 hours |
| Phase 9 | Frontend dashboard | 4-5 hours | 25-34 hours |
| Phase 10 | Advanced signals | 4-5 hours | 29-39 hours |

**Total: ~30-40 hours across 10 phases**

---

## PHASE COMPLETION NOTES

> **Instructions:** After completing each phase, append a section here with completion details.
> Format:
> ```
> ### Phase X — Completed YYYY-MM-DD
> - Files created: [list]
> - Files modified: [list]
> - Deviations from plan: [any changes made]
> - New bugs found: [any issues discovered]
> - Tests passed: [verification results]
> - Notes for next phase: [anything important]
> ```

### Phase 1 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_greeks.py` (~290 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_storage.py` — Added live_greeks, live_pnl, greeks_updated_at fields to create_session()
  - `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` — Added Greeks/MTM block in _monitor_loop() after price fetch
  - `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Added GET /session/<id>/greeks endpoint
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRGreeksFetcher exports
  - `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js` — Added getSessionGreeks() method
- Deviations from plan: None
- New bugs found: None
- Notes for next phase: live_greeks and live_pnl now populated every 5s in monitor loop. BSM fallback handles zero-Greeks from exchange.

### Phase 2 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py` (~260 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_storage.py` — Added exit_rules param + default to create_session()
  - `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` — Added exit condition checks after Greeks block (before payoff zone)
  - `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Added POST /session/<id>/exit endpoint + exit_rules in create
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRExitManager exports
  - `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js` — Added exitSession() + getSessionGreeks() methods
- Deviations from plan: Frontend config panel (2.6) deferred to Phase 9 UI redesign
- New bugs found: None
- Notes for next phase: Exit checks run every 5s cycle, priority order: DTE > Stop Loss > Profit Target. Manual exit via API works independently.

### Phase 3 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py` (~430 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_storage.py` — Added delta_hedge_config param, hedge tracking fields, update_position_leg(), close_position_leg() methods
  - `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` — Added delta hedge block after exit checks, backstop logic with 20min dwell when hedging enabled
  - `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Parse delta_hedge_config in create endpoint
- Deviations from plan: Frontend config UI deferred to Phase 9. Surgical adjustment (Phase 5) integrated into emergency_hedge method.
- Notes for next phase: Monitor loop now: price → Greeks → exits → delta hedge → payoff zone (backstop). Delta hedger uses micro/standard/emergency tiers.

### Phase 4 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_vol_analyzer.py` (~229 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_storage.py` — Added iv_filter_config param + default config to create_session()
  - `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Added IV pre-check before strike selection in start_session(), IV context added to preview_strikes() response, parse iv_filter_config in create
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRVolAnalyzer exports
- Deviations from plan: Frontend IV filter UI (4.4) deferred to Phase 9. Term structure analysis skipped (single expiry sufficient). Skew-based strike adjustment (adjust_strikes_for_skew) not implemented — regime adapter handles this better.
- Notes for next phase: IV filter is opt-in (enabled=False by default). When enabled, blocks entry if IV Rank < min_iv_rank. IV context included in preview_strikes response. Entry recommendation maps IV rank to confidence + size multiplier.

### Phase 6 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_dte_manager.py` (~204 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` — Added DTE phase check at top of monitor loop (before Greeks), passes DTE-adjusted threshold to delta hedger
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRDTEManager exports
- Deviations from plan: DTE thresholds slightly adjusted from plan (Early=0.75x, Peak=1.5x, Gamma=0.5x, Exit=0.25x). Phase transitions logged. DTE info included in session data via current_dte_phase field.
- Notes for next phase: DTE lifecycle phases dynamically adjust delta hedge thresholds and profit targets per cycle. should_close_far_otm_near_expiry() method available for Phase 5 integration.

### Phase 7 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_regime.py` (~211 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Added regime check before strike selection in start_session() (adjusts strike_config based on regime)
  - `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` — Added periodic regime check every 5 minutes, logs regime transitions, stores current_regime in session
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRRegimeAdapter exports
- Deviations from plan: Regime adapter uses lazy-loaded MarketRegimeDetector. Position size multiplier returned but not yet applied to auto_loop_rounds (would need frontend integration). Wing width multiplier applied to strike_config at entry.
- Notes for next phase: Regime check runs every 5 min in monitor loop. Four regimes: trending (0.5x size), high_vol (1.2x size), low_vol (0.5x size), ranging (1.0x standard).

### Phase 5 — Completed 2026-02-20
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_delta_hedger.py` — Added `execute_surgical_adjustment()` method (~150 lines). `execute_emergency_hedge()` now delegates to surgical adjustment. Surgical method closes only troubled side legs, opens new legs at current ATM, and updates position storage via `close_position_leg()` and `update_position_leg()`.
- Deviations from plan: No new file created — surgical adjustment integrated directly into delta_hedger as a method. close_position_leg() was already created in Phase 3.
- Notes for next phase: Surgical adjustment = 4-5 orders ($200-400) vs full butterfly = 8 orders ($600-1000). Emergency hedge now uses surgical by default.

### Phase 8 — Completed 2026-02-20
- Files created: `webui/backend/routes/ssr_algo/ssr_algo_smart_executor.py` (~340 lines)
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_storage.py` — Added execution_stats tracking fields
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRSmartExecutor exports
- Deviations from plan: Smart executor created as standalone module rather than modifying existing executor.py. Existing executor continues to work unchanged for backwards compatibility. Smart executor can be used by delta hedger and exit manager independently.
- Notes for next phase: Smart executor supports 4 urgency levels (low/medium/high/critical). Low urgency uses limit orders with wait+fallback. High/critical uses market immediately. Slippage tracking stored in session.execution_stats.

### Phase 9 — Completed 2026-02-20
- Files created: `webui/frontend/src/components/ssrAlgo/SSRAlgoGreeksPanel.js` (~310 lines)
- Files modified:
  - `webui/frontend/src/components/ssrAlgo/SSRAlgoDashboardRefactored.js` — Added 4th "Greeks" tab, wired live_greeks/live_pnl/current_dte_phase into metrics ribbon
  - `webui/frontend/src/components/ssrAlgo/SSRAlgoConfigPanel.js` — Added "Algo Features" collapsible section with Delta Hedge config, IV Filter config, and Exit Rules config UI
- Deviations from plan: Instead of modifying separate MetricCard/StatusBanner/SessionCard files, consolidated all Greeks/P&L/DTE/regime visualization into a single SSRAlgoGreeksPanel component integrated as a dashboard tab. Config for delta hedge, IV filter, and exit rules added to existing ConfigPanel rather than separate panels. Hook updates unnecessary — dashboard already polls sessions which include all new fields, and SSRAlgoGreeksPanel self-polls Greeks independently.
- New bugs found: None
- Notes for next phase: Dashboard now has 4 tabs (Positions, Greeks, Activity, History). Metrics ribbon shows delta, theta, P&L, and DTE phase inline. Config panel has 3 collapsible sections: Strike Settings, Safety & Limits, Algo Features.

---

## QUICK REFERENCE: EXISTING IMPORTS YOU'LL NEED

```python
# Chain service (for live Greeks, mark prices, IV)
from webui.backend.options_chain.chain_service import OptionsChainService

# Pricing engine (for Black-Scholes Greeks fallback)
from webui.backend.options_strategy.pricing_engine import OptionPricingEngine

# Regime detector (for market regime)
from webui.backend.options_strategy.regime_detector import MarketRegimeDetector

# Volatility analyzer (for IV rank)
from webui.backend.options_strategy.mv_straddle.volatility_analyzer import VolatilityAnalyzer

# Existing SSR Algo modules (relative imports within the package)
from .ssr_algo_engine import get_strike_selector, StrikeSelector, normalize_expiry_format
from .ssr_algo_executor import get_executor, SSRAutoLoopExecutor
from .ssr_algo_payoff import get_payoff_calculator, SSRPayoffCalculator
from .ssr_algo_storage import get_storage, SSRAlgoStorage
from .ssr_algo_monitor import start_session_monitor, stop_session_monitor

# Contract multipliers
# BTC: 0.001 (from ssr_algo_payoff.py CONTRACT_MULTIPLIERS)
# ETH: 0.01

# Symbol format: C-BTC-82000-06022026 or P-ETH-3500-06022026
# Parse with: ssr_algo_payoff.parse_symbol(symbol) → {type, underlying, strike, expiry}
```

---

**END OF DEVELOPMENT PLAN**

*This document is the single source of truth for SSR Algo development. Keep it updated.*

### Phase 10 — Completed 2026-02-20
- Files modified:
  - `webui/backend/routes/ssr_algo/ssr_algo_exit_manager.py` — Added `execute_roll()` method (~80 lines) for rolling to next expiry with session linking
  - `webui/backend/routes/ssr_algo/ssr_algo_monitor.py` — Added RV/IV tracker integration (record_price every ~5 min, compute snapshot every ~10 min) + multi-session correlation monitor (Pearson correlation across underlyings)
  - `webui/backend/routes/ssr_algo/ssr_algo_api.py` — Added 4 new endpoints: GET /analytics, GET /session/<id>/analytics, GET /session/<id>/rv_iv, POST /session/<id>/roll. Also added DTE/Greeks/PnL/Regime data to /status endpoint (Phase 6.3)
  - `webui/backend/routes/ssr_algo/__init__.py` — Added SSRRVTracker + SSRAnalytics exports
  - `webui/frontend/src/components/ssrAlgo/ssrAlgoService.js` — Added 4 new methods: getSessionAnalytics(), getAggregateAnalytics(), getSessionRvIv(), rollSession()
  - `webui/frontend/src/components/ssrAlgo/SSRAlgoSessionCard.js` — Added IV Rank badge (color-coded), DTE Phase badge (with flashing animation for exit zone), and live P&L badge (Phase 4.4)
- Files already created by prior AI: `ssr_algo_rv_tracker.py` (208 lines), `ssr_algo_analytics.py` (220 lines) — both fully implemented
- Deviations from plan: Correlation monitor uses Pearson correlation on rolling 30 price points from RV tracker's shared price history. RV tracking piggybacks on monitor loop counter rather than separate timer.
- Notes: All 10 phases are now COMPLETE. RV tracker starts accumulating data once monitor runs; needs ~5 min of data before first snapshot. Roll endpoint auto-creates new session with same config but does NOT auto-start it (user must start manually).

### Remaining Frontend Enhancements (Phase 4.4 / Phase 6.3) — Completed 2026-02-20
- `SSRAlgoSessionCard.js` — Added IV rank badge, DTE phase badge, live P&L badge as Chips in a new row between Session Info grid and Adjustment Trigger Zones
- `/status` API — Now returns current_dte_phase, live_greeks, live_pnl, current_regime per session
