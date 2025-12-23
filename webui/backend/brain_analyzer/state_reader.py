"""
Bot State Reader Module

Single Responsibility: Read bot's CURRENT STATE in real-time.

Reads:
- runtime_state.json (emergency stop, trading mode)
- .volatility_status.json (IV, RV, is_safe, thresholds)
- .volatility_halt.json (halt state, missed levels)
- positions.json (current positions, pending orders)
- config.yaml (grid parameters)

This is used to ANNOTATE the flowchart with REAL data.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


class BotStateReader:
    """
    Reads bot's current state to annotate decision flowchart.
    
    Provides REAL-TIME data:
    - Is emergency stop active?
    - Current IV/RV values vs thresholds
    - Is volatility safe or unsafe? Why?
    - Current positions and pending orders
    - Next grid levels (buy/sell prices)
    - Missed levels during halt
    """
    
    def __init__(self, bot_root: Path):
        """
        Initialize state reader.
        
        Args:
            bot_root: Path to bot root directory
        """
        self.bot_root = Path(bot_root)
        self.state_dir = self.bot_root / 'bot' / 'state'
        self.config_file = self.bot_root / 'config.yaml'
        
        log.debug(f"BotStateReader initialized: {self.state_dir}")
    
    def read_runtime_state(self) -> Dict[str, Any]:
        """Read runtime_state.json for emergency stop status."""
        try:
            state_file = self.state_dir / 'runtime_state.json'
            if state_file.exists():
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    return {
                        'emergency_stop': data.get('emergency_stop', False),
                        'trading_enabled': data.get('trading_enabled', True),
                        'last_update': data.get('last_update_time')
                    }
        except Exception as e:
            log.error(f"Error reading runtime_state: {e}")
        
        return {'emergency_stop': False, 'trading_enabled': True}
    
    def read_volatility_status(self) -> Dict[str, Any]:
        """Read .volatility_status.json for current IV/RV values."""
        try:
            vol_file = self.bot_root / '.volatility_status.json'
            if vol_file.exists():
                with open(vol_file, 'r') as f:
                    data = json.load(f)
                    
                    is_safe = data.get('is_safe', True)
                    iv = data.get('iv') or data.get('current_iv')
                    rv = data.get('rv') or data.get('current_rv')
                    thresholds = data.get('thresholds', {})
                    max_iv = thresholds.get('max_iv') or data.get('max_iv_threshold')
                    max_rv = thresholds.get('max_rv') or data.get('max_rv_threshold')
                    violation = data.get('violation_reason', '')
                    
                    return {
                        'is_safe': is_safe,
                        'current_iv': iv,
                        'current_rv': rv,
                        'max_iv': max_iv,
                        'max_rv': max_rv,
                        'violation_reason': violation,
                        'status': 'SAFE' if is_safe else 'UNSAFE'
                    }
        except Exception as e:
            log.error(f"Error reading volatility status: {e}")
        
        return {
            'is_safe': True,
            'status': 'UNKNOWN',
            'violation_reason': 'No data'
        }
    
    def read_volatility_halt(self) -> Dict[str, Any]:
        """Read .volatility_halt.json for halt state and missed levels."""
        try:
            halt_file = self.bot_root / '.volatility_halt.json'
            if halt_file.exists():
                with open(halt_file, 'r') as f:
                    data = json.load(f)
                    return {
                        'is_halted': data.get('is_halted', False),
                        'halt_time': data.get('halt_timestamp'),
                        'missed_levels': data.get('missed_levels', []),
                        'pending_buy_at_halt': data.get('pending_buy_at_halt')
                    }
        except Exception as e:
            log.error(f"Error reading volatility halt: {e}")
        
        return {'is_halted': False, 'missed_levels': []}
    
    def read_positions(self) -> Dict[str, Any]:
        """Read positions.json for current positions and orders."""
        try:
            pos_file = self.state_dir / 'positions.json'
            if pos_file.exists():
                with open(pos_file, 'r') as f:
                    data = json.load(f)
                    positions = data.get('positions', [])
                    pending_buy = data.get('pending_buy_order')
                    
                    return {
                        'open_positions': len(positions),
                        'positions': positions,
                        'pending_buy_price': pending_buy.get('price') if pending_buy else None,
                        'pending_buy_id': pending_buy.get('order_id') if pending_buy else None
                    }
        except Exception as e:
            log.error(f"Error reading positions: {e}")
        
        return {'open_positions': 0, 'positions': [], 'pending_buy_price': None}
    
    def _read_grid_config(self) -> Dict[str, Any]:
        """Read config.yaml for grid parameters."""
        try:
            if self.config_file.exists():
                config = {}
                with open(self.config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip().strip('"').strip("'")
                
                # Parse with defaults - use grid.* parameters from config.yaml
                ref_price = float(config.get('GRIDBOT_REF') or config.get('REFERENCE_PRICE') or config.get('ref') or 110000)
                grid_step = float(config.get('GRIDBOT_STEP') or config.get('GRID_STEP') or config.get('step') or 1000)
                max_pos = int(config.get('GRIDBOT_MAX_OPEN') or config.get('MAX_OPEN_POSITIONS') or config.get('max_open') or 3)
                lot_size = int(config.get('GRIDBOT_LOT') or config.get('LOT') or 1)
                max_iv = float(config.get('VOLATILITY_MAX_IV') or config.get('MAX_IV_THRESHOLD') or 35)
                max_rv = float(config.get('VOLATILITY_MAX_RV') or config.get('MAX_RV_THRESHOLD') or 40)
                
                log.debug(f"Config read: ref={ref_price}, step={grid_step}, max={max_pos}")
                
                return {
                    'reference_price': ref_price,
                    'grid_step': grid_step,
                    'max_positions': max_pos,
                    'lot_size': lot_size,
                    'max_iv': max_iv,
                    'max_rv': max_rv
                }
        except Exception as e:
            log.error(f"Error reading grid config: {e}")
            import traceback
            log.error(traceback.format_exc())
        
        return {
            'reference_price': 110000,
            'grid_step': 1000,
            'max_positions': 3,
            'lot_size': 1,
            'max_iv': 35,
            'max_rv': 40
        }
    
    def get_complete_state(self) -> Dict[str, Any]:
        """
        Get complete bot state for flowchart annotation.
        
        Returns comprehensive state with all decision-making data.
        """
        try:
            runtime = self.read_runtime_state()
            volatility = self.read_volatility_status()
            halt = self.read_volatility_halt()
            positions = self.read_positions()
            config = self.read_grid_config()
            
            # Calculate next grid level
            next_buy_price = None
            if positions['positions']:
                lowest_entry = min([p.get('entry_price', 0) for p in positions['positions']])
                next_buy_price = lowest_entry - config['grid_step']
            else:
                next_buy_price = config['reference_price'] - config['grid_step']
            
            return {
                'timestamp': __import__('time').time(),
                'emergency_stop': runtime['emergency_stop'],
                'trading_enabled': runtime['trading_enabled'],
                'volatility': volatility,
                'halt': halt,
                'positions': positions,
                'config': config,
                'next_buy_price': next_buy_price,
                'max_positions_reached': positions['open_positions'] >= config['max_positions']
            }
            
        except Exception as e:
            log.error(f"Error getting complete state: {e}")
            return {}

