# SSR ALGO - Automated Position Adjustment Algorithm

**Created:** February 2, 2026  
**Version:** 1.0  
**Status:** Architecture & Planning Document

---

## 1. Executive Summary

SSR Algo is a fully automated algorithmic trading engine that deploys a **Modified Iron Butterfly with Protective Wings** strategy. It continuously monitors positions and automatically adjusts when the underlying price reaches max loss zones.

### Key Features
- **Automatic Strike Selection**: Based on premium ranges from ATM
- **Auto-Loop Execution**: Existing auto-loop mechanism for order execution
- **Dynamic Adjustment**: Auto-triggers new positions when price hits max loss zones
- **Multi-Session Support**: Run on multiple expiries simultaneously
- **Independent System**: Completely isolated from existing bot positions

---

## 2. Strategy Structure

### Initial Position Structure (Per Deployment)

| Leg | Strike Selection | Qty | Side | Purpose |
|-----|------------------|-----|------|---------|
| **ATM CE** | Strike where CE ≈ PE premium | 1 lot | **SELL** | Core income |
| **ATM PE** | Same strike as ATM CE | 1 lot | **SELL** | Core income |
| **OTM CE** | **45-49% of ATM CE premium** | 2 lots | **BUY** | Upside protection |
| **OTM PE** | **45-49% of ATM PE premium** | 2 lots | **BUY** | Downside protection |
| **Far OTM CE** | **20-30% of ATM CE premium** | 1 lot | **SELL** | Extra income |
| **Far OTM PE** | **20-30% of ATM PE premium** | 1 lot | **SELL** | Extra income |

**Total: 8 legs per deployment**

### Premium-Based Strike Selection (Dynamic)

All strike selections are **relative to ATM premium**, not hardcoded values:

| Strike Type | Premium Range | Example (ATM = 500) | Example (ATM = 1000) |
|-------------|---------------|---------------------|----------------------|
| ATM | Market price | 500 | 1000 |
| OTM Buy | 45-49% of ATM | 225-245 | 450-490 |
| Far OTM Sell | 20-30% of ATM | 100-150 | 200-300 |

### Configurable Parameters (WebUI)

```javascript
{
  otm_buy_percent_min: 45,    // Lower bound for OTM buy selection
  otm_buy_percent_max: 49,    // Upper bound for OTM buy selection
  far_otm_percent_min: 20,    // Lower bound for far OTM sell selection
  far_otm_percent_max: 30,    // Upper bound for far OTM sell selection
}
```

### Ratio: 1:2:1 (Fixed)
- Sell 1 ATM : Buy 2 OTM : Sell 1 Far OTM

---

## 3. Algorithm Rules

### 3.0 Expiry Filtering

**Automatic Expired Contract Filtering:**
- Contracts that expire at **5:30 PM IST** are automatically filtered from the expiry dropdown
- When current time reaches 5:30 PM IST on expiry day, that contract is removed from selection
- This prevents accidental selection of expired or about-to-expire contracts
- Filter applies to all expiry selection interfaces (SSR Algo, Options Chain, etc.)

**Implementation Details:**
- Backend checks current time in IST timezone
- For each expiry date:
  - If expiry date is in the past → filtered out
  - If expiry date == today && current time >= 5:30 PM IST → filtered out
  - Otherwise → shown in dropdown
- Cache TTL reduced to ensure fresh expiry lists

### 3.1 Strike Selection Logic

