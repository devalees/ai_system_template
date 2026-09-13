"""FastAPI authentication and contextual RBAC authorization dependencies."""

import uuid
from typing import Callable, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from core.config import settings
from core.database import get_db
from core.context import set_current_user_id, set_active_company_id, set_actor_type
from core.exceptions import PermissionDeniedException
from modules.base.identity_rbac.models import User, Group, Permission, UserGroupLink, GroupPermissionLink

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/identity_rbac/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate bearer token and resolve active User instance."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        company_id_str: str = payload.get("company_id")
        if not user_id_str or not company_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
        user_id = uuid.UUID(user_id_str)
        company_id = uuid.UUID(company_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from DB
    stmt = select(User).where(User.id == user_id, User.company_id == company_id, User.is_active == True)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found or inactive.")

    # Populate request context
    set_current_user_id(user.id)
    set_active_company_id(user.company_id)
    set_actor_type(user.user_type)

    return user


def require_permission(permission_code: str) -> Callable:
    """Declarative dependency factory verifying actor holds specific permission code or is superuser."""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Superusers bypass all permission checks
        if current_user.is_superuser:
            return current_user

        # Query user permissions through group links
        stmt = (
            select(Permission.code)
            .join(GroupPermissionLink, GroupPermissionLink.permission_id == Permission.id)
            .join(UserGroupLink, UserGroupLink.group_id == GroupPermissionLink.group_id)
            .where(UserGroupLink.user_id == current_user.id, Permission.code == permission_code)
        )
        has_perm = (await db.execute(stmt)).scalar_one_or_none()

        if not has_perm:
            raise PermissionDeniedException(action=permission_code, resource=permission_code.split(".")[0])

        return current_user

    return permission_checker
