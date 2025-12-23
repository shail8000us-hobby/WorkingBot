"""
Backend Configuration - Feature Flags

Allows safe parallel operation of old and new WebUI systems.
Enables instant rollback if issues arise during validation period.

Date: November 12, 2025
Part of: WebUI Robustness Plan Week 3
"""

import os
import json
from pathlib import Path

# Feature flags
FEATURE_FLAGS = {
    # Week 3: Guardian Dashboard
    'guardian_dashboard': True,
    
    # Week 2: New state management
    'new_state_management': True,
    'data_aggregator': True,
    'circuit_breakers': True,
    
    # Week 1: Backend resilience
    'metrics_logging': True,
    'enhanced_health_checks': True,
    
    # Overall toggle
    'new_webui_system': True  # Enable new system by default
}

# Feature flags file path
FEATURE_FLAGS_FILE = Path(__file__).parent / 'feature_flags.json'

def load_feature_flags():
    """Load feature flags from file"""
    if FEATURE_FLAGS_FILE.exists():
        try:
            with open(FEATURE_FLAGS_FILE, 'r') as f:
                loaded_flags = json.load(f)
                FEATURE_FLAGS.update(loaded_flags)
        except Exception as e:
            print(f"Warning: Failed to load feature flags: {e}")
    return FEATURE_FLAGS

def save_feature_flags(flags=None):
    """Save feature flags to file"""
    try:
        flags_to_save = flags if flags is not None else FEATURE_FLAGS
        with open(FEATURE_FLAGS_FILE, 'w') as f:
            json.dump(flags_to_save, f, indent=2)
        return True
    except Exception as e:
        print(f"Error: Failed to save feature flags: {e}")
        return False

def is_feature_enabled(feature_name):
    """Check if a feature is enabled"""
    return FEATURE_FLAGS.get(feature_name, False)

def toggle_feature(feature_name, enabled):
    """Toggle a feature flag"""
    FEATURE_FLAGS[feature_name] = enabled
    return save_feature_flags()

def get_all_flags():
    """Get all feature flags"""
    return FEATURE_FLAGS.copy()

# Load flags on module import
load_feature_flags()

# Load from YAML config
from config.loader import get_config
cfg = get_config()

# General configuration
DEBUG = cfg.webui.flask.debug
HOST = cfg.webui.flask.host
PORT = cfg.webui.flask.port

# Bot configuration paths
BOT_DIR = Path(__file__).parent.parent.parent
BOT_CONFIG_FILE = BOT_DIR / 'bot_config.json'
BOT_LOG_FILE = BOT_DIR / 'bot_live.log'

# WebUI paths
WEBUI_BACKEND_DIR = Path(__file__).parent
WEBUI_FRONTEND_DIR = WEBUI_BACKEND_DIR.parent / 'frontend'

# Metrics database
METRICS_DB_PATH = WEBUI_BACKEND_DIR / 'metrics.db'

# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 15  # seconds

# API timeouts
API_TIMEOUT = 30  # seconds
DELTA_API_TIMEOUT = 10  # seconds

# Logging
LOG_LEVEL = cfg.logging.level if hasattr(cfg, 'logging') and hasattr(cfg.logging, 'level') else 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
