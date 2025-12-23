# Manual Trade Protection Rules

**Last Updated**: November 14, 2025

## Core Principle
**The Async Trading Bot MUST NEVER interfere with manual trades placed by the user.**

## Bot Responsibilities

### Async GridBot (Trading Bot)
✅ **ALLOWED**:
- Place its own grid limit orders
- Cancel its own pending orders
- Manage positions it created
- Read all exchange data for decision making

❌ **FORBIDDEN**:
- Sync/track bracket orders (manual SL/TP)
- Sync/track stop orders
- Sync/track stop-limit orders
- Sync/track market orders
- Cancel any order it didn't create
- Modify manual positions

### Guardian Bot (Safety Monitor)
✅ **ALLOWED**:
- Read ALL positions (manual + bot-placed)
- Read ALL orders (manual + bot-placed)
- Calculate total exposure
- Monitor account risk
- Send alerts/warnings

❌ **FORBIDDEN**:
- Place any trades
- Cancel any orders
- Modify any positions

## Implementation Details

### Order Type Detection
When bot finds existing orders on exchange, it checks:

```python
order_type = order.get('order_type')          # Must be 'limit_order'
bracket_order = order.get('bracket_order')    # Must be None/False
stop_order_type = order.get('stop_order_type') # Must be None
```

### Skip Conditions
Bot will **SKIP** (not sync) orders that are:
1. **Bracket Orders**: `bracket_order == True`
   - These are manual stop-loss or take-profit brackets
   - Example: User's $3,200 stop order

2. **Stop Orders**: `stop_order_type` is set
   - stop_loss_order
   - stop_market_order
   - trailing_stop_order

3. **Non-Limit Orders**: `order_type != 'limit_order'`
   - market_order
   - stop_limit_order
   - Any other order type

### Sync Conditions
Bot will **ONLY SYNC** orders that are:
- `order_type == 'limit_order'` (plain limit order)
- `bracket_order == False or None` (not part of bracket)
- `stop_order_type == None` (not a stop order)
- Matches bot's trading mode (buy for LONG, sell for SHORT)

## Testing Verification

### Test Case: Manual Stop Order at $3,200
**Setup**:
- User placed manual bracket stop-loss order
- Order ID: 1035396049
- Price: $3,200
- Type: Bracket - SL

**Detection**:
```
Order 1035396049: buy 75 @ $3,200.00 [type=limit_order]
📋 Order details: type=limit_order, bracket=True, stop_type=stop_loss_order
⏭️  Skipping bracket order 1035396049 - this is a manual SL/TP order
```

**Result**: ✅ **CORRECTLY SKIPPED** - Bot did not sync or track this order

## Logging

Bot logs show:
1. **Order Detection**: Type, bracket status, stop type for every order
2. **Skip Messages**: Clear indication when skipping manual orders
3. **Sync Messages**: Only when syncing bot's own orders

Example log:
```
⚠️  Found 1 existing open order(s) on exchange:
   Order 1035396049: buy 75 @ $3,200.00 [type=limit_order]
   📋 Order details: type=limit_order, bracket=True, stop_type=stop_loss_order
   ⏭️  Skipping bracket order 1035396049 - this is a manual SL/TP order
⚠️  Existing orders found but none are bot-managed LIMIT orders - continuing with new order
```

## Safety Guarantees

✅ User can place manual stop losses without interference
✅ User can place manual take profits without interference
✅ User can use bracket orders safely
✅ Bot only manages its own plain limit orders
✅ Clear separation between bot and manual trading
✅ Guardian can monitor everything without trading

## Code Location

**Implementation**: `bot/strategy/async_gridbot.py`
- Method: `_place_initial_order()` (lines ~1640-1700)
- Order sync logic with type checking

**Related Files**:
- `bot/api/async_delta_client.py` - Exchange API
- `bot/volatility/iv_rv_tracker.py` - Guardian monitoring

## Emergency Override

If bot mistakenly syncs a manual order:
1. Stop the bot: `pm2 stop gridbot-live`
2. Delete state files: `rm runtime_state*.json`
3. Restart bot: `pm2 restart gridbot-live`
4. Bot will re-check orders and skip manual orders correctly

## Version History

- **v2.0.0** (Nov 14, 2025): Initial implementation with bracket order detection
- Added `order_type`, `bracket_order`, `stop_order_type` checking
- Verified working with manual stop order at $3,200
