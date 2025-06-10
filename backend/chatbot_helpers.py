import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv
import logging
import traceback
from datetime import datetime

# Import security modules
from security.logging import configure_logging, SecurityLogger
from security.errors import APIKeyError, ModelError
from security.validation import validate_user_input, sanitize_output
from security.rate_limiting import rate_limited_function

# Configure enhanced logging
configure_logging(app_name="gemini_chatbot", debug=os.environ.get('DEBUG', 'False').lower() == 'true')
logger = logging.getLogger("chatbot")
security_logger = SecurityLogger("chatbot_core")

# Load environment variables
load_dotenv()

# Get API key with validation
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    error_msg = "Google API Key not found. Please set GOOGLE_API_KEY in your .env file."
    security_logger.critical(
        "API_KEY_MISSING",
        error_msg,
        {"timestamp": datetime.now().isoformat()}
    )
    raise APIKeyError(error_msg)

# Configure the Google Generative AI client
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    security_logger.info(
        "API_INITIALIZED",
        "Google Gemini API initialized successfully",
        {"model": "gemini-pro"}
    )
except Exception as e:
    error_details = {
        "error_type": type(e).__name__,
        "timestamp": datetime.now().isoformat(),
        # Don't log the actual exception message as it might contain sensitive info
    }
    security_logger.critical(
        "API_INITIALIZATION_FAILED",
        "Failed to initialize Gemini API",
        error_details
    )
    raise ModelError("Failed to initialize AI model") from e


@rate_limited_function(max_calls=10, period=60)  # Rate limit: 10 calls per minute
def chatbot(user_input):
    """
    Process user input and get a response from the model.
    
    Args:
        user_input: The input from the user
    
    Returns:
        str: The model's response text or error message
    """
    request_id = f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(user_input)}"
    
    try:
        # Start request tracking
        security_logger.info(
            "REQUEST_STARTED",
            "Processing chatbot request",
            {
                "request_id": request_id,
                "input_length": len(user_input) if user_input else 0
            }
        )
        
        # Validate user input using enhanced validation
        is_valid, result = validate_user_input(user_input)
        if not is_valid:
            security_logger.warning(
                "INPUT_VALIDATION_FAILED",
                "Invalid input rejected",
                {
                    "request_id": request_id,
                    "error": result
                }
            )
            return f"Error: {result}"
        
        user_input = result  # Use validated input
        
        # Log input (avoid logging entire content in production)
        input_preview = user_input[:50] + "..." if len(user_input) > 50 else user_input
        logger.info(f"Processing input: {input_preview}")
        
        # Get the response from the model with safety settings
        safety_settings = {
            "HARASSMENT": "BLOCK_MEDIUM_AND_ABOVE",
            "HATE_SPEECH": "BLOCK_MEDIUM_AND_ABOVE",
            "SEXUAL": "BLOCK_MEDIUM_AND_ABOVE",
            "DANGEROUS": "BLOCK_MEDIUM_AND_ABOVE",
        }
        
        # Track model call start time for performance monitoring
        start_time = datetime.now()
        
        response = model.generate_content(
            user_input,
            safety_settings=safety_settings
        )
        
        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds()
        
        # Log successful API call
        security_logger.info(
            "MODEL_CALL_SUCCESSFUL",
            "Model generated response successfully",
            {
                "request_id": request_id,
                "response_time_seconds": response_time
            }
        )
        
        # Validate response
        if not hasattr(response, 'text') or not response.text:
            security_logger.error(
                "EMPTY_MODEL_RESPONSE",
                "Model returned empty or invalid response",
                {"request_id": request_id}
            )
            return "Error: Unable to generate a valid response."
        
        # Sanitize output before returning
        sanitized_response = sanitize_output(response.text)
        
        # Log completion
        security_logger.info(
            "REQUEST_COMPLETED",
            "Chatbot request completed successfully",
            {
                "request_id": request_id,
                "response_length": len(sanitized_response)
            }
        )
            
        return sanitized_response
        
    except Exception as e:
        # Detailed error logging
        error_details = {
            "request_id": request_id,
            "error_type": type(e).__name__,
            "error_traceback": traceback.format_exc()
        }
        
        security_logger.error(
            "REQUEST_FAILED",
            f"Error processing chatbot request: {type(e).__name__}",
            error_details
        )
        
        # Check for production mode
        is_production = os.environ.get('ENVIRONMENT', '').lower() == 'production'
        
        # Return sanitized error message to the user
        if is_production:
            return "Sorry, there was an error processing your request. Please try again later."
        else:
            # In development, include more details
            return f"Error processing request: {str(e)}"
        
    # Uncomment this if stream is true
    # try:
    #     for chunk in response:
    #         yield chunk.text
    # except Exception as e:
    #     logger.error(f"Error in streaming response: {str(e)}", exc_info=True)
    #     yield "Error in streaming response."
