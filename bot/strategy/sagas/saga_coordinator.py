"""
Saga Coordinator for distributed transaction management.
Implements saga pattern with automatic compensation on failure.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Dict, Any, List, Tuple, Optional
from uuid import uuid4

from loguru import logger as log

from bot.strategy.modules.event_store import EventStore, Event, EventType


@dataclass
class SagaStep:
    """
    Single step in a saga with forward action and compensation.
    
    Attributes:
        name: Step name for logging
        action: Forward action to execute
        compensation: Rollback action if saga fails
        critical: If True, compensation failure is critical
    """
    
    name: str
    action: Callable[[], Awaitable[Dict[str, Any]]]
    compensation: Callable[[Dict[str, Any]], Awaitable[None]]
    critical: bool = False


@dataclass
class SagaContext:
    """
    Saga execution context.
    
    Tracks saga state and step results.
    """
    
    saga_id: str
    correlation_id: str
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "pending"  # pending, running, completed, failed, compensating, compensated
    current_step: int = 0
    step_results: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    compensation_errors: List[str] = field(default_factory=list)


class Saga:
    """
    Saga coordinator with automatic compensation.
    
    Executes a series of steps and automatically compensates
    on failure by rolling back completed steps in reverse order.
    """
    
    def __init__(
        self,
        saga_id: str,
        correlation_id: str,
        event_store: EventStore,
        timeout: float = 60.0
    ):
        """
        Initialize saga.
        
        Args:
            saga_id: Unique saga identifier
            correlation_id: Correlation ID for tracing
            event_store: Event store for persistence
            timeout: Maximum saga execution time
        """
        self.saga_id = saga_id
        self.correlation_id = correlation_id
        self.event_store = event_store
        self.timeout = timeout
        
        self.steps: List[SagaStep] = []
        self.completed_steps: List[Tuple[str, Dict[str, Any]]] = []
        self.context = SagaContext(saga_id=saga_id, correlation_id=correlation_id)
    
    def add_step(self, step: SagaStep) -> None:
        """
        Add step to saga.
        
        Args:
            step: Step to add
        """
        self.steps.append(step)
        log.debug(f"[SAGA {self.saga_id}] Added step: {step.name}")
    
    async def execute(self) -> bool:
        """
        Execute saga with automatic compensation on failure.
        
        Returns:
            True if saga completed successfully, False if failed/compensated
        """
        log.info(f"[SAGA {self.saga_id}] 🚀 Starting execution with {len(self.steps)} steps")
        self.context.status = "running"
        
        # Log saga start event
        start_event = Event(
            event_id=str(uuid4()),
            event_type=EventType.SAGA_STARTED,
            timestamp=time.time(),
            correlation_id=self.correlation_id,
            aggregate_id=self.saga_id,
            data={
                "saga_id": self.saga_id,
                "steps": [s.name for s in self.steps]
            },
            metadata={"timeout": self.timeout}
        )
        self.event_store.append_event(start_event)
        
        try:
            # Execute with timeout
            await asyncio.wait_for(self._execute_steps(), timeout=self.timeout)
            
            # Mark completed
            self.context.status = "completed"
            self.context.completed_at = time.time()
            
            # Log completion event
            complete_event = Event(
                event_id=str(uuid4()),
                event_type=EventType.SAGA_COMPLETED,
                timestamp=time.time(),
                correlation_id=self.correlation_id,
                aggregate_id=self.saga_id,
                data={
                    "saga_id": self.saga_id,
                    "duration": self.context.completed_at - self.context.started_at,
                    "steps_completed": len(self.completed_steps)
                },
                metadata={"step_results": self.context.step_results}
            )
            self.event_store.append_event(complete_event)
            
            log.info(f"[SAGA {self.saga_id}] ✅ Completed successfully in {self.context.completed_at - self.context.started_at:.2f}s")
            return True
        
        except asyncio.TimeoutError:
            log.error(f"[SAGA {self.saga_id}] ⏱️ Timeout after {self.timeout}s")
            self.context.error = f"Saga timeout after {self.timeout}s"
            await self._compensate()
            return False
        
        except Exception as e:
            log.error(f"[SAGA {self.saga_id}] ❌ Failed: {e}")
            self.context.error = str(e)
            await self._compensate()
            return False
    
    async def _execute_steps(self) -> None:
        """Execute saga steps sequentially."""
        for i, step in enumerate(self.steps):
            self.context.current_step = i
            
            log.info(f"[SAGA {self.saga_id}] Executing step {i+1}/{len(self.steps)}: {step.name}")
            
            try:
                # Execute step action
                result = await step.action()
                
                # Record completion
                self.completed_steps.append((step.name, result))
                self.context.step_results[step.name] = result
                
                # Log step event
                step_event = Event(
                    event_id=str(uuid4()),
                    event_type=EventType.SAGA_STEP_COMPLETED,
                    timestamp=time.time(),
                    correlation_id=self.correlation_id,
                    aggregate_id=self.saga_id,
                    data={
                        "saga_id": self.saga_id,
                        "step": step.name,
                        "step_index": i,
                        "result": result
                    },
                    metadata={"total_steps": len(self.steps)}
                )
                self.event_store.append_event(step_event)
                
                log.info(f"[SAGA {self.saga_id}] ✓ Step completed: {step.name}")
            
            except Exception as e:
                log.error(f"[SAGA {self.saga_id}] Step {step.name} failed: {e}")
                
                # Log step failure event
                fail_event = Event(
                    event_id=str(uuid4()),
                    event_type=EventType.SAGA_STEP_FAILED,
                    timestamp=time.time(),
                    correlation_id=self.correlation_id,
                    aggregate_id=self.saga_id,
                    data={
                        "saga_id": self.saga_id,
                        "step": step.name,
                        "step_index": i,
                        "error": str(e)
                    },
                    metadata={"completed_steps": [s[0] for s in self.completed_steps]}
                )
                self.event_store.append_event(fail_event)
                
                raise
    
    async def _compensate(self) -> None:
        """Rollback completed steps in reverse order."""
        if not self.completed_steps:
            log.info(f"[SAGA {self.saga_id}] No steps to compensate")
            return
        
        log.warning(f"[SAGA {self.saga_id}] 🔄 Starting compensation for {len(self.completed_steps)} steps")
        self.context.status = "compensating"
        
        # Log compensation start event
        comp_start_event = Event(
            event_id=str(uuid4()),
            event_type=EventType.SAGA_COMPENSATION_STARTED,
            timestamp=time.time(),
            correlation_id=self.correlation_id,
            aggregate_id=self.saga_id,
            data={
                "saga_id": self.saga_id,
                "steps_to_compensate": [s[0] for s in self.completed_steps],
                "original_error": self.context.error
            },
            metadata={}
        )
        self.event_store.append_event(comp_start_event)
        
        # Compensate in reverse order
        for step_name, result in reversed(self.completed_steps):
            try:
                # Find step definition
                step = next((s for s in self.steps if s.name == step_name), None)
                if not step:
                    log.error(f"[SAGA {self.saga_id}] Step definition not found: {step_name}")
                    continue
                
                log.info(f"[SAGA {self.saga_id}] ↩️ Compensating: {step_name}")
                
                # Execute compensation
                await step.compensation(result)
                
                # Log compensation event
                comp_event = Event(
                    event_id=str(uuid4()),
                    event_type=EventType.SAGA_STEP_COMPENSATED,
                    timestamp=time.time(),
                    correlation_id=self.correlation_id,
                    aggregate_id=self.saga_id,
                    data={
                        "saga_id": self.saga_id,
                        "step": step_name,
                        "original_result": result
                    },
                    metadata={}
                )
                self.event_store.append_event(comp_event)
                
                log.info(f"[SAGA {self.saga_id}] ✓ Compensated: {step_name}")
            
            except Exception as e:
                error_msg = f"Compensation failed for {step_name}: {e}"
                log.error(f"[SAGA {self.saga_id}] 🚨 {error_msg}")
                self.context.compensation_errors.append(error_msg)
                
                # Check if critical
                if step and step.critical:
                    log.critical(f"[SAGA {self.saga_id}] CRITICAL compensation failure - manual intervention required!")
                    
                    # Log critical failure event
                    critical_event = Event(
                        event_id=str(uuid4()),
                        event_type=EventType.SAGA_COMPENSATION_CRITICAL,
                        timestamp=time.time(),
                        correlation_id=self.correlation_id,
                        aggregate_id=self.saga_id,
                        data={
                            "saga_id": self.saga_id,
                            "step": step_name,
                            "error": str(e),
                            "requires_manual_intervention": True
                        },
                        metadata={"compensation_errors": self.context.compensation_errors}
                    )
                    self.event_store.append_event(critical_event)
                    
                    # Don't continue compensation if critical
                    break
                else:
                    # Log non-critical compensation failure
                    comp_fail_event = Event(
                        event_id=str(uuid4()),
                        event_type=EventType.SAGA_STEP_COMPENSATION_FAILED,
                        timestamp=time.time(),
                        correlation_id=self.correlation_id,
                        aggregate_id=self.saga_id,
                        data={
                            "saga_id": self.saga_id,
                            "step": step_name,
                            "error": str(e)
                        },
                        metadata={}
                    )
                    self.event_store.append_event(comp_fail_event)
        
        # Mark compensation complete
        self.context.status = "compensated" if not self.context.compensation_errors else "compensation_failed"
        self.context.completed_at = time.time()
        
        # Log compensation complete event
        comp_complete_event = Event(
            event_id=str(uuid4()),
            event_type=EventType.SAGA_COMPENSATION_COMPLETED,
            timestamp=time.time(),
            correlation_id=self.correlation_id,
            aggregate_id=self.saga_id,
            data={
                "saga_id": self.saga_id,
                "status": self.context.status,
                "compensation_errors": self.context.compensation_errors,
                "duration": self.context.completed_at - self.context.started_at
            },
            metadata={}
        )
        self.event_store.append_event(comp_complete_event)
        
        if self.context.compensation_errors:
            log.error(f"[SAGA {self.saga_id}] ⚠️ Compensation completed with {len(self.context.compensation_errors)} errors")
        else:
            log.info(f"[SAGA {self.saga_id}] ✅ Compensation completed successfully")


class SagaOrchestrator:
    """
    Orchestrator for managing multiple concurrent sagas.
    
    Tracks active sagas and provides monitoring capabilities.
    """
    
    def __init__(self, event_store: EventStore, max_concurrent_sagas: int = 10):
        """
        Initialize saga orchestrator.
        
        Args:
            event_store: Event store for persistence
            max_concurrent_sagas: Maximum concurrent sagas
        """
        self.event_store = event_store
        self.max_concurrent_sagas = max_concurrent_sagas
        
        self._active_sagas: Dict[str, Saga] = {}
        self._saga_tasks: Dict[str, asyncio.Task] = {}
        self._completed_sagas: List[str] = []
        self._max_history = 100
        
        # Metrics
        self._total_started = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_compensated = 0
    
    async def start_saga(self, saga: Saga) -> asyncio.Task:
        """
        Start saga execution.
        
        Args:
            saga: Saga to execute
            
        Returns:
            Task for saga execution
            
        Raises:
            Exception: If max concurrent sagas reached
        """
        if len(self._active_sagas) >= self.max_concurrent_sagas:
            raise Exception(f"Max concurrent sagas reached: {self.max_concurrent_sagas}")
        
        self._active_sagas[saga.saga_id] = saga
        self._total_started += 1
        
        # Start execution task
        task = asyncio.create_task(self._execute_saga(saga))
        self._saga_tasks[saga.saga_id] = task
        
        log.info(f"[Orchestrator] Started saga: {saga.saga_id}")
        return task
    
    async def _execute_saga(self, saga: Saga) -> Saga:
        """
        Execute saga and update metrics.
        
        Returns the saga object with context for inspection.
        """
        try:
            success = await saga.execute()
            
            if success:
                self._total_completed += 1
            else:
                if saga.context.status == "compensated":
                    self._total_compensated += 1
                else:
                    self._total_failed += 1
            
            # Return saga object so caller can inspect step_results
            return saga
        
        finally:
            # Remove from active
            del self._active_sagas[saga.saga_id]
            del self._saga_tasks[saga.saga_id]
            
            # Add to history
            self._completed_sagas.append(saga.saga_id)
            if len(self._completed_sagas) > self._max_history:
                self._completed_sagas.pop(0)
    
    async def stop_all(self, timeout: float = 30.0) -> None:
        """
        Stop all active sagas.
        
        Args:
            timeout: Maximum wait time
        """
        log.info(f"[Orchestrator] Stopping {len(self._active_sagas)} active sagas...")
        
        # Cancel all tasks
        for task in self._saga_tasks.values():
            task.cancel()
        
        # Wait for completion
        if self._saga_tasks:
            await asyncio.wait(
                self._saga_tasks.values(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )
        
        log.info("[Orchestrator] All sagas stopped")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics."""
        return {
            "active_sagas": len(self._active_sagas),
            "total_started": self._total_started,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_compensated": self._total_compensated,
            "success_rate": self._total_completed / max(self._total_started, 1),
            "compensation_rate": self._total_compensated / max(self._total_started, 1),
            "active_saga_ids": list(self._active_sagas.keys())
        }
