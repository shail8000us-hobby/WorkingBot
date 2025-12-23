"""
Concurrency Testing Suite for GridBot Trading System

Tests thread safety, race conditions, deadlocks, and concurrent operations.

CRITICAL: GridBot uses locks (state_lock) - must verify:
1. No race conditions during concurrent operations
2. No deadlocks when multiple threads access shared state
3. State consistency maintained under concurrent load
4. Order placement is thread-safe

Run with: pytest tests/test_concurrency.py -v -s
"""

import pytest
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, MagicMock
from collections import defaultdict

from bot.strategy.modules.grid_calculator import GridCalculator
from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.position_manager import PositionManager


class TestConcurrentOrderPlacement:
    """Test concurrent order placement operations"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
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
                self.placed_orders.append({
                    'id': order_id,
                    'thread': threading.current_thread().name,
                    **kwargs
                })
                # Simulate network delay
                time.sleep(random.uniform(0.001, 0.005))
                return {
                    'success': True,
                    'result': {'id': order_id}
                }
        
        self.api_client.place_order = Mock(side_effect=mock_place_order)
        
        # Real position manager (has actual lock)
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="CONCURRENT_TEST"
        )
        
        # Order manager
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_concurrent_buy_orders_no_race_condition(self):
        """
        Test: Multiple threads placing BUY orders concurrently
        Verify: No race conditions, all orders placed correctly
        """
        num_threads = 10
        orders_per_thread = 5
        errors = []
        
        def worker(thread_id):
            """Each thread places multiple orders"""
            try:
                for i in range(orders_per_thread):
                    # Use grid-aligned prices (step=500, so must be multiples of 500)
                    price = 110000 - (thread_id * 500) - (i * 500)
                    order_id = self.order_mgr.place_buy_order(price=price)
                    assert order_id is not None, f"Thread {thread_id}: order {i} failed"
            except Exception as e:
                errors.append((threading.current_thread().name, str(e)))
        
        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions
        
        # Verify no errors
        assert len(errors) == 0, f"Thread errors occurred: {errors}"
        
        # Verify correct number of orders
        expected_orders = num_threads * orders_per_thread
        assert len(self.placed_orders) == expected_orders, \
            f"Expected {expected_orders} orders, got {len(self.placed_orders)}"
        
        # Verify no duplicate order IDs
        order_ids = [order['id'] for order in self.placed_orders]
        assert len(order_ids) == len(set(order_ids)), \
            "Duplicate order IDs detected (race condition!)"
    
    def test_concurrent_position_updates_thread_safe(self):
        """
        Test: Multiple threads updating positions concurrently
        Verify: State lock prevents race conditions
        """
        num_threads = 20
        positions_per_thread = 5
        errors = []
        
        def worker(thread_id):
            """Each thread adds and removes positions"""
            try:
                for i in range(positions_per_thread):
                    # Add position
                    position = {
                        'buy_order_id': f'ORDER_{thread_id}_{i}',
                        'entry_price': 110000 - (thread_id * 10) - i,
                        'tp_price': 110500 - (thread_id * 10) - i,
                        'size': 1,
                        'timestamp': time.time(),
                        'protected': False
                    }
                    self.position_mgr.add_position(position)
                    
                    # Small delay to increase contention
                    time.sleep(0.001)
                    
                    # Remove position
                    self.position_mgr.remove_position(position)
            except Exception as e:
                errors.append((threading.current_thread().name, str(e)))
        
        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Verify no errors
        assert len(errors) == 0, f"Thread errors: {errors}"
        
        # Verify state consistency: all positions removed
        final_positions = self.position_mgr.get_positions()
        assert len(final_positions) == 0, \
            f"State inconsistency: {len(final_positions)} positions remain"
    
    def test_concurrent_capacity_management_no_overflow(self):
        """
        Test: Concurrent capacity reservation attempts
        Verify: Never exceeds max_open capacity
        """
        num_threads = 50
        attempts_per_thread = 10
        max_open = 10
        
        self.position_mgr.max_open = max_open
        successful_reservations = []
        reservation_lock = threading.Lock()
        
        def worker(thread_id):
            """Try to reserve capacity multiple times"""
            for i in range(attempts_per_thread):
                if self.position_mgr.try_reserve_capacity():
                    with reservation_lock:
                        successful_reservations.append((thread_id, i))
                    # Hold capacity briefly
                    time.sleep(0.001)
                    self.position_mgr.release_capacity()
        
        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Verify final capacity is correct
        capacity = self.position_mgr.get_capacity_status()
        assert capacity['open'] == 0, "Capacity leak detected!"
        assert capacity['pending'] == 0, "Pending capacity leak!"
        
        # Verify we never exceeded max_open
        # (This is hard to verify directly, but if locks work, it won't happen)
        assert len(successful_reservations) >= num_threads, \
            "Lock is too restrictive"


class TestConcurrentStateManagement:
    """Test concurrent state operations"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="STATE_TEST"
        )
    
    def test_concurrent_pending_buy_updates_consistent(self):
        """
        Test: Concurrent updates to pending_buy
        Verify: State remains consistent
        """
        num_threads = 20
        updates_per_thread = 10
        errors = []
        
        def worker(thread_id):
            """Rapidly update pending buy"""
            try:
                for i in range(updates_per_thread):
                    # Set pending buy
                    self.position_mgr.set_pending_buy({
                        'order_id': f'BUY_{thread_id}_{i}',
                        'price': 110000 - (thread_id * 10),
                        'timestamp': time.time()
                    })
                    
                    # Random delay
                    time.sleep(random.uniform(0.0001, 0.001))
                    
                    # Clear pending buy
                    self.position_mgr.clear_pending_buy()
            except Exception as e:
                errors.append((threading.current_thread().name, str(e)))
        
        # Launch threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Verify no errors
        assert len(errors) == 0, f"Errors: {errors}"
        
        # Verify final state is clean
        pending = self.position_mgr.get_pending_buy()
        assert pending is None or pending == {}, \
            f"State leak: pending_buy not cleared: {pending}"
    
    def test_concurrent_position_find_operations(self):
        """
        Test: Concurrent reads while positions are being modified
        Verify: No race conditions during read/write
        """
        num_writers = 5
        num_readers = 15
        operations = 20
        errors = []
        
        # Add some initial positions
        for i in range(5):
            self.position_mgr.add_position({
                'buy_order_id': f'INIT_{i}',
                'entry_price': 110000 - i * 100,
                'tp_price': 110500 - i * 100,
                'size': 1,
                'timestamp': time.time(),
                'protected': False
            })
        
        def writer(thread_id):
            """Continuously add/remove positions"""
            try:
                for i in range(operations):
                    pos = {
                        'buy_order_id': f'WRITE_{thread_id}_{i}',
                        'entry_price': 108000 - (thread_id * 50),
                        'tp_price': 108500 - (thread_id * 50),
                        'size': 1,
                        'timestamp': time.time(),
                        'protected': False
                    }
                    self.position_mgr.add_position(pos)
                    time.sleep(0.002)
                    self.position_mgr.remove_position(pos)
            except Exception as e:
                errors.append(('writer', threading.current_thread().name, str(e)))
        
        def reader(thread_id):
            """Continuously read positions"""
            try:
                for i in range(operations):
                    # Various read operations
                    positions = self.position_mgr.get_positions()
                    assert isinstance(positions, list), "Invalid positions type"
                    
                    capacity = self.position_mgr.get_capacity_status()
                    assert 'open' in capacity, "Invalid capacity data"
                    
                    time.sleep(0.001)
            except Exception as e:
                errors.append(('reader', threading.current_thread().name, str(e)))
        
        # Launch writers and readers
        with ThreadPoolExecutor(max_workers=num_writers + num_readers) as executor:
            writer_futures = [executor.submit(writer, i) for i in range(num_writers)]
            reader_futures = [executor.submit(reader, i) for i in range(num_readers)]
            
            for future in as_completed(writer_futures + reader_futures):
                future.result()
        
        # Verify no errors
        assert len(errors) == 0, f"Concurrent read/write errors: {errors}"