```
1. FIND ATM STRIKE:
   - Query options chain for current spot price
   - ATM = Strike where |CE_premium - PE_premium| is minimum
   - Store ATM_CE_PREMIUM and ATM_PE_PREMIUM
   
2. CALCULATE TARGET PREMIUM RANGES:
   - OTM_BUY_CE_MIN = ATM_CE_PREMIUM × 0.45
   - OTM_BUY_CE_MAX = ATM_CE_PREMIUM × 0.49
   - OTM_BUY_PE_MIN = ATM_PE_PREMIUM × 0.45
   - OTM_BUY_PE_MAX = ATM_PE_PREMIUM × 0.49
   - FAR_OTM_CE_MIN = ATM_CE_PREMIUM × 0.20
   - FAR_OTM_CE_MAX = ATM_CE_PREMIUM × 0.30
   - FAR_OTM_PE_MIN = ATM_PE_PREMIUM × 0.20
   - FAR_OTM_PE_MAX = ATM_PE_PREMIUM × 0.30
   
3. FIND OTM BUY STRIKES (45-49% of ATM):
   - Scan OTM CE strikes: premium >= OTM_BUY_CE_MIN AND premium <= OTM_BUY_CE_MAX
   - Pick first match (closest to ATM)
   - Repeat for PE side with PE ranges
   
4. FIND FAR OTM SELL STRIKES (20-30% of ATM):
   - Scan further OTM CE strikes: premium >= FAR_OTM_CE_MIN AND premium <= FAR_OTM_CE_MAX
   - Pick first match
   - Repeat for PE side with PE ranges
   
5. LOCK STRIKES:
   - All 6 strikes locked for ALL auto-loop rounds
   - Premiums will vary per round (market prices)
```

### 3.1.1 Example Calculation

```
Given: BTC Spot = 76,000, ATM Strike = 76000
       ATM CE Premium = 520, ATM PE Premium = 480

OTM Buy CE Range: 520 × 0.45 to 520 × 0.49 = 234 to 255
OTM Buy PE Range: 480 × 0.45 to 480 × 0.49 = 216 to 235

Far OTM Sell CE Range: 520 × 0.20 to 520 × 0.30 = 104 to 156
Far OTM Sell PE Range: 480 × 0.20 to 480 × 0.30 = 96 to 144

Result:
- ATM CE 76000 @ 520 (SELL)
- ATM PE 76000 @ 480 (SELL)
- OTM CE 82000 @ 240 (BUY) - within 234-255 range
- OTM PE 70000 @ 225 (BUY) - within 216-235 range
- Far OTM CE 85000 @ 120 (SELL) - within 104-156 range
- Far OTM PE 67000 @ 110 (SELL) - within 96-144 range
```

### 3.2 Auto-Loop Execution

```
FOR each round in [1..N]:
   1. Place all 8 orders simultaneously (batch_add API)
   2. Wait for ALL orders to fill (infinite wait per round)
   3. Only after 100% filled → proceed to next round
   4. Use selected order type (SSR recommended)
   
AFTER all rounds complete:
   1. Calculate max loss points from payoff graph
   2. Place limit BUY orders at premium=3 for all SELL legs
   3. Enter MONITORING state
```

### 3.3 Max Loss Zone Detection

```
Trigger Conditions (ALL must be true):
   1. Price within max_loss_point ± 100
   2. Price stays in zone for >= 10 minutes
   3. Algo is in RUNNING state (not PAUSED)
   4. Current time within configured trading hours
   
On Trigger:
   1. Calculate NEW ATM based on current spot
   2. Select new strikes using same rules
   3. Fire configured number of auto-loop rounds
   4. Place limit orders at 3 for new sell legs
   5. Recalculate max loss points (include all positions)
   6. Return to MONITORING state
```

### 3.4 Sell Leg Exit at Premium ≤3

```
After auto-loop completes:
   1. For each SELL leg, place limit BUY order at price=3
   2. Orders sit on exchange until filled
   3. When filled: Include PnL in payoff calculation
   4. Buy legs remain open until expiry/manual
```

---

## 4. State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                        SSR ALGO STATES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────┐     start      ┌──────────────┐                   │
│   │  IDLE   │ ──────────────▶│  SELECTING   │                   │
│   └─────────┘                │   STRIKES    │                   │
│        ▲                     └──────┬───────┘                   │
│        │                            │                            │
│        │ stop                       │ strikes_locked             │
│        │                            ▼                            │
│        │                     ┌──────────────┐                   │
│        │                     │  EXECUTING   │◀─────────────┐    │
│        │                     │  AUTO-LOOP   │              │    │
│        │                     └──────┬───────┘              │    │
│        │                            │                       │    │
│        │                            │ all_rounds_complete   │    │
│        │                            ▼                       │    │
│   ┌────┴────┐                ┌──────────────┐              │    │
│   │ STOPPED │◀───────────────│  MONITORING  │──────────────┘    │
│   └─────────┘    stop        └──────┬───────┘  max_loss_hit     │
│        ▲                            │          (after 10 min)   │
│        │                            │                            │
│        │                     ┌──────▼───────┐                   │
│        │                     │    PAUSED    │                   │
│        └─────────────────────┤  (manual)    │                   │
│              stop            └──────────────┘                   │
│                                     │                            │
│                              resume │                            │
│                                     ▼                            │
│                              ┌──────────────┐                   │
│                              │  MONITORING  │                   │
│                              └──────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### State Descriptions

