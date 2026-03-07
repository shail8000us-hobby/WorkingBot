# MMM WebUI Suggestion System — Design Document

**Date:** March 4, 2026  
**Status:** DESIGN ONLY — awaiting operator review before implementation  
**Scope:** Non-invasive, operator-decides system that suggests (never auto-executes)

---

## 1. CORE PRINCIPLE

> **Suggest, never act.** Every suggestion is a notification with a "Dismiss" and optionally an "Apply" button. The operator always has the final say. No suggestion ever auto-executes. Think Bloomberg terminal alerts, not robo-advisor.

---

## 2. ARCHITECTURE

### 2.1 Backend: `mmm_suggestions.py` (New Module)

A pure analysis module with zero side effects. Called once per heartbeat AFTER all safety/regime/trigger logic runs.

```
mmm_monitor.py heartbeat loop
  └── after: safety, regime, triggers, walkthrough, activity
      └── _generate_suggestions(session, premiums, pnl, regime, margin)
          └── mmm_suggestions.evaluate_all(context)
              └── returns: List[Suggestion]
```

**Suggestion dataclass:**
```python
@dataclass
class Suggestion:
    id: str               # Unique ID (e.g., "shift_recycle_enable_20260304_1130")
    category: str         # 'param_tuning' | 'position_action' | 'risk_warning' | 'opportunity'
    priority: str         # 'low' | 'medium' | 'high' | 'critical'
    title: str            # Short headline: "Enable Shift-Time Recycle"
    rationale: str        # Why: "You have 45 frozen lots blocking capacity on CE side..."
    action_type: str      # 'param_change' | 'close_position' | 'informational' | 'manual'
    action_payload: dict  # For param_change: {'shift_recycle_enabled': True}
                          # For close_position: {'side': 'CE', 'strike': 69000, 'lots': 15}
                          # For informational: {} (dismiss only)
    expires_beats: int    # Auto-dismiss after N heartbeats if not acted on
    cooldown_beats: int   # Don't re-suggest same ID for N beats after dismiss
```

### 2.2 Frontend: `MMMSuggestionPanel.js` (New Component)

- Rendered as a collapsible ribbon/banner at the top of the session detail panel
- Badge count on the tab: "Suggestions (3)"
- Suggestions sorted by priority (critical → high → medium → low)
- Each suggestion card has:
  - Icon by category (💡 param, ⚡ action, ⚠️ risk, 🎯 opportunity)
  - Title + rationale text
  - "Apply" button (for param changes — calls hot-reload API)
  - "Dismiss" button (hides and starts cooldown)
  - Timestamp when suggestion was generated
- Dismissed suggestions go to a "Recently Dismissed" collapsible section

### 2.3 WebSocket Event

```python
emit_suggestions(session_id, suggestions_list)  # New event
```

Frontend listens on `mmm_suggestions` event and updates the panel in real-time.

### 2.4 API Endpoints

```
GET  /api/mmm/session/<id>/suggestions       → current active suggestions
POST /api/mmm/session/<id>/suggestions/apply  → apply a param_change suggestion
POST /api/mmm/session/<id>/suggestions/dismiss → dismiss with cooldown
```

---

## 3. SUGGESTION RULES (Priority-ordered)

### 3.1 Risk Warnings (Critical/High)

| Rule ID | Condition | Priority | Suggestion |
|---------|-----------|----------|------------|
| `RW-01` | `total_lots > 0.85 × max_total_exposure` AND `max_total_exposure > 0` | critical | "Total exposure at 85%+ of ceiling. Consider closing some frozen positions or reducing max_lots_per_side." |
| `RW-02` | Active loss approaching `max_loss_amount` (within 20%) | critical | "P&L approaching max loss limit (-$X of -$Y). Consider tightening positions or reducing lots." |
| `RW-03` | `frozen_total_lots > active_lots × 2` on any side | high | "CE side has 60 frozen vs 30 active lots. Frozen baggage is 2:1. Consider enabling shift_recycle or manually closing cheap frozen positions." |
| `RW-04` | Margin tier is YELLOW for 3+ consecutive beats | high | "Margin has been YELLOW for 15+ minutes. Consider reducing position size before it escalates." |
| `RW-05` | Asymmetry ratio > `rebalance_asymmetry_threshold` | medium | "CE/PE lot ratio is 6.2:1 (threshold: 5.0). Heavy CE side increases directional risk. M3 rebalancing is {enabled/disabled}." |

