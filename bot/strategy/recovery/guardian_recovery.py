"""
Guardian Recovery Engine

Handles recovery when Guardian resumes trading after a halt.
Triggers on Guardian STOP → GO state transitions.

Created: November 20, 2025
"""

from pathlib import Path
from typing import List, Tuple
import time
import sqlite3
from .base_recovery_engine import BaseRecoveryEngine


class GuardianRecoveryEngine(BaseRecoveryEngine):
    """
    Guardian recovery on halt/resume transitions.
    """
    
    def __init__(self, bot, config, logger):
        super().__init__(bot, config, logger)
        self.previous_guardian_state = None
        self.halt_start_price = None
        self.enabled = True  # Always enabled (critical)
    
    async def should_trigger(self) -> Tuple[bool, str]:
        """
        Trigger when Guardian state changes from STOP → GO
        and market has moved during halt.
        """
        try:
            current_state = await self._get_guardian_state()
            
            # Detect STOP → GO transition
            if self.previous_guardian_state == "STOP" and current_state == "GO":
                self.logger.info("[GuardianRecovery] Guardian resumed")
                
                # Update state
                self.previous_guardian_state = current_state
                
                # Check if market moved during halt
                if self.halt_start_price:
                    current_price = await self.bot.get_current_price()
                    price_change = abs(current_price - self.halt_start_price)
                    grid_step = self.config.grid.geometry.step
                    
                    if price_change > grid_step:
                        return True, f"market_moved_${price_change:.0f}_during_halt"
                    else:
                        return False, f"market_moved_only_${price_change:.0f}"
                
                return True, "guardian_resumed"
            
            # Track halt start
            if current_state == "STOP" and self.previous_guardian_state != "STOP":
                self.halt_start_price = await self.bot.get_current_price()
                self.logger.info(f"[GuardianRecovery] Guardian halted at ${self.halt_start_price:,.0f}")
            
            # Update state
            self.previous_guardian_state = current_state
            return False, "no_state_transition"
        
        except Exception as e:
            self.logger.error(f"Error checking Guardian state: {e}")
            return False, f"error: {str(e)}"
    
    async def calculate_missed_grids(self) -> List[float]:
        """
        Calculate all grids between halt price and current price.
        
        JAN 29 2026: Fixed to use grid-aligned calculation.
        
        For LONG mode with halt at 100 and current at 81 (step=5):
        - Missed grids: 95, 90, 85 (from halt, going towards current)
        - TP orders will be grid-aligned: 90→95, 85→90, etc.
        """
        if not self.halt_start_price:
            return []
        
        try:
            current_price = await self.bot.get_current_price()
            step = self.config.grid.geometry.step
            lower = self.config.grid.geometry.lower
            upper = self.config.grid.geometry.upper
            reference = self.config.grid.geometry.reference
            
            # Get max grids from config (default 5 for Guardian)
            try:
                max_grids = getattr(self.config.safety.volatility.opportunistic_recovery, 'max_grids', 5)
            except AttributeError:
                max_grids = 5
            
            # Snap halt_start_price to nearest grid level
            # This ensures we calculate from a valid grid point
            snapped_halt = self._snap_to_grid(self.halt_start_price, reference, step)
            
            missed = []
            
            if self.bot.mode == "LONG":
                # Price dropped during halt - need to buy missed grids
                if current_price < snapped_halt:
                    grid = snapped_halt - step
                    while grid > current_price and grid >= lower and len(missed) < max_grids:
                        missed.append(grid)
                        grid -= step
            else:  # SHORT
                # Price rose during halt - need to sell missed grids
                if current_price > snapped_halt:
                    grid = snapped_halt + step
                    while grid < current_price and grid <= upper and len(missed) < max_grids:
                        missed.append(grid)
                        grid += step
            
            self.logger.info(f"[GuardianRecovery] Found {len(missed)} missed grids (max: {max_grids})")
            self.logger.info(f"  Halt: ${self.halt_start_price:,.0f} (snapped: ${snapped_halt:,.0f})")
            self.logger.info(f"  Current: ${current_price:,.0f}")
            if missed:
                self.logger.info(f"  Missed grids: {[f'${g:,.0f}' for g in missed]}")
            
            return missed
        except Exception as e:
            self.logger.error(f"Error calculating missed grids: {e}")
            return []
    
    def _snap_to_grid(self, price: float, reference: float, step: float) -> float:
        """
        Snap a price to the nearest valid grid level.
        
        For reference=100, step=5:
        - 98 → 100
        - 93 → 95
        - 101 → 100
        """
        # Calculate number of steps from reference
        steps_from_ref = round((price - reference) / step)
        snapped = reference + (steps_from_ref * step)
        return snapped
    
    def get_state_file_path(self) -> Path:
        return Path("data/recovery/guardian_recovery_state.json")
    
    async def _get_guardian_state(self) -> str:
        """
        Get current Guardian state from database.
        Returns: "GO" or "STOP"
        """
        try:
            conn = sqlite3.connect('data/volatility.db')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT state FROM guardian_state 
                ORDER BY timestamp DESC LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else "GO"
        except Exception as e:
            self.logger.error(f"Guardian state query failed: {e}")
            return "GO"  # Default to GO on error (safe)
    
    def _save_state(self):
        """Override to save Guardian-specific state"""
        try:
            import json
            from datetime import datetime
            
            state = {
                'recovered_grids': list(self.recovered_grids),
                'failed_grids': self.failed_grids,
                'health_metrics': self.health_metrics,
                'previous_guardian_state': self.previous_guardian_state,
                'halt_start_price': self.halt_start_price,
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
    
    def _load_state(self):
        """Override to load Guardian-specific state"""
        try:
            import json
            
            state_file = self.get_state_file_path()
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.recovered_grids = set(state.get('recovered_grids', []))
                    self.failed_grids = state.get('failed_grids', {})
                    self.health_metrics.update(state.get('health_metrics', {}))
                    self.previous_guardian_state = state.get('previous_guardian_state')
                    self.halt_start_price = state.get('halt_start_price')
        except Exception as e:
            self.logger.warning(f"Failed to load recovery state: {e}")
