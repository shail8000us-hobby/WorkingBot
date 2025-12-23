# 🎭 HumanLogger Narrative Engine Upgrade - Complete Documentation

## 📋 Executive Summary

The HumanLogger has been transformed from a simple rate-limited logger into a **context-aware, narrative-driven commentary engine** that produces trader-style logs with memory, mood tracking, and intelligent story arcs.

**✅ 100% Backward Compatible** - All existing method names and signatures preserved!

---

## 🧠 NEW NARRATIVE ENGINE ARCHITECTURE

### 1. **Mood State Machine**

The logger now tracks its "mood" based on recent events:

```python
class Mood(Enum):
    CALM = "calm"           # Normal, steady operation
    AGGRESSIVE = "aggressive"  # Multiple rapid fills/actions
    ALERT = "alert"         # Warning state, watching closely
    STRESSED = "stressed"   # Multiple errors/issues
    RECOVERING = "recovering" # Coming back from issues
    EXCITED = "excited"     # Profitable fills, good momentum
```

**Mood Transitions:**
- **3+ errors in last 10 events** → STRESSED
- **Reconnection in progress** → RECOVERING
- **3+ fills, no errors** → EXCITED
- **2+ warnings** → ALERT
- **2+ fills** → AGGRESSIVE
- **Default** → CALM

### 2. **Market Tempo Detection**

Analyzes fill patterns to detect market conditions:

```python
class MarketTempo(Enum):
    CALM = "calm"       # Slow, steady
    TRENDING = "trending"  # Directional movement
    CHOPPY = "choppy"   # Erratic, volatile
```

**Detection Logic:**
- **3+ fills in under 60 seconds** → CHOPPY
- **3+ consecutive BUYs or SELLs** → TRENDING
- **Otherwise** → CALM

### 3. **Rolling Memory System**

The logger maintains a **context window of last 20 events**:

```python
self._event_memory = deque(maxlen=20)  # Rolling context
```

**Tracked Memory:**
- Event type (fill, error, warning, etc.)
- Event timestamp
- Event data (price, side, etc.)

**Memory-Based Features:**
- Last 5 events influence mood
- Fill streaks tracked
- Error streaks tracked
- Average fill spacing calculated
- Last disconnect time remembered

### 4. **Multi-Event Story Arcs**

Special sequences of events trigger **narrative story arcs**:

#### **Reconnection Arc**
```
disconnected → reconnecting → authenticated → subscriptions → restored
```

**Example Output:**
```
🚨 Lost the wire… reconnecting.
🔄 RECONNECTING NOW... Restarting all systems. Hang tight!
🔐 Authenticated! We're back in...
✅ Subscribed! Feed restored. Let's continue.
```

#### **Rapid Fill Arc**
When 3+ fills occur in succession:
```
🔥 Getting fills back-to-back… bot's cooking today!
```

### 5. **Context-Aware Narrative Templates**

Rich template library with rotational selection:

```python
NARRATIVE_TEMPLATES = {
    'buy_order': [
        "📈 Long attempt in — buy @ ${price}.",
        "Another BUY placed. Fishing below the price…",
        "Buy ladder extended. Let's see if market dips.",
        "Putting in another buy. Building the position...",
    ],
    'sell_order': [...],
    'buy_fill': [...],
    'sell_fill': [...],
    'tp_hit': [...],
    'connection_lost': [...],
    'connection_restored': [...],
    'rapid_fills': [...],
    'error_recovery': [...],
    'api_slow': [...],
    'queue_swelling': [...],
}
```

**Template Selection Strategy:**
- Rotates based on order count
- Mood influences selection (excited = more enthusiastic)
- Context modifies output (rapid fills = special template)
- Milestones add commentary (every 10th order, every 5th fill)

---

## 🎯 KEY FEATURES

### ✅ Maintained Features
- All existing method signatures (**100% compatible**)
- Rate limiting (3-second default)
- Force logging option
- Multiple log levels (BOT_OK, WARNING, ALERT, CRITICAL)
- Narrative mode toggle

### ⭐ NEW Features

#### **1. Streak Tracking**
```python
self._fill_streak = 0        # Consecutive fills
self._error_streak = 0       # Consecutive errors
self._warning_streak = 0     # Consecutive warnings
```

#### **2. Side Tracking**
```python
self._last_side = None           # Last order side
self._consecutive_buys = 0       # Consecutive BUY orders
self._consecutive_sells = 0      # Consecutive SELL orders
```

#### **3. Timing Analysis**
```python
self._last_fill_time = None      # Timestamp of last fill
self._avg_fill_spacing = 60.0    # Rolling average between fills
self._rapid_fill_window = deque(maxlen=5)  # Recent fill timestamps
```

#### **4. Story Arc System**
```python
self._in_reconnect_arc = False   # Currently in reconnection story
self._reconnect_steps = []       # Steps completed in arc
```

#### **5. Session Statistics**
```python
self._orders_placed = 0          # Total orders this session
self._orders_filled = 0          # Total fills this session
self._session_start_time = time.time()  # Session start
```

---

## 🔧 HOW TO EXTEND

### Adding New Narrative Templates

1. **Add to NARRATIVE_TEMPLATES dictionary:**
```python
NARRATIVE_TEMPLATES = {
    # ... existing templates ...
    'new_scenario': [
        "First narrative option with context.",
        "Second narrative option with different tone.",
        "Third option for variety.",
    ],
}
```

2. **Use in methods:**
```python
def my_new_method(self, price: float):
    """New scenario handler"""
    self._add_to_memory('new_scenario', price)
    
    narrative = self._get_narrative_for_context(
        self.NARRATIVE_TEMPLATES['new_scenario']
    )
    
    self._log_with_level(
        LogLevel.BOT_OK,
        f"Technical message",
        key="new_scenario",
        narrative=narrative
    )
```

