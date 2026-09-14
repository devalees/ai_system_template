"""Password hashing using native bcrypt and JWT authentication token issuance."""

import uuid
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from jose import jwt

from core.config import settings


def hash_password(password: str) -> str:
    """Hash plaintext password with native bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    user_type: str = "human",
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Issue a signed JWT access token containing subject, tenant, and actor type claims."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    to_encode: Dict[str, Any] = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "user_type": user_type,
        "actor_type": user_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# =========================================================================
# Single-Use Redis Token Lifecycle (Password Reset & Email Verification)
# =========================================================================

import json
import secrets
import redis.asyncio as aioredis


async def get_redis_client() -> aioredis.Redis:
    """Get asynchronous Redis connection."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def create_password_reset_token(
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    ttl_seconds: int = 900,  # 15 minutes
) -> str:
    """Generate a cryptographically secure, time-limited single-use password reset token stored in Redis."""
    token = f"pr_{secrets.token_urlsafe(32)}"
    key = f"sovereign:auth:pwd_reset:{token}"
    data = json.dumps({"user_id": str(user_id), "company_id": str(company_id)})
    r = await get_redis_client()
    try:
        await r.set(key, data, ex=ttl_seconds)
    finally:
        await r.aclose()
    return token


async def verify_and_consume_password_reset_token(token: str) -> Optional[Dict[str, str]]:
    """Verify and atomically consume (burn) a password reset token from Redis to prevent replay attacks."""
    key = f"sovereign:auth:pwd_reset:{token}"
    r = await get_redis_client()
    try:
        val = await r.getdel(key)
        if not val:
            return None
        return json.loads(val)
    finally:
        await r.aclose()


async def create_email_verification_token(
    user_id: uuid.UUID,
    ttl_seconds: int = 86400,  # 24 hours
) -> str:
    """Generate a single-use email verification token stored in Redis."""
    token = f"em_{secrets.token_urlsafe(32)}"
    key = f"sovereign:auth:email_verify:{token}"
    r = await get_redis_client()
    try:
        await r.set(key, str(user_id), ex=ttl_seconds)
    finally:
        await r.aclose()
    return token


async def verify_and_consume_email_token(token: str) -> Optional[uuid.UUID]:
    """Verify and atomically consume (burn) an email verification token from Redis."""
    key = f"sovereign:auth:email_verify:{token}"
    r = await get_redis_client()
    try:
        val = await r.getdel(key)
        if not val:
            return None
        return uuid.UUID(val)
    finally:
        await r.aclose()

