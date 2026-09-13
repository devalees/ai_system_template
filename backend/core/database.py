"""Database engine, async session factory, and automatic multi-tenancy & soft-delete query filtration."""

from typing import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria, Session
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings
from core.context import get_active_company_id, get_current_user_id
from core.base_models import SoftDeleteMixin, TenantMixin

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@event.listens_for(AsyncSession.sync_session_class, "do_orm_execute")
def _add_automatic_query_filtration(execute_state):
    """Intercept all ORM SELECT statements and inject soft-delete and multi-tenancy filters."""
    if execute_state.is_select:
        include_deleted = execute_state.execution_options.get("include_deleted", False)
        ignore_tenant = execute_state.execution_options.get("ignore_tenant", False)

        criteria = []

        # 1. Automatic Soft-Delete Filtering (WHERE deleted_at IS NULL)
        if not include_deleted:
            criteria.append(
                with_loader_criteria(
                    SoftDeleteMixin,
                    lambda cls: cls.deleted_at.is_(None),
                    include_aliases=True,
                )
            )

        # 2. Automatic Multi-Tenancy Isolation (WHERE company_id = :active_company_id)
        active_comp = get_active_company_id()
        if not ignore_tenant and active_comp is not None:
            criteria.append(
                with_loader_criteria(
                    TenantMixin,
                    lambda cls: cls.company_id == active_comp,
                    include_aliases=True,
                )
            )

        if criteria:
            execute_state.statement = execute_state.statement.options(*criteria)


@event.listens_for(AsyncSession.sync_session_class, "before_flush")
def _auto_populate_tenant_and_actors(session: Session, flush_context, instances):
    """Automatically populate company_id and audit actors from request contextvars on insert/update."""
    active_comp = get_active_company_id()
    curr_user = get_current_user_id()

    for obj in session.new:
        if isinstance(obj, TenantMixin) and getattr(obj, "company_id", None) is None and active_comp is not None:
            obj.company_id = active_comp
        if hasattr(obj, "created_by_id") and getattr(obj, "created_by_id", None) is None and curr_user is not None:
            obj.created_by_id = curr_user

    for obj in session.dirty:
        if hasattr(obj, "updated_by_id") and curr_user is not None:
            obj.updated_by_id = curr_user


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped async database session with automatic rollback."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
