"""
Base Actor implementation for message-passing concurrency model.
Provides mailbox-based communication with zero locks.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, Awaitable
from uuid import uuid4

from loguru import logger as log

# Human-readable logging for traders
from bot.utils.human_logger import human_log


@dataclass
class Message:
    """
    Actor message with type, payload, and optional reply channel.
    
    Attributes:
        type: Message type for routing
        payload: Message data
        reply_to: Optional queue for reply
        correlation_id: Unique ID for message tracing
    """
    
    type: str
    payload: Dict[str, Any]
    reply_to: Optional[asyncio.Queue] = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))


class Actor:
    """
    Base Actor class with mailbox for message-passing concurrency.
    
    Features:
    - Single-threaded execution (no locks needed)
    - Async message processing
    - Automatic message routing
    - Graceful shutdown
    - Error isolation
    """
    
    def __init__(self, name: str, mailbox_size: int = 1000):
        """
        Initialize actor.
        
        Args:
            name: Actor name for logging
            mailbox_size: Maximum mailbox queue size
        """
        self.name = name
        self._mailbox_size = mailbox_size
        self.mailbox: Optional[asyncio.Queue] = None  # Created in start()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._processed_count = 0
        self._error_count = 0
        
        # Message processing metrics
        self._last_message_time = 0
        self._processing_times: list[float] = []
        self._max_processing_times = 100  # Keep last 100 for metrics
    
    async def start(self) -> None:
        """
        Start actor message loop.
        
        This runs in a separate task and processes messages sequentially.
        """
        if self._running:
            log.warning(f"[{self.name}] Already running")
            return
        
        # Create mailbox within running event loop
        if self.mailbox is None:
            self.mailbox = asyncio.Queue(maxsize=self._mailbox_size)
        
        log.info(f"[{self.name}] Starting actor")
        self._running = True
        self._task = asyncio.create_task(self._run())
    
    async def stop(self, timeout: float = 5.0) -> None:
        """
        Gracefully stop actor.
        
        Args:
            timeout: Maximum time to wait for remaining messages
        """
        if not self._running:
            log.warning(f"[{self.name}] Not running")
            return
        
        log.info(f"[{self.name}] Stopping actor...")
        self._running = False
        
        # Process remaining messages with timeout
        try:
            await asyncio.wait_for(self._drain_mailbox(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning(f"[{self.name}] Timeout draining mailbox - {self.mailbox.qsize()} messages lost")
        
        # Cancel task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        log.info(f"[{self.name}] Stopped - processed {self._processed_count} messages, {self._error_count} errors")
    
    async def send(self, message: Message) -> None:
        try:
            await asyncio.wait_for(self.mailbox.put(message), timeout=0.1)
        except asyncio.TimeoutError:
            if self.mailbox.full():
                try:
                    dropped = self.mailbox.get_nowait()
                    log.warning(f"[{self.name}] Mailbox full - dropped oldest message {dropped.type}")
                except:
                    pass
                
                try:
                    self.mailbox.put_nowait(message)
                except:
                    log.error(f"[{self.name}] Failed to add message after drop - message {message.type} lost")
        except Exception as e:
            log.error(f"[{self.name}] Error sending message: {e}")
    
    async def tell(self, type: str, payload: Dict[str, Any]) -> None:
        """
        Send message without waiting for reply (fire-and-forget pattern).
        
        Args:
            type: Message type
            payload: Message payload
        """
        message = Message(type=type, payload=payload, reply_to=None)
        await self.send(message)
    
    async def ask(self, type: str, payload: Dict[str, Any], timeout: float = 5.0) -> Any:
        """
        Send message and wait for reply (request-response pattern).
        
        Args:
            type: Message type
            payload: Message payload
            timeout: Reply timeout
            
        Returns:
            Reply from actor
            
        Raises:
            asyncio.TimeoutError: If no reply within timeout
        """
        # Create reply queue within running event loop
        reply_queue = asyncio.Queue(maxsize=1)
        message = Message(type=type, payload=payload, reply_to=reply_queue)
        
        await self.send(message)
        
        try:
            reply = await asyncio.wait_for(reply_queue.get(), timeout=timeout)
            return reply
        except asyncio.TimeoutError:
            log.error(f"[{self.name}] Timeout waiting for reply to {type}")
            raise
    
    async def _run(self) -> None:
        """Main actor loop - process messages sequentially."""
        log.info(f"[{self.name}] Message loop started")
        
        while self._running:
            try:
                # Get message with timeout to allow periodic checks
                message = await asyncio.wait_for(
                    self.mailbox.get(),
                    timeout=1.0
                )
                
                # Process message
                start_time = asyncio.get_event_loop().time()
                await self._handle_message(message)
                
                # Track metrics
                processing_time = asyncio.get_event_loop().time() - start_time
                self._processing_times.append(processing_time)
                if len(self._processing_times) > self._max_processing_times:
                    self._processing_times.pop(0)
                
                self._processed_count += 1
                
                # Log slow messages
                if processing_time > 0.1:
                    log.warning(f"[{self.name}] Slow message processing: {message.type} took {processing_time:.3f}s")
                    human_log.slow_operation(f"{self.name} {message.type}", processing_time)  # Human-readable
            
            except asyncio.TimeoutError:
                # No message - continue loop
                continue
            
            except asyncio.CancelledError:
                log.info(f"[{self.name}] Message loop cancelled")
                break
            
            except Exception as e:
                log.error(f"[{self.name}] Error in message loop: {e}")
                self._error_count += 1
                # Continue processing despite errors
        
        log.info(f"[{self.name}] Message loop ended")
    
    async def _handle_message(self, msg: Message) -> None:
        """
        Route message to handler method.
        
        Args:
            msg: Message to handle
        """
        try:
            # Find handler method
            handler_name = f"_handle_{msg.type.lower().replace('-', '_')}"
            
            if handler := getattr(self, handler_name, None):
                # Only log GET_METRICS and GET_STATE occasionally (every 60 seconds) to reduce spam
                should_log = msg.type not in ["GET_METRICS", "GET_STATE"] or (time.time() - getattr(self, f'_last_{msg.type.lower()}_log', 0) > 60)
                
                if should_log:
                    log.debug(f"[{self.name}] Processing {msg.type} (correlation_id={msg.correlation_id})")
                    if msg.type in ["GET_METRICS", "GET_STATE"]:
                        setattr(self, f'_last_{msg.type.lower()}_log', time.time())
                
                # Call handler
                result = await handler(msg.payload, msg.reply_to, msg.correlation_id)
                
                # Send reply if requested and handler didn't already reply
                if msg.reply_to and result is not None:
                    try:
                        await msg.reply_to.put(result)
                    except asyncio.QueueFull:
                        log.error(f"[{self.name}] Reply queue full for {msg.type}")
            else:
                log.warning(f"[{self.name}] No handler for message type: {msg.type}")
                
                # Send error reply if requested
                if msg.reply_to:
                    try:
                        await msg.reply_to.put({
                            "status": "error",
                            "error": f"No handler for message type: {msg.type}"
                        })
                    except asyncio.QueueFull:
                        pass
        
        except Exception as e:
            log.error(f"[{self.name}] Error handling {msg.type}: {e}", exc_info=True)
            self._error_count += 1
            
            # Send error reply if requested
            if msg.reply_to:
                try:
                    await msg.reply_to.put({
                        "status": "error",
                        "error": str(e)
                    })
                except asyncio.QueueFull:
                    pass
    
    async def _drain_mailbox(self) -> None:
        """Process remaining messages in mailbox."""
        log.info(f"[{self.name}] Draining {self.mailbox.qsize()} messages from mailbox")
        
        while not self.mailbox.empty():
            try:
                message = self.mailbox.get_nowait()
                await self._handle_message(message)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                log.error(f"[{self.name}] Error draining mailbox: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get actor metrics.
        
        Returns:
            Dict with performance metrics
        """
        avg_processing_time = (
            sum(self._processing_times) / len(self._processing_times)
            if self._processing_times else 0
        )
        
        max_processing_time = max(self._processing_times) if self._processing_times else 0
        
        return {
            "name": self.name,
            "running": self._running,
            "mailbox_size": self.mailbox.qsize(),
            "mailbox_capacity": self.mailbox.maxsize,
            "processed_count": self._processed_count,
            "error_count": self._error_count,
            "avg_processing_time_ms": avg_processing_time * 1000,
            "max_processing_time_ms": max_processing_time * 1000,
            "error_rate": self._error_count / max(self._processed_count, 1)
        }


