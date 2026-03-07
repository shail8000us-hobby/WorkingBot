# 🎯 WebUI v3 - Phase 1 Specification

## Mentor-Reviewed & Corrected Vision

**Version:** 1.1 (Post-Review)  
**Date:** January 2, 2026  
**Status:** APPROVED FOR PHASE 1

---

## 📋 Corrections Applied

### ✅ Correction #1: AI Advisor = Constrained Analyst

**Before (Dangerous):**
```
"I recommend tightening your grid by 10%"
```

**After (Operator-Grade):**
```
"Given IV=45%, RV=38%, and your max position cap of 5, 
tightening the grid by 10% reduces drawdown probability 
from 18% → 11%. 

No execution will occur without confirmation.

[Show Evidence] [Dismiss]"
```

**Implementation Principle:**
- Speaks in evidence-backed, state-derived language
- Every suggestion includes quantified impact
- No autonomous tone - mechanical authority model
- Flight computer, not co-pilot with opinions

---

### ✅ Correction #2: 3D Grid = Analysis Mode Only

**Rule:** Traders act fast, not admire geometry.

**Implementation:**
```typescript
// Default: High-contrast 2D (fast, clear, low cognitive load)
<GridVisualization2D mode="trading" />

// Optional: 3D for exploration (behind explicit toggle)
{analysisMode && <GridVisualization3D mode="analysis" />}
```

**UI Pattern:**
```
┌─────────────────────────────────────────────────────┐
│  GRID VIEW                    [Trading] [Analysis]  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Trading Mode (Default):                             │
│  - High-contrast 2D                                  │
│  - Minimal cognitive load                            │
│  - Optimized for quick decisions                     │
│                                                      │
│  Analysis Mode (Toggle):                             │
│  - 3D exploration                                    │
│  - Historical overlays                               │
│  - "What-if" scenarios                               │
│  - NOT for live trading decisions                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### ✅ Correction #3: Safety-First Transparency (Non-Negotiable)

**Invariant:** The UI must never lie.

**Every action path must expose "WHY THIS IS SAFE" before "DO THIS".**

```typescript
// Before any action button becomes clickable:
<ActionButton 
  action="place_order"
  disabled={!safetyChecks.allPassed}
>
  {/* Safety explanation ALWAYS visible */}
  <SafetyExplanation>
    <Check passed={checks.volatility}>
      Volatility: IV={iv}% < {threshold}% ✓
    </Check>
    <Check passed={checks.capacity}>
      Capacity: {positions}/{max} positions ✓
    </Check>
    <Check passed={checks.margin}>
      Margin: {margin}% < {limit}% ✓
    </Check>
  </SafetyExplanation>
  
  {/* Action only after understanding */}
  <ActionLabel>Place Order @ $94,200</ActionLabel>
</ActionButton>
```

**Visual Pattern:**
```
┌─────────────────────────────────────────────────────┐
│  PLACE BUY ORDER                                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  WHY THIS IS SAFE:                                   │
│  ─────────────────                                   │
│  ✓ Volatility: IV=45% < 80% threshold               │
│  ✓ Capacity: 2/5 positions (3 slots available)      │
│  ✓ Margin: 15% < 50% safety limit                   │
│  ✓ RSI: 62 > 35 (not oversold)                      │
│  ✓ Guardian: ACTIVE, no halt signals                │
│                                                      │
│  ORDER DETAILS:                                      │
│  ─────────────────                                   │
│  Side: BUY                                           │
│  Price: $94,200                                      │
│  Size: 0.01 BTC                                      │
│  TP Target: $94,700 (+$5 profit)                    │
│                                                      │
│  [Cancel]                    [Confirm Order]         │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Phase 1 Scope (Frozen)

### What We Build

| Component | Priority | Description |
|-----------|----------|-------------|
| **Command Center** | P0 | Main dashboard with critical metrics |
| **Bot Brain Stream** | P0 | Live decision feed with reasoning |
| **Multi-Instance Control** | P0 | Instance cards, aggregation, switches |
| **WebSocket Backbone** | P0 | Real-time event infrastructure |
| **2D Grid Visualization** | P1 | High-contrast trading view |
| **Safety-First Actions** | P1 | All buttons show "why safe" first |

### What We Defer

