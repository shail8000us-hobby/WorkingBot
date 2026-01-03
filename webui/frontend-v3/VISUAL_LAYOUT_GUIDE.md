# WebUI v3 Visual Layout Guide

## Dashboard Structure (After Phase 1)

```
┌─────────────────────────────────────────────────────────────────────┐
│ DASHBOARD HEADER                                                    │
│ ═══════════════════════════════════════════════════════════════════ │
│ Dashboard                                          [Bot Running ✓]  │
│ Overview of your trading bot performance                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ EMERGENCY ALERT (only if active)                                    │
│ ⚠️ Emergency Mode Active                                            │
│ Trading is halted. Check the Guardian panel for details.            │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────┬──────────────┬──────────────────────┐
│ KEY METRICS (4 columns)                                             │
├──────────────┼──────────────┼──────────────┼──────────────────────┤
│ Total P&L    │ Open         │ Total        │ Win Rate             │
│ ₹12,345.67   │ Positions    │ Invested     │ 65.5%                │
│ [green/red]  │ 8            │ ₹1,00,000    │ [green]              │
└──────────────┴──────────────┴──────────────┴──────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ TRADING STATUS CARD (2 columns)                                     │
├─────────────────────────────────────────┬───────────────────────────┤
│ Trading Status                          │ System Health             │
│                                         │                           │
│ Status: [Active/Paused] Badge          │ ✓ Bot is running          │
│ Mode: GRID_TRADING                      │ ✓ Guardian is active      │
│ Guardian: [Active] Badge               │ ✓ No emergency flag       │
│ Emergency: [Clear] Badge               │ ✓ Trading is allowed      │
│                                         │                           │
│ [Trading Blockers: if any]             │                           │
└─────────────────────────────────────────┴───────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 🆕 TRADING CONTROLS & MARKET DATA (3 columns)                       │
├─────────────────────────┬─────────────────────────┬─────────────────┤
│ Trading Mode Switch     │ Symbol Selector         │ Volatility Panel│
│ ───────────────────────│ ───────────────────────│─────────────────│
│                         │                         │                 │
│ [GRID] Card             │ ▼ Select Symbol        │ Market          │
│ ├─ Grid Icon            │                         │ Volatility      │
│ ├─ Active indicator     │ 🔍 Search...           │                 │
│ └─ Description          │                         │ Level: MODERATE │
│                         │ BTCUSDT  $43,210       │ Score: 45%      │
│ [OPPORTUNISTIC] Card    │ ├─ [+2.3%] Green       │ [Progress bar]  │
│ ├─ Lightning Icon       │                         │                 │
│ └─ Description          │ ETHUSDT  $2,340        │ Trend:          │
│                         │ ├─ [-1.2%] Red         │ ↗ Increasing    │
│ [HYBRID] Card           │                         │                 │
│ ├─ Combined Icon        │ SOLUSDT  $98.50        │ Recommendation: │
│ └─ Description          │ └─ [+5.1%] Green       │ Moderate risk   │
│                         │                         │                 │
└─────────────────────────┴─────────────────────────┴─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 🆕 SYSTEM HEALTH DASHBOARD (Responsive Grid)                        │
├─────────────────────────────────────────────────────────────────────┤
│ System Health                                     [HEALTHY] Badge   │
│ ⏰ Uptime: 2d 5h 23m                                               │
│                                                                     │
├───────────────┬───────────────┬───────────────┬───────────────────┤
│ CPU Usage     │ Memory Usage  │ Disk Usage    │ API Status        │
│ ─────────────│ ─────────────│ ─────────────│─────────────────│
│ 45.2%         │ 68.5%         │ 42.1%         │ [OK] ✓            │
│ [Progress bar]│ [Progress bar]│ [Progress bar]│ Response: 45ms    │
│ [green]       │ [yellow]      │ [green]       │                   │
├───────────────┼───────────────┼───────────────┼───────────────────┤
│ WebSocket     │ Database      │               │                   │
│ ─────────────│ ─────────────│               │                   │
│ [CONNECTED] ✓ │ [OK] ✓        │               │                   │
│ Connections:2 │               │               │                   │
└───────────────┴───────────────┴───────────────┴───────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ 🆕 ACTIVE ALERTS (if any, full width)                               │
│ ⚠️ Active Alerts (2)                                                │
│ ─────────────────────────────────────────────────────────────────── │
│ ⚠️ High CPU usage detected                                         │
│    2025-01-02 14:23:15                                              │
│ ⚠️ Memory usage approaching limit                                  │
│    2025-01-02 14:20:05                                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ OPEN POSITIONS (Existing)                           [View All →]   │
│ Your current trading positions                                      │
│ ─────────────────────────────────────────────────────────────────── │
│ BTCUSDT  | LONG  | Entry: ₹43,100 | Current: ₹43,210 | +0.26%     │
│ ETHUSDT  | LONG  | Entry: ₹2,350  | Current: ₹2,340  | -0.43%     │
│ SOLUSDT  | SHORT | Entry: ₹98.80  | Current: ₹98.50  | +0.30%     │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────┬────────────────────────────┐
│ P&L CHART (2/3 width)                  │ QUICK ACTIONS (1/3 width) │
│                                        │                            │
│ [Line chart showing P&L over time]    │ [Pause/Resume Bot]         │
│ [7D/30D/ALL time toggles]             │ [Emergency Kill]           │
│                                        │ [Refresh Data]             │
│                                        │ [View Logs]                │
└────────────────────────────────────────┴────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ ACTIVITY TIMELINE (Existing)                                        │
│ Recent activity                                                      │
│ ─────────────────────────────────────────────────────────────────── │
│ ● Trade Executed - BTCUSDT LONG @ ₹43,100                    2m ago│
│ ● Guardian Check - All systems normal                        5m ago│
│ ● Order Placed - ETHUSDT LONG @ ₹2,350                      10m ago│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 🆕 NEW IN PHASE 1

#### 1. Trading Mode Switch (Left Column)
```
┌─────────────────────────┐
│ Trading Mode            │
│ ───────────────────────│
│                         │
│ ┌─────────────────────┐│
│ │ ⊞ GRID              ││ ← Clickable card
│ │ Traditional grid    ││
│ │ [Active ✓]          ││ ← Shows if active
│ └─────────────────────┘│
│                         │
│ ┌─────────────────────┐│
│ │ ⚡ OPPORTUNISTIC    ││
│ │ Market opportunities││
│ └─────────────────────┘│
│                         │
│ ┌─────────────────────┐│
│ │ ⟐ HYBRID            ││
│ │ Combined strategy   ││
│ └─────────────────────┘│
└─────────────────────────┘
```

#### 2. Symbol Selector (Middle Column)
```
┌─────────────────────────┐
│ Symbol Selector         │
│ ───────────────────────│
│                         │
│ ▼ BTCUSDT ✓             │ ← Dropdown button
│ ┌─────────────────────┐│
│ │ 🔍 Search symbols   ││ ← Search input
│ ├─────────────────────┤│
│ │ BTCUSDT    $43,210  ││
│ │ [+2.3%] Green ✓     ││ ← Active symbol
│ ├─────────────────────┤│
│ │ ETHUSDT    $2,340   ││
│ │ [-1.2%] Red         ││
│ ├─────────────────────┤│
│ │ SOLUSDT    $98.50   ││
│ │ [+5.1%] Green       ││
│ └─────────────────────┘│
└─────────────────────────┘
```

#### 3. Volatility Panel (Right Column)
```
┌─────────────────────────┐
│ Market Volatility       │
│ 14:23:15                │ ← Timestamp
│ ───────────────────────│
│                         │
│ Level:    [MODERATE]    │ ← Color badge
│ Regime:   [CALM]        │
│                         │
│ Score:           45%    │
│ [████████░░░░░░░░░░]   │ ← Progress bar
│                         │
│ Trend:    ↗ Increasing  │ ← Arrow icon
│                         │
│ ───────────────────────│
│ Recommendation:         │
│ Moderate risk, proceed  │
│ with caution            │
│                         │
│ Short Term:      38%    │
│ Long Term:       52%    │
└─────────────────────────┘
```

#### 4. Health Dashboard (Full Width, Responsive Grid)
```
┌─────────────────────────────────────────────────────────────┐
│ System Health                             [HEALTHY] Badge   │
│ ⏰ Uptime: 2d 5h 23m                                        │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│ CPU Usage   │ Memory      │ Disk        │ API Status      │
│             │             │             │                 │
│ 45.2%       │ 68.5%       │ 42.1%       │ [OK] ✓          │
│ ✓           │ ⚠           │ ✓           │ Resp: 45ms      │
│ [Progress]  │ [Progress]  │ [Progress]  │                 │
│ Green       │ Yellow      │ Green       │                 │
├─────────────┼─────────────┼─────────────┼─────────────────┤
│ WebSocket   │ Database    │             │                 │
│             │             │             │                 │
│ [CONNECTED] │ [OK] ✓      │             │                 │
│ ✓           │             │             │                 │
│ Conns: 2    │             │             │                 │
└─────────────┴─────────────┴─────────────┴─────────────────┘
```

---

## Color Coding

### Trading Mode Switch
- **Active Mode**: Blue border, checkmark icon
- **Inactive Modes**: Gray border, no checkmark
- **Hover**: Subtle background highlight
- **Loading**: Spinner animation

### Symbol Selector
- **Price Changes**:
  - Green badge: Positive change (+X.X%)
  - Red badge: Negative change (-X.X%)
  - Gray badge: No change (0.0%)
- **Active Symbol**: Checkmark icon ✓

### Volatility Panel
- **Levels**:
  - GREEN: Low volatility
  - YELLOW: Moderate volatility
  - ORANGE: High volatility
  - RED: Extreme volatility
- **Progress Bar**: Matches level color
- **Trend**: Green (decreasing), Orange (increasing)

### Health Dashboard
- **Resource Usage** (CPU/Memory/Disk):
  - GREEN: < 60% (healthy)
  - YELLOW: 60-85% (warning)
  - RED: > 85% (critical)
- **Status Badges**:
  - GREEN: OK, HEALTHY, CONNECTED
  - YELLOW: DEGRADED, WARNING
  - RED: ERROR, CRITICAL, DISCONNECTED

---

## Responsive Behavior

### Desktop (> 1024px)
- Trading Controls: 3 columns
- Health Dashboard: 3 columns (CPU/Memory/Disk, API/WebSocket/DB)

### Tablet (768px - 1024px)
- Trading Controls: 2 columns (mode + symbol, volatility below)
- Health Dashboard: 2 columns

### Mobile (< 768px)
- Trading Controls: 1 column (stacked)
- Health Dashboard: 1 column (all metrics stacked)

---

## Real-Time Updates

All new components update automatically:

| Component       | Refresh Interval | Endpoint                      |
|----------------|------------------|-------------------------------|
| Trading Mode   | 10 seconds       | /api/trading-mode             |
| Symbol Data    | 10 seconds       | /api/symbols                  |
| Volatility     | 30 seconds       | /api/volatility/signal        |
| System Health  | 10 seconds       | /api/system-health/summary    |

---

## User Interactions

### Trading Mode Switch
1. Click on a mode card (GRID/OPPORTUNISTIC/HYBRID)
2. Card shows loading state
3. Backend updates mode
4. Success: Active badge appears on new mode
5. Error: Alert message shown at bottom of card

### Symbol Selector
1. Click dropdown button
2. Type in search box to filter
3. Click a symbol
4. Dropdown closes
5. Selected symbol shows checkmark ✓
6. Backend receives selection

### Volatility Panel
- **Read-only**: No user interaction
- Auto-updates every 30 seconds
- Shows loading spinner during refresh
- Displays error message if API fails

### Health Dashboard
- **Read-only**: No user interaction
- Auto-updates every 10 seconds
- Metrics update smoothly
- Alerts appear/disappear dynamically
