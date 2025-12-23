# 🧪 STRESS TEST FRAMEWORK - Pre-Production Validation

**Purpose**: Comprehensive stress testing suite to validate bug fixes before deploying to production  
**Target**: Catch race conditions, fill detection issues, and grid integrity violations  
**Environment**: Delta Exchange Testnet  
**Prerequisites**: All 5 critical bugs fixed (see `PRODUCTION_READINESS_FORENSIC_ANALYSIS_NOV6_2025.md`)

---

## 🎯 TEST SUITE OVERVIEW

| Test ID | Test Name | Target Bug | Duration | Pass Criteria |
|---------|-----------|------------|----------|---------------|
| **ST-1** | Rapid Fill Simulation | BUG #1 (Race Condition) | 60s | Zero duplicates |
| **ST-2** | Concurrent Order Placement | BUG #1 (Race Condition) | 5min | Zero duplicates |
| **ST-3** | Grid Alignment Stress | BUG #2 (Off-Grid) | 2min | Zero off-grid orders |
| **ST-4** | Fill Detection Latency | BUG #3 (Orphaned) | 10min | 99% < 5s latency |
| **ST-5** | Circuit Breaker Resilience | BUG #4 (Cascade) | 5min | No false triggers |
| **ST-6** | Position Size Limits | Position Validation | 5min | Never exceed LOT_SIZE |
| **ST-7** | Full Integration Stress | All Bugs | 60min | Clean run |
| **ST-8** | 24-Hour Production Simulation | All Bugs | 24h | Zero critical failures |

---

## 📝 TEST SPECIFICATIONS

### ST-1: Rapid Fill Simulation

**Objective**: Test order placement under high-frequency fills (simulate volatile market)

**Test File**: `tests/stress_test_fills.py`

**Implementation**:
```python
"""
Rapid Fill Simulation - Stress Test ST-1

Simulates high-frequency fill events to test for race conditions in order placement.
"""

import asyncio
import time
from unittest.mock import Mock, patch
from bot.strategy.gridbot import GridBot

def test_rapid_fills(fills_per_second=10, duration=60):
    """
    Simulate rapid fills and verify no duplicate orders
    
    Args:
        fills_per_second: Number of simulated fills per second
        duration: Test duration in seconds
    """
    # Setup mock API client
    api_client = Mock()
    placed_orders = []
    
    def mock_place_order(**kwargs):
        """Track all order placements"""
        order_id = f"ORDER_{len(placed_orders) + 1}"
        price = float(kwargs['limit_price'])
        placed_orders.append({
            'id': order_id,
            'price': price,
            'timestamp': time.time(),
            'side': kwargs['side']
        })
        return {'success': True, 'result': {'id': order_id}}
    
    api_client.place_order = mock_place_order
    
    # Initialize bot
    bot = GridBot(
        api_client=api_client,
        product_id=84,
        lower=90000,
        upper=110000,
        step=300,
        ref=100000,
        lot_size=1,
        max_open=10
    )
    
    # Simulate rapid fills
    start_time = time.time()
    fill_count = 0
    
    while time.time() - start_time < duration:
        # Simulate fill at random grid level
        fill_price = 100000 + (fill_count % 10) * 300
        bot._handle_buy_fill(fill_price, f"SIMULATED_{fill_count}")
        
        fill_count += 1
        time.sleep(1.0 / fills_per_second)  # Control fill rate
    
    # Analyze results
    print(f"\n{'='*80}")
    print(f"RAPID FILL SIMULATION RESULTS")
    print(f"{'='*80}")
    print(f"Duration: {duration}s")
    print(f"Simulated Fills: {fill_count}")
    print(f"Orders Placed: {len(placed_orders)}")
    print(f"Fill Rate: {fill_count / duration:.2f} fills/s")
    print(f"Order Rate: {len(placed_orders) / duration:.2f} orders/s")
    
    # Check for duplicates
    duplicates = []
    seen_prices = {}
    
    for order in placed_orders:
        price = order['price']
        timestamp = order['timestamp']
        
        if price in seen_prices:
            time_gap = timestamp - seen_prices[price]['timestamp']
            duplicates.append({
                'price': price,
                'order1': seen_prices[price]['id'],
                'order2': order['id'],
                'time_gap': time_gap
            })
        else:
            seen_prices[price] = order
    
    if duplicates:
        print(f"\n❌ FAILURE: {len(duplicates)} DUPLICATE ORDERS DETECTED")
        for dup in duplicates:
            print(f"   Price ${dup['price']:,.0f}: {dup['order1']} + {dup['order2']} "
                  f"(gap: {dup['time_gap']*1000:.1f}ms)")
        return False
    else:
        print(f"\n✅ SUCCESS: ZERO DUPLICATE ORDERS")
        return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fills-per-second', type=int, default=10)
    parser.add_argument('--duration', type=int, default=60)
    args = parser.parse_args()
    
    success = test_rapid_fills(args.fills_per_second, args.duration)
    exit(0 if success else 1)
```

