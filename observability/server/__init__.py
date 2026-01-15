"""
Standalone Metrics Server Package

Runs as a completely separate Flask application on port 9091.
NO modifications to existing WebUI required.
"""

from .metrics_server import app, start_server

__all__ = ['app', 'start_server']
