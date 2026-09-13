"""Pydantic request and response schemas for Identity & RBAC."""

import uuid
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: str
    user_type: Literal["human", "ai_agent"] = "human"
    preferred_language: str = "en"
    company_id: Optional[uuid.UUID] = None


class UserRead(BaseModel):
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
    identifier: str = Field(..., description="Username or email address")
    password: str = Field(...)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
    company_id: uuid.UUID


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = ""
    permission_ids: List[uuid.UUID] = Field(default_factory=list)


class PermissionCreate(BaseModel):
    code: str
    name: str
    module_name: str
    ownership_scope: Literal["GLOBAL", "TEAM", "OWN"] = "GLOBAL"
