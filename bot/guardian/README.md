# Guardian Bot v2.0 - Clean Architecture

## 📁 Directory Structure

```
bot/guardian/
│
├── collectors/              ✅ Data Collectors (NO decisions)
│   ├── __init__.py
│   ├── position_monitor.py  → Positions, PnL, margin
│   └── health_tracker.py    → System health metrics
│
├── engine/                  ✅ Decision Engine (SINGLE source of truth)
│   ├── __init__.py
│   └── risk_decision_engine.py
│       ├── Reads from collectors
│       ├── Publishes GO/STOP to SQL every 5s
│       ├── Watches config.yaml for changes
│       └── 5 safety checks (volatility, loss, position, liquidation, health)
│
├── core/                    ✅ Main Orchestrator (NO risk logic)
│   ├── __init__.py
│   └── guardian_bot.py
│       ├── Starts collectors
│       ├── Starts risk engine
│       ├── Reads OWN signals from database
│       ├── Sends Telegram alerts on signal changes
│       └── Updates health status
│
├── __init__.py              → Package exports
└── README.md                → This file
```

## 🎯 Key Principles

1. **Data Collectors** = Fetch data only, NO decisions
2. **Decision Engine** = ONLY place that decides GO/STOP
3. **Guardian Bot** = Orchestrator, reads signals, sends alerts

## 🚀 Usage

```python
from bot.guardian import GuardianBot

# Start Guardian
bot = GuardianBot()
await bot.run()

# Guardian publishes signals to SQL database every 5s
# Trading bot reads signals from same database
```

## 📊 Signal Flow

```
Collectors → Engine → SQL Database → Guardian Bot → Telegram
                                   ↓
                              Trading Bot (reads signals)
```

## ✅ Benefits

- **Clean separation** of concerns
- **Single source** of truth for decisions
- **Easy to test** each component independently
- **Clear file tree** in VS Code explorer