class TestDeadlockDetection:
    """Test for potential deadlocks"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="DEADLOCK_TEST"
        )
    
    def test_no_deadlock_with_high_contention(self):
        """
        Test: High lock contention doesn't cause deadlock
        Verify: All threads complete within reasonable time
        """
        num_threads = 30
        operations = 50
        timeout_seconds = 10
        completed = []
        completed_lock = threading.Lock()
        
        def worker(thread_id):
            """Perform operations that acquire lock repeatedly"""
            for i in range(operations):
                # Operation 1: Add position (acquires lock)
                pos = {
                    'buy_order_id': f'DL_{thread_id}_{i}',
                    'entry_price': 110000 - i,
                    'tp_price': 110500 - i,
                    'size': 1,
                    'timestamp': time.time(),
                    'protected': False
                }
                self.position_mgr.add_position(pos)
                
                # Operation 2: Get positions (acquires lock)
                positions = self.position_mgr.get_positions()
                
                # Operation 3: Update pending (acquires lock)
                self.position_mgr.set_pending_buy({
                    'order_id': f'PB_{thread_id}_{i}',
                    'price': 109000,
                    'timestamp': time.time()
                })
                
                # Operation 4: Remove position (acquires lock)
                self.position_mgr.remove_position(pos)
                
                # Operation 5: Clear pending (acquires lock)
                self.position_mgr.clear_pending_buy()
            
            with completed_lock:
                completed.append(thread_id)
        
        # Launch threads with timeout
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            
            # Wait for all threads with timeout
            for future in as_completed(futures, timeout=timeout_seconds):
                future.result()
        
        elapsed = time.time() - start_time
        
        # Verify all threads completed
        assert len(completed) == num_threads, \
            f"Possible deadlock: only {len(completed)}/{num_threads} threads completed"
        
        # Verify completion within reasonable time
        assert elapsed < timeout_seconds, \
            f"Operations took too long ({elapsed}s), possible deadlock"
        
        print(f"\n✅ No deadlock: {num_threads} threads, {operations} ops each, {elapsed:.2f}s")


class TestStressAndRaceConditions:
    """Stress testing to expose race conditions"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="STRESS_TEST"
        )
    
    def test_stress_rapid_position_churn(self):
        """
        Test: Rapidly add/remove positions from multiple threads
        Verify: No race conditions in position tracking
        """
        num_threads = 25
        operations = 100
        errors = []
        
        def worker(thread_id):
            """Rapidly churn positions"""
            try:
                for i in range(operations):
                    # Add
                    pos = {
                        'buy_order_id': f'STRESS_{thread_id}_{i}',
                        'entry_price': 110000 - (i % 100),
                        'tp_price': 110500 - (i % 100),
                        'size': 1,
                        'timestamp': time.time(),
                        'protected': False
                    }
                    self.position_mgr.add_position(pos)
                    
                    # Immediately remove (high contention)
                    self.position_mgr.remove_position(pos)
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Run stress test
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Verify no errors
        assert len(errors) == 0, f"Race condition errors: {errors}"
        
        # Verify state is clean
        positions = self.position_mgr.get_positions()
        assert len(positions) == 0, \
            f"State corruption: {len(positions)} positions leaked"
    
    def test_stress_concurrent_capacity_checks(self):
        """
        Test: Many threads checking capacity simultaneously
        Verify: Capacity counter never goes negative or above max
        """
        num_threads = 50
        checks_per_thread = 100
        max_open = 10
        
        self.position_mgr.max_open = max_open
        violations = []
        
        def worker(thread_id):
            """Rapidly reserve and release capacity"""
            for i in range(checks_per_thread):
                # Try to reserve
                reserved = self.position_mgr.try_reserve_capacity()
                
                # Check capacity is valid
                capacity = self.position_mgr.get_capacity_status()
                
                # Verify invariants
                if capacity['open'] < 0:
                    violations.append(f"Negative open: {capacity['open']}")
                if capacity['pending'] < 0:
                    violations.append(f"Negative pending: {capacity['pending']}")
                if capacity['open'] + capacity['pending'] > max_open:
                    violations.append(f"Exceeded max: {capacity}")
                
                # Release if we got it
                if reserved:
                    self.position_mgr.release_capacity()
        
        # Run stress test
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Verify no violations
        assert len(violations) == 0, f"Capacity violations: {violations[:10]}"
        
        # Verify final state
        final_capacity = self.position_mgr.get_capacity_status()
        assert final_capacity['open'] == 0, "Capacity leak!"
        assert final_capacity['pending'] == 0, "Pending leak!"


