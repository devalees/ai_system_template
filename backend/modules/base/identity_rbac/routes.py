"""API Routes for Identity, Authentication, Company Tenancy, and RBAC Management."""

import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, and_
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
    InternalUserCreate,
    UserUpdate,
    UserRead,
    UserDetailRead,
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
    AuthMessageResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    TwoFactorSetupResponse,
    TwoFactorEnableRequest,
    TwoFactorEnableResponse,
    TwoFactorDisableRequest,
    TwoFactorVerifyRequest,
    PermissionCreate,
    PermissionUpdate,
    PermissionRead,
    GroupCreate,
    GroupUpdate,
    GroupRead,
    GroupDetailRead,
    UserSummary,
    CompanyCreate,
    CompanyUpdate,
    CompanyRead,
)
from modules.base.identity_rbac.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_password_reset_token,
    verify_and_consume_password_reset_token,
    create_email_verification_token,
    verify_and_consume_email_token,
    create_mfa_token,
    verify_mfa_token,
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code,
    generate_recovery_codes,
    hash_recovery_code,
)
from modules.base.identity_rbac.dependencies import get_current_user, require_permission
from modules.base.mail_gateway.service import MailService
from modules.base.mail_gateway.schemas import SendMailRequest

logger = logging.getLogger("sovereign.identity_rbac")
router = APIRouter()


# =========================================================================
# Authentication & Self-Registration
# =========================================================================