| State | Description |
|-------|-------------|
| **IDLE** | No active session, waiting for user to start |
| **SELECTING_STRIKES** | Querying chain, finding ATM and premium-based strikes |
| **EXECUTING_AUTO_LOOP** | Running auto-loop rounds, placing orders |
| **MONITORING** | All rounds complete, watching price for max loss zone |
| **PAUSED** | User paused, monitoring continues but no triggers |
| **STOPPED** | Session ended, all automation stopped |

---

## 5. Data Models

### 5.1 SSR Algo Session

```javascript
{
  session_id: "ssr_001_060226_btc",      // Unique session ID
  underlying: "BTC",                       // BTC or ETH
  expiry: "060226",                        // DDMMYY
  
  // Configuration
  auto_loop_rounds: 2,                     // Rounds per trigger
  order_type: "ssr",                       // Order execution type
  start_time: "15:00",                     // IST
  end_time: "21:00",                       // IST
  
  // Premium-based strike selection (percentage of ATM premium)
  strike_config: {
    otm_buy_percent_min: 45,               // OTM buy: 45% of ATM premium
    otm_buy_percent_max: 49,               // OTM buy: 49% of ATM premium
    far_otm_percent_min: 20,               // Far OTM sell: 20% of ATM premium
    far_otm_percent_max: 30,               // Far OTM sell: 30% of ATM premium
  },
  
  // State
  status: "MONITORING",                    // Current state
  trigger_count: 0,                        // Number of adjustments made
  started_at: "2026-02-02T09:30:00Z",
  
  // Positions (SSR Algo managed only)
  positions: [
    {
      trigger_id: 0,                       // 0 = initial, 1+ = adjustment
      atm_strike: 76000,
      atm_ce_premium: 520,                 // Reference for % calculations
      atm_pe_premium: 480,                 // Reference for % calculations
      atm_ce: { symbol: "C-BTC-76000-060226", size: -1, filled: true, exit_order_id: null },
      atm_pe: { symbol: "P-BTC-76000-060226", size: -1, filled: true, exit_order_id: null },
      otm_ce_buy: { symbol: "C-BTC-82000-060226", size: 2, filled: true, selected_premium: 240 },
      otm_pe_buy: { symbol: "P-BTC-70000-060226", size: 2, filled: true, selected_premium: 225 },
      far_otm_ce: { symbol: "C-BTC-85000-060226", size: -1, filled: true, exit_order_id: null, selected_premium: 120 },
      far_otm_pe: { symbol: "P-BTC-67000-060226", size: -1, filled: true, exit_order_id: null, selected_premium: 110 },
    }
  ],
  
  // Payoff tracking
  max_loss_upper: 77759,                   // Upper max loss price
  max_loss_lower: 73566,                   // Lower max loss price
  zone_entry_time: null,                   // When price entered max loss zone
  
  // Closed positions (for payoff calculation)
  closed_positions: [
    { symbol: "C-BTC-85000-060226", size: -1, realized_pnl: 45.2 }
  ]
}
```

### 5.2 Backend Storage

```python
# File: webui/backend/data/ssr_algo_sessions.json
{
  "sessions": {
    "ssr_001_060226_btc": { ... session data ... },
    "ssr_002_130226_eth": { ... session data ... }
  },
  "active_session_ids": ["ssr_001_060226_btc"],
  "version": 1
}
```

---

## 6. File Structure

### Frontend