class SupervisorActor(Actor):
    """
    Supervisor actor for managing child actors.
    
    Implements supervision strategies:
    - Restart on failure
    - Escalate critical errors
    - Monitor child health
    """
    
    def __init__(self, name: str):
        """
        Initialize supervisor.
        
        Args:
            name: Supervisor name
        """
        super().__init__(name)
        self._children: Dict[str, Actor] = {}
        self._restart_counts: Dict[str, int] = {}
        self._max_restarts = 3
    
    async def add_child(self, child: Actor) -> None:
        """
        Add child actor to supervision.
        
        Args:
            child: Child actor to supervise
        """
        self._children[child.name] = child
        self._restart_counts[child.name] = 0
        
        # Start child
        await child.start()
        log.info(f"[{self.name}] Added child actor: {child.name}")
    
    async def remove_child(self, child_name: str) -> None:
        """
        Remove child from supervision.
        
        Args:
            child_name: Name of child to remove
        """
        if child := self._children.get(child_name):
            await child.stop()
            del self._children[child_name]
            del self._restart_counts[child_name]
            log.info(f"[{self.name}] Removed child actor: {child_name}")
    
    async def _handle_supervise(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Handle supervision check.
        
        Args:
            payload: Empty
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Status of all children
        """
        statuses = {}
        
        for name, child in self._children.items():
            statuses[name] = {
                "running": child._running,
                "metrics": child.get_metrics(),
                "restart_count": self._restart_counts[name]
            }
        
        return {"children": statuses}
    
    async def _handle_restart_child(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """
        Restart child actor.
        
        Args:
            payload: Dict with child_name
            reply_to: Reply queue
            correlation_id: Message correlation ID
            
        Returns:
            Restart status
        """
        child_name = payload["child_name"]
        
        if child := self._children.get(child_name):
            self._restart_counts[child_name] += 1
            
            if self._restart_counts[child_name] > self._max_restarts:
                log.error(f"[{self.name}] Child {child_name} exceeded max restarts")
                return {"status": "error", "error": "Max restarts exceeded"}
            
            log.info(f"[{self.name}] Restarting child {child_name} (attempt {self._restart_counts[child_name]})")
            
            # Stop child
            await child.stop()
            
            # Restart child
            await child.start()
            
            return {"status": "ok", "restart_count": self._restart_counts[child_name]}
        
        return {"status": "error", "error": f"Child {child_name} not found"}
