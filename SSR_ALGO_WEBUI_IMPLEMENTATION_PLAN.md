# SSR ALGO - Comprehensive WebUI Implementation Plan

**Created:** February 2, 2026  
**Version:** 1.0  
**Status:** Implementation Ready  
**Based on:** SSR_ALGO_ARCHITECTURE.md

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Component Architecture](#2-component-architecture)
3. [State Management Strategy](#3-state-management-strategy)
4. [Real-Time Data Flow](#4-real-time-data-flow)
5. [User Experience Flows](#5-user-experience-flows)
6. [Component Specifications](#6-component-specifications)
7. [Integration Points](#7-integration-points)
8. [Error Handling & Edge Cases](#8-error-handling--edge-cases)
9. [Performance Optimization](#9-performance-optimization)
10. [Testing Strategy](#10-testing-strategy)
11. [Implementation Checklist](#11-implementation-checklist)

---

## 1. Executive Summary

The SSR Algo WebUI provides a comprehensive interface for automated butterfly strategy management with real-time monitoring, multi-session support, and institutional-grade controls.

### Key Requirements
- **Real-time Updates**: WebSocket-based price and position updates
- **Multi-Session Management**: Handle multiple concurrent algo sessions
- **Visual Clarity**: Payoff graphs, position tables, status indicators
- **Responsive Design**: Works on desktop and tablet
- **Error Resilience**: Graceful degradation and recovery
- **Performance**: Handle updates every second without lag

### Technology Stack
- **Frontend**: React 18+ with Hooks
- **State Management**: Context API + Custom Hooks
- **Real-Time**: WebSocket (existing infrastructure)
- **Charts**: Recharts (consistent with existing UI)
- **Styling**: Tailwind CSS (existing system)
- **API Layer**: Axios with interceptors

---

## 2. Component Architecture

### 2.1 Component Hierarchy

```
SSRAlgoDashboard (Container)
├── SSRAlgoContext.Provider (State Management)
│   ├── SSRAlgoHeader
│   │   ├── StatusSummary
│   │   └── GlobalControls
│   │
│   ├── SSRAlgoConfigPanel (Collapsible)
│   │   ├── SessionConfigForm
│   │   ├── StrikeConfigSliders
│   │   ├── CircuitBreakerConfig
│   │   └── PreviewStrikesPanel
│   │
│   ├── SSRAlgoSessionList
│   │   └── SSRAlgoSessionCard[] (Map over active sessions)
│   │       ├── SessionHeader
│   │       │   ├── StatusBadge
│   │       │   ├── SessionMetrics
│   │       │   └── ControlButtons
│   │       │
│   │       ├── SessionTabs
│   │       │   ├── Tab: Overview
│   │       │   │   ├── SSRAlgoPayoffChart
│   │       │   │   ├── PriceZoneIndicator
│   │       │   │   └── QuickStats
│   │       │   │
│   │       │   ├── Tab: Positions
│   │       │   │   ├── SSRAlgoPositionsTable
│   │       │   │   └── ExitOrderStatus
│   │       │   │
│   │       │   ├── Tab: History
│   │       │   │   └── SSRAlgoTriggerHistory
│   │       │   │
│   │       │   └── Tab: Logs
│   │       │       └── SessionEventLog
│   │       │
│   │       └── SessionFooter
│   │           ├── RiskMetrics
│   │           └── PerformanceStats
│   │
│   └── SSRAlgoHistoricalSessions (Collapsible)
│       └── CompletedSessionCard[]
│
└── SSRAlgoNotifications (Toast System)
```

### 2.2 Component Responsibility Matrix

| Component | Responsibilities | Data Sources | Updates |
|-----------|------------------|--------------|---------|
| **SSRAlgoDashboard** | Layout, navigation, global state provider | API + WebSocket | On mount, route change |
| **SSRAlgoConfigPanel** | Session creation, strike preview | API (preview endpoint) | User input |
| **SSRAlgoSessionCard** | Individual session display, controls | Context + WebSocket | Real-time |
| **SSRAlgoPayoffChart** | Payoff visualization, max loss markers | Context + derived state | Price updates |
| **SSRAlgoPositionsTable** | Position grid, exit order status | Context | Position/order updates |
| **SSRAlgoTriggerHistory** | Adjustment timeline | Context | Trigger events |
| **SSRAlgoStatusBanner** | Current state, zone alerts | Context + WebSocket | State changes |

### 2.3 Shared Components (Reusable)

```javascript
// webui/frontend/src/components/ssrAlgo/shared/

StatusBadge.js          // State indicator with colors
MetricCard.js           // Stat display (triggers, P&L, etc.)
StrikePreviewRow.js     // Strike display with target range
PriceZoneBar.js         // Visual price zone indicator
CircuitBreakerAlert.js  // Warning banners for limits
LoadingSpinner.js       // Consistent loading state
ErrorBoundary.js        // Component-level error handling
ConfirmDialog.js        // Action confirmations
```

---

## 3. State Management Strategy

### 3.1 Context Structure

```javascript
// SSRAlgoContext.js

const SSRAlgoContext = createContext({
  // Session Data
  sessions: [],              // All sessions (active + completed)
  activeSessions: [],        // Currently running sessions
  selectedSessionId: null,   // Currently viewed session
  
  // UI State
  isCreating: false,         // Creation form open
  isLoading: false,          // Initial data load
  error: null,               // Global error state
  
  // Real-time Data
  priceData: {},             // { BTC: 76000, ETH: 3500 }
  wsConnected: false,        // WebSocket status
  lastUpdate: null,          // Timestamp
  
  // Actions
  createSession: async (config) => {},
  startSession: async (sessionId) => {},
  pauseSession: async (sessionId) => {},
  resumeSession: async (sessionId) => {},
  stopSession: async (sessionId) => {},
  deleteSession: async (sessionId) => {},
  previewStrikes: async (config) => {},
  
  // Utilities
  getSession: (id) => {},
  getActiveSessionCount: () => {},
  getTotalTriggers: () => {},
});
```

### 3.2 Custom Hooks

```javascript
// hooks/useSSRAlgoSession.js
export const useSSRAlgoSession = (sessionId) => {
  const context = useContext(SSRAlgoContext);
  const session = context.getSession(sessionId);
  
  return {
    session,
    isActive: session?.status !== 'STOPPED',
    canPause: session?.status === 'MONITORING',
    canResume: session?.status === 'PAUSED',
    canStop: ['MONITORING', 'PAUSED'].includes(session?.status),
    currentPrice: context.priceData[session?.underlying],
    inMaxLossZone: checkMaxLossZone(session, context.priceData),
  };
};

// hooks/useSSRAlgoPayoff.js
export const useSSRAlgoPayoff = (sessionId) => {
  const { session, currentPrice } = useSSRAlgoSession(sessionId);
  
  const payoffData = useMemo(() => {
    return calculatePayoffPoints(
      session.positions,
      session.closed_positions,
      currentPrice
    );
  }, [session.positions, session.closed_positions, currentPrice]);
  
  return {
    payoffPoints: payoffData.points,      // Chart data
    maxLossUpper: session.max_loss_upper,
    maxLossLower: session.max_loss_lower,
    currentPnL: payoffData.currentPnL,
    maxProfit: payoffData.maxProfit,
    maxLoss: payoffData.maxLoss,
  };
};

// hooks/useSSRAlgoMonitor.js
export const useSSRAlgoMonitor = (sessionId) => {
  const [zoneStatus, setZoneStatus] = useState({
    inZone: false,
    duration: 0,        // Seconds in zone
    zoneType: null,     // 'upper' | 'lower'
  });
  
  // Monitor price movements and zone entry
  useEffect(() => {
    // Logic to track zone entry time
  }, [sessionId]);
  
  return zoneStatus;
};

// hooks/useSSRAlgoWebSocket.js
export const useSSRAlgoWebSocket = () => {
  const { updatePriceData, updateSessionStatus } = useContext(SSRAlgoContext);
  
  useEffect(() => {
    const ws = connectWebSocket();
    
    ws.on('ssr_algo_price_update', (data) => {
      updatePriceData(data);
    });
    
    ws.on('ssr_algo_status_change', (data) => {
      updateSessionStatus(data.session_id, data.status);
    });
    
    ws.on('ssr_algo_trigger_fired', (data) => {
      // Show notification
      // Update session
    });
    
    return () => ws.disconnect();
  }, []);
};
```

### 3.3 Data Flow Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                      DATA FLOW                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐         ┌──────────────┐         ┌─────────┐  │
│  │ Backend  │────────▶│  WebSocket   │────────▶│ Context │  │
│  │   API    │  REST   │   Updates    │  Events │  State  │  │
│  └──────────┘         └──────────────┘         └────┬────┘  │
│       ▲                                              │       │
│       │                                              ▼       │
│       │ POST                                  ┌─────────────┐│
│  ┌────┴─────┐                                │  Components ││
│  │  User    │◀───────────────────────────────│   (Hooks)   ││
│  │ Actions  │        UI Events               └─────────────┘│
│  └──────────┘                                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Sequence:
1. Component mounts → useSSRAlgoSession() → Read from Context
2. User action → API call → Update Context → Re-render
3. WebSocket event → Update Context → Re-render affected components
4. Price update → Calculate payoff → Update chart (useMemo)
```

---

## 4. Real-Time Data Flow

### 4.1 WebSocket Event Types

```javascript
// Backend emits these events

'ssr_algo_price_update': {
  underlying: 'BTC',
  price: 76234,
  timestamp: '2026-02-02T10:30:00Z'
}

'ssr_algo_status_change': {
  session_id: 'ssr_001_060226_btc',
  old_status: 'EXECUTING_AUTO_LOOP',
  new_status: 'MONITORING',
  timestamp: '2026-02-02T10:30:00Z'
}

'ssr_algo_trigger_fired': {
  session_id: 'ssr_001_060226_btc',
  trigger_id: 1,
  reason: 'max_loss_upper',
  price: 77800,
  timestamp: '2026-02-02T10:30:00Z'
}

'ssr_algo_order_update': {
  session_id: 'ssr_001_060226_btc',
  order_id: 'ord_123',
  symbol: 'C-BTC-76000-060226',
  status: 'filled',
  filled_qty: 1,
  avg_price: 520
}

'ssr_algo_exit_order_filled': {
  session_id: 'ssr_001_060226_btc',
  symbol: 'C-BTC-85000-060226',
  realized_pnl: 45.2
}

'ssr_algo_circuit_breaker': {
  session_id: 'ssr_001_060226_btc',
  breaker_type: 'max_adjustments_per_day',
  limit: 10,
  current: 10
}
```

### 4.2 Update Frequency Strategy

| Data Type | Update Frequency | Method | Priority |
|-----------|------------------|--------|----------|
| Price | 1 second | WebSocket | HIGH |
| Session status | On change | WebSocket | CRITICAL |
| Positions | On fill | WebSocket | HIGH |
| Exit orders | 10 seconds | WebSocket | MEDIUM |
| Payoff calculations | On price update | Client-side | HIGH |
| Historical data | On demand | REST API | LOW |

### 4.3 Optimistic UI Updates

```javascript
// Example: Starting a session

const handleStartSession = async (sessionId) => {
  // 1. Optimistic update (immediate feedback)
  dispatch({
    type: 'UPDATE_SESSION_STATUS',
    payload: { sessionId, status: 'SELECTING_STRIKES' }
  });
  
  try {
    // 2. API call
    const response = await api.post(`/api/ssr_algo/session/${sessionId}/start`);
    
    // 3. Confirm with server data
    dispatch({
      type: 'UPDATE_SESSION',
      payload: response.data.session
    });
    
    showNotification({
      type: 'success',
      message: 'Session started successfully'
    });
    
  } catch (error) {
    // 4. Rollback on error
    dispatch({
      type: 'UPDATE_SESSION_STATUS',
      payload: { sessionId, status: 'IDLE' }
    });
    
    showNotification({
      type: 'error',
      message: `Failed to start session: ${error.message}`
    });
  }
};
```

---

## 5. User Experience Flows

### 5.1 Session Creation Flow

```
┌────────────────────────────────────────────────────────────┐
│                   SESSION CREATION FLOW                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  1. User clicks "Create New Session" button                │
│     └─▶ Config panel expands                               │
│                                                            │
│  2. User selects underlying (BTC/ETH)                      │
│     └─▶ Fetch available expiries for underlying            │
│                                                            │
│  3. User selects expiry                                    │
│     └─▶ Show expiry details (DTE, days remaining)          │
│                                                            │
│  4. User configures parameters:                            │
│     • Auto-loop rounds (default: 2)                        │
│     • Order type (default: SSR)                            │
│     • Time window (default: 15:00-21:00)                   │
│     • OTM buy % (default: 45-49%)                          │
│     • Far OTM sell % (default: 20-30%)                     │
│     • Circuit breakers (optional)                          │
│                                                            │
│  5. User clicks "Preview Strikes"                          │
│     └─▶ Loading spinner                                    │
│     └─▶ API call: /api/ssr_algo/preview_strikes           │
│     └─▶ Display strike preview table:                      │
│         ┌───────────────────────────────────────────────┐  │
│         │ LEG     │ STRIKE │ PREMIUM │ RANGE │ MATCH? │  │
│         │ ATM CE  │ 76000  │ 520     │ -     │ ✓      │  │
│         │ OTM CE  │ 82000  │ 240     │ 234-  │ ✓      │  │
│         │         │        │         │ 255   │        │  │
│         └───────────────────────────────────────────────┘  │
│                                                            │
│  6. User reviews strikes:                                  │
│     a) If satisfied → Click "Create & Start"               │
│        └─▶ Confirmation dialog                             │
│            └─▶ Create session + Start immediately          │
│                                                            │
│     b) If needs adjustment → Modify parameters             │
│        └─▶ Click "Preview Strikes" again                   │
│                                                            │
│     c) If not suitable → Click "Cancel"                    │
│        └─▶ Clear form                                      │
│                                                            │
│  7. Session created:                                       │
│     └─▶ Config panel collapses                             │
│     └─▶ New SessionCard appears in active list             │
│     └─▶ Auto-scroll to new card                            │
│     └─▶ Show success notification                          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 5.2 Monitoring Flow

```
┌────────────────────────────────────────────────────────────┐
│                    MONITORING FLOW                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Session Status: MONITORING                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                            │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Price Zone Indicator (Visual Bar)               │     │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │     │
│  │                                                  │     │
│  │  [MAX LOSS] ◀───────▶ [PROFIT] ◀───────▶ [MAX LOSS] │
│  │    73,566     74,500   76,000   77,500    77,759    │
│  │                           ▲                        │     │
│  │                      Current: 76,231               │     │
│  │                      Status: ✅ Safe Zone          │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  Real-time Updates (every 1 second):                       │
│  • Current price                                           │
│  • Zone status (safe/warning/danger)                       │
│  • Time in zone (if in max loss zone)                      │
│  • Current P&L                                             │
│  • Exit order status                                       │
│                                                            │
│  Warning States:                                           │
│  ┌────────────────────────────────────────────────┐       │
│  │ ⚠️  APPROACHING MAX LOSS ZONE                  │       │
│  │    Price: 77,650 (109 points to upper limit)  │       │
│  │    Monitoring closely...                       │       │
│  └────────────────────────────────────────────────┘       │
│                                                            │
│  Danger States:                                            │
│  ┌────────────────────────────────────────────────┐       │
│  │ 🚨 IN MAX LOSS ZONE                            │       │
│  │    Price: 77,800 (upper limit breached)        │       │
│  │    Time in zone: 3:45 / 10:00 required         │       │
│  │    [Countdown to adjustment trigger]           │       │
│  └────────────────────────────────────────────────┘       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 5.3 Adjustment Trigger Flow

```
┌────────────────────────────────────────────────────────────┐
│                 ADJUSTMENT TRIGGER FLOW                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  1. Price enters max loss zone                             │
│     └─▶ StatusBadge: 🟠 IN MAX LOSS ZONE                  │
│     └─▶ Start countdown timer                              │
│                                                            │
│  2. Price stays > 10 minutes                               │
│     └─▶ Backend triggers adjustment                        │
│     └─▶ WebSocket: 'ssr_algo_trigger_fired'               │
│                                                            │
│  3. Frontend updates:                                      │
│     └─▶ StatusBadge: 🟡 EXECUTING AUTO-LOOP (Round 1/2)  │
│     └─▶ Show progress bar                                  │
│     └─▶ Disable pause/stop buttons                         │
│     └─▶ Toast: "Adjustment triggered at $77,800"           │
│                                                            │
│  4. Auto-loop execution:                                   │
│     └─▶ Round 1: Placing orders...                         │
│     └─▶ Round 1: Waiting for fills...                      │
│     └─▶ Round 1: ✅ Complete                               │
│     └─▶ Round 2: Placing orders...                         │
│     └─▶ Round 2: Waiting for fills...                      │
│     └─▶ Round 2: ✅ Complete                               │
│                                                            │
│  5. Adjustment complete:                                   │
│     └─▶ StatusBadge: 🟢 MONITORING                        │
│     └─▶ Update positions table (new rows added)            │
│     └─▶ Recalculate payoff graph                           │
│     └─▶ Update max loss zones                              │
│     └─▶ Toast: "Adjustment #1 complete. 8 new legs added" │
│     └─▶ Add entry to trigger history                       │
│                                                            │
│  6. New exit orders placed:                                │
│     └─▶ Show exit order status for new SELL legs           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 5.4 Error Recovery Flow

```
┌────────────────────────────────────────────────────────────┐
│                   ERROR RECOVERY FLOW                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Scenario 1: Partial Order Execution                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  └─▶ 6/8 legs filled, 2 rejected                           │
│      ├─▶ Show warning banner                               │
│      │   "⚠️ Partial execution: 6/8 legs filled"          │
│      ├─▶ Continue to monitoring (not fail)                 │
│      ├─▶ Log warning in session event log                  │
│      └─▶ Recalculate payoff with filled positions only     │
│                                                            │
│  Scenario 2: Strike Selection Fails                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  └─▶ No strikes found matching criteria                    │
│      ├─▶ Show error in preview panel                       │
│      │   "❌ No suitable OTM CE strikes found (45-49%)"   │
│      ├─▶ Suggest parameter adjustment                      │
│      │   "Try widening range to 40-50%"                   │
│      └─▶ Don't allow session creation                      │
│                                                            │
│  Scenario 3: WebSocket Disconnection                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  └─▶ Connection lost                                       │
│      ├─▶ Show reconnection banner (non-intrusive)          │
│      │   "⚠️ Reconnecting... (Session continues on server)"│
│      ├─▶ Retry connection (exponential backoff)            │
│      ├─▶ On reconnect: Fetch latest session state          │
│      └─▶ Show success: "✅ Reconnected"                   │
│                                                            │
│  Scenario 4: Circuit Breaker Triggered                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  └─▶ Max adjustments reached                               │
│      ├─▶ Show critical alert                               │
│      │   "🚨 CIRCUIT BREAKER: Max 10 adjustments reached" │
│      ├─▶ Auto-pause session                                │
│      ├─▶ Prevent new adjustments                           │
│      └─▶ Require manual acknowledgment to resume           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 6. Component Specifications

### 6.1 SSRAlgoConfigPanel

**Purpose:** Session creation with live strike preview

**Props:**
```javascript
{
  onCreateSession: (config) => void,
  onCancel: () => void,
  isCreating: boolean
}
```

**State:**
```javascript
{
  underlying: 'BTC' | 'ETH',
  expiry: string,        // 'DDMMYY'
  autoLoopRounds: number,
  orderType: string,
  startTime: string,
  endTime: string,
  strikeConfig: {
    otm_buy_percent_min: number,
    otm_buy_percent_max: number,
    far_otm_percent_min: number,
    far_otm_percent_max: number
  },
  circuitBreakers: {
    max_adjustments_per_day: number,
    max_adjustments_per_session: number,
    daily_loss_limit: number,
    cooldown_minutes: number
  },
  strikePreview: null | StrikePreviewData,
  isPreviewingStrikes: boolean
}
```

**Key Features:**
- Real-time parameter validation
- Strike preview on-demand
- Tooltips for all parameters
- Default value suggestions
- Form persistence (localStorage)

**Layout:**
```jsx
<div className="config-panel">
  <div className="form-section">
    <h3>Basic Configuration</h3>
    <div className="form-grid">
      <Select label="Underlying" options={['BTC', 'ETH']} />
      <Select label="Expiry" options={expiries} />
      <Input label="Auto-Loop Rounds" type="number" />
      <Select label="Order Type" options={orderTypes} />
      <TimeRange label="Trading Window" />
    </div>
  </div>
  
  <div className="form-section">
    <h3>Strike Selection (% of ATM Premium)</h3>
    <RangeSlider 
      label="OTM Buy Range"
      min={40} max={55}
      defaultValue={[45, 49]}
    />
    <RangeSlider 
      label="Far OTM Sell Range"
      min={15} max={35}
      defaultValue={[20, 30]}
    />
  </div>
  
  <div className="form-section collapsible">
    <h3>Circuit Breakers (Optional)</h3>
    <Input label="Max Adjustments/Day" />
    <Input label="Daily Loss Limit ($)" />
    <Input label="Cooldown (minutes)" />
  </div>
  
  <div className="preview-section">
    <button onClick={handlePreviewStrikes}>Preview Strikes</button>
    {strikePreview && <StrikePreviewTable data={strikePreview} />}
  </div>
  
  <div className="action-buttons">
    <button onClick={handleCancel}>Cancel</button>
    <button onClick={handleCreate} disabled={!strikePreview}>
      Create & Start Session
    </button>
  </div>
</div>
```

### 6.2 SSRAlgoSessionCard

**Purpose:** Display and control individual session

**Props:**
```javascript
{
  sessionId: string,
  compact: boolean  // Compact view for multiple sessions
}
```

**State:**
```javascript
{
  activeTab: 'overview' | 'positions' | 'history' | 'logs',
  isExpanded: boolean,
  showStopConfirm: boolean
}
```

**Key Features:**
- Real-time status updates
- Tab-based navigation
- Collapsible for space
- Context menu for actions
- Export session data

**Layout:**
```jsx
<Card className={`session-card ${status.toLowerCase()}`}>
  <CardHeader>
    <div className="header-left">
      <StatusBadge status={status} />
      <h3>{underlying} • {expiry} • Session #{sessionId}</h3>
    </div>
    <div className="header-right">
      <QuickStats 
        triggers={trigger_count}
        positions={totalLegs}
        uptime={uptime}
        pnl={currentPnL}
      />
      <ControlButtons 
        onPause={handlePause}
        onResume={handleResume}
        onStop={handleStop}
        status={status}
      />
    </div>
  </CardHeader>
  
  <Tabs activeTab={activeTab} onChange={setActiveTab}>
    <Tab label="Overview" icon={LayoutDashboard}>
      <PriceZoneIndicator session={session} currentPrice={price} />
      <SSRAlgoPayoffChart sessionId={sessionId} height={300} />
      <QuickMetrics session={session} />
    </Tab>
    
    <Tab label="Positions" icon={Table} badge={totalLegs}>
      <SSRAlgoPositionsTable sessionId={sessionId} />
      <ExitOrdersPanel sessionId={sessionId} />
    </Tab>
    
    <Tab label="History" icon={Clock} badge={trigger_count}>
      <SSRAlgoTriggerHistory sessionId={sessionId} />
    </Tab>
    
    <Tab label="Logs" icon={FileText}>
      <SessionEventLog sessionId={sessionId} />
    </Tab>
  </Tabs>
</Card>
```

### 6.3 SSRAlgoPayoffChart

**Purpose:** Visualize payoff with max loss zones

**Props:**
```javascript
{
  sessionId: string,
  height: number,
  showControls: boolean
}
```

**Features:**
- Payoff curve (P&L vs price)
- Max loss zone markers (vertical lines)
- Current price indicator (moving dot)
- Breakeven points
- Max profit/loss annotations
- Zoom/pan controls
- Export chart image

**Chart Elements:**
```javascript
{
  x-axis: Price points (spot - 20% to spot + 20%),
  y-axis: P&L in USD,
  
  Series: [
    {
      name: 'Payoff',
      data: payoffPoints,
      color: 'gradient(green to red)',
      lineWidth: 3
    }
  ],
  
  Markers: [
    {
      type: 'vertical-line',
      x: max_loss_lower,
      color: 'red',
      label: 'Max Loss Lower',
      dashArray: '5,5'
    },
    {
      type: 'vertical-line',
      x: max_loss_upper,
      color: 'red',
      label: 'Max Loss Upper',
      dashArray: '5,5'
    },
    {
      type: 'dot',
      x: currentPrice,
      y: currentPnL,
      color: 'blue',
      size: 10,
      animated: true
    }
  ],
  
  Zones: [
    {
      x: [0, max_loss_lower],
      fill: 'rgba(255, 0, 0, 0.1)',
      label: 'Danger Zone'
    },
    {
      x: [max_loss_lower, max_loss_upper],
      fill: 'rgba(0, 255, 0, 0.1)',
      label: 'Profit Zone'
    },
    {
      x: [max_loss_upper, Infinity],
      fill: 'rgba(255, 0, 0, 0.1)',
      label: 'Danger Zone'
    }
  ]
}
```

### 6.4 SSRAlgoPositionsTable

**Purpose:** Display all position legs with status

**Props:**
```javascript
{
  sessionId: string,
  groupByTrigger: boolean
}
```

**Columns:**
```javascript
[
  { key: 'trigger_id', label: 'Adj#', sortable: true },
  { key: 'leg_type', label: 'Leg', sortable: true },
  { key: 'strike', label: 'Strike', sortable: true },
  { key: 'premium', label: 'Premium', sortable: true },
  { key: 'qty', label: 'Qty', sortable: false },
  { key: 'side', label: 'Side', render: (val) => <Badge>{val}</Badge> },
  { key: 'status', label: 'Status', render: (val) => <StatusDot>{val}</StatusDot> },
  { key: 'exit_order', label: 'Exit', render: (pos) => <ExitOrderStatus position={pos} /> },
  { key: 'pnl', label: 'P&L', render: (val) => <PnLCell value={val} /> }
]
```

**Features:**
- Group by adjustment trigger
- Sort by any column
- Highlight filled/pending
- Exit order status indicator
- Click row to see details
- Export to CSV

**Row Styling:**
```javascript
{
  'SELL leg': 'bg-red-50',
  'BUY leg': 'bg-green-50',
  'Exit order pending': 'border-l-4 border-amber-500',
  'Exit order filled': 'opacity-60'
}
```

### 6.5 SSRAlgoTriggerHistory

**Purpose:** Timeline of all adjustment triggers

**Props:**
```javascript
{
  sessionId: string
}
```

**Display Format:**
```jsx
<Timeline>
  {triggers.map(trigger => (
    <TimelineItem key={trigger.trigger_id}>
      <TimelineDot color={trigger.success ? 'green' : 'red'} />
      <TimelineContent>
        <div className="trigger-header">
          <span className="trigger-id">Adjustment #{trigger.trigger_id}</span>
          <span className="trigger-time">{formatTime(trigger.timestamp)}</span>
        </div>
        <div className="trigger-details">
          <p><strong>Reason:</strong> Price hit {trigger.zone_type} max loss zone</p>
          <p><strong>Trigger Price:</strong> ${trigger.price}</p>
          <p><strong>New ATM Strike:</strong> {trigger.new_atm_strike}</p>
          <p><strong>Legs Added:</strong> 8</p>
          <p><strong>Rounds Executed:</strong> {trigger.rounds_completed}/{trigger.rounds_total}</p>
        </div>
        <button onClick={() => showTriggerDetails(trigger)}>
          View Details
        </button>
      </TimelineContent>
    </TimelineItem>
  ))}
</Timeline>
```

### 6.6 PriceZoneIndicator

**Purpose:** Visual price position relative to zones

**Props:**
```javascript
{
  session: SessionData,
  currentPrice: number
}
```

**Visual Design:**
```
┌────────────────────────────────────────────────────────────┐
│  PRICE ZONE INDICATOR                                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Max Loss Zone        Profit Zone        Max Loss Zone    │
│  ┌─────────────┬──────────────────────┬─────────────┐     │
│  │   DANGER    │       SAFE           │   DANGER    │     │
│  │   [░░░]     │   [▓▓▓▓▓▓▓]         │   [░░░]     │     │
│  │             │         ▲            │             │     │
│  └─────────────┴─────────┼────────────┴─────────────┘     │
│  73,566       74,500   76,231 (Current)  77,500   77,759  │
│                                                            │
│  Status: ✅ SAFE ZONE                                      │
│  Distance to Upper Limit: 1,528 points (2.0%)             │
│  Distance to Lower Limit: 2,665 points (3.5%)             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**States:**
```javascript
{
  'safe': { 
    color: 'green', 
    icon: '✅', 
    message: 'Price in profit zone'
  },
  'warning_upper': { 
    color: 'orange', 
    icon: '⚠️', 
    message: 'Approaching upper max loss zone'
  },
  'warning_lower': { 
    color: 'orange', 
    icon: '⚠️', 
    message: 'Approaching lower max loss zone'
  },
  'danger_upper': { 
    color: 'red', 
    icon: '🚨', 
    message: 'IN UPPER MAX LOSS ZONE',
    action: 'Countdown to adjustment'
  },
  'danger_lower': { 
    color: 'red', 
    icon: '🚨', 
    message: 'IN LOWER MAX LOSS ZONE',
    action: 'Countdown to adjustment'
  }
}
```

---

## 7. Integration Points

### 7.1 Backend API Integration

**API Client Setup:**
```javascript
// utils/api/ssrAlgoApi.js

import axios from 'axios';
import { getAuthToken } from '../auth';

const ssrAlgoApi = axios.create({
  baseURL: '/api/ssr_algo',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor
ssrAlgoApi.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
ssrAlgoApi.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || error.message;
    console.error('SSR Algo API Error:', message);
    
    // Global error handling
    if (error.response?.status === 401) {
      // Redirect to login
    }
    
    return Promise.reject({ message, status: error.response?.status });
  }
);

export default ssrAlgoApi;
```

**API Methods:**
```javascript
// utils/api/ssrAlgoService.js

export const ssrAlgoService = {
  // Sessions
  getSessions: () => 
    ssrAlgoApi.get('/sessions'),
  
  getSession: (sessionId) => 
    ssrAlgoApi.get(`/session/${sessionId}`),
  
  createSession: (config) => 
    ssrAlgoApi.post('/session/create', config),
  
  startSession: (sessionId) => 
    ssrAlgoApi.post(`/session/${sessionId}/start`),
  
  pauseSession: (sessionId) => 
    ssrAlgoApi.post(`/session/${sessionId}/pause`),
  
  resumeSession: (sessionId) => 
    ssrAlgoApi.post(`/session/${sessionId}/resume`),
  
  stopSession: (sessionId) => 
    ssrAlgoApi.post(`/session/${sessionId}/stop`),
  
  // Strike preview
  previewStrikes: (config) => 
    ssrAlgoApi.post('/preview_strikes', config),
  
  // Monitoring
  getStatus: () => 
    ssrAlgoApi.get('/status'),
  
  getPayoff: (sessionId) => 
    ssrAlgoApi.get(`/session/${sessionId}/payoff`),
};
```

### 7.2 WebSocket Integration

**WebSocket Manager:**
```javascript
// utils/websocket/ssrAlgoWebSocket.js

import { io } from 'socket.io-client';

class SSRAlgoWebSocket {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
  }
  
  connect() {
    if (this.socket?.connected) return;
    
    this.socket = io('/ssr_algo', {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Infinity
    });
    
    this.socket.on('connect', () => {
      console.log('SSR Algo WebSocket connected');
      this.emit('connection_status', { connected: true });
    });
    
    this.socket.on('disconnect', () => {
      console.log('SSR Algo WebSocket disconnected');
      this.emit('connection_status', { connected: false });
    });
    
    // Register event handlers
    this.socket.on('ssr_algo_price_update', (data) => 
      this.emit('price_update', data));
    
    this.socket.on('ssr_algo_status_change', (data) => 
      this.emit('status_change', data));
    
    this.socket.on('ssr_algo_trigger_fired', (data) => 
      this.emit('trigger_fired', data));
    
    this.socket.on('ssr_algo_order_update', (data) => 
      this.emit('order_update', data));
    
    this.socket.on('ssr_algo_exit_order_filled', (data) => 
      this.emit('exit_order_filled', data));
    
    this.socket.on('ssr_algo_circuit_breaker', (data) => 
      this.emit('circuit_breaker', data));
  }
  
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }
  
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
    
    return () => {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    };
  }
  
  emit(event, data) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(callback => callback(data));
  }
}

export default new SSRAlgoWebSocket();
```

### 7.3 Existing System Integration

**Integration with Existing Components:**

```javascript
// App.js - Add navigation item

const sidebarSections = [
  // ... existing sections
  {
    id: 'ssr_algo',
    label: 'SSR ALGO',
    icon: Target,  // lucide-react icon
    component: lazy(() => import('./components/ssrAlgo/SSRAlgoDashboard')),
    description: 'Automated butterfly adjustment algorithm',
    badge: () => {
      const { activeSessions } = useSSRAlgoContext();
      return activeSessions.length > 0 ? activeSessions.length : null;
    }
  }
];
```

**Shared Utilities:**
```javascript
// Use existing payoff calculation engine
import { calculatePayoff } from '../utils/adjustmentPayoffEngine';

// Use existing WebSocket if available
import { useWebSocket } from '../contexts/WebSocketContext';

// Use existing notification system
import { useNotification } from '../contexts/NotificationContext';

// Use existing theme
import { useTheme } from '../contexts/ThemeContext';
```

---

## 8. Error Handling & Edge Cases

### 8.1 Error Boundary Implementation

```javascript
// components/ssrAlgo/SSRAlgoErrorBoundary.js

class SSRAlgoErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null,
      errorInfo: null 
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('SSR Algo Error:', error, errorInfo);
    
    // Log to monitoring service
    logErrorToService({
      component: 'SSRAlgo',
      error: error.toString(),
      componentStack: errorInfo.componentStack
    });
    
    this.setState({ error, errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-content">
            <h2>⚠️ SSR Algo Error</h2>
            <p>Something went wrong in the SSR Algo dashboard.</p>
            <details>
              <summary>Error Details</summary>
              <pre>{this.state.error?.toString()}</pre>
              <pre>{this.state.errorInfo?.componentStack}</pre>
            </details>
            <div className="error-actions">
              <button onClick={this.handleReset}>Reload Dashboard</button>
              <button onClick={() => window.history.back()}>Go Back</button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
```

### 8.2 API Error Handling

```javascript
// Error handling patterns

// 1. Network Error
try {
  const session = await ssrAlgoService.getSession(sessionId);
} catch (error) {
  if (!navigator.onLine) {
    showNotification({
      type: 'error',
      message: 'No internet connection. Please check your network.',
      duration: 0  // Stay until dismissed
    });
  } else {
    showNotification({
      type: 'error',
      message: `Failed to load session: ${error.message}`
    });
  }
}

// 2. Validation Error
try {
  await ssrAlgoService.createSession(config);
} catch (error) {
  if (error.status === 400) {
    // Show field-level errors
    setFieldErrors(error.data.errors);
  }
}

// 3. Server Error
try {
  await ssrAlgoService.startSession(sessionId);
} catch (error) {
  if (error.status === 500) {
    showNotification({
      type: 'error',
      message: 'Server error. Session continues but UI may be stale. Refreshing...'
    });
    setTimeout(() => window.location.reload(), 3000);
  }
}

// 4. Timeout Error
const timeoutPromise = (promise, ms) => {
  return Promise.race([
    promise,
    new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Request timeout')), ms)
    )
  ]);
};

try {
  await timeoutPromise(ssrAlgoService.previewStrikes(config), 15000);
} catch (error) {
  if (error.message === 'Request timeout') {
    showNotification({
      type: 'warning',
      message: 'Strike preview is taking longer than usual. Please wait...'
    });
  }
}
```

### 8.3 Edge Case Handling

| Edge Case | Detection | Handling |
|-----------|-----------|----------|
| **No strikes match criteria** | Preview API returns empty | Show error with suggestions to widen ranges |
| **Market closed** | Order placement fails | Show warning, queue for next trading session |
| **Insufficient margin** | Order rejection | Show error, suggest reducing lots |
| **Duplicate session** | Same expiry already running | Confirm if user wants multiple on same expiry |
| **Expiry in < 1 hour** | Check time to expiry | Block creation, show warning |
| **Price gap (circuit breaker)** | Large price movement | Auto-pause, alert user |
| **Websocket lag** | No updates > 30 seconds | Show stale data warning |
| **Session stuck in EXECUTING** | Status unchanged > 5 minutes | Show manual intervention button |
| **Backend restart** | All sessions offline | Auto-refresh, restore monitors |
| **Concurrent stop/pause** | Multiple button clicks | Disable buttons during API call |

---

## 9. Performance Optimization

### 9.1 Rendering Optimization

**Memoization Strategy:**
```javascript
// Memoize expensive calculations

const PayoffChart = memo(({ sessionId }) => {
  const { session, currentPrice } = useSSRAlgoSession(sessionId);
  
  // Only recalculate when positions or price change
  const payoffData = useMemo(() => {
    return calculatePayoffPoints(
      session.positions,
      session.closed_positions,
      currentPrice
    );
  }, [session.positions, session.closed_positions, currentPrice]);
  
  // Only re-render chart when data actually changes
  return <LineChart data={payoffData} />;
}, (prevProps, nextProps) => {
  // Custom comparison
  return prevProps.sessionId === nextProps.sessionId;
});

// Memoize context selectors
const useSessionSelector = (sessionId, selector) => {
  const context = useContext(SSRAlgoContext);
  
  return useMemo(() => {
    const session = context.getSession(sessionId);
    return selector(session);
  }, [sessionId, context.sessions]);
};

// Usage
const status = useSessionSelector(sessionId, (session) => session?.status);
```

**Virtual Scrolling for Long Lists:**
```javascript
// Use react-window for positions table with many rows

import { FixedSizeList as List } from 'react-window';

const PositionsTable = ({ positions }) => {
  const Row = ({ index, style }) => (
    <div style={style}>
      <PositionRow position={positions[index]} />
    </div>
  );
  
  return (
    <List
      height={400}
      itemCount={positions.length}
      itemSize={50}
      width="100%"
    >
      {Row}
    </List>
  );
};
```

### 9.2 Data Fetching Optimization

**Debouncing and Throttling:**
```javascript
// Throttle price updates to max 1/second
const throttledPriceUpdate = useCallback(
  throttle((price) => {
    dispatch({ type: 'UPDATE_PRICE', payload: price });
  }, 1000),
  []
);

// Debounce strike preview API calls
const debouncedPreview = useCallback(
  debounce((config) => {
    previewStrikes(config);
  }, 500),
  []
);
```

**Lazy Loading:**
```javascript
// Lazy load historical sessions
const [showHistorical, setShowHistorical] = useState(false);
const [historicalSessions, setHistoricalSessions] = useState(null);

const loadHistoricalSessions = async () => {
  if (!historicalSessions) {
    const data = await ssrAlgoService.getHistoricalSessions();
    setHistoricalSessions(data);
  }
  setShowHistorical(true);
};
```

**Pagination:**
```javascript
// Paginate trigger history
const usePaginatedTriggers = (sessionId) => {
  const [page, setPage] = useState(1);
  const pageSize = 10;
  
  const { session } = useSSRAlgoSession(sessionId);
  const triggers = session?.trigger_history || [];
  
  const paginatedTriggers = useMemo(() => {
    const start = (page - 1) * pageSize;
    return triggers.slice(start, start + pageSize);
  }, [triggers, page]);
  
  return {
    triggers: paginatedTriggers,
    page,
    setPage,
    totalPages: Math.ceil(triggers.length / pageSize)
  };
};
```

### 9.3 Bundle Size Optimization

**Code Splitting:**
```javascript
// Lazy load heavy components
const SSRAlgoPayoffChart = lazy(() => 
  import('./SSRAlgoPayoffChart')
);

const SSRAlgoTriggerHistory = lazy(() => 
  import('./SSRAlgoTriggerHistory')
);

// Use Suspense
<Suspense fallback={<LoadingSpinner />}>
  <SSRAlgoPayoffChart sessionId={sessionId} />
</Suspense>
```

**Tree Shaking:**
```javascript
// Import only what's needed
import { calculatePayoff } from '../utils/payoff'; // ✅
// Not: import * as utils from '../utils'; // ❌
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Component Testing:**
```javascript
// SSRAlgoSessionCard.test.js

describe('SSRAlgoSessionCard', () => {
  it('renders session info correctly', () => {
    const session = createMockSession({ status: 'MONITORING' });
    render(<SSRAlgoSessionCard session={session} />);
    
    expect(screen.getByText('MONITORING')).toBeInTheDocument();
    expect(screen.getByText(session.underlying)).toBeInTheDocument();
  });
  
  it('shows pause button when monitoring', () => {
    const session = createMockSession({ status: 'MONITORING' });
    render(<SSRAlgoSessionCard session={session} />);
    
    expect(screen.getByText('Pause')).toBeEnabled();
  });
  
  it('disables stop button when executing', () => {
    const session = createMockSession({ status: 'EXECUTING_AUTO_LOOP' });
    render(<SSRAlgoSessionCard session={session} />);
    
    expect(screen.getByText('Stop')).toBeDisabled();
  });
  
  it('calls stop API on stop button click', async () => {
    const onStop = jest.fn();
    const session = createMockSession({ status: 'MONITORING' });
    
    render(<SSRAlgoSessionCard session={session} onStop={onStop} />);
    
    fireEvent.click(screen.getByText('Stop'));
    fireEvent.click(screen.getByText('Confirm')); // Confirmation dialog
    
    await waitFor(() => {
      expect(onStop).toHaveBeenCalledWith(session.session_id);
    });
  });
});
```

**Hook Testing:**
```javascript
// useSSRAlgoPayoff.test.js

describe('useSSRAlgoPayoff', () => {
  it('calculates payoff correctly', () => {
    const { result } = renderHook(() => 
      useSSRAlgoPayoff(mockSessionId)
    );
    
    expect(result.current.currentPnL).toBeCloseTo(1250.5);
    expect(result.current.maxLoss).toBeCloseTo(-5000);
    expect(result.current.maxProfit).toBeCloseTo(8000);
  });
  
  it('updates payoff when price changes', () => {
    const { result, rerender } = renderHook(() => 
      useSSRAlgoPayoff(mockSessionId)
    );
    
    const initialPnL = result.current.currentPnL;
    
    // Update price in context
    act(() => {
      updatePrice('BTC', 78000);
    });
    
    rerender();
    
    expect(result.current.currentPnL).not.toBe(initialPnL);
  });
});
```

### 10.2 Integration Tests

**API Integration:**
```javascript
// ssrAlgoApi.integration.test.js

describe('SSR Algo API Integration', () => {
  let mockServer;
  
  beforeAll(() => {
    mockServer = setupMockServer();
  });
  
  afterAll(() => {
    mockServer.close();
  });
  
  it('creates session and receives session ID', async () => {
    const config = createMockConfig();
    const response = await ssrAlgoService.createSession(config);
    
    expect(response.session_id).toBeDefined();
    expect(response.strikes_preview).toBeDefined();
  });
  
  it('handles API errors gracefully', async () => {
    mockServer.mockError('/api/ssr_algo/session/invalid', 404);
    
    await expect(
      ssrAlgoService.getSession('invalid')
    ).rejects.toThrow('Session not found');
  });
});
```

**WebSocket Integration:**
```javascript
// ssrAlgoWebSocket.integration.test.js

describe('SSR Algo WebSocket Integration', () => {
  let ws;
  
  beforeEach(() => {
    ws = createMockWebSocket();
  });
  
  it('receives price updates', (done) => {
    ws.on('price_update', (data) => {
      expect(data.underlying).toBe('BTC');
      expect(data.price).toBeGreaterThan(0);
      done();
    });
    
    ws.emit('ssr_algo_price_update', {
      underlying: 'BTC',
      price: 76000
    });
  });
  
  it('handles trigger events', (done) => {
    ws.on('trigger_fired', (data) => {
      expect(data.trigger_id).toBe(1);
      expect(data.reason).toBe('max_loss_upper');
      done();
    });
    
    ws.emit('ssr_algo_trigger_fired', mockTriggerData);
  });
});
```

### 10.3 E2E Tests

**User Flow Testing:**
```javascript
// ssrAlgo.e2e.test.js

describe('SSR Algo E2E', () => {
  it('complete session creation flow', async () => {
    // 1. Navigate to SSR Algo
    await page.goto('/ssr_algo');
    
    // 2. Click create new session
    await page.click('button[data-testid="create-session"]');
    
    // 3. Fill form
    await page.select('select[name="underlying"]', 'BTC');
    await page.select('select[name="expiry"]', '060226');
    await page.type('input[name="autoLoopRounds"]', '2');
    
    // 4. Preview strikes
    await page.click('button[data-testid="preview-strikes"]');
    await page.waitForSelector('.strike-preview-table');
    
    // 5. Verify preview shows
    const strikes = await page.$$('.strike-preview-row');
    expect(strikes.length).toBe(6);
    
    // 6. Create session
    await page.click('button[data-testid="create-and-start"]');
    
    // 7. Wait for confirmation
    await page.waitForSelector('.session-card', { timeout: 5000 });
    
    // 8. Verify session appears
    const sessionCard = await page.$('.session-card');
    expect(sessionCard).toBeTruthy();
  });
  
  it('pauses and resumes session', async () => {
    // Setup: Create a running session
    const sessionId = await createTestSession();
    await page.goto(`/ssr_algo?session=${sessionId}`);
    
    // Pause
    await page.click('button[data-testid="pause-button"]');
    await page.waitForSelector('.status-badge:has-text("PAUSED")');
    
    // Resume
    await page.click('button[data-testid="resume-button"]');
    await page.waitForSelector('.status-badge:has-text("MONITORING")');
  });
});
```

---

## 11. Implementation Checklist

### Phase 1: Core Infrastructure (Week 1)

**Backend Foundation**
- [ ] Create backend file structure
- [ ] Implement session storage (`ssr_algo_storage.py`)
- [ ] Implement API endpoints (`ssr_algo_api.py`)
- [ ] Add WebSocket events
- [ ] Unit tests for backend

**Frontend Foundation**
- [ ] Create frontend file structure
- [ ] Implement SSRAlgoContext
- [ ] Implement custom hooks
- [ ] Setup WebSocket integration
- [ ] Create shared components

**Integration**
- [ ] Connect frontend to backend APIs
- [ ] Test WebSocket communication
- [ ] Add to main navigation

### Phase 2: Core Components (Week 2)

**Configuration**
- [ ] SSRAlgoConfigPanel component
- [ ] Strike preview functionality
- [ ] Form validation
- [ ] Strike preview table
- [ ] Circuit breaker config

**Session Management**
- [ ] SSRAlgoSessionCard component
- [ ] Status badge with colors
- [ ] Control buttons (pause/resume/stop)
- [ ] Session metrics display
- [ ] Tab navigation

**Data Display**
- [ ] SSRAlgoPositionsTable
- [ ] SSRAlgoTriggerHistory
- [ ] Session event logs
- [ ] Export functionality

### Phase 3: Visualization (Week 3)

**Payoff Chart**
- [ ] SSRAlgoPayoffChart component
- [ ] Max loss zone markers
- [ ] Current price indicator
- [ ] Breakeven annotations
- [ ] Zoom/pan controls

**Price Monitoring**
- [ ] PriceZoneIndicator component
- [ ] Zone status colors
- [ ] Countdown timer for triggers
- [ ] Distance calculations
- [ ] Visual progress bars

### Phase 4: Real-Time Features (Week 4)

**Live Updates**
- [ ] Price update handling
- [ ] Status change handling
- [ ] Order update handling
- [ ] Exit order filled handling
- [ ] Circuit breaker alerts

**Notifications**
- [ ] Toast notification system
- [ ] Sound alerts
- [ ] Browser notifications
- [ ] Notification preferences

### Phase 5: Testing & Polish (Week 5)

**Testing**
- [ ] Unit tests (80%+ coverage)
- [ ] Integration tests
- [ ] E2E tests for critical flows
- [ ] Load testing (multiple sessions)
- [ ] WebSocket stress testing

**Polish**
- [ ] Responsive design (tablet/desktop)
- [ ] Loading states
- [ ] Error states
- [ ] Empty states
- [ ] Accessibility (WCAG AA)

**Documentation**
- [ ] User guide
- [ ] Component documentation
- [ ] API documentation
- [ ] Troubleshooting guide

### Phase 6: Deployment (Week 6)

**Pre-deployment**
- [ ] Code review
- [ ] Performance audit
- [ ] Security audit
- [ ] Browser compatibility testing

**Deployment**
- [ ] Staging deployment
- [ ] User acceptance testing
- [ ] Production deployment
- [ ] Monitoring setup

**Post-deployment**
- [ ] User feedback collection
- [ ] Bug tracking
- [ ] Performance monitoring
- [ ] Feature enhancement planning

---

## 12. Success Metrics

### 12.1 Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Page Load Time** | < 2 seconds | Lighthouse |
| **Time to Interactive** | < 3 seconds | Lighthouse |
| **WebSocket Latency** | < 100ms | Custom monitoring |
| **UI Update Lag** | < 50ms | React DevTools |
| **Bundle Size** | < 500KB | Webpack analyzer |
| **Test Coverage** | > 80% | Jest |
| **Error Rate** | < 1% | Error tracking |
| **Uptime** | > 99.5% | Server monitoring |

### 12.2 User Experience Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Session Creation Time** | < 30 seconds | User timing |
| **Strike Preview Speed** | < 3 seconds | API timing |
| **Chart Render Time** | < 1 second | Performance API |
| **User Errors** | < 5% | Error logs |
| **Support Tickets** | < 10/week | Ticket system |

### 12.3 Business Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Active Sessions** | 10+ concurrent | Backend analytics |
| **Daily Active Users** | 20+ | User tracking |
| **User Retention** | > 80% | Weekly logins |
| **Feature Adoption** | > 60% | Usage tracking |
| **User Satisfaction** | > 4.5/5 | User surveys |

---

## 13. Future Enhancements

### Phase 7+: Advanced Features

1. **Machine Learning Integration**
   - Optimal entry time prediction
   - Strike selection optimization
   - Risk parameter tuning

2. **Advanced Analytics**
   - Historical performance dashboard
   - Strategy backtesting
   - Risk metrics (Sharpe, max drawdown)
   - P&L attribution by adjustment

3. **Mobile App**
   - React Native app
   - Push notifications
   - Gesture controls
   - Offline mode

4. **Social Features**
   - Share session configs
   - Community strategies
   - Leaderboard
   - Discussion forum

5. **Institutional Features**
   - Multi-account support
   - Team collaboration
   - Audit trail export
   - Compliance reports

---

## Appendix A: Component Props Reference

### SSRAlgoDashboard
```typescript
interface SSRAlgoDashboardProps {
  initialSessionId?: string;  // Deep link to specific session
}
```

### SSRAlgoConfigPanel
```typescript
interface SSRAlgoConfigPanelProps {
  onCreateSession: (config: SessionConfig) => Promise<void>;
  onCancel: () => void;
  isCreating: boolean;
  defaults?: Partial<SessionConfig>;
}
```

### SSRAlgoSessionCard
```typescript
interface SSRAlgoSessionCardProps {
  sessionId: string;
  compact?: boolean;
  onSelect?: (sessionId: string) => void;
}
```

### SSRAlgoPayoffChart
```typescript
interface SSRAlgoPayoffChartProps {
  sessionId: string;
  height?: number;
  showControls?: boolean;
  onPriceClick?: (price: number) => void;
}
```

### SSRAlgoPositionsTable
```typescript
interface SSRAlgoPositionsTableProps {
  sessionId: string;
  groupByTrigger?: boolean;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onRowClick?: (position: Position) => void;
}
```

---

## Appendix B: State Type Definitions

```typescript
// Session types
interface SSRAlgoSession {
  session_id: string;
  underlying: 'BTC' | 'ETH';
  expiry: string;
  auto_loop_rounds: number;
  order_type: string;
  start_time: string;
  end_time: string;
  strike_config: StrikeConfig;
  circuit_breakers: CircuitBreakerConfig;
  status: SessionStatus;
  trigger_count: number;
  started_at: string;
  positions: Position[];
  max_loss_upper: number;
  max_loss_lower: number;
  zone_entry_time: string | null;
  closed_positions: ClosedPosition[];
  trigger_history: Trigger[];
}

interface StrikeConfig {
  otm_buy_percent_min: number;
  otm_buy_percent_max: number;
  far_otm_percent_min: number;
  far_otm_percent_max: number;
}

interface CircuitBreakerConfig {
  enabled: boolean;
  max_adjustments_per_day: number;
  max_adjustments_per_session: number;
  daily_loss_limit: number;
  cooldown_minutes: number;
}

type SessionStatus = 
  | 'IDLE'
  | 'SELECTING_STRIKES'
  | 'EXECUTING_AUTO_LOOP'
  | 'MONITORING'
  | 'PAUSED'
  | 'STOPPED';

interface Position {
  trigger_id: number;
  atm_strike: number;
  atm_ce_premium: number;
  atm_pe_premium: number;
  atm_ce: Leg;
  atm_pe: Leg;
  otm_ce_buy: Leg;
  otm_pe_buy: Leg;
  far_otm_ce: Leg;
  far_otm_pe: Leg;
}

interface Leg {
  symbol: string;
  size: number;
  filled: boolean;
  selected_premium?: number;
  exit_order_id?: string | null;
}

interface ClosedPosition {
  symbol: string;
  size: number;
  realized_pnl: number;
}

interface Trigger {
  trigger_id: number;
  timestamp: string;
  reason: 'max_loss_upper' | 'max_loss_lower';
  price: number;
  new_atm_strike: number;
  rounds_completed: number;
  rounds_total: number;
  success: boolean;
}
```

---

**Document Status: COMPREHENSIVE IMPLEMENTATION READY**

This implementation plan provides complete specifications for building a robust, production-ready WebUI for the SSR Algo system. Proceed with Phase 1 when ready.