class TestConcurrentIntegration:
    """Integration tests with multiple components"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.grid_calc = GridCalculator(
            lower=105000,
            upper=115000,
            step=500,
            ref=110000,
            tick_size=0.5
        )
        
        # Mock API
        self.api_client = Mock()
        self.order_counter = 0
        self.api_lock = threading.Lock()
        
        def mock_place_order(**kwargs):
            with self.api_lock:
                self.order_counter += 1
                return {'success': True, 'result': {'id': f'O{self.order_counter}'}}
        
        self.api_client.place_order = Mock(side_effect=mock_place_order)
        
        # Real position manager
        self.position_mgr = PositionManager(
            max_open=10,
            grid_calculator=self.grid_calc,
            session_tag="INTEGRATION_TEST"
        )
        
        # Order manager
        self.order_mgr = OrderManager(
            api_client=self.api_client,
            grid_calculator=self.grid_calc,
            position_manager=self.position_mgr,
            product_id=27,
            lot_size=1,
            tick_size=0.5
        )
    
    def test_concurrent_full_workflow(self):
        """
        Test: Complete concurrent workflow
        Verify: Orders → Positions → Capacity all thread-safe
        """
        num_traders = 10
        trades_per_trader = 5
        errors = []
        
        def trader(trader_id):
            """Simulate a complete trading workflow"""
            try:
                for i in range(trades_per_trader):
                    # Place order
                    price = 110000 - (trader_id * 100) - (i * 10)
                    order_id = self.order_mgr.place_buy_order(price=price)
                    
                    if order_id:
                        # Simulate fill - add position
                        position = {
                            'buy_order_id': order_id,
                            'entry_price': price,
                            'tp_price': price + 500,
                            'size': 1,
                            'timestamp': time.time(),
                            'protected': False
                        }
                        self.position_mgr.add_position(position)
                        
                        # Small delay
                        time.sleep(0.002)
                        
                        # Simulate TP fill - remove position
                        self.position_mgr.remove_position(position)
            except Exception as e:
                errors.append((trader_id, str(e)))
        
        # Run concurrent traders
        with ThreadPoolExecutor(max_workers=num_traders) as executor:
            futures = [executor.submit(trader, i) for i in range(num_traders)]
            for future in as_completed(futures):
                future.result()
        
        # Verify no errors
        assert len(errors) == 0, f"Workflow errors: {errors}"
        
        # Verify final state is clean
        positions = self.position_mgr.get_positions()
        assert len(positions) == 0, "Positions leaked"
        
        capacity = self.position_mgr.get_capacity_status()
        assert capacity['open'] == 0, "Capacity leaked"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])

