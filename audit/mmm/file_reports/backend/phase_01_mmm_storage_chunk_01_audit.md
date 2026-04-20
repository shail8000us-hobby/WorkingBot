# File Audit Report — `mmm_storage.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_storage.py`
- Chunk: `1` (`lines 1–450`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - `__init__` (`58–63`)
  - `_get_conn` (`69–74`)
  - `_init_db` (`76–111`)
  - `_migrate_from_json` (`113–180`)
  - `_apply_retroactive_fixes_on_startup` (`182–249`)
  - `_ensure_strategy_type_column` (`251–263`)
  - `_safe_json_dict` (`265–276`)
  - `_parse_iso_timestamp` (`278–289`)
  - `_derive_strategy_type_strict` (`291–296`)
  - `_derive_strategy_type_legacy_aware` (`298–321`)
  - `_backfill_strategy_type_column` (`323–367`)
  - `_validate_checksum_raw` (`371–405`)
  - `_row_to_session` (`407–437`)
  - `_backfill_session_side_premiums` (`439–450`, partial; remainder in chunk 02)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `__init__` | 58–63 | module paths, DB state | DB schema/data via called methods | initializes DB, migration, and startup repair | `test_sealed_mmm_storage.py`, `test_mmm_integration.py` | RISK |
| `_get_conn` | 69–74 | `self.db_path` | connection settings | opens sqlite connection, sets `busy_timeout` | `test_sealed_mmm_storage.py` (indirect) | PASS |
| `_init_db` | 76–111 | `self.db_path` | schema/index creation | DDL + startup retro-fix kickoff | `test_sealed_mmm_storage.py` (indirect) | PASS |
| `_migrate_from_json` | 113–180 | `LEGACY_JSON_FILE`, legacy JSON payload | inserts into `mmm_sessions`, renames legacy file | one-time JSON→SQLite migration + file rename | `_test_migration.py` (script), `tests/_test_migration.py` | RISK |
| `_apply_retroactive_fixes_on_startup` | 182–249 | all stored session rows | patched `data_json`, `params_json`, checksums | startup retroactive fill-sync persistence | no direct sealed test located | PASS |
| `_ensure_strategy_type_column` | 251–263 | sqlite table info | schema migration | `ALTER TABLE` when missing | `test_mmm_summary_preset_source.py` (indirect via summary behavior) | PASS |
| `_safe_json_dict` / `_parse_iso_timestamp` | 265–289 | arbitrary raw inputs | parsed values only | none | indirect only | PASS |
| `_derive_strategy_type_strict` / `_derive_strategy_type_legacy_aware` | 291–321 | strategy markers + params | derived strategy type | none | `test_mmm_summary_preset_source.py` (indirect), strategy identity tests (indirect) | PASS |
| `_backfill_strategy_type_column` | 323–367 | existing rows + merged params | repaired `strategy_type` column | DB UPDATEs for legacy rows | indirect only | PASS |
| `_validate_checksum_raw` | 371–405 | raw session dict + stored checksums | boolean verdict | warning logs on mismatch | `test_sealed_mmm_storage.py` (checksum-warning flow indirect) | PASS |
| `_row_to_session` | 407–437 | `data_json`, `params_json`, `strategy_type` | merged session dict | checksum validation + corrective transforms | `test_sealed_mmm_storage.py` | RISK |
| `_backfill_session_side_premiums` (partial) | 439–450 | adjustment history, lots | side premium fields | in-memory mutation | continued in chunk 02 | DEFER |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-010 | P1 | `_row_to_session` (decode path) | `mmm_storage.py:417,428` + callers (`get_session`/`list_sessions` in later lines) | A single malformed JSON row can cause session-read blackout behavior. `json.loads(row['params_json'])` is unguarded in `_row_to_session`; `get_session` then returns `None`, and `list_sessions` can collapse to `[]` when one row raises. Runtime probe confirmed: malformed `params_json` produced `get_session_is_none=True` and `list_sessions_len=0` with two stored rows. This can hide active sessions from control-plane views. | Use resilient decode (`_safe_json_dict`) in `_row_to_session` for `params_json` (and optionally guarded decode for `data_json`), attach `_checksum_warning`/`_parse_warning` markers, and skip only bad rows in list flows instead of failing the whole list. Add sealed tests for malformed-row isolation. |
| F01-P2-011 | P2 | `__init__` + `_migrate_from_json` | `mmm_storage.py:32,58–63,113–180` | Legacy migration source is module-global (`LEGACY_JSON_FILE`) and not derived from `self.db_path`. When constructing `MMMStorage` with a custom DB path, migration still targets the global legacy JSON location. Probe confirmed `legacy_tied_to_db_dir=False` for custom DB instances. This creates environment-coupling risk (unexpected import/rename side effects) for non-default storage instances and test harnesses. | Gate migration to default DB only, or derive legacy path from the configured DB directory when custom `db_path` is used; avoid global-path side effects in custom instances. |

## Wiring impact

- Upstream callers:
  - `mmm_monitor` reload loop depends on storage reads each heartbeat (`storage.get_session(...)`).
  - API routes and maintenance flows consume storage list/get behavior for session visibility.
- Downstream dependencies:
  - Strategy identity reconciliation depends on `mmm_state.derive_strategy_type` through storage wrappers.
- Control-plane implications:
  - Decode fragility in `_row_to_session` can present as “session missing” rather than “session corrupted”, reducing operator diagnosability.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_storage.py`
  - `webui/backend/routes/mmm/tests/test_mmm_integration.py` (storage section)
  - `webui/backend/routes/mmm/tests/test_mmm_summary_preset_source.py` (strategy-type summary path)
  - `_test_migration.py` and `tests/_test_migration.py` (migration harness scripts)
- Runtime probes executed:
  - Corrupted one row’s `params_json` → `get_session` returned `None`.
  - Same corruption with two rows present → `list_sessions()` returned `[]` (global list collapse).
  - Custom DB instance check → `LEGACY_JSON_FILE` not tied to custom `db_path` directory.

## Chunk verdict

- **RISK**
- Next chunk dependency notes:
  - Continue `mmm_storage.py` chunk 02 (`lines 451–EOF`) to audit checksum write paths, `save_session`/`update_session` atomicity, summary SQL path, and singleton behavior.
