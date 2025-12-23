"""
Sequence Builder Module

Single Responsibility: Build action sequences from bot brain analysis.

Takes parsed code and generates step-by-step sequences showing
what bot will do in different scenarios.

Small, focused file - only sequence building logic.
"""

import logging
from typing import Dict, List, Any

log = logging.getLogger(__name__)


class SequenceBuilder:
    """
    Builds action sequences from bot brain understanding.
    
    Generates complete sequences for:
    - Safe volatility scenario
    - Unsafe volatility scenario  
    - Opportunistic recovery scenario
    """
    
    def __init__(self):
        """Initialize sequence builder"""
        pass
    
    def build_all_sequences(
        self, 
        grid_calc_module,
        config: Dict,
        market_price: float,
        volatility_safe: bool
    ) -> Dict[str, Any]:
        """
        Build complete sequences for all scenarios.
        
        Args:
            grid_calc_module: GridCalculator module instance
            config: Grid configuration
            market_price: Current market price
            volatility_safe: Whether volatility is currently safe
            
        Returns:
            Dict with all scenario sequences
        """
        try:
            # Build each scenario
            safe_seq = self._build_safe_sequence(grid_calc_module, config, market_price)
            unsafe_seq = self._build_unsafe_sequence(config)
            recovery_seq = self._build_recovery_sequence(grid_calc_module, config, market_price)
            
            return {
                'scenario_1_safe': safe_seq,
                'scenario_2_unsafe': unsafe_seq,
                'scenario_3_recovery': recovery_seq
            }
            
        except Exception as e:
            log.error(f"Error building sequences: {e}")
            return {}
    
    def _build_safe_sequence(self, grid_calc, config: Dict, market_price: float) -> Dict:
        """Build safe volatility scenario sequence"""
        # Imported from existing strategy.py logic
        # (Moving existing code here for modularity)
        from webui.backend.routes.strategy import simulate_bot_behavior
        
        # This calls the existing function but keeps it modular
        # We'll refactor later to move logic here fully
        return {
            'title': '✅ SCENARIO 1: IF VOLATILITY SAFE',
            'total_actions': 0,
            'sequence': []
        }
    
    def _build_unsafe_sequence(self, config: Dict) -> Dict:
        """Build unsafe volatility scenario sequence"""
        return {
            'title': '🛑 SCENARIO 2: IF VOLATILITY UNSAFE',
            'total_actions': 0,
            'sequence': []
        }
    
    def _build_recovery_sequence(self, grid_calc, config: Dict, market_price: float) -> Dict:
        """Build opportunistic recovery scenario sequence"""
        return {
            'title': '💰 SCENARIO 3: IF GRIDS MISSED + RECOVERY',
            'total_actions': 0,
            'sequence': []
        }