### 3.2 Parameter Tuning (Medium)

| Rule ID | Condition | Priority | Suggestion |
|---------|-----------|----------|------------|
| `PT-01` | `frozen_total_lots > 20` AND `shift_recycle_enabled == False` | medium | "You have 45 frozen lots. Enable shift_recycle to automatically clean them during strikes shifts." Action: `{shift_recycle_enabled: true}` |
| `PT-02` | `harvest_pressure_threshold > 0.8` AND capacity pressure > 0.7 | medium | "Lot utilization is 72% but harvest threshold is 80%. Lowering to 0.6 would start freeing capacity earlier." Action: `{harvest_pressure_threshold: 0.6}` |
| `PT-03` | Premium at active strike dropped below `close_at_threshold × 3` (e.g., $15 when threshold is $5) | low | "CE active premium is $14.50, approaching close-at-5 territory. Theta is decaying this position rapidly — profitable close likely within 2-3 heartbeats." |
| `PT-04` | Session running 6+ hours and `adaptive_interval_enabled == False` | low | "Session has been running 6 hours without adaptive intervals. Near expiry, faster checks help catch rapid theta decay." Action: `{adaptive_interval_enabled: true}` |
| `PT-05` | `wind_down_enabled == False` AND `< 3 hours to expiry` | high | "Less than 3 hours to expiry with wind-down disabled. Consider enabling to protect profits." Action: `{wind_down_enabled: true, wind_down_hours_before_expiry: 2.5}` |
| `PT-06` | `max_total_exposure == 0` (auto mode) AND total exposure > 1.5× cap | medium | "max_total_exposure is auto (2×cap = 200). Your actual exposure is 175. Consider setting an explicit ceiling." Action: `{max_total_exposure: 180}` |

### 3.3 Opportunity Alerts (Low/Medium)

| Rule ID | Condition | Priority | Suggestion |
|---------|-----------|----------|------------|
| `OA-01` | A frozen position has premium ≤ $5 (close-at-5 candidate but might be at wrong strike) | low | "Frozen CE position at strike 72000 (15 lots) has decayed to $3.20. Consider closing manually for profit." |
| `OA-02` | CE/PE premium imbalance > 3:1 | medium | "CE premium ($180) is 4x PE premium ($45). Market is heavily skewed bullish. Consider reducing CE exposure."  |
| `OA-03` | Session profit target achieved (if configured) | medium | "Session P&L of $45.20 exceeds typical 0DTE target. Consider taking profit and stopping the session." |
| `OA-04` | All frozen positions profitable (can be closed for net positive) | low | "All 8 frozen positions have decayed significantly. Total buyback cost ~$12.40 for positions collected at $89.00. Net profit on cleanup." |

### 3.4 Market Behavior Suggestions

