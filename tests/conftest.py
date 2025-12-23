import os
import pytest
from pathlib import Path
import tempfile
import shutil
import yaml

from config.loader import ConfigLoader
from config.models import RootConfig

# Ensure WebUI backend tests have deterministic authentication settings.
os.environ.setdefault("WEBUI_AUTH_TOKEN", "unit-test-token")
os.environ.setdefault("WEBUI_AUTH_USERNAME", "unit")
os.environ.setdefault("WEBUI_AUTH_PASSWORD", "unit-secret")
os.environ.setdefault("WEBUI_ALLOWED_ORIGINS", "http://localhost:*")


# ═══════════════════════════════════════════════════════════════════════════
# YAML CONFIG TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def complete_config_dict():
    """Complete configuration with all required fields"""
    return {
        'version': '2.0',
        'trading_mode': 'demo',
        'bot': {
            'symbol': 'BTCUSD',
            'mode': 'LONG',
            'trading_enabled': True,
            'heartbeat_seconds': 20
        },
        'grid': {
            'geometry': {
                'lower': 90000,
                'upper': 110000,
                'step': 500,
                'reference': 95000
            },
            'limits': {
                'max_open_positions': 10,
                'lot_size': 2,
                'max_open_orders': 20,
                'max_qty_per_order': 1
            },
            'behavior': {
                'strict_grid': True,
                'rung_snap_mode': 'below',
                'tick_size': 0.5,
                'dynamic_tick_size': True,
                'seed_initial_count': 0
            },
            'smart_gap_fill': {
                'enabled': False,
                'order_type': 'maker',
                'max_levels': 0
            }
        },
        'capital_protection': {
            'enabled': True,
            'equity_floor': 1000
        },
        'safety': {
            'enabled': True,
            'max_drawdown': 10
        },
        'guardian': {
            'enabled': True
        },
        'liquidation_protection': {
            'enabled': True
        },
        'startup': {
            'seed_initial_positions': False
        },
        'shutdown': {
            'close_all_positions': False
        },
        'order_execution': {
            'retry_count': 3
        },
        'heartbeat': {
            'enabled': True,
            'update_interval': 20,
            'timeout': 60
        },
        'health_check': {
            'enabled': True
        },
        'performance_logging': {
            'enabled': True
        },
        'api': {
            'enabled': True
        },
        'telegram': {
            'enabled': False
        },
        'logging': {
            'level': 'INFO'
        },
        'webui': {
            'enabled': True
        },
        'risk_limits': {
            'max_position_size': 100
        },
        'execution_safety': {
            'execute_orders': False,
            'i_understand_live': 'NO'
        }
    }


@pytest.fixture
def temp_config_file(temp_dir, complete_config_dict):
    """Create temporary config.yaml file"""
    config_file = temp_dir / 'config.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(complete_config_dict, f)
    return config_file
