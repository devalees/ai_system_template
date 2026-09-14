"""Pydantic request and response schemas for Identity, Tenancy & Contextual RBAC."""

import uuid
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# =========================================================================
# User Schemas
# =========================================================================

class UserCreate(BaseModel):
    """Schema for public self-registration (contingent on tenant allow_registration)."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "sarah.connor@sovereign.local",
                "username": "sconnor",
                "password": "StrongPassword2026!",
                "full_name": "Sarah Connor",
                "user_type": "human",
                "preferred_language": "en",
                "company_id": "6f4539e5-a36c-488a-8c3b-2004a5884e33",
            }
        }
    )

    email: EmailStr = Field(..., description="Unique corporate email address used for notifications and login identification")
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric unique login username (strictly no spaces)")
    password: str = Field(..., min_length=6, description="Cleartext password (hashed with bcrypt upon ingestion)")
    full_name: str = Field(..., description="Full display name for the employee or autonomous AI agent")
    user_type: Literal["human", "ai_agent"] = Field("human", description="Actor classification: 'human' employee or first-class 'ai_agent'")
    preferred_language: str = Field("en", description="ISO 639-1 language code for localized emails and UI rendering (e.g. 'en', 'ar')")
    company_id: Optional[uuid.UUID] = Field(None, description="Target company UUID. Required if multiple tenants exist or if registration is gated")


class InternalUserCreate(BaseModel):
    """Schema for administrative user provisioning (bypasses allow_registration restrictions)."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "auditor@sovereign.local",
                "username": "qa_auditor",
                "password": "StrongPassword2026!",
                "full_name": "QA Auditor",
                "user_type": "human",
                "preferred_language": "en",
                "is_superuser": False,
                "group_ids": [
                    "110b59d6-00bc-4273-8014-9876de10909c"
                ],
            }
        }
    )

    email: EmailStr = Field(..., description="Unique corporate email address")
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric login username without whitespace")
    password: str = Field(..., min_length=6, description="Cleartext initial password")
    full_name: str = Field(..., description="Full display name")
    user_type: Literal["human", "ai_agent"] = Field("human", description="User actor classification")
    preferred_language: str = Field("en", description="Preferred locale code ('en', 'ar')")
    is_superuser: bool = Field(False, description="Global superuser flag (bypasses all RBAC capability checks)")
    group_ids: List[uuid.UUID] = Field(default_factory=list, description="List of RBAC Group UUIDs to immediately assign")
    company_id: Optional[uuid.UUID] = Field(None, description="Target company UUID (defaults to caller's company)")


class UserUpdate(BaseModel):
    """Schema for updating user account details, organizational department, or RBAC groups."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Sarah Connor, Lead Auditor",
                "preferred_language": "en",
                "is_active": True,
                "group_ids": [
                    "110b59d6-00bc-4273-8014-9876de10909c"
                ],
            }
        }
    )

    full_name: Optional[str] = Field(None, description="Updated display name")
    email: Optional[EmailStr] = Field(None, description="Updated email address")
    preferred_language: Optional[str] = Field(None, description="Updated ISO 639-1 language code")
    team_id: Optional[uuid.UUID] = Field(None, description="Assigned organizational department / team UUID")
    is_active: Optional[bool] = Field(None, description="Active status toggle (deactivated users cannot authenticate)")
    is_superuser: Optional[bool] = Field(None, description="Superuser privilege toggle (Superuser only)")
    group_ids: Optional[List[uuid.UUID]] = Field(None, description="Full replacement list of RBAC Group UUIDs assigned to this user")


class UserRead(BaseModel):
    """Public serialized representation of a user profile."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    full_name: str
    user_type: str
    is_superuser: bool
    is_primary_admin: bool = False
    email_verified: bool = False
    two_factor_enabled: bool = False
    preferred_language: str
    is_active: bool
    company_id: uuid.UUID


class UserDetailRead(BaseModel):
    """Detailed user representation including assigned groups and timestamps."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    full_name: str
    user_type: str
    is_superuser: bool
    is_primary_admin: bool = False
    email_verified: bool = False
    two_factor_enabled: bool = False
    preferred_language: str
    is_active: bool
    company_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    created_at: datetime
    groups: List[Dict[str, Any]] = Field(default_factory=list, description="Assigned RBAC groups with IDs and names")


# =========================================================================
# Authentication & Tokens
# =========================================================================

class LoginRequest(BaseModel):
    """Request payload for JWT authentication."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "identifier": "admin",
                "password": "AdminPassword2026!",
            }
        }
    )

    identifier: str = Field(..., description="Login username or registered corporate email address")
    password: str = Field(..., description="Cleartext password to verify against hashed bcrypt record")


