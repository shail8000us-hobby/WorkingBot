# WebUI Robustness Plan - Single-User Optimized
**Date**: November 12, 2025  
**Reality Check**: Solo developer, one exchange, production-ready but maintainable  
**Core Philosophy**: Bot is source of truth, WebUI is read-only observer with command privileges

---

## 🎯 Simplified Strategy (Based on Feedback)

### Key Insight
**WebUI = Read-Only Client of Bot's Event Log**
- Bot owns all state (already bulletproof with event sourcing)
- WebUI observes and sends commands (confirmed via saga pattern)
- Perfect failure isolation: UI crash ≠ bot disruption

### What We're Keeping (High ROI)
1. ✅ **Circuit breakers** (backend + frontend) - Prevents cascade failures
2. ✅ **Health checks** with guardian dashboard - See issues before they fail
3. ✅ **Data aggregator** - 91 pollers → 1 (massive win)
4. ✅ **Event sourcing pattern** - But simpler (Zustand, not custom)
5. ✅ **State persistence** - Survive page refresh
6. ✅ **Performance budgets** - Measure, don't guess

### What We're Simplifying
1. ⚡ Skip manual event store → Use **Zustand** (React state with persistence)
2. ⚡ Skip Playwright E2E → Health dashboard gives 90% safety
3. ⚡ Keep Flask for now → FastAPI migration optional later
4. ⚡ Shadow testing only for critical changes → Not everything

### What We're Adding (From Feedback)
1. 🎁 **SQLite metrics log** - Historic trends for guardian dashboard
2. 🎁 **Vite dev overlay** - Better DX during development
3. 🎁 **Command confirmation** - All bot actions go through saga

---

## Phase 1: Backend Resilience (Week 1) - START HERE

### 1.1 Circuit Breaker (3 hours) ✅ KEEP

**Why**: Prevents WebUI from hammering dead Delta API or bot files.

```python
# webui/backend/utils/circuit_breaker.py
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
import logging

log = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Lightweight circuit breaker for single-user setup"""
    def __init__(self, name, failure_threshold=3, timeout=15):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # seconds to stay OPEN
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.lock = Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                    self.state = CircuitState.HALF_OPEN
                    log.info(f"🔄 Circuit {self.name}: HALF_OPEN")
                else:
                    raise Exception(f"Circuit {self.name} is OPEN (cooldown)")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                log.info(f"✅ Circuit {self.name}: CLOSED")
    
    def _on_failure(self):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                log.error(f"🔴 Circuit {self.name}: OPEN (failures: {self.failure_count})")

# Global breakers (keep it simple)
delta_api_breaker = CircuitBreaker("delta_api", failure_threshold=3, timeout=15)
bot_file_breaker = CircuitBreaker("bot_files", failure_threshold=2, timeout=5)
```

**Usage in routes**:
```python
# webui/backend/routes/positions.py
from webui.backend.utils.circuit_breaker import delta_api_breaker

def _get_positions_from_delta():
    try:
        return delta_api_breaker.call(_fetch_positions_impl)
    except Exception as e:
        log.debug(f"Delta API circuit open: {e}")
        return None  # Graceful fallback
```

**Impact**: Prevents UI freeze when Delta API is down. Fast fail = better UX.

---

### 1.2 Health Check Endpoint (2 hours) ✅ KEEP

**Why**: Know system status before users (you) complain.