@router.post(
    "/auth/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register New Account",
)
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user account (human employee or first-class AI agent).
    
    Security & Access:
    - Public endpoint.
    - Strictly gated by target tenant's `allow_registration` policy.
    
    Validation Rules:
    - Rejects if `email` or `username` already exists (400 Bad Request).
    - If `company_id` is provided, verifies that company exists (404) and has `allow_registration == True` (403).
    - If `company_id` is omitted, attempts to bind to an active open-registration company; otherwise rejects (403).
    """
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
        email_verified=False,
        company_id=target_company_id,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Issue single-use email verification token and enqueue notification email
    try:
        verify_token = await create_email_verification_token(new_user.id)
        mail_req = SendMailRequest(
            to_email=new_user.email,
            recipient_name=new_user.full_name,
            subject="Welcome to Sovereign Platform - Verify Your Email",
            body_html=f"<p>Hello {new_user.full_name},</p><p>Welcome to Sovereign Platform! Please verify your email using the verification token below:</p><p><code>{verify_token}</code></p>",
            body_text=f"Hello {new_user.full_name},\n\nYour email verification token is: {verify_token}",
            async_send=True,
        )
        await MailService.enqueue_mail(db=db, req=mail_req, company_id=target_company_id, user_id=new_user.id)
    except Exception as exc:
        logger.warning(f"Could not dispatch registration verification email: {exc}")

    return new_user


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Login (Username & Password)",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username/email and password, returning a signed JWT bearer token.
    
    Security & Access:
    - Public endpoint.
    - Returns JWT token containing user identity and active tenant `company_id`.
    """
    stmt = (
        select(User)
        .where((User.email == payload.identifier) | (User.username == payload.identifier))
        .execution_options(ignore_tenant=True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    # Two-factor authentication challenge
    if user.two_factor_enabled:
        mfa_token = create_mfa_token(
            user_id=user.id,
            company_id=user.company_id,
            user_type=user.user_type,
        )
        return TokenResponse(
            mfa_required=True,
            mfa_token=mfa_token,
        )

    token = create_access_token(user_id=user.id, company_id=user.company_id, user_type=user.user_type)

    user_data = UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        user_type=user.user_type,
        is_superuser=user.is_superuser,
        is_primary_admin=user.is_primary_admin,
        email_verified=user.email_verified,
        two_factor_enabled=user.two_factor_enabled,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        company_id=user.company_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_data,
        company_id=user.company_id,
        mfa_required=False,
    )


@router.get(
    "/auth/me",
    response_model=UserDetailRead,
    tags=["Authentication"],
    summary="Get Current User Profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserDetailRead:
    """Return currently authenticated profile metadata including assigned RBAC groups."""
    stmt_groups = (
        select(Group.id, Group.name)
        .join(UserGroupLink, UserGroupLink.group_id == Group.id)
        .where(UserGroupLink.user_id == current_user.id, Group.deleted_at.is_(None))
    )
    group_rows = (await db.execute(stmt_groups)).all()
    group_list = [{"id": r[0], "name": r[1]} for r in group_rows]

    return UserDetailRead(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        user_type=current_user.user_type,
        is_superuser=current_user.is_superuser,
        is_primary_admin=current_user.is_primary_admin,
        email_verified=current_user.email_verified,
        two_factor_enabled=current_user.two_factor_enabled,
        preferred_language=current_user.preferred_language,
        is_active=current_user.is_active,
        company_id=current_user.company_id,
        team_id=current_user.team_id,
        created_at=current_user.created_at,
        groups=group_list,
    )


@router.post(
    "/auth/change-password",
    response_model=AuthMessageResponse,
    tags=["Authentication"],
    summary="Change Password (In-App Settings)",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthMessageResponse:
    """Change credentials for the currently authenticated session with cryptographic verification.
    
    Security & Access:
    - Requires active authenticated Bearer session.
    - Validates `current_password` against bcrypt hash.
    - Enforces matching `new_password` and `confirm_password`.
    - Prevents redundant password churn (`new_password != current_password`).
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password verification failed.",
        )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation password do not match.",
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be identical to the current password.",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return AuthMessageResponse(success=True, message="Password successfully changed.")


@router.post(
    "/auth/forgot-password",
    response_model=AuthMessageResponse,
    tags=["Authentication"],
    summary="Forgot Password (Step 1: Request Reset Email)",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthMessageResponse:
    """Initiate a single-use password reset token dispatch via Mail Gateway.
    
    Security & Access:
    - Public endpoint.
    - Constant response structure to defend against email enumeration attacks.
    - Issues a 15-minute expiring token in Redis.
    """
    stmt = (
        select(User)
        .where(User.email == payload.email, User.deleted_at.is_(None))
        .execution_options(ignore_tenant=True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user and user.is_active:
        token = await create_password_reset_token(user.id, user.company_id, ttl_seconds=900)
        try:
            mail_req = SendMailRequest(
                to_email=user.email,
                recipient_name=user.full_name,
                subject="Sovereign Platform - Password Reset Request",
                body_html=(
                    f"<p>Hello {user.full_name},</p>"
                    f"<p>A password reset was requested for your Sovereign account. "
                    f"Use the single-use token below within 15 minutes to reset your password:</p>"
                    f"<p style='font-family: monospace; font-size: 16px; font-weight: bold;'>{token}</p>"
                    f"<p>If you did not make this request, please disregard this email.</p>"
                ),
                body_text=f"Hello {user.full_name},\n\nYour password reset token is:\n{token}\n\nThis token will expire in 15 minutes.",
                async_send=True,
            )
            await MailService.enqueue_mail(db=db, req=mail_req, company_id=user.company_id, user_id=user.id)
        except Exception as exc:
            logger.warning(f"Could not enqueue password reset email: {exc}")

    return AuthMessageResponse(
        success=True,
        message="If the email address is registered, a password reset link has been dispatched.",
    )


@router.post(
    "/auth/reset-password",
    response_model=AuthMessageResponse,
    tags=["Authentication"],
    summary="Forgot Password (Step 2: Confirm via Token)",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthMessageResponse:
    """Complete credential reset using an unconsumed, non-expired Redis token.
    
    Security & Access:
    - Public endpoint.
    - Atomic token consumption (GETDEL) prevents token replay attacks.
    - Enforces new password matching and complexity standards.
    """
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation password do not match.",
        )

    token_data = await verify_and_consume_password_reset_token(payload.token)
    if not token_data or "user_id" not in token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    target_user_id = uuid.UUID(token_data["user_id"])
    stmt = (
        select(User)
        .where(User.id == target_user_id, User.deleted_at.is_(None))
        .execution_options(ignore_tenant=True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be identical to the current password.",
        )

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return AuthMessageResponse(
        success=True,
        message="Password has been successfully reset. You may now log in with your new credentials.",
    )


@router.post(
    "/auth/verify-email",
    response_model=AuthMessageResponse,
    tags=["Authentication"],
    summary="Verify Email (Registration Confirmation)",
)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthMessageResponse:
    """Verify an account email address using an unconsumed verification token."""
    user_id = await verify_and_consume_email_token(payload.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification token.",
        )

    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .execution_options(ignore_tenant=True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    user.email_verified = True
    await db.commit()
    return AuthMessageResponse(
        success=True,
        message="Email address has been successfully verified.",
    )


@router.post(
    "/auth/2fa/setup",
    response_model=TwoFactorSetupResponse,
    tags=["Authentication"],
    summary="2FA: Setup (Generate Secret & QR)",
)
async def setup_two_factor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TwoFactorSetupResponse:
    """Generate a TOTP secret and provisioning URI for the authenticated user.
    
    Security & Access:
    - Requires authenticated session.
    - Prevents re-running setup if 2FA is already active.
    - Staged secret is stored pending confirmation via /auth/2fa/enable.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already active for this account. Disable it first to reconfigure.",
        )

    secret = generate_totp_secret()
    current_user.two_factor_secret = secret
    await db.commit()

    otpauth_url = get_totp_uri(secret=secret, username=current_user.username, issuer="Sovereign")
    return TwoFactorSetupResponse(secret=secret, otpauth_url=otpauth_url)


@router.post(
    "/auth/2fa/enable",
    response_model=TwoFactorEnableResponse,
    tags=["Authentication"],
    summary="2FA: Enable (Verify Code & Get Backup Codes)",
)
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TwoFactorEnableResponse:
    """Verify an initial TOTP code, activate 2FA, and return emergency recovery backup codes.
    
    Security & Access:
    - Requires authenticated session.
    - Confirms user possesses authenticator configured with the staged secret.
    - Generates 8 single-use emergency recovery codes, stored as cryptographic SHA-256 hashes.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled.",
        )

    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication setup has not been initiated. Call /auth/2fa/setup first.",
        )

    if not verify_totp_code(current_user.two_factor_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid two-factor authentication code. Verification failed.",
        )

    recovery_codes = generate_recovery_codes(count=8)
    hashed_codes = [hash_recovery_code(code) for code in recovery_codes]

    current_user.two_factor_recovery_codes = hashed_codes
    current_user.two_factor_enabled = True
    await db.commit()

    return TwoFactorEnableResponse(
        enabled=True,
        recovery_codes=recovery_codes,
    )


@router.post(
    "/auth/2fa/disable",
    response_model=AuthMessageResponse,
    tags=["Authentication"],
    summary="2FA: Disable (Password & Code Re-check)",
)
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthMessageResponse:
    """Deactivate Two-Factor Authentication with password re-verification and code validation.
    
    Security & Access:
    - Requires active authenticated Bearer session.
    - Requires current password verification to prevent session hijacking.
    - Requires valid TOTP code or active emergency recovery code.
    - Completely wipes 2FA secret and stored recovery codes.
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not enabled on this account.",
        )

    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password verification failed.",
        )

    code_valid = False
    if current_user.two_factor_secret and verify_totp_code(current_user.two_factor_secret, payload.code):
        code_valid = True
    else:
        req_hash = hash_recovery_code(payload.code)
        if current_user.two_factor_recovery_codes and req_hash in current_user.two_factor_recovery_codes:
            code_valid = True

    if not code_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authentication code or emergency recovery code.",
        )

    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.two_factor_recovery_codes = None
    await db.commit()

    return AuthMessageResponse(
        success=True,
        message="Two-factor authentication has been successfully disabled.",
    )