```
webui/frontend/src/components/ssrAlgo/
├── index.js                              # Exports
├── SSRAlgoDashboard.js                   # Main dashboard component
├── SSRAlgoConfigPanel.js                 # Configuration form
├── SSRAlgoSessionCard.js                 # Individual session display
├── SSRAlgoPositionsTable.js              # Positions for a session
├── SSRAlgoPayoffChart.js                 # Payoff graph with max loss markers
├── SSRAlgoStatusBanner.js                # Status bar (monitoring, triggers)
├── SSRAlgoControlButtons.js              # Start, Pause, Resume, Stop
├── SSRAlgoTriggerHistory.js              # History of adjustment triggers
├── hooks/
│   ├── useSSRAlgoSession.js              # Session state management
│   ├── useSSRAlgoPayoff.js               # Payoff calculation hook
│   └── useSSRAlgoMonitor.js              # Price monitoring hook
├── utils/
│   ├── strikeSelector.js                 # Strike selection logic
│   └── maxLossCalculator.js              # Max loss point calculator
└── context/
    └── SSRAlgoContext.js                 # React context for multi-session
```

### Backend

```
webui/backend/routes/ssr_algo/
├── __init__.py                           # Route registration
├── ssr_algo_api.py                       # REST endpoints
├── ssr_algo_engine.py                    # Core algorithm logic
├── ssr_algo_monitor.py                   # Price monitoring daemon
├── ssr_algo_executor.py                  # Order execution wrapper
├── ssr_algo_payoff.py                    # Payoff calculation
└── ssr_algo_storage.py                   # Session persistence

webui/backend/data/
└── ssr_algo_sessions.json                # Session storage
```

---

## 7. API Endpoints

### 7.1 Session Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ssr_algo/sessions` | GET | List all sessions (active + historical) |
| `/api/ssr_algo/session/<id>` | GET | Get specific session details |
| `/api/ssr_algo/session/create` | POST | Create new session |
| `/api/ssr_algo/session/<id>/start` | POST | Start session |
| `/api/ssr_algo/session/<id>/pause` | POST | Pause session |
| `/api/ssr_algo/session/<id>/resume` | POST | Resume session |
| `/api/ssr_algo/session/<id>/stop` | POST | Stop session |

### 7.2 Strike Selection

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ssr_algo/preview_strikes` | POST | Preview strikes before starting |

### 7.3 Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ssr_algo/status` | GET | Get all active sessions status |
| `/api/ssr_algo/session/<id>/payoff` | GET | Get current payoff data |

### 7.4 Request/Response Examples

**Create Session:**
```json
POST /api/ssr_algo/session/create
{
  "underlying": "BTC",
  "expiry": "060226",
  "auto_loop_rounds": 2,
  "order_type": "ssr",
  "start_time": "15:00",
  "end_time": "21:00",
  "strike_config": {
    "otm_buy_percent_min": 45,
    "otm_buy_percent_max": 49,
    "far_otm_percent_min": 20,
    "far_otm_percent_max": 30
  }
}

Response:
{
  "success": true,
  "session_id": "ssr_001_060226_btc",
  "atm_reference": {
    "strike": 76000,
    "ce_premium": 520,
    "pe_premium": 480
  },
  "strikes_preview": {
    "atm_strike": 76000,
    "otm_ce_buy": { 
      "strike": 82000, 
      "premium": 240,
      "target_range": "234-255 (45-49% of 520)"
    },
    "otm_pe_buy": { 
      "strike": 70000, 
      "premium": 225,
      "target_range": "216-235 (45-49% of 480)"
    },
    "far_otm_ce": { 
      "strike": 85000, 
      "premium": 120,
      "target_range": "104-156 (20-30% of 520)"
    },
    "far_otm_pe": { 
      "strike": 67000, 
      "premium": 110,
      "target_range": "96-144 (20-30% of 480)"
    }
  }
}
```

---

## 8. WebUI Design

### 8.1 Navigation Addition

Add to sidebar sections in `App.js`:
```javascript
{
  id: 'ssr_algo',
  label: '🎯 SSR ALGO',
  icon: Crosshair,  // or appropriate icon
  description: 'Automated butterfly adjustment algorithm',
}
```

### 8.2 Dashboard Layout

**Improved Layout with Resizable Panels:**

