# File Audit Report — `mmm_telegram.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_telegram.py`
- Chunk: `1` (`lines 1–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–546`
- Functions/methods in range:
  - `_get_telegram_credentials`
  - `_get_notifier`
  - `_should_send`
  - `_send_async`
  - `alert_margin_tier_change`
  - `alert_half_roll_detected`
  - `_alert_half_roll_detected_async`
  - `alert_half_roll_recovery_needed`
  - `_alert_half_roll_recovery_needed_async`
  - `alert_straddle_roll_executed`
  - `_alert_straddle_roll_executed_async`
  - `alert_emergency_close`
  - `alert_session_stopped`
  - `alert_rapid_check_activated`
  - `alert_max_loss_breach`
  - `alert_guardian_violation`
  - `alert_guardian_healed`
  - `alert_stale_monitor`
  - `alert_ghost_positions_growing`
  - `alert_both_sides_up`
  - `alert_both_sides_closed_awake`
  - `alert_offhours_unhedged_stop`
  - `alert_active_hours_unhedged_pause`
  - `alert_god_correction`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_get_telegram_credentials` | 37–56 | config telegram creds | none | config load + debug logs | none direct | PASS |
| `_get_notifier` | 59–82 | module singleton + creds | `_notifier_instance` | imports notifier, lazy init | none direct | PASS |
| `_should_send` | 85–92 | `_last_sent` | `_last_sent[key]` | dedup timing gate | none direct | PASS |
| `_send_async` | 95–115 | dedup gate + notifier | none | async Telegram send/logging | none direct | PASS |
| `alert_margin_tier_change` | 121–141 | tier/utilization values | none | emits Markdown alert via `_send_async` | integration via monitor tests | PASS |
| `alert_half_roll_detected` | 154–159 | params only | none | sync wrapper uses `asyncio.create_task` | none direct | PASS |
| `_alert_half_roll_detected_async` | 162–180 | stage/session data | none | emits half-roll alert | none direct | PASS |
| `alert_half_roll_recovery_needed` | 183–188 | params only | none | sync wrapper uses `asyncio.create_task` | none direct | RISK |
| `_alert_half_roll_recovery_needed_async` | 191–202 | state/session data | none | emits startup recovery alert | none direct | PASS |
| `alert_straddle_roll_executed` | 205–219 | params only | none | sync wrapper uses `asyncio.create_task` | none direct | PASS |
| `_alert_straddle_roll_executed_async` | 222–241 | roll info | none | emits roll-success alert | none direct | PASS |
| `alert_emergency_close` | 245–262 | reason/tier/utilization | none | emits emergency close alert | integration via monitor tests | PASS |
| `alert_session_stopped` | 266–280 | reason/session | none | emits stop alert | integration via monitor tests | PASS |
| `alert_rapid_check_activated` | 283–298 | trigger reason/utilization | none | emits rapid-check alert | integration via monitor tests | PASS |
| `alert_max_loss_breach` | 301–317 | pnl/loss values | none | emits max-loss alert | patched in `test_sealed_straddle_roll_pure.py` | RISK |
| `alert_guardian_violation` | 320–334 | violations list | none | emits guardian pause alert | none direct | PASS |
| `alert_guardian_healed` | 337–349 | pause reason | none | emits guardian resume alert | none direct | PASS |
| `alert_stale_monitor` | 352–377 | session/gen/context | none | emits stale-monitor emergency alert | none direct | PASS |
| `alert_ghost_positions_growing` | 380–404 | side/strike/lots | none | emits ghost-position growth alert | none direct | PASS |
| `alert_both_sides_up` | 407–429 | CE/PE values | none | emits both-sides-up pause alert | integration via monitor flow | PASS |
| `alert_both_sides_closed_awake` | 432–453 | session/pnl | none | emits awake-hours info alert | none direct | PASS |
| `alert_offhours_unhedged_stop` | 456–479 | sides/lots/pnl | none | emits off-hours stop alert | `test_active_hours_shutdown.py` | PASS |
| `alert_active_hours_unhedged_pause` | 482–520 | sides/lots/pnl/details | none | emits active-hours pause alert | `test_active_hours_shutdown.py` | PASS |
| `alert_god_correction` | 523–546 | drift/inactivity stats | none | emits god-layer correction alert | none direct | PASS |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-039 | P1 | `alert_half_roll_recovery_needed` wiring | Sync wrapper uses `asyncio.create_task(...)` and swallows exceptions (`mmm_telegram.py:183–188`); it is called from sync startup path (`mmm_monitor.py:307–309`). Runtime probe from sync context produced `RuntimeError: no running event loop` + `coroutine ... was never awaited`. | On backend restart with half-roll state, the session is force-stopped but the critical Telegram recovery alert can silently fail, delaying manual intervention on real-money exposure. | Introduce a sync-safe scheduling helper (e.g., `schedule_telegram_coro`) that uses running loop when present and `run_coroutine_threadsafe` (or dedicated notifier thread queue) when called from sync context with no loop. |
| F01-P1-040 | P1 | `alert_max_loss_breach` caller contract | Hard-stop guard thread calls async function without await/scheduling (`mmm_monitor.py:10419–10427`); pure-roll hard-stop path calls with wrong keyword `current_loss` (`mmm_straddle_roll_pure.py:896–899`). Probe confirmed `TypeError: unexpected keyword argument 'current_loss'`. | Emergency max-loss notifications can be silently dropped in exactly the highest-risk scenarios (independent guard breach or pure-roll hard stop), reducing operator visibility during critical loss events. | Normalize both call sites to the declared signature `(session_id, total_pnl, max_loss)` and enforce actual coroutine execution in guard thread via explicit event-loop scheduling. Add regression tests covering both call paths. |
| F01-P2-041 | P2 | Gate-6 exhaustion alert integration | `mmm_straddle_roll_pure.py` imports `send_telegram_message` (`line 365`) and schedules it (`lines 368–379`), but `mmm_telegram.py` exposes no such symbol (`lines 1–546`). Probe confirmed `ImportError: cannot import name 'send_telegram_message'`. | When max rolls are exhausted (`max_rolls_exhausted`), the intended operator Telegram alert is never sent; this can hide transition into hard-stop-only mode. | Replace import with an existing exported alert function (or add a stable `send_telegram_message` shim in `mmm_telegram.py` delegating to `_send_async`). |
| F01-P3-042 | P3 | Telegram alert contract coverage | Test search shows direct coverage only for active/off-hours messages (`test_active_hours_shutdown.py`) and one patched symbol in pure-roll tests (`test_sealed_straddle_roll_pure.py:273`); no dedicated contracts for startup wrappers, dedup semantics, or hard-stop max-loss caller compatibility. | Async/sync scheduling regressions and signature drift can reappear undetected despite green suites. | Add a dedicated `test_sealed_mmm_telegram.py` covering: dedup behavior, sync-wrapper scheduling in no-loop context, async send success/failure paths, and callsite compatibility contracts for max-loss and half-roll startup alerts. |

## Wiring impact

- Upstream callers reviewed:
  - `mmm_monitor.py` (tier, emergency close, session stop, rapid-check, max-loss, stale-monitor, both-sides alerts, god-layer alert)
  - `mmm_guardian.py` (stale monitor + guardian violation alerts)
  - `mmm_straddle_adjustment.py` (half-roll + roll-success alerts)
  - `mmm_straddle_roll_pure.py` (half-roll + roll-success + max-loss/exhaustion alerts)
- Downstream notifier path:
  - `webui/backend/services/notifications.py::TelegramNotifier._send_message`
- Contract risk propagation:
  - Findings are mostly integration-path faults (scheduler/context/signature/export mismatch) rather than message-template logic defects.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_active_hours_shutdown.py`
  - `webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py`
- Test execution performed:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_active_hours_shutdown.py webui/backend/routes/mmm/tests/test_sealed_straddle_roll_pure.py -q` → `51 passed`.
- Runtime probes executed:
  - Sync-call probe for `alert_half_roll_recovery_needed` captured `RuntimeError: no running event loop` + unawaited-coroutine warning.
  - Signature probe for `alert_max_loss_breach(..., current_loss=...)` raised `TypeError`.
  - Import probe for `send_telegram_message` from `mmm_telegram` raised `ImportError`.

## Chunk verdict

- **RISK**
- File status:
  - `mmm_telegram.py` audit complete (single chunk).
- Next file dependency note:
  - Continue Phase 01 foundations with `webui/backend/routes/mmm/mmm_websocket.py` chunk 01.