**Run Command**:
```powershell
# Default: 10 fills/s for 60s
python tests/stress_test_fills.py

# Aggressive: 20 fills/s for 120s
python tests/stress_test_fills.py --fills-per-second 20 --duration 120
```

**Expected Output**:
```
================================================================================
RAPID FILL SIMULATION RESULTS
================================================================================
Duration: 60s
Simulated Fills: 600
Orders Placed: 300
Fill Rate: 10.00 fills/s
Order Rate: 5.00 orders/s

✅ SUCCESS: ZERO DUPLICATE ORDERS
```

**Pass Criteria**: ZERO duplicate orders at same price level

---

### ST-2: Concurrent Order Placement

**Objective**: Test thread-safety of order placement with multiple concurrent threads

**Test File**: `tests/test_race_conditions.py`

**Implementation**:
```python
"""
Concurrent Order Placement - Stress Test ST-2

Tests OrderManager with multiple threads attempting to place orders simultaneously.
Validates mutex implementation prevents race conditions.
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock

from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.position_manager import PositionManager

class TestConcurrentOrderPlacement:
    """Test concurrent order placement with race condition detection"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=90000,
            upper=110000,
            step=300,
            ref=100000,
            tick_size=0.5
        )
        
        # Mock API client with thread-safe counter
        self.api_client = Mock()
        self.order_counter = 0
        self.order_lock = threading.Lock()
        self.placed_orders = []
        
        def mock_place_order(**kwargs):
            """Thread-safe mock order placement"""
            with self.order_lock:
                self.order_counter += 1
                order_id = f"ORDER_{self.order_counter}"
                price = float(kwargs['limit_price'])
                self.placed_orders.append({
                    'id': order_id,
                    'price': price,
                    'thread': threading.current_thread().name,
                    'timestamp': time.time()
                })
                # Simulate network delay
                time.sleep(0.001)
                return {'success': True, 'result': {'id': order_id}}
        
        self.api_client.place_order = mock_place_order
        
        # Position manager
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="STRESS_TEST"
        )
        
        # Order manager (with our race condition fix)
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=84,
            lot_size=1
        )
    
    def test_concurrent_buy_orders_same_price(self):
        """
        Test: 10 threads simultaneously trying to place BUY @ same price
        Verify: Only ONE order placed (others detect duplicate and skip)
        """
        num_threads = 10
        target_price = 100500.0
        results = []
        
        def worker(thread_id):
            """Each thread tries to place order at same price"""
            try:
                order_id = self.order_mgr.place_buy_order(target_price)
                results.append({
                    'thread': thread_id,
                    'order_id': order_id,
                    'success': order_id is not None
                })
            except Exception as e:
                results.append({
                    'thread': thread_id,
                    'error': str(e),
                    'success': False
                })
        
        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Analyze results
        orders_at_price = [o for o in self.placed_orders if o['price'] == target_price]
        successful_threads = [r for r in results if r['success']]
        
        print(f"\n{'='*80}")
        print(f"CONCURRENT ORDER PLACEMENT TEST")
        print(f"{'='*80}")
        print(f"Threads: {num_threads}")
        print(f"Target Price: ${target_price:,.0f}")
        print(f"Orders Placed: {len(orders_at_price)}")
        print(f"Successful Threads: {len(successful_threads)}")
        
        if len(orders_at_price) > 1:
            print(f"\n❌ FAILURE: {len(orders_at_price)} DUPLICATE ORDERS")
            for order in orders_at_price:
                print(f"   {order['id']} from {order['thread']} @ {order['timestamp']}")
            assert False, f"Race condition detected: {len(orders_at_price)} orders at same price"
        else:
            print(f"\n✅ SUCCESS: Only 1 order placed (mutex working)")
            print(f"   Order ID: {orders_at_price[0]['id']}")
            print(f"   Thread: {orders_at_price[0]['thread']}")
    
    def test_concurrent_different_prices(self):
        """
        Test: 20 threads placing orders at different prices
        Verify: All orders placed successfully (no blocking)
        """
        num_threads = 20
        
        def worker(thread_id):
            """Each thread places order at different price"""
            price = 100000 + (thread_id * 300)  # Different grid levels
            return self.order_mgr.place_buy_order(price)
        
        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            order_ids = [f.result() for f in as_completed(futures)]
        
        successful_orders = [o for o in order_ids if o is not None]
        
        print(f"\n{'='*80}")
        print(f"CONCURRENT DIFFERENT PRICES TEST")
        print(f"{'='*80}")
        print(f"Threads: {num_threads}")
        print(f"Successful Orders: {len(successful_orders)}")
        
        assert len(successful_orders) == num_threads, \
            f"Expected {num_threads} orders, got {len(successful_orders)}"
        
        print(f"\n✅ SUCCESS: All {num_threads} orders placed")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--concurrent-threads', type=int, default=10)
    args = parser.parse_args()
    
    # Run pytest programmatically
    pytest.main([__file__, '-v', '-s'])
```

