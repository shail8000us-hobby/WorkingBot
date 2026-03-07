# Threaded GridBot Archive - November 14, 2025

This directory contains the **legacy threaded GridBot** implementation that was used before migrating to the async actor-based architecture.

## Archived Date
**November 14, 2025**

## Reason for Archive
The system has been fully migrated to **AsyncGridBot** with:
- Actor model (PositionManagerActor, OrderManagerActor)
- Saga pattern for complex workflows
- SQL event store for state persistence
- 100% validation completed during shadow mode testing

## Archived Files

### Core Bot
- `gridbot.py` - Main threaded GridBot class
- `handlers/` - Long/Short mode handlers
  - `long_handler.py`
  - `short_handler.py`

### Modules
- `position_manager.py` - Threaded position management
- `order_manager.py` - Threaded order management
- `reconciliation.py` - Position reconciliation logic
- `volatility_handler.py` - Volatility-based order management
- `order_manager.py.bak` - Backup file

### Utilities
- `grid_sync.py` - Grid synchronization utilities

## Migration Notes

### What Changed
1. **State Management**: JSON files → SQL event store database
2. **Concurrency**: Threading → Async/await with actors
3. **Workflow**: Direct calls → Saga orchestration
4. **Data Source**: `state.json`, `positions.json` → SQL queries via `data_writer.py`

### Current System (AsyncGridBot)
- **State Storage**: `bot_events_LONG.db` (SQLite with WAL mode)
- **WebUI Data**: Reads from SQL via `bot/monitoring/data_writer.py`
- **Actors**: `bot/strategy/actors/position_actor.py`, `order_actor.py`
- **Sagas**: `bot/strategy/sagas/` (fill processing, position closing, etc.)

## Recovery Instructions

**⚠️ NOT RECOMMENDED** - Async bot is production-ready and validated.

If emergency rollback is needed:
1. Move files back from this archive to original locations
2. Restore old imports in `bot/run.py`
3. Set environment variable: `USE_LEGACY_BOT=true`

## Validation History
- Shadow mode: 20.5 hours
- Comparisons: 1,233 state comparisons
- Match rate: 100% ✅
- Cutover date: November 12, 2025

## Contact
For questions about this archive, refer to git history or async bot documentation.
