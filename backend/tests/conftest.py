"""Shared pytest fixtures for async SQLAlchemy and database testing."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from core.config import settings
from core.base_models import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide an isolated database session with dedicated NullPool per test."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()

    await test_engine.dispose()
