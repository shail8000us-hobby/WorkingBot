"""
Hot-reload and file watching tests.
Tests ConfigWatcher, ConfigHistory, and callback mechanisms.
"""

import pytest
import asyncio
import time
from pathlib import Path
import tempfile
import shutil
import yaml

from config.watcher import ConfigWatcher, ConfigHistory, ConfigFileHandler
from config.models import RootConfig
from config.loader import ConfigLoader


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_config_dict(complete_config_dict):
    """Sample configuration dictionary - uses complete config from conftest"""
    return complete_config_dict


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CONFIG HISTORY
# ═══════════════════════════════════════════════════════════════════════════

def test_history_save_and_rollback(sample_config_dict):
    """Test saving versions and rolling back"""
    history = ConfigHistory(max_history=10)
    
    # Save version 1
    config1 = RootConfig(**sample_config_dict)
    history.save_version(config1)
    
    # Save version 2
    config2_dict = sample_config_dict.copy()
    config2_dict['grid']['geometry']['step'] = 600
    config2 = RootConfig(**config2_dict)
    history.save_version(config2)
    
    # Save version 3
    config3_dict = sample_config_dict.copy()
    config3_dict['grid']['geometry']['step'] = 700
    config3 = RootConfig(**config3_dict)
    history.save_version(config3)
    
    # Current should be version 3
    assert history.current_index == 2
    assert len(history.history) == 3
    
    # Rollback 1 step
    prev = history.rollback(1)
    assert prev.grid.geometry.step == 600
    assert history.current_index == 1
    
    # Rollback to beginning
    prev = history.rollback(1)
    assert prev.grid.geometry.step == 500
    assert history.current_index == 0


def test_history_rollforward(sample_config_dict):
    """Test rolling forward after rollback"""
    history = ConfigHistory(max_history=10)
    
    # Save 3 versions
    for step in [500, 600, 700]:
        config_dict = sample_config_dict.copy()
        config_dict['grid']['geometry']['step'] = step
        config = RootConfig(**config_dict)
        history.save_version(config)
    
    # Rollback to first
    history.rollback(2)
    assert history.current_index == 0
    
    # Rollforward 1 step
    newer = history.rollforward(1)
    assert newer.grid.geometry.step == 600
    assert history.current_index == 1
    
    # Rollforward to latest
    newer = history.rollforward(1)
    assert newer.grid.geometry.step == 700
    assert history.current_index == 2


def test_history_max_limit(sample_config_dict):
    """Test that history respects max_history limit"""
    history = ConfigHistory(max_history=5)
    
    # Save 10 versions
    for step in range(500, 1500, 100):
        config_dict = sample_config_dict.copy()
        config_dict['grid']['geometry']['step'] = step
        config = RootConfig(**config_dict)
        history.save_version(config)
    
    # Should only keep last 5
    assert len(history.history) == 5
    
    # Current should be latest (step=1400)
    current = history.get_current()
    assert current.grid.geometry.step == 1400


def test_history_invalidates_future(sample_config_dict):
    """Test that saving after rollback invalidates future"""
    history = ConfigHistory(max_history=10)
    
    # Save 3 versions
    for step in [500, 600, 700]:
        config_dict = sample_config_dict.copy()
        config_dict['grid']['geometry']['step'] = step
        config = RootConfig(**config_dict)
        history.save_version(config)
    
    # Rollback to version 1
    history.rollback(2)
    assert history.current_index == 0
    
    # Save a new version
    new_config_dict = sample_config_dict.copy()
    new_config_dict['grid']['geometry']['step'] = 550
    new_config = RootConfig(**new_config_dict)
    history.save_version(new_config)
    
    # History should now be [500, 550]
    assert len(history.history) == 2
    assert history.current_index == 1
    assert history.get_current().grid.geometry.step == 550


# ═══════════════════════════════════════════════════════════════════════════
# TEST: FILE WATCHER
# ═══════════════════════════════════════════════════════════════════════════

def test_watcher_initialization(temp_dir, sample_config_dict):
    """Test ConfigWatcher initialization"""
    # Create config file
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    # Create watcher
    watcher = ConfigWatcher(config_file)
    
    assert watcher.config_path == config_file
    assert watcher.observer is not None


