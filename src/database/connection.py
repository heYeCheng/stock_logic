"""Async MySQL connection pool using SQLAlchemy 2.0 + aiomysql.

Per D-01: MySQL only, no SQLite dual-support.
Connection string format: mysql+aiomysql://user:password@host:port/database
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Base class for ORM models
Base = declarative_base()

# Database URL from environment variable
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+aiomysql://root:root@127.0.0.1:3306/stock_logic"
)

# Async engine with connection pooling
# pool_size=10, max_overflow=20, pool_pre_ping=True per plan constraints
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Connection health check before use
    echo=False,  # Set True for SQL debugging
    future=True,  # Ensure SQLAlchemy 2.0 behavior
)

# AsyncSession factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent async issues after commit
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injector for FastAPI (future use).

    Yields:
        AsyncSession: Database session for request handling.

    Usage:
        async def my_endpoint(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables.

    Usage:
        from src.database.connection import init_db
        await init_db()
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database engine connections.

    Call on application shutdown.
    """
    await engine.dispose()
