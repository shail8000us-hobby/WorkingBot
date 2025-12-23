"""
Multi-strategy execution tests.
Tests StrategyManager, CapitalAllocator, strategy inheritance.
"""

import pytest
from copy import deepcopy

from config.models import RootConfig, StrategyOverride
from config.strategy_manager import StrategyManager, CapitalAllocator


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def base_config(complete_config_dict):
    """Base configuration for testing - uses complete config from conftest"""
    return complete_config_dict


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CAPITAL ALLOCATOR
# ═══════════════════════════════════════════════════════════════════════════

def test_equal_allocation():
    """Test equal capital allocation"""
    allocator = CapitalAllocator(total_capital=100000)
    
    allocator.allocate_equal(['s1', 's2', 's3'])
    
    assert allocator.get_allocation('s1') == pytest.approx(33333.33, rel=0.01)
    assert allocator.get_allocation('s2') == pytest.approx(33333.33, rel=0.01)
    assert allocator.get_allocation('s3') == pytest.approx(33333.33, rel=0.01)
    
    # Should have minimal unallocated due to rounding
    assert allocator.get_unallocated_capital() < 1


def test_weighted_allocation():
    """Test weighted capital allocation"""
    allocator = CapitalAllocator(total_capital=100000)
    
    allocator.allocate_weighted({
        's1': 0.5,
        's2': 0.3,
        's3': 0.2
    })
    
    assert allocator.get_allocation('s1') == 50000
    assert allocator.get_allocation('s2') == 30000
    assert allocator.get_allocation('s3') == 20000
    assert allocator.get_unallocated_capital() == 0


def test_fixed_allocation():
    """Test fixed capital allocation"""
    allocator = CapitalAllocator(total_capital=100000)
    
    allocator.allocate_fixed({
        's1': 40000,
        's2': 25000,
        's3': 15000
    })
    
    assert allocator.get_allocation('s1') == 40000
    assert allocator.get_allocation('s2') == 25000
    assert allocator.get_allocation('s3') == 15000
    assert allocator.get_unallocated_capital() == 20000


def test_capital_reservation():
    """Test capital reservation"""
    allocator = CapitalAllocator(total_capital=100000)
    
    # Reserve 20%
    allocator.reserve_capital(20000)
    
    assert allocator.get_available_capital() == 80000
    assert allocator.reserved_capital == 20000
    
    # Allocate from available
    allocator.allocate_equal(['s1', 's2'])
    
    assert allocator.get_allocation('s1') == pytest.approx(40000, rel=0.01)
    assert allocator.get_allocation('s2') == pytest.approx(40000, rel=0.01)


def test_over_allocation_error():
    """Test that over-allocation raises error"""
    allocator = CapitalAllocator(total_capital=100000)
    
    with pytest.raises(ValueError, match="Total allocation.*exceeds available"):
        allocator.allocate_fixed({
            's1': 60000,
            's2': 50000
        })


def test_invalid_weights_error():
    """Test that invalid weights raise error"""
    allocator = CapitalAllocator(total_capital=100000)
    
    with pytest.raises(ValueError, match="Weights sum.*must equal 1.0"):
        allocator.allocate_weighted({
            's1': 0.6,
            's2': 0.6  # Sum = 1.2
        })


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STRATEGY MANAGER
# ═══════════════════════════════════════════════════════════════════════════

def test_strategy_creation(base_config):
    """Test creating strategy manager"""
    config = RootConfig(**base_config)
    manager = StrategyManager(config)
    
    assert manager.base_config == config
    assert len(manager.strategies) == 0


def test_add_strategy(base_config):
    """Test adding a strategy"""
    config = RootConfig(**base_config)
    
    # Add strategy to config
    strategy = StrategyOverride(
        name='aggressive',
        description='Aggressive strategy',
        overrides={
            'grid.geometry.step': 200,
            'grid.limits.lot_size': 5
        }
    )
    config.strategies = [strategy]
    
    manager = StrategyManager(config)
    assert len(manager.strategies) == 1
    assert 'aggressive' in manager.strategies


