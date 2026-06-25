import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "nexora-super-secret-key-12345")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "nexora-jwt-secret-key-67890")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    
    # SQLite for local development, PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///nexora.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Uploads configuration
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads")))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB limit

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, require secure cookies for refresh tokens
    JWT_COOKIE_SECURE = True
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT = True

config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}
