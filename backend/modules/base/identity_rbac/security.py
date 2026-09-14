"""Password hashing using native bcrypt and JWT authentication token issuance."""

import uuid
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
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


# =========================================================================
# Two-Factor Authentication (RFC 6238 TOTP & Recovery Codes)
# =========================================================================

import hashlib
import pyotp


def create_mfa_token(
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    user_type: str = "human",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Issue a short-lived signed JWT challenge token for completing 2FA verification."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=5))

    to_encode: Dict[str, Any] = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "user_type": user_type,
        "token_purpose": "mfa_pending",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_mfa_token(mfa_token: str) -> Optional[Dict[str, Any]]:
    """Validate a 2FA challenge token and return its payload if valid."""
    try:
        payload = jwt.decode(mfa_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("token_purpose") != "mfa_pending":
            return None
        return payload
    except Exception:
        return None


def generate_totp_secret() -> str:
    """Generate a random Base32 encoded TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: str = "Sovereign") -> str:
    """Generate an otpauth:// URI suitable for authenticator QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code against the given secret allowing clock skew tolerance."""
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    cleaned_code = code.strip().replace(" ", "")
    return totp.verify(cleaned_code, valid_window=valid_window)


def generate_recovery_codes(count: int = 8) -> List[str]:
    """Generate a list of alphanumeric emergency recovery codes."""
    codes: List[str] = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        formatted = f"{raw[:4]}-{raw[4:]}"
        codes.append(formatted)
    return codes


def hash_recovery_code(code: str) -> str:
    """Compute a deterministic cryptographic SHA-256 hash for secure storage and comparison."""
    normalized = code.strip().upper().replace(" ", "").replace("-", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

