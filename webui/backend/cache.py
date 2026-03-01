"""
Centralized caching module for WebUI backend

Provides Flask-Caching instance and helper decorators for performance optimization.
Phase 3 optimization - March 2026
"""

from flask_caching import Cache

# Cache instance (initialized in app.py)
cache = None

def init_cache(app):
    """Initialize cache with Flask app"""
    global cache
    cache = Cache(app, config={
        'CACHE_TYPE': 'SimpleCache',  # In-memory cache (use Redis for production scaling)
        'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes default
        'CACHE_THRESHOLD': 500,  # Maximum number of cached items
    })
    return cache

def make_cache_key(*args, **kwargs):
    """
    Generate cache key from request args
    Includes query parameters for proper cache invalidation
    """
    from flask import request
    # Include instance/symbol/mode query params in cache key
    instance = request.args.get('instance', '')
    symbol = request.args.get('symbol', '')
    mode = request.args.get('mode', '')
    path = request.path
    return f"{path}:{instance}:{symbol}:{mode}"

# Cache timeouts for different endpoint types (in seconds)
CACHE_TIMEOUTS = {
    'health': 2,          # Health checks - 2s
    'positions': 5,       # Positions - 5s
    'config': 60,         # Config - 1min
    'analytics': 30,      # Analytics - 30s
    'market': 10,         # Market data - 10s
    'static': 300,        # Static data - 5min
    'todos': 10,          # Todos - 10s
    'logs': 5,            # Logs - 5s
}