| Component | Phase | Reason |
|-----------|-------|--------|
| AI Advisor (Interactive) | Phase 2 | Start with read-only insights |
| 3D Grid Visualization | Phase 2 | Analysis mode, not default |
| Config Wizard | Phase 2 | Existing config works |
| Mobile PWA | Phase 2 | Desktop-first for operators |

---

## 🏗️ Architecture (Refined)

### Data Flow Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRUTH HIERARCHY                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Level 0: EXCHANGE (Ultimate truth)                              │
│     ↓                                                            │
│  Level 1: BOT STATE (Synced from exchange)                       │
│     ↓                                                            │
│  Level 2: WEBSOCKET EVENTS (Real-time deltas)                    │
│     ↓                                                            │
│  Level 3: UI STATE (Derived, never authoritative)                │
│                                                                  │
│  INVARIANT: UI never shows data newer than exchange truth        │
│  INVARIANT: Stale data is marked, never hidden                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Staleness Indicators (Required)

```typescript
// Every data display must show freshness
interface DataDisplay {
  value: number
  timestamp: number
  source: 'exchange' | 'websocket' | 'cache'
}

function PriceDisplay({ data }: { data: DataDisplay }) {
  const age = Date.now() - data.timestamp
  const isStale = age > 5000 // 5 seconds
  
  return (
    <div className={isStale ? 'stale-warning' : 'fresh'}>
      <span className="value">${data.value}</span>
      <span className="age">
        {isStale && '⚠️'} {formatAge(age)} ago
      </span>
      {isStale && (
        <span className="warning">Data may be outdated</span>
      )}
    </div>
  )
}
```

---

## 🧠 Bot Brain Stream (Core Feature)

### Design Philosophy

> "Exposing reasoning, not just outcomes, is how humans build trust in automation."

### Implementation

```typescript
interface BrainThought {
  id: string
  timestamp: number
  type: 'check' | 'decision' | 'action' | 'safety'
  
  // The reasoning chain (most important)
  reasoning: {
    observation: string      // What the bot observed
    evaluation: string       // How it evaluated the situation
    conclusion: string       // What it decided
    confidence: number       // 0-100% confidence
    evidence: Evidence[]     // Supporting data points
  }
  
  // Optional action taken
  action?: {
    type: 'order' | 'cancel' | 'adjust'
    details: Record<string, any>
    safetyChecks: SafetyCheck[]
  }
}

interface Evidence {
  name: string
  value: string | number
  threshold?: string | number
  passed: boolean
}
```

### Visual Design

