"""
Input validation utilities for the chatbot application.
"""

import re
import logging
from typing import Dict, List, Any, Tuple, Optional
from pydantic import BaseModel, Field, validator
from .errors import InvalidInputError, log_security_event

# Configure logging
logger = logging.getLogger("security.validation")

# Regular expressions for validation
HARMFUL_PATTERNS = [
    r"(?i)system\s*\(",
    r"(?i)exec\s*\(",
    r"(?i)eval\s*\(",
    r"(?i)os\.",
    r"(?i)subprocess\.",
    r"(?i)<script>",
    r"(?i)DROP\s+TABLE",
    r"(?i)DELETE\s+FROM"
]

class UserInput(BaseModel):
    """Pydantic model for validating user input to the chatbot."""
    content: str = Field(..., min_length=1, max_length=4000)
    
    @validator('content')
    def content_must_not_contain_harmful_patterns(cls, v):
        """Validate that the content doesn't contain harmful patterns."""
        for pattern in HARMFUL_PATTERNS:
            if re.search(pattern, v):
                log_security_event(
                    "HARMFUL_PATTERN_DETECTED",
                    f"Harmful pattern detected in user input",
                    {"pattern": pattern, "input_preview": v[:50] + "..." if len(v) > 50 else v}
                )
                raise InvalidInputError(f"Input contains potentially harmful content")
        return v

class UserCredentials(BaseModel):
    """Pydantic model for validating user credentials."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')

def validate_user_input(input_text: str) -> Tuple[bool, str]:
    """
    Validate user input for the chatbot.
    
    Args:
        input_text: The text input from the user
        
    Returns:
        Tuple of (is_valid, sanitized_input or error_message)
    """
    try:
        # Use Pydantic model for validation
        validated = UserInput(content=input_text)
        
        # Additional custom validation can be added here
        
        # Return sanitized input (here we simply trim and normalize whitespace)
        sanitized_input = validated.content.strip()
        return True, sanitized_input
    
    except InvalidInputError as e:
        # These are expected validation errors
        logger.warning(f"Input validation failed: {str(e)}")
        return False, str(e)
    
    except Exception as e:
        # Unexpected validation errors
        logger.error(f"Unexpected error during input validation: {str(e)}", exc_info=True)
        return False, "Input validation failed"

def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username input.
    
    Args:
        username: The username to validate
        
    Returns:
        Tuple of (is_valid, error_message if any)
    """
    try:
        # Use Pydantic model for validation
        validated = UserCredentials(username=username)
        return True, None
    
    except Exception as e:
        logger.warning(f"Username validation failed: {str(e)}")
        return False, "Username must be 3-50 characters and contain only letters, numbers, underscores, and hyphens"

def sanitize_output(output: str) -> str:
    """
    Sanitize the model's output to prevent leakage of sensitive information.
    
    Args:
        output: The raw output from the model
        
    Returns:
        Sanitized output string
    """
    # Example sanitization rules - can be expanded
    # Remove anything that looks like an API key
    sanitized = re.sub(r'[A-Za-z0-9_-]{20,}', '[REDACTED]', output)
    
    # Remove anything that looks like an email address
    sanitized = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL REDACTED]', sanitized)
    
    return sanitized
