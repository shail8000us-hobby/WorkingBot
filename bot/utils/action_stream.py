"""
Bot Action Stream - Real-time event logging for bot actions and intentions

This module provides a centralized event logging system that tracks:
- What the bot is doing right now
- What it plans to do next
- Why it made certain decisions
- Future actions based on conditions

Events are broadcast via WebSocket to the frontend for real-time display.
"""

import json
import time
import uuid
import queue
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import deque
import threading

# ✅ FIX #10: Proper logging instead of print()
logger = logging.getLogger("bot.action_stream")

class BotActionStream:
    """
    Singleton class for managing bot action events and broadcasting to subscribers
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the action stream"""
        if self._initialized:
            return
            
        self.events = deque(maxlen=1000)  # Keep last 1000 events in memory
        self._events_lock = threading.Lock()  # ✅ FIX #3: Thread-safe deque access
        self.socketio = None  # Will be set by Flask app
        self.log_file = "logs/bot_actions.jsonl"
        
        # ✅ FIX #5: Log rotation settings
        self.max_log_size = 10 * 1024 * 1024  # 10 MB per file
        self.max_rotated_files = 5  # Keep 5 old files (50 MB total)
        
        # ✅ FIX #2: Async file writer to prevent blocking trading thread
        self._write_queue = queue.Queue()
        
        # ✅ CRITICAL FIX: Initialize _shutdown BEFORE starting thread
        # Thread accesses self._shutdown immediately in while loop
        self._shutdown = False
        
        self._writer_thread = threading.Thread(
            target=self._background_file_writer,
            daemon=True,
            name="BotActionWriter"
        )
        self._writer_thread.start()
        
        self._initialized = True
        
    def set_socketio(self, socketio):
        """Set the SocketIO instance for broadcasting"""
        self.socketio = socketio
        
    def log_action(
        self,
        action_type: str,
        data: Dict[str, Any],
        future_intentions: Optional[Dict[str, str]] = None,
        importance: str = "normal"
    ):
        """
        Log a bot action with timestamp and optional future intentions
        
        Args:
            action_type: Type of action (e.g., 'bot_startup', 'volatility_halt', etc.)
            data: Action-specific data
            future_intentions: What the bot will do under different conditions
            importance: 'low', 'normal', 'high', 'critical'
        """
        event = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'unix_time': time.time(),
            'action_type': action_type,
            'data': data,
            'future_intentions': future_intentions or {},
            'importance': importance
        }
        
        # ✅ FIX #3: Thread-safe append to in-memory queue
        with self._events_lock:
            self.events.append(event)
        
        # Persist to file
        self._persist_event(event)
        
        # Broadcast to WebSocket subscribers
        self._broadcast_event(event)
        
        return event
    
    def _persist_event(self, event: Dict[str, Any]):
        """Enqueue event for async file write
        
        ✅ FIX #2: Non-blocking write - event queued for background thread
        Trading thread never waits for file I/O
        """
        try:
            self._write_queue.put_nowait(event)
        except queue.Full:
            # ✅ FIX #10: Proper logging with severity
            logger.warning("Write queue full, event may be dropped - consider increasing queue size")
        except Exception as e:
            logger.error(f"Error queuing event for persistence: {e}", exc_info=True)
    
    def _rotate_log_if_needed(self):
        """Rotate log file if it exceeds max size
        
        ✅ FIX #5: Automatic log rotation prevents disk exhaustion
        Rotates: bot_actions.jsonl → .jsonl.1 → .jsonl.2 etc.
        """
        try:
            if not os.path.exists(self.log_file):
                return
            
            file_size = os.path.getsize(self.log_file)
            if file_size < self.max_log_size:
                return
            
            # Rotate existing files: .5 gets deleted, .4→.5, .3→.4, etc.
            for i in range(self.max_rotated_files - 1, 0, -1):
                old_file = f"{self.log_file}.{i}"
                new_file = f"{self.log_file}.{i+1}"
                
                if i == self.max_rotated_files - 1 and os.path.exists(old_file):
                    os.remove(old_file)  # Delete oldest
                
                if os.path.exists(old_file):
                    os.rename(old_file, new_file)
            
            # Rotate current file to .1
            if os.path.exists(self.log_file):
                os.rename(self.log_file, f"{self.log_file}.1")
                # ✅ FIX #10: Proper info-level logging for rotation
                logger.info(f"Rotated bot_actions.jsonl (size: {file_size / 1024 / 1024:.1f} MB)")
                
        except Exception as e:
            # ✅ FIX #10: Error-level logging with stack trace
            logger.error(f"Error rotating log file: {e}", exc_info=True)
    
    def _background_file_writer(self):
        """Background thread that handles all file I/O
        
        ✅ FIX #2: Async writer - removes file I/O from hot path
        ✅ FIX #5: Includes automatic log rotation
        Runs in separate daemon thread, never blocks trading logic
        """
        import logging
        logger = logging.getLogger("action_stream_writer")
        
        event_count = 0
        
        while not self._shutdown:
            try:
                # Wait for event with timeout (allows shutdown check)
                try:
                    event = self._write_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # ✅ FIX #5: Check for rotation every 100 events
                event_count += 1
                if event_count % 100 == 0:
                    self._rotate_log_if_needed()
                
                # Write to file (blocking I/O happens here, not in trading thread)
                try:
                    with open(self.log_file, 'a') as f:
                        f.write(json.dumps(event) + '\n')
                except Exception as e:
                    logger.error(f"Error persisting event: {e}")
                finally:
                    self._write_queue.task_done()
                    
            except Exception as e:
                logger.error(f"Error in background writer: {e}")
        
        # Flush remaining events on shutdown
        while not self._write_queue.empty():
            try:
                event = self._write_queue.get_nowait()
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(event) + '\n')
            except Exception:
                pass
    
    def _broadcast_event(self, event: Dict[str, Any]):
        """Broadcast event to WebSocket subscribers
        
        ✅ FIX #1: Removed namespace parameter - emit to default namespace
        Frontend connects to default namespace, so events must be emitted there
        """
        if self.socketio:
            try:
                self.socketio.emit('bot_action', event)  # ✅ No namespace - use default
            except Exception as e:
                # ✅ FIX #10: Proper error logging for broadcast failures
                logger.error(f"Error broadcasting event to WebSocket: {e}", exc_info=True)
    
    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events from memory
        
        ✅ FIX #3: Thread-safe read from deque
        """
        with self._events_lock:
            events_list = list(self.events)
        return events_list[-limit:] if len(events_list) > limit else events_list
    
    def load_events_from_file(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Load recent events from file"""
        events = []
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        events.append(json.loads(line.strip()))
                    except:
                        continue
        except FileNotFoundError:
            logger.debug(f"No existing bot_actions.jsonl file found")
        except Exception as e:
            # ✅ FIX #10: Proper error logging
            logger.error(f"Error loading events from file: {e}", exc_info=True)
        
        return events
    
    def clear_events(self):
        """Clear in-memory events (file remains)
        
        ✅ FIX #3: Thread-safe clear
        """
        with self._events_lock:
            self.events.clear()
    
    def shutdown(self):
        """
        Gracefully shutdown the action stream
        
        Stops background writer thread and flushes pending events
        """
        if not hasattr(self, '_shutdown'):
            return
            
        logger.info("Shutting down action stream...")
        self._shutdown = True
        
        # Wait for writer thread to finish
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=5)
        
        logger.info("Action stream shutdown complete")


