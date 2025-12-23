"""
Performance Benchmark Tests - System Throughput & Latency Validation

Validates system performance under load:
1. Actor message throughput (target: >1000 msg/s)
2. EventStore write performance (target: >5000 events/s)
3. Memory usage profiling
4. Latency percentiles (p50, p95, p99)
5. Saga execution performance
6. Concurrent operation stress
"""

import asyncio
import pytest
import time
import statistics
import tracemalloc
import uuid
from typing import List, Dict

from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.modules.event_store import EventStore, Event, EventType
from bot.strategy.sagas.saga_coordinator import Saga, SagaStep


def create_test_event(event_type=EventType.POSITION_OPENED, data=None, correlation_id=None):
    """Helper to create test events."""
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=time.time(),
        correlation_id=correlation_id or str(uuid.uuid4()),
        aggregate_id=f"test-{uuid.uuid4()}",
        data=data or {},
        metadata={"test": True, "benchmark": True}
    )


class TestActorPerformance:
    """Benchmark actor message processing throughput and latency."""
    
    @pytest.mark.asyncio
    async def test_actor_throughput_benchmark(self):
        """
        Benchmark: Actor should handle >1000 messages/second
        Test: Send 10,000 GET_STATE messages, measure throughput
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store, max_positions=100)
        
        # Start actor
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)  # Let actor initialize
        
        # Warm-up phase (JIT optimization, cache warming)
        warmup_tasks = [actor.ask("GET_STATE", {}) for _ in range(100)]
        await asyncio.gather(*warmup_tasks)
        
        # Benchmark phase
        print(f"\n{'='*80}")
        print(f"ACTOR THROUGHPUT BENCHMARK")
        print(f"{'='*80}")
        print(f"Starting 10,000 message benchmark...")
        
        start_time = time.perf_counter()
        benchmark_tasks = [actor.ask("GET_STATE", {}) for _ in range(10000)]
        results = await asyncio.gather(*benchmark_tasks)
        elapsed = time.perf_counter() - start_time
        
        # Calculate metrics
        throughput = 10000 / elapsed
        latency_per_msg = (elapsed / 10000) * 1000  # milliseconds
        
        print(f"\nResults:")
        print(f"  Messages processed: 10,000")
        print(f"  Total time: {elapsed:.3f}s")
        print(f"  Throughput: {throughput:.1f} msg/s")
        print(f"  Average latency: {latency_per_msg:.3f}ms per message")
        print(f"  Target: >1000 msg/s")
        print(f"  Status: {'✅ PASS' if throughput > 1000 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        # Cleanup
        await actor.stop()
        await actor_task
        
        # Verify all messages succeeded
        assert len(results) == 10000, "Should process all messages"
        assert all(isinstance(r, dict) for r in results), "All responses should be dicts"
        
        # Performance assertion
        assert throughput > 1000, \
            f"Actor throughput below target: {throughput:.1f} msg/s < 1000 msg/s"
    
    @pytest.mark.asyncio
    async def test_actor_latency_percentiles(self):
        """
        Benchmark: Measure latency distribution (p50, p95, p99)
        Test: Individual message latencies for performance profiling
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store, max_positions=100)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        # Warm-up
        for _ in range(50):
            await actor.ask("GET_STATE", {})
        
        # Measure individual latencies
        latencies = []
        
        for _ in range(1000):
            start = time.perf_counter()
            await actor.ask("GET_STATE", {})
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        # Calculate percentiles
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[len(latencies_sorted) // 2]
        p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
        p_min = min(latencies)
        p_max = max(latencies)
        p_mean = statistics.mean(latencies)
        p_stdev = statistics.stdev(latencies)
        
        print(f"\n{'='*80}")
        print(f"ACTOR LATENCY PERCENTILES")
        print(f"{'='*80}")
        print(f"Messages: 1,000")
        print(f"\nLatency Distribution:")
        print(f"  Minimum:  {p_min:.3f}ms")
        print(f"  p50 (median): {p50:.3f}ms")
        print(f"  Mean:     {p_mean:.3f}ms")
        print(f"  p95:      {p95:.3f}ms")
        print(f"  p99:      {p99:.3f}ms")
        print(f"  Maximum:  {p_max:.3f}ms")
        print(f"  Std Dev:  {p_stdev:.3f}ms")
        print(f"\nTarget: p95 < 10ms")
        print(f"Status: {'✅ PASS' if p95 < 10 else '⚠️ ACCEPTABLE' if p95 < 50 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        await actor.stop()
        await actor_task
        
        # Reasonable latency targets
        assert p95 < 50, f"p95 latency too high: {p95:.3f}ms"
        assert p99 < 100, f"p99 latency too high: {p99:.3f}ms"
    
    @pytest.mark.asyncio
    async def test_actor_concurrent_write_performance(self):
        """
        Benchmark: Actor handling concurrent writes (ADD_POSITION)
        Test: 1000 concurrent position additions
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store, max_positions=5000)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        print(f"\n{'='*80}")
        print(f"ACTOR CONCURRENT WRITE BENCHMARK")
        print(f"{'='*80}")
        print(f"Starting 1,000 concurrent position additions...")
        
        # Create 1000 concurrent ADD_POSITION tasks
        start_time = time.perf_counter()
        
        tasks = []
        for i in range(1000):
            task = actor.ask("ADD_POSITION", {
                "position_id": f"perf-pos-{i}",
                "entry_price": 100000.0 + i,
                "tp_price": 101000.0 + i,
                "size": 1,
                "correlation_id": f"perf-{i}"
            })
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start_time
        
        # Calculate metrics
        throughput = 1000 / elapsed
        
        # Verify state
        state = await actor.ask("GET_STATE", {})
        positions_added = len(state["open_tranches"])
        
        print(f"\nResults:")
        print(f"  Positions added: {positions_added}/1000")
        print(f"  Total time: {elapsed:.3f}s")
        print(f"  Throughput: {throughput:.1f} writes/s")
        print(f"  Average latency: {(elapsed/1000)*1000:.3f}ms per write")
        print(f"  Target: >500 writes/s")
        print(f"  Status: {'✅ PASS' if throughput > 500 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        await actor.stop()
        await actor_task
        
        # Assertions
        assert positions_added == 1000, "All positions should be added"
        assert throughput > 500, f"Write throughput too low: {throughput:.1f} writes/s"


class TestEventStorePerformance:
    """Benchmark EventStore write and query performance."""
    
    def test_event_store_write_throughput(self):
        """
        Benchmark: EventStore should write >5000 events/second
        Test: Write 10,000 events, measure throughput
        """
        event_store = EventStore(":memory:")
        
        # Warm-up phase
        for i in range(100):
            event = create_test_event(
                event_type=EventType.POSITION_OPENED,
                correlation_id=f"warmup-{i}",
                data={"position_id": f"pos-{i}", "price": 100000.0}
            )
            event_store.append_event(event)
        
        print(f"\n{'='*80}")
        print(f"EVENTSTORE WRITE THROUGHPUT BENCHMARK")
        print(f"{'='*80}")
        print(f"Starting 10,000 event write benchmark...")
        
        # Benchmark phase
        start_time = time.perf_counter()
        
        for i in range(10000):
            event = create_test_event(
                event_type=EventType.POSITION_OPENED,
                correlation_id=f"bench-{i}",
                data={
                    "position_id": f"pos-{i}",
                    "price": 100000.0 + i,
                    "size": 1,
                    "sequence": i
                }
            )
            event_store.append_event(event)
        
        elapsed = time.perf_counter() - start_time
        
        # Calculate metrics
        throughput = 10000 / elapsed
        latency_per_write = (elapsed / 10000) * 1000  # milliseconds
        
        print(f"\nResults:")
        print(f"  Events written: 10,000")
        print(f"  Total time: {elapsed:.3f}s")
        print(f"  Throughput: {throughput:.1f} events/s")
        print(f"  Average latency: {latency_per_write:.4f}ms per write")
        print(f"  Target: >5000 events/s")
        print(f"  Status: {'✅ PASS' if throughput > 5000 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        # Verify data integrity
        all_events = event_store.get_all_events()
        assert len(all_events) >= 10000, "All events should be persisted"
        
        # Performance assertion
        assert throughput > 5000, \
            f"EventStore write throughput below target: {throughput:.1f} events/s < 5000 events/s"
    
    def test_event_store_query_performance(self):
        """
        Benchmark: EventStore query performance
        Test: Query 1000 times from 10,000 events
        """
        event_store = EventStore(":memory:")
        
        # Populate with 10,000 events
        for i in range(10000):
            event = create_test_event(
                event_type=EventType.POSITION_OPENED if i % 2 == 0 else EventType.POSITION_CLOSED,
                correlation_id=f"corr-{i % 100}",  # 100 unique correlations
                data={"position_id": f"pos-{i}", "sequence": i}
            )
            event_store.append_event(event)
        
        print(f"\n{'='*80}")
        print(f"EVENTSTORE QUERY PERFORMANCE BENCHMARK")
        print(f"{'='*80}")
        print(f"Dataset: 10,000 events")
        print(f"Starting 1,000 query benchmark...")
        
        # Benchmark queries
        start_time = time.perf_counter()
        
        for i in range(1000):
            # Query by correlation_id (common use case)
            events = event_store.get_events_by_correlation(f"corr-{i % 100}")
        
        elapsed = time.perf_counter() - start_time
        
        # Calculate metrics
        throughput = 1000 / elapsed
        latency_per_query = (elapsed / 1000) * 1000  # milliseconds
        
        print(f"\nResults:")
        print(f"  Queries executed: 1,000")
        print(f"  Total time: {elapsed:.3f}s")
        print(f"  Throughput: {throughput:.1f} queries/s")
        print(f"  Average latency: {latency_per_query:.3f}ms per query")
        print(f"  Target: >500 queries/s")
        print(f"  Status: {'✅ PASS' if throughput > 500 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        assert throughput > 500, f"Query throughput too low: {throughput:.1f} queries/s"


class TestSagaPerformance:
    """Benchmark saga execution performance."""
    
    @pytest.mark.asyncio
    async def test_saga_execution_throughput(self):
        """
        Benchmark: Saga execution throughput
        Test: Execute 100 sagas sequentially, measure performance
        """
        event_store = EventStore(":memory:")
        
        async def fast_step():
            await asyncio.sleep(0.001)  # 1ms simulated work
            return True
        
        async def fast_compensation():
            await asyncio.sleep(0.001)
            return True
        
        print(f"\n{'='*80}")
        print(f"SAGA EXECUTION THROUGHPUT BENCHMARK")
        print(f"{'='*80}")
        print(f"Starting 100 saga executions (3 steps each)...")
        
        start_time = time.perf_counter()
        
        successful_sagas = 0
        for i in range(100):
            saga = Saga(
                saga_id=f"perf-saga-{i}",
                correlation_id=f"perf-corr-{i}",
                event_store=event_store,
                timeout=5.0
            )
            
            # Add 3 steps
            for step_num in range(3):
                saga.add_step(SagaStep(
                    name=f"step_{step_num}",
                    action=fast_step,
                    compensation=fast_compensation
                ))
            
            success = await saga.execute()
            if success:
                successful_sagas += 1
        
        elapsed = time.perf_counter() - start_time
        
        # Calculate metrics
        throughput = 100 / elapsed
        avg_saga_time = elapsed / 100
        
        print(f"\nResults:")
        print(f"  Sagas executed: {successful_sagas}/100")
        print(f"  Total time: {elapsed:.3f}s")
        print(f"  Throughput: {throughput:.2f} sagas/s")
        print(f"  Average per saga: {avg_saga_time*1000:.3f}ms")
        print(f"  Target: >10 sagas/s")
        print(f"  Status: {'✅ PASS' if throughput > 10 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        assert successful_sagas == 100, "All sagas should succeed"
        assert throughput > 10, f"Saga throughput too low: {throughput:.2f} sagas/s"
    
    @pytest.mark.asyncio
    async def test_concurrent_saga_execution(self):
        """
        Benchmark: Concurrent saga execution
        Test: Execute 50 sagas concurrently
        """
        event_store = EventStore(":memory:")
        
        async def concurrent_step():
            await asyncio.sleep(0.01)  # 10ms simulated work
            return True
        
        async def concurrent_compensation():
            await asyncio.sleep(0.005)
            return True
        
        print(f"\n{'='*80}")
        print(f"CONCURRENT SAGA EXECUTION BENCHMARK")
        print(f"{'='*80}")
        print(f"Starting 50 concurrent sagas (3 steps each)...")
        
        # Create 50 sagas
        sagas = []
        for i in range(50):
            saga = Saga(
                saga_id=f"concurrent-saga-{i}",
                correlation_id=f"concurrent-corr-{i}",
                event_store=event_store,
                timeout=10.0
            )
            
            for step_num in range(3):
                saga.add_step(SagaStep(
                    name=f"step_{step_num}",
                    action=concurrent_step,
                    compensation=concurrent_compensation
                ))
            
            sagas.append(saga)
        
        # Execute all concurrently
        start_time = time.perf_counter()
        results = await asyncio.gather(*[saga.execute() for saga in sagas])
        elapsed = time.perf_counter() - start_time
        
        successful = sum(1 for r in results if r is True)
        
        print(f"\nResults:")
        print(f"  Sagas executed: {successful}/50")
        print(f"  Total time: {elapsed:.3f}s")
        print(f"  Effective throughput: {50/elapsed:.2f} sagas/s")
        print(f"  Speedup vs sequential: {(50*0.03)/elapsed:.2f}x")
        print(f"  Target: <2s for 50 concurrent sagas")
        print(f"  Status: {'✅ PASS' if elapsed < 2.0 else '⚠️ ACCEPTABLE' if elapsed < 5.0 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        assert successful == 50, "All sagas should succeed"
        assert elapsed < 5.0, f"Concurrent execution too slow: {elapsed:.3f}s"


class TestMemoryProfiling:
    """Profile memory usage during operations."""
    
    @pytest.mark.asyncio
    async def test_actor_memory_usage(self):
        """
        Profile: Actor memory usage with 1000 positions
        Verify: Memory growth is reasonable
        """
        tracemalloc.start()
        
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store, max_positions=2000)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        # Baseline memory
        snapshot_start = tracemalloc.take_snapshot()
        
        # Add 1000 positions
        for i in range(1000):
            await actor.ask("ADD_POSITION", {
                "position_id": f"mem-pos-{i}",
                "entry_price": 100000.0 + i,
                "tp_price": 101000.0 + i,
                "size": 1,
                "correlation_id": f"mem-{i}"
            })
        
        # Measure memory after
        snapshot_end = tracemalloc.take_snapshot()
        
        # Calculate memory growth
        top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')
        total_growth = sum(stat.size_diff for stat in top_stats) / 1024 / 1024  # MB
        
        print(f"\n{'='*80}")
        print(f"ACTOR MEMORY PROFILING")
        print(f"{'='*80}")
        print(f"Positions added: 1,000")
        print(f"Memory growth: {total_growth:.2f} MB")
        print(f"Per position: {(total_growth*1024)/1000:.2f} KB")
        print(f"\nTop 3 memory allocations:")
        for stat in top_stats[:3]:
            print(f"  {stat}")
        print(f"\nTarget: <10 MB for 1000 positions")
        print(f"Status: {'✅ PASS' if total_growth < 10 else '⚠️ ACCEPTABLE' if total_growth < 50 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        await actor.stop()
        await actor_task
        tracemalloc.stop()
        
        # Reasonable memory limit
        assert total_growth < 50, f"Memory usage too high: {total_growth:.2f} MB"
    
    def test_event_store_memory_usage(self):
        """
        Profile: EventStore memory usage with 10,000 events
        Verify: Memory growth is linear and reasonable
        """
        tracemalloc.start()
        
        event_store = EventStore(":memory:")
        
        snapshot_start = tracemalloc.take_snapshot()
        
        # Add 10,000 events
        for i in range(10000):
            event = create_test_event(
                event_type=EventType.POSITION_OPENED,
                correlation_id=f"mem-{i % 100}",
                data={
                    "position_id": f"pos-{i}",
                    "price": 100000.0 + i,
                    "size": 1,
                    "timestamp": time.time()
                }
            )
            event_store.append_event(event)
        
        snapshot_end = tracemalloc.take_snapshot()
        
        top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')
        total_growth = sum(stat.size_diff for stat in top_stats) / 1024 / 1024  # MB
        
        print(f"\n{'='*80}")
        print(f"EVENTSTORE MEMORY PROFILING")
        print(f"{'='*80}")
        print(f"Events stored: 10,000")
        print(f"Memory growth: {total_growth:.2f} MB")
        print(f"Per event: {(total_growth*1024)/10000:.3f} KB")
        print(f"\nTop 3 memory allocations:")
        for stat in top_stats[:3]:
            print(f"  {stat}")
        print(f"\nTarget: <20 MB for 10,000 events")
        print(f"Status: {'✅ PASS' if total_growth < 20 else '⚠️ ACCEPTABLE' if total_growth < 100 else '❌ FAIL'}")
        print(f"{'='*80}\n")
        
        tracemalloc.stop()
        
        assert total_growth < 100, f"EventStore memory usage too high: {total_growth:.2f} MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
