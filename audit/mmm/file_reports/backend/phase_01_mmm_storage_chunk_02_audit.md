# File Audit Report — `mmm_storage.py` (chunk 02)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_storage.py`
- Chunk: `2` (`lines 451–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–1255`
- Functions/methods in range:
  - `_backfill_session_side_premiums` (remainder + complete coverage)
  - `_correct_fillsync_double_booking`
  - `_calculate_checksum`
  - `_calculate_checksum_v2`
  - `_validate_checksum`
  - `save_session`
  - `get_session`
  - `list_sessions`
  - `delete_session`
  - `update_session`
  - `get_active_session_ids`
  - `list_session_summaries`
  - `_get_side_premium`
  - `_row_to_summary_fallback`
  - `get_session_count`
  - `get_storage`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_backfill_session_side_premiums` | 439–467 (complete by chunk 02) | `adjustment_history`, side entry fills, lots | `ce_premium_collected`, `pe_premium_collected` | in-memory normalization on load | `test_sealed_mmm_storage.py` (indirect), `test_mmm_summary_preset_source.py` (summary paths) | PASS |
| `_correct_fillsync_double_booking` | 468–512 | legacy fill bookkeeping keys | `realized_pnl`, correction flags/amounts | retroactive mutation to canonicalize pre-ledger sessions | no direct sealed test located | PASS |
| `_calculate_checksum` / `_calculate_checksum_v2` | 514–567 | canonical + legacy checksum fields | checksum strings | none | `tests/mmm/test_reliability.py` (direct for `_calculate_checksum`) | PASS |
| `_validate_checksum` | 569–609 | checksum fields | boolean verdict only | warning logs | `tests/mmm/test_reliability.py` (direct) | PASS |
| `save_session` | 612–741 | caller session + existing row snapshot (`params_json`, `updated_at`) | upserted row + caller metadata fields | transactional save, hot-reload arbitration | `test_sealed_mmm_storage.py` (core save contracts) | RISK |
| `get_session` | 743–772 | `session_id` row | returned session dict | logs and graceful fail on DB errors | `test_sealed_mmm_storage.py` | PASS |
| `list_sessions` | 775–802 | all rows or active subset | list of session dicts | logs and graceful fail | `test_sealed_mmm_storage.py`, `test_mmm_integration.py` | PASS |
| `delete_session` | 804–828 | `session_id` | row deletion + bool result | DB delete | `test_sealed_mmm_storage.py`, `test_mmm_integration.py` | PASS |
| `update_session` | 831–938 | target row + update patch | merged row + recomputed checksums | transactional partial update with strategy immutability guard | `test_mmm_strategy_type_identity.py` (indirect via API/storage contract) | PASS |
| `get_active_session_ids` | 940–952 | status-filtered IDs | list of IDs | none | indirect only | PASS |
| `list_session_summaries` | 954–1105 | SQL json_extract fields from `data_json` + `params_json` | compact summary list | primary fast-path + fallback to full list | `test_mmm_summary_preset_source.py` | PASS |
| `_get_side_premium` | 1107–1149 | summary-row fields + history JSON | derived side premium | none | `test_mmm_summary_preset_source.py` (indirect) | PASS |
| `_row_to_summary_fallback` | 1151–1222 | fully materialized session dict | summary dict | none | `test_mmm_summary_preset_source.py` (direct) | PASS |
| `get_session_count` / `get_storage` | 1224–1255 | DB count / singleton state | count value / singleton instance | global storage singleton management | indirect only | PASS |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P2-012 | P2 | `save_session` | `mmm_storage.py:673–699,732–737` | Hot-reload arbitration can correctly persist newer DB `params_json`, but caller in-memory `session['params']` is not updated to the chosen `final_params`. Probe confirmed divergence: DB interval became `111` while caller object stayed `300` immediately after save. This creates one-cycle control-plane drift for any logic that reads caller memory after save and before next reload. | After successful commit, also assign `session['params'] = final_params` (same place caller `updated_at` and checksums are synced) so in-memory and persisted state are consistent immediately. |

## Carry-forward risk note (from chunk 01)

- `F01-P1-010` remains active and affects chunk-02 consumers:
  - `list_sessions()` and `list_session_summaries()` remain sensitive to malformed row decode paths due shared `_row_to_session` dependency.
  - Probe on malformed `params_json` confirmed `list_session_summaries()` can end up returning `[]` after SQL-fast-path failure and fallback collapse.

## Wiring impact

- Upstream callers:
  - `mmm_monitor` heartbeat loop repeatedly uses `get_session` and `save_session`.
  - API routes rely on `update_session`, `list_sessions`, `list_session_summaries`, `get_active_session_ids`.
- Downstream contracts:
  - Summary payloads feed dashboard/session-table views and strategy badges.
  - Atomicity + checksum paths provide persistence safety envelope for live monitors.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_storage.py`
  - `webui/backend/routes/mmm/tests/test_mmm_summary_preset_source.py`
  - `webui/backend/routes/mmm/tests/test_sealed_smart_execute.py` (documented storage behavior note)
  - `tests/mmm/test_reliability.py` (checksum helper usage)
- Runtime probes executed:
  - `save_session` arbitration probe: DB adopted newer params (`111`) while caller dict remained stale (`300`).
  - Summary-path malformed-row probe: `list_session_summaries()` logged malformed JSON and returned `[]` via fallback path.

## Chunk verdict

- **RISK**
- Next file dependency notes:
  - `mmm_storage.py` file audit is complete (chunks 01 + 02).
  - Continue Phase 01 with `webui/backend/routes/mmm/mmm_trigger.py` chunk 01.