# Global singleton instance
action_stream = BotActionStream()


# Helper functions for common event types

def log_bot_startup(grid_config: Dict[str, Any]):
    """Log bot startup with grid configuration"""
    action_stream.log_action(
        action_type='bot_startup',
        data={
            'grid_lower': grid_config.get('lower'),
            'grid_upper': grid_config.get('upper'),
            'grid_step': grid_config.get('step'),
            'grid_ref': grid_config.get('ref'),
            'max_open': grid_config.get('max_open'),
            'lot_size': grid_config.get('lot'),
            'mode': grid_config.get('mode', 'LIVE')
        },
        future_intentions={
            'next_action': f"Place BUY order at ${grid_config.get('ref', 0) - grid_config.get('step', 0):,.0f}",
            'condition': 'When price available and volatility safe'
        },
        importance='high'
    )


def log_volatility_halt(
    iv: float,
    rv: float,
    max_iv: float,
    max_rv: float,
    blocked_order_price: float,
    reason: str,
    current_price: float
):
    """Log volatility halt event"""
    action_stream.log_action(
        action_type='volatility_halt',
        data={
            'iv': round(iv, 2),
            'rv': round(rv, 2),
            'max_iv': max_iv,
            'max_rv': max_rv,
            'spread': round(iv - rv, 2),
            'blocked_order': blocked_order_price,
            'current_price': current_price,
            'reason': reason
        },
        future_intentions={
            'on_safe': f'Resume buying at ${blocked_order_price:,.0f}',
            'on_price_drop': 'Calculate and fill missed grid levels at market price',
            'monitoring': 'Checking volatility every 10 seconds',
            'strict_grid': 'Temporarily suspended during recovery'
        },
        importance='high'
    )


