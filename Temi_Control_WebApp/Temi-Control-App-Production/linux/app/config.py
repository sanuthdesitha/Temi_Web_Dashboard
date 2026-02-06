"""
Configuration Management for Temi Control Web Application

Supports environment-based configuration for development, staging, and production.
Load configuration from environment variables or use defaults.
"""

import os
from datetime import timedelta


class Config:
    """Base configuration"""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-CHANGE-IN-PROD'
    DEBUG = False

    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or './temi_control.db'

    # MQTT Broker Configuration
    MQTT_BROKER = os.environ.get('MQTT_BROKER') or 'localhost'
    MQTT_PORT = int(os.environ.get('MQTT_PORT') or 1883)
    MQTT_USERNAME = os.environ.get('MQTT_USERNAME') or None
    MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD') or None
    MQTT_USE_TLS = os.environ.get('MQTT_USE_TLS', 'false').lower() == 'true'

    # MQTT Topic Configuration
    MQTT_BASE_TOPIC = 'temi'
    YOLO_DETECTION_TOPIC = 'yolo/detection'
    YOLO_MESSAGE_TIMEOUT = 30  # seconds

    # Position Tracking
    POSITION_HISTORY_MAX = 500  # maximum positions per robot
    POSITION_UPDATE_THROTTLE = 500  # milliseconds between updates

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or './logs/temi_control.log'

    # Performance
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25
    SOCKETIO_MESSAGE_QUEUE = None  # Use Redis in production for scaling

    # API Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "200 per day, 50 per hour"
    RATELIMIT_LOGIN = "5 per minute"

    # File Upload
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or './uploads'
    ALLOWED_EXTENSIONS = {'csv', 'json', 'txt'}

    # Email Configuration (for alerts)
    EMAIL_ENABLED = os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
    SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'smtp.gmail.com'
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME') or None
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or None
    ALERT_EMAIL_RECIPIENTS = os.environ.get('ALERT_EMAIL_RECIPIENTS', '').split(',')

    # SMS Configuration (for alerts)
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false').lower() == 'true'
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID') or None
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN') or None
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER') or None

    # Violation Alert Settings
    VIOLATION_HIGH_SEVERITY_THRESHOLD = 5  # violations within 60 seconds
    VIOLATION_ALERT_COOLDOWN = 300  # seconds (don't alert more than once per 5 min)

    # Feature Flags
    ENABLE_YOLO_MONITORING = True
    ENABLE_POSITION_TRACKING = True
    ENABLE_SCHEDULED_PATROLS = True
    ENABLE_ROUTE_OPTIMIZATION = True

    @staticmethod
    def init_app(app):
        """Initialize application with config"""
        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        # Create log folder if it doesn't exist
        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False

    # Allow cross-origin requests in development
    CORS_ORIGINS = "*"


class TestingConfig(Config):
    """Testing configuration"""

    TESTING = True
    DATABASE_PATH = ':memory:'  # Use in-memory database
    SOCKETIO_ASYNC_MODE = 'threading'

    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False

    # Force HTTPS
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'

    # Stricter CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://temi-control.example.com').split(',')

    # Use Redis for message queues (requires redis-server running)
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # Redis cache
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/1'

    # Higher rate limits for production
    RATELIMIT_DEFAULT = "500 per day, 100 per hour"


class StagingConfig(ProductionConfig):
    """Staging configuration (similar to production with some relaxed limits)"""

    DEBUG = False
    TESTING = False

    # Slightly more lenient than production
    RATELIMIT_DEFAULT = "1000 per day, 200 per hour"


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'staging': StagingConfig,
    'default': DevelopmentConfig
}


def get_config() -> Config:
    """
    Get configuration based on FLASK_ENV environment variable

    Returns:
        Config class instance
    """
    env = os.environ.get('FLASK_ENV', 'development').lower()
    config_class = config.get(env, DevelopmentConfig)
    return config_class