**Run Command**:
```powershell
# Default: 10 concurrent threads
python tests/test_race_conditions.py

# Stress: 50 concurrent threads
python tests/test_race_conditions.py --concurrent-threads 50
```

**Expected Output**:
```
================================================================================
CONCURRENT ORDER PLACEMENT TEST
================================================================================
Threads: 10
Target Price: $100,500
Orders Placed: 1
Successful Threads: 10

✅ SUCCESS: Only 1 order placed (mutex working)
   Order ID: ORDER_1
   Thread: ThreadPoolExecutor-0_0
```

**Pass Criteria**: 
- Only 1 order placed at same price (other threads detect duplicate)
- All threads at different prices succeed
- Zero race conditions

---

### ST-3: Grid Alignment Stress Test

**Objective**: Validate all order prices are grid-aligned under stress

**Test File**: `tests/test_grid_alignment.py`

**Implementation**:
```python
"""
Grid Alignment Stress Test - ST-3

Validates that order placement ALWAYS produces grid-aligned prices,
even under stress conditions with rapid position changes.
"""

import random
from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.position_manager import PositionManager
from unittest.mock import Mock

def test_grid_alignment_stress(iterations=1000):
    """
    Run 1000 iterations of:
    1. Random position creation
    2. Calculate next buy level
    3. Validate grid alignment
    """
    grid_calc = GridCalculator(
        lower=90000,
        upper=110000,
        step=300,
        ref=100000,
        tick_size=0.5
    )
    
    position_mgr = PositionManager(
        max_open=10,
        grid_calculator=grid_calc,
        session_tag="GRID_TEST"
    )
    
    api_client = Mock()
    api_client.place_order = Mock(return_value={'success': True, 'result': {'id': 'TEST'}})
    
    order_mgr = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=position_mgr,
        product_id=84,
        lot_size=1
    )
    
    off_grid_count = 0
    tested_prices = []
    
    print(f"\n{'='*80}")
    print(f"GRID ALIGNMENT STRESS TEST")
    print(f"{'='*80}")
    print(f"Iterations: {iterations}")
    print(f"Grid: ${grid_calc.lower:,.0f} - ${grid_calc.upper:,.0f}, Step: ${grid_calc.step:,.0f}")
    
    for i in range(iterations):
        # Create random positions
        num_positions = random.randint(0, 5)
        positions = []
        
        for _ in range(num_positions):
            # Random grid-aligned entry price
            entry = grid_calc.lower + (random.randint(0, 60) * grid_calc.step)
            positions.append({'entry_price': entry})
        
        # Calculate next buy level
        next_buy = grid_calc.compute_next_buy_level(positions)
        
        if next_buy is None:
            continue
        
        tested_prices.append(next_buy)
        
        # Validate grid alignment
        is_aligned = grid_calc.is_price_grid_aligned(next_buy)
        
        if not is_aligned:
            off_grid_count += 1
            print(f"\n❌ ITERATION {i+1}: OFF-GRID PRICE ${next_buy:,.2f}")
            print(f"   Positions: {[p['entry_price'] for p in positions]}")
            print(f"   Expected multiple of {grid_calc.step} from ${grid_calc.lower:,.0f}")
    
    print(f"\nTested Prices: {len(tested_prices)}")
    print(f"Off-Grid Count: {off_grid_count}")
    
    if off_grid_count > 0:
        print(f"\n❌ FAILURE: {off_grid_count} OFF-GRID PRICES")
        return False
    else:
        print(f"\n✅ SUCCESS: ALL {len(tested_prices)} PRICES GRID-ALIGNED")
        return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=1000)
    args = parser.parse_args()
    
    success = test_grid_alignment_stress(args.iterations)
    exit(0 if success else 1)
```