```
┌──────────────────────────────────────────────────────────────┐
│  🧠 Bot Brain Stream                         ● Live (0.2s)   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ⏱ 2s ago                                      Confidence: 94%│
│  ┌────────────────────────────────────────────────────────┐  │
│  │ OBSERVATION:                                            │  │
│  │ "Price dropped to $94,500 (was $94,650)"               │  │
│  │                                                         │  │
│  │ EVALUATION:                                             │  │
│  │ "This crosses grid level at $94,500. Checking if       │  │
│  │  conditions allow new position..."                      │  │
│  │                                                         │  │
│  │ EVIDENCE:                                               │  │
│  │  ✓ Emergency stop: OFF                                  │  │
│  │  ✓ Guardian signal: GO                                  │  │
│  │  ✓ Volatility: IV=45% < 80%                            │  │
│  │  ✓ Positions: 2/5 (capacity available)                 │  │
│  │  ✓ RSI: 62 > 35 (not oversold)                         │  │
│  │  ✓ Margin: 15% < 50%                                   │  │
│  │                                                         │  │
│  │ CONCLUSION:                                             │  │
│  │ "All safety checks passed. Placing buy order."         │  │
│  │                                                         │  │
│  │ ACTION TAKEN:                                           │  │
│  │  ⚡ PLACE_BUY @ $94,200 (0.01 BTC)                      │  │
│  │  🎯 TP set @ $94,700                                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ⏱ 30s ago                                     Confidence: 87%│
│  ┌────────────────────────────────────────────────────────┐  │
│  │ OBSERVATION:                                            │  │
│  │ "Order filled: BUY 0.01 BTC @ $94,200"                 │  │
│  │                                                         │  │
│  │ ACTION TAKEN:                                           │  │
│  │  📦 Position opened: +0.01 BTC @ $94,200               │  │
│  │  🎯 TP order placed: SELL @ $94,700                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  [All] [Decisions] [Actions] [Safety] [Errors]               │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Command Center Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  GRIDBOT COMMAND CENTER                     BTCUSD ▼  │ ● Connected  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ CRITICAL METRICS (Always Visible)                                │ │
│  │                                                                   │ │
│  │  P&L Today     │  Positions   │  Price       │  System           │ │
│  │  +$234.50 ▲    │  3/5         │  $94,500     │  ✓ All Healthy    │ │
│  │  (0.2s ago)    │  (0.2s ago)  │  (0.1s ago)  │  (1s ago)         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌────────────────────────────┐  ┌────────────────────────────────┐  │
│  │ GRID VISUALIZATION (2D)    │  │ BOT BRAIN STREAM               │  │
│  │                            │  │                                │  │
│  │  $95,000 ─── Upper ●       │  │  ⏱ Just now                   │  │
│  │          ○ TP $94,800      │  │  "Checking grid level..."     │  │
│  │  $94,500 ─ ─ Price ─ ─     │  │   ✓ All checks passed         │  │
│  │          ● BUY $94,200     │  │   ⚡ PLACE_BUY @ $94,200      │  │
│  │          ○ BUY $93,900     │  │                                │  │
│  │  $93,000 ─── Lower ●       │  │  ⏱ 30s ago                    │  │
│  │                            │  │  "Order filled..."            │  │
│  │  [Trading] [Analysis]      │  │                                │  │
│  └────────────────────────────┘  └────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────┐  ┌────────────────────────────────┐  │
│  │ GUARDIAN STATUS            │  │ QUICK ACTIONS                  │  │
│  │                            │  │                                │  │
│  │  Signal: GO ✓              │  │  [⏸ Pause Trading]            │  │
│  │  RSI: 62 (threshold: 35)   │  │                                │  │
│  │  IV: 45% (limit: 80%)      │  │  [🚨 Emergency Stop]          │  │
│  │  Margin: 15% (limit: 50%)  │  │                                │  │
│  │                            │  │  [📊 Full Analysis]           │  │
│  │  Last check: 2s ago        │  │                                │  │
│  └────────────────────────────┘  └────────────────────────────────┘  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 WebSocket Event Types

```typescript
// Server → Client Events
interface WebSocketEvents {
  // Price updates (highest frequency)
  'price:update': {
    instance: string
    price: number
    timestamp: number
    source: 'exchange' | 'websocket'
  }
  
  // Bot brain thoughts (medium frequency)
  'brain:thought': {
    instance: string
    thought: BrainThought
  }
  
  // Order events
  'order:placed': { order: Order }
  'order:filled': { order: Order, fill: Fill }
  'order:cancelled': { orderId: string, reason: string }
  
  // Position events
  'position:opened': { position: Position }
  'position:closed': { position: Position, pnl: number }
  
  // Safety events (must display immediately)
  'safety:warning': { level: 'info' | 'warning' | 'critical', message: string }
  'guardian:signal': { signal: 'GO' | 'STOP', reason: string }
  
  // System health
  'system:health': { status: HealthStatus }
  'connection:status': { connected: boolean, latency: number }
}
```

---

## 📁 Project Structure

```
webui/frontend-v3/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout with providers
│   ├── page.tsx                  # Command Center (home)
│   ├── instances/
│   │   ├── page.tsx              # Multi-instance overview
│   │   └── [id]/page.tsx         # Single instance detail
│   └── analysis/
│       └── page.tsx              # Analysis mode (3D grid)
│
├── components/
│   ├── ui/                       # shadcn/ui base components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   └── ...
│   │
│   ├── trading/                  # Trading-specific components
│   │   ├── PriceDisplay.tsx      # Price with staleness
│   │   ├── SafetyCheck.tsx       # Individual safety check
│   │   ├── SafetyGate.tsx        # "Why safe" before action
│   │   ├── GridVisualization2D.tsx
│   │   └── GridVisualization3D.tsx  # Analysis mode only
│   │
│   ├── brain/                    # Bot Brain components
│   │   ├── BrainStream.tsx       # Live thought stream
│   │   ├── ThoughtBubble.tsx     # Single thought display
│   │   └── EvidenceList.tsx      # Check evidence
│   │
│   ├── dashboard/                # Dashboard components
│   │   ├── CommandCenter.tsx
│   │   ├── MetricsBar.tsx
│   │   ├── GuardianStatus.tsx
│   │   └── QuickActions.tsx
│   │
│   └── instances/                # Multi-instance components
│       ├── InstanceCard.tsx
│       ├── InstanceSwitcher.tsx
│       └── AggregatedStats.tsx
│
├── lib/
│   ├── api.ts                    # REST API client
│   ├── websocket.ts              # WebSocket client
│   ├── queries.ts                # TanStack Query hooks
│   └── stores.ts                 # Zustand stores
│
├── hooks/
│   ├── useLivePrice.ts
│   ├── useBrainStream.ts
│   ├── useInstance.ts
│   └── useSafetyChecks.ts
│
└── types/
    ├── trading.ts
    ├── brain.ts
    └── events.ts
