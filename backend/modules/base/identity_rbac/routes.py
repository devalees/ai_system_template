"""API Routes for Identity, Authentication, Company Tenancy, and RBAC Management."""

import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.context import get_active_company_id
from modules.base.identity_rbac.models import (
    User,
    Group,
    Permission,
    UserGroupLink,
    GroupPermissionLink,
    Company,
)
from modules.base.identity_rbac.schemas import (
    UserCreate,
    UserRead,
    LoginRequest,
    TokenResponse,
    GroupCreate,
    PermissionCreate,
    CompanyCreate,
    CompanyUpdate,
    CompanyRead,
    InternalUserCreate,
)
from modules.base.identity_rbac.security import hash_password, verify_password, create_access_token
from modules.base.identity_rbac.dependencies import get_current_user, require_permission

router = APIRouter()


# =========================================================================
# Authentication & Public Registration
# =========================================================================

@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user account (human employee or AI agent) with strict tenant registration gating."""
    # 1. Verify email uniqueness
    existing_email = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    # 2. Verify username uniqueness
    existing_username = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if existing_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken.")

    # 3. Resolve and validate target company registration permission
    target_company_id = payload.company_id or get_active_company_id()
    if not target_company_id:
        # Check if there is an active tenant that explicitly permits public registration
        stmt_comp = select(Company).where(
            Company.allow_registration == True,
            Company.is_active == True,
            Company.deleted_at.is_(None),
        ).limit(1)
        company = (await db.execute(stmt_comp)).scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public self-registration is not available. Please specify a valid company_id or contact an administrator.",
            )
        target_company_id = company.id
    else:
        stmt_comp = select(Company).where(Company.id == target_company_id, Company.deleted_at.is_(None))
        company = (await db.execute(stmt_comp)).scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found.")
        if not company.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Target company is deactivated.")
        if not company.allow_registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-registration is disabled for this company. Please contact an administrator.",
            )

    new_user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        user_type=payload.user_type,
        preferred_language=payload.preferred_language,
        company_id=target_company_id,
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


# =========================================================================
# Internal User Management (Admin / Superuser)
# =========================================================================

@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["Identity Administration"])
async def create_internal_user(
    payload: InternalUserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Provision an internal user account within an organization (Admin or Superuser).
    
    Bypasses allow_registration restriction because this is an authenticated internal action.
    """
    if not current_user.is_superuser:
        target_company_id = current_user.company_id
    else:
        target_company_id = payload.company_id or current_user.company_id

    # Check email uniqueness
    existing_email = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    # Check username uniqueness
    existing_username = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if existing_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken.")

    # Verify company exists
    stmt_comp = select(Company).where(Company.id == target_company_id, Company.deleted_at.is_(None))
    company = (await db.execute(stmt_comp)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found.")

    new_user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        user_type=payload.user_type,
        preferred_language=payload.preferred_language,
        is_superuser=payload.is_superuser if current_user.is_superuser else False,
        company_id=target_company_id,
    )
    db.add(new_user)
    await db.flush()

    for gid in payload.group_ids:
        link = UserGroupLink(user_id=new_user.id, group_id=gid, company_id=target_company_id)
        db.add(link)

    await db.commit()
    await db.refresh(new_user)
    return new_user


# =========================================================================
# Company / Tenant Administration
# =========================================================================

@router.post("/companies", response_model=CompanyRead, status_code=status.HTTP_201_CREATED, tags=["Tenant Administration"])
async def create_company(
    payload: CompanyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Create a new tenant organization (Superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    existing = (await db.execute(select(Company).where(Company.code == payload.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Company with code '{payload.code}' already exists.")

    company = Company(
        name=payload.name,
        code=payload.code,
        allow_registration=payload.allow_registration,
        email_domain=payload.email_domain,
        currency_id=payload.currency_id or "USD",
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.get("/companies", response_model=List[CompanyRead], tags=["Tenant Administration"])
async def list_companies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Company]:
    """List tenant companies. Superusers view all tenants; regular users view their own tenant."""
    if current_user.is_superuser:
        stmt = select(Company).where(Company.deleted_at.is_(None)).order_by(Company.created_at.desc())
    else:
        stmt = select(Company).where(Company.id == current_user.company_id, Company.deleted_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/companies/{company_id}", response_model=CompanyRead, tags=["Tenant Administration"])
async def get_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Retrieve details for a specific tenant organization."""
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to tenant organization.")

    stmt = select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return company


@router.patch("/companies/{company_id}", response_model=CompanyRead, tags=["Tenant Administration"])
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Company:
    """Update tenant configuration, including toggling allow_registration (Superuser or Tenant Admin)."""
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to tenant organization.")

    stmt = select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)

    await db.commit()
    await db.refresh(company)
    return company


# =========================================================================
# RBAC Capabilities & Role Management
# =========================================================================

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
