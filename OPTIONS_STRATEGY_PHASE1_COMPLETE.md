# Options Strategy Builder - Phase 1 Complete

**Date:** January 5, 2026  
**Status:** ✅ Backend Foundation Complete

## Module Location

```
/webui/backend/options_strategy/
├── __init__.py              # Blueprint registration
├── strategy_models.py       # Data models (Strategy, StrategyLeg, etc.)
├── strategy_definitions.py  # Strategy factory (6 built-in strategies)
├── leg_executor.py          # Multi-leg order execution
├── strategy_manager.py      # CRUD + persistence (SQLite)
├── strategy_routes.py       # REST API endpoints
└── strategies.db            # SQLite database (auto-created)
```

## API Endpoints

Base URL: `http://localhost:5555/api/options-strategy`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/templates` | GET | Available strategy templates |
| `/create` | POST | Create strategy from template |
| `/create-custom` | POST | Create custom strategy |
| `/active` | GET | List active strategies |
| `/list` | GET | List all strategies (with filters) |
| `/summary` | GET | Get statistics |
| `/<id>` | GET | Get strategy details |
| `/<id>` | DELETE | Delete strategy (if not executed) |
| `/execute/<id>` | POST | Execute strategy |
| `/close/<id>` | POST | Close strategy |
| `/pnl/<id>` | GET | Get strategy P&L |
| `/payoff/<id>` | GET | Get payoff diagram data |

## Supported Strategy Types

1. **Straddle** - Buy ATM call + put (neutral, unlimited profit)
2. **Strangle** - Buy OTM call + put (neutral, cheaper than straddle)
3. **Iron Condor** - 4 legs, profit in range (neutral, defined risk)
4. **Iron Butterfly** - 4 legs, max profit at center (neutral)
5. **Call Spread** - Bull call spread (bullish, defined risk)
6. **Put Spread** - Bear put spread (bearish, defined risk)

## Usage Examples

### Create a Straddle
```bash
curl -X POST http://localhost:5555/api/options-strategy/create \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "straddle",
    "underlying": "BTC",
    "expiry": "260110",
    "params": {"strike": 95000}
  }'
```

### Create an Iron Condor
```bash
curl -X POST http://localhost:5555/api/options-strategy/create \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "iron_condor",
    "underlying": "BTC",
    "expiry": "260117",
    "params": {
      "call_sell_strike": 100000,
      "call_buy_strike": 105000,
      "put_sell_strike": 90000,
      "put_buy_strike": 85000
    }
  }'
```

### Execute a Strategy
```bash
curl -X POST http://localhost:5555/api/options-strategy/execute/{strategy_id} \
  -H "Content-Type: application/json" \
  -d '{"execution_mode": "sequential", "order_type": "limit"}'
```

## Database Schema

**strategies** table:
- id (TEXT PK)
- name, strategy_type, underlying, expiry, status
- legs_json, entry_conditions_json, exit_conditions_json
- total_cost, current_pnl
- created_at, executed_at, closed_at, notes

**execution_history** table:
- id (INTEGER PK), strategy_id, action, timestamp, details_json

## Key Features

✅ Isolated module - no interference with gridbot/options_chain  
✅ Singleton pattern for manager  
✅ SQLite persistence  
✅ Multi-leg execution (sequential/parallel)  
✅ Rollback on partial fills  
✅ Entry/exit conditions support  
✅ P&L calculation  
✅ Payoff diagram data generation  

## Next Steps (Phase 2)

1. Frontend Strategy Builder UI
2. Live price fetching for leg validation
3. Execution status real-time updates
4. Payoff diagram visualization
5. Strategy monitoring dashboard
