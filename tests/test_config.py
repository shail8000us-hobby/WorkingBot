"""
Comprehensive test suite for YAML configuration system.
Tests all phases: models, loading, conversion, strategies, hot-reload, API.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from copy import deepcopy

from config.models import (
    RootConfig, GridGeometry, TradingMode, GridMode,
    StrategyOverride
)
from config.loader import ConfigLoader, get_config, reload_config
from config.env_converter import EnvToYamlConverter, env_to_dict
from config.strategy_manager import StrategyManager, CapitalAllocator
from config.watcher import ConfigHistory


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_config(complete_config_dict):
    """Sample valid configuration - uses complete config from conftest"""
    return complete_config_dict


# ═══════════════════════════════════════════════════════════════════════════
# TEST: MODELS (Phase 0)
# ═══════════════════════════════════════════════════════════════════════════

def test_grid_geometry_validation():
    """Test GridGeometry validation"""
    # Valid geometry
    geo = GridGeometry(lower=90000, upper=110000, step=500, reference=95000)
    assert geo.lower == 90000
    assert geo.upper == 110000
    
    # Invalid: upper < lower
    with pytest.raises(ValueError):
        GridGeometry(lower=110000, upper=90000, step=500, reference=95000)
    
    # Invalid: reference out of range
    with pytest.raises(ValueError):
        GridGeometry(lower=90000, upper=110000, step=500, reference=120000)


def test_config_cross_field_validation(sample_config):
    """Test cross-field validation"""
    config = RootConfig(**sample_config)
    
    # Should pass
    config.validate_cross_field_constraints()
    
    # Too many grid levels
    config.grid.geometry.step = 10  # Would create 2000 levels
    with pytest.raises(ValueError, match="Grid would create"):
        config.validate_cross_field_constraints()


def test_enum_validation():
    """Test enum field validation"""
    # Valid
    assert TradingMode.DEMO == 'demo'
    assert GridMode.LONG == 'LONG'
    
    # Invalid values caught by Pydantic
    with pytest.raises(ValueError):
        RootConfig(trading_mode='invalid', **{})


# ═══════════════════════════════════════════════════════════════════════════
# TEST: LOADER (Phase 1)
# ═══════════════════════════════════════════════════════════════════════════

def test_yaml_loading(temp_dir, sample_config):
    """Test loading YAML configuration"""
    import yaml
    
    # Write YAML file
    yaml_file = temp_dir / 'test_config.yaml'
    with open(yaml_file, 'w') as f:
        yaml.dump(sample_config, f)
    
    # Load it
    loader = ConfigLoader(yaml_file)
    config = loader.load()
    
    assert config.bot.symbol == 'BTCUSD'
    assert config.grid.geometry.lower == 90000


def test_config_auto_detection(temp_dir, sample_config):
    """Test automatic config file detection"""
    import yaml
    
    # Save current dir
    original_cwd = os.getcwd()
    
    try:
        # Change to temp dir
        os.chdir(temp_dir)
        
        # Create config.yaml
        with open('config.yaml', 'w') as f:
            yaml.dump(sample_config, f)
        
        # Should auto-detect
        loader = ConfigLoader()
        assert loader.config_path.name == 'config.yaml'
        
    finally:
        os.chdir(original_cwd)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CONVERTER (Phase 1)
# ═══════════════════════════════════════════════════════════════════════════

def test_env_to_yaml_conversion(temp_dir):
    """Test ENV to YAML conversion"""
    # Create sample ENV file
    env_file = temp_dir / 'test.env'
    env_content = """
