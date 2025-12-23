# Recovery Engine Architecture - Complete Implementation Plan

**Date:** November 20, 2025  
**Status:** Design Phase  
**Priority:** HIGH (Fixes critical duplicate order bug)

---

## Executive Summary

### Problem
Current opportunistic recovery system creates duplicate positions at the same grid level due to:
- No position existence checks
- No state tracking across restarts
- Shared execution logic between startup and guardian recovery

### Solution
Separate, independent recovery engines with enterprise-grade safety:
- **Startup Recovery Engine** - Runs once at bot startup
- **Guardian Recovery Engine** - Runs when Guardian resumes after halt
- **Base Recovery Engine** - Shared safety mechanisms (circuit breaker, rate limiter, locking)

---

## Architecture

```
AsyncGridBot (Main)
├── Normal Grid Trading
├── Startup Recovery Engine (once at startup)
├── Guardian Recovery Engine (on Guardian resume)
└── Base Recovery Engine (shared safety logic)
```

---

## File Structure

```
bot/strategy/recovery/
├── __init__.py
├── base_recovery_engine.py      # Base class with safety features
├── startup_recovery.py          # Startup recovery
├── guardian_recovery.py         # Guardian recovery
└── recovery_monitor.py          # Health monitoring

data/recovery/
├── startup_recovery_state.json
├── guardian_recovery_state.json
├── StartupRecoveryEngine_history.jsonl
└── GuardianRecoveryEngine_history.jsonl
```

---

## Core Components

### 1. Base Recovery Engine

**Safety Mechanisms:**
- ✅ Circuit Breaker (3 failures → open for 60s)
- ✅ Rate Limiter (0.5 orders/sec)
- ✅ Distributed Lock (5 min timeout)
- ✅ Retry Logic (3 attempts with 5s delay)
- ✅ State Persistence (atomic writes)
- ✅ Audit Trail (JSONL logs)
- ✅ Health Metrics

**Key Methods:**
```python
class BaseRecoveryEngine(ABC):
    @abstractmethod
    async def should_trigger(self) -> Tuple[bool, str]
    
    @abstractmethod
    async def calculate_missed_grids(self) -> List[float]
    
    async def execute_recovery(self) -> Dict
    async def _recover_single_grid_with_retry(self, grid_price: float) -> RecoveryAttempt
    async def _preflight_checks(self) -> Dict
    async def _has_position_at_grid(self, grid_price: float) -> bool
    async def _has_pending_order_at_grid(self, grid_price: float) -> bool
    def get_health_status(self) -> Dict
```

### 2. Startup Recovery Engine

**Characteristics:**
- Executes ONCE per bot session
- Maximum 3 grids recovered
- 1-hour cooldown between runs
- Can be disabled via config

**Trigger Conditions:**
- Bot startup
- Market < first grid (LONG) or Market > first grid (SHORT)
- Not executed in current session
- Not executed in last 1 hour

### 3. Guardian Recovery Engine

**Characteristics:**
- Always enabled (critical)
- No grid limit (recovers all missed)
- Triggers on Guardian STOP → GO transition
- Tracks halt start price

**Trigger Conditions:**
- Guardian state changes from STOP to GO
- Market moved > 1 grid step during halt

---

## Integration with AsyncGridBot

```python
class AsyncGridBot:
    def __init__(self, config):
        self.startup_recovery = StartupRecoveryEngine(self, config, logger)
        self.guardian_recovery = GuardianRecoveryEngine(self, config, logger)
    
    async def start(self):
        # Execute startup recovery (once)
        result = await self.startup_recovery.execute_recovery()
        
        # Start Guardian recovery monitor
        self.tasks.append(
            asyncio.create_task(self._guardian_recovery_monitor())
        )
    
    async def _guardian_recovery_monitor(self):
        while self.running:
            await self.guardian_recovery.execute_recovery()
            await asyncio.sleep(10)
    
    async def place_recovery_order(self, grid_price: float, tag: str) -> int:
        return await self.order_manager.place_buy_market(
            price=grid_price,
            size=self.config.grid.limits.lot_size,
            tag=tag
        )
```

---

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

---

## Implementation Plan

### Phase 1: Base Engine (Week 1)
1. Create `bot/strategy/recovery/` directory
2. Implement `base_recovery_engine.py` with all safety features
3. Add unit tests for CircuitBreaker, RateLimiter
4. Test state persistence

### Phase 2: Startup Engine (Week 1)
1. Implement `startup_recovery.py`
2. Extract logic from current `async_gridbot.py`
3. Add single-execution guarantee
4. Add unit tests

### Phase 3: Guardian Engine (Week 2)
1. Implement `guardian_recovery.py`
2. Add Guardian state detection
3. Add halt price tracking
4. Add unit tests

