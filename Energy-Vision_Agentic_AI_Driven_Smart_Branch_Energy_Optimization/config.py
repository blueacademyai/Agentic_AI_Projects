# config.py
"""
EnerVision Configuration Management
"""
import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application settings"""
    
    # Application
    app_name: str = "EnerVision"
    app_version: str = "1.0.0"
    debug_mode: bool = os.getenv("DEBUG_MODE", "False").lower() == "true"
    
    # API Keys
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "demo_key")
    agentops_api_key: str = os.getenv("AGENTOPS_API_KEY", "demo_key")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "demo_key")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///enervision.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Email - These are the key ones for your SMTP functionality
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "demo_secret_key")
    jwt_secret: str = os.getenv("JWT_SECRET", "demo_jwt_secret")
    
    # File Processing
    max_file_size: str = os.getenv("MAX_FILE_SIZE", "10MB")
    allowed_extensions: List[str] = ["pdf", "docx", "txt", "csv", "json"]
    
    # RAG Settings
    embedding_model: str = "all-MiniLM-L6-v2"
    max_chunk_size: int = 512
    chunk_overlap: int = 50
    similarity_threshold: float = 0.7
    
    # Agent Settings
    max_agents: int = 10
    agent_timeout: int = 300  # seconds
    max_retries: int = 3
    
    # Monitoring
    enable_monitoring: bool = True
    health_check_interval: int = 60
    log_level: str = "INFO"

# Global settings instance
settings = Settings()

# Rest of your FeatureFlags, Constants, etc. classes stay the same...


# Feature flags
class FeatureFlags:
    """Feature flag management"""
    
    ENABLE_AI_AGENTS = True
    ENABLE_RAG_CHATBOT = True
    ENABLE_ANOMALY_DETECTION = True
    ENABLE_FORECASTING = True
    ENABLE_EMAIL_NOTIFICATIONS = True
    ENABLE_DOCUMENT_UPLOAD = True
    ENABLE_REPORT_GENERATION = True
    ENABLE_WORK_ORDERS = True
    ENABLE_MONITORING = True
    
    # Advanced features
    ENABLE_REAL_TIME_MONITORING = False
    ENABLE_ADVANCED_ML_MODELS = False
    ENABLE_MULTI_TENANT = False
    ENABLE_API_ACCESS = False

# Constants
class Constants:
    """Application constants"""
    
    # Energy metrics
    DEFAULT_COST_PER_KWH = 0.12
    DEFAULT_CARBON_FACTOR = 0.0005  # tons CO2 per kWh
    
    # ESG scoring
    ESG_SCORE_MIN = 0.0
    ESG_SCORE_MAX = 10.0
    ESG_TARGET_SCORE = 8.0
    
    # Anomaly detection
    ANOMALY_THRESHOLD_SIGMA = 2.0
    ANOMALY_WINDOW_DAYS = 7
    
    # Forecasting
    FORECAST_CONFIDENCE_LEVEL = 0.85
    MAX_FORECAST_DAYS = 365
    
    # UI
    MAX_CHART_POINTS = 1000
    DEFAULT_PAGE_SIZE = 50
    
    # File processing
    MAX_DOCUMENT_PAGES = 100
    MAX_CHUNKS_PER_DOCUMENT = 500
    
    # Rate limits
    MAX_QUERIES_PER_MINUTE = 60
    MAX_FILES_PER_UPLOAD = 10
    
    # Monitoring
    HEALTH_CHECK_ENDPOINTS = [
        "/health",
        "/api/health",
        "/monitoring/health"
    ]

# Database configuration
DATABASE_CONFIG = {
    "sqlite": {
        "driver": "sqlite3",
        "database": "enervision.db",
        "check_same_thread": False
    },
    "postgresql": {
        "driver": "postgresql",
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "enervision"),
        "username": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASS", "password")
    }
}

# Email templates
EMAIL_TEMPLATES = {
    "work_order": {
        "subject": "New Work Order: {title}",
        "template": """
        <h2>New Work Order Created</h2>
        <p><strong>Work Order ID:</strong> {id}</p>
        <p><strong>Title:</strong> {title}</p>
        <p><strong>Priority:</strong> {priority}</p>
        <p><strong>Branch:</strong> {branch}</p>
        <p><strong>Due Date:</strong> {due_date}</p>
        <p><strong>Description:</strong></p>
        <p>{description}</p>
        <p><strong>Special Instructions:</strong></p>
        <p>{instructions}</p>
        <p>Please log into EnerVision to view complete details.</p>
        """
    },
    "anomaly_alert": {
        "subject": "Energy Anomaly Detected - {branch}",
        "template": """
        <h2>Energy Consumption Anomaly Alert</h2>
        <p><strong>Branch:</strong> {branch}</p>
        <p><strong>Date:</strong> {date}</p>
        <p><strong>Consumption:</strong> {consumption} kWh</p>
        <p><strong>Expected:</strong> {expected} kWh</p>
        <p><strong>Deviation:</strong> {deviation}%</p>
        <p><strong>Severity:</strong> {severity}</p>
        <p>Please investigate this anomaly and take appropriate action.</p>
        """
    },
    "report_ready": {
        "subject": "EnerVision Report Ready - {report_type}",
        "template": """
        <h2>Your EnerVision Report is Ready</h2>
        <p><strong>Report Type:</strong> {report_type}</p>
        <p><strong>Generated:</strong> {timestamp}</p>
        <p><strong>Branches Covered:</strong> {branches}</p>
        <p>Your report has been generated successfully. Please log into EnerVision to download it.</p>
        """
    }
}

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard"
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/enervision.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "detailed"
        }
    },
    "loggers": {
        "enervision": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "streamlit": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    }
}