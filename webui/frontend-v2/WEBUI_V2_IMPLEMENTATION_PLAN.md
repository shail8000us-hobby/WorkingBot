# WebUI v2 Complete Implementation Plan

> **Created:** January 1, 2026  
> **Goal:** Make v2 WebUI fully functional with GridBot v6.0 multi-instance trading bot  
> **Status:** 🟡 In Progress

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Bot Architecture Understanding](#2-bot-architecture-understanding)
3. [Current v2 State Analysis](#3-current-v2-state-analysis)
4. [Gap Analysis: v1 vs v2](#4-gap-analysis-v1-vs-v2)
5. [API Endpoint Mapping](#5-api-endpoint-mapping)
6. [Implementation Phases](#6-implementation-phases)
7. [Component Specifications](#7-component-specifications)
8. [Data Flow Architecture](#8-data-flow-architecture)
9. [Testing & Validation](#9-testing--validation)

---

## 1. Executive Summary

### The Bot

GridBot is a **v6.0 multi-instance async grid trading bot** for Delta Exchange:
- Each **Instance = Symbol + Mode** (e.g., `BTCUSD_LONG`, `ETHUSD_SHORT`)
- Uses **Actor pattern** for lock-free state management
- **Event-sourced** with SQLite databases per instance
- **Guardian bot** runs as separate process for risk management
- **5-layer monitoring** system for comprehensive visibility

### The Problem

Current v2 WebUI has:
- ✅ 16 panels created with good structure
- ❌ Most panels use **demo/mock data** instead of real APIs
- ❌ Missing multi-instance support (hardcoded to single instance)
- ❌ API endpoints don't match actual backend routes
- ❌ No WebSocket integration for real-time updates
- ❌ Missing critical features (grid visualization, reconciliation, etc.)

### The Solution

This plan provides a systematic approach to:
1. Map all v2 panels to actual backend APIs
2. Implement multi-instance context switching
3. Add WebSocket for real-time updates
4. Complete all missing features from v1

---

## 2. Bot Architecture Understanding

### 2.1 Instance Model (v6.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                        GRIDBOT v6.0                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Instance: BTCUSD_LONG          Instance: BTCUSD_SHORT         │
│   ┌──────────────────────┐       ┌──────────────────────┐       │
│   │ Symbol: BTCUSD       │       │ Symbol: BTCUSD       │       │
│   │ Mode: LONG           │       │ Mode: SHORT          │       │
│   │ Product ID: 139      │       │ Product ID: 139      │       │
│   │ Capital: $7000       │       │ Capital: $5000       │       │
│   │ Grid: 85k-95k        │       │ Grid: 95k-105k       │       │
│   │ DB: bot_events_*.db  │       │ DB: bot_events_*.db  │       │
│   └──────────────────────┘       └──────────────────────┘       │
│                                                                  │
│   Instance: ETHUSD_LONG          Instance: SOLUSD_LONG          │
│   ┌──────────────────────┐       ┌──────────────────────┐       │
│   │ Symbol: ETHUSD       │       │ Symbol: SOLUSD       │       │
│   │ Mode: LONG           │       │ Mode: LONG           │       │
│   │ Product ID: 84       │       │ Product ID: 92       │       │
│   └──────────────────────┘       └──────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Files Per Instance

| File Pattern | Purpose |
|--------------|---------|
| `data/bot_events_{INSTANCE}.db` | Event store (positions, orders, fills) |
| `data/monitoring_snapshot_{INSTANCE}.json` | Real-time monitoring data |
| `logs/gridbot_{INSTANCE}.log` | Log file |
| `data/system_state.json` | Shared system state |

### 2.3 Authority Layers

The bot has 3 independent decision-makers:

| Layer | Question | States |
|-------|----------|--------|
| **HEARTBEAT** | Is system alive? | healthy, unhealthy, dead |
| **GUARDIAN** | Is trading allowed? | GO, STOP, blocked |
| **TRADING** | What does strategy want? | active, paused, hold |

WebUI must show which layer is currently **controlling** the bot.

### 2.4 Key Backend Routes

| Category | Endpoint | Method | Returns |
|----------|----------|--------|---------|
| **Instances** | `/api/instances` | GET | List all instances with config |
| **Positions** | `/api/positions` | GET | Positions with PnL (query: `?instance=`) |
| **Orders** | `/api/orders` | GET | Open orders (query: `?instance=`) |
| **Guardian** | `/api/guardian/status` | GET | Risk status per symbol |
| **Bot Control** | `/api/bot/status` | GET | Bot running status |
| **Bot Control** | `/api/bot/start` | POST | Start bot |
| **Bot Control** | `/api/bot/stop` | POST | Stop bot |
| **Grid Mode** | `/api/bot/grid-mode` | GET/POST | LONG/SHORT mode |
| **Config** | `/api/yaml-config` | GET/POST | YAML configuration |
| **Logs** | `/api/logs` | GET | Log entries |
| **Monitoring** | `/api/monitoring/status` | GET | 5-layer monitoring |
| **PnL** | `/api/pnl-history` | GET | Historical PnL |
| **Safety** | `/api/safety/dashboard` | GET | Unified safety status |

---

## 3. Current v2 State Analysis

### 3.1 Existing Panels

| Panel | Status | Real API | Mock Data | Notes |
|-------|--------|----------|-----------|-------|
| Dashboard (InstrumentGrid) | ✅ Works | Partial | Yes | Uses v2 API |
| PositionsPanel | ✅ Works | No | Yes | Needs real `/api/positions` |
| LogsPanel | ✅ Works | Partial | Yes | Uses `/api/logs` |
| ConfigPanel | ✅ Works | Yes | No | Uses `/api/yaml-config` |
| BotManagementPanel | ✅ Works | Partial | Yes | Needs full PM2 support |
| RSIPanel | ✅ Works | Partial | Yes | Uses `/api/guardian/rsi/status` |
| SystemHealthPanel | ✅ Works | Partial | Yes | Needs `/api/system/health` |
| IntelligencePanel | ✅ Works | No | Yes | Needs AI advisor backend |
| GuardianPanel | ⚠️ Partial | Yes | Yes | Needs proper response mapping |
| BotActionsPanel | ⚠️ Partial | No | Yes | Needs `/api/monitoring/predictive-map` |
| TodoListPanel | ✅ Works | N/A | N/A | localStorage only |
| FileEditorPanel | ⚠️ Partial | Yes | Yes | Uses `/api/file-manager/*` |
| ModeSwitcherPanel | ⚠️ Partial | Yes | Yes | Uses `/api/bot/grid-mode` |
| InstanceManagerPanel | ⚠️ Partial | Yes | Yes | Uses `/api/instances` |
| EmergencyControlsPanel | ⚠️ Partial | Yes | Yes | Uses `/api/emergency/*` |
| PortfolioPanel | ⚠️ Partial | Yes | Yes | Uses `/api/v2/instances` |

### 3.2 Missing Critical Features

| Feature | v1 Has | v2 Has | Priority |
|---------|--------|--------|----------|
| Multi-instance context | ✅ | ❌ | **P0** |
| WebSocket real-time | ✅ | ❌ | **P0** |
| Grid visualization | ✅ | ❌ | **P1** |
| 5-layer monitoring | ✅ | ❌ | **P1** |
| Reconciliation panel | ✅ | ❌ | **P1** |
| PnL chart | ✅ | ❌ | **P1** |
| Volatility chart | ✅ | ❌ | **P2** |
| Bot brain analyzer | ✅ | ❌ | **P2** |
| Strategy editor | ✅ | ❌ | **P3** |
| AI advisor | ✅ | ❌ | **P3** |

---

## 4. Gap Analysis: v1 vs v2

### 4.1 Architecture Gaps

| Aspect | v1 | v2 | Gap |
|--------|----|----|-----|
| State Management | Zustand + DataAggregator | Zustand only | Need DataAggregator service |
| Real-time | WebSocket + Polling | Polling only | Need WebSocket integration |
| Instance Context | InstanceContext provider | None | Need instance switching |
| Error Handling | EnhancedErrorBoundary + Circuit Breaker | Basic try/catch | Need robust error handling |
| API Layer | TypeScript + Zod validation | Raw fetch | Need typed API layer |

### 4.2 Component Gaps

| v1 Component | v2 Equivalent | Status |
|--------------|---------------|--------|
| MonitoringDashboard | ❌ Missing | Need to create |
| GridLevelChart | ❌ Missing | Need to create |
| VolatilityChart | ❌ Missing | Need to create |
| PnLChart | ❌ Missing | Need to create |
| ReconciliationPanel | ❌ Missing | Need to create |
| RiskSafetyDashboard | ❌ Missing | Need to create |
| PM2Panel | BotManagementPanel | Needs PM2 integration |
| SymbolSelector | ❌ Missing | Need to create |
| InstanceContextBar | ❌ Missing | Need to create |

### 4.3 API Integration Gaps

| v2 Panel | Current API Call | Correct API Call | Fix Needed |
|----------|-----------------|------------------|------------|
| PositionsPanel | Mock data | `GET /api/positions?instance=X` | Add real fetch |
| GuardianPanel | `/api/guardian/status` | Same, fix response mapping | Map `running`, `global.risk_status` |
| BotActionsPanel | Mock data | `GET /api/monitoring/predictive-map` | Add real fetch |
| SystemHealthPanel | Mock data | `GET /api/safety/dashboard` | Add real fetch |
| InstanceManagerPanel | `/api/instances` | Same, working | - |
| EmergencyControlsPanel | Various `/api/emergency/*` | Same, working | - |

---

## 5. API Endpoint Mapping

### 5.1 Instance-Aware Endpoints

All these endpoints accept `?instance=BTCUSD_LONG` query parameter:

```typescript
// Primary endpoints for v2
const ENDPOINTS = {
  // Instances
  listInstances: 'GET /api/instances',
  
  // Positions & Orders
  getPositions: 'GET /api/positions?instance={instance}',
  getOrders: 'GET /api/orders?instance={instance}',
  
  // Bot Control
  getBotStatus: 'GET /api/bot/status?instance={instance}',
  startBot: 'POST /api/bot/start',  // Body: { instance: "BTCUSD_LONG" }
  stopBot: 'POST /api/bot/stop',
  restartBot: 'POST /api/bot/restart',
  
  // Grid Mode
  getGridMode: 'GET /api/bot/grid-mode',
  setGridMode: 'POST /api/bot/grid-mode',  // Body: { mode: "LONG" }
  
  // Guardian
  getGuardianStatus: 'GET /api/guardian/status?instance={instance}',
  startGuardian: 'POST /api/guardian/start',
  stopGuardian: 'POST /api/guardian/stop',
  getRsiStatus: 'GET /api/guardian/rsi/status',
  
  // Monitoring (5-layer)
  getMonitoringStatus: 'GET /api/monitoring/status?instance={instance}',
  getPriceHealth: 'GET /api/monitoring/price-health?instance={instance}',
  getPreOrderStats: 'GET /api/monitoring/pre-order-stats?instance={instance}',
  getTpVerification: 'GET /api/monitoring/tp-verification?instance={instance}',
  getAnomalies: 'GET /api/monitoring/anomalies?instance={instance}',
  getPredictiveMap: 'GET /api/monitoring/predictive-map?instance={instance}',
  
  // Safety
  getSafetyDashboard: 'GET /api/safety/dashboard',
  
  // Configuration
  getConfig: 'GET /api/yaml-config?section={section}',
  updateConfig: 'POST /api/yaml-config',  // Body: { path, value }
  
  // Logs
  getLogs: 'GET /api/logs?lines=200&instance={instance}',
  
  // PnL
  getPnlHistory: 'GET /api/pnl-history',
  getPnlSummary: 'GET /api/pnl/summary?instance={instance}',
  
  // Emergency
  emergencyKill: 'POST /api/emergency/kill-all',
  resetGatekeeper: 'POST /api/emergency/reset_gatekeeper',
  forceRestart: 'POST /api/emergency/force_restart',
  
  // Reconciliation
  getReconStatus: 'GET /api/recon/status?instance={instance}',
  getReconTable: 'GET /api/recon/table?instance={instance}',
  runRecon: 'POST /api/recon/run',
  
  // File Manager
  listFiles: 'POST /api/file-manager/list',  // Body: { path }
  readFile: 'POST /api/file-manager/read',   // Body: { path }
  saveFile: 'POST /api/file-manager/save',   // Body: { path, content }
  
  // System
  getSystemHealth: 'GET /api/system/health',
  getFeatureFlags: 'GET /api/system/feature-flags',
};
```

### 5.2 Response Format Reference

```typescript
// Standard response wrapper (varies by endpoint)
interface ApiResponse<T> {
  success?: boolean;
  data?: T;
  error?: string;
  timestamp?: number;
}

// Instances response
interface InstancesResponse {
  instances: Instance[];
  config_version: string;
  total: number;
  enabled_count: number;
}

interface Instance {
  name: string;           // "BTCUSD_LONG"
  symbol: string;         // "BTCUSD"
  mode: "LONG" | "SHORT";
  enabled: boolean;
  product_id: number;
  grid: { lower: number; upper: number; step: number; };
  safety: { max_account_loss_inr: number; };
  rsi: { stop_threshold: number; resume_threshold: number; };
}

// Guardian response
interface GuardianResponse {
  success: boolean;
  running: boolean;
  active: boolean;
  last_check: string;
  global: {
    total_loss_inr: number;
    total_positions: number;
    risk_status: "SAFE" | "WARNING" | "DANGER" | "CRITICAL";
    total_capital_inr: number;
  };
  symbols: Record<string, SymbolGuardianData>;
  health: object;
}

// Positions response
interface PositionsResponse {
  positions: Position[];
  summary: {
    total_positions: number;
    total_pnl_usd: number;
    total_pnl_inr: number;
    portfolio_delta: number;
  };
}
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1) 🔴 **CRITICAL**

#### 1.1 Instance Context System
Create a context provider for instance selection:

```typescript
// src/contexts/InstanceContext.tsx
interface InstanceContextValue {
  instances: Instance[];
  selectedInstance: string | null;  // "BTCUSD_LONG"
  setSelectedInstance: (id: string) => void;
  withInstance: (url: string) => string;  // Adds ?instance= param
  loading: boolean;
  error: string | null;
}
```

**Files to create:**
- `src/contexts/InstanceContext.tsx`
- `src/hooks/useInstance.ts`
- `src/components/InstanceSelector/InstanceSelector.tsx`

#### 1.2 API Service Layer
Create typed API service:

```typescript
// src/services/api.ts - ENHANCE existing file
export const apiService = {
  // Instance-aware fetcher
  async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    if (!response.ok) throw new ApiError(response.status, await response.text());
    return response.json();
  },
  
  // Typed endpoints
  instances: {
    list: () => apiService.fetch<InstancesResponse>('/api/instances'),
  },
  positions: {
    get: (instance: string) => apiService.fetch<PositionsResponse>(`/api/positions?instance=${instance}`),
  },
  // ... etc
};
```

#### 1.3 Data Aggregator Service
Port from v1 for automatic data refresh:

```typescript
// src/services/dataAggregator.ts
class DataAggregator {
  private intervalId: number | null = null;
  
  start(instance: string) {
    this.intervalId = setInterval(() => this.fetchAll(instance), 2000);
  }
  
  stop() {
    if (this.intervalId) clearInterval(this.intervalId);
  }
  
  private async fetchAll(instance: string) {
    const [positions, orders, guardian, monitoring] = await Promise.allSettled([
      apiService.positions.get(instance),
      apiService.orders.get(instance),
      apiService.guardian.status(instance),
      apiService.monitoring.status(instance),
    ]);
    
    // Update Zustand store
    useGlobalStore.getState().bulkUpdate({
      positions: positions.status === 'fulfilled' ? positions.value : null,
      orders: orders.status === 'fulfilled' ? orders.value : null,
      // ...
    });
  }
}
```

#### 1.4 Update Global Store
Enhance Zustand store for multi-instance:

```typescript
// src/stores/globalStore.ts - ENHANCE
interface GlobalState {
  // Instance management
  instances: Instance[];
  selectedInstance: string | null;
  
  // Per-instance data (keyed by instance name)
  instanceData: Record<string, InstanceData>;
  
  // Actions
  setInstances: (instances: Instance[]) => void;
  selectInstance: (instance: string) => void;
  updateInstanceData: (instance: string, data: Partial<InstanceData>) => void;
}

interface InstanceData {
  positions: Position[];
  orders: Order[];
  guardianStatus: GuardianStatus;
  monitoringData: MonitoringData;
  pnl: PnlData;
  lastUpdate: number;
}
```

### Phase 2: Core Panels (Week 2)

#### 2.1 Fix Existing Panels

| Panel | Fix Required |
|-------|--------------|
| **PositionsPanel** | Use real `/api/positions?instance=` API |
| **GuardianPanel** | Map `running`, `global.*` fields correctly |
| **BotActionsPanel** | Use `/api/monitoring/predictive-map` |
| **SystemHealthPanel** | Use `/api/safety/dashboard` |
| **RSIPanel** | Add instance selector |

#### 2.2 Create Missing Panels

**MonitoringDashboard** (5-layer monitoring):
```typescript
// src/components/MonitoringDashboard/MonitoringDashboard.tsx
// Fetches from:
// - /api/monitoring/price-health
// - /api/monitoring/pre-order-stats
// - /api/monitoring/tp-verification
// - /api/monitoring/anomalies
// - /api/monitoring/predictive-map
```

**GridLevelChart** (Visual grid):
```typescript
// src/components/GridLevelChart/GridLevelChart.tsx
// Shows:
// - Grid upper/lower bounds
// - Current price marker
// - Active entry orders
// - Grid levels with step size
```

**ReconciliationPanel**:
```typescript
// src/components/ReconciliationPanel/ReconciliationPanel.tsx
// Fetches from:
// - /api/recon/status
// - /api/recon/table
// Actions:
// - POST /api/recon/run
```

### Phase 3: Real-time Updates (Week 3)

#### 3.1 WebSocket Integration

```typescript
// src/services/websocket.ts - ENHANCE
import { io, Socket } from 'socket.io-client';

class WebSocketManager {
  private socket: Socket | null = null;
  
  connect() {
    this.socket = io(API_BASE, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
    });
    
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
    });
    
    this.socket.on('log_entry', (data) => {
      useGlobalStore.getState().addLogEntry(data);
    });
    
    this.socket.on('positions_update', (data) => {
      useGlobalStore.getState().updatePositions(data);
    });
    
    // Ping for latency measurement
    this.socket.on('pong', ({ latency }) => {
      useGlobalStore.getState().setLatency(latency);
    });
  }
  
  disconnect() {
    this.socket?.disconnect();
  }
}

export const wsManager = new WebSocketManager();
```

#### 3.2 Update Components for Real-time

- LogsPanel: Subscribe to `log_entry` events
- PositionsPanel: Subscribe to `positions_update`
- Add connection status indicator

### Phase 4: Advanced Features (Week 4)

#### 4.1 Charts & Visualization

**PnLChart**:
- Fetch from `/api/pnl-history`
- Use Recharts or Chart.js
- Show cumulative PnL over time

**VolatilityChart**:
- Fetch from volatility API
- Show IV vs RV comparison

#### 4.2 Safety Dashboard

**RiskSafetyDashboard**:
- Fetch from `/api/safety/dashboard`
- Show 6-layer protection status:
  1. Guardian status
  2. Volatility monitoring
  3. PnL loss limits
  4. Position size monitoring
  5. Liquidation protection
  6. System health

#### 4.3 Bot Brain Analyzer

- Fetch from `/api/brain-analyzer/*`
- Visual decision flow
- Scenario simulation

---

## 7. Component Specifications

### 7.1 InstanceSelector

**Location:** `src/components/InstanceSelector/InstanceSelector.tsx`

```typescript
interface Props {
  value: string | null;
  onChange: (instance: string) => void;
  showStatus?: boolean;  // Show running/stopped badge
}
```

**Features:**
- Dropdown with all instances
- Color-coded status (green=running, gray=stopped)
- Mode indicator (LONG=green, SHORT=red)
- Shows enabled/disabled state

### 7.2 MonitoringDashboard

**Location:** `src/components/MonitoringDashboard/MonitoringDashboard.tsx`

**5 Layers:**
1. **Price Health** - Price freshness, staleness warning
2. **Pre-Order Stats** - Order decision statistics
3. **TP Verification** - Take-profit order status
4. **Anomalies** - Detected issues
5. **Predictive Actions** - Next expected bot actions

### 7.3 GridLevelChart

**Location:** `src/components/GridLevelChart/GridLevelChart.tsx`

**Visualization:**
```
Upper: $95,000  ─────────────────────────────
                    │
Grid Level 10       ├── $94,500
Grid Level 9        ├── $94,000
Grid Level 8        ├── $93,500 ● (pending buy)
Grid Level 7        ├── $93,000
Current Price →     ├── $92,750 ═══════════════
Grid Level 6        ├── $92,500 ● (pending buy)
Grid Level 5        ├── $92,000 ▲ (filled position)
Grid Level 4        ├── $91,500 ▲ (filled position)
Grid Level 3        ├── $91,000
Grid Level 2        ├── $90,500
Grid Level 1        ├── $90,000
                    │
Lower: $85,000  ─────────────────────────────
```

### 7.4 ReconciliationPanel

**Location:** `src/components/ReconciliationPanel/ReconciliationPanel.tsx`

**Features:**
- Bot vs Exchange position comparison
- Order memory status
- Auto-heal actions
- Manual resync button

---

## 8. Data Flow Architecture

### 8.1 Overall Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND v2                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │  InstanceContext  │────▶│   Zustand Store   │                 │
│  │  (selected inst) │     │  (global state)   │                 │
│  └──────────────────┘     └────────┬─────────┘                  │
│           │                        │                             │
│           ▼                        ▼                             │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │  DataAggregator   │────▶│   Components     │                 │
│  │  (2s polling)     │     │  (React panels)  │                 │
│  └──────────────────┘     └──────────────────┘                  │
│           │                        │                             │
│           ▼                        ▼                             │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │  API Service      │     │  WebSocket       │                 │
│  │  (HTTP)           │     │  (real-time)     │                 │
│  └────────┬─────────┘     └────────┬─────────┘                  │
│           │                        │                             │
└───────────┼────────────────────────┼─────────────────────────────┘
            │                        │
            ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (Flask)                              │
├─────────────────────────────────────────────────────────────────┤
│  /api/instances  /api/positions  /api/guardian  /api/monitoring │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ config.yaml │  │ SQLite DBs  │  │ JSON files  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Instance Switching Flow

```
User clicks instance in selector
            │
            ▼
InstanceContext.setSelectedInstance("ETHUSD_LONG")
            │
            ├──▶ DataAggregator.switchInstance("ETHUSD_LONG")
            │           │
            │           ▼
            │    Fetch all data for new instance
            │           │
            │           ▼
            │    Zustand store updated
            │
            ▼
All components re-render with new instance data
```

### 8.3 Real-time Update Flow

```
Exchange event (fill, position change)
            │
            ▼
Bot writes to SQLite event store
            │
            ▼
Backend polls event store OR watches file
            │
            ▼
Backend emits WebSocket event
            │
            ▼
Frontend WebSocket receives event
            │
            ▼
Zustand store updated
            │
            ▼
Component re-renders with new data
```

---

## 9. Testing & Validation

### 9.1 Integration Test Checklist

| Test | Expected Result |
|------|-----------------|
| Load `/` with no instances | Shows "No instances configured" |
| Load `/` with instances | Shows instance selector, first instance selected |
| Switch instance | All panels update to new instance data |
| Start bot | Status changes to "running" |
| Stop bot | Status changes to "stopped" |
| Open positions visible | Matches exchange API response |
| PnL calculation | Matches backend calculation |
| Guardian status | Shows GO/STOP correctly |
| RSI threshold | Shows per-mode thresholds |
| Emergency kill | All bots stop, confirmation shown |

### 9.2 API Validation

For each endpoint, verify:
1. ✅ Endpoint exists and returns 200
2. ✅ Response format matches expected interface
3. ✅ Instance query param is respected
4. ✅ Error responses are handled gracefully

### 9.3 Performance Targets

| Metric | Target |
|--------|--------|
| Initial load | < 2 seconds |
| Instance switch | < 500ms |
| Data refresh | Every 2 seconds |
| WebSocket latency | < 100ms |

---

## Appendix A: File Structure

```
src/
├── components/
│   ├── Dashboard/
│   │   ├── InstrumentGrid.tsx       ✅ Exists
│   │   └── MonitoringDashboard.tsx  🆕 Create
│   ├── Positions/
│   │   └── PositionsPanel.tsx       ⚠️ Fix API
│   ├── Guardian/
│   │   └── GuardianPanel.tsx        ⚠️ Fix response mapping
│   ├── Charts/
│   │   ├── GridLevelChart.tsx       🆕 Create
│   │   ├── PnLChart.tsx             🆕 Create
│   │   └── VolatilityChart.tsx      🆕 Create
│   ├── Safety/
│   │   └── RiskSafetyDashboard.tsx  🆕 Create
│   ├── Reconciliation/
│   │   └── ReconciliationPanel.tsx  🆕 Create
│   ├── Instance/
│   │   ├── InstanceSelector.tsx     🆕 Create
│   │   └── InstanceContextBar.tsx   🆕 Create
│   └── ... (existing panels)
├── contexts/
│   └── InstanceContext.tsx          🆕 Create
├── hooks/
│   ├── useInstance.ts               🆕 Create
│   ├── usePositions.ts              🆕 Create
│   └── useGuardian.ts               🆕 Create
├── services/
│   ├── api.ts                       ⚠️ Enhance
│   ├── websocket.ts                 ⚠️ Enhance
│   └── dataAggregator.ts            🆕 Create
└── stores/
    └── globalStore.ts               ⚠️ Enhance
```

---

## Appendix B: Priority Matrix

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Instance context system | Medium | Critical |
| P0 | Fix PositionsPanel API | Low | High |
| P0 | Fix GuardianPanel mapping | Low | High |
| P1 | DataAggregator service | Medium | High |
| P1 | MonitoringDashboard | High | High |
| P1 | GridLevelChart | Medium | Medium |
| P1 | ReconciliationPanel | Medium | High |
| P2 | WebSocket integration | Medium | Medium |
| P2 | PnL/Volatility charts | Medium | Medium |
| P3 | Bot brain analyzer | High | Low |
| P3 | Strategy editor | High | Low |

---

## Next Steps

1. **Immediate (Today):**
   - Create InstanceContext and selector
   - Fix PositionsPanel to use real API
   - Fix GuardianPanel response mapping

2. **This Week:**
   - Implement DataAggregator service
   - Create MonitoringDashboard
   - Add GridLevelChart

3. **Next Week:**
   - WebSocket integration
   - ReconciliationPanel
   - Safety dashboard

---

*This plan will be updated as implementation progresses.*