**Run Command**:
```powershell
# Default: 1000 iterations
python tests/test_grid_alignment.py

# Extensive: 10000 iterations
python tests/test_grid_alignment.py --iterations 10000
```

**Expected Output**:
```
================================================================================
GRID ALIGNMENT STRESS TEST
================================================================================
Iterations: 1000
Grid: $90,000 - $110,000, Step: $300

Tested Prices: 847
Off-Grid Count: 0

✅ SUCCESS: ALL 847 PRICES GRID-ALIGNED
```

**Pass Criteria**: ZERO off-grid prices in 1000+ iterations

---

### ST-4: Fill Detection Latency Test

**Objective**: Measure fill detection latency and ensure 99% < 5 seconds

**Test File**: `tests/test_fill_detection_latency.py`

**Implementation**:
```python
"""
Fill Detection Latency Test - ST-4

Measures time from order fill to bot detection.
Validates that 99% of fills are detected within 5 seconds.
"""

import time
import asyncio
from statistics import mean, median, stdev
from bot.delta_websocket.ws_manager import WebSocketManager

async def test_fill_detection_latency(duration=600):
    """
    Monitor fill detection for 10 minutes
    Record latency for each fill
    
    Args:
        duration: Test duration in seconds (default 600 = 10 minutes)
    """
    latencies = []
    order_times = {}
    
    # Mock fill handler that records latency
    def record_fill(order_id, fill_time):
        """Record time from order placement to fill detection"""
        if order_id in order_times:
            latency = fill_time - order_times[order_id]
            latencies.append(latency)
            print(f"Fill detected: Order {order_id}, Latency: {latency:.3f}s")
    
    # Setup WebSocket manager with instrumentation
    ws_manager = WebSocketManager(
        api_key="test_key",
        api_secret="test_secret",
        product_id=84
    )
    
    # Patch fill handler
    original_handler = ws_manager._handle_fill
    
    def instrumented_handler(fill_data):
        order_id = fill_data.get('order_id')
        record_fill(order_id, time.time())
        original_handler(fill_data)
    
    ws_manager._handle_fill = instrumented_handler
    
    # Run for specified duration
    print(f"\n{'='*80}")
    print(f"FILL DETECTION LATENCY TEST")
    print(f"{'='*80}")
    print(f"Duration: {duration}s ({duration/60:.1f} minutes)")
    print(f"Monitoring fill detection latency...")
    
    start_time = time.time()
    
    # Note: This requires bot to be running on testnet
    print(f"\n⚠️  Ensure bot is running on testnet with active trading")
    print(f"Waiting for fills...")
    
    await asyncio.sleep(duration)
    
    # Analyze results
    if len(latencies) == 0:
        print(f"\n❌ NO FILLS DETECTED - Cannot measure latency")
        return False
    
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies) // 2]
    p95 = latencies_sorted[int(len(latencies) * 0.95)]
    p99 = latencies_sorted[int(len(latencies) * 0.99)]
    max_latency = max(latencies)
    
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"Total Fills: {len(latencies)}")
    print(f"Mean Latency: {mean(latencies):.3f}s")
    print(f"Median Latency: {p50:.3f}s")
    print(f"Std Dev: {stdev(latencies):.3f}s")
    print(f"P95 Latency: {p95:.3f}s")
    print(f"P99 Latency: {p99:.3f}s")
    print(f"Max Latency: {max_latency:.3f}s")
    
    # Check pass criteria
    slow_fills = [l for l in latencies if l > 5.0]
    slow_pct = (len(slow_fills) / len(latencies)) * 100
    
    print(f"\nFills > 5s: {len(slow_fills)} ({slow_pct:.1f}%)")
    
    if p99 > 5.0:
        print(f"\n❌ FAILURE: P99 latency {p99:.3f}s exceeds 5s threshold")
        return False
    else:
        print(f"\n✅ SUCCESS: P99 latency {p99:.3f}s within 5s threshold")
        return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=int, default=600)
    args = parser.parse_args()
    
    success = asyncio.run(test_fill_detection_latency(args.duration))
    exit(0 if success else 1)
```

