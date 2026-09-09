"""
HMAC Signature verification for inbound SaaS webhooks (GitHub, Stripe, Slack, Custom).
"""

import hmac
import hashlib
from typing import Dict, Tuple


def verify_hmac_signature(
    provider: str,
    secret_token: str,
    payload_bytes: bytes,
    headers: Dict[str, str]
) -> Tuple[bool, str]:
    """
    Verify incoming HTTP webhook request HMAC signature according to provider rules.
    Returns tuple of (is_valid, error_message).
    """
    if not secret_token:
        return True, ""  # Unauthenticated webhook if secret token is empty

    # Normalize headers to lowercase for casing-insensitive lookup
    normalized_headers = {k.lower(): str(v) for k, v in headers.items()}

    if provider == "github":
        sig_header = normalized_headers.get("x-hub-signature-256", "")
        if not sig_header or not sig_header.startswith("sha256="):
            return False, "Missing or malformed X-Hub-Signature-256 header."
        expected_sig = sig_header.split("sha256=")[1].strip()
        computed = hmac.new(
            secret_token.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, computed):
            return False, "GitHub HMAC SHA-256 signature mismatch."
        return True, ""

    elif provider == "stripe":
        sig_header = normalized_headers.get("stripe-signature", "")
        if not sig_header:
            return False, "Missing Stripe-Signature header."
        parts = dict(pair.split("=", 1) for pair in sig_header.split(",") if "=" in pair)
        timestamp = parts.get("t")
        signature = parts.get("v1")
        if not timestamp or not signature:
            return False, "Malformed Stripe-Signature header."
        
        signed_payload = f"{timestamp}.{payload_bytes.decode('utf-8', errors='ignore')}"
        computed = hmac.new(
            secret_token.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, computed):
            return False, "Stripe HMAC signature mismatch."
        return True, ""

    elif provider == "slack":
        sig_header = normalized_headers.get("x-slack-signature", "")
        timestamp = normalized_headers.get("x-slack-request-timestamp", "")
        if not sig_header or not timestamp:
            return False, "Missing X-Slack-Signature or X-Slack-Request-Timestamp header."
        if not sig_header.startswith("v0="):
            return False, "Malformed X-Slack-Signature header."
        expected_sig = sig_header.split("v0=")[1].strip()
        
        sig_base_string = f"v0:{timestamp}:{payload_bytes.decode('utf-8', errors='ignore')}"
        computed = hmac.new(
            secret_token.encode("utf-8"),
            sig_base_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, computed):
            return False, "Slack HMAC signature mismatch."
        return True, ""

    elif provider == "custom":
        sig_header = normalized_headers.get("x-signature") or normalized_headers.get("x-hmac-signature", "")
        if not sig_header:
            return False, "Missing X-Signature or X-HMAC-Signature header."
        raw_sig = sig_header.replace("sha256=", "").strip()
        computed = hmac.new(
            secret_token.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(raw_sig, computed):
            return False, "Custom HMAC signature mismatch."
        return True, ""

    return False, f"Unsupported webhook provider '{provider}'."
