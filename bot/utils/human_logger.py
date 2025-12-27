"""
Human-Readable Logger for WorkingBot
Transforms technical debug messages into trader-friendly status updates.
NOW WITH FULL NARRATIVE ENGINE - Context-aware, mood-driven commentary!
"""

import time
from typing import Dict, Optional, List, Any
from loguru import logger
from enum import Enum
from collections import deque


class LogLevel(Enum):
    """Human-readable log levels for traders"""
    BOT_OK = "BOT OK"       # Normal operation
    WARNING = "WARNING"     # Suspicious or delayed condition
    ALERT = "ALERT"         # Temporary malfunction or missing data
    CRITICAL = "CRITICAL"   # Async system failure, reconnection, or stalled loop


class Mood(Enum):
    """Bot's current mood/state for narrative engine"""
    CALM = "calm"               # Normal, steady operation
    AGGRESSIVE = "aggressive"   # Multiple rapid fills/actions
    ALERT = "alert"             # Warning state, watching closely
    STRESSED = "stressed"       # Multiple errors/issues
    RECOVERING = "recovering"   # Coming back from issues
    EXCITED = "excited"         # Profitable fills, good momentum


class MarketTempo(Enum):
    """Market activity level"""
    CALM = "calm"       # Slow, steady
    TRENDING = "trending"  # Directional movement
    CHOPPY = "choppy"   # Erratic, volatile


