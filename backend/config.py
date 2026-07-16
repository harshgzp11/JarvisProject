"""
config.py — Central configuration module for the Jarvis backend.

All environment variables are loaded here exactly once, and exported as
named constants.  Every other backend module (main.py, database.py,
voice_listener.py) must import from here instead of calling os.getenv()
directly in their own files.

Load priority (highest wins):
  1. Shell environment variables already present at process start
  2. backend/.env  (service-specific overrides)
  3. Root-level .env  (shared project-wide values)
"""

import logging
import os

from dotenv import load_dotenv

_this_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_this_dir)

# Load root .env first (lowest priority — shared defaults).
# override=False means these values only apply if the key is not already in the environment.
load_dotenv(os.path.join(_root_dir, ".env"), override=False)

# Load backend/.env with override=True so it ALWAYS wins over stale shell
# environment variables that uvicorn may have cached from a previous run.
# This ensures changes to .env are respected after uvicorn auto-reloads.
load_dotenv(os.path.join(_this_dir, ".env"), override=True)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT: str = os.getenv("DB_PORT", "3306")
DB_NAME: str = os.getenv("DB_NAME", "jarvis_db")

# ---------------------------------------------------------------------------
# Authentication / Security
# ---------------------------------------------------------------------------
# JWT_SECRET is the canonical key; JWT_SECRET_KEY kept as legacy fallback.
JWT_SECRET: str = os.getenv("JWT_SECRET", os.getenv("JWT_SECRET_KEY", ""))
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

# ---------------------------------------------------------------------------
# Mock / Development Auth  (NEVER enable in production)
# ---------------------------------------------------------------------------
ENABLE_MOCK_AUTH: bool = os.getenv("ENABLE_MOCK_AUTH", "false").lower() == "true"
MOCK_AUTH_TOKEN: str = os.getenv("MOCK_AUTH_TOKEN", "")
DEV_USER_EMAIL: str = os.getenv("DEV_USER_EMAIL", "dev@jarvis.local")
DEV_USER_NAME: str = os.getenv("DEV_USER_NAME", "Jarvis Dev User")

# ---------------------------------------------------------------------------
# Service Endpoints
# ---------------------------------------------------------------------------
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
OLLAMA_ENDPOINT: str = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/chat")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------
WORKSPACE_PATH: str = os.getenv(
    "WORKSPACE_PATH",
    os.path.join(os.path.expanduser("~"), "JarvisWorkspace"),
)

# ---------------------------------------------------------------------------
# Required-key validation
# ---------------------------------------------------------------------------
_REQUIRED_KEYS = [
    "DB_HOST", "DB_PORT", "JWT_SECRET",
    "BACKEND_URL", "OLLAMA_ENDPOINT", "WORKSPACE_PATH",
]

_config_logger = logging.getLogger("jarvis.config")


def verify_required_config() -> list[str]:
    """
    Returns a list of environment-variable names that are missing or empty.
    Logs a CRITICAL entry for each missing key so ops tooling can detect it.
    """
    missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        _config_logger.critical(
            "CRITICAL: Configuration Missing -> %s", ", ".join(missing)
        )
    return missing
