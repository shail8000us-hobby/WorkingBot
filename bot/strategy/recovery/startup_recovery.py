"""
Startup Recovery Engine

Handles recovery when bot starts and market has moved past grid levels.
Executes ONCE per bot session with single-execution guarantee.

Created: November 20, 2025
"""

from pathlib import Path
from typing import List, Tuple
import time
from .base_recovery_engine import BaseRecoveryEngine


class StartupRecoveryEngine(BaseRecoveryEngine):
    """
    Startup recovery with single-execution guarantee.
    """
    
    def __init__(self, bot, config, logger):
        super().__init__(bot, config, logger)
        self.has_executed = False
        self.execution_timestamp = None
        
        # Check if enabled in config
        try:
            self.enabled = config.safety.volatility.opportunistic_recovery.enabled
        except AttributeError:
            self.enabled = True  # Default to enabled
    
    async def should_trigger(self) -> Tuple[bool, str]:
        """
        Trigger only once at startup.
        """
        # Already executed check
        if self.has_executed:
            return False, "already_executed_this_session"
        
        # Check if executed recently (within 1 hour)
        if self.execution_timestamp:
            elapsed = time.time() - self.execution_timestamp
            if elapsed < 3600:  # 1 hour
                return False, f"executed_{int(elapsed)}s_ago"
        
        # Check market conditions
        try:
            current_price = await self.bot.get_current_price()
            first_grid = self._calculate_first_grid_level()
            
            if self.bot.mode == "LONG":
                should_trigger = current_price < first_grid
                reason = f"market_below_first_grid (${current_price:,.0f} < ${first_grid:,.0f})"
            else:
                should_trigger = current_price > first_grid
                reason = f"market_above_first_grid (${current_price:,.0f} > ${first_grid:,.0f})"
            
            return should_trigger, reason
        except Exception as e:
            self.logger.error(f"Error checking trigger conditions: {e}")
            return False, f"error: {str(e)}"
    
    async def calculate_missed_grids(self) -> List[float]:
        """
        Calculate missed grids with safety limits.
        """
        try:
            current_price = await self.bot.get_current_price()
            reference = self.config.grid.geometry.reference
            step = self.config.grid.geometry.step
            lower = self.config.grid.geometry.lower
            upper = self.config.grid.geometry.upper
            
            # Get max grids from config
            try:
                max_grids = self.config.safety.volatility.opportunistic_recovery.max_grids
            except AttributeError:
                max_grids = 3  # Default
            
            missed = []
            
            if self.bot.mode == "LONG":
                grid = reference - step
                while grid > current_price and grid >= lower and len(missed) < max_grids:
                    missed.append(grid)
                    grid -= step
            else:
                grid = reference + step
                while grid < current_price and grid <= upper and len(missed) < max_grids:
                    missed.append(grid)
                    grid += step
            
            return missed
        except Exception as e:
            self.logger.error(f"Error calculating missed grids: {e}")
            return []
    
    def get_state_file_path(self) -> Path:
        return Path("data/recovery/startup_recovery_state.json")
    
    async def execute_recovery(self) -> dict:
        """Execute with single-execution guarantee"""
        result = await super().execute_recovery()
        
        if result['success']:
            self.has_executed = True
            self.execution_timestamp = time.time()
            self._save_state()
        
        return result
    
    def _calculate_first_grid_level(self) -> float:
        """Calculate the first grid level based on mode"""
        reference = self.config.grid.geometry.reference
        step = self.config.grid.geometry.step
        
        if self.bot.mode == "LONG":
            return reference - step
        else:
            return reference + step
    
    def _save_state(self):
        """Override to save execution state"""
        try:
            import json
            from datetime import datetime
            
            state = {
                'recovered_grids': list(self.recovered_grids),
                'failed_grids': self.failed_grids,
                'health_metrics': self.health_metrics,
                'has_executed': self.has_executed,
                'execution_timestamp': self.execution_timestamp,
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
        """Override to load execution state"""
        try:
            import json
            
            state_file = self.get_state_file_path()
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.recovered_grids = set(state.get('recovered_grids', []))
                    self.failed_grids = state.get('failed_grids', {})
                    self.health_metrics.update(state.get('health_metrics', {}))
                    self.has_executed = state.get('has_executed', False)
                    self.execution_timestamp = state.get('execution_timestamp')
        except Exception as e:
            self.logger.warning(f"Failed to load recovery state: {e}")
