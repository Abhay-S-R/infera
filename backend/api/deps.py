"""Shared FastAPI dependencies."""
from fastapi import HTTPException

from backend.core.database import is_database_available


async def require_database() -> None:
    """Raise 503 when Postgres is unreachable."""
    if not await is_database_available():
        raise HTTPException(status_code=503, detail="Database unavailable")