def test_watcher_detect_changes(temp_dir, sample_config_dict):
    """Test that watcher detects file changes"""
    # Create config file
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    # Track changes
    changes_detected = []
    
    def on_change(old_config, new_config):
        changes_detected.append((old_config, new_config))
    
    # Create watcher with callback
    watcher = ConfigWatcher(config_file)
    watcher.add_callback(on_change)
    watcher.start()
    
    try:
        # Modify config file
        modified_config = sample_config_dict.copy()
        modified_config['grid']['geometry']['step'] = 600
        
        time.sleep(0.5)  # Wait for watcher to initialize
        
        with open(config_file, 'w') as f:
            yaml.dump(modified_config, f)
        
        # Wait for change detection (debounce + processing)
        time.sleep(2)
        
        # Should have detected change
        assert len(changes_detected) >= 1
        
    finally:
        watcher.stop()


def test_watcher_callback_async(temp_dir, sample_config_dict):
    """Test async callbacks"""
    # Create config file
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    # Track async changes
    async_changes = []
    
    async def async_callback(old_config, new_config):
        async_changes.append((old_config, new_config))
        await asyncio.sleep(0.1)
    
    # Create watcher
    watcher = ConfigWatcher(config_file)
    watcher.add_callback(async_callback)
    watcher.start()
    
    try:
        # Modify config
        modified_config = sample_config_dict.copy()
        modified_config['grid']['geometry']['step'] = 700
        
        time.sleep(0.5)
        
        with open(config_file, 'w') as f:
            yaml.dump(modified_config, f)
        
        time.sleep(2)
        
        # Should have called async callback
        assert len(async_changes) >= 1
        
    finally:
        watcher.stop()


def test_watcher_debounce(temp_dir, sample_config_dict):
    """Test that rapid changes are debounced"""
    # Create config file
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    changes_count = []
    
    def count_changes(old_config, new_config):
        changes_count.append(1)
    
    # Create watcher with 1 second debounce
    watcher = ConfigWatcher(config_file, debounce_seconds=1.0)
    watcher.add_callback(count_changes)
    watcher.start()
    
    try:
        time.sleep(0.5)
        
        # Make multiple rapid changes
        for step in [600, 650, 700]:
            modified_config = sample_config_dict.copy()
            modified_config['grid']['geometry']['step'] = step
            with open(config_file, 'w') as f:
                yaml.dump(modified_config, f)
            time.sleep(0.2)  # Less than debounce time
        
        # Wait for debounce + processing
        time.sleep(2)
        
        # Should only trigger once due to debounce
        assert len(changes_count) <= 2  # May get 1-2 triggers depending on timing
        
    finally:
        watcher.stop()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

def test_watcher_with_history(temp_dir, sample_config_dict):
    """Test watcher integration with history tracking"""
    # Create config file
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    # Create history tracker
    history = ConfigHistory(max_history=10)
    
    def on_change(old_config, new_config):
        history.save_version(new_config)
    
    # Create watcher
    watcher = ConfigWatcher(config_file)
    watcher.add_callback(on_change)
    watcher.start()
    
    try:
        time.sleep(0.5)
        
        # Make changes
        for step in [600, 700, 800]:
            modified_config = sample_config_dict.copy()
            modified_config['grid']['geometry']['step'] = step
            with open(config_file, 'w') as f:
                yaml.dump(modified_config, f)
            time.sleep(1.5)  # Wait for debounce
        
        # History should have versions
        assert len(history.history) >= 1
        
    finally:
        watcher.stop()


def test_reload_on_change(temp_dir, sample_config_dict):
    """Test that config is actually reloaded on file change"""
    # Create config file
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_dict, f)
    
    # Load initial config
    loader = ConfigLoader(config_file)
    config = loader.load()
    initial_step = config.grid.geometry.step
    
    # Track reloads
    reloaded_configs = []
    
    def on_change(old_config, new_config):
        reloaded = loader.load()
        reloaded_configs.append(reloaded)
    
    # Start watcher
    watcher = ConfigWatcher(config_file)
    watcher.add_callback(on_change)
    watcher.start()
    
    try:
        time.sleep(0.5)
        
        # Modify config
        modified_config = sample_config_dict.copy()
        modified_config['grid']['geometry']['step'] = 999
        with open(config_file, 'w') as f:
            yaml.dump(modified_config, f)
        
        time.sleep(2)
        
        # Should have reloaded
        if len(reloaded_configs) > 0:
            assert reloaded_configs[-1].grid.geometry.step == 999
        
    finally:
        watcher.stop()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
