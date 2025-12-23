#!/usr/bin/env python3
"""
Monitoring Data Writer - Shared State for WebUI

Writes monitoring data to JSON file so WebUI can access it even when
bot runs standalone (not started from WebUI).

Created: November 8, 2025
Purpose: Eliminate "monitoring only works from WebUI start" bandage
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger(__name__)


class MonitoringDataWriter:
    """
    Writes monitoring system state to shared JSON file.
    
    This allows WebUI to read monitoring data regardless of how bot was started.
    Eliminates the need for `set_bot_instance()` wiring.
    """
    
    def __init__(self, output_file: str = "data/monitoring_snapshot.json"):
        """
        Initialize monitoring data writer.
        
        Args:
            output_file: Path to JSON file for monitoring data
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_write_time = 0
        
        log.info(f"📊 Monitoring data writer initialized: {self.output_file}")
    
    def write_snapshot(self, bot_instance) -> bool:
        """
        Write current monitoring state to JSON file.
        
        Args:
            bot_instance: GridBot instance with monitoring systems
            
        Returns:
            True if write successful, False otherwise
        """
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'monitoring_active': True,
                'bot_status': self._get_bot_status(bot_instance),
                'layers': {
                    'price_health': self._get_price_health(bot_instance),
                    'pre_order_stats': self._get_pre_order_stats(bot_instance),
                    'tp_verification': self._get_tp_verification(bot_instance),
                    'anomalies': self._get_anomalies(bot_instance),
                    'predictive': self._get_predictive(bot_instance),
                    'trading_condition': self._get_trading_condition(bot_instance),
                    'opportunistic_recovery': self._get_opportunistic_recovery(bot_instance)
                }
            }
            
            # Atomic write (write to temp, then rename)
            tmp_file = self.output_file.with_suffix('.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(data, f, indent=2)
            tmp_file.replace(self.output_file)
            
            return True
            
        except Exception as e:
            log.debug(f"Failed to write monitoring snapshot: {e}")
            return False
    
    def _get_bot_status(self, bot) -> Dict[str, Any]:
        """Get basic bot status"""
        try:
            # Bot is active if it has a current price (WebSocket connected)
            is_active = getattr(bot, 'current_price', None) is not None
            
            return {
                'active': is_active,
                'mode': getattr(bot, 'grid_mode', 'UNKNOWN'),
                'current_price': getattr(bot, 'current_price', None),
                'positions': len(bot.position_mgr.get_positions()) if hasattr(bot, 'position_mgr') else 0,
                'max_positions': getattr(bot, 'max_open', 0)
            }
        except Exception as e:
            log.debug(f"Error getting bot status: {e}")
            return {}
    
    def _get_price_health(self, bot) -> Dict[str, Any]:
        """Get price health monitor data"""
        try:
            if not hasattr(bot, 'price_monitor') or not bot.price_monitor:
                return {'active': False}
            
            return bot.price_monitor.get_status()
            
        except Exception as e:
            log.debug(f"Error getting price health: {e}")
            return {'active': False, 'error': str(e)}
    
    def _get_pre_order_stats(self, bot) -> Dict[str, Any]:
        """Get pre-order logger statistics"""
        try:
            if not hasattr(bot, 'pre_order_logger') or not bot.pre_order_logger:
                return {'active': False}
            
            stats = bot.pre_order_logger.get_statistics()
            stats['active'] = True  # Add active flag
            return stats
            
        except Exception as e:
            log.debug(f"Error getting pre-order stats: {e}")
            return {'active': False, 'error': str(e)}
    
    def _get_tp_verification(self, bot) -> Dict[str, Any]:
        """Get TP verification system data"""
        try:
            if not hasattr(bot, 'tp_verifier') or not bot.tp_verifier:
                return {'active': False}
            
            stats = bot.tp_verifier.get_statistics()
            stats['active'] = True  # Add active flag
            return stats
            
        except Exception as e:
            log.debug(f"Error getting TP verification: {e}")
            return {'active': False, 'error': str(e)}
    
    def _get_anomalies(self, bot) -> Dict[str, Any]:
        """Get anomaly detection system data"""
        try:
            if not hasattr(bot, 'anomaly_detector') or not bot.anomaly_detector:
                return {'active': False}
            
            return bot.anomaly_detector.get_summary()
            
        except Exception as e:
            log.debug(f"Error getting anomalies: {e}")
            return {'active': False, 'error': str(e)}
    
    def _get_predictive(self, bot) -> Dict[str, Any]:
        """Get predictive display system data using REAL bot brain"""
        try:
            if not hasattr(bot, 'grid_calc') or not bot.grid_calc:
                return {'active': False, 'error': 'Grid calculator not available'}
            
            # Get current state from real bot brain
            current_price = getattr(bot, 'current_price', None)
            grid_mode = getattr(bot, 'grid_mode', 'LONG')
            grid_step = bot.grid_calc.step if hasattr(bot, 'grid_calc') else 500
            
            # Get state from SQL event store database AND position actor
            # SQL for pending orders (source of truth), actor for current positions (in-memory state)
            import sqlite3
            import json
            import asyncio
            import concurrent.futures
            
            state = None
            try:
                # Check if bot has event_store
                if not hasattr(bot, 'event_store'):
                    log.warning("[DATA_WRITER] Bot missing event_store")
                    state = {"open_tranches": [], "pending_buy": None, "pending_sell": None}
                else:
                    # Query SQL database for latest pending order events (source of truth)
                    db_path = bot.event_store.db_path
                    
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    # Get latest PENDING_BUY_SET or PENDING_BUY_CLEARED event
                    cursor.execute("""
                        SELECT event_type, data, timestamp 
                        FROM events 
                        WHERE event_type IN ('pending_buy_set', 'pending_buy_cleared')
                        ORDER BY timestamp DESC 
                        LIMIT 1
                    """)
                    pending_buy_row = cursor.fetchone()
                    
                    # Get latest PENDING_SELL_SET or PENDING_SELL_CLEARED event
                    cursor.execute("""
                        SELECT event_type, data, timestamp 
                        FROM events 
                        WHERE event_type IN ('pending_sell_set', 'pending_sell_cleared')
                        ORDER BY timestamp DESC 
                        LIMIT 1
                    """)
                    pending_sell_row = cursor.fetchone()
                    
                    conn.close()
                    
                    # Parse pending orders from JSON data
                    pending_buy = None
                    if pending_buy_row and pending_buy_row['event_type'] == 'pending_buy_set':
                        pending_buy = json.loads(pending_buy_row['data'])
                    
                    pending_sell = None
                    if pending_sell_row and pending_sell_row['event_type'] == 'pending_sell_set':
                        pending_sell = json.loads(pending_sell_row['data'])
                    
                    # Get current positions from position_actor (in-memory, accurate)
                    positions = []
                    if hasattr(bot, 'position_actor') and hasattr(bot, 'loop'):
                        try:
                            coro = bot.position_actor.ask("GET_STATE", {}, timeout=2.0)
                            future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                            actor_state = future.result(timeout=3.0)
                            positions = actor_state.get("open_tranches", [])
                        except Exception as e:
                            log.warning(f"[DATA_WRITER] Could not get positions from actor: {e}")
                    
                    state = {
                        "open_tranches": positions,
                        "pending_buy": pending_buy,
                        "pending_sell": pending_sell
                    }
                    log.info(f"[DATA_WRITER] pending_buy={pending_buy is not None}, pending_sell={pending_sell is not None}, positions={len(positions)}")
                    
            except Exception as e:
                log.error(f"[DATA_WRITER] Error querying SQL database: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                state = {"open_tranches": [], "pending_buy": None, "pending_sell": None}
            
            positions = state.get("open_tranches", [])
            max_open = getattr(bot, 'max_open', 10)
            
            # Get pending orders from SQL state
            pending_buy = state.get("pending_buy")
            pending_sell = state.get("pending_sell")
            
            if not current_price:
                return {'active': False, 'error': 'No current price'}
            
            # Use grid calculator to get REAL next levels
            next_buy = None
            next_tp = None
            
            if grid_mode == 'LONG':
                # Get next BUY from grid calculator (uses real bot logic)
                next_buy = bot.grid_calc.compute_next_buy_level(positions, current_price)
                
                # If we have positions, get next TP (highest position + step)
                if positions:
                    highest_entry = max(p.get('entry_price', 0) for p in positions)
                    next_tp = bot.grid_calc.compute_tp_price(highest_entry)
            else:  # SHORT mode
                # Get next SELL from grid calculator
                next_sell = bot.grid_calc.compute_next_sell_level(positions, current_price)
                if next_sell:
                    next_buy = next_sell  # Will be labeled as SELL in frontend
                
                # If we have positions, get next TP (lowest position - step)
                if positions:
                    lowest_entry = min(p.get('entry_price', float('inf')) for p in positions)
                    next_tp = bot.grid_calc.compute_tp_price_short(lowest_entry)
            
            # Get actual executed orders from bot memory
            executed_orders = []
            placed_tps = []
            
            for pos in positions:
                executed_orders.append({
                    'entry_price': pos.get('entry_price'),
                    'size': pos.get('size'),
                    'grid_level': pos.get('grid_level', 'N/A'),
                    'timestamp': pos.get('timestamp', 'N/A')
                })
                
                if pos.get('tp_price'):
                    placed_tps.append({
                        'tp_price': pos.get('tp_price'),
                        'entry_price': pos.get('entry_price'),
                        'size': pos.get('size'),
                        'order_id': pos.get('tp_order_id', 'N/A')
                    })
            
            # Generate scenarios using REAL bot brain
            return {
                'active': True,
                'current_state': {
                    'mode': grid_mode,
                    'price': current_price,
                    'grid_step': grid_step,
                    'positions': len(positions),
                    'max_positions': max_open,
                    'capacity_used_pct': (len(positions) / max_open * 100) if max_open > 0 else 0,
                    'pending_buy': pending_buy is not None,
                    'pending_sell': pending_sell is not None
                },
                'executed_orders': executed_orders,
                'placed_tps': placed_tps,
                'scenarios': self._generate_real_scenarios(
                    bot.grid_calc,
                    current_price,
                    grid_mode,
                    positions,
                    max_open,
                    pending_buy,
                    pending_sell,
                    next_buy,
                    next_tp
                )
            }
            
        except Exception as e:
            log.debug(f"Error getting predictive data: {e}")
            return {'active': False, 'error': str(e)}
    
    def _generate_real_scenarios(
        self,
        grid_calc,
        current_price: float,
        grid_mode: str,
        positions: List,
        max_positions: int,
        pending_buy: Any,
        pending_sell: Any,
        next_buy: Optional[float],
        next_tp: Optional[float]
    ) -> Dict[str, Any]:
        """
        Generate scenarios using REAL bot brain (GridCalculator)
        
        Shows EXACTLY what the bot will do next based on actual grid logic.
        """
        scenarios = {
            'next_action': None,
            'price_drops': [],
            'price_rises': []
        }
        
        # NEXT IMMEDIATE ACTION (most important!)
        if pending_buy:
            scenarios['next_action'] = {
                'type': 'PENDING_BUY' if grid_mode == 'LONG' else 'PENDING_SELL',
                'price': pending_buy.get('price') if isinstance(pending_buy, dict) else None,
                'status': 'Waiting for fill',
                'then': f"Place TP at ${next_tp:,.0f}" if next_tp else "Calculate TP"
            }
        elif pending_sell:
            scenarios['next_action'] = {
                'type': 'PENDING_TP',
                'price': pending_sell.get('price') if isinstance(pending_sell, dict) else None,
                'status': 'Waiting for TP fill',
                'then': f"Place next BUY at ${next_buy:,.0f}" if next_buy else "No more capacity"
            }
        elif next_buy and len(positions) < max_positions:
            # CRITICAL: Only show BUY as next action if price needs to DROP to reach it (LONG)
            # or price needs to RISE to reach it (SHORT)
            price_will_trigger = (grid_mode == 'LONG' and current_price > next_buy) or \
                                (grid_mode == 'SHORT' and current_price < next_buy)
            
            if price_will_trigger:
                scenarios['next_action'] = {
                    'type': 'WILL_BUY' if grid_mode == 'LONG' else 'WILL_SELL',
                    'price': next_buy,
                    'status': f'Will place when price drops to ${next_buy:,.0f}' if grid_mode == 'LONG' else f'Will place when price rises to ${next_buy:,.0f}',
                    'then': f"Then TP at ${next_tp:,.0f}" if next_tp else "Calculate TP"
                }
            else:
                # Price already passed this level, no immediate action
                scenarios['next_action'] = {
                    'type': 'NO_TPS' if positions else 'NO_ACTION',
                    'status': 'No open positions' if not positions else 'Waiting for TP fills',
                    'then': 'Price must move to trigger new entry'
                }
        elif len(positions) >= max_positions:
            scenarios['next_action'] = {
                'type': 'CAPACITY_FULL',
                'status': f'{len(positions)}/{max_positions} positions filled',
                'then': 'Wait for TP fill to free capacity'
            }
        else:
            scenarios['next_action'] = {
                'type': 'NO_ACTION',
                'status': 'No valid action (outside grid bounds)',
                'then': 'Wait for price to enter grid range'
            }
        
        # PRICE DROP SCENARIOS (what happens if price drops)
        if grid_mode == 'LONG':
            # Show next 3 BUY levels using REAL grid calculator
            temp_positions = positions.copy()
            for i in range(3):
                if len(temp_positions) >= max_positions:
                    scenarios['price_drops'].append({
                        'action': 'Cannot place',
                        'price': None,
                        'reason': 'Position limit reached',
                        'sequence': i + 1
                    })
                    continue
                
                # Calculate next BUY using real bot logic
                next_level = grid_calc.compute_next_buy_level(temp_positions, current_price)
                
                if not next_level:
                    scenarios['price_drops'].append({
                        'action': 'Cannot place',
                        'price': None,
                        'reason': 'Below grid lower bound',
                        'sequence': i + 1
                    })
                    break
                
                # Calculate TP for this position
                tp_price = grid_calc.compute_tp_price(next_level)
                change_pct = ((current_price - next_level) / current_price) * 100
                
                scenarios['price_drops'].append({
                    'action': 'BUY',
                    'price': next_level,
                    'tp_price': tp_price,
                    'change_pct': -change_pct,
                    'reason': f'Grid level #{len(temp_positions) + 1}',
                    'sequence': i + 1,
                    'profit_target': tp_price - next_level
                })
                
                # Simulate adding this position for next iteration
                temp_positions.append({'entry_price': next_level, 'tp_price': tp_price})
        
        else:  # SHORT mode
            # Show next 3 SELL levels
            temp_positions = positions.copy()
            for i in range(3):
                if len(temp_positions) >= max_positions:
                    scenarios['price_drops'].append({
                        'action': 'Cannot place',
                        'price': None,
                        'reason': 'Position limit reached',
                        'sequence': i + 1
                    })
                    continue
                
                next_level = grid_calc.compute_next_sell_level(temp_positions, current_price)
                
                if not next_level:
                    scenarios['price_drops'].append({
                        'action': 'Cannot place',
                        'price': None,
                        'reason': 'Above grid upper bound',
                        'sequence': i + 1
                    })
                    break
                
                tp_price = grid_calc.compute_tp_price_short(next_level)
                change_pct = ((current_price - next_level) / current_price) * 100
                
                scenarios['price_drops'].append({
                    'action': 'SELL',
                    'price': next_level,
                    'tp_price': tp_price,
                    'change_pct': -change_pct,
                    'reason': f'Grid level #{len(temp_positions) + 1}',
                    'sequence': i + 1,
                    'profit_target': next_level - tp_price
                })
                
                temp_positions.append({'entry_price': next_level, 'tp_price': tp_price})
        
        # PRICE RISE SCENARIOS (what happens if price rises = TP fills)
        if positions:
            # Show TPs in order (closest to farthest)
            sorted_positions = sorted(positions, key=lambda p: p.get('entry_price', 0), reverse=(grid_mode == 'LONG'))
            
            for i, pos in enumerate(sorted_positions[:3]):
                entry = pos.get('entry_price', 0)
                tp_price = pos.get('tp_price') or (
                    grid_calc.compute_tp_price(entry) if grid_mode == 'LONG' 
                    else grid_calc.compute_tp_price_short(entry)
                )
                
                change_pct = ((tp_price - current_price) / current_price) * 100
                profit = (tp_price - entry) if grid_mode == 'LONG' else (entry - tp_price)
                
                scenarios['price_rises'].append({
                    'action': 'TP Fill',
                    'price': tp_price,
                    'entry_price': entry,
                    'change_pct': change_pct,
                    'reason': f'TP for position @ ${entry:,.0f}',
                    'sequence': i + 1,
                    'profit': profit
                })
        
        if not scenarios['price_rises']:
            scenarios['price_rises'].append({
                'action': 'No TPs',
                'price': None,
                'reason': 'No open positions',
                'sequence': 1
            })
        
        return scenarios
    
    def _get_trading_condition(self, bot) -> Dict[str, Any]:
        """
        Get trading condition data from guarding bot features (blocker tracker, safety systems)
        
        Shows comprehensive view of all safety checks and what's blocking/allowing trading
        """
        try:
            from bot.safety.blocker_tracker import get_blocker_tracker
            import os
            
            # Get blocker tracker data
            tracker = get_blocker_tracker()
            blocker_data = tracker.check_all_blockers()
            
            # Get guardian bot status if available
            guardian_status = self._get_guardian_status()
            
            # Get key safety settings from config
            cfg = get_config()
            safety_config = {
                'execute_orders': cfg.safety.execute_orders,
                'trading_mode': cfg.trading_mode,  # At root level
                'guardian_enabled': cfg.guardian.enabled,
                'volatility_safety': cfg.safety.volatility.enabled,
                'liquidation_protection': cfg.liquidation_protection.enabled,
                'drawdown_cap': cfg.capital_protection.drawdown_cap.enabled,
                'order_confirmation': cfg.safety.confirmation_guard.enabled
            }
            
            # Categorize blockers by severity
            critical_blockers = []
            warning_blockers = []
            info_blockers = []
            
            for blocker in blocker_data.get('blockers', []):
                if not blocker.get('active'):
                    continue
                    
                severity = blocker.get('severity', 'info')
                blocker_info = {
                    'name': blocker.get('name', 'Unknown'),
                    'category': blocker.get('category', 'UNKNOWN'),
                    'message': blocker.get('message', ''),
                    'details': blocker.get('details', {})
                }
                
                if severity == 'critical':
                    critical_blockers.append(blocker_info)
                elif severity == 'warning':
                    warning_blockers.append(blocker_info)
                else:
                    info_blockers.append(blocker_info)
            
            # Add volatility halt status if bot has volatility_monitor
            volatility_data = {}
            if hasattr(bot, 'volatility_monitor') and hasattr(bot, 'loop'):
                try:
                    import asyncio
                    coro = bot.volatility_monitor.ask("GET_STATUS", {}, timeout=2.0)
                    future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                    vol_status = future.result(timeout=3.0)
                    
                    if vol_status.get("status") == "ok":
                        volatility_data = {
                            'volatility_halted': vol_status.get("halt_active", False),
                            'iv': vol_status.get("iv", 0),
                            'rv': vol_status.get("rv", 0),
                            'spread': vol_status.get("spread", 0),
                            'halt_duration': vol_status.get("halt_duration", 0),
                            'halt_reason': vol_status.get("halt_reason")
                        }
                        
                        # Add cancelled order price and current price from bot
                        if hasattr(bot, 'halt_cancelled_order_price'):
                            volatility_data['cancelled_order_price'] = bot.halt_cancelled_order_price
                        if hasattr(bot, 'current_price'):
                            volatility_data['current_price'] = bot.current_price
                        if hasattr(bot, 'grid_calc'):
                            volatility_data['grid_step'] = bot.grid_calc.step
                except Exception as e:
                    log.debug(f"Could not fetch volatility status: {e}")
            
            return {
                'active': True,
                'trading_allowed': blocker_data.get('trading_allowed', False),
                'total_blockers': blocker_data.get('total_blockers', 0),
                'critical_blockers': critical_blockers,
                'warning_blockers': warning_blockers,
                'info_blockers': info_blockers,
                'safety_config': safety_config,
                'guardian_status': guardian_status,
                'timestamp': blocker_data.get('timestamp'),
                **volatility_data  # Merge volatility data
            }
            
        except Exception as e:
            log.debug(f"Error getting trading condition: {e}")
            return {'active': False, 'error': str(e)}
    
    def _get_opportunistic_recovery(self, bot) -> Dict[str, Any]:
        """Get opportunistic recovery statistics"""
        try:
            import asyncio
            import concurrent.futures
            from config.loader import get_config
            
            # Check if opportunistic recovery is enabled in config
            config = get_config()
            recovery_enabled = False
            try:
                vol_config = config.get('safety', {}).get('volatility', {})
                opp_recovery = vol_config.get('opportunistic_recovery', {})
                recovery_enabled = opp_recovery.get('enabled', False)
            except (AttributeError, KeyError):
                recovery_enabled = False
            
            # Get stats from PositionActor
            if hasattr(bot, 'position_actor') and hasattr(bot, 'loop'):
                try:
                    coro = bot.position_actor.ask("GET_STATE", {}, timeout=2.0)
                    future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                    state = future.result(timeout=3.0)
                    
                    stats = state.get("opportunistic_recovery_stats", {})
                    positions = state.get("open_tranches", [])
                    
                    # Filter opportunistic positions
                    opp_positions = [
                        {
                            "position_id": p.get("position_id"),
                            "grid_entry": p.get("entry_price"),
                            "actual_entry": p.get("actual_entry", p.get("entry_price")),
                            "saved_capital": p.get("saved_capital", 0),
                            "tp_price": p.get("tp_price"),
                            "size": p.get("size"),
                            "timestamp": p.get("timestamp")
                        }
                        for p in positions
                        if p.get("is_opportunistic", False)
                    ]
                    
                    # Get recent recovery events from EventStore
                    recent_recoveries = []
                    if hasattr(bot, 'event_store'):
                        try:
                            events = bot.event_store.get_events_by_type(
                                "opportunistic_recovery_started",
                                limit=10
                            )
                            recent_recoveries = [
                                {
                                    "timestamp": e.timestamp,
                                    "recovery_type": e.data.get("recovery_type"),
                                    "correlation_id": e.correlation_id
                                }
                                for e in events
                            ]
                        except Exception as e:
                            log.debug(f"Could not fetch recent recoveries: {e}")
                    
                    return {
                        'active': True,
                        'enabled': recovery_enabled,
                        'total_recoveries': stats.get("total_recoveries", 0),
                        'total_positions_recovered': stats.get("total_positions_recovered", 0),
                        'total_capital_saved': stats.get("total_capital_saved", 0.0),
                        'startup_recoveries': stats.get("startup_recoveries", 0),
                        'volatility_recoveries': stats.get("volatility_recoveries", 0),
                        'last_recovery_time': stats.get("last_recovery_time"),
                        'current_opportunistic_positions': opp_positions,
                        'recent_recoveries': recent_recoveries
                    }
                    
                except Exception as e:
                    log.debug(f"Error getting stats from bot: {e}")
            
            # Fallback to zero stats if bot not available
            return {
                'active': False,
                'enabled': recovery_enabled,
                'total_recoveries': 0,
                'total_positions_recovered': 0,
                'total_capital_saved': 0.0,
                'startup_recoveries': 0,
                'volatility_recoveries': 0,
                'last_recovery_time': None,
                'current_opportunistic_positions': [],
                'recent_recoveries': []
            }
            
        except Exception as e:
            log.debug(f"Error getting opportunistic recovery: {e}")
            return {'active': False, 'error': str(e)}
    
    def _get_guardian_status(self) -> Dict[str, Any]:
        """Get guardian bot status from health file"""
        try:
            from pathlib import Path
            import json
            
            # Check for guardian health file
            guardian_health_file = Path('bot/guardian/.guardian_health.json')
            
            if not guardian_health_file.exists():
                return {'running': False}
            
            with open(guardian_health_file, 'r') as f:
                health_data = json.load(f)
            
            # Check if guardian is recently active (within last 60 seconds)
            import time
            last_check = health_data.get('last_check_timestamp', 0)
            is_active = (time.time() - last_check) < 60
            
            return {
                'running': is_active,
                'last_check': health_data.get('last_check_time'),
                'risk_level': health_data.get('risk_level', 'unknown'),
                'total_positions': health_data.get('total_positions', 0),
                'total_loss_inr': health_data.get('total_loss_inr', 0)
            }
            
        except Exception as e:
            log.debug(f"Error getting guardian status: {e}")
            return {'running': False}
