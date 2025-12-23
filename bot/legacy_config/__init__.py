#!/usr/bin/env python3
"""
Configuration Management System
Centralized, type-safe configuration for all bot modules
"""

from bot.legacy_config.config_manager_core import (
    get_config_manager,
    get_config,
    set_config,
    reload_config,
    get_all_config,
    BulletproofConfigManager,
    ConfigParameter
)

__all__ = [
    'get_config_manager',
    'get_config',
    'set_config',
    'reload_config',
    'get_all_config',
    'BulletproofConfigManager',
    'ConfigParameter'
]

