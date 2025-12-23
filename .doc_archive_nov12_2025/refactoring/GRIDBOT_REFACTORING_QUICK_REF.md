# GridBot Refactoring - Quick Reference

**For All AI Assistants Reading This Codebase**

---

## 🚨 CRITICAL: Architecture Changed (Oct 31, 2025)

**Old documentation references `bot/strategy/gbot_ws.py` (3,492-line God Class).**  
**This file is now BACKUP ONLY. Production uses modular architecture.**

---

## Production Architecture

**Entry Point:**
```python
from bot.strategy.gridbot import run_grid_strategy  # ✅ CURRENT
```

**Main Files:**
```
bot/strategy/
├── gbot_ws.py                # ⚠️ BACKUP (preserved for rollback)
├── gridbot.py                # ✅ ACTIVE ORCHESTRATOR (538 lines)
└── modules/                  # ✅ ACTIVE MODULES
    ├── grid_calculator.py      (181 lines) - Pure math
    ├── websocket_handler.py    (198 lines) - Event routing
    ├── fill_detector.py        (197 lines) - Fill detection
    ├── position_manager.py     (487 lines) - State (owns lock)
    ├── order_manager.py        (491 lines) - Orders
    ├── reconciliation.py       (301 lines) - Exchange sync
    └── volatility_handler.py   (449 lines) - Volatility
```

---

## Quick Method Lookup

| Need | Module | Method |
|------|--------|--------|
| Fill detection | fill_detector.py | process_websocket_fill() |
| Place BUY | order_manager.py | place_buy_order() |
| Place TP | order_manager.py | place_tp_order() |
| Reconnect sync | reconciliation.py | sync_on_reconnect() |
| State save | position_manager.py | persist_runtime_state() |
| Volatility halt | volatility_handler.py | trigger_volatility_halt() |
| Recovery | volatility_handler.py | trigger_recovery() |
| Grid realign | volatility_handler.py | _realign_grid() |

---

## Critical Fixes Preserved

| Fix | Old Location | New Location | Status |
|-----|-------------|--------------|--------|
| FIX #12 (Reconnect) | gbot_ws.py:2682-2710 | reconciliation.py:62-142 | ✅ |
| FIX #13 (State) | gbot_ws.py:2740-2785 | position_manager.py:342-388 | ✅ |
| FIX #8 (TP Collision) | gbot_ws.py:1710-1800 | order_manager.py:401-447 | ✅ |
| FIX #6 (Realign) | gbot_ws.py:1935-2000 | volatility_handler.py:298-350 | ✅ |

---

## When Reading Old Docs

- **gbot_ws.py references** → Historical/backup context
- **Line numbers** → Deprecated, use method names
- **"God Class"** → Refactored into 7 modules
- **"ACTIVE"** label on gbot_ws.py → Now applies to gridbot.py

---

## Full Details

See: `ARCHITECTURE_UPDATE_REFACTORED_GRIDBOT.md`

**Test Coverage:** 96.7% (30/31 tests)  
**Status:** ✅ Production-ready  
**Rollback:** Available (instant, zero data loss)

---

**Last Updated:** October 31, 2025
