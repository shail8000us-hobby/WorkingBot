# MMM Audit Master Index

**Primary plan:** `MMM_FULLSTACK_PHASEWISE_AUDIT_PLAN.md`  
**Last updated:** 2026-04-20

## Coverage counters

- Backend MMM files audited: `6 / 57`
- Backend MMM functions audited: `61 / 866`
- Frontend MMM files audited: `0 / 38`
- Backend MMM tests reviewed: `17 / 75`
- API endpoints contract-checked: `0 / 93`
- WebSocket events contract-checked: `0 / 37`

## Phase status

- [x] Phase 00 — Setup + manifests
- [ ] Phase 01 — Foundations *(in progress: `mmm_constants.py` + `mmm_config.py` chunks 01/02 + `mmm_state.py` chunks 01/02 + `mmm_storage.py` chunks 01/02 + `mmm_trigger.py` chunks 01/02 + `mmm_reversal.py` chunk 01 audited; `mmm_state.py` + `mmm_storage.py` + `mmm_trigger.py` + `mmm_reversal.py` files complete)*
- [ ] Phase 02 — Persistence + P&L kernel
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
| F01-P1-009 | P1 | Control-plane integrity | `mmm_state.HOT_RELOAD_PARAMS` vs `mmm_config.PARAM_RULES` | Open | State marks 20 keys hot that config validation does not declare; PATCH validation silently drops those keys |
| F01-P1-010 | P1 | Storage decode resilience | `mmm_storage._row_to_session` | Open | Single malformed JSON row can cause `get_session` miss and `list_sessions` empty-list collapse |
| F01-P2-011 | P2 | Storage migration coupling | `mmm_storage.__init__` + `_migrate_from_json` | Open | Legacy JSON migration source is module-global and not derived from custom `db_path` |
| F01-P2-012 | P2 | Storage hot-reload coherence | `mmm_storage.save_session` | Open | Arbitration can persist newer DB params while leaving caller in-memory `session['params']` stale until next reload |
| F01-P1-013 | P1 | Trigger snapshot ratchet integrity | `mmm_trigger.update_trigger_snapshots` | Open | Cross-side active-key skip can block frozen snapshot updates when strike equals opposite side active strike |
| F01-P2-014 | P2 | Trigger data-gap handling | `mmm_trigger.evaluate_triggers` | Open | Missing snapshot on one side suppresses both sides (`OUTCOME_NONE`), creating one-side blindness under partial-data states |
| F01-P2-015 | P2 | Reversal cooldown state integrity | `mmm_reversal.is_cooldown_active` + `activate_cooldown` | Open | `cooldown_active=True` with missing `cooldown_until` can become a sticky invalid state that blocks future cooldown activation |

## Next action

Continue Phase 01 with `webui/backend/routes/mmm/mmm_strike_shift.py` chunk 01 and publish the next chunk report.
