from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

from backend.config import settings


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


async def init_db() -> None:
    """Initialize database schema on startup."""
    from backend.models.tables import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await _migrate_schema(connection)
