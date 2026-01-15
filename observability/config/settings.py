"""
Observability Settings

Configuration for the observability module.
Loaded from environment variables or config file.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class ObservabilitySettings:
    """Settings for observability module"""
    
    # Metrics server
    metrics_host: str = '0.0.0.0'
    metrics_port: int = 9091
    metrics_path: str = '/metrics'
    
    # Collection settings
    collect_interval_seconds: int = 15
    cache_ttl_seconds: int = 5
    
    # Data sources (paths relative to WorkingBot root)
    guardian_health_paths: List[str] = field(default_factory=lambda: [
        'bot/guardian/.guardian_health.json',
        '.guardian_health.json',
        '.guardian_health'
    ])
    
    bot_state_paths: List[str] = field(default_factory=lambda: [
        'data/runtime_state_LONG.json',
        'data/runtime_state_SHORT.json',
        'data/bot_state.json'
    ])
    
    monitoring_snapshot_path: str = 'data/monitoring_snapshot.json'
    options_state_path: str = 'data/options_state.json'
    
    # Feature flags
    collect_system_metrics: bool = True
    collect_guardian_metrics: bool = True
    collect_bot_metrics: bool = True
    collect_options_metrics: bool = True
    collect_pm2_metrics: bool = True
    
    # Prometheus settings
    prometheus_url: str = 'http://localhost:9090'
    
    # Grafana settings
    grafana_url: str = 'http://localhost:3000'
    grafana_api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'ObservabilitySettings':
        """Load settings from environment variables"""
        return cls(
            metrics_host=os.environ.get('METRICS_HOST', '0.0.0.0'),
            metrics_port=int(os.environ.get('METRICS_PORT', '9091')),
            collect_interval_seconds=int(os.environ.get('METRICS_COLLECT_INTERVAL', '15')),
            prometheus_url=os.environ.get('PROMETHEUS_URL', 'http://localhost:9090'),
            grafana_url=os.environ.get('GRAFANA_URL', 'http://localhost:3000'),
            grafana_api_key=os.environ.get('GRAFANA_API_KEY'),
        )
    
    def get_base_dir(self) -> Path:
        """Get WorkingBot base directory"""
        return Path(__file__).parent.parent.parent
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path to absolute"""
        return self.get_base_dir() / relative_path


# Global settings instance
_settings: Optional[ObservabilitySettings] = None


def get_settings() -> ObservabilitySettings:
    """Get global settings instance"""
    global _settings
    if _settings is None:
        _settings = ObservabilitySettings.from_env()
    return _settings
