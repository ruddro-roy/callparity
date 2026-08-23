from __future__ import annotations

import hashlib
import hmac

import structlog

log = structlog.get_logger("webhook")


def normalize_signature(header: str | None) -> str:
    if not header:
        return ""
    value = header.strip()
    if value.lower().startswith("sha256="):
        return value.split("=", 1)[1].strip()
    return value


def verify_calle_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """HMAC-SHA256 over the raw body. Fail closed when secret is configured."""
    if not secret:
        return True
    provided = normalize_signature(signature_header)
    if not provided:
        log.warning("webhook_signature_missing")
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, provided)
    if not ok:
        log.warning("webhook_signature_mismatch")
    return ok