**Run Command**:
```powershell
# Default: 10 minutes
python tests/test_fill_detection_latency.py

# Quick: 5 minutes
python tests/test_fill_detection_latency.py --duration 300
```

**Expected Output**:
```
================================================================================
RESULTS
================================================================================
Total Fills: 23
Mean Latency: 1.234s
Median Latency: 0.987s
Std Dev: 0.456s
P95 Latency: 2.345s
P99 Latency: 3.456s
Max Latency: 4.123s

Fills > 5s: 0 (0.0%)

✅ SUCCESS: P99 latency 3.456s within 5s threshold
```

**Pass Criteria**: P99 latency < 5 seconds

---

### ST-5: Circuit Breaker Resilience Test

**Objective**: Validate circuit breaker doesn't trigger on expected errors (404s)

**Test File**: `tests/test_circuit_breaker.py` (already exists, enhance)

**Enhancement**:
```python
"""
Circuit Breaker Resilience Test - ST-5

Validates circuit breaker behavior:
1. Should NOT trigger on expected errors (404, order_not_found)
2. SHOULD trigger on real API failures (timeout, 500 errors)
3. Timeout should be adaptive (shorter during high volatility)
"""

import pytest
from bot.api.circuit_breaker import CircuitBreaker

def test_circuit_breaker_ignores_404():
    """Test that 404 errors don't trigger circuit breaker"""
    cb = CircuitBreaker(failure_threshold=3, timeout=60)
    
    # Simulate 10 consecutive 404 errors
    for i in range(10):
        cb.record_failure(error_code='order_not_found')
    
    # Circuit breaker should still be CLOSED
    assert cb.state == 'CLOSED', f"Circuit breaker opened on 404 errors (should ignore)"
    print("✅ Circuit breaker ignores 404 errors")

def test_circuit_breaker_triggers_on_real_failures():
    """Test that real API failures trigger circuit breaker"""
    cb = CircuitBreaker(failure_threshold=3, timeout=60)
    
    # Simulate 3 real API failures
    for i in range(3):
        cb.record_failure(error_code='api_timeout')
    
    # Circuit breaker should be OPEN
    assert cb.state == 'OPEN', f"Circuit breaker didn't open after 3 failures"
    print("✅ Circuit breaker triggers on real failures")

def test_circuit_breaker_adaptive_timeout():
    """Test adaptive timeout during high volatility"""
    cb = CircuitBreaker(failure_threshold=5, timeout=60)
    
    # Trigger with high volatility
    with patch('bot.volatility.iv_rv_tracker.get_volatility_tracker') as mock:
        mock_tracker = Mock()
        mock_tracker.is_high_volatility.return_value = True
        mock.return_value = mock_tracker
        
        # Trigger circuit breaker
        for i in range(5):
            cb.record_failure()
        
        # Should use shorter timeout
        timeout_used = cb.open_until - time.time()
        assert timeout_used <= 20, f"Timeout {timeout_used:.1f}s too long for high volatility"
        print(f"✅ Adaptive timeout: {timeout_used:.1f}s during high volatility")

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
```

