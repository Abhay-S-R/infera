"""
ASCENT Configuration — loads from .env file.
All team members: import settings from here, never read os.environ directly.
"""
from pathlib import Path

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    SLACK_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Slack Incoming Webhook URL (https://hooks.slack.com/services/...).",
    )

    OUTBOUND_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Optional HTTPS URL for a generic JSON POST on report completion (Zapier, etc.).",
    )

    # Delivery Integrations
    LINEAR_API_KEY: Optional[str] = None
    LINEAR_TEAM_ID: Optional[str] = None

    # Delivery (Dev 3 — SendGrid CEO brief)
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = None
    CEO_EMAIL: Optional[str] = None

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

    # Phase 4 — verification & demo
    VERIFIER_STRICT: bool = True
    VERIFIER_DEMO_PASS_TITLES: str = (
        "golden path,nimbus ai,scheduled scan: nimbus"
    )
    REPORTS_OUTPUT_DIR: str = "reports_output"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