class TokenResponse(BaseModel):
    """JWT bearer token response or multi-factor authentication challenge envelope."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "company_id": "6f4539e5-a36c-488a-8c3b-2004a5884e33",
                "user": {
                    "id": "1c63490d-575f-4a0f-8424-43768a70c99d",
                    "email": "admin@admin.com",
                    "username": "admin",
                    "full_name": "Super Administrator",
                    "user_type": "human",
                    "is_superuser": True,
                    "preferred_language": "en",
                    "is_active": True,
                    "company_id": "6f4539e5-a36c-488a-8c3b-2004a5884e33",
                    "email_verified": True,
                    "two_factor_enabled": False,
                },
                "mfa_required": False,
                "mfa_token": None,
            }
        }
    )

    access_token: Optional[str] = Field(None, description="Cryptographically signed JWT bearer token (present when authentication is complete)")
    token_type: Optional[str] = Field("bearer", description="OAuth2 authorization scheme header prefix")
    user: Optional[UserRead] = Field(None, description="Active user metadata snapshot")
    company_id: Optional[uuid.UUID] = Field(None, description="Primary tenant company UUID for context propagation")
    mfa_required: bool = Field(False, description="Flag indicating if secondary MFA/TOTP verification is required to complete authentication")
    mfa_token: Optional[str] = Field(None, description="Temporary challenge token required for calling POST /auth/2fa/verify")


class ChangePasswordRequest(BaseModel):
    """Payload for an authenticated user to update their account password."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "OldPassword2026!",
                "new_password": "NewSecurePassword2026!",
                "confirm_password": "NewSecurePassword2026!",
            }
        }
    )

    current_password: str = Field(..., min_length=6, description="Existing user password for authentication verification")
    new_password: str = Field(..., min_length=8, description="New secret password meeting complexity standards (minimum 8 characters)")
    confirm_password: str = Field(..., min_length=8, description="Confirmation matching the new password")


class AuthMessageResponse(BaseModel):
    """Standard response envelope for authentication operations."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password updated successfully.",
            }
        }
    )

    success: bool = Field(True, description="Indicates whether the operation succeeded")
    message: str = Field(..., description="Human-readable operation status summary")


class ForgotPasswordRequest(BaseModel):
    """Request payload to initiate an asynchronous password reset email."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "sarah.connor@sovereign.local",
            }
        }
    )

    email: EmailStr = Field(..., description="Registered user account email address")


class ResetPasswordRequest(BaseModel):
    """Request payload to complete a password reset using a single-use token."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "pr_9f8d7c6b5a4321_sample_token",
                "new_password": "NewSecurePassword2026!",
                "confirm_password": "NewSecurePassword2026!",
            }
        }
    )

    token: str = Field(..., description="Cryptographically signed, single-use password reset token")
    new_password: str = Field(..., min_length=8, description="New secret password meeting complexity standards (minimum 8 characters)")
    confirm_password: str = Field(..., min_length=8, description="Confirmation matching the new password")


class VerifyEmailRequest(BaseModel):
    """Request payload to verify account email address using a single-use token."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "em_1a2b3c4d5e6f_sample_token",
            }
        }
    )

    token: str = Field(..., description="Single-use email verification token")


# =========================================================================
# Two-Factor Authentication (2FA / TOTP)
# =========================================================================

class TwoFactorSetupResponse(BaseModel):
    """Response containing the TOTP secret and provisioning URI for authenticator apps."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "otpauth_url": "otpauth://totp/Sovereign:admin?secret=JBSWY3DPEHPK3PXP&issuer=Sovereign",
            }
        }
    )

    secret: str = Field(..., description="Base32 TOTP secret key")
    otpauth_url: str = Field(..., description="otpauth:// URI for QR code generation")


class TwoFactorEnableRequest(BaseModel):
    """Request payload to verify and activate 2FA."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "123456",
            }
        }
    )

    code: str = Field(..., min_length=6, max_length=12, description="6-digit TOTP code generated by authenticator app")


class TwoFactorEnableResponse(BaseModel):
    """Response confirming 2FA activation with single-use emergency recovery backup codes."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "recovery_codes": [
                    "A1B2-C3D4",
                    "E5F6-G7H8",
                ],
            }
        }
    )

    enabled: bool = Field(True, description="Indicates whether 2FA is successfully enabled")
    recovery_codes: List[str] = Field(..., description="Single-use emergency recovery backup codes (keep them safe)")


class TwoFactorDisableRequest(BaseModel):
    """Request payload to deactivate 2FA."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "password": "CurrentPassword2026!",
                "code": "123456",
            }
        }
    )

    password: str = Field(..., description="Current password for identity re-verification")
    code: str = Field(..., description="6-digit TOTP code or emergency recovery code")


