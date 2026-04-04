"""Async database engine, session factory, and dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.base import Base

# ---------------------------------------------------------------------------
# Convert the standard PostgreSQL URL to an async one (asyncpg driver).
# Allows callers to set DATABASE_URL with either prefix.
# ---------------------------------------------------------------------------
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("postgresql://"):
    _async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgresql+asyncpg://"):
    _async_url = _raw_url
else:
    _async_url = _raw_url  # let SQLAlchemy surface a clear error

engine = create_async_engine(
    _async_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an ``AsyncSession`` and ensures cleanup.

    Usage::

        @router.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables defined on ``Base.metadata``.

    Intended for development / test bootstrapping.  In production, use Alembic
    migrations instead.
    """
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Ensure physician_id is nullable (appointments can be created during
        # intake before a physician is assigned).
        await conn.execute(
            text("ALTER TABLE appointments ALTER COLUMN physician_id DROP NOT NULL")
        )