def test_strategy_inheritance(base_config):
    """Test that strategy inherits base config"""
    config = RootConfig(**base_config)
    
    # Add override strategy
    strategy = StrategyOverride(
        name='modified',
        description='Modified strategy',
        overrides={
            'grid.geometry.step': 300
        }
    )
    config.strategies = [strategy]
    
    manager = StrategyManager(config)
    modified_config = manager.get_strategy('modified')
    
    # Should have overridden value
    assert modified_config.grid.geometry.step == 300
    
    # Should keep base values
    assert modified_config.grid.geometry.lower == 90000
    assert modified_config.grid.geometry.upper == 110000
    assert modified_config.bot.symbol == 'BTCUSD'


def test_strategy_deep_override(base_config):
    """Test deep nested overrides"""
    config = RootConfig(**base_config)
    
    strategy = StrategyOverride(
        name='deep_test',
        description='Deep override test',
        overrides={
            'grid.geometry.step': 400,
            'grid.limits.lot_size': 3,
            'bot.mode': 'SHORT'
        }
    )
    config.strategies = [strategy]
    
    manager = StrategyManager(config)
    deep_config = manager.get_strategy('deep_test')
    
    # All overrides should apply
    assert deep_config.grid.geometry.step == 400
    assert deep_config.grid.limits.lot_size == 3
    assert deep_config.bot.mode == 'SHORT'


def test_get_all_strategies(base_config):
    """Test getting all strategies"""
    config = RootConfig(**base_config)
    
    # Add multiple strategies
    config.strategies = [
        StrategyOverride(
            name='s1',
            description='Strategy 1',
            overrides={'grid.geometry.step': 200}
        ),
        StrategyOverride(
            name='s2',
            description='Strategy 2',
            overrides={'grid.geometry.step': 300}
        ),
        StrategyOverride(
            name='s3',
            description='Strategy 3',
            overrides={'grid.geometry.step': 400}
        )
    ]
    
    manager = StrategyManager(config)
    all_strategies = manager.get_all_strategies()
    
    assert len(all_strategies) == 3
    assert 's1' in all_strategies
    assert 's2' in all_strategies
    assert 's3' in all_strategies


def test_strategy_activation(base_config):
    """Test activating strategies"""
    config = RootConfig(**base_config)
    
    config.strategies = [
        StrategyOverride(
            name='active1',
            description='Active strategy 1',
            overrides={'grid.geometry.step': 200}
        ),
        StrategyOverride(
            name='active2',
            description='Active strategy 2',
            overrides={'grid.geometry.step': 300}
        )
    ]
    
    manager = StrategyManager(config)
    
    # Activate strategies
    manager.activate_strategy('active1')
    manager.activate_strategy('active2')
    
    assert 'active1' in manager.active_strategies
    assert 'active2' in manager.active_strategies
    assert len(manager.active_strategies) == 2


def test_strategy_deactivation(base_config):
    """Test deactivating strategies"""
    config = RootConfig(**base_config)
    
    config.strategies = [
        StrategyOverride(
            name='test',
            description='Test strategy',
            overrides={'grid.geometry.step': 200}
        )
    ]
    
    manager = StrategyManager(config)
    
    # Activate then deactivate
    manager.activate_strategy('test')
    assert 'test' in manager.active_strategies
    
    manager.deactivate_strategy('test')
    assert 'test' not in manager.active_strategies


def test_get_active_strategies(base_config):
    """Test getting only active strategies"""
    config = RootConfig(**base_config)
    
    config.strategies = [
        StrategyOverride(name='s1', description='S1', overrides={}),
        StrategyOverride(name='s2', description='S2', overrides={}),
        StrategyOverride(name='s3', description='S3', overrides={})
    ]
    
    manager = StrategyManager(config)
    
    # Activate only some
    manager.activate_strategy('s1')
    manager.activate_strategy('s3')
    
    active = manager.get_active_strategy_configs()
    
    assert len(active) == 2
    assert 's1' in active
    assert 's3' in active
    assert 's2' not in active


