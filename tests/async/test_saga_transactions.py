"""
Saga Transaction Tests - Production Grade

Tests real saga execution with compensation, timeout, and failure scenarios.
"""

import pytest
import asyncio
from typing import List
from bot.strategy.modules.event_store import EventStore, EventType
from bot.strategy.sagas.saga_coordinator import Saga, SagaStep, SagaContext


class TestSagaExecution:
    """Test real saga execution with async steps."""
    
    @pytest.mark.asyncio
    async def test_successful_3_step_saga_no_compensation(self):
        """
        Test: Saga with 3 steps executes successfully without compensation.
        
        Validates:
        - All 3 steps execute in order
        - No compensation triggered
        - EventStore contains correct events
        - Context shows 'completed' status
        """
        event_store = EventStore(":memory:")
        execution_log: List[str] = []
        
        saga = Saga(
            saga_id="test-saga-success",
            correlation_id="test-corr-001",
            event_store=event_store,
            timeout=5.0
        )
        
        # Step 1: Action
        async def step1_action():
            await asyncio.sleep(0.01)
            execution_log.append("step1_executed")
            return {"step": 1, "data": "step1_result"}
        
        async def step1_compensation(result):
            execution_log.append("step1_compensated")
        
        saga.add_step(SagaStep(
            name="step1",
            action=step1_action,
            compensation=step1_compensation
        ))
        
        # Step 2: Action
        async def step2_action():
            await asyncio.sleep(0.01)
            execution_log.append("step2_executed")
            return {"step": 2, "data": "step2_result"}
        
        async def step2_compensation(result):
            execution_log.append("step2_compensated")
        
        saga.add_step(SagaStep(
            name="step2",
            action=step2_action,
            compensation=step2_compensation
        ))
        
        # Step 3: Action
        async def step3_action():
            await asyncio.sleep(0.01)
            execution_log.append("step3_executed")
            return {"step": 3, "data": "step3_result"}
        
        async def step3_compensation(result):
            execution_log.append("step3_compensated")
        
        saga.add_step(SagaStep(
            name="step3",
            action=step3_action,
            compensation=step3_compensation
        ))
        
        # Execute saga
        print(f"\n{'='*60}")
        print("TEST: 3-Step Saga - Success Path")
        print(f"{'='*60}")
        
        success = await saga.execute()
        
        # Verify success
        assert success is True, "Saga should succeed"
        assert saga.context.status == "completed", f"Expected 'completed', got '{saga.context.status}'"
        
        # Verify all steps executed
        assert "step1_executed" in execution_log, "Step 1 should execute"
        assert "step2_executed" in execution_log, "Step 2 should execute"
        assert "step3_executed" in execution_log, "Step 3 should execute"
        
        # Verify NO compensation
        assert "step1_compensated" not in execution_log, "Step 1 should NOT compensate"
        assert "step2_compensated" not in execution_log, "Step 2 should NOT compensate"
        assert "step3_compensated" not in execution_log, "Step 3 should NOT compensate"
        
        # Verify execution order
        assert execution_log == ["step1_executed", "step2_executed", "step3_executed"], \
            f"Expected ordered execution, got: {execution_log}"
        
        # Verify EventStore events
        events = event_store.get_all_events()
        event_types = [e.event_type for e in events]
        
        assert EventType.SAGA_STARTED in event_types, "Missing SAGA_STARTED event"
        assert EventType.SAGA_STEP_COMPLETED in event_types, "Missing SAGA_STEP_COMPLETED events"
        assert EventType.SAGA_COMPLETED in event_types, "Missing SAGA_COMPLETED event"
        
        # Count step completions
        step_completed_count = event_types.count(EventType.SAGA_STEP_COMPLETED)
        assert step_completed_count == 3, f"Expected 3 SAGA_STEP_COMPLETED events, got {step_completed_count}"
        
        # Verify step results stored in context
        assert "step1" in saga.context.step_results, "Step 1 result not in context"
        assert "step2" in saga.context.step_results, "Step 2 result not in context"
        assert "step3" in saga.context.step_results, "Step 3 result not in context"
        
        print(f"✅ SUCCESS: Saga completed - executed {len(execution_log)} steps")
        print(f"   Execution log: {execution_log}")
        print(f"   EventStore events: {len(events)} total")
        print(f"   Status: {saga.context.status}")
    
    @pytest.mark.asyncio
    async def test_saga_compensation_on_step2_failure(self):
        """
        Test: Step 2 fails → compensates Step 1 in reverse order.
        
        Validates:
        - Step 1 executes successfully
        - Step 2 fails with exception
        - Step 1 compensation executes
        - Saga status is 'compensated'
        - EventStore contains compensation events
        """
        event_store = EventStore(":memory:")
        execution_log: List[str] = []
        
        saga = Saga(
            saga_id="test-saga-fail",
            correlation_id="test-corr-002",
            event_store=event_store,
            timeout=5.0
        )
        
        # Step 1: Success
        async def step1_action():
            await asyncio.sleep(0.01)
            execution_log.append("step1_executed")
            return {"step": 1, "data": "step1_result"}
        
        async def step1_compensation(result):
            await asyncio.sleep(0.01)
            execution_log.append("step1_compensated")
        
        saga.add_step(SagaStep(
            name="step1",
            action=step1_action,
            compensation=step1_compensation
        ))
        
        # Step 2: FAIL
        async def step2_action():
            await asyncio.sleep(0.01)
            execution_log.append("step2_attempted")
            raise Exception("Step 2 intentional failure")
        
        async def step2_compensation(result):
            execution_log.append("step2_compensated")
        
        saga.add_step(SagaStep(
            name="step2",
            action=step2_action,
            compensation=step2_compensation
        ))
        
        # Execute saga
        print(f"\n{'='*60}")
        print("TEST: Saga Compensation - Step 2 Failure")
        print(f"{'='*60}")
        
        success = await saga.execute()
        
        # Verify failure
        assert success is False, "Saga should fail"
        assert saga.context.status == "compensated", f"Expected 'compensated', got '{saga.context.status}'"
        
        # Verify step 1 executed
        assert "step1_executed" in execution_log, "Step 1 should execute"
        
        # Verify step 2 attempted but failed
        assert "step2_attempted" in execution_log, "Step 2 should be attempted"
        
        # Verify step 1 compensated
        assert "step1_compensated" in execution_log, "Step 1 should be compensated"
        
        # Verify step 2 NOT compensated (it never completed)
        assert "step2_compensated" not in execution_log, "Step 2 should NOT be compensated (never completed)"
        
        # Verify compensation happened AFTER failure
        step1_exec_idx = execution_log.index("step1_executed")
        step2_attempt_idx = execution_log.index("step2_attempted")
        step1_comp_idx = execution_log.index("step1_compensated")
        
        assert step1_exec_idx < step2_attempt_idx < step1_comp_idx, \
            f"Expected order: step1_exec -> step2_attempt -> step1_comp, got: {execution_log}"
        
        # Verify error recorded
        assert saga.context.error is not None, "Error should be recorded"
        # Note: saga.context.error may be simplified event type, not full exception message
        assert saga.context.error != "", "Error message should not be empty"
        
        # Verify EventStore events
        events = event_store.get_all_events()
        event_types = [e.event_type for e in events]
        
        assert EventType.SAGA_STARTED in event_types, "Missing SAGA_STARTED event"
        assert EventType.SAGA_STEP_FAILED in event_types, "Missing SAGA_STEP_FAILED event"
        assert EventType.SAGA_COMPENSATION_STARTED in event_types, "Missing SAGA_COMPENSATION_STARTED event"
        assert EventType.SAGA_STEP_COMPENSATED in event_types, "Missing SAGA_STEP_COMPENSATED event"
        assert EventType.SAGA_COMPENSATION_COMPLETED in event_types, "Missing SAGA_COMPENSATION_COMPLETED event"
        
        print(f"✅ SUCCESS: Compensation triggered correctly")
        print(f"   Execution log: {execution_log}")
        print(f"   Error: {saga.context.error}")
        print(f"   Status: {saga.context.status}")
    
    @pytest.mark.asyncio
    async def test_compensation_reverse_order_3_steps(self):
        """
        Test: 3 steps execute → Step 3 fails → compensate in REVERSE order (2, 1).
        
        This is the CRITICAL saga feature - compensation MUST be in reverse order.
        
        Validates:
        - Steps 1, 2 execute successfully
        - Step 3 fails
        - Compensation runs in reverse: step2 → step1
        - Compensation order is strictly enforced
        """
        event_store = EventStore(":memory:")
        execution_log: List[str] = []
        
        saga = Saga(
            saga_id="test-saga-reverse",
            correlation_id="test-corr-003",
            event_store=event_store,
            timeout=5.0
        )
        
        # Step 1
        async def step1_action():
            await asyncio.sleep(0.01)
            execution_log.append("step1_executed")
            return {"step": 1}
        
        async def step1_compensation(result):
            await asyncio.sleep(0.01)
            execution_log.append("step1_compensated")
        
        saga.add_step(SagaStep(name="step1", action=step1_action, compensation=step1_compensation))
        
        # Step 2
        async def step2_action():
            await asyncio.sleep(0.01)
            execution_log.append("step2_executed")
            return {"step": 2}
        
        async def step2_compensation(result):
            await asyncio.sleep(0.01)
            execution_log.append("step2_compensated")
        
        saga.add_step(SagaStep(name="step2", action=step2_action, compensation=step2_compensation))
        
        # Step 3 - FAIL
        async def step3_action():
            await asyncio.sleep(0.01)
            execution_log.append("step3_attempted")
            raise Exception("Step 3 fails")
        
        async def step3_compensation(result):
            execution_log.append("step3_compensated")
        
        saga.add_step(SagaStep(name="step3", action=step3_action, compensation=step3_compensation))
        
        # Execute saga
        print(f"\n{'='*60}")
        print("TEST: Compensation Reverse Order (CRITICAL)")
        print(f"{'='*60}")
        
        success = await saga.execute()
        
        # Verify failure
        assert success is False, "Saga should fail"
        
        # Verify execution order
        assert execution_log[0] == "step1_executed", "Step 1 should execute first"
        assert execution_log[1] == "step2_executed", "Step 2 should execute second"
        assert execution_log[2] == "step3_attempted", "Step 3 should be attempted"
        
        # CRITICAL: Verify compensation REVERSE order
        assert execution_log[3] == "step2_compensated", "Step 2 should compensate BEFORE step 1"
        assert execution_log[4] == "step1_compensated", "Step 1 should compensate AFTER step 2"
        
        # Verify step 3 NOT compensated (never completed)
        assert "step3_compensated" not in execution_log, "Step 3 should NOT be compensated"
        
        # Verify exact execution sequence
        expected_log = [
            "step1_executed",
            "step2_executed",
            "step3_attempted",
            "step2_compensated",  # REVERSE order!
            "step1_compensated"
        ]
        assert execution_log == expected_log, \
            f"Expected {expected_log}, got {execution_log}"
        
        print(f"✅ SUCCESS: Compensation ran in REVERSE order")
        print(f"   Execution: step1 → step2 → step3(fail)")
        print(f"   Compensation: step2 → step1 (REVERSE)")
        print(f"   Full log: {execution_log}")
    
    @pytest.mark.asyncio
    async def test_critical_compensation_failure(self):
        """
        Test: Critical step compensation fails → saga marked as 'compensation_failed'.
        
        Validates:
        - Critical step compensation failure is detected
        - Saga status becomes 'compensation_failed'
        - EventStore contains SAGA_COMPENSATION_CRITICAL event
        - Compensation errors are recorded
        """
        event_store = EventStore(":memory:")
        execution_log: List[str] = []
        
        saga = Saga(
            saga_id="test-saga-critical",
            correlation_id="test-corr-004",
            event_store=event_store,
            timeout=5.0
        )
        
        # Step 1 - CRITICAL with failing compensation
        async def step1_action():
            await asyncio.sleep(0.01)
            execution_log.append("step1_executed")
            return {"step": 1}
        
        async def step1_compensation(result):
            await asyncio.sleep(0.01)
            execution_log.append("step1_compensation_attempted")
            raise Exception("CRITICAL: Step 1 compensation failed - manual intervention required")
        
        saga.add_step(SagaStep(
            name="step1_critical",
            action=step1_action,
            compensation=step1_compensation,
            critical=True  # Mark as CRITICAL
        ))
        
        # Step 2 - Will fail
        async def step2_action():
            await asyncio.sleep(0.01)
            execution_log.append("step2_attempted")
            raise Exception("Step 2 fails")
        
        async def step2_compensation(result):
            execution_log.append("step2_compensated")
        
        saga.add_step(SagaStep(name="step2", action=step2_action, compensation=step2_compensation))
        
        # Execute saga
        print(f"\n{'='*60}")
        print("TEST: Critical Compensation Failure")
        print(f"{'='*60}")
        
        success = await saga.execute()
        
        # Verify failure
        assert success is False, "Saga should fail"
        
        # Verify critical compensation failure
        assert saga.context.status == "compensation_failed", \
            f"Expected 'compensation_failed', got '{saga.context.status}'"
        
        # Verify compensation errors recorded
        assert len(saga.context.compensation_errors) > 0, "Compensation errors should be recorded"
        assert any("CRITICAL" in err for err in saga.context.compensation_errors), \
            "Critical error should be in compensation_errors"
        
        # Verify compensation was attempted
        assert "step1_compensation_attempted" in execution_log, "Step 1 compensation should be attempted"
        
        # Verify EventStore contains critical event
        events = event_store.get_all_events()
        event_types = [e.event_type for e in events]
        
        assert EventType.SAGA_COMPENSATION_CRITICAL in event_types, \
            "Missing SAGA_COMPENSATION_CRITICAL event"
        
        # Find critical event and verify data
        critical_event = next((e for e in events if e.event_type == EventType.SAGA_COMPENSATION_CRITICAL), None)
        assert critical_event is not None, "Critical event should exist"
        assert critical_event.data.get("requires_manual_intervention") is True, \
            "Critical event should require manual intervention"
        
        print(f"✅ SUCCESS: Critical compensation failure detected")
        print(f"   Status: {saga.context.status}")
        print(f"   Compensation errors: {len(saga.context.compensation_errors)}")
        print(f"   Errors: {saga.context.compensation_errors}")
    
    @pytest.mark.asyncio
    async def test_saga_timeout_triggers_compensation(self):
        """
        Test: Saga times out → triggers compensation.
        
        Validates:
        - Saga execution times out
        - Timeout triggers compensation
        - Context shows timeout error
        - EventStore contains timeout-related events
        """
        event_store = EventStore(":memory:")
        execution_log: List[str] = []
        
        saga = Saga(
            saga_id="test-saga-timeout",
            correlation_id="test-corr-005",
            event_store=event_store,
            timeout=0.1  # Very short timeout
        )
        
        # Step 1 - Fast
        async def step1_action():
            execution_log.append("step1_executed")
            return {"step": 1}
        
        async def step1_compensation(result):
            execution_log.append("step1_compensated")
        
        saga.add_step(SagaStep(name="step1", action=step1_action, compensation=step1_compensation))
        
        # Step 2 - SLOW (will cause timeout)
        async def step2_action():
            execution_log.append("step2_started")
            await asyncio.sleep(1.0)  # Sleep longer than timeout
            execution_log.append("step2_completed")  # Should NOT reach here
            return {"step": 2}
        
        async def step2_compensation(result):
            execution_log.append("step2_compensated")
        
        saga.add_step(SagaStep(name="step2", action=step2_action, compensation=step2_compensation))
        
        # Execute saga
        print(f"\n{'='*60}")
        print("TEST: Saga Timeout → Compensation")
        print(f"{'='*60}")
        
        success = await saga.execute()
        
        # Verify timeout
        assert success is False, "Saga should fail on timeout"
        
        # Verify error is timeout
        assert saga.context.error is not None, "Error should be recorded"
        assert "timeout" in saga.context.error.lower(), f"Error should mention timeout, got: {saga.context.error}"
        
        # Verify step 1 executed
        assert "step1_executed" in execution_log, "Step 1 should execute"
        
        # Verify step 2 started but didn't complete
        assert "step2_started" in execution_log, "Step 2 should start"
        assert "step2_completed" not in execution_log, "Step 2 should NOT complete (timeout)"
        
        # Verify step 1 compensated
        assert "step1_compensated" in execution_log, "Step 1 should be compensated after timeout"
        
        # Verify EventStore contains compensation events
        events = event_store.get_all_events()
        event_types = [e.event_type for e in events]
        
        assert EventType.SAGA_COMPENSATION_STARTED in event_types, \
            "Timeout should trigger compensation"
        
        print(f"✅ SUCCESS: Timeout triggered compensation")
        print(f"   Timeout: 0.1s")
        print(f"   Error: {saga.context.error}")
        print(f"   Execution log: {execution_log}")
        print(f"   Status: {saga.context.status}")


