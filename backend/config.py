"""
ASCENT Configuration — loads from .env file.
All team members: import settings from here, never read os.environ directly.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Always load ascent/.env regardless of current working directory (e.g. demo/fixtures).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ascent:ascent_pass@localhost:5432/ascent_db"
    DATABASE_URL_SYNC: str = "postgresql://ascent:ascent_pass@localhost:5432/ascent_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Optional integrations
    OMIUM_API_KEY: Optional[str] = None
    OMIUM_ENDPOINT: str = "https://api.omium.dev"
    OMIUM_WORKSPACE: str = "ascent"
    SLACK_WEBHOOK_URL: Optional[str] = None

    # App config
    DEMO_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    MAX_TOKENS_PER_WORKFLOW: int = 500_000
    MAX_COST_PER_WORKFLOW: float = 2.00

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # Scheduling (Dev 1)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_MINUTES: int = 5

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
