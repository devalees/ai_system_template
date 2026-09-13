"""API Routes for Identity, Authentication, and RBAC Management."""

import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from modules.base.identity_rbac.models import User, Group, Permission, UserGroupLink, GroupPermissionLink
from modules.base.identity_rbac.schemas import (
    UserCreate,
    UserRead,
    LoginRequest,
    TokenResponse,
    GroupCreate,
    PermissionCreate,
)
from modules.base.identity_rbac.security import hash_password, verify_password, create_access_token
from modules.base.identity_rbac.dependencies import get_current_user, require_permission

router = APIRouter()


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user account (human employee or AI agent)."""
    # Check email uniqueness
    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    company_id = payload.company_id or get_active_company_id() or uuid.uuid4()

    new_user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        user_type=payload.user_type,
        preferred_language=payload.preferred_language,
        company_id=company_id,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username/email and password, returning JWT bearer token."""
    stmt = select(User).where(
        (User.email == payload.identifier) | (User.username == payload.identifier)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    token = create_access_token(user_id=user.id, company_id=user.company_id, user_type=user.user_type)

    user_data = UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        user_type=user.user_type,
        is_superuser=user.is_superuser,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        company_id=user.company_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_data,
        company_id=user.company_id,
    )


@router.get("/auth/me", response_model=UserRead, tags=["Authentication"])
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return currently authenticated profile metadata."""
    return current_user


@router.post("/permissions", status_code=status.HTTP_201_CREATED, tags=["RBAC Administration"])
async def create_permission(
    payload: PermissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a granular model capability (Superuser or Admin)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    perm = Permission(
        code=payload.code,
        name=payload.name,
        module_name=payload.module_name,
        ownership_scope=payload.ownership_scope,
        company_id=current_user.company_id,
    )
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return {"id": str(perm.id), "code": perm.code, "name": perm.name}


@router.post("/groups", status_code=status.HTTP_201_CREATED, tags=["RBAC Administration"])
async def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create an RBAC Group with linked permissions."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    group = Group(name=payload.name, description=payload.description, company_id=current_user.company_id)
    db.add(group)
    await db.flush()

    for perm_id in payload.permission_ids:
        link = GroupPermissionLink(group_id=group.id, permission_id=perm_id, company_id=current_user.company_id)
        db.add(link)

    await db.commit()
    return {"id": str(group.id), "name": group.name, "permissions_count": len(payload.permission_ids)}