The dashboard now features a **draggable vertical divider** between the payoff chart and configuration sections, allowing users to resize panels based on their preference.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🎯 SSR ALGO Dashboard                                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌───────────────────────────────────┬─────────────────────────────────────┐ │
│  │  Payoff Diagram & Session Info    │║  Configuration & Controls          │ │
│  │  (Resizable)                      │║  (Resizable)                       │ │
│  │                                   │║                                    │ │
│  │  [Interactive Payoff Chart]       │║  + Create New Session              │ │
│  │  - Max Loss Zones marked          │║  ┌──────────────────────────────┐ │ │
│  │  - Current price indicator        │║  │ Underlying: [BTC ▼]          │ │ │
│  │  - Breakeven points               │║  │ Expiry: [Auto-filtered ▼]   │ │ │
│  │                                   │║  │ (No expired contracts)       │ │ │
│  │  [Session Controls]               │║  └──────────────────────────────┘ │ │
│  │  [PAUSE] [STOP]                   │║                                    │ │
│  │                                   │║  [Preview] [Start Session]         │ │
│  │                                   │║                                    │ │
│  │  Drag divider ═══════════════════>│║  Strike Preview Table              │ │
│  │  to resize panels                 │║  Advanced Settings                 │ │
│  └───────────────────────────────────┴─────────────────────────────────────┘ │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Draggable Divider Features:**
- Smooth drag interaction with visual feedback
- Minimum panel widths enforced (30% each side)
- Persists user's preferred layout in localStorage
- Hover effect shows draggable cursor
- Mobile-responsive (stacks vertically on small screens)

### 8.3 Status Colors

| Status | Color | Badge |
|--------|-------|-------|
| IDLE | Gray | ⚪ |
| SELECTING_STRIKES | Blue | 🔵 Selecting... |
| EXECUTING_AUTO_LOOP | Amber | 🟡 Executing Round X/Y |
| MONITORING | Green | 🟢 Monitoring |
| PAUSED | Orange | 🟠 Paused |
| STOPPED | Red | 🔴 Stopped |
| IN_MAX_LOSS_ZONE | Flashing Red | ⚠️ Max Loss Zone! |

---

## 9. Implementation Phases

### Phase 1: Core Backend (3-4 hours)
- [ ] Create file structure
- [ ] Implement `ssr_algo_storage.py` - Session persistence
- [ ] Implement `ssr_algo_engine.py` - Strike selection logic
- [ ] Implement `ssr_algo_executor.py` - Auto-loop wrapper
- [ ] Implement `ssr_algo_api.py` - REST endpoints
- [ ] Test strike selection with mock data

### Phase 2: Payoff & Monitoring (2-3 hours)
- [ ] Implement `ssr_algo_payoff.py` - Max loss calculation
- [ ] Implement `ssr_algo_monitor.py` - Price monitoring daemon
- [ ] Add 10-minute zone dwell logic
- [ ] Add limit order placement for sell legs

### Phase 3: Frontend Dashboard (3-4 hours)
- [ ] Create component structure
- [ ] Implement `SSRAlgoConfigPanel.js`
- [ ] Implement `SSRAlgoSessionCard.js`
- [ ] Implement `SSRAlgoPayoffChart.js`
- [ ] Add WebSocket for real-time updates

### Phase 4: Integration & Navigation (1-2 hours)
- [ ] Add navigation item to `App.js`
- [ ] Add lazy loading
- [ ] Connect frontend to backend APIs
- [ ] Add sound notifications for triggers

### Phase 5: Testing & Polish (2-3 hours)
- [ ] End-to-end testing
- [ ] Edge case handling
- [ ] Error states and recovery
- [ ] Documentation

**Total Estimated Time: 12-16 hours**

---

## 10. Risk Management

### Built-in Safeguards

1. **10-Minute Dwell Time**: Prevents whipsaw triggers
2. **Time Window**: Only triggers within configured hours
3. **Pause Capability**: User can pause without losing state
4. **Limit Orders at 3**: Automatic exit for worthless options
5. **Independent System**: Cannot affect other bot positions

### Monitoring Points

- Current price vs max loss zones
- Auto-loop execution status
- Limit order fill status
- Session uptime and health

---

## 11. Technical Dependencies

### Existing Systems Used

| System | Purpose |
|--------|---------|
| `batch_add` API | Concurrent order placement |
| `adjustmentPayoffEngine.js` | Payoff calculation |
| Options Chain API | Strike data and premiums |
| Auto-loop mechanism | Multi-round execution |
| WebSocket | Real-time updates |

### New Dependencies

- None required - uses existing infrastructure

---