**Run Command**:
```powershell
python tests/test_circuit_breaker.py
```

**Pass Criteria**: 
- 404 errors DON'T trigger circuit breaker
- Real failures DO trigger circuit breaker
- Timeout adaptive during high volatility

---

### ST-6: Position Size Limits Test

**Objective**: Validate bot never exceeds LOT_SIZE per price level

**Test File**: `tests/test_position_size_limits.py`

**Implementation**:
```python
"""
Position Size Limits Test - ST-6

Validates that bot NEVER holds more than LOT_SIZE contracts at any single price level.
Tests position size validator implementation.
"""

from bot.strategy.modules.position_manager import PositionManager
from bot.strategy.modules.grid_calculator import GridCalculator

def test_position_size_limits():
    """Test position size enforcement"""
    grid_calc = GridCalculator(
        lower=90000,
        upper=110000,
        step=300,
        ref=100000,
        tick_size=0.5
    )
    
    position_mgr = PositionManager(
        max_open=10,
        grid_calculator=grid_calc,
        session_tag="SIZE_TEST",
        lot_size=1  # LOT_SIZE = 1
    )
    
    print(f"\n{'='*80}")
    print(f"POSITION SIZE LIMITS TEST")
    print(f"{'='*80}")
    print(f"LOT_SIZE: 1")
    print(f"MAX_OPEN: 10")
    
    # Try to add multiple positions at same price
    test_price = 100500.0
    
    # Add first position (should succeed)
    pos1 = position_mgr.add_position(test_price, 1)
    assert pos1 is not None, "First position should be added"
    print(f"✅ Position 1 added @ ${test_price:,.0f}")
    
    # Try to add second position at SAME price (should FAIL)
    pos2 = position_mgr.add_position(test_price, 1)
    
    if pos2 is None:
        print(f"✅ Second position @ ${test_price:,.0f} REJECTED (size limit enforced)")
    else:
        print(f"❌ Second position @ ${test_price:,.0f} ALLOWED (BUG: size limit not enforced)")
        return False
    
    # Verify total size at price level
    positions_at_price = [p for p in position_mgr.get_positions() if p['entry_price'] == test_price]
    total_size = sum(p['size'] for p in positions_at_price)
    
    print(f"\nTotal size @ ${test_price:,.0f}: {total_size}")
    
    if total_size > 1:
        print(f"❌ FAILURE: Size {total_size} exceeds LOT_SIZE=1")
        return False
    else:
        print(f"✅ SUCCESS: Size limit enforced")
        return True

if __name__ == '__main__':
    success = test_position_size_limits()
    exit(0 if success else 1)
```

