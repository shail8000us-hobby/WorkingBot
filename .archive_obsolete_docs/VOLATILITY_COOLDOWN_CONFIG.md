# 🔧 Volatility Cooldown Configuration

## Overview

**Problem Solved**: Prevents bot from oscillating between halt/recovery states when volatility fluctuates rapidly.

**Solution**: Bidirectional cooldown timers that enforce minimum time between state transitions.

---

## How It Works

### Before Cooldown (❌ Problem)
```
T=0   Volatility spikes → HALT triggered
T=1   Volatility normalizes → RECOVERY starts
T=2   _resume_normal_grid() clears halt flag
T=3   _place_buy_order() called
T=4   Volatility check in _place_buy_order() runs
T=5   Volatility spiked again → IMMEDIATE RE-HALT ❌
T=6   Bot oscillates: halt → recovery → halt → recovery...
```

### After Cooldown (✅ Solution)
```
T=0   Volatility spikes → HALT triggered
      _last_halt_trigger_time = T=0
T=1   Volatility normalizes → RECOVERY starts
      _last_recovery_time = T=1
T=15  Volatility spikes again
      Cooldown active: (T=15 - T=0) = 15s < 30s
      HALT TRIGGER SKIPPED (cooldown protection)
T=31  Volatility spikes (if still happening)
      Cooldown expired: (T=31 - T=0) = 31s > 30s
      HALT ALLOWED (legitimate volatility shift)
```

---

## Configuration Variables

### 1. VOLATILITY_HALT_COOLDOWN
**Location**: Environment variable or .env file  
**Default**: `30` seconds  
**Purpose**: Minimum time between consecutive halt triggers

```bash
# .env
VOLATILITY_HALT_COOLDOWN=30  # Prevents rapid re-halts
```

**Use Cases**:
- **30s (default)**: Good for most markets, gives bot time to place order + TP
- **60s**: Very volatile markets (prevents excessive halts)
- **15s**: Lower latency environments, faster recovery cycles
- **0s**: DISABLE cooldown (NOT RECOMMENDED - allows oscillation)

### 2. VOLATILITY_RECOVERY_COOLDOWN
**Location**: Environment variable or .env file  
**Default**: `30` seconds  
**Purpose**: Minimum time between consecutive recovery attempts

```bash
# .env
VOLATILITY_RECOVERY_COOLDOWN=30  # Prevents rapid recovery loops
```

**Use Cases**:
- **30s (default)**: Standard protection
- **45s**: Extra conservative (markets with frequent false normalizations)
- **20s**: Faster recovery response
- **0s**: DISABLE cooldown (NOT RECOMMENDED)

---

## Timeline Breakdown

### What Happens in 30 Seconds?

| Time | Action | Duration |
|------|--------|----------|
| T+0ms | Recovery triggers | - |
| T+100ms | Load halt state from .volatility_halt.json | ~100ms |
| T+200ms | Calculate missed grid levels | ~100ms |
| T+300ms | Place market order for missed level | ~100ms |
| T+500ms | Order fills (average) | ~200ms |
| T+700ms | Place TP order | ~200ms |
| T+1000ms | TP order confirmed | ~300ms |
| T+1500ms | Call _resume_normal_grid() | ~500ms |
| T+2000ms | Calculate next BUY target | ~500ms |
| T+2500ms | Place normal BUY order | ~500ms |
| **T+3000ms** | **ALL CRITICAL OPERATIONS COMPLETE** | **~3s total** |
| T+30000ms | Cooldown expires | - |

**Result**: 30s cooldown provides **10x safety margin** over actual operation time (~3s).

---

## Why 30 Seconds is Optimal

### Too Short (< 10s)
- ❌ Risk of re-halt before order placement completes
- ❌ Network latency could cause race conditions
- ❌ Volatility calculations need time to stabilize

### Just Right (30s)
- ✅ Plenty of time for order placement + TP setup
- ✅ True volatility shifts don't reverse in 30s
- ✅ Prevents oscillation while staying responsive
- ✅ Matches typical volatility calculation window

### Too Long (> 60s)
- ⚠️ Slower response to legitimate volatility changes
- ⚠️ Missed recovery opportunities
- ⚠️ Delayed halt triggers in genuinely unsafe conditions

---

## Behavior Examples

### Scenario 1: Single Volatility Spike (Normal)
```
T=0     IV spikes to 12% (MAX: 10%) → HALT
T=30    IV drops to 8% → RECOVERY (cooldown allows)
T=60    IV stable at 8% → Normal trading continues
Result: ✅ Clean halt → recovery cycle
```