# ═══════════════════════════════════════════════════════════════════════════
# TEST: INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

def test_strategy_with_capital_allocation(base_config):
    """Test strategies with capital allocation"""
    config = RootConfig(**base_config)
    
    config.strategies = [
        StrategyOverride(name='s1', description='Strategy 1', overrides={}),
        StrategyOverride(name='s2', description='Strategy 2', overrides={}),
        StrategyOverride(name='s3', description='Strategy 3', overrides={})
    ]
    
    manager = StrategyManager(config)
    allocator = CapitalAllocator(total_capital=100000)
    
    # Activate all strategies
    manager.activate_strategy('s1')
    manager.activate_strategy('s2')
    manager.activate_strategy('s3')
    
    # Allocate capital equally
    allocator.allocate_equal(list(manager.active_strategies))
    
    # Each should get ~33,333
    for name in manager.active_strategies:
        capital = allocator.get_allocation(name)
        assert capital == pytest.approx(33333.33, rel=0.01)


def test_dynamic_strategy_switching(base_config):
    """Test switching active strategies"""
    config = RootConfig(**base_config)
    
    config.strategies = [
        StrategyOverride(name='conservative', description='Conservative', overrides={'grid.geometry.step': 1000}),
        StrategyOverride(name='aggressive', description='Aggressive', overrides={'grid.geometry.step': 200})
    ]
    
    manager = StrategyManager(config)
    allocator = CapitalAllocator(total_capital=100000)
    
    # Start with conservative
    manager.activate_strategy('conservative')
    allocator.allocate_fixed({'conservative': 100000})
    
    assert allocator.get_allocation('conservative') == 100000
    
    # Switch to aggressive
    manager.deactivate_strategy('conservative')
    manager.activate_strategy('aggressive')
    
    # Reallocate
    allocator = CapitalAllocator(total_capital=100000)
    allocator.allocate_fixed({'aggressive': 100000})
    
    assert allocator.get_allocation('aggressive') == 100000
    assert allocator.get_allocation('conservative') == 0


def test_multi_strategy_parallel_execution(base_config):
    """Test setup for parallel strategy execution"""
    config = RootConfig(**base_config)
    
    # Create multiple strategies for different market conditions
    config.strategies = [
        StrategyOverride(
            name='btc_bull',
            description='Bitcoin bull market',
            overrides={
                'bot.symbol': 'BTCUSD',
                'bot.mode': 'LONG',
                'grid.geometry.step': 500
            }
        ),
        StrategyOverride(
            name='btc_bear',
            description='Bitcoin bear market',
            overrides={
                'bot.symbol': 'BTCUSD',
                'bot.mode': 'SHORT',
                'grid.geometry.step': 500
            }
        ),
        StrategyOverride(
            name='eth_neutral',
            description='Ethereum neutral',
            overrides={
                'bot.symbol': 'ETHUSD',
                'bot.mode': 'LONG',
                'grid.geometry.step': 50
            }
        )
    ]
    
    manager = StrategyManager(config)
    allocator = CapitalAllocator(total_capital=150000)
    
    # Activate all
    for name in ['btc_bull', 'btc_bear', 'eth_neutral']:
        manager.activate_strategy(name)
    
    # Allocate with weights
    allocator.allocate_weighted({
        'btc_bull': 0.4,
        'btc_bear': 0.3,
        'eth_neutral': 0.3
    })
    
    # Verify allocations
    assert allocator.get_allocation('btc_bull') == 60000
    assert allocator.get_allocation('btc_bear') == 45000
    assert allocator.get_allocation('eth_neutral') == 45000
    
    # Verify configs
    btc_bull_config = manager.get_strategy('btc_bull')
    assert btc_bull_config.bot.symbol == 'BTCUSD'
    assert btc_bull_config.bot.mode == 'LONG'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
