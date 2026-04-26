# MMM Audit Master Index

**Primary plan:** `MMM_FULLSTACK_PHASEWISE_AUDIT_PLAN.md`  
**Last updated:** 2026-04-23

## Coverage counters

- Backend MMM files audited: `25 / 57`
- Backend MMM functions audited: `353 / 866`
- Frontend MMM files audited: `0 / 38`
- Backend MMM tests reviewed: `42 / 75`
- API endpoints contract-checked: `0 / 93`
- WebSocket events contract-checked: `0 / 37`

## Phase status

- [x] Phase 00 — Setup + manifests
- [x] Phase 01 — Foundations *(complete: `mmm_constants.py` + `mmm_config.py` + `mmm_dte_presets.py` + `mmm_telegram.py` + `mmm_websocket.py` + `mmm_activity.py` + `mmm_audit_log.py` + `mmm_audit_remark.py` + `mmm_analytics_storage.py` + `mmm_analytics_aggregator.py` + `mmm_performance.py` + `mmm_walkthrough.py`)*
- [x] Phase 02 — Persistence + P&L kernel *(complete: `mmm_state.py` + `mmm_storage.py` + `mmm_pnl_core.py` + `mmm_observer.py`)*
- [ ] Phase 03 — Execution primitives
- [ ] Phase 04 — Safety + guardians
- [ ] Phase 05 — Position lifecycle
- [ ] Phase 06 — Strategy overlays
- [ ] Phase 07 — Dispatch + whipsaw
- [ ] Phase 08 — Engine + monitor
- [ ] Phase 09 — API + backend wiring
- [ ] Phase 10 — Frontend data layer + sockets
- [ ] Phase 11 — Frontend panels
- [ ] Phase 12 — Tests + synthesis

## Findings rollup

