import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

# Import database and middleware setup
from backend.app.core.database import db
from backend.app.core.middleware import setup_middleware
from backend.app.core.exceptions import AppException
from backend.app.config import config_by_name

# Initialize Flask Extensions
cors = CORS()
jwt = JWTManager()
socketio = SocketIO(cors_allowed_origins="*")

def create_app(config_name="development"):
    """
    Application Factory to construct and configure the Flask app.
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config_by_name[config_name])
    
    # Configure Logging
    configure_logging(app)
    
    # Initialize Extensions
    db.init_app(app)
    cors.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)
    
    # Setup Middleware (tenant extraction, latency tracking)
    setup_middleware(app)
    
    # Register Global Exception Handlers
    register_error_handlers(app)
    
    # Register blueprints (routes will be added in subsequent phases)
    register_blueprints(app)
    
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "environment": config_name,
            "database": "connected" if db.engine else "disconnected"
        }), 200

    return app

def configure_logging(app):
    """
    Configures rotating file logs and console logging for observability.
    """
    log_dir = os.path.abspath(os.path.join(app.root_path, "../logs"))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, "nexora.log")
    
    # Rotating handler: 10MB limit, keep 5 archive files
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s:%(lineno)d] - %(message)s'
    ))
    file_handler.setLevel(logging.INFO)
    
    # Attach to root logger
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.INFO)
    
    app.logger.info("Nexora AI logger initialized.")

def register_error_handlers(app):
    """
    Global exception handling for consistent API JSON responses.
    """
    @app.errorhandler(AppException)
    def handle_app_exception(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        # Log the full exception traceback
        app.logger.exception(f"Unhandled system error: {error}")
        response = jsonify({
            "status": "error",
            "message": "An internal server error occurred"
        })
        response.status_code = 500
        return response

def register_blueprints(app):
    """
    Registers blueprints for different business domains.
    """
    # Import blueprints dynamically to avoid circular references
    from backend.app.domains.auth.routes import auth_bp
    from backend.app.domains.lms.routes import lms_bp
    from backend.app.domains.chat.routes import chat_bp
    
    # Versioned API path
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(lms_bp, url_prefix="/api/v1/lms")
    app.register_blueprint(chat_bp, url_prefix="/api/v1/chat")

    # Import sockets module to register event handlers
    import backend.app.domains.chat.sockets
