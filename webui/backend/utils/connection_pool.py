#!/usr/bin/env python3
"""
Connection Pool Manager for WebUI Backend

Provides connection pooling and resource management to prevent ERR_INSUFFICIENT_RESOURCES.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional
import threading


class ConnectionPoolManager:
    """
    Singleton manager for HTTP connection pooling.
    
    Prevents resource exhaustion by:
    - Reusing TCP connections
    - Limiting concurrent connections
    - Automatic retries with backoff
    - Connection keep-alive
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,                    # Total retry attempts
            backoff_factor=0.3,         # Wait 0.3s, 0.6s, 1.2s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Configure HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,        # Number of connection pools to cache
            pool_maxsize=20,            # Max connections per pool
            max_retries=retry_strategy,
            pool_block=False            # Don't block waiting for connection
        )
        
        # Mount adapter for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'GridBot-WebUI/1.0',
            'Connection': 'keep-alive'
        })
    
    def get(self, url: str, timeout: int = 5, **kwargs):
        """
        GET request with connection pooling.
        
        Args:
            url: URL to request
            timeout: Request timeout in seconds (default: 5)
            **kwargs: Additional arguments for requests.get()
        
        Returns:
            requests.Response object
        """
        return self.session.get(url, timeout=timeout, **kwargs)
    
    def post(self, url: str, timeout: int = 5, **kwargs):
        """
        POST request with connection pooling.
        
        Args:
            url: URL to request
            timeout: Request timeout in seconds (default: 5)
            **kwargs: Additional arguments for requests.post()
        
        Returns:
            requests.Response object
        """
        return self.session.post(url, timeout=timeout, **kwargs)
    
    def put(self, url: str, timeout: int = 5, **kwargs):
        """PUT request with connection pooling."""
        return self.session.put(url, timeout=timeout, **kwargs)
    
    def delete(self, url: str, timeout: int = 5, **kwargs):
        """DELETE request with connection pooling."""
        return self.session.delete(url, timeout=timeout, **kwargs)
    
    def close(self):
        """Close all connections and cleanup resources."""
        if hasattr(self, 'session'):
            self.session.close()


# Global instance
_pool_manager = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ConnectionPoolManager:
    """
    Get the global connection pool manager instance.
    
    Thread-safe singleton accessor.
    """
    global _pool_manager
    if _pool_manager is None:
        with _pool_lock:
            if _pool_manager is None:
                _pool_manager = ConnectionPoolManager()
    return _pool_manager


def http_get(url: str, timeout: int = 5, **kwargs):
    """
    Convenience function for GET requests with connection pooling.
    
    Example:
        from webui.backend.utils.connection_pool import http_get
        response = http_get('http://localhost:11434/api/tags', timeout=2)
    """
    pool = get_connection_pool()
    return pool.get(url, timeout=timeout, **kwargs)


def http_post(url: str, timeout: int = 5, **kwargs):
    """
    Convenience function for POST requests with connection pooling.
    
    Example:
        from webui.backend.utils.connection_pool import http_post
        response = http_post('http://localhost:8080/api/start', json={'mode': 'live'}, timeout=3)
    """
    pool = get_connection_pool()
    return pool.post(url, timeout=timeout, **kwargs)


def cleanup_connections():
    """Cleanup all connection pool resources (call on shutdown)."""
    global _pool_manager
    if _pool_manager is not None:
        _pool_manager.close()
        _pool_manager = None