| ID | Severity | Area | File/Function | Status | Notes |
|---|---|---|---|---|---|
| F00-P2-001 | P2 | Inventory baseline | Phase 00 manifests | Open | MMM package has 57 `mmm_*.py` modules + 1 support `__init__.py`; keep counters module-scoped |
| F00-P2-002 | P2 | Inventory baseline | Phase 00 manifests | Open | Frontend MMM has 38 production files + 3 frontend test files in same folder tree |
| F00-P2-003 | P2 | WS contract backlog | `MANIFEST_WS_EVENTS.md` | Open | WS parity currently: 25 OK, 12 BACKEND_ONLY, 1 FRONTEND_ONLY (`connect`) |
| F01-P3-001 | P3 | Maintainability | `mmm_constants.py` module conventions | Open | Decimal helper conventions are duplicated across modules; low-risk drift concern |
| F01-P1-002 | P1 | Control-plane truth drift | `mmm_config.py` (`whipsaw_smart_enabled`) vs runtime selector | Open | Config exposes hot control as binding gate, but runtime engine selection is keyed to `whipsaw_engine` only |
| F01-P2-004 | P2 | Operator UX consistency | `MMMSettingsDialog.js` + `MMMWhipsawCompareTab.js` | Open | Frontend guidance is internally inconsistent about whether `whipsaw_smart_enabled` is binding |
| F01-P3-005 | P3 | Maintainability | `mmm_config.py` strategy forbidden sets | Open | Large manual `_ADJUSTMENT_ENGINE_ONLY_PARAMS` list is currently consistent but drift-prone |
| F01-P1-006 | P1 | Validation integrity | `mmm_config.validate_params` + `mmm_api.update_session_params` | Open | Interdependency checks run on patch subset, allowing invalid merged session param states |
| F01-P2-007 | P2 | Create-time config safety | `mmm_config.validate_params` + `mmm_api.create_session_endpoint` | Open | Unknown keys are silently dropped during session creation; typo risk masked by defaults |
| F01-P3-008 | P3 | Maintainability | `mmm_state.derive_strategy_type` + `mmm_config` namespace normalizer | Open | Strategy identity normalization is duplicated across modules and can drift on future alias additions |
| F01-P1-009 | P1 | Control-plane integrity | `mmm_state.HOT_RELOAD_PARAMS` vs `mmm_config.PARAM_RULES` | **FIXED** | Added all 20 missing keys to PARAM_RULES with correct types/bounds/hot=True (2026-04-21) |
| F01-P1-010 | P1 | Storage decode resilience | `mmm_storage._row_to_session` | **FIXED** | list_sessions now iterates per-row with try/except — corrupt rows skipped, valid sessions returned (2026-04-21) |
| F01-P2-011 | P2 | Storage migration coupling | `mmm_storage.__init__` + `_migrate_from_json` | Open | Legacy JSON migration source is module-global and not derived from custom `db_path` |
| F01-P2-012 | P2 | Storage hot-reload coherence | `mmm_storage.save_session` | Open | Arbitration can persist newer DB params while leaving caller in-memory `session['params']` stale until next reload |
| F01-P1-013 | P1 | Trigger snapshot ratchet integrity | `mmm_trigger.update_trigger_snapshots` | Open | Cross-side active-key skip can block frozen snapshot updates when strike equals opposite side active strike |
| F01-P2-014 | P2 | Trigger data-gap handling | `mmm_trigger.evaluate_triggers` | Verified-no-issue | Already fixed (AUDIT FIX BUG4): each side validated independently; only skips when BOTH snapshots missing |
| F01-P2-015 | P2 | Reversal cooldown state integrity | `mmm_reversal.is_cooldown_active` + `activate_cooldown` | **FIXED** | Clear cooldown_active=False when cooldown_until is None, preventing permanent block on re-activation (2026-04-21) |
| F01-P2-018 | P2 | Close guard integrity (legacy original path) | `mmm_close_at_5.scan_closeable_positions` + `close_position` (chunk 01) | Open | Original close payload can be emitted with `_pos_id=None`; no fallback in-flight guard exists for original no-`_pos_id` path |
| F01-P1-020 | P1 | Close helper state integrity on ID mismatch | `mmm_close_at_5.close_position` + `_partial_close_position` + `_remove_closed_position` (chunk 02) | Open | If `_pos_id` is present on payload but missing in `positions[]`, partial fill path can under-track remaining lots (state can collapse to flat while exchange still has exposure) |
| F01-P2-021 | P2 | Market no-ID cleanup asymmetry | `mmm_close_at_5.close_position` market branch (chunk 02) | Open | No-ID market failure clears in-flight flag on pos-id path but leaves content-match `_being_closed` markers set until TTL, delaying retries |
| F01-P2-022 | P2 | Harvest asymmetry throughput contract drift | `mmm_harvester.py` + `mmm_monitor._process_harvest` | Open | M3 override returns `harvest_max_per_beat`, but runtime cap remains static session param, so extreme asymmetry does not increase harvest throughput |
| F01-P2-023 | P2 | Harvest in-flight guard integrity (no-ID) | `mmm_harvester.scan_harvestable_positions` | Open | In-flight suppression is keyed to truthy `_pos_id`; no-ID `_being_closed` entries can be re-selected for harvest |
| F01-P1-025 | P1 | Recycler cap integrity (`recycle_max_pct`) | `mmm_recycler.execute_lot_recycling` (chunk 01) | Open | Candidate selection can exceed `recycle_max_pct` when a single candidate lot size is larger than remaining cap allowance |
| F01-P2-026 | P2 | Recycler in-flight guard integrity (no-ID) | `mmm_recycler.select_recyclable_positions` (chunk 01) | Open | `_being_closed` suppression requires truthy `_pos_id`; no-ID entries can bypass selection guard |
| F01-P1-027 | P1 | Recycler success-path integrity under partial Phase A | `mmm_recycler.execute_lot_recycling` (chunk 02) | Open | Success path can report positive planned net gain while actual executed net-lot outcome is negative after partial Phase A |
| F01-P1-030 | P1 | Wind-down partial-fill state integrity | `mmm_wind_down.apply_lifo_removals` wiring via `mmm_monitor._process_wind_down_buyback` | Open | Partial exchange fills can still remove full requested lots from session state when close records are not trimmed to `filled_size` |
| F01-P2-028 | P2 | Recycler planned-vs-actual metric drift in returns | `mmm_recycler.execute_lot_recycling` (chunk 02) | Open | Success payload fields (`net_lot_gain`, `buyback_cost`, `viability_details`) can remain planned values after partial execution |
| F01-P2-031 | P2 | Wind-down status parity drift | `mmm_wind_down.get_wind_down_status` vs `is_wind_down_active` | Open | Regime-triggered wind-down can be active while status helper reports inactive when `wind_down_enabled=False` |
| F01-P2-034 | P2 | Whipsaw safety-path suppression drift | `mmm_safety.run_all_checks` + `mmm_whipsaw.whipsaw_decide` | Verified-no-issue | `session.pop()` self-resets flag each beat — no persistent skip possible |
| F01-P2-035 | P2 | Position-cap signaling drift | `mmm_safety.check_position_cap` vs `mmm_engine` hard cap | Open | Safety cap alert is based on `active_lots` while engine hard-cap enforcement is based on `total_lots` (active+frozen) |
| F01-P2-036 | P2 | Total-exposure telemetry component drift (reverse-inclusive) | `mmm_safety.check_total_exposure` | Open | Effective exposure includes reverse lots, but event payload omits reverse component; displayed components can fail to reconcile with enforced total |
| F01-P2-037 | P2 | Margin telemetry component drift (reverse-inclusive) | `mmm_safety.check_margin` | Open | Margin total includes reverse lots while CE/PE detail fields exclude reverse component, obscuring why warnings fire |
| F01-P3-024 | P3 | Harvest default/documentation consistency drift | `mmm_harvester` + `mmm_state` + `mmm_config` | Open | `active_lots` implementation, fallback defaults (0.6/0.8), and docs (`total_lots`) are not fully aligned |
| F01-P3-029 | P3 | Recycler partial-Phase-A test coverage gap | `mmm_recycler.execute_lot_recycling` tests | Open | No dedicated contract test for partial Phase A + successful Phase B with post-execution metric reconciliation |
| F01-P3-032 | P3 | Wind-down status/partial-fill coverage gap | `mmm_wind_down` + wind-down monitor path tests | Open | No direct tests for `get_wind_down_status` parity and no wind-down partial-fill lot-parity regression test |
| F01-P3-033 | P3 | DTE preset contract-doc drift | `mmm_dte_presets.build_straddle_adjustment_preset` | Open | Docstring still describes `2–12h` and `<2/>12` rejection while runtime/tests enforce `>=1h` and warning-only for `>24h` |
| F01-P3-038 | P3 | Reverse-inclusive safety coverage gap | `test_sealed_mmm_safety.py` + `test_mmm_safety.py` | Open | No dedicated assertions for `_reverse`-inclusive telemetry parity in `check_total_exposure` / `check_margin` |
| F01-P1-039 | P1 | Startup half-roll Telegram dispatch failure | `mmm_telegram.alert_half_roll_recovery_needed` + `mmm_monitor.start` | **FIXED** | Falls back to daemon thread with asyncio.run() when no event loop running (2026-04-21) |
| F01-P1-040 | P1 | Max-loss Telegram contract drift | `mmm_monitor._run_hard_stop_guard` + `mmm_straddle_roll_pure.execute_pure_straddle_roll` + `mmm_telegram.alert_max_loss_breach` | **FIXED** | Renamed `current_loss=` → `total_pnl=` in mmm_straddle_roll_pure.py (2026-04-21) |
| F01-P2-041 | P2 | Missing Telegram export used by pure-roll exhaustion path | `mmm_straddle_roll_pure` import of `send_telegram_message` vs `mmm_telegram` exports | **FIXED** | Added `async def send_telegram_message()` wrapper in mmm_telegram.py (2026-04-21) |
| F01-P3-042 | P3 | Telegram critical-path coverage gap | `mmm_telegram` tests/wiring | Open | No dedicated contracts for sync-wrapper scheduling, dedup semantics, or max-loss caller compatibility; regressions can pass green suites |
| F01-P3-016 | P3 | Shift threshold maintainability | `mmm_strike_shift.check_shift_needed` + `find_new_strike` | Open | Dynamic threshold derivation is duplicated across decision/filter paths; currently consistent but drift-prone |
| F01-P3-017 | P3 | Shift pre-scan test coverage gap | `mmm_strike_shift.pre_scan_shift_candidates` | Open | Pre-scan cache/proximity logic has no dedicated contract tests despite operational impact on shift latency and cache correctness |
| F01-P3-019 | P3 | Emergency market close coverage gap | `mmm_close_at_5.close_position` market branch (chunk 01) | Open | No direct sealed contracts for market-order branch semantics (success/partial/no-ID cleanup/pending verification) |
| F01-P3-043 | P3 | WebSocket payload mutation contract drift | `mmm_websocket._emit` | Open | `_emit` mutates caller payload (`data['timestamp']=...`) and can overwrite explicit callsite timestamps; low-risk but drift-prone for contract-sensitive consumers |
| F01-P2-044 | P2 | Event-log writer retry/backpressure resilience | `mmm_audit_log.MMMSessionEventLog._writer_loop` | **FIXED** | Aligned with trade-writer: added `batch.clear()`, `conn.close()`, `conn = None` on DB error path to prevent infinite retry and queue backpressure |
| F01-P2-045 | P2 | Analytics completion classification drift | `mmm_analytics_aggregator.get_aggregated_analytics` | Verified-no-issue | Audit description was incorrect — current code uses positive whitelist `in ('STOPPED','CLOSED','EXITED')`. No fix needed. |
| F01-P2-045b | P2 | Analytics `final_total_pnl` missing fees/perp/reverse | `mmm_analytics_storage.save_session_analytics` | **FIXED** | Was `realized+unrealized` only; changed to `compute_current_total_pnl(session)` which includes fees, perp, and reverse P&L |
| F01-P2-046 | P2 | Walkthrough trigger reconstruction fidelity | `mmm_walkthrough.generate_heartbeat_walkthrough` + monitor call order | Open | Trigger math uses post-update session snapshots in heartbeat narration, which can diverge from pre-decision trigger values used for actual adjustment decision |
| F01-P3-047 | P3 | Performance contract coverage gap | `mmm_performance` tests | Open | No dedicated sealed/direct tests found for performance scoring, classify-exit edge cases, or schema evolution paths |
| F02-P2-048 | P2 | Ledger migration trigger gap (zero-net legacy attribution) | `mmm_pnl_core._ensure_ledger` | Verified-no-issue | Line 93 already checks all attribution buckets — migration runs even for zero-net sessions with non-zero buckets |
| F02-P3-049 | P3 | Legacy reverse attribution migration drift | `mmm_pnl_core._migrate_existing_pnl` | Open | Legacy `pnl_reverse` is not explicitly migrated and can fall through as `adjustment` attribution via gap fallback |
| F02-P1-050 | P1 | Reverse-close attribution runtime failure | `mmm_pnl_core.compute_attribution` + `_sync_session_fields` + `get_pnl` | Verified-no-issue | `pnl_reverse` key is properly initialized in accumulator dict + defensive guard auto-creates missing keys |
| F02-P3-051 | P3 | Reverse-close sealed coverage gap | `test_sealed_mmm_pnl_core.py` | Open | No sealed contract currently exercises `record_close(source='reverse_close')` or validates reverse attribution/get_pnl stability |
| F02-P3-052 | P3 | Observer/guardian contract-doc drift | `mmm_observer.py` + `mmm_close_at_5.py` + `test_mmm_observer.py` | Open | Current architecture is split (observer=price/ledger, guardian=continuity/velocity) but comments/docs still claim observer runs 4 checks, creating debugging ambiguity |
| F02-P3-053 | P3 | Observer sealed/branch coverage gap | `test_mmm_observer.py` | Open | Observer has non-sealed tests only; no sealed contract and no `shift_recycle` branch assertions found |
| F03-P2-054 | P2 | Duplicate coid recovery blind spot | `mmm_executor.smart_execute` (`duplicate_client_order_id` branch) | **FIXED** | When open-order lookup finds nothing, breaks immediately with critical log + activity log instead of retrying — prevents duplicate placement (2026-04-21) |
| F03-P3-055 | P3 | Executor duplicate-recovery sealed coverage gap | `test_sealed_smart_execute.py` + executor test surface | Open | No direct sealed assertions found for `duplicate_client_order_id` recovery / open-order lookup behavior |
| F03-P1-056 | P1 | Continuation cancel-replace size drift | `mmm_executor.smart_execute` (continuation + cancel/replace branch) | Open | After `_current_order_size` is reduced for continuation, cancel-path fill math and replacement placement still use original `size`, risking over-placement and filled-size misreport under partial-fill races |
| F03-P2-057 | P2 | Execution-intent terminal closure gap on attempts exhaustion | `mmm_executor.smart_execute` (reprice exhausted path) | Open | `ORDER_INTENT` is written on placement, but attempts-exhausted failure path returns without a terminal `EXECUTION_INTENT` event, leaving potential dangling intent rows |
| F03-P3-058 | P3 | Smart-execute continuation/cancel branch coverage gap | `test_sealed_smart_execute.py` + executor sealed surface | Open | No direct sealed assertions found for continuation-order cancel/replace sizing or attempts-exhausted intent closure behavior |
| F03-P1-059 | P1 | Entry success contract accepts partial legs as full success | `mmm_executor.execute_entry` (chunk 03) | Open | `all_success` is gated on boolean `success` only, so partial-fill legs can still produce entry success with asymmetric exposure |
| F03-P1-060 | P1 | Entry rollback lot-size normalization gap | `mmm_executor.execute_entry` (CE rollback branch, chunk 03) | Open | Rollback buy uses requested `lots` instead of successful leg `filled_size`, increasing reject/escalation/orphan risk when successful leg was partial |
| F03-P2-061 | P2 | Emergency fill-quantity verification fallback is optimistic | `mmm_executor.emergency_execute` (filled-state `unfilled_size` handling) | Open | Missing/unparseable `unfilled_size` falls back to assumed full fill, which can overstate actual closure under exchange payload races |
| F03-P3-062 | P3 | Emergency/entry sealed coverage + remediation-doc drift | `test_sealed_execution_risk_remediation.py` + executor test surface | Open | Remediation header claims H-1/H-3 for executor but implemented body is H-2 only; no direct `execute_entry` branch tests found |
| F03-P1-063 | P1 | Post-only buy retry repricing contradiction | `mmm_executor._place_limit_order` (chunk 04) | Open | Buy retry path sets `current_price=best_ask` while keeping `post_only=True`, which can repeatedly cross/reject and exhaust retries on close/rollback paths |
| F03-P1-066 | P1 | Cancel/failure reconciliation gap on attempts exhaustion | `mmm_executor._cancel_order` + `smart_execute` attempts-exhausted cancel path (chunk 05) | Open | `_cancel_order` returns false on 400 (“likely already filled/cancelled”), but attempts-exhausted path returns failure without final status reconciliation, enabling false-failure / duplicate-retry risk |
| F03-P2-064 | P2 | Adjustment recovery lot normalization drift | `mmm_executor.execute_adjustment` (chunk 04) | Open | Recovery re-sell uses requested `close_lots` instead of actual close `filled_size`; partial-close/open-fail scenarios can over-restore lots (latent helper risk) |
| F03-P3-065 | P3 | Chunk-04 executor branch coverage gap | `_place_limit_order` / `execute_adjustment` test surface | Open | No direct sealed contracts for post-only buy-retry branch or `MMMExecutor.execute_adjustment` recovery semantics |
| F03-P3-067 | P3 | Chunk-05 helper branch coverage gap | `_cancel_order` / `_wait_for_fill` / `get_executor` test surface | Open | No direct sealed contracts for cancel-400 reconciliation, wait-loop dead/timeout helper transitions, or singleton accessor concurrency/idempotence |
| F03-P1-068 | P1 | Manual-selection expiry/underlying contract blind spot | `mmm_initializer.validate_manual_selection` + `mmm_api` init-fresh symbol persistence (chunk 01 boundary) | Open | Validation path accepts expiry/underlying contract but does not enforce CE/PE symbol-expiry/underlying parity before symbols are persisted into session state |
| F03-P3-069 | P3 | Initializer core contract coverage gap | `mmm_initializer` core surfaces (`normalize_expiry`, `preview_*`, `validate_manual_selection`) | Open | No direct sealed contracts for initializer parsing/selection/manual-validation branches; current coverage is primarily consumer-level and mocked |
| F03-P2-070 | P2 | Auto-mode sellability gate bypass in strike ranking flow | `mmm_initializer._rank_strikes` + `MMMConfigPanel` preview→init-fresh flow | Open | Zero-bid candidates are penalty-ranked (not hard-rejected), and auto mode can init/start directly from preview output without manual validate-selection gate |
| F03-P3-071 | P3 | Initializer chunk-02 helper contract coverage gap | `build_symbol` / `_extract_ticker_data` / `check_liquidity` / premium helper methods | Open | No direct sealed contracts found for chunk-02 helper surfaces; regressions can hide behind mocked consumer tests |
| F03-P2-072 | P2 | Pending-order partial-fill recovery gap | `mmm_pending_orders.check_and_resolve_pending` | Open | Partially filled orders that later cancel/expire are cleared without recording executed lots because the guard only handles all-or-nothing filled/dead states and never inspects `filled_size` / `unfilled_size` |
| F03-P3-073 | P3 | Pending-order partial-recovery coverage gap | `test_sealed_mmm_pending_orders.py` | Open | No sealed contract exercises partial-fill terminal states or callback-failure idempotence in the pending-order recovery path; the suite only covers full fill/open/dead/error cases |

## Next action

Continue Phase 03 execution-primitives audit with `webui/backend/routes/mmm/mmm_trigger.py` chunk 01.
