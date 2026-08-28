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


def presented_actor(authorization: str | None, x_operator_token: str | None) -> str | None:
    """Actor id when the request carries the valid operator token, else None.

    Fails closed: an unset server token matches nobody. Comparison is
    constant-time, on bytes, so a non-ASCII header value returns None rather
    than raising inside compare_digest.
    """
    configured = get_settings().operator_token.strip()
    provided = _bearer(authorization, x_operator_token)
    if (
        not configured
        or not provided
        or not hmac.compare_digest(configured.encode("utf-8"), provided.encode("utf-8"))
    ):
        return None
    return actor_fingerprint(provided)


def require_operator(
    authorization: str | None = Header(default=None),
    x_operator_token: str | None = Header(default=None, alias="X-Operator-Token"),
) -> str:
    """Gate a mutating route on the shared operator token. Returns the actor id.

    Fails closed: an unset server token denies everyone, and a missing or wrong
    request token is 401. The token itself never enters a log line or the
    audit trail, only its fingerprint.
    """
    actor = presented_actor(authorization, x_operator_token)
    if actor is None:
        raise HTTPException(status_code=401, detail="operator token required")
    return actor