```python
# webui/backend/routes/health.py
@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """
    Lightweight health check for single-user setup
    Returns: overall status + component details
    """
    components = {}
    
    # Check Delta API (quick test)
    try:
        delta_client = DeltaClient()
        start = time.time()
        delta_client._req('GET', '/v2/products/27')
        latency = (time.time() - start) * 1000
        components['delta_api'] = {
            'status': 'degraded' if latency > 1000 else 'healthy',
            'latency_ms': round(latency, 2),
            'circuit': delta_api_breaker.state.value
        }
    except Exception as e:
        components['delta_api'] = {
            'status': 'unhealthy',
            'error': str(e),
            'circuit': delta_api_breaker.state.value
        }
    
    # Check bot process
    components['bot_process'] = {
        'status': 'healthy' if is_bot_running() else 'unhealthy'
    }
    
    # Check critical files
    try:
        positions_file = BASE_DIR / "bot" / "reports" / "positions.json"
        components['bot_files'] = {
            'status': 'healthy' if positions_file.exists() else 'degraded'
        }
    except Exception:
        components['bot_files'] = {'status': 'unhealthy'}
    
    # Overall status
    overall = 'healthy'
    if any(c['status'] == 'unhealthy' for c in components.values()):
        overall = 'unhealthy'
    elif any(c['status'] == 'degraded' for c in components.values()):
        overall = 'degraded'
    
    return jsonify({
        'status': overall,
        'timestamp': datetime.now().isoformat(),
        'components': components,
        'uptime_seconds': _get_uptime()
    })
```

**Impact**: 30-second health polling shows issues immediately.

---

### 1.3 Metrics Logger (SQLite) (2 hours) 🎁 NEW

**Why**: Historic trends for guardian dashboard. Better than logs.

```python
# webui/backend/utils/metrics_logger.py
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'metrics.db'

class MetricsLogger:
    """Log WebUI metrics to SQLite for trending"""
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                timestamp TEXT,
                metric_type TEXT,
                metric_name TEXT,
                value REAL,
                status TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics(timestamp)')
        conn.commit()
        conn.close()
    
    def log_metric(self, metric_type, metric_name, value, status='ok'):
        """Log a metric data point"""
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT INTO metrics VALUES (?, ?, ?, ?, ?)',
            (datetime.now().isoformat(), metric_type, metric_name, value, status)
        )
        conn.commit()
        conn.close()
    
    def get_recent_metrics(self, metric_type, hours=24):
        """Get recent metrics for charting"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            '''SELECT timestamp, metric_name, value, status 
               FROM metrics 
               WHERE metric_type = ? 
               AND timestamp > datetime('now', '-' || ? || ' hours')
               ORDER BY timestamp DESC''',
            (metric_type, hours)
        )
        results = cursor.fetchall()
        conn.close()
        return results

metrics_logger = MetricsLogger()

# Usage: Log API latencies, error counts, circuit states
@app.after_request
def log_request_metrics(response):
    metrics_logger.log_metric(
        'api_latency',
        request.path,
        response.elapsed_time if hasattr(response, 'elapsed_time') else 0,
        'ok' if response.status_code < 400 else 'error'
    )
    return response
```

**Impact**: Guardian dashboard can show "API latency last 24h" with real data.

---

### 1.4 Request Timeout Decorator (1 hour) ✅ KEEP

**Why**: No more 30s hangs. Fast fail is better UX.

```python
# webui/backend/utils/timeout_decorator.py
from functools import wraps
import signal

class TimeoutError(Exception):
    pass

def timeout(seconds=5):
    """Simple timeout decorator for route handlers"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"Request exceeded {seconds}s timeout")
            
            # Set alarm
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancel alarm
                return result
            except TimeoutError:
                return jsonify({'error': f'Request timeout ({seconds}s)'}), 504
        
        return wrapper
    return decorator

# Usage
@positions_bp.route('/api/positions', methods=['GET'])
@timeout(seconds=5)
def get_positions():
    # Must complete in 5s or return 504
    ...
```

**Impact**: Predictable failure (504) instead of hanging forever.

---

## Phase 2: Frontend State Management (Week 2)

### 2.1 Zustand Store with Persistence (3 hours) ⚡ SIMPLIFIED

**Why**: Replaces custom event store. Lightweight, React-native, persistent.

```bash
cd webui/frontend
npm install zustand
```