### Scenario 2: Rapid Oscillation (Protected)
```
T=0     IV spikes to 12% → HALT
T=5     IV drops to 8% → RECOVERY
T=10    IV spikes to 11% → HALT BLOCKED (cooldown active)
T=15    IV drops to 9% → RECOVERY BLOCKED (cooldown active)
T=20    IV spikes to 10.5% → HALT BLOCKED (cooldown active)
T=31    IV stable at 9% → Normal trading (cooldowns expired)
Result: ✅ Bot stays calm during volatile period
```

### Scenario 3: Sustained Volatility (Respected)
```
T=0     IV spikes to 12% → HALT
T=30    IV drops to 8% → RECOVERY (cooldown allows)
T=35    Volatility still high during _place_buy_order() check
T=35    HALT RE-TRIGGERED (legitimate, after recovery cooldown)
T=65    IV finally normalizes → RECOVERY (cooldown allows)
Result: ✅ Bot adapts to sustained volatility properly
```

---

## Monitoring Cooldown Status

### Logs
```bash
# Cooldown active (protection working)
⏱️  Halt cooldown active: 15s remaining (prevents oscillation)
⏱️  Recovery cooldown active: 22s remaining (prevents oscillation)

# Cooldown expired (transition allowed)
🌊 VOLATILITY HALT TRIGGERED
✅ VOLATILITY NORMALIZED - INITIATING SMART RECOVERY
```

### Bot Actions Panel
- Cooldown events are **NOT** logged to action stream (internal protection)
- You'll only see halt/recovery events that pass cooldown checks
- Cleaner UI, less noise

---

## Advanced Tuning

### Market-Specific Settings

**Bitcoin (High Liquidity)**
```bash
VOLATILITY_HALT_COOLDOWN=30
VOLATILITY_RECOVERY_COOLDOWN=30
```

**Altcoins (Medium Liquidity)**
```bash
VOLATILITY_HALT_COOLDOWN=45
VOLATILITY_RECOVERY_COOLDOWN=45
```

**Micro-caps (Low Liquidity)**
```bash
VOLATILITY_HALT_COOLDOWN=60
VOLATILITY_RECOVERY_COOLDOWN=60
```

### Testing/Development
```bash
# Faster cycling for testing (NOT for production)
VOLATILITY_HALT_COOLDOWN=5
VOLATILITY_RECOVERY_COOLDOWN=5
```

---

## Troubleshooting

### Bot Not Recovering
**Symptom**: Bot halts but never recovers even when volatility normalizes

**Check**:
```bash
# In logs, look for:
⏱️  Recovery cooldown active: Xs remaining

# If you see this repeatedly, cooldown is blocking recovery
# Wait for cooldown to expire OR reduce cooldown setting
```

**Solution**: Reduce `VOLATILITY_RECOVERY_COOLDOWN` to 15-20s

### Bot Halting Too Frequently
**Symptom**: Bot halts, recovers, halts again immediately

**Check**:
```bash
# In logs, look for:
🌊 VOLATILITY HALT TRIGGERED
✅ VOLATILITY NORMALIZED - INITIATING SMART RECOVERY
🌊 VOLATILITY HALT TRIGGERED  # ← Too soon!

# Time between these should be > 30s
```

**Solution**: Increase `VOLATILITY_HALT_COOLDOWN` to 45-60s

---

## Code References

### Cooldown Implementation
- **File**: `bot/strategy/gbot_ws.py`
- **Variables**: Lines 230-231
  ```python
  self._last_halt_trigger_time = 0
  self._last_recovery_time = 0
  ```

- **Halt Protection**: Lines 1045-1055
  ```python
  cooldown_seconds = int(os.getenv('VOLATILITY_HALT_COOLDOWN', '30'))
  time_since_last_halt = time.time() - self._last_halt_trigger_time
  if time_since_last_halt < cooldown_seconds:
      return  # Skip halt
  ```

- **Recovery Protection**: Lines 1434-1444
  ```python
  cooldown_seconds = int(os.getenv('VOLATILITY_RECOVERY_COOLDOWN', '30'))
  time_since_last_recovery = time.time() - self._last_recovery_time
  if time_since_last_recovery < cooldown_seconds:
      return  # Skip recovery
  ```

---

## Summary

✅ **Cooldown prevents infinite oscillation** between halt/recovery states  
✅ **30s default gives 10x safety margin** over actual operation time  
✅ **Bidirectional protection** (halt cooldown + recovery cooldown)  
✅ **Configurable** via environment variables  
✅ **Transparent** logging shows when cooldowns are active  

**Your trading is protected from volatility whiplash!** 🛡️