def log_price_update_during_halt(
    current_price: float,
    volatility_status: str,
    missed_levels: List[float],
    iv: float,
    rv: float
):
    """Log price movement while halted"""
    action_stream.log_action(
        action_type='price_update_during_halt',
        data={
            'current_price': current_price,
            'volatility_status': volatility_status,
            'iv': round(iv, 2),
            'rv': round(rv, 2),
            'missed_levels_count': len(missed_levels),
            'missed_levels': [round(p, 2) for p in missed_levels]
        },
        future_intentions={
            'if_safe_now': f'Place {len(missed_levels)} MARKET orders (ignore strict grid)' if missed_levels else 'Resume at saved level',
            'tp_targets': [round(level + 1000, 2) for level in missed_levels] if missed_levels else [],
            'note': 'Market orders will fill missed grid levels at better prices' if missed_levels else None
        },
        importance='normal' if len(missed_levels) < 3 else 'high'
    )


def log_recovery_start(
    current_price: float,
    missed_levels: List[float],
    iv: float,
    rv: float
):
    """Log start of opportunistic recovery"""
    action_stream.log_action(
        action_type='recovery_start',
        data={
            'current_price': current_price,
            'iv': round(iv, 2),
            'rv': round(rv, 2),
            'missed_levels_count': len(missed_levels),
            'missed_levels': [round(p, 2) for p in missed_levels],
            'action': 'Placing MARKET orders (ignoring strict grid temporarily)'
        },
        future_intentions={
            'next_step': 'Wait for fills and set TP orders',
            'after_recovery': 'Resume strict grid mode'
        },
        importance='critical'
    )


def log_recovery_complete(
    filled_positions: List[Dict[str, Any]],
    average_fill: float,
    total_extra_profit: float,
    next_buy_level: Optional[float]
):
    """Log completion of opportunistic recovery"""
    action_stream.log_action(
        action_type='recovery_complete',
        data={
            'positions_filled': len(filled_positions),
            'average_fill_price': round(average_fill, 2),
            'tp_targets': [round(p['tp_price'], 2) for p in filled_positions],
            'extra_profit_potential': round(total_extra_profit, 2),
            'positions': [
                {
                    'entry': round(p['actual_entry'], 2),
                    'tp': round(p['tp_price'], 2),
                    'profit_potential': round(p['tp_price'] - p['actual_entry'], 2)
                }
                for p in filled_positions
            ]
        },
        future_intentions={
            'next_action': f'Resume strict grid - Place BUY at ${next_buy_level:,.0f}' if next_buy_level else 'Monitor for next opportunity',
            'strict_grid': 'Now ACTIVE - orders placed below current price',
            'monitoring': 'Watching for TP fills and new grid opportunities'
        },
        importance='critical'
    )


def log_order_placed(
    order_type: str,
    side: str,
    price: float,
    size: int,
    order_id: str,
    reason: str = "Grid trading"
):
    """Log order placement"""
    action_stream.log_action(
        action_type='order_placed',
        data={
            'order_type': order_type,
            'side': side,
            'price': round(price, 2),
            'size': size,
            'order_id': order_id,
            'reason': reason
        },
        future_intentions={
            'on_fill': f'Place TP order at ${price + 1000:,.0f}' if side == 'buy' else 'Position closed',
            'monitoring': 'Watching for fill via WebSocket'
        },
        importance='normal'
    )


def log_order_filled(
    order_type: str,
    side: str,
    fill_price: float,
    size: int,
    order_id: str,
    profit: Optional[float] = None
):
    """Log order fill"""
    action_stream.log_action(
        action_type='order_filled',
        data={
            'order_type': order_type,
            'side': side,
            'fill_price': round(fill_price, 2),
            'size': size,
            'order_id': order_id,
            'profit': round(profit, 2) if profit else None
        },
        future_intentions={
            'next_action': f'Place new BUY order one step below' if side == 'sell' else f'Wait for TP fill',
            'grid_adjustment': 'Position count updated'
        },
        importance='high' if profit and profit > 500 else 'normal'
    )


def log_max_tranches_reached(current_count: int, max_allowed: int, blocked_price: float):
    """Log when max tranches limit is reached"""
    action_stream.log_action(
        action_type='max_tranches_reached',
        data={
            'current_tranches': current_count,
            'max_allowed': max_allowed,
            'blocked_price': blocked_price,
            'utilization_pct': round((current_count / max_allowed) * 100, 1)
        },
        future_intentions={
            'wait_for': 'Any existing position to close (TP fill)',
            'then': f'Place BUY order at ${blocked_price:,.0f}',
            'queue_status': f'{current_count}/{max_allowed} slots used'
        },
        importance='normal'
    )


