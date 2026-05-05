# AI Context: Grid Bot RANGE Mode

**Author:** Claude Sonnet 4.6  
**Date:** 2026-05-05  
**Commits:** `7e7b22199` (feature), `691edaba2` (review fixes)  
**Branch:** SSR

---

## What RANGE Mode Is

RANGE mode is a third grid bot operating mode (alongside LONG and SHORT) where the bot **automatically switches between LONG and SHORT** based on the current market price relative to a user-defined **anchor price**.

```
Price > anchor + hysteresis  →  SHORT grid runs (sells rallies, buys drops)
Price < anchor - hysteresis  →  LONG grid runs  (buys dips, sells bounces)
Price outside [lower, upper] →  Both grids stop (out of range)
```

### Why the handoff is always clean

When price moves from SHORT zone back to the anchor:
- SHORT entries at 76,000; 75,500 have TPs at 75,500; 75,000 respectively
- Price must cross 75,500 (TP hits) then 75,000 (TP hits) before reaching the anchor
- By the time price reaches `anchor - hysteresis`, **all SHORT TPs have already executed**

Same logic in reverse for LONG. This is a mathematical guarantee of the grid TP structure, not a software feature.

### The natural gap prevents anchor whipsaw

- First SHORT entry: `anchor + step` (e.g., 75,500)
- First LONG entry: `anchor - step` (e.g., 74,500)
- The hysteresis band (e.g., ±200) sits inside this 1,000-USDT gap

No entries are placed within `anchor ± step` of the anchor, so price oscillation near the anchor never causes double-entry.

---

## Architecture: How It Works

RANGE mode uses **no new bot processes**. It reuses the existing dual-instance architecture (BTCUSD_LONG + BTCUSD_SHORT run simultaneously) and controls which one trades via the existing Guardian GO/STOP signal.

```
Config (dual_mode.enabled=true)
    ↓
GuardianBot (BTCUSD_LONG)        GuardianBot (BTCUSD_SHORT)
    ↓                                 ↓
RiskDecisionEngine                RiskDecisionEngine
    ↓                                 ↓
RegimeDetector (shared logic,     RegimeDetector (same logic,
 independent state — but always    always same result)
 computes same result)
    ↓                                 ↓
Check 7: if regime ≠ LONG → STOP  Check 7: if regime ≠ SHORT → STOP
    ↓                                 ↓
EventStore (BTCUSD_LONG.db)       EventStore (BTCUSD_SHORT.db)
    ↓                                 ↓
GridBot BTCUSD_LONG               GridBot BTCUSD_SHORT
```

Both Guardian instances independently compute the same regime because they observe the same LTP and apply the same rules from the same config. Their `RegimeDetector` instances are not shared — they each maintain local state — but they converge to identical results.

---

## Files Changed

### New file
| File | Purpose |
|------|---------|
| `bot/guardian/engine/regime_detector.py` | Stateful LONG/SHORT/OOB regime computation with hysteresis |

### Modified files
| File | What changed |
|------|-------------|
| `config/models.py` | Added `GridMode.RANGE` enum value; new `DualModeConfig` Pydantic model; added `dual_mode: Optional[DualModeConfig]` to `RootConfig` |
| `config/env_mapping.py` | Added `GRIDBOT_ANCHOR → dual_mode.anchor`, `GRIDBOT_HYSTERESIS → dual_mode.hysteresis` |
| `config.yaml` | Added `dual_mode` section (default: `enabled: false`) |
| `bot/guardian/core/guardian_bot.py` | Calls `risk_decision_engine.set_instance_mode(self.instance_name)` after engine init |
| `bot/guardian/engine/risk_decision_engine.py` | Added Check 7 (regime gate), `set_instance_mode()`, `_init_regime_detector()`, `_check_regime()`; `_on_config_changed()` now re-inits detector on hot-reload |
| `webui/backend/routes/grid_mode.py` | POST `/api/bot/grid-mode` accepts `RANGE`; `_activate_range_mode()` writes both instance configs + `dual_mode` block + optional PM2 restart |
| `webui/frontend/src/components/ConfigPanel.js` | 3-button toggle (LONG/SHORT/RANGE); RANGE shows Anchor + Hysteresis fields + dual-zone summary chip |

---

## Key Classes and Methods

### `RegimeDetector` (`bot/guardian/engine/regime_detector.py`)

```python
RegimeDetector(anchor, lower, upper, hysteresis)
    .update(ltp: float) -> str   # call each Guardian cycle; returns REGIME_LONG/SHORT/OOB
    .current_regime -> str       # last computed regime
```

**Transition rules:**
- `LONG → SHORT`: only when `ltp > anchor + hysteresis`
- `SHORT → LONG`: only when `ltp < anchor - hysteresis`
- `* → OOB`: when `ltp < lower` or `ltp > upper` (no hysteresis — hard boundary)
- `OOB → *`: re-entry uses raw anchor as divider (no extra hysteresis)
- First observation: `ltp > anchor → SHORT`, else `LONG`

**Invariant:** Both Guardian instances (LONG and SHORT) instantiate `RegimeDetector` independently. Because they see the same LTP stream and apply the same rules, they always compute the same current regime. No inter-process communication needed.

### `GuardianRiskDecisionEngine` — additions (`bot/guardian/engine/risk_decision_engine.py`)

```python
engine.set_instance_mode(instance_name: str)
# Must be called after __init__ and before run_continuous_monitoring()
# instance_name: e.g. "BTCUSD_LONG" — parsed via config.loader.parse_instance_name()
```

**Check 7 in `_generate_signal()`** (runs after all existing safety checks):
```python
if self._regime_detector is not None:
    regime_stop = self._check_regime()
    if regime_stop is not None:
        return regime_stop   # STOP signal with reason
```