| Rule ID | Condition | Priority | Suggestion |
|---------|-----------|----------|------------|
| `MB-01` | IV spike detected (vol regime HIGH or ELEVATED) AND `regime_enabled == False` | high | "IV spiked 35% in last 5 minutes. Regime controls are OFF. Consider enabling to auto-block new sells during vol spikes." Action: `{regime_enabled: true}` |
| `MB-02` | Trend tier ≥ 2 (Guard) for 3+ consecutive beats | medium | "BTC has moved 1.2% from anchor (sustained trend). Algo is blocking dangerous-side sells. Consider manual position reduction if trend continues." |
| `MB-03` | BTC spot within 1% of an original entry strike | high | "BTC ($69,200) is approaching your CE entry strike ($69,600). ATM gamma risk is elevated. Consider enabling wind_down_on_atm or reducing CE lots." |
| `MB-04` | Circuit breaker has been OPEN for 2+ minutes | medium | "Exchange API has been unreachable for 2+ minutes (circuit breaker OPEN). Algo running on cached prices. Monitor exchange status." |
| `MB-05` | Expiry in < 30 minutes AND `stop_adjustment_mins < 10` | high | "Only 25 minutes to expiry. stop_adjustment_mins is set to 5 — algo will still adjust for 20 more minutes. Consider stopping adjustments earlier." Action: `{stop_adjustment_mins: 25}` |

---

## 4. EVALUATION FREQUENCY & PERFORMANCE

- Run suggestion evaluation **once per heartbeat** (not per second)
- Suggestions cached in memory — only re-evaluated when context changes
- Each rule is a pure function: `(context) → Optional[Suggestion]`
- Total evaluation should take < 5ms (all in-memory, no I/O)
- Dismissed suggestions tracked in `session['_dismissed_suggestions']` dict with expiry timestamps

---

## 5. FRONTEND UX MOCKUP

```
┌─────────────────────────────────────────────────────────────────┐
│ 💡 Suggestions (2)                                    [Collapse]│
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ HIGH — Enable Wind-Down Before Expiry                       │
│ Less than 3 hours to expiry with wind-down disabled.           │
│ Consider enabling to protect profits in the final stretch.      │
│ [Apply: Enable Wind-Down]  [Dismiss]        2 min ago           │
├─────────────────────────────────────────────────────────────────┤
│ 💡 MEDIUM — Enable Shift-Time Recycle                          │
│ CE side has 45 frozen lots (vs 30 active). Shift-time recycle  │
│ would automatically clean cheap frozen lots during shifts.      │
│ [Apply: Enable]  [Dismiss]                  5 min ago           │
├─────────────────────────────────────────────────────────────────┤
│ ▸ Recently Dismissed (1)                                        │
│   Adaptive interval (dismissed 12 min ago)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. IMPLEMENTATION PLAN

### Phase 1: Core Infrastructure (1 day)
- Create `mmm_suggestions.py` with `Suggestion` dataclass and `evaluate_all()` framework
- Add `emit_suggestions` to `mmm_websocket.py`
- Hook into monitor heartbeat (after all other processing)
- API endpoints for get/apply/dismiss
- Create `MMMSuggestionPanel.js` with basic rendering

### Phase 2: Risk Warning Rules (0.5 day)
- Implement rules RW-01 through RW-05
- These are the highest value — prevent operator mistakes

### Phase 3: Market Behavior Rules (0.5 day)
- Implement rules MB-01 through MB-05
- Connect to existing regime, IV, and trend data

### Phase 4: Parameter Tuning + Opportunities (0.5 day)
- Implement remaining rules (PT-*, OA-*)
- "Apply" button integration with hot-reload API

### Phase 5: Polish (0.5 day)
- Cooldown tracking, dismissed state persistence
- Notification count badge on session tab
- Optional Telegram notification for CRITICAL suggestions

---

## 7. KEY DESIGN DECISIONS

1. **No auto-execution.** Suggestions never change parameters or close positions without operator clicking "Apply."
2. **Cooldown prevents nagging.** Once dismissed, a suggestion won't reappear for N heartbeats (configurable per rule).
3. **No new data fetching.** All suggestion logic uses data already available in the heartbeat context (premiums, pnl, regime, margin, session state). Zero additional API calls.
4. **Prioritized display.** Critical suggestions pin to top. Low suggestions can be collapsed. Dashboard never feels cluttered.
5. **Backend-driven logic, frontend-rendered.** The evaluation runs in Python (same codebase, testable), frontend just renders the result. No complex JS logic.

---

*This is a suggestion system design. Review, adjust rules/priorities, and confirm before implementation begins.*
