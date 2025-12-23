# GridBot Monitoring System

**Created:** November 19, 2025  
**Purpose:** Proactive monitoring to detect missed fills and state issues

---

## Overview

The monitoring system provides multiple layers of verification to ensure no fills are missed and bot state remains consistent with the exchange.

### Current Modules

#### 1. BaseMonitor
**File:** `base_monitor.py`

Abstract base class for all monitors providing:
- Standard start/stop lifecycle
- Error handling and logging
- Health status reporting
- Execution loop management

#### 2. FillMonitor (Phase 1)
**File:** `fill_monitor.py`

Proactive fill verification system that:
- Tracks all placed orders
- Verifies order status every 30 seconds
- Detects missed fills within 30-60 seconds
- Triggers bot callback for processing

**Key Features:**
- Independent of WebSocket health
- Handles all Delta Exchange order states
- Automatic cleanup of old orders
- Detailed metrics and logging

---

## Integration with async_gridbot.py

### Minimal Changes Required

**1. Import (at top of file):**
```python
from bot.strategy.monitors import FillMonitor
```

**2. Initialize (in `__init__()` method):**
```python
self.fill_monitor = FillMonitor(
    api_client=self.api_client,
    event_store=self.event_store,
    product_id=self.product_id,
    check_interval=30,
    verification_delay=30,
    missed_fill_callback=self.handle_missed_fill_from_monitor
)
```

**3. Start (in `start()` method, add to async_tasks list):**
```python
async_tasks.append(
    asyncio.create_task(self.fill_monitor.start(), name="fill_monitor")
)
```

**4. Track Orders (in OrderActor after successful order placement):**
```python
# After order placed successfully
if hasattr(self, 'fill_monitor'):
    self.fill_monitor.track_order(
        order_id=order_id,
        side=side,
        price=price,
        size=size
    )
```

**5. Mark Fills (in WebSocket fill handler):**
```python
# After processing fill via WebSocket
if hasattr(self, 'fill_monitor'):
    self.fill_monitor.mark_filled(order_id, source="websocket")
```

**6. Callback Method (add to async_gridbot.py):**
```python
async def handle_missed_fill_from_monitor(
    self, 
    order_id: str, 
    fill_data: Dict[str, Any]
) -> None:
    """
    Called by fill_monitor when it detects a missed fill.
    Processes the fill through existing reconciliation logic.
    """
    log.warning(f"🔔 [FILL MONITOR] Processing missed fill: {order_id}")
    
    await self._process_missed_fill(
        order_id=order_id,
        side=fill_data["side"],
        fill_price=fill_data["fill_price"],
        fill_size=fill_data["fill_size"]
    )
```

---

## Configuration

Add to `config.yaml`:

```yaml
monitoring:
  fill_monitor:
    enabled: true
    check_interval: 30        # Check every 30 seconds
    verification_delay: 30    # Wait 30s before first check
    max_age: 86400           # Remove orders older than 24 hours
```

---

## Usage Example

```python
# Initialize
fill_monitor = FillMonitor(
    api_client=api_client,
    event_store=event_store,
    product_id=27,
    missed_fill_callback=handle_missed_fill
)

# Start monitoring
await fill_monitor.start()

# Track an order after placement
fill_monitor.track_order(
    order_id="1044622629",
    side="buy",
    price=91000.0,
    size=1
)

# Mark as filled when WebSocket notification arrives
fill_monitor.mark_filled("1044622629", source="websocket")

# Get metrics
metrics = fill_monitor.get_metrics()
print(f"Fills detected: {metrics['fills_detected']}")
print(f"Pending orders: {metrics['pending_orders']}")

# Get health status
health = fill_monitor.get_health_status()
print(f"Monitor health: {health['health']}")
print(f"Uptime: {health['uptime']:.1f}s")

# Stop monitoring
await fill_monitor.stop()
```

---

## How It Works

### Order Lifecycle Tracking

