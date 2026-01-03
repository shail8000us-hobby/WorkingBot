# Authority Layers Architecture

## The Critical Question: "Why Is Nothing Happening?"

In a multi-instrument trading system, the most dangerous moment is when a trader looks at the screen and sees "Trading Halted" without understanding **why**. This document describes the Authority Layers architecture that makes the answer to "why" unmissable.

## The Three Decision-Makers

Your trading system has **three independent authorities** that can prevent trading:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHORITY CHAIN                               │
│  (In order of precedence - higher overrides lower)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 💓 HEARTBEAT    Technical Permission                        │
│     ─────────────                                                │
│     "Is the system ALIVE?"                                       │
│                                                                  │
│     Monitors:                                                    │
│     • API connection health                                      │
│     • WebSocket connectivity                                     │
│     • Backend process status                                     │
│     • Exchange reachability                                      │
│                                                                  │
│     States:                                                      │
│     • alive    → System operational                              │
│     • degraded → Partial connectivity                            │
│     • dead     → System down                                     │
│                                                                  │
│     If dead: NOTHING TRADES. Fix infrastructure first.          │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  2. 🛡️ GUARDIAN     Capital Permission                          │
│     ─────────────                                                │
│     "Is trading ALLOWED by risk rules?"                          │
│                                                                  │
│     Monitors:                                                    │
│     • Daily loss limits                                          │
│     • Position size limits                                       │
│     • Margin requirements                                        │
│     • Drawdown thresholds                                        │
│                                                                  │
│     States:                                                      │
│     • allowed  → All risk metrics OK                             │
│     • cautious → Approaching limits                              │
│     • blocked  → Risk limit reached                              │
│                                                                  │
│     If blocked: Trading FORBIDDEN even if system is alive.      │
│     This is protective, not an error.                            │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  3. 📈 TRADING      Strategic Intent                             │
│     ─────────────                                                │
│     "What does the STRATEGY want to do?"                         │
│                                                                  │
│     Monitors:                                                    │
│     • Strategy signals                                           │
│     • Grid level calculations                                    │
│     • Market conditions                                          │
│     • User commands                                              │
│                                                                  │
│     Intents:                                                     │
│     • active → Strategy executing trades                         │
│     • hold   → Intentionally waiting (user or strategy)         │
│     • exit   → Closing all positions                             │
│     • error  → Strategy logic error                              │
│                                                                  │
│     Sources:                                                     │
│     • strategy → Bot decided this                                │
│     • user     → Human clicked pause                             │
│     • system   → System forced this state                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Why Three Authorities Matter

Consider these three scenarios where "Trading Halted" appears:

### Scenario 1: Heartbeat is Dead
```
💓 Heartbeat: DEAD (no heartbeat for 45s)
🛡️ Guardian:  allowed
📈 Trading:   active

DIAGNOSIS: System infrastructure is down
ACTION:    Check backend process, API connectivity
URGENCY:   HIGH - system broken, needs immediate attention
```

### Scenario 2: Guardian is Blocking
```
💓 Heartbeat: alive
🛡️ Guardian:  BLOCKED (daily loss limit: $500/$500)
📈 Trading:   active

DIAGNOSIS: Risk protection triggered
ACTION:    Review limits, wait for next day, or adjust risk
URGENCY:   LOW - this is protection working correctly
```

### Scenario 3: User Paused
```
💓 Heartbeat: alive
🛡️ Guardian:  allowed
📈 Trading:   HOLD (paused by user)

DIAGNOSIS: User intentionally paused
ACTION:    Click resume when ready
URGENCY:   NONE - this is intentional
```

**Without authority separation, all three show as "Trading Halted".**
**With authority separation, the trader knows exactly what to do.**

## Controlling Authority

At any moment, one authority is "in control" - it's the one blocking trading (if anything is blocking) or the one actively trading (if nothing is blocking).

```typescript
type ControllingAuthority = 
  | 'heartbeat'  // System down, everything blocked
  | 'guardian'   // Risk limits hit, trading forbidden
  | 'user'       // User paused, intentional hold
  | 'trading';   // Strategy is in control
```

The derivation logic:

```typescript
function deriveControllingAuthority(authority: AuthorityState): ControllingAuthority {
  // Heartbeat takes precedence - if system is down, nothing else matters
  if (authority.heartbeat.status === 'dead' || authority.heartbeat.status === 'unhealthy') {
    return 'heartbeat';
  }
  
  // Guardian takes precedence over trading intent
  if (authority.guardian.status === 'blocked') {
    return 'guardian';
  }
  
  // User pause takes precedence over strategy
  if (authority.trading.intent === 'hold' && authority.trading.source === 'user') {
    return 'user';
  }
  
  // Strategy is in control
  return 'trading';
}
```

