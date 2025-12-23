"""
Multi-strategy manager.
Manages multiple trading strategies with inheritance and overrides.
"""

from typing import Dict, List, Optional
from pathlib import Path
from copy import deepcopy

from config.models import RootConfig, StrategyOverride
from config.loader import get_config
from config.env_mapping import get_nested_value, set_nested_value


class StrategyManager:
    """Manage multiple trading strategies"""
    
    def __init__(self, config: Optional[RootConfig] = None):
        """Initialize strategy manager
        
        Args:
            config: Root configuration (auto-loaded if None)
        """
        self.base_config = config or get_config()
        self.strategies: Dict[str, RootConfig] = {}
        self.active_strategies: List[str] = []
        
        # Build all defined strategies
        self._build_strategies()
        
    def _build_strategies(self):
        """Build all defined strategies from config"""
        # Add base strategy if strategies are defined
        if self.base_config.strategies:
            # Base strategy is the default config
            self.strategies['base'] = self.base_config
            
            # Build each strategy override
            for strategy_def in self.base_config.strategies:
                if strategy_def.enabled:
                    strategy_config = self._build_strategy(strategy_def)
                    self.strategies[strategy_def.name] = strategy_config
        
        # Load active strategies
        self.active_strategies = self.base_config.active_strategies.copy()
        
    def _build_strategy(self, strategy_def: StrategyOverride) -> RootConfig:
        """Build complete strategy config with inheritance
        
        Args:
            strategy_def: Strategy override definition
            
        Returns:
            Complete RootConfig for strategy
        """
        # Start with base config
        if strategy_def.extends and strategy_def.extends in self.strategies:
            # Inherit from another strategy
            base = self.strategies[strategy_def.extends]
        else:
            # Inherit from root config
            base = self.base_config
        
        # Deep copy base config dict
        config_dict = deepcopy(base.dict())
        
        # Apply overrides
        for path, value in strategy_def.overrides.items():
            set_nested_value(config_dict, path, value)
        
        # Create new RootConfig instance
        return RootConfig(**config_dict)
        
    def get_strategy(self, name: str) -> RootConfig:
        """Get strategy configuration by name
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy configuration
            
        Raises:
            KeyError: If strategy not found
        """
        if name not in self.strategies:
            raise KeyError(f"Strategy not found: {name}")
        return self.strategies[name]
        
    def list_strategies(self) -> List[str]:
        """List all available strategies
        
        Returns:
            List of strategy names
        """
        return list(self.strategies.keys())
        
    def get_active_strategies(self) -> List[RootConfig]:
        """Get all active strategy configurations
        
        Returns:
            List of active strategy configs
        """
        return [self.strategies[name] for name in self.active_strategies if name in self.strategies]
        
    def activate_strategy(self, name: str):
        """Activate a strategy
        
        Args:
            name: Strategy name
            
        Raises:
            KeyError: If strategy not found
        """
        if name not in self.strategies:
            raise KeyError(f"Strategy not found: {name}")
        
        if name not in self.active_strategies:
            self.active_strategies.append(name)
            
    def deactivate_strategy(self, name: str):
        """Deactivate a strategy
        
        Args:
            name: Strategy name
        """
        if name in self.active_strategies:
            self.active_strategies.remove(name)
            
    def is_active(self, name: str) -> bool:
        """Check if strategy is active
        
        Args:
            name: Strategy name
            
        Returns:
            True if active, False otherwise
        """
        return name in self.active_strategies
        
    def add_strategy(self, strategy_def: StrategyOverride):
        """Add new strategy definition
        
        Args:
            strategy_def: Strategy override definition
        """
        strategy_config = self._build_strategy(strategy_def)
        self.strategies[strategy_def.name] = strategy_config
        
        # Add to base config strategies list
        if strategy_def not in self.base_config.strategies:
            self.base_config.strategies.append(strategy_def)
            
    def remove_strategy(self, name: str):
        """Remove strategy
        
        Args:
            name: Strategy name
        """
        # Deactivate first
        self.deactivate_strategy(name)
        
        # Remove from strategies dict
        if name in self.strategies:
            del self.strategies[name]
        
        # Remove from base config
        self.base_config.strategies = [
            s for s in self.base_config.strategies if s.name != name
        ]
        
    def get_strategy_summary(self, name: str) -> Dict:
        """Get strategy summary for display
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy summary dict
        """
        if name not in self.strategies:
            raise KeyError(f"Strategy not found: {name}")
        
        config = self.strategies[name]
        strategy_def = next((s for s in self.base_config.strategies if s.name == name), None)
        
        return {
            'name': name,
            'active': self.is_active(name),
            'symbol': config.bot.symbol,
            'mode': config.bot.mode.value,
            'grid_lower': config.grid.geometry.lower,
            'grid_upper': config.grid.geometry.upper,
            'grid_step': config.grid.geometry.step,
            'lot_size': config.grid.limits.lot_size,
            'max_positions': config.grid.limits.max_open_positions,
            'description': strategy_def.description if strategy_def else None,
            'extends': strategy_def.extends if strategy_def else None,
        }