```javascript
// webui/frontend/src/store/index.js
import create from 'zustand';
import { persist } from 'zustand/middleware';

export const useStore = create(
  persist(
    (set, get) => ({
      // State
      positions: [],
      orders: [],
      config: {},
      health: { status: 'unknown' },
      pnl: {},
      lastUpdate: null,
      
      // Actions
      updatePositions: (positions) => set({ 
        positions, 
        lastUpdate: Date.now() 
      }),
      
      updateOrders: (orders) => set({ 
        orders, 
        lastUpdate: Date.now() 
      }),
      
      updateHealth: (health) => set({ health }),
      
      updateConfig: (config) => set({ config }),
      
      updatePnL: (pnl) => set({ pnl }),
      
      // Reset (for logout/refresh)
      reset: () => set({
        positions: [],
        orders: [],
        config: {},
        health: { status: 'unknown' },
        pnl: {},
        lastUpdate: null
      })
    }),
    {
      name: 'webui-storage', // localStorage key
      partialize: (state) => ({
        // Only persist these (not health, too dynamic)
        config: state.config,
        lastUpdate: state.lastUpdate
      })
    }
  )
);

// Selector hooks (avoid re-renders)
export const usePositions = () => useStore(state => state.positions);
export const useOrders = () => useStore(state => state.orders);
export const useHealth = () => useStore(state => state.health);
export const useConfig = () => useStore(state => state.config);
```

**Usage in components**:
```javascript
import { usePositions, useStore } from '../store';

function PositionsPanel() {
  const positions = usePositions();
  const updatePositions = useStore(state => state.updatePositions);
  
  // Component logic...
  
  return <div>{positions.map(...)}</div>;
}
```

**Impact**: 
- State survives page refresh
- 3 lines of code vs 100+ for custom event store
- Built-in dev tools

---

### 2.2 Data Aggregator (Single Poller) (4 hours) ✅ KEEP

**Why**: 91 components polling → 1 poller. Massive API load reduction.

```javascript
// webui/frontend/src/services/dataAggregator.js
import { useStore } from '../store';
import apiClient from '../utils/apiClient';

class DataAggregator {
  constructor() {
    this.interval = null;
    this.isRunning = false;
  }
  
  start() {
    if (this.isRunning) return;
    
    this.isRunning = true;
    console.log('📡 Data aggregator started');
    
    // Single polling loop
    this.interval = setInterval(async () => {
      await this._fetchAllData();
    }, 2000);  // 2s refresh
    
    // Immediate fetch
    this._fetchAllData();
  }
  
  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
      this.isRunning = false;
      console.log('📡 Data aggregator stopped');
    }
  }
  
  async _fetchAllData() {
    try {
      // Parallel fetch (faster than sequential)
      const [positions, orders, health, pnl] = await Promise.allSettled([
        apiClient.get('/api/positions'),
        apiClient.get('/api/orders'),
        apiClient.get('/api/health'),
        apiClient.get('/api/pnl/summary')
      ]);
      
      // Update store (even if some failed)
      const store = useStore.getState();
      
      if (positions.status === 'fulfilled') {
        store.updatePositions(positions.value.positions || []);
      }
      
      if (orders.status === 'fulfilled') {
        store.updateOrders(orders.value.orders || []);
      }
      
      if (health.status === 'fulfilled') {
        store.updateHealth(health.value);
      }
      
      if (pnl.status === 'fulfilled') {
        store.updatePnL(pnl.value);
      }
      
    } catch (error) {
      console.error('Data aggregation failed:', error);
    }
  }
}

export const dataAggregator = new DataAggregator();

// Start on app mount
// webui/frontend/src/App.js
useEffect(() => {
  dataAggregator.start();
  return () => dataAggregator.stop();
}, []);
```

**Components just read from store** (no individual polling):
```javascript
function PositionsPanel() {
  const positions = usePositions();
  // That's it! No useEffect, no polling, just reactive data
  return <div>{positions.map(...)}</div>;
}
```

**Impact**:
- **91 API calls/2s → 5 API calls/2s** (95% reduction!)
- Consistent update timing
- Easier to debug (single source)

---

### 2.3 Error Boundaries (1 hour) ✅ KEEP

**Why**: Component crash ≠ UI crash. Isolation.

