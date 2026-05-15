"""
ASCENT Configuration — loads from .env file.
All team members: import settings from here, never read os.environ directly.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ascent:ascent_pass@localhost:5433/ascent_db"
    DATABASE_URL_SYNC: str = "postgresql://ascent:ascent_pass@localhost:5433/ascent_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Optional integrations
    OMIUM_API_KEY: Optional[str] = None
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

    # Scheduling
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_MINUTES: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