### Phase 4: Integration (Week 2)
1. Update `async_gridbot.py` to use engines
2. Remove old recovery code
3. Add health monitoring endpoints
4. Integration tests

### Phase 5: Testing & Deployment (Week 3)
1. Test with startup recovery disabled
2. Test Guardian recovery in isolation
3. Enable startup recovery after validation
4. Monitor metrics and tune parameters

---

## Testing Strategy

### Unit Tests
- Circuit breaker behavior
- Rate limiter token bucket
- Single execution guarantee
- State persistence
- Guardian state detection

### Integration Tests
- Startup recovery with market below reference
- Guardian recovery on STOP → GO transition
- No duplicates on bot restart
- Concurrent recovery prevention

### Chaos Tests
- API failures during recovery
- WebSocket disconnection
- Database errors
- Circuit breaker activation

---

## Health Monitoring

### API Endpoints
```
GET /api/recovery/health
GET /api/recovery/metrics
GET /api/recovery/history
POST /api/recovery/clear-state
```

### Health Response
```json
{
  "startup": {
    "enabled": true,
    "circuit_state": "closed",
    "success_rate": "100%",
    "recovered_grids_count": 2
  },
  "guardian": {
    "enabled": true,
    "circuit_state": "closed",
    "success_rate": "95.2%",
    "recovered_grids_count": 5
  }
}
```

---

## Safety Guarantees

✅ **No duplicates** - Position/order checks + state tracking  
✅ **No concurrent recovery** - Distributed lock  
✅ **No API abuse** - Rate limiter + circuit breaker  
✅ **No cascading failures** - Circuit breaker auto-recovery  
✅ **Full auditability** - Session history + JSONL logs  
✅ **Graceful degradation** - Fails safely on errors  
✅ **Independent engines** - Can disable/test separately  

---

## Migration Path

### Immediate (Tonight)
1. Disable startup recovery in config
2. Clean up duplicate positions manually
3. Adjust reference price to match market

### Short Term (This Week)
1. Implement base engine with safety features
2. Implement startup engine
3. Test in isolation

### Medium Term (Next Week)
1. Implement guardian engine
2. Integrate with main bot
3. Deploy with startup disabled

### Long Term (Week 3)
1. Monitor guardian recovery performance
2. Enable startup recovery after validation
3. Tune parameters based on metrics

---

## Success Criteria

- ✅ Zero duplicate positions
- ✅ 95%+ recovery success rate
- ✅ < 5s average recovery time per grid
- ✅ No API rate limit violations
- ✅ Circuit breaker activates on failures
- ✅ Full audit trail maintained
- ✅ Guardian recovery works on halt/resume

---

## WebUI Integration (Optional Enhancement)

### Phase 6: WebUI Dashboard (Week 4)

**Purpose:** Visual monitoring and control of recovery engines

#### 6.1 Recovery Status Panel

**Location:** `webui/frontend/src/components/panels/RecoveryStatusPanel.js`

**Features:**
- Real-time recovery engine status
- Circuit breaker state indicators
- Success rate gauges
- Recent recovery sessions list
- Enable/disable toggle buttons

**UI Layout:**
```
┌─────────────────────────────────────────────────────┐
│ 🔄 Recovery System Status                           │
├─────────────────────────────────────────────────────┤
│                                                      │
│ Startup Recovery          Guardian Recovery         │
│ ● Enabled                 ● Enabled                 │
│ 🟢 Circuit: Closed        🟢 Circuit: Closed        │
│ ✅ Success: 100%          ✅ Success: 95.2%         │
│ 📊 Recovered: 8           📊 Recovered: 47          │
│ ⏱️  Last: 2h ago          ⏱️  Last: 15m ago         │
│                                                      │
│ [Disable] [Clear State]   [View History]            │
└─────────────────────────────────────────────────────┘
```

#### 6.2 Recovery History Table

**Location:** `webui/frontend/src/components/tables/RecoveryHistoryTable.js`

**Columns:**
- Session ID
- Engine (Startup/Guardian)
- Timestamp
- Trigger Reason
- Grids Recovered
- Grids Failed
- Duration
- Status

**Features:**
- Sortable columns
- Filter by engine/status
- Expandable rows (show attempt details)
- Export to CSV

#### 6.3 Recovery Metrics Chart

**Location:** `webui/frontend/src/components/charts/RecoveryMetricsChart.js`

**Charts:**
1. Success rate over time (line chart)
2. Recovery count per day (bar chart)
3. Circuit breaker activations (timeline)
4. Average recovery duration (line chart)

#### 6.4 Backend API Endpoints

**New Routes:** `webui/backend/routes/recovery.py`