```javascript
// webui/frontend/src/components/ErrorBoundary.js
import React from 'react';
import { Alert, Button } from '@mui/material';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('🔴 Component error:', error, errorInfo);
    
    // Log to backend (for your monitoring)
    fetch('/api/logs/frontend-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        error: error.toString(),
        stack: error.stack,
        component: this.props.name || 'unknown'
      })
    }).catch(() => {}); // Don't crash on logging error
    
    this.setState({ error });
  }

  render() {
    if (this.state.hasError) {
      return (
        <Alert 
          severity="error" 
          action={
            <Button onClick={() => this.setState({ hasError: false })}>
              Retry
            </Button>
          }
        >
          <strong>{this.props.name || 'Component'} Error</strong>
          <p>{this.state.error?.message}</p>
        </Alert>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

**Usage in App.js**:
```javascript
<ErrorBoundary name="Positions">
  <PositionsPanel />
</ErrorBoundary>

<ErrorBoundary name="Orders">
  <OrdersPanel />
</ErrorBoundary>
```

**Impact**: One panel crashes, others keep working. You can retry without refresh.

---

### 2.4 Frontend Circuit Breaker (2 hours) ✅ KEEP

**Why**: Stop hammering dead backend. Matches backend pattern.

```javascript
// webui/frontend/src/utils/circuitBreaker.js
class CircuitBreaker {
  constructor(name, threshold = 3, timeout = 15000) {
    this.name = name;
    this.threshold = threshold;
    this.timeout = timeout;
    
    this.state = 'CLOSED';
    this.failureCount = 0;
    this.lastFailureTime = null;
  }
  
  async call(func) {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.timeout) {
        this.state = 'HALF_OPEN';
        console.log(`🔄 Circuit ${this.name}: HALF_OPEN`);
      } else {
        throw new Error(`Circuit ${this.name} is OPEN`);
      }
    }
    
    try {
      const result = await func();
      this._onSuccess();
      return result;
    } catch (error) {
      this._onFailure();
      throw error;
    }
  }
  
  _onSuccess() {
    if (this.state === 'HALF_OPEN') {
      this.state = 'CLOSED';
      this.failureCount = 0;
      console.log(`✅ Circuit ${this.name}: CLOSED`);
    }
  }
  
  _onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    
    if (this.failureCount >= this.threshold) {
      this.state = 'OPEN';
      console.error(`🔴 Circuit ${this.name}: OPEN`);
    }
  }
  
  getState() {
    return this.state;
  }
}

export const apiCircuit = new CircuitBreaker('backend_api', 3, 15000);

// Integrate into apiClient
import { apiCircuit } from './circuitBreaker';

async request(method, url, data, options) {
  return await apiCircuit.call(async () => {
    // Existing retry logic
    return await this._requestImpl(method, url, data, options);
  });
}
```

**Impact**: After 3 failures, stop trying for 15s. Shows "Backend unavailable" instead of hanging.

---

## Phase 3: Guardian Dashboard (Week 3)

### 3.1 Health Monitor Panel (4 hours) ✅ KEEP

**Why**: See system health at a glance (like bot guardian).

```javascript
// webui/frontend/src/components/GuardianDashboard.js
import { useHealth } from '../store';
import { apiCircuit } from '../utils/circuitBreaker';