```
1. Order Placed
   ↓
   fill_monitor.track_order(order_id, ...)
   ↓
2. Wait verification_delay (30s)
   ↓
3. Query Exchange
   ↓
   ┌─────────────────────────────────┐
   │ State Check                     │
   ├─────────────────────────────────┤
   │ "filled" or "closed" (unfilled=0)│ → Missed Fill! → Callback
   │ "cancelled" / "rejected"        │ → Mark cancelled
   │ "open"                          │ → Continue tracking
   │ Unknown                         │ → Log warning
   └─────────────────────────────────┘
   ↓
4. Repeat check every check_interval (30s)
   ↓
5. Cleanup after 24 hours or when filled/cancelled
```

### Missed Fill Detection

When a fill is detected:
1. Check if already processed (deduplication)
2. Calculate detection delay
3. Log warning with details
4. Mark as filled in tracking
5. Call missed_fill_callback with fill data
6. Bot processes through existing saga logic

---

## Metrics

### Available Metrics

- `tracked_orders`: Total orders currently tracked
- `verified_orders`: Orders marked as verified (deduplication)
- `fills_detected`: Total missed fills detected
- `verifications_performed`: Total verification checks
- `api_calls`: Total API calls made
- `pending_orders`: Orders still pending
- `filled_orders`: Orders filled
- `cancelled_orders`: Orders cancelled

### Health Status

- `running`: Is monitor active
- `uptime`: Time since start
- `loop_count`: Number of execution loops
- `error_count`: Number of errors
- `last_execution`: Timestamp of last execution
- `time_since_last`: Seconds since last execution
- `health`: "healthy" or "unhealthy"

---

## Error Handling

### Graceful Degradation

If monitor encounters errors:
1. Error logged with details
2. Error counter incremented
3. 5-second backoff before retry
4. Monitor continues running
5. Bot continues normal operation

### Monitor Failure

If monitor crashes:
- Bot continues working normally
- Falls back to existing reconciliation (5 minutes)
- No impact on trading logic
- Can be restarted independently

---

## Testing

### Unit Tests

```python
# Test order tracking
monitor.track_order("123", "buy", 100.0, 1)
assert "123" in monitor._tracked_orders

# Test fill marking
monitor.mark_filled("123", "websocket")
assert monitor._tracked_orders["123"]["status"] == "filled"

# Test cleanup
# (add old orders and verify cleanup)
```

### Integration Tests

```python
# Test with mock API
mock_api = MockDeltaClient()
monitor = FillMonitor(mock_api, event_store, 27)

# Simulate missed fill
mock_api.set_order_state("123", "filled")
await monitor._verify_order("123")

# Verify callback was called
assert callback_called
```

---

## Troubleshooting

### Monitor Not Detecting Fills

**Check:**
1. Is monitor running? `health['running']`
2. Is order tracked? Check `tracked_orders`
3. Has verification_delay passed? (30s)
4. Check API connectivity
5. Check logs for errors

### False Positives

**Check:**
1. Is WebSocket marking fills? (should prevent detection)
2. Is deduplication working? Check `verified_orders`
3. Check order state interpretation logic

### High API Usage

**Adjust:**
1. Increase `check_interval` (30s → 60s)
2. Increase `verification_delay` (30s → 60s)
3. Reduce `max_age` (cleanup sooner)

---

## Future Enhancements

### Phase 2 (Planned)
- Dual-channel monitoring (WebSocket + REST simultaneously)
- Order state machine with timeout handling
- Predictive fill detection

### Phase 3 (Planned)
- State comparator (bot vs exchange)
- Continuous reconciliation
- Advanced metrics and alerting

---

## Support

For issues or questions:
1. Check logs: `[FillMonitor]` prefix
2. Check health status: `fill_monitor.get_health_status()`
3. Check metrics: `fill_monitor.get_metrics()`
4. Review this documentation
5. Check `monitoring_update.md` for implementation plan
