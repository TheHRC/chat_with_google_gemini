"""
Custom error classes and error handling utilities for the chatbot application.
"""

import logging
from enum import Enum

# Configure logging
logger = logging.getLogger("security")

class SecurityErrorLevel(Enum):
    """Enum for categorizing security errors by severity level."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class SecurityError(Exception):
    """Base class for all security-related exceptions in the application."""
    def __init__(self, message, level=SecurityErrorLevel.ERROR, details=None):
        self.message = message
        self.level = level
        self.details = details
        
        # Log with appropriate level
        if level == SecurityErrorLevel.INFO:
            logger.info(f"Security Info: {message}", extra={"details": details})
        elif level == SecurityErrorLevel.WARNING:
            logger.warning(f"Security Warning: {message}", extra={"details": details})
        elif level == SecurityErrorLevel.ERROR:
            logger.error(f"Security Error: {message}", extra={"details": details})
        elif level == SecurityErrorLevel.CRITICAL:
            logger.critical(f"Security Critical: {message}", extra={"details": details})
            
        super().__init__(message)

class AuthenticationError(SecurityError):
    """Raised when authentication fails."""
    def __init__(self, message="Authentication failed", details=None):
        super().__init__(message, SecurityErrorLevel.WARNING, details)

class InvalidInputError(SecurityError):
    """Raised when input validation fails."""
    def __init__(self, message="Invalid input provided", details=None):
        super().__init__(message, SecurityErrorLevel.WARNING, details)

class APIKeyError(SecurityError):
    """Raised when there are issues with API keys."""
    def __init__(self, message="API key error", details=None):
        super().__init__(message, SecurityErrorLevel.CRITICAL, details)

class RateLimitError(SecurityError):
    """Raised when rate limits are exceeded."""
    def __init__(self, message="Rate limit exceeded", details=None):
        super().__init__(message, SecurityErrorLevel.WARNING, details)

class ModelError(SecurityError):
    """Raised when the LLM model encounters issues."""
    def __init__(self, message="Model error occurred", details=None):
        super().__init__(message, SecurityErrorLevel.ERROR, details)

# Error handling utilities
def get_safe_error_message(error: Exception, is_production: bool) -> str:
    """
    Returns a user-friendly error message depending on the environment.
    
    In production, returns a generic message without technical details.
    In development, returns more details to help with debugging.
    
    Args:
        error: The exception that occurred
        is_production: Boolean indicating if the app is running in production
        
    Returns:
        A user-friendly error message
    """
    if is_production:
        if isinstance(error, SecurityError):
            # Even in production, we can customize messages for our known error types
            if isinstance(error, InvalidInputError):
                return "The input provided was invalid. Please try again."
            elif isinstance(error, RateLimitError):
                return "Too many requests. Please try again later."
            else:
                return "An unexpected error occurred. Please try again later."
        else:
            # Generic message for unknown errors in production
            return "An unexpected error occurred. Please try again later."
    else:
        # In development, return more details
        return str(error)

def log_security_event(event_type: str, message: str, details: dict = None):
    """
    Log a security-related event with standardized formatting.
    
    Args:
        event_type: Type of security event (e.g., "ACCESS_ATTEMPT", "VALIDATION_FAILURE")
        message: Description of the event
        details: Additional context for the event
    """
    if details is None:
        details = {}
    
    logger.info(
        f"SECURITY_EVENT: {event_type} - {message}",
        extra={
            "security_event": {
                "type": event_type,
                "message": message,
                "details": details
            }
        }
    )