### Creating New Story Arcs

```python
# 1. Initialize arc flag
self._in_my_arc = False
self._my_arc_steps = []

# 2. Start arc on trigger event
def trigger_event(self):
    self._in_my_arc = True
    self._my_arc_steps = ['started']
    # Log first step...

# 3. Continue arc in subsequent events
def next_event(self):
    if self._in_my_arc:
        self._my_arc_steps.append('next_step')
        # Log with arc-aware narrative...

# 4. Complete arc on final event
def final_event(self):
    if self._in_my_arc:
        self._my_arc_steps.append('completed')
        self._in_my_arc = False
        # Log completion...
```

### Adding New Moods

```python
# 1. Add to Mood enum
class Mood(Enum):
    # ... existing moods ...
    NEW_MOOD = "new_mood"

# 2. Update mood detection in _update_mood()
def _update_mood(self):
    # ... existing logic ...
    
    if my_condition:
        self._mood = Mood.NEW_MOOD
```

---

## 📊 SIMULATED SCENARIOS

### **Scenario 1: Startup → First Order → Fill → TP**

```
💬 🚀 WE'RE LIVE! Bot is armed and ready. Took 2.3s to boot up. Let's make some money!
💬 📈 Long attempt in — buy @ $50,000.
💬 ✅ BUY FILLED @ $50,000! Market came to us.
💬 Position: 1 contracts. +$50.00 and climbing! 💰
💬 💰 TP HIT! Bag locked at $50,250.
💬 Profit booked. Re-arming the next step.
```

### **Scenario 2: Connection Lost → Reconnect → Resume**

```
💬 🚨 Lost the wire… reconnecting.
💬 🔄 RECONNECTING NOW... Restarting all systems. Hang tight!
💬 🔐 Authenticated! We're back in...
💬 ✅ Subscribed! Feed restored. Let's continue.
💬 ✅ Back online! Feed restored.
```

### **Scenario 3: Rapid BUY/SELL Fills**

```
💬 📈 Long attempt in — buy @ $49,000.
💬 ✅ BUY FILLED @ $49,000! Market came to us.
💬 📈 Another BUY placed. Fishing below the price…
💬 ✅ Sweet fill on the buy side. Entry secured.
💬 📈 Buy ladder extended. Let's see if market dips.
💬 🔥 Getting fills back-to-back… bot's cooking today!
💬 Market's cooking at $49,500! 🔥
```

### **Scenario 4: Multiple Warnings → Recovery**

```
💬 ⚠️ Hmm, haven't seen a price update in 8s. Keeping an eye on this...
💬 ⚠️ API feeling sluggish today… retrying.
💬 ⚠️ Handler stumbled — picking it back up.
💬 Price at $50,000. Watching carefully...
💬 ✅ BUY FILLED @ $50,000! Market came to us.
💬 Minor hiccup. Already recovered.
```

---

## 🧪 INTERNAL METHODS (For Reference)

### `_add_to_memory(event_type, data=None)`
Adds event to rolling 20-event memory window.

### `_update_mood()`
Analyzes last 10 events and updates mood state.

### `_detect_market_tempo()`
Analyzes fill patterns to determine market tempo.

### `_get_narrative_for_context(base_narratives)`
Selects narrative from template list based on:
- Current mood
- Order/fill count
- Rotation strategy

### `_log_with_level(level, message, force, key, narrative)`
Core logging function with:
- Rate limiting
- Mood updates
- Narrative selection
- Memory tracking

---

## 📝 USAGE EXAMPLES

### Basic Usage (No Changes Needed)
```python
from bot.utils.human_logger import human_log

# All existing calls work unchanged
human_log.price_data_flowing(price=50000.0)
human_log.order_placed("ORD123", "BUY", 49500.0)
human_log.order_filled("ORD123", "BUY", 49500.0)
```

### Toggle Narrative Mode
```python
# Enable narrative mode (default)
human_log.narrative_mode = True

# Disable for technical format
human_log.narrative_mode = False
```

### Access Session Statistics
```python
print(f"Orders placed: {human_log._orders_placed}")
print(f"Orders filled: {human_log._orders_filled}")
print(f"Current mood: {human_log._mood.value}")
print(f"Market tempo: {human_log._market_tempo.value}")
```

---

## ⚡ PERFORMANCE CHARACTERISTICS

- **Memory footprint:** ~20 events × 100 bytes = ~2KB
- **Mood calculation:** O(10) - scans last 10 events
- **Template selection:** O(1) - simple modulo/indexing
- **Rate limiting:** O(1) - dictionary lookup
- **Overall impact:** **Negligible** - all operations are lightweight

---

## 🔒 SAFETY GUARANTEES

✅ **No external dependencies added** - Uses only standard library (time, typing, enum, collections)
✅ **No breaking changes** - All method signatures preserved
✅ **No actor message changes** - Message format unchanged
✅ **No architecture changes** - Logging system only
✅ **Backward compatible** - Can toggle narrative mode off anytime

---

## 🎬 CONCLUSION

The HumanLogger is now a **context-aware storyteller** that:
- Remembers recent events
- Tracks mood and market tempo
- Tells coherent multi-event stories
- Provides trader-friendly commentary
- Maintains full backward compatibility

**The bot now narrates its journey like a human trader would!** 🚀

---

## 📞 SUPPORT

For questions or to extend functionality, reference:
- `bot/utils/human_logger.py` - Main implementation
- This document - Architecture and usage guide
- Existing bot code - Integration examples
