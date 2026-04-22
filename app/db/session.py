"""
Database Session Management
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import Base  # single source of truth for Base

logger = get_logger(__name__)

# Ensure we use an async-compatible URL for SQLite
_db_url = settings.database_url
if _db_url.startswith("sqlite://"):
    _db_url = _db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

_connect_args = {"check_same_thread": False} if "sqlite" in _db_url else {}
_pool_class = StaticPool if "sqlite" in _db_url else None

engine = create_async_engine(
    _db_url,
    echo=settings.is_development,
    poolclass=_pool_class,
    connect_args=_connect_args,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception("Database session error", error=str(e))
            raise
        finally:
            await session.close()


async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.exception("Failed to initialize database", error=str(e))
        raise


async def close_db() -> None:
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.exception("Error closing database connections", error=str(e))