def log_emergency_stop(reason: str, active_positions: int, pending_orders: int):
    """Log emergency trading halt"""
    action_stream.log_action(
        action_type='emergency_stop',
        data={
            'reason': reason,
            'active_positions': active_positions,
            'pending_orders': pending_orders,
            'timestamp': datetime.now().isoformat()
        },
        future_intentions={
            'action': 'ALL new orders blocked',
            'positions': 'Existing positions kept with TP orders',
            'recovery': 'Manual intervention required - remove .bot_shutdown file'
        },
        importance='critical'
    )


def log_gatekeeper_block(block_reason: str, attempted_action: str, context: Dict[str, Any]):
    """Log when safety gatekeeper blocks an action"""
    action_stream.log_action(
        action_type='gatekeeper_block',
        data={
            'block_reason': block_reason,
            'attempted_action': attempted_action,
            'price': context.get('price'),
            'side': context.get('side', 'BUY'),
            'details': context
        },
        future_intentions={
            'waiting_for': f'Safety condition to resolve: {block_reason}',
            'check_status': 'View Safety Gatekeeper panel for details',
            'auto_retry': 'Bot will retry when conditions normalize'
        },
        importance='high'
    )


def log_margin_block(margin_util: float, margin_limit: float, blocked_price: float):
    """Log when order is blocked due to high margin utilization"""
    action_stream.log_action(
        action_type='margin_block',
        data={
            'margin_utilization': round(margin_util, 1),
            'margin_limit': round(margin_limit, 1),
            'blocked_price': blocked_price,
            'over_limit_by': round(margin_util - margin_limit, 1)
        },
        future_intentions={
            'action': 'Block new BUY orders until margin reduces',
            'allow': 'TP/SELL orders still active (reduce exposure)',
            'recommendation': 'Close some positions or add margin to account'
        },
        importance='high'
    )


def log_liquidation_warning(
    distance_zone: str,
    margin_util: float,
    blocked_price: float,
    distance_pct: Optional[float] = None
):
    """Log liquidation protection warning"""
    action_stream.log_action(
        action_type='liquidation_warning',
        data={
            'distance_zone': distance_zone,
            'margin_utilization': round(margin_util, 1),
            'blocked_price': blocked_price,
            'liquidation_distance_pct': round(distance_pct, 1) if distance_pct else None
        },
        future_intentions={
            'protection': 'Blocking new BUY orders - too close to liquidation',
            'allow': 'TP orders active to reduce risk',
            'auto_action': 'May emergency close positions if DANGER persists'
        },
        importance='critical'
    )


def log_outside_grid(current_price: float, grid_upper: float, grid_lower: float):
    """Log when price moves outside grid boundaries"""
    action_stream.log_action(
        action_type='outside_grid',
        data={
            'current_price': current_price,
            'grid_upper': grid_upper,
            'grid_lower': grid_lower,
            'distance_from_grid': abs(current_price - grid_upper) if current_price > grid_upper else abs(grid_lower - current_price)
        },
        future_intentions={
            'if_returns': f'Resume grid trading when price returns to ${grid_lower:,.0f} - ${grid_upper:,.0f}',
            'current_strategy': 'Hold existing positions with TP orders',
            'no_new_buys': 'Waiting for price to re-enter grid'
        },
        importance='normal'
    )


def log_order_rejected(
    reason: str,
    price: float,
    side: str,
    exchange_error: Optional[str] = None
):
    """Log when exchange rejects an order"""
    action_stream.log_action(
        action_type='order_rejected',
        data={
            'reject_reason': reason,
            'price': price,
            'side': side,
            'exchange_error': exchange_error
        },
        future_intentions={
            'retry': 'Will retry on next price tick' if 'insufficient' not in reason.lower() else 'Need to add funds',
            'check': 'Review order parameters and account status'
        },
        importance='high'
    )


def log_tp_placement_failed(
    entry_price: float,
    tp_price: float,
    position_size: int,
    error_reason: Optional[str] = None
):
    """Log CRITICAL failure to place TP order - position is unprotected"""
    action_stream.log_action(
        action_type='tp_placement_failed',
        data={
            'entry_price': entry_price,
            'tp_price': tp_price,
            'position_size': position_size,
            'error_reason': error_reason or 'Unknown error',
            'risk_exposure': 'UNPROTECTED POSITION'
        },
        future_intentions={
            'manual_action': '🚨 URGENT: Manually place TP order or close position',
            'risk': 'Position has no stop-loss protection',
            'recommended_tp': f'Place SELL order at ${tp_price:,.0f}'
        },
        importance='critical'
    )


# ============================================================================
# Singleton Accessor Function
# ============================================================================

def get_action_stream() -> BotActionStream:
    """
    Get the global BotActionStream instance
    
    Returns:
        BotActionStream: The singleton action stream instance
    """
    return action_stream
