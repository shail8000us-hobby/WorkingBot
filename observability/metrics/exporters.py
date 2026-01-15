"""
Prometheus Metrics Exporters

Generates Prometheus-formatted metrics output.
"""

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .definitions import REGISTRY
from .collectors import MetricsCollector


def generate_metrics() -> bytes:
    """
    Generate metrics in Prometheus format.
    
    This function:
    1. Triggers collection of all metrics
    2. Generates Prometheus-formatted output
    
    Returns:
        bytes: Prometheus-formatted metrics
    """
    # Collect all metrics before generating output
    MetricsCollector.collect_all()
    
    # Generate Prometheus format
    return generate_latest(REGISTRY)


def get_content_type() -> str:
    """Get the Prometheus content type"""
    return CONTENT_TYPE_LATEST


def get_metrics_text() -> str:
    """Get metrics as text string (for debugging)"""
    return generate_metrics().decode('utf-8')