@router.post(
    "/auth/2fa/verify",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="2FA: Login Challenge Verification",
)
async def verify_two_factor_login(
    payload: TwoFactorVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Validate secondary MFA token with TOTP code or emergency recovery code to issue access token.
    
    Security & Access:
    - Public endpoint.
    - Consumes temporary MFA challenge token.
    - Accepts standard 6-digit TOTP code or single-use recovery code.
    - If recovery code is used, it is atomically burned from the user's stored recovery codes.
    """
    mfa_payload = verify_mfa_token(payload.mfa_token)
    if not mfa_payload or "sub" not in mfa_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA session token. Please initiate login again.",
        )

    user_id = uuid.UUID(mfa_payload["sub"])
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .execution_options(ignore_tenant=True)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    if not user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is not active on this account.",
        )

    code_valid = False
    used_recovery_code_hash = None

    if user.two_factor_secret and verify_totp_code(user.two_factor_secret, payload.code):
        code_valid = True
    else:
        req_hash = hash_recovery_code(payload.code)
        if user.two_factor_recovery_codes and req_hash in user.two_factor_recovery_codes:
            code_valid = True
            used_recovery_code_hash = req_hash

    if not code_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid two-factor authentication code or recovery code.",
        )

    # Burn single-use recovery code if used
    if used_recovery_code_hash:
        user.two_factor_recovery_codes = [
            h for h in (user.two_factor_recovery_codes or []) if h != used_recovery_code_hash
        ]
        await db.commit()

    token = create_access_token(user_id=user.id, company_id=user.company_id, user_type=user.user_type)

    user_data = UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        user_type=user.user_type,
        is_superuser=user.is_superuser,
        is_primary_admin=user.is_primary_admin,
        email_verified=user.email_verified,
        two_factor_enabled=user.two_factor_enabled,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        company_id=user.company_id,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_data,
        company_id=user.company_id,
        mfa_required=False,
    )


# =========================================================================
# User Management (CRUD & Administration)
# =========================================================================

@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Identity Administration"],
)
async def create_user(
    payload: InternalUserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Provision an internal user account within an organization (Admin or Superuser).
    
    Security & Access:
    - Requires authenticated Administrator or Superuser.
    - Bypasses public `allow_registration` restrictions.
    """
    target_company_id = payload.company_id if (current_user.is_superuser and payload.company_id) else current_user.company_id

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

    # Only Primary Admin can grant is_superuser
    if payload.is_superuser:
        if not current_user.is_primary_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the primary system administrator can provision superuser accounts.",
            )

    new_user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        user_type=payload.user_type,
        preferred_language=payload.preferred_language,
        is_superuser=payload.is_superuser if current_user.is_primary_admin else False,
        is_primary_admin=False,
        email_verified=True,
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


