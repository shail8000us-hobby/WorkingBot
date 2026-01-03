# GridBot WebUI v2.0 - Complete Architecture Document

## Executive Summary

This document describes a ground-up redesign of the GridBot trading WebUI, built from first principles to be **multi-instrument by default**. The old UI was retrofitted for multiple instruments—this new architecture was designed for it from day one.

---

## 🧠 First Principle: How Traders Think

### Attention Hierarchy

A trader's attention flows through three levels:

| Level | Question | Time Budget | UI Element |
|-------|----------|-------------|------------|
| **Peripheral** | "Is anything on fire?" | <0.5s glance | Global Control Plane |
| **Scanning** | "What's my portfolio doing?" | <3s scan | Instrument Grid |
| **Focused** | "Tell me everything about THIS" | Unlimited | Focus Mode |

### Error Recovery Model

When something goes wrong, traders ask in this order:
1. "Am I losing money?" → PnL must be visible
2. "Is the system working?" → Health must be unambiguous
3. "Can I stop it?" → Kill switch must be accessible
4. "What went wrong?" → Errors must be human-readable

### Cognitive Overload Prevention

- **7±2 Rule**: Maximum 7 instruments visible without scrolling
- **3 Colors Only**: Green (good), Yellow (attention), Red (action required)
- **Numbers with Context**: "+$150 today" not just "150"
- **Destructive = Confirmation**: Actions require appropriate barriers

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GLOBAL CONTROL PLANE                                 │
│  [System Health] [Trading Mode] [Data Freshness] [Alerts] [EMERGENCY STOP]  │
│  ──────────────────────────── NEVER SCROLLS ────────────────────────────────│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────────┐
│       INSTRUMENT GRID           │   │           FOCUS MODE                │
│                                 │   │                                     │
│  ┌─────┐ ┌─────┐ ┌─────┐       │   │  ┌─────────────────────────────┐   │
│  │ BTC │ │ ETH │ │ SOL │       │   │  │     EXPANDED INSTRUMENT     │   │
│  │LONG │ │LONG │ │SHORT│       │   │  │                             │   │
│  └─────┘ └─────┘ └─────┘       │   │  │  • Positions Table          │   │
│                                 │   │  │  • Orders List              │   │
│  Each card is INDEPENDENT       │   │  │  • Grid Visualization       │   │
│  One can fail without           │   │  │  • Risk Metrics             │   │
│  affecting others               │   │  │  • Activity Timeline        │   │
│                                 │   │  │                             │   │
└─────────────────────────────────┘   │  └─────────────────────────────┘   │
                                      │                                     │
                                      │  ┌─────────────────────────────┐   │
                                      │  │ PERIPHERAL: Other symbols   │   │
                                      │  │ BTC ●+$234  ETH ○-$12       │   │
                                      │  └─────────────────────────────┘   │
                                      └─────────────────────────────────────┘
```

---

## 🗂 Folder Structure

### Frontend (`/webui/frontend-v2/`)

```
src/
├── main.tsx                    # Entry point
├── App.tsx                     # Root component
│
├── types/
│   └── index.ts                # All TypeScript types
│
├── stores/
│   ├── globalStore.ts          # Global state (trading mode, instances list)
│   └── instrumentStore.ts      # Per-instrument store factory
│
├── services/
│   ├── api.ts                  # REST API client
│   └── websocket.ts            # WebSocket manager
│
├── components/
│   ├── GlobalControlPlane/
│   │   ├── GlobalControlPlane.tsx
│   │   └── GlobalControlPlane.module.css
│   │
│   ├── InstrumentCard/
│   │   ├── InstrumentCard.tsx
│   │   └── InstrumentCard.module.css
│   │
│   ├── InstrumentGrid/
│   │   ├── InstrumentGrid.tsx
│   │   └── InstrumentGrid.module.css
│   │
│   └── FocusView/
│       ├── FocusView.tsx
│       └── FocusView.module.css
│
└── styles/
    ├── variables.css           # Design tokens
    └── global.css              # Base styles
