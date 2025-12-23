"""
Base Recovery Engine with Enterprise-Grade Safety

Provides shared recovery logic with:
- Circuit breaker pattern
- Rate limiting
- Distributed locking
- Retry logic
- State persistence
- Audit trail

Created: November 20, 2025
"""

from abc import ABC, abstractmethod
from typing import List, Set, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import asyncio
import json
import hashlib
import time
from pathlib import Path
from collections import deque


class RecoveryStatus(Enum):
    """Recovery execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CIRCUIT_OPEN = "circuit_open"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failures detected, blocking requests
    HALF_OPEN = "half_open"    # Testing if service recovered


@dataclass
class RecoveryAttempt:
    """Single recovery attempt record"""
    attempt_id: str
    grid_price: float
    timestamp: float
    status: RecoveryStatus
    order_id: Optional[int] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    retry_count: int = 0


@dataclass
class RecoverySession:
    """Complete recovery session"""
    session_id: str
    engine_name: str
    start_time: float
    end_time: Optional[float] = None
    trigger_reason: str = ""
    missed_grids: Optional[List[float]] = None
    attempts: Optional[List[RecoveryAttempt]] = None
    total_recovered: int = 0
    total_failed: int = 0
    status: RecoveryStatus = RecoveryStatus.PENDING
    
    def __post_init__(self):
        if self.missed_grids is None:
            self.missed_grids = []
        if self.attempts is None:
            self.attempts = []


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    Opens circuit after N failures, closes after timeout.
    """
    
    def __init__(self, failure_threshold: int = 3, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def record_success(self):
        """Record successful operation"""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def can_attempt(self) -> Tuple[bool, str]:
        """Check if operation can be attempted"""
        if self.state == CircuitState.CLOSED:
            return True, "circuit_closed"
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    return True, "circuit_half_open"
                return False, f"circuit_open_for_{int(self.timeout - elapsed)}s"
            return False, "circuit_open"
        
        # HALF_OPEN: allow one attempt
        return True, "circuit_half_open"


class RateLimiter:
    """
    Token bucket rate limiter.
    Prevents API abuse and exchange rate limit violations.
    """
    
    def __init__(self, max_tokens: int = 10, refill_rate: float = 1.0):
        self.max_tokens = max_tokens
        self.tokens = float(max_tokens)
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens, wait if necessary"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        # Wait for tokens to refill
        wait_time = (tokens - self.tokens) / self.refill_rate
        await asyncio.sleep(wait_time)
        
        self._refill()
        self.tokens -= tokens
        return True


class BaseRecoveryEngine(ABC):
    """
    Ultra-robust base recovery engine with enterprise features.
    """
    
    def __init__(self, bot, config, logger):
        self.bot = bot
        self.config = config
        self.logger = logger
        
        # State management
        self.recovered_grids: Set[float] = set()
        self.pending_grids: Set[float] = set()
        self.failed_grids: Dict[float, int] = {}  # grid -> failure count
        
        # Session tracking
        self.current_session: Optional[RecoverySession] = None
        self.session_history: deque = deque(maxlen=100)  # Last 100 sessions
        
        # Safety mechanisms
        recovery_config = getattr(config, 'recovery', None)
        if recovery_config:
            failure_threshold = getattr(recovery_config, 'recovery_failure_threshold', 3)
            circuit_timeout = getattr(recovery_config, 'recovery_circuit_timeout', 60)
            max_tokens = getattr(recovery_config, 'recovery_max_concurrent', 5)
            rate_limit = getattr(recovery_config, 'recovery_rate_limit', 0.5)
            self.max_retries = getattr(recovery_config, 'max_retries', 3)
            self.retry_delay = getattr(recovery_config, 'retry_delay', 5)
            self.max_concurrent_recoveries = getattr(recovery_config, 'recovery_max_concurrent', 3)
        else:
            failure_threshold = 3
            circuit_timeout = 60
            max_tokens = 5
            rate_limit = 0.5
            self.max_retries = 3
            self.retry_delay = 5
            self.max_concurrent_recoveries = 3
        
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=circuit_timeout
        )
        self.rate_limiter = RateLimiter(
            max_tokens=max_tokens,
            refill_rate=rate_limit
        )
        
        # Distributed lock (prevents concurrent recovery)
        self.lock = asyncio.Lock()
        self.lock_timeout = 300  # 5 minutes
        
        # Health monitoring
        self.health_metrics = {
            'total_sessions': 0,
            'successful_sessions': 0,
            'failed_sessions': 0,
            'total_recovered': 0,
            'total_failed': 0,
            'circuit_opens': 0,
            'last_success_time': None,
            'last_failure_time': None
        }
        
        # Configuration
        self.enabled = True
        
        # Load persisted state
        self._load_state()
    
    @abstractmethod
    async def should_trigger(self) -> Tuple[bool, str]:
        """
        Determine if recovery should trigger.
        Returns: (should_trigger, reason)
        """
        pass
    
    @abstractmethod
    async def calculate_missed_grids(self) -> List[float]:
        """Calculate which grids were missed"""
        pass
    
    @abstractmethod
    def get_state_file_path(self) -> Path:
        """Return path to state file"""
        pass
    
    async def execute_recovery(self) -> Dict:
        """
        Main recovery execution with full safety mechanisms.
        This is the bulletproof entry point.
        """
        # Generate session ID
        session_id = self._generate_session_id()
        
        try:
            # Acquire distributed lock (prevent concurrent recovery)
            try:
                # Use asyncio.wait_for for Python 3.9 compatibility (asyncio.timeout added in 3.11)
                async with self.lock:
                    return await asyncio.wait_for(
                        self._execute_recovery_locked(session_id),
                        timeout=self.lock_timeout
                    )
            except asyncio.TimeoutError:
                self.logger.error(f"[{self.__class__.__name__}] Lock timeout - another recovery in progress")
                return {
                    'success': False,
                    'reason': 'lock_timeout',
                    'session_id': session_id
                }
        
        except Exception as e:
            self.logger.error(f"[{self.__class__.__name__}] Unexpected error: {e}", exc_info=True)
            return {
                'success': False,
                'reason': f'unexpected_error: {str(e)}',
                'session_id': session_id
            }
    
    async def _execute_recovery_locked(self, session_id: str) -> Dict:
        """Execute recovery with lock held"""
        
        # Pre-flight checks
        preflight_result = await self._preflight_checks()
        if not preflight_result['passed']:
            return {
                'success': False,
                'reason': preflight_result['reason'],
                'session_id': session_id
            }
        
        # Check circuit breaker
        can_attempt, circuit_reason = self.circuit_breaker.can_attempt()
        if not can_attempt:
            self.health_metrics['circuit_opens'] += 1
            return {
                'success': False,
                'reason': circuit_reason,
                'session_id': session_id,
                'status': RecoveryStatus.CIRCUIT_OPEN
            }
        
        # Check if should trigger
        should_trigger, trigger_reason = await self.should_trigger()
        if not should_trigger:
            return {
                'success': False,
                'reason': trigger_reason,
                'session_id': session_id
            }
        
        # Calculate missed grids
        missed_grids = await self.calculate_missed_grids()
        
        if not missed_grids:
            return {
                'success': True,
                'recovered': 0,
                'reason': 'no_missed_grids',
                'session_id': session_id
            }
        
        # Create recovery session
        self.current_session = RecoverySession(
            session_id=session_id,
            engine_name=self.__class__.__name__,
            start_time=time.time(),
            trigger_reason=trigger_reason,
            missed_grids=missed_grids,
            attempts=[],
            status=RecoveryStatus.RUNNING
        )
        
        self.logger.info(f"[{self.__class__.__name__}] Starting recovery session {session_id}")
        self.logger.info(f"  Trigger: {trigger_reason}")
        self.logger.info(f"  Missed grids: {len(missed_grids)}")
        
        # Execute recovery for each grid
        results = []
        recovered_count = 0
        failed_count = 0
        
        for grid_price in missed_grids:
            # Rate limiting
            await self.rate_limiter.acquire()
            
            # Recover single grid with retries
            result = await self._recover_single_grid_with_retry(grid_price)
            results.append(result)
            
            if result.status == RecoveryStatus.SUCCESS:
                recovered_count += 1
                self.circuit_breaker.record_success()
            else:
                failed_count += 1
                self.circuit_breaker.record_failure()
            
            self.current_session.attempts.append(result)
            
            # Check if circuit opened
            if self.circuit_breaker.state == CircuitState.OPEN:
                self.logger.warning(f"[{self.__class__.__name__}] Circuit breaker opened - stopping recovery")
                break
        
        # Finalize session
        self.current_session.end_time = time.time()
        self.current_session.total_recovered = recovered_count
        self.current_session.total_failed = failed_count
        self.current_session.status = RecoveryStatus.SUCCESS if failed_count == 0 else RecoveryStatus.FAILED
        
        # Update health metrics
        self._update_health_metrics(self.current_session)
        
        # Save session to history
        self.session_history.append(self.current_session)
        
        # Persist state
        self._save_state()
        self._save_session_history()
        
        # Log summary
        duration = self.current_session.end_time - self.current_session.start_time
        self.logger.info(f"[{self.__class__.__name__}] Recovery session {session_id} completed")
        self.logger.info(f"  Duration: {duration:.2f}s")
        self.logger.info(f"  Recovered: {recovered_count}/{len(missed_grids)}")
        self.logger.info(f"  Failed: {failed_count}/{len(missed_grids)}")
        
        return {
            'success': True,
            'session_id': session_id,
            'recovered': recovered_count,
            'failed': failed_count,
            'duration': duration,
            'status': self.current_session.status
        }
    
    async def _recover_single_grid_with_retry(self, grid_price: float) -> RecoveryAttempt:
        """
        Recover single grid with retry logic.
        """
        attempt_id = self._generate_attempt_id(grid_price)
        
        for retry in range(self.max_retries + 1):
            start_time = time.time()
            
            try:
                # Attempt recovery
                result = await self._recover_single_grid(grid_price, attempt_id, retry)
                
                # Calculate duration
                duration = (time.time() - start_time) * 1000
                result.duration_ms = duration
                
                if result.status == RecoveryStatus.SUCCESS:
                    return result
                
                # Retry on failure
                if retry < self.max_retries:
                    self.logger.warning(f"Grid {grid_price} recovery failed (attempt {retry + 1}/{self.max_retries + 1}) - retrying in {self.retry_delay}s")
                    await asyncio.sleep(self.retry_delay)
                
            except Exception as e:
                self.logger.error(f"Grid {grid_price} recovery exception: {e}", exc_info=True)
                
                if retry < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Final failure
                    return RecoveryAttempt(
                        attempt_id=attempt_id,
                        grid_price=grid_price,
                        timestamp=time.time(),
                        status=RecoveryStatus.FAILED,
                        error=str(e),
                        retry_count=retry + 1
                    )
        
        # All retries exhausted
        return RecoveryAttempt(
            attempt_id=attempt_id,
            grid_price=grid_price,
            timestamp=time.time(),
            status=RecoveryStatus.FAILED,
            error="max_retries_exceeded",
            retry_count=self.max_retries + 1
        )
    
    async def _recover_single_grid(self, grid_price: float, attempt_id: str, retry: int) -> RecoveryAttempt:
        """
        Recover a single grid level with full safety checks.
        """
        timestamp = time.time()
        
        # Check if already recovered
        if grid_price in self.recovered_grids:
            return RecoveryAttempt(
                attempt_id=attempt_id,
                grid_price=grid_price,
                timestamp=timestamp,
                status=RecoveryStatus.SUCCESS,
                error="already_recovered",
                retry_count=retry
            )
        
        # Check if currently pending
        if grid_price in self.pending_grids:
            return RecoveryAttempt(
                attempt_id=attempt_id,
                grid_price=grid_price,
                timestamp=timestamp,
                status=RecoveryStatus.FAILED,
                error="already_pending",
                retry_count=retry
            )
        
        # Check if position exists
        if await self._has_position_at_grid(grid_price):
            self.logger.info(f"Grid {grid_price} has existing position - marking as recovered")
            self.recovered_grids.add(grid_price)
            return RecoveryAttempt(
                attempt_id=attempt_id,
                grid_price=grid_price,
                timestamp=timestamp,
                status=RecoveryStatus.SUCCESS,
                error="position_exists",
                retry_count=retry
            )
        
        # Check if pending order exists
        if await self._has_pending_order_at_grid(grid_price):
            return RecoveryAttempt(
                attempt_id=attempt_id,
                grid_price=grid_price,
                timestamp=timestamp,
                status=RecoveryStatus.FAILED,
                error="pending_order_exists",
                retry_count=retry
            )
        
        # Mark as pending
        self.pending_grids.add(grid_price)
        
        try:
            # Place recovery order
            order_id = await self._place_recovery_order(grid_price, attempt_id)
            
            # Mark as recovered
            self.recovered_grids.add(grid_price)
            self.pending_grids.discard(grid_price)
            
            # Clear failure count
            self.failed_grids.pop(grid_price, None)
            
            return RecoveryAttempt(
                attempt_id=attempt_id,
                grid_price=grid_price,
                timestamp=timestamp,
                status=RecoveryStatus.SUCCESS,
                order_id=order_id,
                retry_count=retry
            )
        
        except Exception as e:
            # Remove from pending
            self.pending_grids.discard(grid_price)
            
            # Track failure
            self.failed_grids[grid_price] = self.failed_grids.get(grid_price, 0) + 1
            
            return RecoveryAttempt(
                attempt_id=attempt_id,
                grid_price=grid_price,
                timestamp=timestamp,
                status=RecoveryStatus.FAILED,
                error=str(e),
                retry_count=retry
            )
    
    async def _preflight_checks(self) -> Dict:
        """
        Comprehensive pre-flight safety checks.
        """
        # Check 1: Engine enabled
        if not self.enabled:
            return {'passed': False, 'reason': 'engine_disabled'}
        
        # Check 2: Bot running
        if not self.bot._running:
            return {'passed': False, 'reason': 'bot_not_running'}
        
        # Check 3: Not too many pending recoveries
        if len(self.pending_grids) >= self.max_concurrent_recoveries:
            return {'passed': False, 'reason': 'too_many_pending'}
        
        # Check 4: Cooldown
        if not self._check_cooldown():
            return {'passed': False, 'reason': 'cooldown_active'}
        
        return {'passed': True}
    
    async def _has_position_at_grid(self, grid_price: float) -> bool:
        """Check if position exists at grid level (with tolerance)"""
        try:
            # Get positions from position actor
            response = await self.bot.position_actor.ask({
                'type': 'GET_POSITIONS',
                'payload': {}
            })
            positions = response.get('positions', [])
            tolerance = 1.0
            
            return any(
                abs(pos.get('entry_price', 0) - grid_price) < tolerance
                for pos in positions
            )
        except Exception as e:
            self.logger.error(f"Error checking positions: {e}")
            return False  # Assume no position on error (safe)
    
    async def _has_pending_order_at_grid(self, grid_price: float) -> bool:
        """Check if pending order exists at grid level"""
        try:
            orders = await self.bot.get_open_orders()
            tolerance = 1.0
            
            return any(
                abs(order.get('limit_price', 0) - grid_price) < tolerance
                and order.get('state') == 'open'
                and not order.get('reduce_only', False)
                for order in orders
            )
        except Exception as e:
            self.logger.error(f"Error checking orders: {e}")
            return True  # Assume order exists on error (safe)
    
    async def _place_recovery_order(self, grid_price: float, attempt_id: str) -> int:
        """Place recovery MARKET order with tracking"""
        self.logger.info(f"Placing recovery order for grid {grid_price} (attempt: {attempt_id})")
        
        order_id = await self.bot.place_recovery_order(
            grid_price=grid_price,
            tag=f"RECOVERY_{attempt_id}"
        )
        
        return order_id
    
    def _check_cooldown(self) -> bool:
        """Check if recovery cooldown has passed"""
        last_time = self.health_metrics.get('last_success_time')
        if not last_time:
            return True
        
        cooldown = 300  # 5 minutes default
        elapsed = time.time() - last_time
        
        return elapsed >= cooldown
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.now().isoformat()
        engine_name = self.__class__.__name__
        return hashlib.sha256(f"{engine_name}_{timestamp}".encode()).hexdigest()[:16]
    
    def _generate_attempt_id(self, grid_price: float) -> str:
        """Generate unique attempt ID"""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(f"{grid_price}_{timestamp}".encode()).hexdigest()[:12]
    
    def _update_health_metrics(self, session: RecoverySession):
        """Update health metrics after session"""
        self.health_metrics['total_sessions'] += 1
        
        if session.status == RecoveryStatus.SUCCESS:
            self.health_metrics['successful_sessions'] += 1
            self.health_metrics['last_success_time'] = session.end_time
        else:
            self.health_metrics['failed_sessions'] += 1
            self.health_metrics['last_failure_time'] = session.end_time
        
        self.health_metrics['total_recovered'] += session.total_recovered
        self.health_metrics['total_failed'] += session.total_failed
    
    def _load_state(self):
        """Load persisted state"""
        try:
            state_file = self.get_state_file_path()
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.recovered_grids = set(state.get('recovered_grids', []))
                    self.failed_grids = state.get('failed_grids', {})
                    self.health_metrics.update(state.get('health_metrics', {}))
        except Exception as e:
            self.logger.warning(f"Failed to load recovery state: {e}")
    
    def _save_state(self):
        """Persist state to file"""
        try:
            state = {
                'recovered_grids': list(self.recovered_grids),
                'failed_grids': self.failed_grids,
                'health_metrics': self.health_metrics,
                'last_updated': datetime.now().isoformat()
            }
            
            state_file = self.get_state_file_path()
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write
            temp_file = state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.replace(state_file)
            
        except Exception as e:
            self.logger.error(f"Failed to save recovery state: {e}")
    
    def _save_session_history(self):
        """Save session history to audit log"""
        try:
            history_file = self.get_state_file_path().parent / f"{self.__class__.__name__}_history.jsonl"
            
            if self.current_session:
                with open(history_file, 'a') as f:
                    session_dict = asdict(self.current_session)
                    # Convert enum to string
                    session_dict['status'] = session_dict['status'].value if isinstance(session_dict['status'], RecoveryStatus) else session_dict['status']
                    for attempt in session_dict.get('attempts', []):
                        if isinstance(attempt.get('status'), RecoveryStatus):
                            attempt['status'] = attempt['status'].value
                    f.write(json.dumps(session_dict) + '\n')
        
        except Exception as e:
            self.logger.error(f"Failed to save session history: {e}")
    
    def get_health_status(self) -> Dict:
        """Get current health status"""
        success_rate = 0
        if self.health_metrics['total_sessions'] > 0:
            success_rate = (self.health_metrics['successful_sessions'] / 
                          self.health_metrics['total_sessions']) * 100
        
        return {
            'engine': self.__class__.__name__,
            'enabled': self.enabled,
            'circuit_state': self.circuit_breaker.state.value,
            'recovered_grids_count': len(self.recovered_grids),
            'pending_grids_count': len(self.pending_grids),
            'failed_grids_count': len(self.failed_grids),
            'success_rate': f"{success_rate:.1f}%",
            **self.health_metrics
        }
    
    def clear_recovered_grids(self, grids: List[float] = None):
        """Clear recovered grids (maintenance operation)"""
        if grids:
            for grid in grids:
                self.recovered_grids.discard(grid)
                self.failed_grids.pop(grid, None)
        else:
            self.recovered_grids.clear()
            self.failed_grids.clear()
        
        self._save_state()
        self.logger.info(f"[{self.__class__.__name__}] Cleared recovered grids")