@router.get(
    "/users",
    response_model=List[UserRead],
    tags=["Identity Administration"],
)
async def list_users(
    user_type: Optional[str] = Query(None, description="Filter by actor type ('human' or 'ai_agent')"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by username, full name, or email"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[User]:
    """List users within the caller's active company with optional search and filters."""
    query = select(User).where(User.company_id == current_user.company_id, User.deleted_at.is_(None))

    if user_type:
        query = query.where(User.user_type == user_type)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        term = f"%{search}%"
        query = query.where(or_(User.username.ilike(term), User.full_name.ilike(term), User.email.ilike(term)))

    query = query.order_by(User.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get(
    "/users/{user_id}",
    response_model=UserDetailRead,
    tags=["Identity Administration"],
)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserDetailRead:
    """Retrieve detailed user profile including assigned RBAC groups."""
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    if not current_user.is_superuser:
        stmt = stmt.where(User.company_id == current_user.company_id)

    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    stmt_groups = (
        select(Group.id, Group.name)
        .join(UserGroupLink, UserGroupLink.group_id == Group.id)
        .where(UserGroupLink.user_id == user.id, Group.deleted_at.is_(None))
    )
    group_rows = (await db.execute(stmt_groups)).all()
    group_list = [{"id": r[0], "name": r[1]} for r in group_rows]

    return UserDetailRead(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        user_type=user.user_type,
        is_superuser=user.is_superuser,
        is_primary_admin=user.is_primary_admin,
        email_verified=user.email_verified,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        company_id=user.company_id,
        team_id=user.team_id,
        created_at=user.created_at,
        groups=group_list,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserDetailRead,
    tags=["Identity Administration"],
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserDetailRead:
    """Update user account attributes, active toggle, and RBAC group assignments."""
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    if not current_user.is_superuser:
        stmt = stmt.where(User.company_id == current_user.company_id)

    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    # 1. Primary Admin Immunity & Protection
    if user.is_primary_admin:
        if current_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The primary system administrator account cannot be modified by other users.",
            )
        if payload.is_superuser is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The primary system administrator cannot revoke their own superuser status.",
            )
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The primary system administrator cannot deactivate their own root account.",
            )

    # 2. Superuser Peer Protection (Secondary Superusers)
    elif user.is_superuser:
        if current_user.id != user.id and not current_user.is_primary_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the primary system administrator can modify another superuser account.",
            )

    # Update basic fields
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.preferred_language is not None:
        user.preferred_language = payload.preferred_language
    if payload.team_id is not None:
        user.team_id = payload.team_id
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.email is not None:
        # Verify email uniqueness
        existing = (await db.execute(select(User).where(User.email == payload.email, User.id != user_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already in use.")
        user.email = payload.email

    if payload.is_superuser is not None and payload.is_superuser != user.is_superuser:
        if not current_user.is_primary_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the primary system administrator can grant or revoke superuser privileges.",
            )
        user.is_superuser = payload.is_superuser

    # Re-sync group memberships if specified
    if payload.group_ids is not None:
        # Delete existing links
        existing_links = (await db.execute(select(UserGroupLink).where(UserGroupLink.user_id == user.id))).scalars().all()
        for link in existing_links:
            await db.delete(link)
        await db.flush()
        # Add new links
        for gid in payload.group_ids:
            new_link = UserGroupLink(user_id=user.id, group_id=gid, company_id=user.company_id)
            db.add(new_link)

    await db.commit()
    await db.refresh(user)

    # Return updated detail
    stmt_groups = (
        select(Group.id, Group.name)
        .join(UserGroupLink, UserGroupLink.group_id == Group.id)
        .where(UserGroupLink.user_id == user.id, Group.deleted_at.is_(None))
    )
    group_rows = (await db.execute(stmt_groups)).all()
    group_list = [{"id": r[0], "name": r[1]} for r in group_rows]

    return UserDetailRead(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        user_type=user.user_type,
        is_superuser=user.is_superuser,
        is_primary_admin=user.is_primary_admin,
        email_verified=user.email_verified,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
        company_id=user.company_id,
        team_id=user.team_id,
        created_at=user.created_at,
        groups=group_list,
    )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    tags=["Identity Administration"],
)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Soft-delete a user account.
    
    Security Guards:
    - Users cannot delete their own active authenticated account.
    - Primary system administrator is permanent and cannot be deleted by anyone.
    - Secondary superusers can only be deleted by the primary system administrator.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own active session account.")

    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    if not current_user.is_superuser:
        stmt = stmt.where(User.company_id == current_user.company_id)

    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    # Primary Admin Immunity
    if user.is_primary_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The primary system administrator account is permanent and cannot be deleted.",
        )

    # Superuser Deletion Guard
    if user.is_superuser and not current_user.is_primary_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the primary system administrator can delete a superuser account.",
        )

    user.soft_delete(user_id=current_user.id)
    await db.commit()
    return {"status": "deleted", "id": str(user_id), "message": "User soft-deleted successfully."}