`_check_regime()` resolves instance_mode as: `self._instance_mode or config.bot.mode`. `_instance_mode` is always set via `set_instance_mode()` when RANGE is active.

**Hot-reload:** `_on_config_changed()` calls `_init_regime_detector()` after config reload. This means enabling RANGE mode via the WebUI takes effect on the live Guardian **without a restart**.

`_init_regime_detector()` always sets `_regime_detector = None` first, so toggling `dual_mode.enabled` off also takes effect immediately.

---

## Config Schema

### `config.yaml` — `dual_mode` section

```yaml
dual_mode:
  enabled: false          # Set to true to activate RANGE mode
  symbol: BTCUSD
  anchor: 75000           # Price boundary between LONG and SHORT zones
  lower: 73000            # OOB floor — both bots stop below this
  upper: 77000            # OOB ceiling — both bots stop above this
  step: 500               # Grid step size (same for both zones)
  lot_size: 5             # Lot size (same for both zones)
  hysteresis: 200         # Price delta past anchor before regime switches
  max_open_positions: 20  # Per zone
```

### Auto-derived instance configs

When RANGE mode is activated via the UI or API, `_activate_range_mode()` writes these to `instances`:

```yaml
instances:
  BTCUSD_LONG:
    enabled: true
    grid.geometry:
      lower: 73000          # dual_mode.lower
      upper: 75000          # dual_mode.anchor  ← anchor is LONG's ceiling
      reference: 74000      # midpoint of LONG zone
  BTCUSD_SHORT:
    enabled: true
    grid.geometry:
      lower: 75000          # dual_mode.anchor  ← anchor is SHORT's floor
      upper: 77000          # dual_mode.upper
      reference: 76000      # midpoint of SHORT zone
```

The existing `is_within_bounds()` check in `GridEngine` already prevents entries outside each zone's bounds. The regime gate in the Guardian adds an extra layer of control.

---

## API

### `POST /api/bot/grid-mode`

```json
{
  "mode": "RANGE",
  "symbol": "BTCUSD",
  "anchor": 75000,
  "lower": 73000,
  "upper": 77000,
  "step": 500,
  "lot_size": 5,
  "hysteresis": 200,
  "max_open_positions": 20,
  "product_id": 27,
  "auto_restart": true
}
```

**Validation:** `lower < anchor < upper` is enforced server-side.

**Response:**
```json
{
  "success": true,
  "mode": "RANGE",
  "changed": true,
  "anchor": 75000,
  "lower": 73000,
  "upper": 77000,
  "hysteresis": 200,
  "restart": { "success": true, "message": "Both instances restarted via PM2" }
}
```

---

## How to Start RANGE Mode

1. In the WebUI Config panel → Trading Direction → select **↕ RANGE**
2. Set: Lower Bound, Anchor Price, Upper Bound, Step, Lot Size, Hysteresis
3. Save — config is written, both instance configs auto-generated
4. If PM2 is enabled, both instances restart automatically
5. Start (or restart) the Guardian for each instance:
   ```bash
   python start_guardian.py --instance BTCUSD_LONG
   python start_guardian.py --instance BTCUSD_SHORT
   ```

---

## Invariants — DO NOT BREAK

1. **Anchor must be strictly between lower and upper.** `RegimeDetector.__init__` enforces this and raises `ValueError`.

2. **`_init_regime_detector()` must always reset `_regime_detector = None` first.** If this reset is removed, toggling `dual_mode.enabled = false` via the WebUI will leave the old detector running.

3. **`set_instance_mode()` must be called before `run_continuous_monitoring()`.** It is called in `guardian_bot.py` immediately after the engine is created and before `set_components()`.

4. **`_on_config_changed()` must call `self._init_regime_detector()` after config reload.** This is the hot-reload path. Without it, enabling RANGE via the WebUI has no effect on the live Guardian process.

5. **The existing three-layer stale-monitor guard (from the 2026-03-24 incident) is untouched.** RANGE mode only modifies the Guardian's GO/STOP publishing, not the GridBot's internal safeguards.

6. **Both LONG and SHORT instances remain fully independent.** They have separate DBs, separate actors, separate Guardians. RANGE mode only adds a regime gate to each Guardian. It does not create shared state between instances.

7. **LONG and SHORT zones must not overlap.** The anchor is simultaneously `LONG.grid.upper` and `SHORT.grid.lower`. Any code that modifies instance bounds must preserve `LONG.upper == SHORT.lower == anchor`.

---

## Known Limitations

- **Extra `fetch_ticker()` call:** `_check_regime()` calls `position_monitor.get_current_price()` (a REST API call) each Guardian cycle. The existing cycle already makes 2–3 exchange calls; this adds one more. Impact: negligible at 5-second intervals. Future optimization: pass mark price from already-fetched position data.

- **RANGE mode and RSI:** RSI safety is disabled on both instances when RANGE mode is activated (`rsi.enabled: false` in instance safety config). RSI thresholds for LONG mode (stop at oversold) conflict with SHORT mode operations when both run on the same symbol. Re-enabling RSI in RANGE mode requires per-zone threshold tuning.

- **No position close on regime switch:** When the regime changes (e.g., LONG → SHORT), the stopped instance cancels its pending entry order but keeps existing open positions. Their TPs remain active and will fill naturally. No forced close is performed. This is correct by design (see "Why the handoff is always clean" above).

- **Startup with existing positions:** If RANGE mode is started with open positions from a prior standalone LONG or SHORT session, those positions are not managed by RANGE mode. Start RANGE mode with a clean slate (no open positions on the exchange).
