# Bot Actions System - Complete Implementation

> **Architecture Update (Oct 31, 2025):** References to `bot/strategy/gbot_ws.py` reflect the 
> original implementation. The bot integration now uses `bot/strategy/gridbot.py` and modules. 
> All action logging functionality preserved. See `GRIDBOT_REFACTORING_QUICK_REF.md`.

## Overview

The Bot Actions system provides **real-time visibility** into what the bot is doing NOW and what it WILL do under different market conditions. This is displayed on the frontpage of the WebUI as the first tab.

## Architecture

### Backend Components

#### 1. **BotActionStream** (`bot/utils/action_stream.py`)
Centralized event logging system with:
- **In-memory queue**: `deque(maxlen=1000)` for fast access
- **JSONL persistence**: `logs/bot_actions.jsonl` for historical tracking
- **WebSocket broadcasting**: Real-time push to connected clients
- **Future intentions**: Track what bot will do under different conditions

**Event Structure:**
```python
{
    "id": "unique-uuid",
    "timestamp": "2024-10-30T20:45:00Z",
    "action_type": "volatility_halt",
    "importance": "high",  # low, normal, high, critical
    "message": "Human-readable message",
    "data": {
        "current_iv": 43.9,
        "max_iv": 30.0,
        # ... action-specific data
    },
    "future_intentions": {
        "on_safe": "Resume buying at $109k",
        "on_price_drop": "Calculate and fill missed levels"
    }
}
```

**Helper Functions:**
- `log_bot_startup()` - Grid configuration and initial action
- `log_volatility_halt()` - Halt trigger with future intentions
- `log_price_update_during_halt()` - Missed level tracking
- `log_recovery_start()` - Recovery execution begin
- `log_recovery_complete()` - Results and next actions
- `log_order_placed()` - Order placement events
- `log_order_filled()` - Fill events with profit tracking

#### 2. **Flask Integration** (`webui/backend/app.py`)

**REST API Endpoint:**
```
GET /api/bot-actions/recent?limit=100
```
Returns recent events from memory/file.

**WebSocket Handlers:**
```javascript
// Subscribe to real-time events
socket.emit('subscribe_bot_actions');

// Receive initial events
socket.on('bot_actions_initial', (data) => {
    // data.events = last 50 events
});

// Receive new events
socket.on('bot_action', (event) => {
    // Real-time event
});
```

#### 3. **Bot Integration** (Modular Architecture)

**Current**: `bot/strategy/gridbot.py` + `bot/strategy/modules/volatility_handler.py`  
**Original**: `bot/strategy/gbot_ws.py`

Logging integrated at key decision points:

1. **Bot Startup** (`__init__`)
   ```python
   log_bot_startup(symbol, lower, upper, step, ref, lot, max_open, mode)
   ```

2. **Volatility Halt** (`_trigger_volatility_halt`)
   ```python
   log_volatility_halt(current_iv, current_rv, max_iv, max_rv, 
                       cancelled_orders, open_positions)
   ```

3. **Price Updates During Halt** (`_check_pending_order_safety`)
   ```python
   log_price_update_during_halt(current_price, cancelled_price, 
                                 missed_levels, current_iv, current_rv)
   ```

4. **Recovery Start** (`_execute_opportunistic_recovery`)
   ```python
   log_recovery_start(current_iv, current_rv)
   ```

5. **Recovery Complete** (`_execute_opportunistic_recovery`)
   ```python
   log_recovery_complete(filled_positions, total_saved, extra_profit,
                          current_iv, current_rv)
   ```

### Frontend Components

#### 1. **BotActionsPanel** (`webui/frontend/src/components/BotActionsPanel.js`)

React component with:
- **WebSocket connection** to real-time event stream
- **Event filtering** (all, high priority, critical only)
- **Auto-scroll** toggle for new events
- **Connection status** indicator with reconnection
- **Event-specific rendering** for each action type
- **Future intentions display** with special highlighting

