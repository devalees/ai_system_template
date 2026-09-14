"""Pydantic request and response schemas for Identity & RBAC."""

import uuid
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "sarah.connor@sovereign.local",
                "username": "sconnor",
                "password": "StrongPassword2026!",
                "full_name": "Sarah Connor",
                "user_type": "human",
                "preferred_language": "en",
                "company_id": "a0000000-0000-0000-0000-000000000001",
            }
        }
    )

    email: EmailStr = Field(..., description="Unique corporate email address")
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric unique login username")
    password: str = Field(..., min_length=6, description="Cleartext password (hashed using bcrypt upon ingestion)")
    full_name: str = Field(..., description="Display name for human employee or AI agent")
    user_type: Literal["human", "ai_agent"] = Field("human", description="Actor classification: human or ai_agent")
    preferred_language: str = Field("en", description="ISO 639-1 language code")
    company_id: Optional[uuid.UUID] = Field(None, description="Tenant company association (auto-injected if omitted)")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    full_name: str
    user_type: str
    is_superuser: bool
    preferred_language: str
    is_active: bool
    company_id: uuid.UUID


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "identifier": "sconnor",
                "password": "StrongPassword2026!",
            }
        }
    )

    identifier: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "user": {
                    "id": "u0000000-0000-0000-0000-000000000001",
                    "email": "sarah.connor@sovereign.local",
                    "username": "sconnor",
                    "full_name": "Sarah Connor",
                    "user_type": "human",
                    "is_superuser": False,
                    "preferred_language": "en",
                    "is_active": True,
                    "company_id": "a0000000-0000-0000-0000-000000000001",
                },
            }
        }
    )

    access_token: str
    token_type: str = "bearer"
    user: UserRead
    company_id: uuid.UUID


class GroupCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Financial Auditors",
                "description": "Read and review access to general ledger and journal entries",
                "permission_ids": ["p0000000-0000-0000-0000-000000000001"],
            }
        }
    )

    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = ""
    permission_ids: List[uuid.UUID] = Field(default_factory=list)


class PermissionCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "accounting.invoice.post",
                "name": "Post Invoices",
                "module_name": "accounting",
                "ownership_scope": "GLOBAL",
            }
        }
    )

    code: str
    name: str
    module_name: str
    ownership_scope: Literal["GLOBAL", "TEAM", "OWN"] = "GLOBAL"


class CompanyCreate(BaseModel):
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
    code: str = Field(..., min_length=2, max_length=50, description="Unique tenant identification code")
    allow_registration: bool = Field(
        False,
        description="Whether public self-registration via /auth/register is permitted for this tenant",
    )
    email_domain: Optional[str] = Field(None, max_length=100, description="Optional corporate email domain constraint")
    currency_id: Optional[str] = Field("USD", max_length=3, description="Base accounting currency ISO code")


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    allow_registration: Optional[bool] = Field(None, description="Toggle public registration permission")
    email_domain: Optional[str] = Field(None, max_length=100)
    currency_id: Optional[str] = Field(None, max_length=3)
    is_active: Optional[bool] = None


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    allow_registration: bool
    email_domain: Optional[str] = None
    currency_id: Optional[str] = "USD"
    is_active: bool
    created_at: datetime


class InternalUserCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "employee@sovereign.local",
                "username": "employee1",
                "password": "StrongPassword2026!",
                "full_name": "Internal Employee",
                "user_type": "human",
                "preferred_language": "en",
                "is_superuser": False,
                "group_ids": [],
            }
        }
    )

    email: EmailStr = Field(..., description="Unique corporate email address")
    username: str = Field(..., min_length=3, max_length=50, description="Alphanumeric unique login username")
    password: str = Field(..., min_length=6, description="Cleartext password (hashed using bcrypt)")
    full_name: str = Field(..., description="Full display name")
    user_type: Literal["human", "ai_agent"] = Field("human", description="User actor classification")
    preferred_language: str = Field("en", description="ISO 639-1 language code")
    is_superuser: bool = Field(False, description="Superuser access flag")
    group_ids: List[uuid.UUID] = Field(default_factory=list, description="Optional RBAC group IDs to link")
    company_id: Optional[uuid.UUID] = Field(None, description="Target company ID (defaults to active company)")

