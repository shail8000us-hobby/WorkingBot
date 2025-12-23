"""
Mode Switcher Service - Phase 3
Auto LONG/SHORT mode switching based on market conditions

Features:
- Hysteresis-based switching (prevents flip-flopping)
- Configurable switch delay
- Manual override support
- Switch history tracking
- Telegram notifications
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from .market_monitor import get_market_monitor

logger = logging.getLogger(__name__)


@dataclass
class SwitchEvent:
    """Mode switch event record"""
    timestamp: str
    price: float
    from_mode: str
    to_mode: str
    reason: str
    trigger: str  # 'auto', 'manual'
    

class ModeSwitcher:
    """
    Manages automatic LONG/SHORT mode switching
    
    Strategy:
    - When price < (reference - hysteresis) → LONG mode
    - When price > (reference + hysteresis) → SHORT mode
    - In hysteresis zone → maintain current mode (no switching)
    - Enforce minimum delay between switches
    - Support manual override with timeout
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Switching configuration
        self.reference_price = config.get('reference_price', 95500)
        self.hysteresis = config.get('hysteresis', 200)  # +/- buffer
        self.switch_delay = config.get('switch_delay', 30)  # seconds
        
        # Strategy assignments
        self.long_strategy = config.get('long_strategy', 'conservative')
        self.short_strategy = config.get('short_strategy', 'conservative')
        
        # Current state
        self.current_mode: Optional[str] = None
        self.pending_switch: Optional[str] = None
        self.last_switch_time: Optional[datetime] = None
        
        # Manual override
        self.manual_override_active = False
        self.manual_override_mode: Optional[str] = None
        self.manual_override_until: Optional[datetime] = None
        
        # Switch history
        self.switch_history: List[SwitchEvent] = []
        self.max_history = 100
        
        # State persistence
        self.state_file = Path("data/mode_switcher_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Running flag
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Notification callback
        self._notification_callback = None
        
        logger.info(f"ModeSwitcher initialized (ref: ${self.reference_price}, hyst: ${self.hysteresis})")
    
    @property
    def long_activate_price(self) -> float:
        """Price threshold to activate LONG mode"""
        return self.reference_price - self.hysteresis
    
    @property
    def short_activate_price(self) -> float:
        """Price threshold to activate SHORT mode"""
        return self.reference_price + self.hysteresis
    
    def set_notification_callback(self, callback):
        """Set callback for switch notifications"""
        self._notification_callback = callback
    
    async def start(self):
        """Start mode switcher"""
        if self._running:
            logger.warning("ModeSwitcher already running")
            return
        
        self._running = True
        self._load_state()
        self._task = asyncio.create_task(self._switcher_loop())
        logger.info("ModeSwitcher started")
    
    async def stop(self):
        """Stop mode switcher"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self._save_state()
        logger.info("ModeSwitcher stopped")
    
    async def _switcher_loop(self):
        """Main switching loop"""
        check_interval = 5  # Check every 5 seconds
        
        while self._running:
            try:
                # Check if manual override expired
                self._check_manual_override()
                
                # Skip if manual override active
                if self.manual_override_active:
                    await asyncio.sleep(check_interval)
                    continue
                
                # Get current market price
                market_monitor = get_market_monitor()
                market_snapshot = market_monitor.get_snapshot()
                current_price = market_snapshot.current_price
                
                if current_price == 0:
                    logger.warning("No market price available, skipping switch check")
                    await asyncio.sleep(check_interval)
                    continue
                
                # Check if mode switch needed
                await self._check_and_switch(current_price)
                
                # Save state
                self._save_state()
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in mode switcher loop: {e}", exc_info=True)
                await asyncio.sleep(check_interval)
    
    async def _check_and_switch(self, current_price: float):
        """Check price and switch modes if needed"""
        # Determine target mode based on price
        if current_price < self.long_activate_price:
            target_mode = 'LONG'
        elif current_price > self.short_activate_price:
            target_mode = 'SHORT'
        else:
            # In hysteresis zone - maintain current mode
            return
        
        # No switch needed if already in target mode
        if self.current_mode == target_mode:
            self.pending_switch = None
            return
        
        # Check if switch delay has passed
        if not self._can_switch():
            if self.pending_switch != target_mode:
                logger.info(f"Mode switch to {target_mode} pending (delay: {self.switch_delay}s)")
                self.pending_switch = target_mode
            return
        
        # Execute the switch
        await self._execute_switch(target_mode, current_price, 'auto')
    
    def _can_switch(self) -> bool:
        """Check if enough time has passed since last switch"""
        if self.last_switch_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_switch_time).total_seconds()
        return elapsed >= self.switch_delay
    
    async def _execute_switch(self, new_mode: str, price: float, trigger: str):
        """Execute mode switch"""
        old_mode = self.current_mode or 'NONE'
        
        # Record switch event
        event = SwitchEvent(
            timestamp=datetime.now().isoformat(),
            price=price,
            from_mode=old_mode,
            to_mode=new_mode,
            reason=f"Price {'crossed down' if new_mode == 'LONG' else 'crossed up'}",
            trigger=trigger
        )
        
        self.switch_history.append(event)
        if len(self.switch_history) > self.max_history:
            self.switch_history = self.switch_history[-self.max_history:]
        
        # Update state
        self.current_mode = new_mode
        self.last_switch_time = datetime.now()
        self.pending_switch = None
        
        logger.info(f"🔄 Mode Switch: {old_mode} → {new_mode} @ ${price:,.2f}")
        
        # TODO: Actually activate/deactivate strategies
        # This will require integration with strategy manager
        # For now, just log the switch
        
        # Send notification
        await self._send_notification(event)
    
    async def _send_notification(self, event: SwitchEvent):
        """Send notification about mode switch"""
        message = (
            f"🔄 Mode Switch: {event.from_mode} → {event.to_mode}\n"
            f"Price: ${event.price:,.0f}\n"
            f"Time: {datetime.fromisoformat(event.timestamp).strftime('%H:%M:%S')}\n"
            f"Reason: {event.reason}"
        )
        
        if self._notification_callback:
            try:
                await self._notification_callback(message)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
        
        logger.info(f"Notification: {message}")
    
    def _check_manual_override(self):
        """Check if manual override has expired"""
        if not self.manual_override_active:
            return
        
        if self.manual_override_until and datetime.now() >= self.manual_override_until:
            logger.info("Manual override expired, resuming auto-switching")
            self.manual_override_active = False
            self.manual_override_mode = None
            self.manual_override_until = None
    
    def set_manual_override(
        self,
        mode: str,
        duration_hours: Optional[float] = None,
        reason: str = "Manual override"
    ):
        """
        Manually override mode
        
        Args:
            mode: 'LONG', 'SHORT', or 'AUTO' (to resume auto-switching)
            duration_hours: How long override lasts (None = indefinite)
            reason: Reason for override
        """
        if mode == 'AUTO':
            # Resume auto-switching
            self.manual_override_active = False
            self.manual_override_mode = None
            self.manual_override_until = None
            logger.info("Manual override cleared, auto-switching resumed")
            return
        
        # Set override
        self.manual_override_active = True
        self.manual_override_mode = mode
        
        if duration_hours:
            self.manual_override_until = datetime.now() + timedelta(hours=duration_hours)
            logger.info(f"Manual override: {mode} for {duration_hours}h ({reason})")
        else:
            self.manual_override_until = None
            logger.info(f"Manual override: {mode} indefinitely ({reason})")
        
        # If mode different from current, record switch
        if mode != self.current_mode:
            market_monitor = get_market_monitor()
            current_price = market_monitor.current_price or 0
            
            asyncio.create_task(
                self._execute_switch(mode, current_price, 'manual')
            )
    
    def update_reference_price(self, price: float):
        """Update reference price"""
        old_ref = self.reference_price
        self.reference_price = price
        self.config['reference_price'] = price
        
        logger.info(f"Reference price updated: ${old_ref:,.0f} → ${price:,.0f}")
        logger.info(f"New thresholds: LONG < ${self.long_activate_price:,.0f}, SHORT > ${self.short_activate_price:,.0f}")
    
    def update_hysteresis(self, hysteresis: float):
        """Update hysteresis buffer"""
        old_hyst = self.hysteresis
        self.hysteresis = hysteresis
        self.config['hysteresis'] = hysteresis
        
        logger.info(f"Hysteresis updated: ${old_hyst:,.0f} → ${hysteresis:,.0f}")
    
    def get_state(self) -> Dict:
        """Get current state"""
        return {
            'enabled': self._running,
            'current_mode': self.current_mode,
            'pending_switch': self.pending_switch,
            'manual_override_active': self.manual_override_active,
            'manual_override_mode': self.manual_override_mode,
            'manual_override_until': self.manual_override_until.isoformat() if self.manual_override_until else None,
            'reference_price': self.reference_price,
            'hysteresis': self.hysteresis,
            'long_activate_price': self.long_activate_price,
            'short_activate_price': self.short_activate_price,
            'switch_delay': self.switch_delay,
            'last_switch_time': self.last_switch_time.isoformat() if self.last_switch_time else None,
            'switch_history_count': len(self.switch_history)
        }
    
    def get_history(self, hours: int = 24) -> List[Dict]:
        """Get switch history for last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent_switches = [
            asdict(event)
            for event in self.switch_history
            if datetime.fromisoformat(event.timestamp) >= cutoff
        ]
        
        return recent_switches
    
    def _save_state(self):
        """Save state to file"""
        try:
            state = {
                'current_mode': self.current_mode,
                'last_switch_time': self.last_switch_time.isoformat() if self.last_switch_time else None,
                'reference_price': self.reference_price,
                'hysteresis': self.hysteresis,
                'switch_history': [asdict(e) for e in self.switch_history[-50:]],
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save mode switcher state: {e}")
    
    def _load_state(self):
        """Load state from file"""
        try:
            if not self.state_file.exists():
                logger.info("No previous mode switcher state found")
                return
            
            with open(self.state_file) as f:
                state = json.load(f)
            
            self.current_mode = state.get('current_mode')
            self.reference_price = state.get('reference_price', self.reference_price)
            self.hysteresis = state.get('hysteresis', self.hysteresis)
            
            last_switch = state.get('last_switch_time')
            if last_switch:
                self.last_switch_time = datetime.fromisoformat(last_switch)
            
            # Restore history
            history_data = state.get('switch_history', [])
            self.switch_history = [
                SwitchEvent(**event) for event in history_data
            ]
            
            logger.info(f"Mode switcher state loaded (mode: {self.current_mode}, {len(self.switch_history)} switches)")
            
        except Exception as e:
            logger.error(f"Failed to load mode switcher state: {e}")


# Global instance
_mode_switcher: Optional[ModeSwitcher] = None


def get_mode_switcher(config: Optional[Dict] = None) -> ModeSwitcher:
    """Get or create global mode switcher instance"""
    global _mode_switcher
    
    if _mode_switcher is None:
        if config is None:
            config = {
                'reference_price': 95500,
                'hysteresis': 200,
                'switch_delay': 30,
                'long_strategy': 'conservative',
                'short_strategy': 'conservative'
            }
        _mode_switcher = ModeSwitcher(config)
    
    return _mode_switcher


async def start_mode_switcher(config: Optional[Dict] = None):
    """Start the global mode switcher"""
    switcher = get_mode_switcher(config)
    await switcher.start()
    return switcher


async def stop_mode_switcher():
    """Stop the global mode switcher"""
    global _mode_switcher
    if _mode_switcher:
        await _mode_switcher.stop()
