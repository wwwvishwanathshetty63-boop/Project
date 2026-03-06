import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT = int(os.getenv("PORT", 5000))

    # Database (SQLite)
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
    _db_path = os.getenv("DATABASE_PATH", "database.db")
    DATABASE_PATH = _db_path if os.path.isabs(_db_path) else os.path.join(_PROJECT_ROOT, _db_path)

    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET", "jwt-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

    # SMTP Email
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "API Monitor")

    # Monitoring
    MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", 60))
    REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", 30))
    CONSECUTIVE_FAILURES_THRESHOLD = 3

    # Rate Limiting
    RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "200 per hour")

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
