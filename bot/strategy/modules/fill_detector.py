"""
FillDetector - Fill Detection and Processing Module

Single Responsibility: Detect and process order fills from multiple sources

This module implements the dual fill detection architecture:
- PRIMARY: WebSocket fill detection (instant, 0.05s latency)
- BACKUP: Robust fill detector (polling, 5s latency, catches missed fills)

✅ NOV 8: Sequential fill processing via queue for grid bot safety
- All fills processed in strict FIFO order
- Eliminates race conditions from concurrent fills
- Guarantees consistent grid state

Extracted from GridBotWebSocket (Phase 3 - Fill processing)
"""

import logging
import time
import queue
import threading
import os
from typing import Dict, Callable, Optional, Set, Any
from collections import deque

from .fill_audit_log import FillAuditLog, FillProcessingRecord

log = logging.getLogger("runner")


class FillDetector:
    """
    Dual-source fill detection with sequential processing queue
    
    ✅ NOV 8: BULLETPROOF CONCURRENT FILLS via processing queue
    
    Architecture:
    - WebSocket/Robust detector → Queue fill events (instant, non-blocking)
    - Worker thread → Process fills sequentially (FIFO order)
    - State lock → Exclusive access during processing (no contention)
    
    Benefits:
    - Guaranteed sequential processing (grid state always consistent)
    - No race conditions (impossible with single-threaded processor)
    - No state staleness (each fill sees fresh state from previous fill)
    - Natural backpressure (queue depth indicates load)
    
    Responsibilities:
    - WebSocket fill detection (primary, instant)
    - Robust fill detection (backup, polling)
    - Fill deduplication (prevents double processing)
    - Sequential fill processing (queue-based)
    - Fill callback invocation
    
    NOT Responsible For:
    - TP placement (OrderManager handles this)
    - Position tracking (PositionManager handles this)
    - Order placement (OrderManager handles this)
    """
    
    def __init__(
        self,
        state_lock: threading.Lock,
        dedup_size: int = 5000,
        queue_size: int = 1000  # ✅ PHASE 0 FIX: Increased from 100 to 1000 (NOV 9)
    ):
        """
        Initialize fill detector with processing queue
        
        Args:
            state_lock: Shared state lock for thread-safe operations
            dedup_size: Maximum number of fill IDs to track for deduplication
            queue_size: Maximum fill queue size (prevents memory overflow)
        """
        self._state_lock = state_lock
        
        # FIFO deque for fill deduplication (auto-evicts oldest, no memory leak)
        # maxlen=5000 means automatic cleanup - oldest fill IDs removed when full
        # Much better than Set with manual cleanup (no random eviction)
        self._processed_fills = deque(maxlen=dedup_size)
        
        # Fill callback storage
        self._fill_callback: Optional[Callable[[Dict], None]] = None
        
        # State manager for reloading state before fill processing
        self._state_manager: Optional[Any] = None
        
        # Robust fill detector integration (optional)
        self.robust_fill_detector: Optional[Any] = None
        
        # ✅ NOV 8: Fill processing queue for sequential processing
        self.fill_queue = queue.Queue(maxsize=queue_size)
        self.processing_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Queue statistics (thread-safe with dedicated lock)
        self._stats_lock = threading.Lock()
        self._queue_stats = {
            'total_queued': 0,
            'total_processed': 0,
            'max_depth': 0,
            'drops': 0
        }
        
        # ✅ CRITICAL NOV 9: Persistent fill audit log - BOT MEMORY!
        self.audit_log = FillAuditLog()
        log.info(f"✅ Fill audit log initialized - bot now has permanent memory!")
        
        log.info(f"✅ FillDetector initialized (queue_size={queue_size}, dedup_size={dedup_size})")
    
    def set_fill_callback(self, callback: Callable[[Dict], None]):
        """
        Register callback for fill detection
        
        Args:
            callback: Function to call when fill is detected
                     Should accept fill_data dict
        """
        self._fill_callback = callback
    
    def set_state_manager(self, state_manager: Any):
        """
        Set state manager for state reloading
        
        Args:
            state_manager: State manager instance with load_state() method
        """
        if state_manager is not None and not hasattr(state_manager, 'load_state'):
            raise ValueError("State manager must have 'load_state()' method")
        
        self._state_manager = state_manager
        log.info(f"✅ State manager {'set' if state_manager else 'cleared'}")
    
    def set_robust_detector(self, robust_detector: Any):
        """
        Register robust fill detector (polling backup system)
        
        Args:
            robust_detector: Robust fill detection instance
        """
        self.robust_fill_detector = robust_detector
        
        # Register ourselves as callback for robust detector
        if robust_detector:
            robust_detector.add_fill_callback(self.handle_robust_fill)
    
    # ========================================================================
    # Sequential Fill Processing (NOV 8 - Queue-based)
    # ========================================================================
    
    def start_processing(self):
        """
        Start sequential fill processor thread
        
        ✅ NOV 8: Worker thread processes fills in strict FIFO order
        This eliminates all race conditions from concurrent fill processing.
        """
        if not self._fill_callback:
            raise ValueError("❌ No fill callback registered - call set_fill_callback() first")
        
        if self.processing_thread and self.processing_thread.is_alive():
            log.warning("⚠️ Fill processor already running")
            return
        
        self.shutdown_event.clear()
        self.processing_thread = threading.Thread(
            target=self._process_fill_queue,
            daemon=True,
            name="FillProcessor"
        )
        self.processing_thread.start()
        log.info("✅ Fill processing queue started")
    
    def requeue_fill(self, fill_data: Dict):
        """
        🛡️ FIX NOV 9 PHASE 2: Requeue a fill for reprocessing
        
        Used when fill processing fails due to transient errors (timeouts, etc.)
        """
        try:
            self.fill_queue.put_nowait(fill_data)
            log.info(f"♻️  Requeued fill: {fill_data.get('order_id')}")
        except queue.Full:
            log.error(f"❌ Fill queue full - cannot requeue fill {fill_data.get('order_id')}")
            raise
    
    def stop_processing(self):
        """
        Gracefully stop fill processor
        
        Processes remaining fills in queue before shutdown.
        """
        log.info("🛑 Stopping fill processor...")
        self.shutdown_event.set()
        
        # Wait for worker thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
            
            if self.processing_thread.is_alive():
                log.critical("❌ Fill processor thread didn't stop - may cause issues!")
                log.critical("   NOT processing remaining fills to avoid concurrent access")
                return  # Don't process remaining fills if thread is still running
        
        # Only process remaining fills if worker thread is definitely stopped
        self._process_remaining_fills()
        
        log.info(f"✅ Fill processor stopped (stats: {self._queue_stats})")
    
    def _process_remaining_fills(self):
        """
        Process remaining fills after worker thread has stopped
        
        Only call this after confirming worker thread is dead.
        """
        remaining = self.fill_queue.qsize()
        if remaining > 0:
            log.info(f"📥 Processing {remaining} remaining fills...")
            processed = 0
            while not self.fill_queue.empty():
                try:
                    fill_data = self.fill_queue.get_nowait()
                    self._process_single_fill_safe(fill_data)
                    self.fill_queue.task_done()
                    processed += 1
                except queue.Empty:
                    break
                except Exception as e:
                    log.error(f"Error processing remaining fill: {e}")
                    self.fill_queue.task_done()  # Still need to mark as done
            log.info(f"✅ Processed {processed} remaining fills")
    
    def _process_fill_queue(self):
        """
        Worker thread - processes fills sequentially (FIFO order)
        
        ✅ NOV 8: This is the heart of concurrent fill protection
        - Runs in single thread → no concurrency
        - Processes FIFO → predictable order
        - Minimal lock time → prevent deadlocks
        - Fresh state per fill → no staleness
        
        ✅ NOV 8 FIX: Reduced lock scope to prevent deadlocks
        """
        log.info("🚀 Fill processor worker started")
        consecutive_errors = 0
        max_consecutive_errors = 2  # ✅ NOV 11 FIX: Reduced from 5 to 2 for faster halt on critical errors
        
        # ✅ NOV 11 FIX: Add error rate tracking
        total_fills_processed = 0
        total_errors = 0
        error_rate_threshold = 0.20  # 20% error rate triggers halt
        min_sample_size = 10  # Need at least 10 fills before checking error rate
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for fill (1 second timeout to check shutdown flag)
                fill_data = self.fill_queue.get(timeout=1.0)
                
                # Track queue depth for monitoring (thread-safe)
                current_depth = self.fill_queue.qsize()
                with self._stats_lock:
                    self._queue_stats['max_depth'] = max(
                        self._queue_stats['max_depth'],
                        current_depth
                    )
                
                # Alert if queue getting deep (might indicate system overload)
                if current_depth > 10:
                    log.warning(f"📊 Fill queue depth: {current_depth} (high load)")
                
                try:
                    # 🔥 CRITICAL FIX: Process WITHOUT holding state lock for extended periods
                    # This prevents deadlock when other threads need the lock
                    self._process_single_fill_safe(fill_data)
                    
                    with self._stats_lock:
                        self._queue_stats['total_processed'] += 1
                    
                    # ✅ NOV 11 FIX: Track successful fills
                    total_fills_processed += 1
                    consecutive_errors = 0  # Reset on success
                    
                except RuntimeError as e:
                    # ✅ NOV 11 FIX: CRITICAL ERROR - TP placement failed after all retries
                    # This is a FATAL error that requires immediate bot halt
                    log.critical("=" * 80)
                    log.critical("🚨 CRITICAL ERROR: TP PLACEMENT FAILED - HALTING BOT!")
                    log.critical("=" * 80)
                    log.critical(f"Error: {e}")
                    log.critical(f"Fill data: {fill_data}")
                    log.critical("")
                    log.critical("REASON: TP placement failed after all retry attempts.")
                    log.critical("RISK: Position is UNPROTECTED with unlimited loss exposure.")
                    log.critical("ACTION: Bot will halt immediately. Manual intervention required.")
                    log.critical("=" * 80)
                    
                    # Send critical alert
                    try:
                        from bot.utils.notifier import TelegramNotifier
                        notifier = TelegramNotifier()
                        notifier.send(
                            f"🚨 BOT HALTED - CRITICAL ERROR\n\n"
                            f"TP placement failed after all retries:\n{e}\n\n"
                            f"Fill: {fill_data.get('side', 'UNKNOWN')} @ "
                            f"${fill_data.get('fill_price', 0):,.0f}\n\n"
                            f"⚠️ POSITION IS UNPROTECTED\n"
                            f"Manual intervention required immediately!"
                        )
                    except Exception as notify_err:
                        log.error(f"Failed to send alert: {notify_err}")
                    
                    # Signal main thread to shutdown
                    self.shutdown_event.set()
                    
                    # Stop processing immediately
                    break
                    
                except Exception as e:
                    # Non-critical errors - continue with circuit breaker
                    consecutive_errors += 1
                    total_errors += 1
                    total_fills_processed += 1
                    
                    log.error(f"❌ Error processing fill: {e}")
                    import traceback
                    log.error(traceback.format_exc())
                    
                    # ✅ NOV 11 FIX: Check error rate (not just consecutive errors)
                    if total_fills_processed >= min_sample_size:
                        error_rate = total_errors / total_fills_processed
                        if error_rate > error_rate_threshold:
                            log.critical("=" * 80)
                            log.critical(f"🚨 ERROR RATE THRESHOLD EXCEEDED: {error_rate:.1%}")
                            log.critical(f"Total fills: {total_fills_processed}")
                            log.critical(f"Total errors: {total_errors}")
                            log.critical(f"Threshold: {error_rate_threshold:.1%}")
                            log.critical("=" * 80)
                            
                            # Send alert
                            try:
                                from bot.utils.notifier import TelegramNotifier
                                notifier = TelegramNotifier()
                                notifier.send(
                                    f"🚨 BOT HALTED - HIGH ERROR RATE\n\n"
                                    f"Error rate: {error_rate:.1%}\n"
                                    f"Errors: {total_errors}/{total_fills_processed}\n"
                                    f"Threshold: {error_rate_threshold:.1%}\n\n"
                                    f"Bot halted for safety."
                                )
                            except Exception:
                                pass
                            
                            # Signal shutdown and stop
                            self.shutdown_event.set()
                            break
                    
                    # Circuit breaker: stop if too many consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        log.critical("=" * 80)
                        log.critical(f"🚨 CIRCUIT BREAKER: {consecutive_errors} consecutive errors")
                        log.critical("=" * 80)
                        
                        # Send alert
                        try:
                            from bot.utils.notifier import TelegramNotifier
                            notifier = TelegramNotifier()
                            notifier.send(
                                f"🚨 BOT HALTED - CIRCUIT BREAKER\n\n"
                                f"{consecutive_errors} consecutive errors detected.\n"
                                f"Bot halted for safety."
                            )
                        except Exception:
                            pass
                        
                        # Signal shutdown and stop
                        self.shutdown_event.set()
                        break
                finally:
                    # ALWAYS call task_done, even on error
                    self.fill_queue.task_done()
                
            except queue.Empty:
                continue  # Timeout - check shutdown flag and loop
        
        log.info(f"Fill processor worker stopped (processed {self._queue_stats['total_processed']} fills)")
        log.info(f"Final stats: {total_fills_processed} fills, {total_errors} errors ({total_errors/max(total_fills_processed, 1):.1%} error rate)")
    
    def _normalize_fill_data(self, fill_data: Dict) -> Dict:
        """
        Normalize fill data to consistent format
        
        Args:
            fill_data: Fill data in any format
            
        Returns:
            Normalized fill data dict with consistent field names
        """
        return {
            'order_id': str(fill_data.get('order_id', '')),
            'fill_price': float(fill_data.get('fill_price', fill_data.get('price', 0))),
            'fill_size': float(fill_data.get('fill_size', fill_data.get('size', 0))),
            'side': fill_data.get('side', '').lower(),
            'role': fill_data.get('role', ''),
            'timestamp': fill_data.get('timestamp', ''),
            'detection_source': fill_data.get('detection_source', 'websocket'),
            # 🔥 CRITICAL: Preserve partial fill tracking fields from ws_manager
            'cumulative_filled': fill_data.get('cumulative_filled', fill_data.get('fill_size', 0)),
            'total_order_size': fill_data.get('total_order_size', fill_data.get('fill_size', 0)),
            'unfilled_size': fill_data.get('unfilled_size', 0),
            'is_complete': fill_data.get('is_complete', True)  # Assume complete if not specified
        }
    
    def _validate_fill_data(self, fill_data: Dict) -> bool:
        """
        Validate fill data before processing
        
        Args:
            fill_data: Fill data dict (should be normalized first)
            
        Returns:
            True if valid, False otherwise
        """
        order_id = str(fill_data.get('order_id', ''))
        fill_price = fill_data.get('fill_price', 0)
        fill_size = fill_data.get('fill_size', 0)
        
        if not order_id:
            log.warning("⚠️ Fill missing order_id")
            return False
        if fill_price <= 0:
            log.warning(f"⚠️ Fill has invalid price: {fill_price}")
            return False
        if fill_size <= 0:
            log.warning(f"⚠️ Fill has invalid size: {fill_size}")
            return False
        
        return True
    
    def _generate_fill_id(self, fill_data: Dict) -> str:
        """
        Generate consistent fill ID for deduplication
        
        Args:
            fill_data: Fill data dict
            
        Returns:
            Unique fill ID string
        """
        order_id = str(fill_data.get('order_id', ''))
        fill_price = fill_data.get('fill_price', 0)
        fill_size = fill_data.get('fill_size', 0)
        
        # Don't include timestamp to catch true duplicates
        return f"{order_id}_{fill_price}_{fill_size}"
    
    def _is_duplicate_fill(self, fill_id: str) -> bool:
        """
        Check if fill is duplicate and mark as processed atomically
        
        Args:
            fill_id: Fill ID to check
            
        Returns:
            True if duplicate, False if new (and now marked as processed)
        """
        with self._state_lock:
            if fill_id in self._processed_fills:
                return True
            self._processed_fills.append(fill_id)
            return False
    
    def _process_single_fill_safe(self, fill_data: Dict):
        """
        Process fill with minimal lock time to prevent deadlocks
        
        ✅ NOV 8 FIX: Split into prepare (with lock) and execute (without lock) phases
        - Prepare phase: acquire state lock, read needed data, release lock
        - Execute phase: call callbacks WITHOUT holding state lock
        - Prevents deadlock when callbacks need to acquire other locks
        """
        order_id = fill_data.get('order_id')
        side = fill_data.get('side', '').lower()
        size = float(fill_data.get('fill_size', 0))
        fill_price = float(fill_data.get('fill_price', 0))
        
        # Generate fill ID for deduplication
        fill_id = self._generate_fill_id(fill_data)
        
        # ✅ CRITICAL NOV 9: Check audit log first (permanent memory)
        if self.audit_log.was_fill_processed(str(order_id)):
            existing_record = self.audit_log.get_fill_record(str(order_id))
            log.info(f"✅ Fill already processed successfully (in audit log): {order_id}")
            if existing_record:
                log.debug(f"   Previous processing at: {time.ctime(existing_record.processed_at)}")
                log.debug(f"   TP placed: {existing_record.tp_order_placed}, Grid placed: {existing_record.next_grid_placed}")
            return
        
        # Atomic duplicate check and marking (in-memory dedup)
        if self._is_duplicate_fill(fill_id):
            log.debug(f"⚠️ Duplicate fill detected in memory, skipping: {fill_id}")
            return
        
        log.info(f"🔄 Processing fill: {side.upper()} {size} @ ${fill_price:,.2f} (Order: {order_id})")
        
        # 🔥 PHASE 1: Prepare - MINIMAL lock time
        state_loaded = False
        with self._state_lock:
            # Load fresh state from disk BEFORE processing
            if self._state_manager:
                try:
                    self._state_manager.load_state()
                    state_loaded = True
                    log.debug("✅ Fresh state loaded from disk before fill processing")
                except Exception as e:
                    log.warning(f"⚠️ Could not reload state before fill: {e}")
        
        # 🔥 PHASE 2: Execute - NO LOCK (callbacks may acquire other locks)
        # This prevents deadlock scenarios where:
        # - Thread A holds state_lock, waits for other_lock
        # - Thread B holds other_lock, waits for state_lock
        
        # ✅ CRITICAL NOV 9: Track fill processing in audit log
        detected_at = time.time()
        detection_method = fill_data.get('detection_source', 'unknown')
        processing_success = False
        error_msg = None
        
        if self._fill_callback:
            try:
                # 🎯 This is where fill processing happens (TP placement, next grid order)
                # Callback executes WITHOUT holding state_lock
                self._fill_callback(fill_data)
                processing_success = True
                log.info(f"✅ Fill processed successfully via callback")
            except Exception as e:
                error_msg = str(e)
                log.error(f"❌ Error in fill processed callback: {e}")
                import traceback
                log.error(traceback.format_exc())
                # Don't crash worker - just log and continue
        else:
            error_msg = "No fill callback registered"
            log.warning("⚠️ No fill callback registered - fill not processed!")
        
        # ✅ CRITICAL NOV 9: Record to audit log for permanent memory
        # This gives the bot complete memory of what it did!
        try:
            audit_record = FillProcessingRecord(
                order_id=str(order_id),
                fill_price=fill_price,
                fill_size=size,
                side=side,
                role=fill_data.get('role', 'unknown'),
                detected_at=detected_at,
                processed_at=time.time(),
                detection_method=detection_method,
                tp_order_placed=False,  # Will be updated by callback if successful
                tp_order_id=None,
                tp_price=None,
                next_grid_placed=False,
                next_grid_order_id=None,
                next_grid_price=None,
                success=processing_success,
                error_message=error_msg,
                retry_count=0,
                session_tag=getattr(self, 'session_tag', 'unknown'),
                bot_pid=os.getpid()
            )
            
            self.audit_log.record_fill_processing(audit_record)
            log.debug(f"📝 Fill recorded to audit log: {order_id}")
        
        except Exception as e:
            log.error(f"❌ Failed to record fill to audit log: {e}")
            # Non-fatal - continue processing
    
    def _process_single_fill(self, fill_data: Dict):
        """
        LEGACY: Process a single fill with exclusive state lock
        
        ⚠️ DEPRECATED: Use _process_single_fill_safe() to avoid deadlocks
        This method is kept for compatibility but should not be used.
        """
        log.warning("⚠️ Using deprecated _process_single_fill method - use _process_single_fill_safe instead")
        
        # Normalize data to handle both old and new formats
        normalized_data = self._normalize_fill_data(fill_data)
        
        # Use the safe method internally
        self._process_single_fill_safe(normalized_data)
    
    def get_queue_stats(self) -> Dict:
        """
        Get queue statistics for monitoring (thread-safe)
        
        Returns:
            Dict with queue depth, processed count, etc.
        """
        # Capture queue size outside lock to minimize lock time
        current_depth = self.fill_queue.qsize()
        is_processing = self.processing_thread.is_alive() if self.processing_thread else False
        
        with self._stats_lock:
            return {
                'current_depth': current_depth,
                'max_depth': self._queue_stats['max_depth'],
                'total_queued': self._queue_stats['total_queued'],
                'total_processed': self._queue_stats['total_processed'],
                'drops': self._queue_stats['drops'],
                'is_processing': is_processing
            }
    
    def get_health_status(self) -> Dict:
        """
        Get comprehensive health status of fill detector
        
        Returns:
            Dict with health status, issues, stats, and component status
        """
        stats = self.get_queue_stats()
        
        # Determine health based on various factors
        is_healthy = True
        issues = []
        
        if not self._fill_callback:
            is_healthy = False
            issues.append("No fill callback registered")
        
        if stats['drops'] > 0:
            is_healthy = False
            issues.append(f"Fill drops detected: {stats['drops']}")
        
        if stats['current_depth'] > self.fill_queue.maxsize * 0.8:
            is_healthy = False
            issues.append(f"Queue nearly full: {stats['current_depth']}/{self.fill_queue.maxsize}")
        
        if not stats['is_processing']:
            is_healthy = False
            issues.append("Fill processor not running")
        
        return {
            'is_healthy': is_healthy,
            'issues': issues,
            'stats': stats,
            'dedup_cache_size': self.get_processed_count(),
            'components': {
                'fill_callback': self._fill_callback is not None,
                'state_manager': self._state_manager is not None,
                'robust_detector': self.robust_fill_detector is not None,
                'processor_running': stats['is_processing']
            }
        }
    
    # ========================================================================
    # Fill Detection (Queueing Entry Points)
    # ========================================================================
    
    def _handle_queue_full(self, order_id: str, fill_price: float):
        """
        Handle queue full scenario with proper error logging
        
        Args:
            order_id: Order ID of dropped fill
            fill_price: Fill price of dropped fill
        """
        with self._stats_lock:
            self._queue_stats['drops'] += 1
            total_drops = self._queue_stats['drops']
        
        log.critical("=" * 80)
        log.critical(f"🚨 CRITICAL: FILL QUEUE FULL - FILL DROPPED!")
        log.critical(f"   Order ID: {order_id}")
        log.critical(f"   Fill Price: ${fill_price:,.0f}")
        log.critical(f"   Queue Size: {self.fill_queue.qsize()}/{self.fill_queue.maxsize}")
        log.critical(f"   Total Drops: {total_drops}")
        log.critical("   ⚠️ System may be overloaded or worker thread stuck!")
        log.critical("=" * 80)
        
        # Send Telegram alert with proper error handling
        try:
            from bot.utils.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.send(
                f"🚨 CRITICAL: Fill Queue Full!\n\n"
                f"Order: {order_id}\n"
                f"Price: ${fill_price:,.0f}\n"
                f"Queue: {self.fill_queue.qsize()}/{self.fill_queue.maxsize}\n"
                f"Drops: {total_drops}\n\n"
                f"System overloaded or worker stuck!"
            )
            log.info("✅ Critical alert sent via Telegram")
        except ImportError:
            log.warning("⚠️ TelegramNotifier not available - alert not sent")
        except Exception as e:
            log.error(f"❌ Failed to send Telegram alert: {e}")
    
    def _queue_normalized_fill(self, normalized_data: Dict) -> bool:
        """
        Queue already normalized and validated fill data
        
        Args:
            normalized_data: Pre-normalized and validated fill data
            
        Returns:
            True if queued successfully, False otherwise
        """
        order_id = normalized_data['order_id']
        fill_price = normalized_data['fill_price']
        
        try:
            self.fill_queue.put_nowait(normalized_data)
            
            # Thread-safe stats update
            with self._stats_lock:
                self._queue_stats['total_queued'] += 1
                total_queued = self._queue_stats['total_queued']
            
            queue_depth = self.fill_queue.qsize()
            log.info(f"✅ Fill queued successfully: {order_id} @ ${fill_price:,.0f} "
                     f"(queue depth: {queue_depth}, total queued: {total_queued})")
            
            return True
            
        except queue.Full:
            self._handle_queue_full(order_id, fill_price)
            return False
    
    def process_websocket_fill(self, fill_data: Dict) -> bool:
        """
        Queue fill detected via WebSocket for sequential processing
        
        ✅ NOV 8: Changed from direct processing to queueing
        - Instant return (< 1ms) → no WebSocket blocking  
        - Fill queued for sequential processing by worker thread
        - Strict FIFO order guaranteed
        
        ✅ NOV 8 FIX: Non-blocking put to prevent WebSocket thread stalling
        
        This is 400x faster than REST polling (0.05s vs 20s).
        
        Args:
            fill_data: Fill data with order_id, fill_price, fill_size, side
            
        Returns:
            True if fill was queued, False if queue full or invalid data
        """
        # Normalize data to consistent format
        normalized_data = self._normalize_fill_data(fill_data)
        
        order_id = normalized_data['order_id']
        fill_price = normalized_data['fill_price']
        
        # 🔍 DEBUG: Log that callback was called
        log.info(f"📥 process_websocket_fill() CALLED: order_id={order_id}, price=${fill_price:,.0f}")
        
        # Validate normalized data
        if not self._validate_fill_data(normalized_data):
            log.warning(f"⚠️ Invalid fill data after normalization: {normalized_data}")
            return False
        
        # Queue the normalized data
        return self._queue_normalized_fill(normalized_data)
    
    def handle_robust_fill(self, fill_data: Dict):
        """
        Handle fill detection from robust fill detection system (BACKUP)
        
        ✅ NOV 8: Queues fill for sequential processing (same as WebSocket)
        
        This provides backup fill detection using multiple methods:
        - WebSocket (primary, already handled above)
        - Order polling (fallback)
        - Position synchronization (reconciliation)
        
        The deduplication system ensures fills are processed exactly once,
        even if both WebSocket and polling detect the same fill.
        
        Args:
            fill_data: Fill data from robust detection system
        """
        try:
            # Normalize and validate before processing
            normalized_data = self._normalize_fill_data(fill_data)
            
            if not self._validate_fill_data(normalized_data):
                log.warning("⚠️ Invalid robust fill data, skipping")
                return
            
            order_id = normalized_data['order_id']
            detection_source = normalized_data.get('detection_source', 'robust_detector')
            
            log.info(f"🔔 Robust fill detected via {detection_source}: Order {order_id}")
            
            # Add order to robust tracking if detector available
            if self.robust_fill_detector:
                self.robust_fill_detector.add_order(order_id)
            
            # Queue directly without re-processing (data already normalized/validated)
            self._queue_normalized_fill(normalized_data)
            
        except Exception as e:
            log.error(f"Error handling robust fill: {e}")
    
    def get_processed_count(self) -> int:
        """
        Get number of fills processed (dedup cache size)
        
        Returns:
            Number of fill IDs currently in deduplication cache
        """
        with self._state_lock:
            return len(self._processed_fills)
    
    def clear_processed_fills(self):
        """
        Clear processed fills cache (for cleanup)
        
        Use during shutdown to free memory.
        """
        with self._state_lock:
            self._processed_fills.clear()
            log.debug("Cleared processed fills cache")