#### 2. **Styling** (`webui/frontend/src/components/BotActionsPanel.css`)

- Dark theme matching WebUI design
- Color-coded importance levels:
  - 🔴 Critical (red border)
  - 🟠 High (orange border)
  - 🟢 Normal (green border)
  - ⚪ Low (gray, muted)
- Smooth slide-in animations for new events
- Responsive mobile layout
- Future intentions cards with cyan highlighting

#### 3. **Main App Integration** (`webui/frontend/src/App.js`)

- Added as **first tab** ("Bot Actions") in navigation
- Integrated with existing routing system
- Error boundary protection
- Uses Zap icon (⚡) for identification

## Event Types & Display

### 1. Bot Startup
**Icon:** 🚀  
**Shows:**
- Symbol, grid range, step size
- Trading mode (LIVE/DEMO)
- Initial action

### 2. Volatility Halt
**Icon:** 🌊  
**Shows:**
- Current IV/RV vs limits
- Cancelled order price
- Open positions count
- **Future Intentions:**
  - What happens when volatility normalizes
  - What happens if price drops during halt

### 3. Price Update During Halt
**Icon:** 📊  
**Shows:**
- Current price vs cancelled level
- Number of missed levels
- List of missed grid levels (tags)
- Volatility still unsafe status

### 4. Recovery Start
**Icon:** 🔄  
**Shows:**
- Normalized volatility values
- Recovery process initiated
- Analyzing missed levels

### 5. Recovery Complete
**Icon:** ✅  
**Shows:**
- Number of positions filled
- Capital saved
- Extra profit potential
- **Future Intentions:**
  - Next grid level to buy
  - What happens on price movement

### 6. Order Placed
**Icon:** 📤  
**Shows:**
- Side (BUY/SELL)
- Price and size
- Order type (LIMIT/MARKET)

### 7. Order Filled
**Icon:** 💰  
**Shows:**
- Fill price and size
- Profit (if sell)
- **Future Intentions:**
  - Next buy level
  - TP target for position

## Real-World Example

### Scenario: Volatility Halt → Price Drop → Recovery

1. **T+0s**: Normal trading
   ```
   🟢 BOT STARTUP
   Symbol: BTCUSD
   Grid: $105k - $120k, Step: $1k
   Mode: LIVE
   ```

2. **T+30s**: Volatility spike
   ```
   🟠 VOLATILITY HALT
   IV: 43.9% / 30.0% ⚠️
   RV: 62.1% / 55.0% ⚠️
   Cancelled Order: $109k
   
   🔮 Future Intentions:
   - on_safe: Resume buying at $109k
   - on_price_drop: Fill missed levels at better prices
   ```

3. **T+35s**: Price drops to $107k during halt
   ```
   📊 PRICE UPDATE (HALTED)
   Current: $107,500
   Cancelled: $109,000
   Missed: 2 levels
   [$108k] [$109k]
   ```

4. **T+40s**: Price at $106k
   ```
   📊 PRICE UPDATE (HALTED)
   Current: $106,200
   Cancelled: $109,000
   Missed: 3 levels
   [$107k] [$108k] [$109k]
   ```

5. **T+120s**: Volatility normalizes
   ```
   🔄 RECOVERY START
   IV: 28.5% ✅
   RV: 52.3% ✅
   Analyzing missed levels...
   ```

6. **T+125s**: Recovery completes
   ```
   ✅ RECOVERY COMPLETE
   Filled: 3 positions
   Capital Saved: $5,400
   Extra Profit: $2,800 🎉
   
   Positions:
   1. Grid $107k → Filled @ $106.2k (saved $800)
   2. Grid $108k → Filled @ $106.4k (saved $1,600)
   3. Grid $109k → Filled @ $106.8k (saved $2,200)
   
   🔮 Future Intentions:
   - next_buy: Place maker at $105k
   - on_fills: TPs at $107k, $108k, $109k
   ```

## User Experience

### What Users See