```python
# Health and Status
GET  /api/recovery/health
GET  /api/recovery/metrics
GET  /api/recovery/status/:engine

# History and Audit
GET  /api/recovery/history
GET  /api/recovery/sessions/:session_id
GET  /api/recovery/export/csv

# Control
POST /api/recovery/enable/:engine
POST /api/recovery/disable/:engine
POST /api/recovery/clear-state/:engine
POST /api/recovery/reset-circuit/:engine

# Testing (dev only)
POST /api/recovery/test-trigger/:engine
```

**Example Response:**
```json
{
  "success": true,
  "health": {
    "startup": {
      "enabled": true,
      "circuit_state": "closed",
      "success_rate": "100%",
      "recovered_grids_count": 2,
      "pending_grids_count": 0,
      "last_execution": "2025-11-20T00:15:30"
    },
    "guardian": {
      "enabled": true,
      "circuit_state": "closed",
      "success_rate": "95.2%",
      "recovered_grids_count": 5,
      "pending_grids_count": 0,
      "last_execution": "2025-11-20T00:25:30"
    }
  }
}
```

#### 6.5 Real-time Updates

**WebSocket Events:**
```javascript
// Subscribe to recovery events
socket.on('recovery:session_started', (data) => {
  // Update UI: show "Recovery in progress"
});

socket.on('recovery:session_completed', (data) => {
  // Update UI: show results, refresh metrics
});

socket.on('recovery:circuit_opened', (data) => {
  // Alert: Circuit breaker activated
});

socket.on('recovery:grid_recovered', (data) => {
  // Live update: Grid X recovered
});
```

#### 6.6 Alert Integration

**Telegram Notifications:**
```
🔄 Recovery Session Started
Engine: Guardian Recovery
Trigger: Guardian resumed after halt
Grids to recover: 5

✅ Recovery Session Completed
Engine: Guardian Recovery
Recovered: 5/5 grids
Duration: 12.3s
Success rate: 100%

⚠️ Circuit Breaker Opened
Engine: Startup Recovery
Reason: 3 consecutive failures
Timeout: 60s
```

#### 6.7 Configuration Editor

**Add to existing config editor:**

```yaml
# In webui config editor, add Recovery section
recovery:
  enabled: true
  max_retries: 3
  retry_delay: 5
  recovery_cooldown: 300
  recovery_failure_threshold: 3
  recovery_circuit_timeout: 60
  
safety:
  volatility:
    opportunistic_recovery:
      enabled: true  # Toggle for startup recovery
      max_grids: 3
      cooldown: 3600
```

**UI Features:**
- Toggle switches for enable/disable
- Sliders for numeric values
- Inline help tooltips
- Validation on save

#### 6.8 Implementation Checklist

**Backend (Week 4, Day 1-2):**
- [ ] Create `webui/backend/routes/recovery.py`
- [ ] Implement health endpoint
- [ ] Implement metrics endpoint
- [ ] Implement history endpoint
- [ ] Implement control endpoints
- [ ] Add WebSocket events
- [ ] Add to `webui/backend/app.py`

**Frontend (Week 4, Day 3-5):**
- [ ] Create `RecoveryStatusPanel.js`
- [ ] Create `RecoveryHistoryTable.js`
- [ ] Create `RecoveryMetricsChart.js`
- [ ] Add to main dashboard
- [ ] Implement WebSocket listeners
- [ ] Add to config editor
- [ ] Style with Tailwind CSS

**Testing (Week 4, Day 5):**
- [ ] Test all API endpoints
- [ ] Test WebSocket events
- [ ] Test enable/disable toggles
- [ ] Test history pagination
- [ ] Test chart rendering
- [ ] Mobile responsiveness

#### 6.9 WebUI Benefits

**For Users:**
- ✅ Visual confirmation recovery is working
- ✅ Quick enable/disable without editing files
- ✅ Historical analysis of recovery patterns
- ✅ Early warning via circuit breaker alerts
- ✅ Audit trail for debugging

**For Developers:**
- ✅ Easy testing of recovery engines
- ✅ Real-time debugging during development
- ✅ Metrics for performance tuning
- ✅ Session replay for bug investigation

#### 6.10 Optional: Recovery Simulator

**Testing Tool:** `webui/frontend/src/components/tools/RecoverySimulator.js`

**Features:**
- Simulate Guardian halt/resume
- Simulate market price changes
- Trigger recovery manually
- Preview what would be recovered
- Dry-run mode (no actual orders)

**Use Cases:**
- Test recovery logic before enabling
- Understand recovery behavior
- Training and documentation
- Debugging edge cases

---

## Documentation

- `recovery_engine.md` - This document
- `bot/strategy/recovery/README.md` - Developer guide
- `ai_context.md` - Update with recovery architecture
- API documentation for health endpoints
- `Monitoring_webUI_19Nov_2025.md` - Reference for WebUI patterns

---

**Status:** Ready for implementation  
**Next Step:** Create base_recovery_engine.py with safety features  
**WebUI:** Optional Phase 6 (Week 4) - Enhances visibility and control
