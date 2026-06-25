import os
from dotenv import load_dotenv
from backend.app import create_app, socketio, db

# Load environment variables from .env file
load_dotenv()

# Select config name based on environment
env_name = os.getenv("FLASK_ENV", "development")
app = create_app(env_name)

if __name__ == "__main__":
    # Create tables locally if using SQLite for ease of development
    with app.app_context():
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
            db.create_all()
            print("SQLite tables created successfully.")

    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug = app.config.get("DEBUG", True)
    
    print(f"Starting Nexora AI API Server on {host}:{port} ({env_name} mode)...")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
