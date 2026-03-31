# Grid Bot — Single Entry Order Invariant Fix

**Incident**: Duplicate SELL entry orders on exchange (SELL @ 68500 + SELL @ 68000 simultaneously).
**Root cause**: `_handle_replace_pending_sell_order` swallows API exceptions → places new order without confirming old one cancelled. Secondary: no `order_purpose="entry"` passed to `_handle_place_sell`, disabling dedup checks.
**Solution**: Cancel by known ID (deterministic) + best-effort orphan sweep. Fixes both the primary exception vector and the propagation-delay vector.

---

## Files to change

1. `bot/strategy/actors/order_actor.py`
   - [x] `_handle_replace_pending_sell_order` Phase 1: known-ID cancel (blocking) + sweep (non-blocking)
   - [x] `_handle_replace_pending_sell_order` Phase 3: add `"order_purpose": "entry"`
   - [x] `_handle_replace_pending_buy_order` Phase 1: same (symmetric for LONG mode)
   - [x] `_handle_replace_pending_buy_order` Phase 3: add `"order_purpose": "entry"`

2. `bot/strategy/sagas/fill_processing_saga.py`
   - [x] `create_short_tp_saga` Step 3: get known_pending_sell_id, pass to REPLACE
   - [x] `create_short_entry_saga` Step 3: get known_pending_sell_id, pass to REPLACE

3. `bot/strategy/modules/grid_engine.py`
   - [x] `place_initial_order`: cancel ALL bot-tagged SELL entry orders at startup
   - [x] `place_grid_order`: use REPLACE_PENDING_SELL_ORDER for SHORT mode (PLACE_SELL for LONG stays as-is for now — different bug)

---

## Architecture of the fix

```
REPLACE_PENDING_SELL_ORDER now has two phases:

Phase 1a — Cancel by known ID (BLOCKING):
  payload["known_pending_id"] → cancel that exact order_id
  If cancel returns status=error (not already_gone) → ABORT, return error
  Do NOT proceed to placement if known order not confirmed cancelled.

Phase 1b — Orphan sweep (NON-BLOCKING):
  get_open_orders → cancel any remaining bot-tagged SELL at != target_price
  Exception here is WARNING only, does not abort placement
  (Phase 1a already handled the authoritative cancel)

Phase 3 — Place with order_purpose="entry":
  Re-enables timestamp cooldown + exchange dedup check in _handle_place_sell
```

## Key invariant being enforced

Before ANY new entry SELL is placed:
- The tracked pending_sell order_id is confirmed cancelled (or already gone)
- Any orphaned exchange orders (from restarts) are swept best-effort
- If the primary cancel cannot be confirmed → placement is blocked

---

## Status: COMPLETE
