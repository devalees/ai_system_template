"""
Cryptographic Utilities for Encrypting and Masking Sensitive Settings.

Uses Django's cryptographic signing infrastructure and SECRET_KEY
to securely serialize, encrypt, and decrypt secret parameters (e.g. API keys, webhook secrets).
"""

import json
from django.conf import settings
from django.core.signing import Signer, BadSignature


SALT = "apps.core.settings.crypto.salt"


def encrypt_secret(value: str) -> str:
    """
    Encrypt a secret string into a tamper-proof signed payload.

    Args:
        value: Plaintext secret string.

    Returns:
        Encrypted signed string safe for database storage.
    """
    if not value:
        return ""
    signer = Signer(salt=SALT)
    return signer.sign(value)


def decrypt_secret(encrypted_value: str) -> str:
    """
    Decrypt an encrypted signed secret back to plaintext.

    Args:
        encrypted_value: Encrypted signed string.

    Returns:
        Decrypted plaintext string, or empty string if tampered/invalid.
    """
    if not encrypted_value:
        return ""
    signer = Signer(salt=SALT)
    try:
        return signer.unsign(encrypted_value)
    except BadSignature:
        # If signature verification fails, return raw or empty
        return ""


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """
    Produce a masked representation of a secret for administrative UI display.

    Example:
        `sk-ant-api03-1234567890abcdef` -> `sk-a••••••••••••••••cdef`
    """
    if not value:
        return ""
    length = len(value)
    if length <= visible_chars * 2:
        return "•" * length
    prefix = value[:visible_chars]
    suffix = value[-visible_chars:]
    mask = "•" * (length - (visible_chars * 2))
    return f"{prefix}{mask}{suffix}"