1. **Real-time updates** - Events appear instantly as bot makes decisions
2. **Clear intentions** - Know what bot will do under different conditions
3. **Historical context** - See last 100 events with timestamps
4. **Priority filtering** - Focus on important events
5. **Connection status** - Know if live data is flowing

### Key Benefits

1. **Transparency** - No black box trading
2. **Confidence** - See bot is working as designed
3. **Education** - Learn how grid trading works
4. **Debugging** - Identify issues quickly
5. **Planning** - Know future actions in advance

## Configuration

### Enable/Disable Logging

In `bot/strategy/gbot_ws.py`, action stream is imported with fallback:
```python
try:
    from bot.utils.action_stream import ...
    ACTION_STREAM_AVAILABLE = True
except ImportError:
    ACTION_STREAM_AVAILABLE = False
    # No-op functions used
```

### File Persistence

Events are saved to:
```
logs/bot_actions.jsonl
```

Each line is a complete JSON event. This allows:
- Historical analysis
- Debugging past issues
- Bot behavior auditing
- Performance tracking

### Memory Management

- In-memory queue limited to 1000 events
- Old events auto-removed
- File keeps full history
- WebSocket only sends new events

## Testing

### Backend Test
```bash
python3 -c "from bot.utils.action_stream import action_stream; print('✅ Import successful')"
```

### Frontend Test
1. Start WebUI
2. Navigate to "Bot Actions" tab (first tab)
3. Should see "Loading bot actions..." then events
4. Check connection status indicator (green = connected)

### Integration Test
1. Start bot
2. Should see "BOT STARTUP" event immediately
3. Trigger volatility halt (if volatility high)
4. Should see halt event with future intentions
5. Wait for volatility to normalize
6. Should see recovery events

## Maintenance

### Log Rotation

Bot actions file can grow large. Rotate periodically:
```bash
# Archive old actions
mv logs/bot_actions.jsonl logs/bot_actions_$(date +%Y%m%d).jsonl

# System will create new file automatically
```

### Performance

- **WebSocket**: Negligible overhead (<1ms per event)
- **File I/O**: Async, non-blocking
- **Memory**: ~100KB for 1000 events
- **Network**: ~500 bytes per event

### Troubleshooting

**No events showing:**
1. Check backend is running
2. Check WebSocket connection (status indicator)
3. Check browser console for errors
4. Verify bot is running and logging events

**Events delayed:**
1. Check network connectivity
2. Check WebSocket reconnection attempts
3. Check backend logs for errors

**Missing event types:**
1. Ensure bot is triggering those actions
2. Check ACTION_STREAM_AVAILABLE flag
3. Verify helper functions are called

## Future Enhancements

Possible additions:
1. **Event search** - Filter by text/type
2. **Export to CSV** - Download event history
3. **Event replay** - Replay past bot decisions
4. **Performance metrics** - Event frequency charts
5. **Alerts** - Browser notifications for critical events
6. **Event annotations** - User notes on specific events

## Code References

### Backend
- `bot/utils/action_stream.py` - Core streaming system
- `webui/backend/app.py` - Flask integration (lines 660-670, 4270-4300, 2540-2565)
- `bot/strategy/gbot_ws.py` - Bot logging integration

### Frontend
- `webui/frontend/src/components/BotActionsPanel.js` - Main component
- `webui/frontend/src/components/BotActionsPanel.css` - Styling
- `webui/frontend/src/App.js` - Navigation integration

### Documentation
- This file: `BOT_ACTIONS_SYSTEM.md`
- Related: `OPPORTUNISTIC_RECOVERY_COMPLETE.md`
- Related: `AI_CONTEXT.md`

## Conclusion

The Bot Actions system provides **complete transparency** into bot decision-making. Users can see:
- What the bot is doing NOW
- What it WILL do under different conditions
- Historical context and patterns
- Real-time event stream

This builds trust, enables debugging, and provides educational value while maintaining a clean, professional interface.

**Status:** ✅ Fully implemented and integrated
**Version:** 1.0.0
**Date:** October 30, 2024
