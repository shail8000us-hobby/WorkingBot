# Recovery Engine System

Enterprise-grade recovery system with separate engines for startup and guardian recovery.

## Architecture

```
BaseRecoveryEngine (Abstract)
├── Circuit Breaker
├── Rate Limiter
├── Distributed Lock
├── Retry Logic
├── State Persistence
└── Audit Trail

StartupRecoveryEngine (Concrete)
├── Single execution guarantee
├── Max 3 grids
└── 1-hour cooldown

GuardianRecoveryEngine (Concrete)
├── STOP → GO detection
├── Unlimited grids
└── Always enabled
```

## Usage

### Initialization

```python
from bot.strategy.recovery import StartupRecoveryEngine, GuardianRecoveryEngine

# In AsyncGridBot.__init__()
self.startup_recovery = StartupRecoveryEngine(self, config, logger)
self.guardian_recovery = GuardianRecoveryEngine(self, config, logger)
```

### Execution

```python
# Startup recovery (once)
async def start(self):
    result = await self.startup_recovery.execute_recovery()
    if result['success'] and result['recovered'] > 0:
        logger.info(f"Recovered {result['recovered']} positions")

# Guardian recovery (continuous monitoring)
async def _guardian_recovery_monitor(self):
    while self.running:
        await self.guardian_recovery.execute_recovery()
        await asyncio.sleep(10)
```

## Safety Features

- ✅ Circuit breaker (3 failures → 60s timeout)
- ✅ Rate limiter (0.5 orders/sec)
- ✅ Distributed locking (prevents concurrent recovery)
- ✅ Retry logic (3 attempts with 5s delay)
- ✅ Position existence checks
- ✅ Pending order checks
- ✅ State persistence (atomic writes)
- ✅ Audit trail (JSONL logs)

## State Files

```
data/recovery/
├── startup_recovery_state.json       # Startup engine state
├── guardian_recovery_state.json      # Guardian engine state
├── StartupRecoveryEngine_history.jsonl   # Startup audit log
└── GuardianRecoveryEngine_history.jsonl  # Guardian audit log
```

## Health Monitoring

```python
# Get health status
health = recovery_engine.get_health_status()
# {
#   'engine': 'StartupRecoveryEngine',
#   'enabled': True,
#   'circuit_state': 'closed',
#   'success_rate': '100%',
#   'recovered_grids_count': 2
# }
```

## Configuration

```yaml
recovery:
  enabled: true
  max_retries: 3
  retry_delay: 5
  recovery_cooldown: 300
  recovery_failure_threshold: 3
  recovery_circuit_timeout: 60
  recovery_max_concurrent: 5
  recovery_rate_limit: 0.5

safety:
  volatility:
    opportunistic_recovery:
      enabled: true  # Startup recovery
      max_grids: 3
      cooldown: 3600
```

## Created

November 20, 2025