```

### Backend (`/webui/backend/`)

```
├── api_v2.py                   # V2 API blueprint
├── trading_state.py            # Position/order/PnL data
├── trading_control.py          # Pause/resume/kill actions
├── system_health.py            # Health checks
└── instance_manager.py         # Instance registry (existing)
```

---

## 🔧 State Management Strategy

### Why Zustand + Store Factory

| Alternative | Rejected Because |
|-------------|------------------|
| Redux | Too much boilerplate, global by default |
| React Context | Re-renders entire tree on change |
| MobX | Magic is dangerous in trading systems |
| Jotai/Recoil | Atoms too granular for instrument scope |

### Store Isolation Pattern

```typescript
// Each instrument gets its OWN store instance
const stores = new Map<InstanceId, InstrumentStore>();

const getInstrumentStore = (instanceId) => {
  if (!stores.has(instanceId)) {
    stores.set(instanceId, createInstrumentStore(instanceId));
  }
  return stores.get(instanceId);
};
```

**Key principle**: One instrument's store crash cannot affect another's.

### State Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                     GLOBAL STATE                                 │
│  • Trading mode (LIVE/SIM)                                      │
│  • Instance list (just IDs, no data)                            │
│  • System health                                                 │
│  • Alerts                                                        │
│                                                                  │
│  ❌ NEVER contains instrument-specific data                      │
└─────────────────────────────────────────────────────────────────┘
                              │
           References by instanceId only (string)
                              │
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ BTCUSD_LONG  │  │ ETHUSD_LONG  │  │ SOLUSD_SHORT │
│ Store        │  │ Store        │  │ Store        │
│              │  │              │  │              │
│ • identity   │  │ • identity   │  │ • identity   │
│ • health     │  │ • health     │  │ • health     │
│ • positions  │  │ • positions  │  │ • positions  │
│ • orders     │  │ • orders     │  │ • orders     │
│ • pnl        │  │ • pnl        │  │ • pnl        │
│ • grid       │  │ • grid       │  │ • grid       │
│ • risk       │  │ • risk       │  │ • risk       │
│ • timeline   │  │ • timeline   │  │ • timeline   │
│              │  │              │  │              │
│ ❌ NO CROSS- │  │ ❌ NO CROSS- │  │ ❌ NO CROSS- │
│ REFERENCES   │  │ REFERENCES   │  │ REFERENCES   │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## 🌐 Backend API Contract

### Design Principles

1. **All endpoints are instance-scoped** (no global mutable state)
2. **Every response includes staleness metadata**
3. **Stateless REST for control**
4. **WebSocket for real-time data per instrument**

### REST Endpoints (v2)

```
# Instance Management
GET  /api/v2/instances                     # List all instances
GET  /api/v2/instances/:id                 # Full instance state
GET  /api/v2/instances/:id/positions       # Instance positions
GET  /api/v2/instances/:id/orders          # Instance orders
GET  /api/v2/instances/:id/grid            # Grid configuration

# Trading Actions
POST /api/v2/instances/:id/trading/pause   # Pause trading
POST /api/v2/instances/:id/trading/resume  # Resume trading
POST /api/v2/instances/:id/trading/kill    # Emergency stop

# Global
POST /api/v2/global/kill-all              # EMERGENCY STOP ALL
GET  /api/v2/global/health                # System health
```

### Response Format

```json
{
  "success": true,
  "data": { ... },
  "timestamp": 1704067200000,
  "staleAfterMs": 5000,
  "error": null
}
```

### WebSocket Channels

```javascript
// Subscribe per-instrument
{
  "action": "subscribe",
  "channels": [
    "instance:BTCUSD_LONG:positions",
    "instance:BTCUSD_LONG:orders",
    "instance:BTCUSD_LONG:heartbeat"
  ]
}

// Messages include staleness
{
  "channel": "instance:BTCUSD_LONG:positions",
  "sequence": 12345,
  "timestamp": 1704067200000,
  "staleAfterMs": 5000,
  "data": [...]
}
```

---

## 🚨 Failure Scenarios

### Scenario 1: Single Instrument Disconnect

**What happens:**
- BTCUSD WebSocket disconnects
- ETH and SOL continue operating normally

**UI Response:**
```
BTCUSD card shows:
🔴 DISCONNECTED
Since: 2 min ago
Last known: Position 5 LONG, PnL +$234
[🔄 Reconnect] [⚠️ Close Position]
```

**Other cards:** Completely unaffected

### Scenario 2: Stale Data

**What happens:**
- Data for ETHUSD is >5 seconds old
- Connection still active

**UI Response:**
```
ETHUSD card shows:
🟡 DATA STALE
Last update: 8s ago
Position: 3 LONG (may be outdated)
Trading continues with caution
```

### Scenario 3: Risk Breach

**What happens:**
- SOLUSD exceeds max daily loss

**UI Response:**
```
SOLUSD card shows:
🔴 RISK BREACH
Max loss exceeded