function GuardianDashboard() {
  const health = useHealth();
  const [metrics, setMetrics] = useState(null);
  
  useEffect(() => {
    // Fetch 24h metrics
    apiClient.get('/api/metrics/recent?hours=24').then(setMetrics);
  }, []);
  
  return (
    <Card>
      <CardHeader>
        <h2>🛡️ System Health</h2>
        <StatusBadge status={health.status}>
          {health.status}
        </StatusBadge>
      </CardHeader>
      
      <CardContent>
        {/* Backend Components */}
        <Section title="Backend">
          {Object.entries(health.components || {}).map(([name, comp]) => (
            <Row key={name}>
              <span>{name}</span>
              <StatusBadge status={comp.status}>{comp.status}</StatusBadge>
              {comp.latency_ms && <span>{comp.latency_ms}ms</span>}
              {comp.circuit && <CircuitBadge state={comp.circuit} />}
            </Row>
          ))}
        </Section>
        
        {/* Frontend Status */}
        <Section title="Frontend">
          <Row>
            <span>API Circuit</span>
            <CircuitBadge state={apiCircuit.getState()} />
          </Row>
          <Row>
            <span>Data Aggregator</span>
            <StatusBadge status={dataAggregator.isRunning ? 'healthy' : 'stopped'}>
              {dataAggregator.isRunning ? 'Running' : 'Stopped'}
            </StatusBadge>
          </Row>
        </Section>
        
        {/* Metrics Chart (if available) */}
        {metrics && (
          <Section title="24h Trends">
            <MetricsChart data={metrics} />
          </Section>
        )}
      </CardContent>
    </Card>
  );
}
```

**Impact**: Know when Delta API is slow, bot is down, or circuits are open.

---

### 3.2 Command Confirmation Pattern (3 hours) 🎁 NEW

**Why**: All bot actions confirmed via saga. No silent failures.

```javascript
// webui/frontend/src/utils/commandSender.js
import { toast } from 'react-toastify';

export async function sendBotCommand(command, params = {}) {
  const confirmationId = Date.now();
  
  try {
    // Optimistic UI update (instant feedback)
    toast.info(`Sending command: ${command}...`);
    
    // Send command to bot (saga pattern)
    const response = await apiClient.post('/api/bot/command', {
      command,
      params,
      confirmationId,
      timestamp: new Date().toISOString()
    });
    
    if (response.success) {
      toast.success(`✅ ${command} confirmed by bot`);
      return response;
    } else {
      throw new Error(response.error || 'Command failed');
    }
    
  } catch (error) {
    toast.error(`❌ ${command} failed: ${error.message}`);
    throw error;
  }
}

// Usage
async function handleStopBot() {
  try {
    await sendBotCommand('stop', { reason: 'user_request' });
    // Bot will confirm stop via event log
  } catch (error) {
    console.error('Stop command failed:', error);
  }
}
```

**Backend handler**:
```python
@bot_control_bp.route('/api/bot/command', methods=['POST'])
def handle_bot_command():
    data = request.json
    command = data.get('command')
    confirmation_id = data.get('confirmationId')
    
    # Execute via saga (confirmed execution)
    result = bot_controller.execute_command(command, data.get('params'))
    
    # Log to event store
    event_store.append({
        'type': 'COMMAND_EXECUTED',
        'command': command,
        'confirmation_id': confirmation_id,
        'result': result,
        'timestamp': datetime.now().isoformat()
    })
    
    return jsonify({'success': True, 'result': result})
```

**Impact**: UI knows command succeeded. No "did it work?" uncertainty.

---

## Phase 4: Optional Enhancements (Future)

### 4.1 FastAPI Migration (Optional)
**When**: If Flask threading becomes a bottleneck (unlikely for single user)
**Why**: Native async, better performance
**Effort**: 2-3 days

### 4.2 Playwright E2E Tests (Optional)
**When**: After UI stabilizes
**Why**: Catch regressions automatically
**Effort**: 1-2 days for critical flows

### 4.3 Vite Dev Overlay (Optional)
**When**: During active development
**Why**: Better DX (hot reload, faster builds)
**Effort**: 2 hours

---

## Implementation Timeline (Realistic)

### Week 1: Backend Bulletproofing (8 hours)
- **Day 1-2**: Circuit breakers + health checks (5h)
- **Day 3**: Metrics logger + timeout decorator (3h)
- **Validation**: Health endpoint shows real data, circuits open/close

### Week 2: Frontend State Refactor (10 hours)
- **Day 1**: Zustand store + persistence (3h)
- **Day 2-3**: Data aggregator + component migration (5h)
- **Day 4**: Error boundaries + frontend circuit (2h)
- **Validation**: 91 pollers → 1, state survives refresh

### Week 3: Guardian Dashboard (7 hours)
- **Day 1-2**: Health monitor panel (4h)
- **Day 3**: Command confirmation pattern (3h)
- **Validation**: Dashboard shows metrics, commands confirmed

**Total**: ~25 hours (3 focused days or 1 relaxed week)

---

## Success Metrics (Measurable)

### Reliability
- **Target**: Zero UI crashes in 1 week
- **Measure**: Error boundary triggers
- **Baseline**: Unknown

### Performance
- **Target**: API load reduced by 90%
- **Measure**: Backend request logs
- **Baseline**: ~450 requests/min (91 components × 5 calls/min)
- **Expected**: ~50 requests/min (1 aggregator × 5 calls/min)

### Resilience
- **Target**: UI survives backend restart
- **Measure**: Manual test (kill backend, check UI)
- **Baseline**: UI freezes, requires refresh
- **Expected**: Shows "degraded" status, reconnects automatically

### User Experience (You!)
- **Target**: Know system status without debugging
- **Measure**: Guardian dashboard shows health
- **Expected**: See "Delta API slow" instead of discovering it

---

## Rollback Plan

Feature flags for instant disable:

```python
# webui/backend/config.py
FEATURES = {
    'circuit_breakers': os.getenv('FEATURE_CIRCUIT_BREAKERS', 'true').lower() == 'true',
    'health_checks': os.getenv('FEATURE_HEALTH_CHECKS', 'true').lower() == 'true',
    'metrics_logging': os.getenv('FEATURE_METRICS_LOGGING', 'true').lower() == 'true',
}

