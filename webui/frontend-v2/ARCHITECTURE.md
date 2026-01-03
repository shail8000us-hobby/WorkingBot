# GridBot WebUI v2.0 - Multi-Instrument Architecture

## Design Philosophy

### Core Principles
1. **Instrument Isolation**: Each instrument is a self-contained universe
2. **Failure Locality**: One instrument's failure never affects another
3. **Cognitive Clarity**: UI answers "why should I care?" for every element
4. **Safety First**: Destructive actions require confirmation, reads are instant

### Mental Model

```
TRADER'S MIND                          UI STRUCTURE
─────────────────                      ────────────────────
"Is anything broken?"          →       Global Health Bar (fixed)
"What's my portfolio doing?"   →       Instrument Grid (scrollable)
"Tell me about THIS one"       →       Focus Mode (expandable)
"STOP EVERYTHING"              →       Emergency Kill (always visible)
```

---

## Component Responsibility Map

### Layer 1: Global Control Plane
| Component | Responsibility | Updates |
|-----------|---------------|---------|
| `SystemHealthBeacon` | Overall system status | Every 1s |
| `TradingModeIndicator` | LIVE/SIM/READ-ONLY | On change |
| `DataFreshnessGauge` | Last data received | Every 500ms |
| `AlertSummaryBadge` | Count of warnings | On change |
| `EmergencyKillSwitch` | Stop all trading | User action |

### Layer 2: Instrument Workspace
| Component | Responsibility | Isolation |
|-----------|---------------|-----------|
| `InstrumentCard` | Container for one instrument | Full |
| `ConnectionState` | WebSocket health | Per-instrument |
| `PositionSummary` | Current positions | Per-instrument |
| `PnLDisplay` | Profit/Loss calculation | Per-instrument |
| `StrategyState` | Grid/trading status | Per-instrument |
| `ActionTimeline` | Recent events | Per-instrument |
| `InstrumentActions` | Control buttons | Per-instrument |

### Layer 3: Focus Mode
| Component | Responsibility |
|-----------|---------------|
| `ExpandedInstrumentView` | Full detail layout |
| `PositionsTable` | Detailed position list |
| `GridVisualization` | Visual grid representation |
| `OrderHistory` | Historical orders |
| `RiskMetrics` | Detailed risk analysis |
| `StrategyDecisionLog` | Why bot made decisions |

---

## State Management Strategy

### Why Zustand + Per-Instrument Stores

**Rejected Alternatives:**
- ❌ Redux: Too much boilerplate, global by default
- ❌ Context: Re-renders entire tree on change
- ❌ MobX: Magic is dangerous in trading systems
- ❌ Jotai/Recoil: Atoms are too granular for instrument scope

**Chosen: Zustand with Store Factory Pattern**

Each instrument gets its OWN store instance:

```typescript
// Store factory - creates isolated store per instrument
const createInstrumentStore = (instanceId: string) => create<InstrumentState>((set, get) => ({
  instanceId,
  connectionState: 'disconnected',
  positions: [],
  pnl: { realized: 0, unrealized: 0 },
  gridState: null,
  lastUpdate: null,
  error: null,
  
  // Actions are scoped to THIS instance only
  connect: () => { /* ... */ },
  disconnect: () => { /* ... */ },
  pauseTrading: () => { /* ... */ },
}));

// Registry manages all instrument stores
const instrumentStores = new Map<string, ReturnType<typeof createInstrumentStore>>();

export const getInstrumentStore = (instanceId: string) => {
  if (!instrumentStores.has(instanceId)) {
    instrumentStores.set(instanceId, createInstrumentStore(instanceId));
  }
  return instrumentStores.get(instanceId)!;
};
```

### State Isolation Enforcement

```
┌─────────────────────────────────────────────────────────────┐
│                     GLOBAL STATE                             │
│  • Trading mode (LIVE/SIM)                                  │
│  • User preferences                                          │
│  • System health                                             │
│  • Registered instances list                                 │
│                                                              │
│  NEVER contains instrument-specific data                     │
└─────────────────────────────────────────────────────────────┘
         │
         │ References by instanceId only
         ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ BTCUSD_LONG  │  │ ETHUSD_LONG  │  │ SOLUSD_SHORT │
│ Store        │  │ Store        │  │ Store        │
│              │  │              │  │              │
│ • positions  │  │ • positions  │  │ • positions  │
│ • pnl        │  │ • pnl        │  │ • pnl        │
│ • grid       │  │ • grid       │  │ • grid       │
│ • connection │  │ • connection │  │ • connection │
│ • error      │  │ • error      │  │ • error      │
│              │  │              │  │              │
│ NO CROSS-    │  │ NO CROSS-    │  │ NO CROSS-    │
│ REFERENCES   │  │ REFERENCES   │  │ REFERENCES   │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Backend Contract

### API Design Principles
1. All endpoints are instance-scoped
2. No global mutable state
3. Explicit staleness metadata in every response
4. WebSocket per instrument (or multiplexed with clear channels)

### REST Endpoints

```
GET  /api/v2/instances                     # List all instances
GET  /api/v2/instances/:id                 # Single instance state
GET  /api/v2/instances/:id/positions       # Instance positions
GET  /api/v2/instances/:id/orders          # Instance orders
GET  /api/v2/instances/:id/grid            # Grid configuration
GET  /api/v2/instances/:id/strategy        # Strategy state

