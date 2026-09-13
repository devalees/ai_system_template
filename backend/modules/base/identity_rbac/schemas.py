"""Pydantic request and response schemas for Identity & RBAC."""

import uuid
from typing import Optional, List, Literal
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
