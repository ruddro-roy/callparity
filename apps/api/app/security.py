from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException

from app.config import get_settings


def _bearer(authorization: str | None, x_operator_token: str | None) -> str:
    if authorization and authorization.strip().lower().startswith("bearer "):
        return authorization.strip()[7:].strip()
    return (x_operator_token or "").strip()


def actor_fingerprint(token: str) -> str:
    """Stable, non-reversible id for the credential that acted. No raw token stored."""
    return "op_" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def require_operator(
    authorization: str | None = Header(default=None),
    x_operator_token: str | None = Header(default=None, alias="X-Operator-Token"),
) -> str:
    """Gate a mutating route on a configured operator token. Returns the actor id.

    OPERATOR_TOKEN may hold several comma-separated tokens so a rotation can
    overlap the old and new credential without a hard cutover; each token
    keeps its own fingerprint, so audit rows and rate buckets tell the two
    apart. Fails closed: no configured token denies everyone, and a missing
    or wrong request token is 401. Every candidate is compared with
    hmac.compare_digest and every candidate is always compared. The token
    itself never enters a log line or the audit trail, only its fingerprint.
    """
    configured = get_settings().operator_tokens
    provided = _bearer(authorization, x_operator_token)
    # Compare on bytes so a non-ASCII header value fails closed with 401 rather
    # than raising inside compare_digest.
    provided_bytes = provided.encode("utf-8")
    matched = False
    for candidate in configured:
        matched |= hmac.compare_digest(candidate.encode("utf-8"), provided_bytes)
    if not configured or not provided or not matched:
        raise HTTPException(status_code=401, detail="operator token required")
    return actor_fingerprint(provided)
