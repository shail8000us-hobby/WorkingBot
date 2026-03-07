"""
Contract Test: update_yaml_config
==================================
SEALED — v1.0.0 — March 5, 2026
Protocol: AI_SEAL.md

Locks the known-good behavior of update_yaml_config in yaml_config.py.
Uses a real temporary YAML file — no real config.yaml touched, no cleanup needed.

What is locked:
- Returns True on a successful write
- Grid parameters (reference, step, lower, upper) are correctly persisted
- Dot-notation paths create missing parent keys automatically
- Multiple keys updated in one call are all persisted
- Returns False when the config file does not exist

If this test fails after any code change, that change broke a sealed function.
DO NOT modify this test without an UNSEAL command in AI_SEAL.md.

Run with:
    python3 -m pytest webui/backend/utils/tests/test_sealed_update_yaml_config.py -v
Or run all sealed tests:
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import pytest
import yaml
from unittest.mock import patch
from pathlib import Path

pytestmark = pytest.mark.sealed


@pytest.fixture
def temp_config(tmp_path):
    """Provide a real temporary config.yaml with minimal initial grid config."""
    cfg_file = tmp_path / "config.yaml"
    initial = {
        "symbols": {
            "BTCUSD": {
                "grid": {
                    "geometry": {
                        "reference": 90000,
                        "step": 500,
                        "lower_bound": 85000,
                        "upper_bound": 95000,
                    }
                }
            }
        }
    }
    cfg_file.write_text(yaml.dump(initial, default_flow_style=False, sort_keys=False))
    return cfg_file


def _call(cfg_file, updates):
    """Patch YAML_CONFIG_FILE and call update_yaml_config."""
    import webui.backend.utils.yaml_config as mod
    with patch.object(mod, 'YAML_CONFIG_FILE', cfg_file):
        return mod.update_yaml_config(updates)


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

def test_returns_true_on_success(temp_config):
    """update_yaml_config must return True when write succeeds."""
    result = _call(temp_config, {"symbols.BTCUSD.grid.geometry.reference": 93000})
    assert result is True


def test_grid_reference_persisted(temp_config):
    """New grid reference price must be written to config.yaml."""
    _call(temp_config, {"symbols.BTCUSD.grid.geometry.reference": 93000})
    with open(temp_config) as f:
        saved = yaml.safe_load(f)
    assert saved["symbols"]["BTCUSD"]["grid"]["geometry"]["reference"] == 93000


def test_grid_step_persisted(temp_config):
    """New grid step must be written to config.yaml."""
    _call(temp_config, {"symbols.BTCUSD.grid.geometry.step": 250})
    with open(temp_config) as f:
        saved = yaml.safe_load(f)
    assert saved["symbols"]["BTCUSD"]["grid"]["geometry"]["step"] == 250


def test_multiple_grid_params_in_one_call(temp_config):
    """All four grid geometry params updated in a single call must all persist."""
    _call(temp_config, {
        "symbols.BTCUSD.grid.geometry.reference": 91000,
        "symbols.BTCUSD.grid.geometry.step": 300,
        "symbols.BTCUSD.grid.geometry.lower_bound": 86000,
        "symbols.BTCUSD.grid.geometry.upper_bound": 96000,
    })
    with open(temp_config) as f:
        saved = yaml.safe_load(f)
    geom = saved["symbols"]["BTCUSD"]["grid"]["geometry"]
    assert geom["reference"] == 91000
    assert geom["step"] == 300
    assert geom["lower_bound"] == 86000
    assert geom["upper_bound"] == 96000


def test_creates_missing_parent_keys(temp_config):
    """Writing to a dot-path whose parents don't exist must create them."""
    _call(temp_config, {"symbols.ETHUSD.grid.geometry.reference": 3000})
    with open(temp_config) as f:
        saved = yaml.safe_load(f)
    assert saved["symbols"]["ETHUSD"]["grid"]["geometry"]["reference"] == 3000


def test_existing_keys_not_clobbered(temp_config):
    """Updating one key must not destroy sibling keys."""
    _call(temp_config, {"symbols.BTCUSD.grid.geometry.reference": 95000})
    with open(temp_config) as f:
        saved = yaml.safe_load(f)
    # step should still be the original 500
    assert saved["symbols"]["BTCUSD"]["grid"]["geometry"]["step"] == 500


def test_returns_false_when_file_missing(tmp_path):
    """update_yaml_config must return False (not raise) when config.yaml is absent."""
    missing = tmp_path / "nonexistent.yaml"
    result = _call(missing, {"symbols.BTCUSD.grid.geometry.reference": 93000})
    assert result is False