class TwoFactorVerifyRequest(BaseModel):
    """Request payload to complete MFA challenge during login."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mfa_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "code": "123456",
            }
        }
    )

    mfa_token: str = Field(..., description="MFA pending challenge token returned during primary login")
    code: str = Field(..., description="6-digit TOTP code or emergency recovery code")


# =========================================================================
# RBAC Permissions & Capabilities
# =========================================================================

class PermissionCreate(BaseModel):
    """Schema for registering a granular model capability."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "module_name": "accounting",
                "resource": "invoice",
                "action": "read",
                "ownership_scope": "GLOBAL",
                "name": "Read Accounting Invoices",
                "code": "accounting.invoice.read",
            }
        }
    )

    module_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Parent system module namespace (e.g. 'accounting', 'crm', 'sales', 'identity_rbac')",
    )
    resource: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Target business entity or model name (e.g. 'invoice', 'lead', 'order', 'user')",
    )
    action: Literal["read", "create", "update", "delete", "manage", "approve", "export"] = Field(
        ...,
        description="Operational action type: 'read' (view), 'create' (insert), 'update' (edit), 'delete' (soft-delete), 'manage' (full admin), 'approve' (sign-off), or 'export' (bulk download)",
    )
    ownership_scope: Literal["GLOBAL", "TEAM", "OWN"] = Field(
        "GLOBAL",
        description="3-tier record ownership boundary: 'GLOBAL' (access any company record), 'TEAM' (restricted to user's team_id), 'OWN' (restricted to records created by user)",
    )
    name: str = Field(..., min_length=2, max_length=100, description="Human-readable title describing the capability")
    code: Optional[str] = Field(
        None,
        description="Unique canonical identifier. If omitted, auto-generated as '{module_name}.{resource}.{action}'",
    )


class PermissionUpdate(BaseModel):
    """Schema for modifying an existing permission's title or ownership scope."""
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="Updated display title")
    ownership_scope: Optional[Literal["GLOBAL", "TEAM", "OWN"]] = Field(None, description="Updated ownership scope constraint")


class PermissionRead(BaseModel):
    """Full serialized capability representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    module_name: str
    resource: str
    action: str
    ownership_scope: str
    created_at: datetime


# =========================================================================
# RBAC Groups & Roles
# =========================================================================

class UserSummary(BaseModel):
    """Compact summary of an assigned user."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str
    email: str
    user_type: str


class GroupCreate(BaseModel):
    """Schema for creating a new RBAC role/group with assigned permissions and users."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Financial Auditors",
                "description": "Read and review access to general ledger and journal entries",
                "permission_ids": [],
                "user_ids": [],
            }
        }
    )

    name: str = Field(..., min_length=2, max_length=50, description="Unique role/group title within the organization")
    description: Optional[str] = Field("", max_length=200, description="Operational scope and responsibility summary")
    permission_ids: List[uuid.UUID] = Field(default_factory=list, description="List of granular Permission UUIDs to link to this group")
    user_ids: List[uuid.UUID] = Field(default_factory=list, description="Optional list of User UUIDs to immediately assign to this group")


class GroupUpdate(BaseModel):
    """Schema for updating group metadata or reassigning permissions and users."""
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="Updated group title")
    description: Optional[str] = Field(None, max_length=200, description="Updated group description")
    permission_ids: Optional[List[uuid.UUID]] = Field(None, description="Full replacement list of linked Permission UUIDs")
    user_ids: Optional[List[uuid.UUID]] = Field(None, description="Full replacement list of assigned User UUIDs")


class GroupRead(BaseModel):
    """Basic serialized representation of an RBAC group."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = ""
    permissions_count: int = 0
    users_count: int = 0
    created_at: datetime


class GroupDetailRead(BaseModel):
    """Detailed group representation including full linked permissions and member users."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = ""
    permissions: List[PermissionRead] = Field(default_factory=list, description="List of linked permission objects")
    users: List[UserSummary] = Field(default_factory=list, description="List of users currently assigned to this group")
    created_at: datetime


# =========================================================================
# Company / Tenant Administration
# =========================================================================

class CompanyCreate(BaseModel):
    """Schema for creating a new tenant organization."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sovereign Enterprise System",
                "code": "SOV-MAIN",
                "allow_registration": False,
                "email_domain": "sovereign.local",
                "currency_id": "USD",
            }
        }
    )

    name: str = Field(..., min_length=2, max_length=100, description="Organization legal or trading name")
    code: str = Field(..., min_length=2, max_length=50, description="Unique tenant identification code (alphanumeric)")
    allow_registration: bool = Field(
        False,
        description="Whether public self-registration via /auth/register is permitted for this tenant. If False, users must be invited/created by an admin",
    )
    email_domain: Optional[str] = Field(None, max_length=100, description="Optional corporate email domain restriction")
    currency_id: Optional[str] = Field("USD", max_length=3, description="Base accounting currency ISO 4217 code")


class CompanyUpdate(BaseModel):
    """Schema for updating tenant configuration."""
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="Updated company name")
    code: Optional[str] = Field(None, min_length=2, max_length=50, description="Updated company code")
    allow_registration: Optional[bool] = Field(None, description="Toggle public registration policy (True = open, False = internal only)")
    email_domain: Optional[str] = Field(None, max_length=100, description="Updated corporate domain")
    currency_id: Optional[str] = Field(None, max_length=3, description="Updated base currency code")
    is_active: Optional[bool] = Field(None, description="Active status toggle (deactivating locks all users out)")


class CompanyRead(BaseModel):
    """Serialized representation of a tenant company."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    allow_registration: bool
    email_domain: Optional[str] = None
    currency_id: Optional[str] = "USD"
    is_active: bool
    created_at: datetime
