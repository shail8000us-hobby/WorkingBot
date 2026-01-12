"""
Rate Limiting Implementation for Delta Exchange API
====================================================
Thread-safe rate limiter to prevent API throttling (429 errors).

Imported from OptionBot project.
Original: options_trading_bot/core/rate_limiter.py

Usage:
    from webui.backend.utils.rate_limiter import RateLimiter
    
    # Delta Exchange allows ~100 requests per minute
    limiter = RateLimiter(max_requests=90, time_window=60)
    
    # Before each API call
    if limiter.acquire(timeout=5.0):
        response = api.call()
    else:
        raise RateLimitError("Rate limit exceeded, try again later")
"""

import time
from collections import deque
from typing import Optional
import threading
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Thread-safe sliding window rate limiter.
    
    Tracks API requests within a time window and blocks new requests
    if the limit is exceeded. Essential for production trading bots
    to avoid API bans.
    
    Attributes:
        max_requests: Maximum number of requests allowed in the time window
        time_window: Time window in seconds (default: 60)
        
    Example:
        limiter = RateLimiter(max_requests=90, time_window=60)
        
        async def place_order(order):
            if not limiter.acquire(timeout=2.0):
                raise RateLimitError("Rate limited")
            return await api.place_order(order)
    """
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds (default: 60)
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if time_window <= 0:
            raise ValueError("time_window must be positive")
            
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque = deque()
        self.lock = threading.Lock()
        
        logger.info(f"RateLimiter initialized: {max_requests} requests per {time_window}s")
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a request.
        
        Blocks until a request slot is available or timeout expires.
        Returns immediately if a slot is available.
        
        Args:
            timeout: Maximum time to wait for permission (seconds).
                     None means wait indefinitely.
                     0 means don't wait (return immediately).
            
        Returns:
            True if permission granted, False if timeout expired
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                now = time.time()
                
                # Remove old requests outside the time window
                while self.requests and self.requests[0] <= now - self.time_window:
                    self.requests.popleft()
                
                # Check if we can make a request
                if len(self.requests) < self.max_requests:
                    self.requests.append(now)
                    return True
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Rate limit timeout after {elapsed:.2f}s")
                    return False
            
            # Wait before trying again (100ms)
            time.sleep(0.1)
    
    def try_acquire(self) -> bool:
        """
        Try to acquire permission without waiting.
        
        Returns:
            True if permission granted immediately, False otherwise
        """
        return self.acquire(timeout=0)
    
    def get_remaining_requests(self) -> int:
        """
        Get number of remaining requests in current window.
        
        Returns:
            Number of requests that can still be made
        """
        with self.lock:
            now = time.time()
            
            # Remove old requests
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()
            
            return max(0, self.max_requests - len(self.requests))
    
    def get_reset_time(self) -> float:
        """
        Get time until rate limit resets (oldest request expires).
        
        Returns:
            Seconds until a new request slot becomes available
        """
        with self.lock:
            if not self.requests:
                return 0.0
            
            oldest_request = self.requests[0]
            reset_time = oldest_request + self.time_window
            return max(0.0, reset_time - time.time())
    
    def get_status(self) -> dict:
        """
        Get current rate limiter status for monitoring.
        
        Returns:
            Dictionary with status information
        """
        with self.lock:
            now = time.time()
            
            # Clean old requests
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()
            
            used = len(self.requests)
            remaining = max(0, self.max_requests - used)
            reset_time = 0.0
            if self.requests:
                reset_time = max(0.0, self.requests[0] + self.time_window - now)
            
            return {
                'max_requests': self.max_requests,
                'time_window': self.time_window,
                'used': used,
                'remaining': remaining,
                'reset_in_seconds': round(reset_time, 2),
                'utilization_pct': round((used / self.max_requests) * 100, 1)
            }
    
    def reset(self):
        """
        Reset the rate limiter (clear all tracked requests).
        
        Use with caution - this allows immediate requests but may
        cause rate limit errors if API hasn't actually reset.
        """
        with self.lock:
            self.requests.clear()
            logger.info("RateLimiter reset")


# Pre-configured rate limiters for Delta Exchange
# Delta allows ~100 requests per minute for authenticated endpoints
DELTA_API_LIMITER = RateLimiter(max_requests=90, time_window=60)

# More conservative limiter for order placement (avoid order spam)
DELTA_ORDER_LIMITER = RateLimiter(max_requests=30, time_window=60)

# Public endpoints have higher limits
DELTA_PUBLIC_LIMITER = RateLimiter(max_requests=120, time_window=60)