# Quick disable
if FEATURES['circuit_breakers']:
    # Use circuit breaker
else:
    # Direct call (old behavior)
```

---

## What We Cut (And Why It's OK)

1. ❌ **Custom event store** → Zustand is better maintained
2. ❌ **Playwright E2E** → Health dashboard + manual testing is enough initially
3. ❌ **FastAPI migration** → Flask works fine for single user
4. ❌ **Shadow testing framework** → Use it only for critical refactors
5. ❌ **Complex state recovery** → Zustand persistence is simpler
6. ❌ **WebSocket health checks** → Keep simple reconnect logic
7. ❌ **Rate limiting** → Not needed for single user

---

## Final Architecture (Simple & Bulletproof)

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Mac Mini M4                         │
│                                                              │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │   GridBot       │◄────────┤   WebUI          │          │
│  │   (Event Store) │         │   (Observer)     │          │
│  │                 │         │                  │          │
│  │  • LONG/SHORT   │         │  • Zustand State │          │
│  │  • Saga Pattern │         │  • Data Aggregator│         │
│  │  • Guardian     │         │  • Health Dashboard│        │
│  └────────┬────────┘         └──────────┬───────┘          │
│           │                              │                  │
│           │  ┌──────────────────────────┼─────────┐        │
│           ├──┤   Circuit Breakers       │         │        │
│           │  │   (Backend + Frontend)   │         │        │
│           │  └──────────────────────────┘         │        │
│           │                                        │        │
│           ▼                                        ▼        │
│  ┌─────────────────┐                    ┌──────────────┐   │
│  │  Delta Exchange │                    │  Metrics DB  │   │
│  │  (India API)    │                    │  (SQLite)    │   │
│  └─────────────────┘                    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘

Key: Bot is source of truth, WebUI is read-only observer with command privileges
```

---

## Why This Works for Single User

1. **No over-engineering**: Zustand vs custom event store (90% less code)
2. **High-impact wins**: Data aggregator (90% API reduction)
3. **Maintainable**: Standard libraries, minimal custom code
4. **Scalable later**: Add FastAPI/Playwright when needed
5. **Proven patterns**: Bot brain architecture (already bulletproof)

---

## Next Steps

1. ✅ **Review this simplified plan**
2. 🚀 **Start Week 1**: Circuit breakers + health checks (5 hours)
3. 📊 **Validate**: Health endpoint shows real data
4. 🔄 **Iterate**: Week 2 (state refactor), Week 3 (dashboard)

**Total commitment**: ~25 hours for production-grade reliability  
**ROI**: Immortal UI that mirrors bot brain's robustness 🎯

---

**Ready to make WebUI bulletproof the smart way?** 🚀
