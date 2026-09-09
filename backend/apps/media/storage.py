"""
Pluggable storage utilities and cryptographically signed download URL security services.
"""

import logging
from typing import Optional, Tuple

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Dedicated signer namespace for secure file download links
SIGNER_SALT = "apps.media.secure_download"


class SecureDocumentStorage(FileSystemStorage):
    """Custom FileSystemStorage maintaining media root directory structure."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
        kwargs.setdefault("base_url", getattr(settings, "MEDIA_URL", "/media/"))
        super().__init__(*args, **kwargs)


def generate_secure_download_token(document_id: str, user_id: str) -> str:
    """
    Generate a cryptographically signed, time-limited token for downloading private documents.
    """
    signer = TimestampSigner(salt=SIGNER_SALT)
    payload = f"{document_id}:{user_id}"
    return signer.sign(payload)


def verify_secure_download_token(token: str, max_age: int = 3600) -> Optional[Tuple[str, str]]:
    """
    Verify and unsign a secure download token. Returns (document_id, user_id) tuple if valid.
    """
    signer = TimestampSigner(salt=SIGNER_SALT)
    try:
        payload = signer.unsign(token, max_age=max_age)
        parts = payload.split(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    except SignatureExpired:
        logger.warning("Secure download token expired.")
    except BadSignature:
        logger.warning("Invalid secure download token signature.")
    except Exception as e:
        logger.error("Error verifying secure download token: %s", e)

    return None
