"""
Enhanced security logging for the chatbot application.
"""

import os
import logging
import json
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any, Optional

# Constants
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
SECURITY_LOG_FILE = os.path.join(LOG_DIR, "security.log")
APPLICATION_LOG_FILE = os.path.join(LOG_DIR, "application.log")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Custom formatter for security logs
class SecurityLogFormatter(logging.Formatter):
    """Custom formatter for security logs that includes additional context."""
    
    def format(self, record):
        """Format the log record with additional security context."""
        # Get the original formatted message
        message = super().format(record)
        
        # Add security context if available
        if hasattr(record, 'security_event'):
            security_context = record.security_event
        else:
            security_context = {}
            
        # Add timestamp and log level
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "message": record.message,
            "security_context": security_context,
            # Add source information
            "source": {
                "file": record.pathname,
                "function": record.funcName,
                "line": record.lineno
            }
        }
        
        # Return JSON formatted log entry
        return json.dumps(log_entry)

def configure_logging(app_name: str = "chatbot", debug: bool = False):
    """
    Configure the application's logging system with security focus.
    
    Args:
        app_name: Name of the application for logging context
        debug: Whether to enable debug logging
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
            
    # Create handlers
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    console_handler.setFormatter(logging.Formatter(console_format))
    
    # Application log file handler (rotating to prevent huge log files)
    app_file_handler = RotatingFileHandler(
        APPLICATION_LOG_FILE,
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    app_file_handler.setLevel(log_level)
    app_file_handler.setFormatter(logging.Formatter(console_format))
    
    # Security log file handler (rotating with JSON formatting)
    security_file_handler = RotatingFileHandler(
        SECURITY_LOG_FILE,
        maxBytes=10485760,  # 10MB
        backupCount=10  # Keep more backups of security logs
    )
    security_file_handler.setLevel(logging.INFO)  # Security logs are always at least INFO level
    security_file_handler.setFormatter(SecurityLogFormatter())
    
    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_file_handler)
    
    # Create and configure security logger specifically
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    security_logger.addHandler(security_file_handler)
    security_logger.propagate = False  # Don't propagate to root logger
    
    # Log startup message
    root_logger.info(f"{app_name} logging initialized at {datetime.now().isoformat()}")
    security_logger.info(f"{app_name} security logging initialized", 
                        extra={"security_event": {"type": "LOGGING_INITIALIZED"}})

class SecurityLogger:
    """
    Security-focused logger that adds context to log entries.
    Use this to log security-related events with proper context.
    """
    
    def __init__(self, component_name: str):
        """
        Initialize a security logger for a specific component.
        
        Args:
            component_name: Name of the component (e.g., "auth", "api", "validation")
        """
        self.logger = logging.getLogger(f"security.{component_name}")
        self.component_name = component_name
    
    def _log(self, level: int, event_type: str, message: str, details: Dict[str, Any] = None):
        """Internal method to log with security context."""
        if details is None:
            details = {}
            
        # Add component name to context
        details["component"] = self.component_name
        
        # Add timestamp
        details["timestamp"] = time.time()
        
        self.logger.log(
            level,
            message,
            extra={
                "security_event": {
                    "type": event_type,
                    "details": details
                }
            }
        )
    
    def info(self, event_type: str, message: str, details: Dict[str, Any] = None):
        """Log a security info event."""
        self._log(logging.INFO, event_type, message, details)
    
    def warning(self, event_type: str, message: str, details: Dict[str, Any] = None):
        """Log a security warning event."""
        self._log(logging.WARNING, event_type, message, details)
    
    def error(self, event_type: str, message: str, details: Dict[str, Any] = None):
        """Log a security error event."""
        self._log(logging.ERROR, event_type, message, details)
    
    def critical(self, event_type: str, message: str, details: Dict[str, Any] = None):
        """Log a critical security event."""
        self._log(logging.CRITICAL, event_type, message, details)