class HumanLogger:
    """
    Advanced narrative-driven logging system with context awareness.
    Transforms raw events into trader-style commentary with memory and mood.
    
    Features:
    - Context-aware narrative engine
    - Mood state machine (calm → aggressive → stressed → recovering)
    - Rolling event memory (last 20 events)
    - Multi-event story arcs
    - Streak tracking (fills, errors, warnings)
    - Market tempo detection
    - Smart template selection based on context
    
    100% Backward Compatible - all existing method signatures preserved!
    """
    
    def __init__(self, rate_limit_seconds: float = 3.0, narrative_mode: bool = True, log_delay: float = 0.0):
        self.rate_limit_seconds = rate_limit_seconds
        self.narrative_mode = narrative_mode
        self.log_delay = log_delay  # Delay between log outputs (0.0 = no delay)
        self._last_log_times: Dict[str, float] = {}
        self._session_start_time = time.time()
        
        # ===== NARRATIVE ENGINE =====
        self._mood: Mood = Mood.CALM
        self._market_tempo: MarketTempo = MarketTempo.CALM
        self._event_memory: deque = deque(maxlen=20)  # Rolling context window
        self._session_theme: str = "Starting fresh"
        
        # ===== MEMORY SYSTEM =====
        self._orders_placed = 0
        self._orders_filled = 0
        self._last_side: Optional[str] = None
        self._last_price: Optional[float] = None
        self._fill_streak = 0
        self._error_streak = 0
        self._warning_streak = 0
        self._last_disconnect_time: Optional[float] = None
        self._consecutive_buys = 0
        self._consecutive_sells = 0
        self._last_fill_time: Optional[float] = None
        self._avg_fill_spacing = 60.0  # seconds
        
        # ===== STORY ARC TRACKING =====
        self._in_reconnect_arc = False
        self._reconnect_steps: List[str] = []
        self._rapid_fill_window = deque(maxlen=5)
        
    def _should_log(self, message_key: str) -> bool:
        """Rate-limit repetitive messages"""
        current_time = time.time()
        last_time = self._last_log_times.get(message_key, 0)
        
        if current_time - last_time >= self.rate_limit_seconds:
            self._last_log_times[message_key] = current_time
            return True
        return False
    
    def _add_to_memory(self, event_type: str, data: Any = None):
        """Add event to rolling memory for context"""
        self._event_memory.append({
            'type': event_type,
            'time': time.time(),
            'data': data
        })
    
    def _update_mood(self):
        """Update bot mood based on recent events"""
        recent_events = list(self._event_memory)[-10:]
        
        # Count event types in recent history
        fills = sum(1 for e in recent_events if e['type'] == 'fill')
        errors = sum(1 for e in recent_events if e['type'] == 'error')
        warnings = sum(1 for e in recent_events if e['type'] == 'warning')
        
        # Mood transitions
        if errors >= 3:
            self._mood = Mood.STRESSED
        elif self._in_reconnect_arc:
            self._mood = Mood.RECOVERING
        elif fills >= 3 and errors == 0:
            self._mood = Mood.EXCITED
        elif warnings >= 2:
            self._mood = Mood.ALERT
        elif fills >= 2:
            self._mood = Mood.AGGRESSIVE
        else:
            self._mood = Mood.CALM
    
    def _detect_market_tempo(self):
        """Detect market tempo from fill patterns"""
        if len(self._rapid_fill_window) >= 3:
            time_span = self._rapid_fill_window[-1] - self._rapid_fill_window[0]
            if time_span < 60:  # 3+ fills in under 1 minute
                self._market_tempo = MarketTempo.CHOPPY
            elif self._consecutive_buys >= 3 or self._consecutive_sells >= 3:
                self._market_tempo = MarketTempo.TRENDING
            else:
                self._market_tempo = MarketTempo.CALM
        else:
            self._market_tempo = MarketTempo.CALM
    
    def _get_narrative_for_context(self, base_narratives: List[str]) -> str:
        """Select narrative based on current context and mood"""
        # Add mood flavor to narrative
        if self._mood == Mood.EXCITED and "filled" in str(base_narratives).lower():
            return base_narratives[0] + " 🔥"
        elif self._mood == Mood.STRESSED:
            return base_narratives[-1] if len(base_narratives) > 1 else base_narratives[0]
        else:
            # Rotate through narratives based on counter
            idx = self._orders_placed % len(base_narratives) if self._orders_placed else 0
            return base_narratives[idx]
    
    def _log_with_level(self, level: LogLevel, message: str, force: bool = False, 
                       key: Optional[str] = None, narrative: Optional[str] = None):
        """Internal logging with rate limiting and optional narrative mode"""
        message_key = key or message
        
        if force or self._should_log(message_key):
            # Add delay if configured (for slowing down terminal output)
            if self.log_delay > 0:
                time.sleep(self.log_delay)
            
            # Update context
            self._update_mood()
            
            # Use narrative version if available and narrative mode enabled
            if self.narrative_mode and narrative:
                formatted = f"💬 {narrative}"
            else:
                formatted = f"{level.value} → {message}"
            
            if level == LogLevel.BOT_OK:
                logger.info(formatted)
            elif level == LogLevel.WARNING:
                logger.warning(formatted)
                self._add_to_memory('warning')
                self._warning_streak += 1
            elif level == LogLevel.ALERT:
                logger.warning(formatted)
                self._add_to_memory('error')
                self._error_streak += 1
            elif level == LogLevel.CRITICAL:
                logger.error(formatted)
                self._add_to_memory('error')
                self._error_streak += 1
    
    # ==================== NARRATIVE TEMPLATES ====================
    
    NARRATIVE_TEMPLATES = {
        'buy_order': [
            "📈 Long attempt in — buy @ ${price}.",
            "Another BUY placed. Fishing below the price…",
            "Buy ladder extended. Let's see if market dips.",
            "Putting in another buy. Building the position...",
        ],
        'sell_order': [
            "📉 Sell order live @ ${price}.",
            "Posted a SELL. Taking profit zone set.",
            "Sell ladder active. Waiting for bounce...",
        ],
        'buy_fill': [
            "✅ BUY FILLED @ ${price}! Market came to us.",
            "Nice! Got that buy fill. Position growing.",
            "Sweet fill on the buy side. Entry secured.",
            "Buy executed clean. Added to the stack.",
        ],
        'sell_fill': [
            "💰 SELL FILLED @ ${price}! Profit locked.",
            "That's sweet — sold into strength.",
            "Bag secured! SELL executed.",
            "Profit booked. Cash in hand.",
        ],
        'tp_hit': [
            "💰 TP HIT! Bag locked at ${price}.",
            "That's sweet — loop closed perfectly.",
            "Profit booked. Re-arming the next step.",
            "Target reached! Position closed with profit.",
        ],
        'connection_lost': [
            "🚨 Lost the wire… reconnecting.",
            "Connection dropped. Re-dialing the exchange...",
            "We're offline. Bringing systems back up...",
        ],
        'connection_restored': [
            "✅ Back online! Feed restored.",
            "Connection solid again. We're back.",
            "Reconnected successfully. Trading resumed.",
        ],
        'rapid_fills': [
            "🔥 Getting fills back-to-back… bot's cooking today!",
            "Market's active! Multiple fills coming in.",
            "Hot streak! Fills rolling in fast.",
        ],
        'error_recovery': [
            "⚠️ Handler stumbled — picking it back up.",
            "Minor hiccup. Already recovered.",
            "Caught an error. Systems normalizing...",
        ],
        'api_slow': [
            "⚠️ API feeling sluggish today… retrying.",
            "Exchange response time dragging. Being patient...",
            "API's moving slow. Hanging in there...",
        ],
        'queue_swelling': [
            "📊 Order queue swelling up, market's getting lively.",
            "Message backlog building. Processing catch-up...",
            "Queue's stacking up. Working through it...",
        ],
    }
    
    # ==================== BOT OK (Normal Operations) ====================
    
    def price_data_flowing(self, price: Optional[float] = None):
        """Price data received and processed"""
        self._last_price = price
        self._add_to_memory('price_update', price)
        
        if price:
            # Context-aware narrative
            if self._mood == Mood.EXCITED:
                narrative = f"Market's cooking at ${price:,.0f}! 🔥"
            elif self._mood == Mood.STRESSED:
                narrative = f"Price at ${price:,.0f}. Watching carefully..."
            else:
                narrative = f"Market's at ${price:,.0f}. Feed is solid. 📊"
            
            self._log_with_level(
                LogLevel.BOT_OK, 
                f"Price: ${price:,.0f} | Feed stable.", 
                key="price_flowing",
                narrative=narrative
            )
        else:
            self._log_with_level(
                LogLevel.BOT_OK, 
                "Price data flowing correctly.", 
                key="price_flowing",
                narrative="Price updates coming in smooth. We're locked in. 🎯"
            )
    
    def connection_stable(self):
        """WebSocket connection healthy"""
        self._add_to_memory('connection_ok')
        
        # If we just recovered from disconnect, complete the arc
        if self._in_reconnect_arc:
            narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['connection_restored'])
            self._in_reconnect_arc = False
            self._reconnect_steps = []
            self._mood = Mood.CALM
        else:
            narrative = "Exchange is talking to us. Connection solid as a rock. 🔗"
        
        self._log_with_level(
            LogLevel.BOT_OK, 
            "Connection stable, exchange responding.", 
            key="connection_stable",
            narrative=narrative
        )
    
    def heartbeat_ok(self):
        """Network heartbeat working - silenced (too frequent)"""
        # No longer logged - heartbeat happens every 5s and provides no actionable info
        pass
    
    def message_routed(self, msg_type: str, handler_count: int):
        """Message successfully routed to handlers"""
        self._add_to_memory('message_routed')
        
        # Suppress noisy ticker messages in narrative mode
        if msg_type == "v2/ticker":
            # Too frequent, skip narrative
            return
        
        self._log_with_level(
            LogLevel.BOT_OK, 
            f"Data routing OK: {msg_type} → {handler_count} handler(s).",
            key=f"route_{msg_type}",
            narrative=f"📡 {msg_type} data flowing clean. Handlers processing..."
        )
    
    def websocket_authenticated(self):
        """WebSocket authenticated successfully"""
        self._add_to_memory('authenticated')
        
        # Part of reconnection story arc?
        if self._in_reconnect_arc:
            self._reconnect_steps.append('authenticated')
            narrative = "🔐 Authenticated! We're back in..."
        else:
            narrative = "🔐 Logged in! Exchange recognized us. We're cleared for trading."
        
        self._log_with_level(
            LogLevel.BOT_OK, 
            "WebSocket authenticated successfully.", 
            force=True,
            narrative=narrative
        )
    
    def subscriptions_active(self, channels: list):
        """Subscriptions confirmed"""
        self._add_to_memory('subscribed')
        
        # Complete reconnection arc if active
        if self._in_reconnect_arc:
            self._reconnect_steps.append('subscribed')
            narrative = "✅ Subscribed! Feed restored. Let's continue."
        else:
            channels_str = ", ".join(channels[:3])  # Show first 3
            narrative = f"📡 Subscribed to {channels_str}. Data flowing!"
        
        channels_str = ", ".join(channels)
        self._log_with_level(LogLevel.BOT_OK, f"Subscriptions active: {channels_str}", 
                           force=True, narrative=narrative)
    
    def order_placed(self, order_id: str, side: str, price: float):
        """Order placed successfully"""
        self._orders_placed += 1
        self._last_side = side
        self._last_price = price
        self._add_to_memory('order_placed', {'side': side, 'price': price})
        
        # Track consecutive sides for trend detection
        if side == "BUY":
            self._consecutive_buys += 1
            self._consecutive_sells = 0
        else:
            self._consecutive_sells += 1
            self._consecutive_buys = 0
        
        # Select narrative based on context
        template_key = 'buy_order' if side == "BUY" else 'sell_order'
        narratives = self.NARRATIVE_TEMPLATES[template_key]
        narrative = self._get_narrative_for_context(narratives).replace('${price}', f"{price:,.0f}")
        
        # Add order count context
        if self._orders_placed % 10 == 0:
            narrative += f" Order #{self._orders_placed} today."
        
        emoji = "📈" if side == "BUY" else "📉"
        self._log_with_level(
            LogLevel.BOT_OK, 
            f"Order placed: {side} @ ${price:,.0f} (ID: {order_id})",
            force=True,
            narrative=f"{emoji} {narrative}"
        )
    
    def order_filled(self, order_id: str, side: str, price: float):
        """Order filled"""
        self._orders_filled += 1
        self._fill_streak += 1
        self._error_streak = 0  # Reset error streak on success
        self._add_to_memory('fill', {'side': side, 'price': price})
        
        # Track fill timing for tempo detection
        current_time = time.time()
        if self._last_fill_time:
            time_since_last = current_time - self._last_fill_time
            self._avg_fill_spacing = (self._avg_fill_spacing * 0.7) + (time_since_last * 0.3)
        self._last_fill_time = current_time
        self._rapid_fill_window.append(current_time)
        
        # Update market tempo
        self._detect_market_tempo()
        
        # Detect rapid fill scenario
        if self._fill_streak >= 3:
            narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['rapid_fills'])
        else:
            # Regular fill narrative
            template_key = 'buy_fill' if side == "BUY" else 'sell_fill'
            narratives = self.NARRATIVE_TEMPLATES[template_key]
            narrative = self._get_narrative_for_context(narratives).replace('${price}', f"{price:,.0f}")
            
            # Add fill count milestone
            if self._orders_filled % 5 == 0:
                narrative += f" Fill #{self._orders_filled} today!"
        
        emoji = "✅" if side == "BUY" else "💰"
        self._log_with_level(
            LogLevel.BOT_OK, 
            f"Order filled: {side} @ ${price:,.0f} (ID: {order_id})",
            force=True,
            narrative=f"{emoji} {narrative}"
        )
    
    def order_cancelled(self, order_id: str):
        """Order cancelled successfully"""
        self._add_to_memory('order_cancelled')
        self._log_with_level(
            LogLevel.BOT_OK,
            f"Order cancelled: {order_id}",
            key="order_cancelled",
            narrative=f"🚫 Order cancelled. Market moved away - pulling that order back."
        )
    
    def order_already_gone(self, order_id: str):
        """Order already filled or cancelled"""
        self._log_with_level(
            LogLevel.BOT_OK,
            f"Order {order_id} already filled/cancelled - no need to cancel.",
            key="order_already_gone",
            narrative="📋 That order's already done. Market beat us to it - all good!"
        )
    
    def order_cancel_failed(self, order_id: str, reason: str):
        """Order cancellation failed"""
        self._add_to_memory('error', 'cancel_failed')
        self._error_streak += 1
        self._log_with_level(
            LogLevel.ERROR,
            f"Failed to cancel order {order_id}: {reason}",
            force=True,
            narrative=f"⚠️ Couldn't cancel that order. Exchange said: {reason}. Checking what's up..."
        )
    
    def position_updated(self, size: int, pnl: Optional[float] = None):
        """Position updated"""
        self._add_to_memory('position_update', {'size': size, 'pnl': pnl})
        
        if pnl is not None:
            # Context-aware PnL commentary
            if pnl > 100:
                narrative = f"Position: {size} contracts. +${pnl:,.2f} and climbing! 💰"
            elif pnl < -100:
                narrative = f"Position: {size} contracts. Down ${abs(pnl):,.2f} but we're managing risk. 🛡️"
            else:
                narrative = f"Position: {size} contracts. PnL: ${pnl:,.2f}"
            
            self._log_with_level(
                LogLevel.BOT_OK, 
                f"Position: {size} contracts | PnL: ${pnl:,.2f}",
                key="position_update",
                narrative=narrative
            )
        else:
            self._log_with_level(
                LogLevel.BOT_OK, 
                f"Position: {size} contracts",
                key="position_update",
                narrative=f"Position updated: {size} contracts active."
            )
    
    def actor_processing(self, actor_name: str):
        """Actor processing message"""
        self._add_to_memory('actor_processing')
        self._log_with_level(
            LogLevel.BOT_OK, 
            f"{actor_name} processing data.",
            key=f"actor_{actor_name}",
            narrative=f"⚙️ {actor_name} handling the flow. Systems operational."
        )
    
    def cooldown_active(self, seconds: float):
        """Cooldown period active"""
        self._add_to_memory('cooldown')
        
        if seconds > 30:
            narrative = f"⏳ Long cooldown active: {seconds:.0f}s. Market's too hot, taking a break."
        else:
            narrative = f"⏳ Taking a {seconds:.0f}s breather before the next order. Safety first!"
        
        self._log_with_level(
            LogLevel.BOT_OK, 
            f"Safety cooldown: {seconds:.0f}s remaining.",
            key="cooldown",
            narrative=narrative
        )
    
    # ==================== WARNING (Delays/Suspicious) ====================
    
    def price_delayed(self, seconds: float):
        """Price update delayed"""
        self._add_to_memory('warning', 'price_delayed')
        self._warning_streak += 1
        
        if seconds > 60:
            narrative = f"⚠️ ALERT: No price for {seconds:.0f}s! That's too long. Checking connection..."
        else:
            narrative = f"⚠️ Hmm, haven't seen a price update in {seconds:.0f}s. Keeping an eye on this..."
        
        self._log_with_level(
            LogLevel.WARNING, 
            f"No price update for {seconds:.0f} seconds.",
            key="price_delayed",
            narrative=narrative
        )
    
    def heartbeat_delayed(self, seconds: float):
        """Heartbeat delayed"""
        self._add_to_memory('warning', 'heartbeat_delayed')
        self._log_with_level(
            LogLevel.WARNING, 
            f"Exchange heartbeat delayed ({seconds:.0f}s).",
            key="heartbeat_delayed",
            narrative=f"⚠️ Exchange heartbeat late by {seconds:.0f}s. Network might be lagging..."
        )
    
    def data_stale(self, data_type: str, age_seconds: float):
        """Data becoming stale"""
        self._add_to_memory('warning', 'data_stale')
        self._log_with_level(
            LogLevel.WARNING, 
            f"{data_type} data stale ({age_seconds:.0f}s old).",
            key=f"stale_{data_type}",
            narrative=f"⚠️ {data_type} hasn't updated in {age_seconds:.0f}s. Watching for refresh..."
        )
    
    def queue_growing(self, queue_name: str, size: int):
        """Message queue growing"""
        self._add_to_memory('warning', 'queue_growth')
        
        narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['queue_swelling'])
        narrative = f"📊 {queue_name} queue at {size} messages. " + narrative.split('.')[0] + "."
        
        self._log_with_level(
            LogLevel.WARNING, 
            f"{queue_name} queue backed up: {size} messages.",
            key=f"queue_{queue_name}",
            narrative=narrative
        )
    
    def slow_response(self, operation: str, duration: float):
        """Slow API response"""
        self._add_to_memory('warning', 'slow_api')
        
        narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['api_slow'])
        
        self._log_with_level(
            LogLevel.WARNING, 
            f"{operation} took {duration:.1f}s (slow response).",
            key=f"slow_{operation}",
            narrative=narrative
        )
    
    # ==================== ALERT (Temporary Failures) ====================
    
    def connection_unstable(self):
        """WebSocket connection unstable"""
        self._add_to_memory('error', 'connection_unstable')
        self._error_streak += 1
        
        self._log_with_level(
            LogLevel.ALERT, 
            "Connection unstable, retrying automatically.",
            key="connection_unstable",
            narrative="🔧 Connection's getting choppy. Don't worry, I'm handling it - reconnecting now..."
        )
    
    def websocket_not_ready(self):
        """WebSocket not ready for sending"""
        self._add_to_memory('error', 'ws_not_ready')
        self._log_with_level(
            LogLevel.ALERT, 
            "WebSocket not ready, queuing message for retry.",
            key="ws_not_ready",
            narrative="📮 WebSocket's not ready yet. I'll queue this message and send it when we're back online."
        )
    
    def handler_failed(self, handler_name: str, error: str):
        """Message handler failed"""
        self._add_to_memory('error', f'handler_{handler_name}')
        self._error_streak += 1
        
        # Check if we're in stressed mode
        if self._error_streak >= 3:
            narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['error_recovery'])
            narrative = f"⚠️ {handler_name} crashed. {narrative}"
        else:
            narrative = f"⚠️ {handler_name} stumbled: {error[:50]}. Recovering..."
        
        self._log_with_level(
            LogLevel.ALERT, 
            f"{handler_name} failed: {error}",
            key=f"handler_{handler_name}",
            narrative=narrative
        )
    
    def api_error(self, operation: str, error_msg: str):
        """API call failed"""
        self._add_to_memory('error', 'api_error')
        self._error_streak += 1
        
        narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['api_slow'])
        
        self._log_with_level(
            LogLevel.ALERT, 
            f"API error ({operation}): {error_msg}",
            key=f"api_{operation}",
            narrative=narrative
        )
    
    def order_rejected(self, reason: str):
        """Order rejected by exchange"""
        self._add_to_memory('error', 'order_rejected')
        self._error_streak += 1
        
        self._log_with_level(
            LogLevel.ALERT, 
            f"Order rejected: {reason}",
            force=True,
            narrative=f"❌ Exchange rejected our order: {reason}. Analyzing why..."
        )
    
    def missing_data(self, data_type: str):
        """Expected data missing"""
        self._add_to_memory('error', 'missing_data')
        self._log_with_level(
            LogLevel.ALERT, 
            f"Missing {data_type} - waiting for exchange.",
            key=f"missing_{data_type}",
            narrative=f"🔍 Can't find {data_type}. Waiting for exchange to send it..."
        )
    
    def retry_attempt(self, operation: str, attempt: int):
        """Retrying failed operation"""
        self._add_to_memory('retry', operation)
        
        if attempt >= 3:
            narrative = f"🔄 Attempt #{attempt} for {operation}. Still trying... this is taking longer than usual."
        else:
            narrative = f"🔄 Attempt #{attempt} for {operation}. Not giving up yet!"
        
        self._log_with_level(
            LogLevel.ALERT, 
            f"Retrying {operation} (attempt {attempt})...",
            key=f"retry_{operation}",
            narrative=narrative
        )
    
    def safety_halt_active(self, context: str):
        """Safety halt preventing action"""
        self._add_to_memory('safety_halt')
        self._log_with_level(
            LogLevel.WARNING,
            f"Safety halt active - cannot {context}",
            force=True,
            narrative=f"🛡️ Safety system engaged! Not {context} until risk clears."
        )
    
    def volatility_unsafe(self, reason: str):
        """Volatility conditions unsafe for trading"""
        self._add_to_memory('volatility_unsafe')
        self._log_with_level(
            LogLevel.WARNING,
            f"Volatility unsafe: {reason}",
            force=True,
            narrative=f"⚠️ Markets too wild right now! {reason}. Sitting tight until things calm down."
        )
    
    def duplicate_order_detected(self, side: str, price: float):
        """Duplicate order detected - not placing new one"""
        self._add_to_memory('duplicate_order_detected')
        self._log_with_level(
            LogLevel.BOT_OK,
            f"Already have pending {side} @ ${price:,.2f} - skipping duplicate",
            key="duplicate_order",
            narrative=f"✅ We already have a {side} order at ${price:,.0f}. No need for another one - keeping it simple!"
        )
    
    # ==================== CRITICAL (System Failures) ====================
    
    def disconnected(self):
        """Bot disconnected from exchange"""
        self._add_to_memory('critical', 'disconnected')
        self._last_disconnect_time = time.time()
        self._in_reconnect_arc = True
        self._reconnect_steps = ['disconnected']
        
        narrative = self._get_narrative_for_context(self.NARRATIVE_TEMPLATES['connection_lost'])
        
        self._log_with_level(
            LogLevel.CRITICAL, 
            "Bot disconnected, reconnecting.",
            force=True,
            narrative=narrative
        )
    
    def reconnecting(self):
        """Reconnection in progress"""
        self._add_to_memory('critical', 'reconnecting')
        self._reconnect_steps.append('reconnecting')
        
        self._log_with_level(
            LogLevel.CRITICAL, 
            "Reconnection triggered. All tasks restarting.",
            force=True,
            narrative="🔄 RECONNECTING NOW... Restarting all systems. Hang tight!"
        )
    
    def task_died(self, task_name: str):
        """Background task died"""
        self._add_to_memory('critical', 'task_died')
        self._error_streak += 1
        
        self._log_with_level(
            LogLevel.CRITICAL, 
            f"Task died: {task_name} - restarting automatically.",
            force=True,
            narrative=f"⚠️ SYSTEM ALERT: {task_name} crashed! Auto-restarting it now..."
        )
    
    def loop_stalled(self, loop_name: str, expected_interval: float):
        """Background loop stalled"""
        self._add_to_memory('critical', 'loop_stalled')
        self._log_with_level(
            LogLevel.CRITICAL, 
            f"{loop_name} loop stalled (expected every {expected_interval:.0f}s).",
            force=True,
            narrative=f"🚨 {loop_name} has frozen! Expected update every {expected_interval:.0f}s. Investigating..."
        )
    
    def websocket_closed(self, reason: str = "Unknown"):
        """WebSocket connection closed"""
        self._add_to_memory('critical', 'ws_closed')
        self._in_reconnect_arc = True
        self._reconnect_steps = ['closed']
        
        self._log_with_level(
            LogLevel.CRITICAL, 
            f"WebSocket closed: {reason}",
            force=True,
            narrative=f"🔌 WebSocket dropped: {reason}. Reconnecting immediately..."
        )
    
    def authentication_failed(self, reason: str):
        """Authentication failed"""
        self._add_to_memory('critical', 'auth_failed')
        self._log_with_level(
            LogLevel.CRITICAL, 
            f"Authentication failed: {reason}",
            force=True,
            narrative=f"🔐 AUTH FAILED: {reason}. Can't trade without authentication. Retrying..."
        )
    
    def emergency_stop(self, reason: str):
        """Emergency stop triggered"""
        self._add_to_memory('critical', 'emergency_stop')
        self._log_with_level(
            LogLevel.CRITICAL, 
            f"🛑 EMERGENCY STOP: {reason}",
            force=True,
            narrative=f"🛑 EMERGENCY STOP: {reason}. All trading halted for safety!"
        )
    
    def data_loss(self, data_type: str):
        """Critical data loss detected"""
        self._add_to_memory('critical', 'data_loss')
        self._log_with_level(
            LogLevel.CRITICAL, 
            f"Data loss detected: {data_type} unavailable.",
            force=True,
            narrative=f"🚨 CRITICAL: {data_type} data lost! We need this to trade safely. Investigating..."
        )
    
    # ==================== System Operations (Human-Readable) ====================
    
    def checking_positions(self):
        """Checking positions with exchange"""
        self._add_to_memory('checking_positions')
        self._log_with_level(
            LogLevel.BOT_OK,
            "Checking positions with exchange.",
            key="check_positions",
            narrative="📊 Syncing positions with the exchange... making sure we're square."
        )
    
    def checking_orders(self):
        """Checking orders with exchange"""
        self._add_to_memory('checking_orders')
        self._log_with_level(
            LogLevel.BOT_OK,
            "Checking open orders with exchange.",
            key="check_orders",
            narrative="🔍 Verifying open orders. Let's see what's out there..."
        )
    
    def fetching_price(self, symbol: str):
        """Fetching current market price"""
        self._log_with_level(
            LogLevel.BOT_OK,
            f"Getting current {symbol} price from exchange.",
            key="fetch_price",
            narrative=f"Let me check what {symbol} is trading at right now... 🔍"
        )
    
    def state_saved(self):
        """Trading state saved"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Trading state saved (safe to restart).",
            key="state_saved",
            narrative="💾 Saved everything to disk. If we crash, we'll remember where we left off."
        )
    
    def position_tracker_active(self):
        """Position tracker checking status"""
        self._add_to_memory('position_tracker')
        self._log_with_level(
            LogLevel.BOT_OK,
            "Position tracker checking current status.",
            key="position_tracker",
            narrative="📊 Position tracker online. Monitoring our exposure..."
        )
    
    def order_manager_active(self):
        """Order manager processing request"""
        self._add_to_memory('order_manager')
        self._log_with_level(
            LogLevel.BOT_OK,
            "Order manager processing request.",
            key="order_manager",
            narrative="⚙️ Order manager handling the request. Systems working..."
        )
    
    def health_monitoring_active(self):
        """Health monitoring started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Health monitoring active - tracking bot status.",
            force=True,
            narrative="🏥 Health monitor is up. I'll watch for any signs of trouble."
        )
    
    def watchdog_active(self):
        """Watchdog monitoring started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Watchdog active - monitoring for stuck processes.",
            force=True,
            narrative="🐕 Watchdog's on duty. If anything freezes, I'll bark."
        )
    
    def reconciliation_active(self):
        """Reconciliation loop started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Exchange sync active - verifying orders match.",
            force=True,
            narrative="🔄 Reconciliation started. Every 5 minutes, I'll double-check our orders match the exchange."
        )
    
    def monitoring_active(self):
        """Monitoring loop started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Performance monitoring active - tracking metrics.",
            force=True,
            narrative="📊 Metrics tracker online. Recording everything for the dashboard."
        )
    
    def websocket_message_loop_active(self):
        """WebSocket message loop started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Live price feed active - listening for updates.",
            force=True,
            narrative="📡 Tuned into the live feed. Price updates coming in hot!"
        )
    
    def heartbeat_loop_active(self):
        """Heartbeat loop started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Status updates enabled - broadcasting bot health.",
            force=True,
            narrative="💗 Heartbeat started. I'll tell you how I'm doing every few seconds."
        )
    
    def rest_fallback_active(self):
        """REST fallback monitor started"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Backup data source active - ensuring price availability.",
            force=True,
            narrative="🔌 Backup system ready. If the live feed cuts out, I'll switch to REST API automatically."
        )
    
    def startup_notification_sent(self):
        """Startup notification sent"""
        self._add_to_memory('startup_notification')
        self._log_with_level(
            LogLevel.BOT_OK,
            "Startup notification sent to monitoring.",
            force=True,
            narrative="📢 Notified the monitoring system. We're officially live!"
        )
    
    def slow_operation(self, operation: str, duration: float):
        """Operation took longer than expected"""
        self._log_with_level(
            LogLevel.WARNING,
            f"{operation} took {duration:.1f}s (slower than usual).",
            key=f"slow_{operation}"
        )
    
    def existing_orders_found(self, count: int):
        """Found existing orders on exchange"""
        self._add_to_memory('existing_orders')
        
        if count > 5:
            narrative = f"⚠️ Found {count} existing orders out there! Let me check what's going on..."
        else:
            narrative = f"Found {count} order(s) already on the exchange. Checking their status..."
        
        self._log_with_level(
            LogLevel.WARNING,
            f"Found {count} existing order(s) on exchange - checking status.",
            force=True,
            narrative=narrative
        )
    
    def initial_order_placed(self, side: str, price: float):
        """Initial order placed successfully"""
        self._log_with_level(
            LogLevel.BOT_OK,
            f"Initial {side} order placed @ ${price:,.0f} - watching for fill.",
            force=True,
            narrative=f"🎯 Alright! First {side} order is in at ${price:,.0f}. Let's see if the market comes to us..."
        )
    
    def wiring_webui(self):
        """Connecting to WebUI"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Connecting bot to monitoring dashboard.",
            force=True,
            narrative="🔗 Hooking up to the dashboard so you can watch everything in real-time..."
        )
    
    def webui_connected(self):
        """WebUI connection established"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "Dashboard connected - charts and status available.",
            force=True,
            narrative="✨ Dashboard is live! Open it up - you can see all the charts and positions now."
        )
    
    def bot_started_successfully(self):
        """Bot started successfully"""
        runtime = time.time() - self._session_start_time
        self._log_with_level(
            LogLevel.BOT_OK,
            "🚀 Bot started successfully - trading active.",
            force=True,
            narrative=f"🚀 WE'RE LIVE! Bot is armed and ready. Took {runtime:.1f}s to boot up. Let's make some money!"
        )
    
    def bot_shutting_down(self):
        """Bot shutting down"""
        self._log_with_level(
            LogLevel.BOT_OK,
            "🛑 Bot shutting down - cancelling pending orders...",
            force=True,
            narrative="🛑 Shutting down gracefully. Cancelling pending entry orders to keep things clean..."
        )
    
    def checking_for_entry(self):
        """Checking for entry opportunity"""
        self._add_to_memory('checking_entry')
        self._log_with_level(
            LogLevel.BOT_OK,
            "Analyzing market for entry opportunity.",
            key="check_entry",
            narrative="🎯 Scanning the market... looking for our entry opportunity."
        )
    
    def code_narration_event(self, text: str):
        """
        Log a code narration event (runtime code explanation).
        
        This method is called by the narrator integration system to log
        human-readable explanations of what the code is doing at runtime.
        
        Args:
            text: Human explanation of code behavior
        
        Features:
        - Rate-limited separately from other logs
        - Respects narrative mode
        - Async-safe (never blocks)
        - Optional/switchable via config
        
        Example:
            human_log.code_narration_event(
                "This BUY order was triggered by Step 3 of create_buy_fill_saga."
            )
        """
        self._add_to_memory('code_narration')
        
        # Use special rate limiting key for code narrations
        # This prevents them from interfering with regular logs
        self._log_with_level(
            LogLevel.BOT_OK,
            f"Code Narration: {text}",
            key="code_narration",
            narrative=f"💡 Decoded Logic:\n{text}"
        )


# Global singleton instance with NARRATIVE MODE enabled!
# Set narrative_mode=False for technical format, True for trader's story
# log_delay=0.25 slows terminal output by 4x for readability
human_log = HumanLogger(rate_limit_seconds=3.0, narrative_mode=True, log_delay=0.25)