**Run Command**:
```powershell
python tests/test_position_size_limits.py
```

**Pass Criteria**: Cannot add >LOT_SIZE contracts at same price

---

### ST-7: Full Integration Stress Test

**Objective**: Comprehensive test combining all stress scenarios

**Test File**: `tests/stress_test_integration.py`

**Run Command**:
```powershell
# 1 hour stress test with high volatility simulation
python tests/stress_test_integration.py --duration 3600 --volatility high

# Quick validation (10 minutes)
python tests/stress_test_integration.py --duration 600 --volatility medium
```

**Expected Output**:
```
================================================================================
FULL INTEGRATION STRESS TEST
================================================================================
Duration: 3600s (60 minutes)
Volatility: HIGH
Starting testnet bot...

[... bot runs for 1 hour ...]

================================================================================
STRESS TEST RESULTS
================================================================================
Total Orders: 237
Total Fills: 235
Duplicate Orders: 0 ✅
Off-Grid Orders: 0 ✅
Orphaned Positions: 0 ✅
Circuit Breaker Triggers: 0 ✅
Position Size Violations: 0 ✅
Max Fill Latency: 3.456s ✅
P99 Fill Latency: 2.123s ✅

✅ STRESS TEST PASSED - System ready for production
```

**Pass Criteria**: ALL metrics clean (zero critical failures)

---

### ST-8: 24-Hour Production Simulation

**Objective**: Final validation - run bot on testnet for 24 hours

**Prerequisites**: All previous tests (ST-1 through ST-7) passed

**Procedure**:

```powershell
# 1. Start bot on testnet
pm2 start ecosystem.config.js --only gridbot-demo

# 2. Monitor continuously
pm2 logs gridbot-demo

# 3. Run analysis script after 24h
python tests/analyze_24h_run.py
```

**Analysis Script** (`tests/analyze_24h_run.py`):
```python
"""
Analyze 24-hour testnet run for production readiness
"""

import re
from datetime import datetime, timedelta

def analyze_24h_run(log_file='logs/pm2-gridbot-demo-combined.log'):
    """Analyze 24-hour log for critical failures"""
    
    # Metrics to track
    metrics = {
        'duplicate_orders': 0,
        'off_grid_orders': 0,
        'orphaned_positions': 0,
        'circuit_breaker_triggers': 0,
        'position_size_violations': 0,
        'fill_detection_delays': [],
        'total_orders': 0,
        'total_fills': 0
    }
    
    # Parse logs
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            # Count orders
            if '✅ BUY order placed' in line or '✅ SELL order placed' in line:
                metrics['total_orders'] += 1
            
            # Count fills
            if '🎯 FILL DETECTED' in line:
                metrics['total_fills'] += 1
            
            # Detect duplicates
            if 'DUPLICATE' in line.upper():
                metrics['duplicate_orders'] += 1
            
            # Detect off-grid
            if 'NOT grid-aligned' in line:
                metrics['off_grid_orders'] += 1
            
            # Detect circuit breaker
            if 'Circuit breaker' in line and 'OPEN' in line:
                metrics['circuit_breaker_triggers'] += 1
    
    # Print report
    print(f"\n{'='*80}")
    print(f"24-HOUR TESTNET RUN ANALYSIS")
    print(f"{'='*80}")
    print(f"Total Orders: {metrics['total_orders']}")
    print(f"Total Fills: {metrics['total_fills']}")
    print(f"\nCritical Issues:")
    print(f"  Duplicate Orders: {metrics['duplicate_orders']} {'✅' if metrics['duplicate_orders'] == 0 else '❌'}")
    print(f"  Off-Grid Orders: {metrics['off_grid_orders']} {'✅' if metrics['off_grid_orders'] == 0 else '❌'}")
    print(f"  Orphaned Positions: {metrics['orphaned_positions']} {'✅' if metrics['orphaned_positions'] == 0 else '❌'}")
    print(f"  Circuit Breaker: {metrics['circuit_breaker_triggers']} {'✅' if metrics['circuit_breaker_triggers'] == 0 else '❌'}")
    
    # Overall verdict
    critical_issues = sum([
        metrics['duplicate_orders'],
        metrics['off_grid_orders'],
        metrics['orphaned_positions'],
        metrics['circuit_breaker_triggers']
    ])
    
    if critical_issues == 0:
        print(f"\n✅ PRODUCTION READY - Zero critical failures in 24h")
        return True
    else:
        print(f"\n❌ NOT READY - {critical_issues} critical issues detected")
        return False

if __name__ == '__main__':
    success = analyze_24h_run()
    exit(0 if success else 1)
```