## 12. Questions for Future Enhancement

1. **Machine Learning**: Should algo learn optimal entry times?
2. **Dynamic Lot Sizing**: Scale based on account size?
3. **Multi-Underlying**: Run BTC + ETH simultaneously?
4. **Backtesting**: Historical performance analysis?
5. **Telegram Alerts**: Push notifications for triggers?

---

## 13. Institutional-Level Improvements (Future Roadmap)

The following enhancements are planned to bring SSR Algo to institutional-grade reliability:

### 13.1 Heartbeat Monitoring (Priority: HIGH)
- Background health check daemon (every 30 seconds)
- Detect stale price feeds, frozen monitors, or memory leaks
- Auto-restart unhealthy components
- Dashboard indicator for algo health

### 13.2 Telegram/Discord Alerts (Priority: HIGH)
- Real-time notifications for:
  - Session start/stop
  - Adjustment triggers
  - Circuit breaker activation
  - Daily P&L summaries
- Integration with existing notification system

### 13.3 Position Reconciliation (Priority: HIGH)
- Every 5 minutes: Compare SSR Algo's tracked positions vs actual exchange positions
- Alert on mismatches (phantom positions, missed fills)
- Auto-heal capability for minor discrepancies
- Manual intervention alerts for major issues

### 13.4 Expiry Day Safety (Priority: MEDIUM)
- Auto-pause or close positions X hours before expiry
- Warning when expiry approaches
- Square-off logic for near-expiry positions
- Weekend/holiday awareness

### 13.5 Audit Trail (Priority: MEDIUM)
- Log every action with timestamp and actor
- Immutable log file for compliance
- Trade reconstruction capability
- P&L attribution per adjustment

### 13.6 Backtesting Integration (Priority: MEDIUM)
- Replay historical data through the algo
- Calculate theoretical vs actual performance
- Parameter optimization suggestions
- Risk metrics (Sharpe, max drawdown, etc.)

### 13.7 Graceful Degradation (Priority: MEDIUM)
- If strike selection fails → use last known good strikes
- If order placement fails → queue for retry with exponential backoff
- If price feed fails → use last known price + staleness warning
- Fallback modes for each subsystem

### 13.8 Order Execution Quality (Priority: LOW)
- Track slippage per order
- Compare maker vs taker fill rates
- Best execution analysis
- Order timing optimization

### 13.9 Multi-Account Support (Priority: LOW)
- Run same strategy across multiple exchange accounts
- Aggregate P&L reporting
- Risk distribution across accounts

### 13.10 API Rate Limit Management (Priority: LOW)
- Track API usage per minute
- Automatic throttling when approaching limits
- Priority queuing for critical orders

---

## 14. Currently Implemented Safety Features (v1.0)

✅ **Circuit Breakers** (Implemented Feb 2, 2026)
- Max adjustments per day: 10 (configurable)
- Max adjustments per session: 20 (configurable)
- Daily loss limit: $5,000 USD (configurable)
- Cooldown between adjustments: 5 minutes

✅ **Greeks Exposure Limits** (Implemented Feb 2, 2026)
- Max delta exposure: 5.0
- Max gamma exposure: 2.0
- Max vega exposure: $1,000
- (Disabled by default - advanced feature)

✅ **Guardian Signal Integration**
- Respects master trading control (GO/STOP/PAUSE)
- Pauses monitoring when trading disabled

✅ **End Time Auto-Stop**
- Automatically stops session at configured end time
- Prevents overnight unmonitored running

✅ **Backend Restart Resilience**
- Monitors restored on backend startup
- Sessions continue after server restart

✅ **Partial Execution Handling**
- Session continues to monitoring even if some rounds fail
- Warning logged instead of stopping

✅ **CRITICAL FIX: Payoff Calculation Based on Filled Positions Only** (Feb 10, 2026)
- Fixed bug where positions were marked "filled" immediately after auto-loop
- Payoff graph now only includes ACTUALLY FILLED positions from exchange
- Max loss trigger zones calculated only from filled positions
- Prevents "fake" payoff graphs based on pending orders
- Frontend displays warning when orders are still pending
- Ensures accurate trigger zone detection

---

**Document Status: READY FOR IMPLEMENTATION**

Proceed to Phase 1 when ready.