TRADING HALTED
Positions: CLOSING

Loss: -$500.00
Limit: -$400.00

[Acknowledge] [View Details]
```

### Scenario 4: Backend Down

**What happens:**
- Backend API unreachable

**UI Response:**
```
Global Control Plane shows:
🔴 Backend: DOWN

All cards show:
⚠️ Cannot refresh
Last known data displayed
Actions disabled
```

---

## 🔒 Safety Design

### Kill Switch Hierarchy

| Action | Barriers | UX |
|--------|----------|-----|
| View data | 0 | Instant |
| Pause instrument | 1 | Click + confirm |
| Resume instrument | 1 | Click + confirm |
| Kill instrument | 2 | Click + hold 1s + confirm |
| Kill ALL | 3 | Click + hold 2s + type "STOP" |

### Emergency Stop Implementation

```typescript
// Hold-to-confirm pattern
const handleKillButton = () => {
  const HOLD_DURATION = 2000; // 2 seconds
  
  onMouseDown: () => {
    startTimer();
    showProgress();
  }
  
  onProgress100%: () => {
    showConfirmDialog("Type STOP to confirm");
  }
  
  onConfirm: () => {
    api.killAllTrading();
  }
}
```

---

## 🎨 UI Layout Strategy

### Attention Guidance

1. **Worst first**: Cards sorted by severity (critical → warning → normal)
2. **Color economy**: Only 3 colors have meaning
3. **Number context**: Every number answers "compared to what?"

### Clutter Prevention

1. **Progressive disclosure**: Summary first, details on click
2. **Smart defaults**: Hide zero values
3. **Empty states are messages**: "No positions" not blank
4. **Temporal grouping**: Recent (5min) vs Older

---

## ✅ Success Criteria

This WebUI is successful if:

| Criteria | Test |
|----------|------|
| Adding new instrument feels boring | Add AVAXUSD in <30 seconds |
| Removing instrument feels safe | No orphan state, no errors |
| One dying causes zero panic | BTCUSD crash doesn't touch ETH |
| Human understands in 5 seconds | New user can identify problem instruments |
| Future developer can plug in | New strategy without UI rewrite |

---

## 📋 Implementation Checklist

### Phase 1: Core Infrastructure ✅
- [x] Type definitions
- [x] Global store
- [x] Instrument store factory
- [x] API service
- [x] WebSocket manager

### Phase 2: Components ✅
- [x] GlobalControlPlane
- [x] InstrumentCard
- [x] InstrumentGrid
- [x] FocusView

### Phase 3: Backend API
- [x] API v2 blueprint
- [x] Trading state module
- [x] Trading control module
- [x] System health module
- [ ] WebSocket streaming
- [ ] Integration with bot processes

### Phase 4: Integration
- [ ] Connect to real instance data
- [ ] Connect to real position/order data
- [ ] Connect to real PnL calculation
- [ ] End-to-end testing

### Phase 5: Polish
- [ ] Loading states
- [ ] Error boundaries
- [ ] Accessibility audit
- [ ] Performance optimization
- [ ] Mobile responsiveness

---

## 🚀 Getting Started

```bash
# Install dependencies
cd webui/frontend-v2
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

The frontend runs on port 3002 (different from v1's 3001).

---

## 🏗 Migration Path

The v2 frontend is designed to run alongside v1:
- v1: `http://localhost:3001`
- v2: `http://localhost:3002`

Both connect to the same backend on port 5557. The backend serves both v1 and v2 API endpoints.

When v2 is stable:
1. Update nginx/reverse proxy to point to v2
2. Keep v1 available as fallback
3. After confidence period, deprecate v1

---

*This architecture document was created on January 1, 2026.*
*Designed with trader cognition as the primary constraint.*