## UI Implementation: AuthorityPanel

The `AuthorityPanel` component shows all three authorities in a compact, scannable format:

```
┌────────────────────────────────────────┐
│  Authority Chain                        │
├────────────────────────────────────────┤
│  💓 Heartbeat  ● alive   System OK     │
│  🛡️ Guardian   ● allowed             │
│  📈 Trading    ● active  [CONTROLLER] │ ← Badge shows who's in control
├────────────────────────────────────────┤
│  🟢 Trading ACTIVE: Strategy in control │ ← Summary for quick reading
└────────────────────────────────────────┘
```

When something is blocking:

```
┌────────────────────────────────────────┐
│  Authority Chain                        │
├────────────────────────────────────────┤
│  💓 Heartbeat  ● alive   System OK     │
│  🛡️ Guardian   ● BLOCKED [CONTROLLER] │ ← Red, badge shows blocking
│       Daily loss limit reached          │
│  📈 Trading    ○ active               │ ← Dimmed, not in control
├────────────────────────────────────────┤
│  🔴 Trading FORBIDDEN: Daily loss limit │ ← Red summary
└────────────────────────────────────────┘
```

## Color Coding

| Authority | State | Color | Meaning |
|-----------|-------|-------|---------|
| Heartbeat | alive | Green | System operational |
| Heartbeat | degraded | Yellow | Partial connectivity |
| Heartbeat | dead | Red | System down |
| Guardian | allowed | Green | All limits OK |
| Guardian | cautious | Yellow | Approaching limits |
| Guardian | blocked | Red | Limit reached |
| Trading | active | Green | Strategy executing |
| Trading | hold | Yellow | Intentionally waiting |
| Trading | exit | Orange | Closing positions |
| Trading | error | Red | Strategy error |

## Backend Integration

The backend returns authority data in every instance state response:

```json
{
  "identity": { ... },
  "tradingState": "paused",
  "authority": {
    "heartbeat": {
      "status": "alive",
      "lastSeen": 1703456789000,
      "message": "System operational"
    },
    "guardian": {
      "status": "blocked",
      "reason": "Daily loss limit reached",
      "limits": {
        "dailyLoss": { "current": 500, "max": 500, "percent": 100 }
      }
    },
    "trading": {
      "intent": "active",
      "source": "strategy",
      "reason": "Strategy executing normally",
      "since": 1703450000000
    }
  },
  "controlledBy": "guardian"
}
```

## WebSocket Channels

Authority updates are pushed via WebSocket:

- `{instanceId}:authority:heartbeat` - Heartbeat status changes
- `{instanceId}:authority:guardian` - Guardian status changes
- `{instanceId}:authority:trading` - Trading intent changes

## Key Design Principles

1. **Separation of Concerns**: Each authority monitors different things
2. **Clear Precedence**: Heartbeat > Guardian > User > Trading
3. **Always Visible**: All three authorities always shown, not just the blocking one
4. **Controller Badge**: The controlling authority is always marked
5. **Actionable Messages**: Each state tells you what to DO, not just what IS
6. **Color Consistency**: Same colors mean same things across all authorities

## Migration from v1

In v1, we had a single `tradingState` that collapsed all authorities:
- `active` → Trading
- `paused` → Could be user, guardian, or strategy
- `halted` → Could be heartbeat, guardian, or error
- `error` → Could be heartbeat or trading

v2 maintains `tradingState` for backward compatibility but derives it FROM authorities:

```typescript
function deriveTradingState(authority: AuthorityState): TradingState {
  const controller = deriveControllingAuthority(authority);
  
  switch (controller) {
    case 'heartbeat':
      return 'halted';
    case 'guardian':
      return 'halted';
    case 'user':
      return 'paused';
    case 'trading':
      return authority.trading.intent === 'error' ? 'error' : 
             authority.trading.intent === 'hold' ? 'paused' : 'active';
  }
}
```

## Testing Checklist

When implementing authority layers, verify:

- [ ] All three authorities are visible in normal state
- [ ] Heartbeat failure shows as CRITICAL (red card border, pulsing)
- [ ] Guardian block shows as WARNING (yellow, protective)
- [ ] User pause shows as PAUSED (yellow, intentional)
- [ ] The controlling authority has a visible badge
- [ ] Summary section clearly states WHY and WHO
- [ ] Colors are consistent across all views
- [ ] Authority updates via WebSocket reflect immediately
- [ ] Card severity derives from controlling authority, not just state
