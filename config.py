"""App configuration."""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
TRICOUNT_ID = "tiBfSEGXQrDizSkrlO"
CREDENTIALS_PATH = BASE_DIR / "tricount_credentials.json"

# Flask config
DEBUG = os.getenv("FLASK_ENV") == "development"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# Cache settings (in seconds)
# Long TTL since we bust manually via /api/cache/clear or the refresh button
CACHE_TTL = 1800  # 30 minutes
