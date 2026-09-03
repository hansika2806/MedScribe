"""PostgreSQL connection with async support and connection pooling."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global engine and session maker
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


def get_database_url() -> str:
    """Get database URL from settings or environment."""
    # Check if DATABASE_URL is set (for production)
    import os
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # Ensure it uses asyncpg driver
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return db_url
    
    # Fallback to SQLite for development
    return "sqlite+aiosqlite:///./data/medscribe.db"


def create_engine() -> AsyncEngine:
    """Create async database engine with connection pooling."""
    db_url = get_database_url()
    
    is_postgres = "postgresql" in db_url
    
    engine_kwargs: dict = {
        "echo": settings.debug if hasattr(settings, 'debug') else False,
        "future": True,
    }
    
    if is_postgres:
        # PostgreSQL with connection pooling
        engine_kwargs["poolclass"] = QueuePool
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 3600
        logger.info("Using PostgreSQL with connection pooling")
    else:
        # SQLite without pooling
        engine_kwargs["poolclass"] = NullPool
        logger.info("Using SQLite (development mode)")
    
    return create_async_engine(db_url, **engine_kwargs)


def get_engine() -> AsyncEngine:
    """Get or create the global engine."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the global session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Get an async database session.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    engine = get_engine()
    
    # For PostgreSQL, tables are created by init.sql
    # For SQLite, we need to create them programmatically
    db_url = get_database_url()
    
    if "sqlite" in db_url:
        logger.info("Initializing SQLite database...")
        # Import and create tables using SQLAlchemy models
        from backend.database.models import SCHEMA_STATEMENTS
        
        async with get_session() as session:
            for statement in SCHEMA_STATEMENTS:
                # Convert SQLite syntax to work with async
                try:
                    await session.execute(text(statement))
                except Exception as e:
                    logger.warning(f"Error executing statement: {e}")
        
        logger.info("SQLite database initialized")
    else:
        logger.info("PostgreSQL database initialized via init.sql")


async def close_db() -> None:
    """Close database connections."""
    global _engine, _async_session_maker
    
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database connections closed")


async def health_check() -> bool:
    """Check database connectivity."""
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# Dependency for FastAPI
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @app.get("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(query)
    """
    async with get_session() as session:
        yield session

# Made with Bob
