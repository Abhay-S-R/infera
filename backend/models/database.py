import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

from backend.config import settings

_db_available: bool = True
_db_last_check: float = 0.0
_DB_CHECK_TTL_SECONDS = 5.0


engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def _migrate_schema(connection) -> None:
    """Add columns/tables introduced after initial deploy (create_all is not additive)."""
    from sqlalchemy import text

    await connection.execute(
        text(
            """
            ALTER TABLE workflows
            ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0
            """
        )
    )
    await connection.execute(
        text(
            """
            ALTER TABLE workflows
            ADD COLUMN IF NOT EXISTS estimated_cost DOUBLE PRECISION DEFAULT 0.0
            """
        )
    )


def set_database_available(available: bool) -> None:
    global _db_available, _db_last_check
    _db_available = available
    _db_last_check = time.monotonic()


async def check_database_connection() -> bool:
    """Ping Postgres; update cached availability flag."""
    global _db_available, _db_last_check
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        _db_available = True
    except Exception:
        _db_available = False
    _db_last_check = time.monotonic()
    return _db_available


async def is_database_available() -> bool:
    """Return cached Postgres availability (re-check at most every few seconds)."""
    global _db_last_check
    if time.monotonic() - _db_last_check > _DB_CHECK_TTL_SECONDS:
        await check_database_connection()
    return _db_available


async def init_db() -> None:
    """Initialize database schema on startup."""
    from backend.models.tables import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await _migrate_schema(connection)
    set_database_available(True)