POST /api/v2/instances/:id/trading/pause   # Pause trading
POST /api/v2/instances/:id/trading/resume  # Resume trading
POST /api/v2/instances/:id/trading/kill    # Emergency stop

POST /api/v2/global/kill-all              # Emergency stop ALL
GET  /api/v2/global/health                # System health
```

### WebSocket Channels

```
ws://localhost:5557/ws/v2/stream

Subscribe to channels:
{
  "action": "subscribe",
  "channels": [
    "instance:BTCUSD_LONG:positions",
    "instance:BTCUSD_LONG:orders",
    "instance:BTCUSD_LONG:heartbeat",
    "global:health"
  ]
}

Messages include staleness:
{
  "channel": "instance:BTCUSD_LONG:positions",
  "timestamp": 1704067200000,
  "sequence": 12345,
  "stale_after_ms": 5000,
  "data": { ... }
}
```

---

## Failure Scenarios & Recovery

### Scenario 1: Single Instrument Disconnect

```
BTCUSD disconnects. ETH and SOL continue.

UI Response:
┌─────────────────────┐  ┌─────────────────────┐
│ BTCUSD • LONG       │  │ ETHUSD • LONG       │
│ ═══════════════════ │  │ ═══════════════════ │
│ 🔴 DISCONNECTED     │  │ 🟢 Connected        │  ← Others unaffected
│ Since: 2 min ago    │  │                     │
│                     │  │ Position: 3 LONG    │
│ Last known:         │  │ PnL: -$12.30        │
│ Position: 5 LONG    │  │                     │
│ PnL: +$234.50       │  │ [Focus] [⏸ Pause]   │
│                     │  └─────────────────────┘
│ [🔄 Reconnect]      │
│ [⚠️ Close Position] │  ← Clear recovery actions
└─────────────────────┘
```

### Scenario 2: Backend Lag / Stale Data

```
Data older than threshold shows visual warning:

┌─────────────────────┐
│ BTCUSD • LONG       │
│ ═══════════════════ │
│ 🟡 DATA STALE       │  ← Yellow, not red
│ Last update: 8s ago │
│                     │
│ Position: 5 LONG    │  ← Show last known
│ PnL: +$234.50 ⚠️    │  ← Warning on PnL
│                     │
│ Trading continues   │  ← Inform user
│ with caution        │
└─────────────────────┘
```

### Scenario 3: Risk Breach

```
┌─────────────────────┐
│ BTCUSD • LONG       │
│ ═══════════════════ │
│ 🔴 RISK BREACH      │
│ Max loss exceeded   │
│                     │
│ TRADING HALTED      │  ← Automatic stop
│ Positions: CLOSING  │
│                     │
│ Loss: -$500.00      │
│ Limit: -$400.00     │
│                     │
│ [Acknowledge]       │  ← Must acknowledge
│ [View Details]      │
└─────────────────────┘
```

### Scenario 4: Partial Data

```
Positions loaded, but orders failed:

┌─────────────────────┐
│ BTCUSD • LONG       │
│ ═══════════════════ │
│ 🟡 PARTIAL DATA     │
│                     │
│ ✓ Positions: 5 LONG │  ← What we have
│ ✓ PnL: +$234.50     │
│ ✗ Orders: Failed    │  ← What failed
│                     │
│ [🔄 Retry Orders]   │
└─────────────────────┘
```

---

## UI Layout Strategy

### Attention Guidance

1. **Severity-based positioning**: Worst state instruments bubble to top
2. **Color economy**: Only 3 colors mean anything
   - 🟢 Green: All good, no action needed
   - 🟡 Yellow: Attention needed, not urgent
   - 🔴 Red: Action required NOW
3. **Number context**: Every number answers "compared to what?"
   - "+$234.50 today" not "$234.50"
   - "5/20 filled (25%)" not "5"
   - "8s stale (limit: 5s)" not "8s"

### Clutter Prevention

1. **Progressive disclosure**: Summary → Click → Details
2. **Smart defaults**: Hide zero values, empty states are messages
3. **Temporal grouping**: "Recent" (5min) vs "Older" (>5min)
4. **Search/filter**: For >5 instruments, provide quick filter

---

## Safety Design

### Kill Switch Hierarchy

```
┌─────────────────────────────────────────────────────┐
│                 EMERGENCY CONTROLS                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  GLOBAL KILL              Per-Instrument Kill       │
│  ┌─────────────┐          ┌─────────────┐           │
│  │ ⚠️ STOP ALL │          │ ⏹ Stop BTC │           │
│  │             │          │ ⏹ Stop ETH │           │
│  │ Requires:   │          │ ⏹ Stop SOL │           │
│  │ • Click     │          │             │           │
│  │ • Hold 2s   │          │ Single click│           │
│  │ • Confirm   │          │ + confirm   │           │
│  └─────────────┘          └─────────────┘           │
│                                                      │
│  Global = 3 barriers     Single = 2 barriers        │
└─────────────────────────────────────────────────────┘
```

### Action Classification

| Action Type | Barriers | Example |
|-------------|----------|---------|
| Read | 0 | View positions |
| Navigate | 0 | Switch focus |
| Pause | 1 (confirm) | Pause trading |
| Resume | 1 (confirm) | Resume trading |
| Close Position | 2 (confirm + reason) | Close 1 position |
| Kill Instrument | 2 (confirm + hold) | Stop all for 1 |
| Kill All | 3 (confirm + hold + type) | Stop everything |

