import hashlib
import json


def derive_idempotency_key(ticket_id: str, party: str, claim_set: list[dict] | None = None) -> str:
    """Authorization-scoped key: ticket + party + claim-set hash, not HTTP attempt."""
    payload = {
        "ticket_id": ticket_id,
        "party": party,
        "claims": sorted((claim_set or []), key=lambda c: c.get("id", "")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"{ticket_id}:{party}:{digest[:16]}"


def sha256_text(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