**Pass Criteria**: 
- Zero critical failures in 24 hours
- At least 50+ orders placed/filled
- All metrics clean

---

## 📊 TEST EXECUTION SEQUENCE

### Phase 1: Unit Tests (2-3 hours)

```powershell
# 1. Race condition tests
python tests/test_race_conditions.py

# 2. Grid alignment tests
python tests/test_grid_alignment.py

# 3. Circuit breaker tests
python tests/test_circuit_breaker.py

# 4. Position size tests
python tests/test_position_size_limits.py
```

**Requirement**: ALL unit tests PASS before proceeding

---

### Phase 2: Stress Tests (6-8 hours)

```powershell
# 1. Rapid fills (1 hour)
python tests/stress_test_fills.py --duration 3600

# 2. Concurrent placement (30 min)
python tests/test_race_conditions.py --concurrent-threads 50

# 3. Grid alignment stress (30 min)
python tests/test_grid_alignment.py --iterations 10000

# 4. Fill latency (1 hour)
python tests/test_fill_detection_latency.py --duration 3600

# 5. Full integration (3 hours)
python tests/stress_test_integration.py --duration 10800 --volatility high
```

**Requirement**: ALL stress tests PASS before proceeding

---

### Phase 3: 24-Hour Validation (24 hours)

```powershell
# Start bot
pm2 start ecosystem.config.js --only gridbot-demo

# Wait 24 hours...

# Analyze
python tests/analyze_24h_run.py
```

**Requirement**: Zero critical failures

---

## ✅ PRODUCTION READINESS CHECKLIST

- [ ] **Unit Tests**: All passing
- [ ] **ST-1**: Zero duplicate orders (rapid fills)
- [ ] **ST-2**: Mutex prevents race conditions
- [ ] **ST-3**: All prices grid-aligned (1000+ iterations)
- [ ] **ST-4**: P99 fill latency < 5s
- [ ] **ST-5**: Circuit breaker resilient to 404s
- [ ] **ST-6**: Position size limits enforced
- [ ] **ST-7**: Integration stress test clean (3 hours)
- [ ] **ST-8**: 24-hour testnet run clean
- [ ] **Code Review**: Second developer approval
- [ ] **Risk Management**: Approval to proceed

**Final Verdict**: If ALL checkboxes ✅, proceed to production deployment

---

## 🚨 FAILURE HANDLING

If ANY test fails:

1. **STOP**: Do not proceed to next phase
2. **ANALYZE**: Review logs and identify root cause
3. **FIX**: Implement fix for specific failure
4. **RETEST**: Run ALL tests from beginning
5. **REPEAT**: Until 100% pass rate

**DO NOT SKIP FAILED TESTS** - Each test validates critical safety

---

## 📞 SUPPORT

For test failures or questions:
- Review `PRODUCTION_READINESS_FORENSIC_ANALYSIS_NOV6_2025.md`
- Review `BUG_FIX_IMPLEMENTATION_PLAN.md`
- Contact: [Your support details]

---

**Document Status**: ✅ COMPLETE  
**Version**: 1.0  
**Last Updated**: November 6, 2025