# =========================================================================
# Company / Tenant Administration
# =========================================================================

@router.post(
    "/companies",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Tenant Administration"],
)
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


@router.get(
    "/companies",
    response_model=List[CompanyRead],
    tags=["Tenant Administration"],
)
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


@router.get(
    "/companies/{company_id}",
    response_model=CompanyRead,
    tags=["Tenant Administration"],
)
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


@router.patch(
    "/companies/{company_id}",
    response_model=CompanyRead,
    tags=["Tenant Administration"],
)
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


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_200_OK,
    tags=["Tenant Administration"],
)
async def delete_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Soft-delete an organization tenant (Superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    stmt = select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    company.soft_delete(user_id=current_user.id)
    await db.commit()
    return {"status": "deleted", "id": str(company_id), "message": f"Company '{company.name}' soft-deleted successfully."}


# =========================================================================
# RBAC Permissions (Capabilities)
# =========================================================================

@router.post(
    "/permissions",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["RBAC Administration"],
)
async def create_permission(
    payload: PermissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Permission:
    """Create a granular model capability (Superuser only).
    
    Canonical Code Generation:
    - If `code` is omitted, auto-generates: `{module_name}.{resource}.{action}`.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    # Canonical code generation
    canonical_code = payload.code or f"{payload.module_name}.{payload.resource}.{payload.action}".lower()

    existing = (await db.execute(select(Permission).where(Permission.code == canonical_code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Permission with code '{canonical_code}' already exists.")

    perm = Permission(
        code=canonical_code,
        name=payload.name,
        module_name=payload.module_name.lower(),
        resource=payload.resource.lower(),
        action=payload.action.lower(),
        ownership_scope=payload.ownership_scope,
        company_id=current_user.company_id,
    )
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


@router.get(
    "/permissions",
    response_model=List[PermissionRead],
    tags=["RBAC Administration"],
)
async def list_permissions(
    module_name: Optional[str] = Query(None, description="Filter by system module namespace"),
    resource: Optional[str] = Query(None, description="Filter by business model/entity name"),
    action: Optional[str] = Query(None, description="Filter by operation action type"),
    ownership_scope: Optional[str] = Query(None, description="Filter by ownership boundary ('GLOBAL', 'TEAM', 'OWN')"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Permission]:
    """List registered capabilities with optional category and scope filters."""
    query = select(Permission).where(Permission.deleted_at.is_(None))

    if module_name:
        query = query.where(Permission.module_name == module_name.lower())
    if resource:
        query = query.where(Permission.resource == resource.lower())
    if action:
        query = query.where(Permission.action == action.lower())
    if ownership_scope:
        query = query.where(Permission.ownership_scope == ownership_scope)

    query = query.order_by(Permission.module_name.asc(), Permission.resource.asc(), Permission.action.asc())
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get(
    "/permissions/{permission_id}",
    response_model=PermissionRead,
    tags=["RBAC Administration"],
)
async def get_permission(
    permission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Permission:
    """Retrieve details of a specific permission capability."""
    stmt = select(Permission).where(Permission.id == permission_id, Permission.deleted_at.is_(None))
    perm = (await db.execute(stmt)).scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")
    return perm


@router.patch(
    "/permissions/{permission_id}",
    response_model=PermissionRead,
    tags=["RBAC Administration"],
)
async def update_permission(
    permission_id: uuid.UUID,
    payload: PermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Permission:
    """Update permission title or ownership scope (Superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    stmt = select(Permission).where(Permission.id == permission_id, Permission.deleted_at.is_(None))
    perm = (await db.execute(stmt)).scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")

    if payload.name is not None:
        perm.name = payload.name
    if payload.ownership_scope is not None:
        perm.ownership_scope = payload.ownership_scope

    await db.commit()
    await db.refresh(perm)
    return perm


@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_200_OK,
    tags=["RBAC Administration"],
)
async def delete_permission(
    permission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Soft-delete an RBAC permission capability (Superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required.")

    stmt = select(Permission).where(Permission.id == permission_id, Permission.deleted_at.is_(None))
    perm = (await db.execute(stmt)).scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")

    perm.soft_delete(user_id=current_user.id)
    await db.commit()
    return {"status": "deleted", "id": str(permission_id), "message": f"Permission '{perm.code}' soft-deleted successfully."}


# =========================================================================
# RBAC Groups & Roles
# =========================================================================

@router.post(
    "/groups",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED,
    tags=["RBAC Administration"],
)
async def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupRead:
    """Create an RBAC Group/Role with linked permissions and users (Superuser or Tenant Admin)."""
    group = Group(name=payload.name, description=payload.description, company_id=current_user.company_id)
    db.add(group)
    await db.flush()

    for perm_id in payload.permission_ids:
        link = GroupPermissionLink(group_id=group.id, permission_id=perm_id, company_id=current_user.company_id)
        db.add(link)

    for uid in payload.user_ids:
        u_link = UserGroupLink(user_id=uid, group_id=group.id, company_id=current_user.company_id)
        db.add(u_link)

    await db.commit()
    await db.refresh(group)
    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        permissions_count=len(payload.permission_ids),
        users_count=len(payload.user_ids),
        created_at=group.created_at,
    )


@router.get(
    "/groups",
    response_model=List[GroupRead],
    tags=["RBAC Administration"],
)
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GroupRead]:
    """List RBAC groups for active tenant with count of assigned permissions and users."""
    stmt = select(Group).where(Group.company_id == current_user.company_id, Group.deleted_at.is_(None)).order_by(Group.name.asc())
    groups = (await db.execute(stmt)).scalars().all()

    result = []
    for g in groups:
        p_count = len((await db.execute(
            select(GroupPermissionLink.id).where(GroupPermissionLink.group_id == g.id)
        )).scalars().all())
        u_count = len((await db.execute(
            select(UserGroupLink.id).where(UserGroupLink.group_id == g.id)
        )).scalars().all())
        result.append(
            GroupRead(
                id=g.id,
                name=g.name,
                description=g.description,
                permissions_count=p_count,
                users_count=u_count,
                created_at=g.created_at,
            )
        )
    return result


@router.get(
    "/groups/{group_id}",
    response_model=GroupDetailRead,
    tags=["RBAC Administration"],
)
async def get_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupDetailRead:
    """Retrieve detailed RBAC group with full list of assigned permissions and member users."""
    stmt = select(Group).where(
        Group.id == group_id,
        Group.company_id == current_user.company_id,
        Group.deleted_at.is_(None),
    )
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    stmt_perms = (
        select(Permission)
        .join(GroupPermissionLink, GroupPermissionLink.permission_id == Permission.id)
        .where(GroupPermissionLink.group_id == group.id, Permission.deleted_at.is_(None))
    )
    perms = (await db.execute(stmt_perms)).scalars().all()

    stmt_users = (
        select(User)
        .join(UserGroupLink, UserGroupLink.user_id == User.id)
        .where(UserGroupLink.group_id == group.id, User.deleted_at.is_(None))
    )
    users = (await db.execute(stmt_users)).scalars().all()

    return GroupDetailRead(
        id=group.id,
        name=group.name,
        description=group.description,
        permissions=[PermissionRead.model_validate(p) for p in perms],
        users=[UserSummary.model_validate(u) for u in users],
        created_at=group.created_at,
    )


@router.patch(
    "/groups/{group_id}",
    response_model=GroupDetailRead,
    tags=["RBAC Administration"],
)
async def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupDetailRead:
    """Update group title, description, or reassign permission links and user memberships."""
    stmt = select(Group).where(
        Group.id == group_id,
        Group.company_id == current_user.company_id,
        Group.deleted_at.is_(None),
    )
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description

    # Re-sync permission links if specified
    if payload.permission_ids is not None:
        existing_links = (await db.execute(select(GroupPermissionLink).where(GroupPermissionLink.group_id == group.id))).scalars().all()
        for link in existing_links:
            await db.delete(link)
        await db.flush()

        for pid in payload.permission_ids:
            new_link = GroupPermissionLink(group_id=group.id, permission_id=pid, company_id=group.company_id)
            db.add(new_link)

    # Re-sync user memberships if specified
    if payload.user_ids is not None:
        existing_u_links = (await db.execute(select(UserGroupLink).where(UserGroupLink.group_id == group.id))).scalars().all()
        for u_link in existing_u_links:
            await db.delete(u_link)
        await db.flush()

        for uid in payload.user_ids:
            new_u_link = UserGroupLink(user_id=uid, group_id=group.id, company_id=group.company_id)
            db.add(new_u_link)

    await db.commit()
    await db.refresh(group)

    stmt_perms = (
        select(Permission)
        .join(GroupPermissionLink, GroupPermissionLink.permission_id == Permission.id)
        .where(GroupPermissionLink.group_id == group.id, Permission.deleted_at.is_(None))
    )
    perms = (await db.execute(stmt_perms)).scalars().all()

    stmt_users = (
        select(User)
        .join(UserGroupLink, UserGroupLink.user_id == User.id)
        .where(UserGroupLink.group_id == group.id, User.deleted_at.is_(None))
    )
    users = (await db.execute(stmt_users)).scalars().all()

    return GroupDetailRead(
        id=group.id,
        name=group.name,
        description=group.description,
        permissions=[PermissionRead.model_validate(p) for p in perms],
        users=[UserSummary.model_validate(u) for u in users],
        created_at=group.created_at,
    )


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_200_OK,
    tags=["RBAC Administration"],
)
async def delete_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Soft-delete an RBAC group."""
    stmt = select(Group).where(
        Group.id == group_id,
        Group.company_id == current_user.company_id,
        Group.deleted_at.is_(None),
    )
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    group.soft_delete(user_id=current_user.id)
    await db.commit()
    return {"status": "deleted", "id": str(group_id), "message": f"Group '{group.name}' soft-deleted successfully."}


@router.get(
    "/groups/{group_id}/users",
    response_model=List[UserSummary],
    tags=["RBAC Administration"],
)
async def list_group_users(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserSummary]:
    """List all active member users assigned to an RBAC group."""
    stmt_group = select(Group).where(Group.id == group_id, Group.company_id == current_user.company_id, Group.deleted_at.is_(None))
    if not (await db.execute(stmt_group)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    stmt_users = (
        select(User)
        .join(UserGroupLink, UserGroupLink.user_id == User.id)
        .where(UserGroupLink.group_id == group_id, User.deleted_at.is_(None))
    )
    users = (await db.execute(stmt_users)).scalars().all()
    return [UserSummary.model_validate(u) for u in users]


@router.post(
    "/groups/{group_id}/users/{user_id}",
    status_code=status.HTTP_200_OK,
    tags=["RBAC Administration"],
)
async def add_user_to_group(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Directly assign an existing user to an RBAC group."""
    stmt_group = select(Group).where(Group.id == group_id, Group.company_id == current_user.company_id, Group.deleted_at.is_(None))
    group = (await db.execute(stmt_group)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    stmt_user = select(User).where(User.id == user_id, User.company_id == current_user.company_id, User.deleted_at.is_(None))
    user = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    existing = (await db.execute(
        select(UserGroupLink).where(UserGroupLink.group_id == group_id, UserGroupLink.user_id == user_id)
    )).scalar_one_or_none()
    if not existing:
        link = UserGroupLink(user_id=user_id, group_id=group_id, company_id=current_user.company_id)
        db.add(link)
        await db.commit()

    return {"status": "success", "message": f"User '{user.username}' added to group '{group.name}'."}


@router.delete(
    "/groups/{group_id}/users/{user_id}",
    status_code=status.HTTP_200_OK,
    tags=["RBAC Administration"],
)
async def remove_user_from_group(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Directly remove a user from an RBAC group."""
    stmt_group = select(Group).where(Group.id == group_id, Group.company_id == current_user.company_id, Group.deleted_at.is_(None))
    group = (await db.execute(stmt_group)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    existing = (await db.execute(
        select(UserGroupLink).where(UserGroupLink.group_id == group_id, UserGroupLink.user_id == user_id)
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()

    return {"status": "success", "message": f"User removed from group '{group.name}'."}