class CapitalAllocator:
    """Allocate capital across multiple strategies"""
    
    def __init__(self, total_capital: float):
        """Initialize capital allocator
        
        Args:
            total_capital: Total available capital
        """
        self.total_capital = total_capital
        self.allocations: Dict[str, float] = {}
        self.reserved: float = 0
        
    def allocate_equal(self, strategies: List[str]):
        """Allocate capital equally across strategies
        
        Args:
            strategies: List of strategy names
        """
        available = self.total_capital - self.reserved
        per_strategy = available / len(strategies) if strategies else 0
        
        self.allocations = {name: per_strategy for name in strategies}
        
    def allocate_weighted(self, weights: Dict[str, float]):
        """Allocate capital by weights
        
        Args:
            weights: Dict of strategy_name -> weight
        """
        available = self.total_capital - self.reserved
        total_weight = sum(weights.values())
        
        if total_weight == 0:
            self.allocations = {name: 0 for name in weights.keys()}
            return
        
        self.allocations = {
            name: available * (weight / total_weight)
            for name, weight in weights.items()
        }
        
    def allocate_fixed(self, allocations: Dict[str, float]):
        """Allocate fixed amounts to strategies
        
        Args:
            allocations: Dict of strategy_name -> amount
            
        Raises:
            ValueError: If total exceeds available capital
        """
        total = sum(allocations.values())
        available = self.total_capital - self.reserved
        
        if total > available:
            raise ValueError(f"Total allocation ({total}) exceeds available capital ({available})")
        
        self.allocations = allocations.copy()
        
    def get_allocation(self, strategy: str) -> float:
        """Get allocated capital for strategy
        
        Args:
            strategy: Strategy name
            
        Returns:
            Allocated capital amount
        """
        return self.allocations.get(strategy, 0)
        
    def reserve_capital(self, amount: float):
        """Reserve capital (emergency fund)
        
        Args:
            amount: Amount to reserve
            
        Raises:
            ValueError: If amount exceeds total capital
        """
        if amount > self.total_capital:
            raise ValueError(f"Reserve amount ({amount}) exceeds total capital ({self.total_capital})")
        
        self.reserved = amount
        
    def get_available_capital(self) -> float:
        """Get total available capital (after reservations)
        
        Returns:
            Available capital amount
        """
        return self.total_capital - self.reserved
        
    def get_allocated_capital(self) -> float:
        """Get total allocated capital
        
        Returns:
            Sum of all allocations
        """
        return sum(self.allocations.values())
        
    def get_unallocated_capital(self) -> float:
        """Get unallocated capital
        
        Returns:
            Unallocated capital amount
        """
        return self.get_available_capital() - self.get_allocated_capital()