```

---

## ⏱️ Phase 1 Timeline (2 Weeks)

### Week 1: Foundation + Core

| Day | Focus | Deliverables |
|-----|-------|--------------|
| 1 | Project Setup | Next.js 15, TypeScript, Tailwind, shadcn/ui |
| 2 | Base Components | Button, Card, Badge, PriceDisplay, SafetyCheck |
| 3 | WebSocket Layer | Connection, reconnection, event handling |
| 4 | TanStack Query | API hooks, caching, background sync |
| 5 | Layout + Routing | DashboardLayout, navigation, responsive grid |

### Week 2: Features

| Day | Focus | Deliverables |
|-----|-------|--------------|
| 6 | Command Center | Metrics bar, quick actions, layout |
| 7 | Bot Brain Stream | Thought stream, evidence display |
| 8 | Grid Visualization 2D | High-contrast trading view |
| 9 | Multi-Instance | Instance cards, switcher, aggregation |
| 10 | Safety-First Actions | SafetyGate component, action confirmations |
| 11 | Guardian Integration | Status panel, signal handling |
| 12 | Polish + Testing | Responsiveness, edge cases, error states |
| 13 | Documentation | Usage guide, API docs |
| 14 | Deployment | Production build, side-by-side with v1 |

---

## ✅ Phase 1 GO Criteria

Before marking Phase 1 complete:

- [ ] Command Center shows all critical metrics with staleness indicators
- [ ] Bot Brain Stream displays live thoughts with full reasoning chain
- [ ] WebSocket connection handles reconnection gracefully
- [ ] All action buttons show "Why This Is Safe" first
- [ ] Multi-instance switching works without page reload
- [ ] 2D Grid shows accurate position/order markers
- [ ] Guardian status updates in real-time
- [ ] Mobile-responsive (readable, not optimized)
- [ ] No data displayed without timestamp
- [ ] Stale data is visually marked

---

## 🚫 Phase 1 Anti-Patterns (Do Not Build)

1. **No AI suggestions that sound like opinions**
2. **No 3D visualization in trading mode**
3. **No action buttons without safety explanation**
4. **No data without staleness indicators**
5. **No "ChatGPT-style" conversational AI**
6. **No optimistic UI updates for trading actions**
7. **No hidden error states**

---

## 🔮 Phase 2 Preview (After Phase 1)

| Feature | Description |
|---------|-------------|
| AI Insights (Read-Only) | Evidence-backed analysis, no suggestions |
| 3D Analysis Mode | Behind toggle, for exploration only |
| Config Wizard | Step-by-step with live preview |
| Mobile PWA | Native-like experience |
| Historical Replay | "What happened at timestamp X" |
| Alerting System | Push notifications for critical events |

---

## 📌 Philosophical Guardrail

> "Buttons are cheap. Trust is expensive."

Every design decision must answer:

1. **Does this help the operator make better decisions?**
2. **Is the data provably fresh?**
3. **Are the safety implications visible?**
4. **Can this ever show incorrect information as correct?**

If the answer to #4 is "maybe", redesign it.

---

## 🚀 Ready for GO

Phase 1 is scoped, corrections are applied, guardrails are set.

**Waiting for "GO" to begin implementation.**