TRADING_MODE=demo
GRIDBOT_SYMBOL=BTCUSD
GRIDBOT_LOWER=90000
GRIDBOT_UPPER=110000
GRIDBOT_STEP=500
GRIDBOT_LOT=2
"""
    env_file.write_text(env_content)
    
    # Convert
    converter = EnvToYamlConverter(env_file)
    yaml_dict = converter.convert()
    
    assert yaml_dict['trading_mode'] == 'demo'
    assert yaml_dict['bot']['symbol'] == 'BTCUSD'
    assert yaml_dict['grid']['geometry']['lower'] == 90000


def test_type_conversion():
    """Test type conversion from ENV strings"""
    os.environ['TEST_BOOL'] = 'true'
    os.environ['TEST_INT'] = '12345'
    os.environ['TEST_FLOAT'] = '12.34'
    
    from config.env_mapping import convert_bool, convert_int, convert_float
    
    assert convert_bool('true') == True
    assert convert_bool('false') == False
    assert convert_int('12345') == 12345
    assert convert_float('12.34') == 12.34


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STRATEGY MANAGER (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════

def test_strategy_inheritance(sample_config):
    """Test strategy inheritance"""
    # Create base config
    base_config = RootConfig(**sample_config)
    
    # Add strategy override
    strategy_override = StrategyOverride(
        name='aggressive',
        description='Aggressive strategy',
        overrides={
            'grid.geometry.step': 200,
            'grid.limits.lot_size': 5
        }
    )
    
    base_config.strategies = [strategy_override]
    
    # Create manager
    manager = StrategyManager(base_config)
    
    # Get aggressive strategy
    aggressive = manager.get_strategy('aggressive')
    
    # Should have overridden values
    assert aggressive.grid.geometry.step == 200
    assert aggressive.grid.limits.lot_size == 5
    
    # Should keep other values from base
    assert aggressive.grid.geometry.lower == 90000


def test_strategy_activation():
    """Test strategy activation/deactivation"""
    manager = StrategyManager()
    
    # Initially no active strategies
    assert len(manager.active_strategies) == 0
    
    # Would need actual strategies to test activation
    # This is placeholder for when strategies are defined


def test_capital_allocation():
    """Test capital allocation"""
    allocator = CapitalAllocator(total_capital=100000)
    
    # Equal allocation
    allocator.allocate_equal(['strategy1', 'strategy2', 'strategy3'])
    assert allocator.get_allocation('strategy1') == pytest.approx(33333.33, rel=0.01)
    
    # Weighted allocation
    allocator.allocate_weighted({
        'strategy1': 0.5,
        'strategy2': 0.3,
        'strategy3': 0.2
    })
    assert allocator.get_allocation('strategy1') == 50000
    assert allocator.get_allocation('strategy2') == 30000
    assert allocator.get_allocation('strategy3') == 20000
    
    # Fixed allocation
    allocator.allocate_fixed({
        'strategy1': 40000,
        'strategy2': 30000
    })
    assert allocator.get_unallocated_capital() == 30000


def test_capital_reservation():
    """Test capital reservation"""
    allocator = CapitalAllocator(total_capital=100000)
    
    # Reserve 20%
    allocator.reserve_capital(20000)
    assert allocator.get_available_capital() == 80000
    
    # Allocate from available
    allocator.allocate_equal(['s1', 's2'])
    assert allocator.get_allocation('s1') == 40000


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CONFIG HISTORY (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

def test_config_history(sample_config):
    """Test configuration history tracking"""
    history = ConfigHistory(max_history=5)
    
    # Save versions
    config1 = RootConfig(**sample_config)
    history.save_version(config1)
    
    config2 = RootConfig(**sample_config)
    config2.grid.geometry.step = 600
    history.save_version(config2)
    
    config3 = RootConfig(**sample_config)
    config3.grid.geometry.step = 700
    history.save_version(config3)
    
    # Should have 3 versions
    assert len(history.history) == 3
    assert history.current_index == 2
    
    # Rollback
    prev = history.rollback(1)
    assert prev.grid.geometry.step == 600
    assert history.current_index == 1
    
    # Rollback again
    prev = history.rollback(1)
    assert prev.grid.geometry.step == 500
    assert history.current_index == 0
    
    # Roll forward
    newer = history.rollforward(1)
    assert newer.grid.geometry.step == 600
    assert history.current_index == 1


def test_history_max_limit():
    """Test history maximum limit"""
    history = ConfigHistory(max_history=3)
    
    # Add 5 versions
    for i in range(5):
        config = RootConfig(
            version='2.0',
            trading_mode='demo',
            bot={'symbol': f'TEST{i}'}
        )
        history.save_version(config)
    
    # Should only keep last 3
    assert len(history.history) == 3


# ═══════════════════════════════════════════════════════════════════════════
# TEST: VALIDATION EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

def test_execution_safety_validation(sample_config):
    """Test execution safety validation"""
    config = RootConfig(**sample_config)
    
    # Cannot execute orders without acknowledgment
    config.execution_safety.execute_orders = True
    config.execution_safety.i_understand_live = 'NO'
    
    with pytest.raises(ValueError, match="Cannot enable execute_orders"):
        config.execution_safety.execute_orders  # Trigger validation


def test_heartbeat_timing_validation(sample_config):
    """Test heartbeat timing validation"""
    config = RootConfig(**sample_config)
    
    # Invalid: update_interval >= timeout
    config.heartbeat.update_interval = 30
    config.heartbeat.timeout = 20
    
    with pytest.raises(ValueError, match="update_interval.*must be"):
        config.validate_cross_field_constraints()


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_full_workflow(temp_dir, sample_config):
    """Test complete workflow: save, load, modify, reload"""
    import yaml
    
    # Save current dir
    original_cwd = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # 1. Save initial config
        config_file = Path('config.yaml')
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        # 2. Load it
        loader = ConfigLoader()
        config = loader.load()
        assert config.grid.geometry.step == 500
        
        # 3. Modify and save
        config.grid.geometry.step = 600
        loader.save_yaml(config, config_file)
        
        # 4. Reload
        loader2 = ConfigLoader()
        config2 = loader2.load()
        assert config2.grid.geometry.step == 600
        
    finally:
        os.chdir(original_cwd)


def test_env_to_yaml_roundtrip(temp_dir):
    """Test ENV -> YAML -> Load roundtrip"""
    # Create ENV file
    env_file = temp_dir / 'test.env'
    env_content = """
TRADING_MODE=demo
GRIDBOT_SYMBOL=BTCUSD
GRIDBOT_LOWER=90000
GRIDBOT_UPPER=110000
GRIDBOT_STEP=500
GRIDBOT_REF=95000
GRIDBOT_LOT=2
GRIDBOT_MAX_OPEN=10
"""
    env_file.write_text(env_content)
    
    # Convert to YAML
    converter = EnvToYamlConverter(env_file)
    yaml_file = temp_dir / 'converted.yaml'
    converter.save_yaml(yaml_file)
    
    # Load YAML
    loader = ConfigLoader(yaml_file)
    config = loader.load()
    
    # Verify values match
    assert config.bot.symbol == 'BTCUSD'
    assert config.grid.geometry.lower == 90000
    assert config.grid.geometry.upper == 110000
    assert config.grid.geometry.step == 500


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
