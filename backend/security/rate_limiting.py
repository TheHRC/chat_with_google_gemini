"""
Rate limiting utilities for the chatbot application.
"""

import time
from typing import Dict, Any, Tuple, Optional
from functools import wraps
from flask import request, jsonify
from ratelimit import limits, RateLimitException

from .errors import RateLimitError, log_security_event
from .logging import SecurityLogger

# Initialize security logger
security_logger = SecurityLogger("rate_limiting")

# In-memory store for tracking request counts
# In production, you should use Redis or another distributed cache
REQUEST_COUNTS: Dict[str, Dict[str, Any]] = {}

def get_request_identifier():
    """Get a unique identifier for the current request (usually IP address)."""
    return request.remote_addr or "unknown"

def rate_limit(max_calls: int, period: int = 60):
    """
    Decorator for rate-limiting API endpoints.
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Period in seconds (default: 60)
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            identifier = get_request_identifier()
            
            # Get or initialize the request count
            if identifier not in REQUEST_COUNTS:
                REQUEST_COUNTS[identifier] = {"count": 0, "reset_time": time.time() + period}
            
            # Check if period has reset
            if time.time() > REQUEST_COUNTS[identifier]["reset_time"]:
                REQUEST_COUNTS[identifier] = {"count": 0, "reset_time": time.time() + period}
            
            # Check if rate limit is exceeded
            if REQUEST_COUNTS[identifier]["count"] >= max_calls:
                security_logger.warning(
                    "RATE_LIMIT_EXCEEDED",
                    f"Rate limit exceeded for {identifier}",
                    {"max_calls": max_calls, "period": period}
                )
                return jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after": int(REQUEST_COUNTS[identifier]["reset_time"] - time.time())
                }), 429
            
            # Increment count and call the original function
            REQUEST_COUNTS[identifier]["count"] += 1
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def rate_limit_socketio(max_calls: int, period: int = 60):
    """
    Rate limiting for Socket.IO events.
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Period in seconds (default: 60)
        
    Returns:
        Tuple indicating if the request is allowed and any error message
    """
    def check_rate_limit(sid: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a Socket.IO client has exceeded rate limits.
        
        Args:
            sid: Socket.IO session ID
            
        Returns:
            Tuple of (is_allowed, error_message if any)
        """
        # Use session ID as identifier
        identifier = f"socketio:{sid}"
        
        # Get or initialize the request count
        if identifier not in REQUEST_COUNTS:
            REQUEST_COUNTS[identifier] = {"count": 0, "reset_time": time.time() + period}
        
        # Check if period has reset
        if time.time() > REQUEST_COUNTS[identifier]["reset_time"]:
            REQUEST_COUNTS[identifier] = {"count": 0, "reset_time": time.time() + period}
        
        # Check if rate limit is exceeded
        if REQUEST_COUNTS[identifier]["count"] >= max_calls:
            security_logger.warning(
                "SOCKETIO_RATE_LIMIT_EXCEEDED",
                f"Socket.IO rate limit exceeded for {identifier}",
                {"max_calls": max_calls, "period": period}
            )
            retry_after = int(REQUEST_COUNTS[identifier]["reset_time"] - time.time())
            return False, f"Rate limit exceeded. Retry after {retry_after} seconds."
        
        # Increment count
        REQUEST_COUNTS[identifier]["count"] += 1
        return True, None
    
    return check_rate_limit

# Function implementation using ratelimit library for functions
def rate_limited_function(max_calls: int, period: int = 60):
    """
    Decorator for rate-limiting any function.
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Period in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        @limits(calls=max_calls, period=period)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except RateLimitException:
                security_logger.warning(
                    "FUNCTION_RATE_LIMIT_EXCEEDED",
                    f"Function rate limit exceeded for {func.__name__}",
                    {"max_calls": max_calls, "period": period}
                )
                raise RateLimitError(f"Rate limit exceeded for {func.__name__}")
        
        return wrapper
    
    return decorator