class TestSagaContext:
    """Test saga context tracking."""
    
    @pytest.mark.asyncio
    async def test_context_tracks_step_results(self):
        """
        Test: Context stores results from each step.
        
        Validates:
        - Step results are stored in context.step_results
        - Results are accessible by step name
        - Results persist after saga completion
        """
        event_store = EventStore(":memory:")
        
        saga = Saga(
            saga_id="test-saga-context",
            correlation_id="test-corr-006",
            event_store=event_store
        )
        
        # Add steps with different return values
        async def step1_action():
            return {"data": "step1_data", "value": 100}
        
        async def step1_compensation(result):
            pass
        
        saga.add_step(SagaStep(name="step1", action=step1_action, compensation=step1_compensation))
        
        async def step2_action():
            return {"data": "step2_data", "value": 200}
        
        async def step2_compensation(result):
            pass
        
        saga.add_step(SagaStep(name="step2", action=step2_action, compensation=step2_compensation))
        
        # Execute
        print(f"\n{'='*60}")
        print("TEST: Context Tracks Step Results")
        print(f"{'='*60}")
        
        success = await saga.execute()
        
        # Verify success
        assert success is True, "Saga should succeed"
        
        # Verify results stored
        assert "step1" in saga.context.step_results, "Step 1 result should be stored"
        assert "step2" in saga.context.step_results, "Step 2 result should be stored"
        
        # Verify result contents
        step1_result = saga.context.step_results["step1"]
        assert step1_result["data"] == "step1_data", "Step 1 data should match"
        assert step1_result["value"] == 100, "Step 1 value should match"
        
        step2_result = saga.context.step_results["step2"]
        assert step2_result["data"] == "step2_data", "Step 2 data should match"
        assert step2_result["value"] == 200, "Step 2 value should match"
        
        # Verify context timing
        assert saga.context.started_at > 0, "Started timestamp should be set"
        assert saga.context.completed_at > 0, "Completed timestamp should be set"
        assert saga.context.completed_at > saga.context.started_at, "Completed should be after started"
        
        print(f"✅ SUCCESS: Context tracked all step results")
        print(f"   Step results: {saga.context.step_results}")
        print(f"   Duration: {saga.context.completed_at - saga.context.started_at:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
