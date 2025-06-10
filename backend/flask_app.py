import os
import json
import logging
from datetime import datetime
from chatbot_helpers import chatbot
from langchain_llm import llm_initializer
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Flask app & socket setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# DB Setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)

# Embeddings path
embeddings_path = input("Enter the embedding's path: ").strip()
llm = llm_initializer(embeddings_path)


# Define User and Message models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)


with app.app_context():
    db.create_all()


@app.get("/")
def index():
    render_template("index.html")


# Import security modules
from security.validation import validate_user_input, validate_username
from security.logging import SecurityLogger
from security.rate_limiting import rate_limit, rate_limit_socketio
from security.errors import get_safe_error_message

# Initialize security logger
security_logger = SecurityLogger("flask_app")

# Configure rate limiting for socket.io
message_rate_limit = rate_limit_socketio(max_calls=20, period=60)  # 20 messages per minute

@socketio.on('message')
def handle_message(message):
    try:
        # Rate limit check
        is_allowed, error_message = message_rate_limit(request.sid)
        if not is_allowed:
            security_logger.warning(
                "SOCKET_RATE_LIMIT_EXCEEDED", 
                "Rate limit exceeded for socket message", 
                {"sid": request.sid}
            )
            socketio.emit('response', f"Error: {error_message}", room=request.sid)
            return
            
        # Log and validate the message
        security_logger.info(
            "SOCKET_MESSAGE_RECEIVED", 
            "Received message via socket", 
            {"sid": request.sid, "message_length": len(message) if message else 0}
        )
        
        # Validate the input
        is_valid, result = validate_user_input(message)
        if not is_valid:
            security_logger.warning(
                "INVALID_SOCKET_INPUT", 
                "Invalid input received via socket", 
                {"sid": request.sid, "error": result}
            )
            socketio.emit('response', f"Error: {result}", room=request.sid)
            return
            
        # Process with validated input
        validated_message = result
        
        # Google gemini processing
        response = llm.ask_llm(validated_message)
        
        # Emit the response
        socketio.emit('response', response, room=request.sid)
        
        # Log successful message processing
        security_logger.info(
            "SOCKET_MESSAGE_PROCESSED", 
            "Successfully processed socket message", 
            {"sid": request.sid, "response_length": len(response) if response else 0}
        )
    except Exception as e:
        # Log error
        security_logger.error(
            "SOCKET_MESSAGE_ERROR", 
            f"Error processing socket message: {type(e).__name__}", 
            {"sid": request.sid, "error": str(e)}
        )
        
        # Return safe error message
        is_production = os.environ.get('ENVIRONMENT', '').lower() == 'production'
        error_msg = get_safe_error_message(e, is_production)
        socketio.emit('response', f"Error: {error_msg}", room=request.sid)


@app.route('/set_username', methods=['POST'])
@rate_limit(max_calls=5, period=60)  # Rate limit: 5 registrations per minute per IP
def set_username():
    try:
        # Get and validate data
        data = request.get_json()
        if not data:
            security_logger.warning(
                "MISSING_REQUEST_DATA", 
                "No JSON data in request", 
                {"route": "/set_username", "remote_addr": request.remote_addr}
            )
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        username = data.get('username')
        if not username:
            security_logger.warning(
                "MISSING_USERNAME", 
                "Username missing in request", 
                {"route": "/set_username", "remote_addr": request.remote_addr}
            )
            return jsonify({'success': False, 'message': 'Username is required'}), 400
            
        # Validate username
        is_valid, error_message = validate_username(username)
        if not is_valid:
            security_logger.warning(
                "INVALID_USERNAME", 
                "Invalid username format", 
                {"route": "/set_username", "remote_addr": request.remote_addr}
            )
            return jsonify({'success': False, 'message': error_message}), 400
        
        # Check if username exists
        user = User.query.filter_by(username=username).first()

        if user is None:
            # Create new user
            new_user = User(username=username)
            db.session.add(new_user)
            db.session.commit()
            
            security_logger.info(
                "USER_CREATED", 
                "New user registered", 
                {"username": username}
            )
            return jsonify({'success': True})
        else:
            security_logger.info(
                "USERNAME_CONFLICT", 
                "Attempted registration with existing username", 
                {"username": username}
            )
            return jsonify({'success': False, 'message': 'Username already taken'}), 409
    except Exception as e:
        # Log the error
        security_logger.error(
            "USERNAME_REGISTRATION_ERROR", 
            f"Error in username registration: {type(e).__name__}", 
            {"error": str(e)}
        )
        
        # Return safe error message
        is_production = os.environ.get('ENVIRONMENT', '').lower() == 'production'
        return jsonify({
            'success': False, 
            'message': get_safe_error_message(e, is_production)
        }), 500


if __name__ == '__main__':
    # socketio.run(app, host="192.168.1.4", port=5000)
    socketio.run(app, port=5000)

