"""OPERATOR_TOKEN accepts comma-separated tokens so rotation needs no cutover.

A single-token value behaves exactly as before. During a rotation window the
old and new token are both configured; each keeps its own fingerprint so
audit rows and rate buckets tell them apart. Malformed values (empty
segments) refuse to boot, and the comparison mechanism stays
hmac.compare_digest for every candidate.
"""

from __future__ import annotations

import inspect

import pytest
from app.config import Settings, get_settings
from app.security import actor_fingerprint, require_operator
from pydantic import ValidationError
from test_live_import import IMPORT_BODY, reader_override, recorded_get_transport

OLD_TOKEN = "rotation-old-credential"
NEW_TOKEN = "rotation-new-credential"


def _audit_rows():
    from app.db import session_factory
    from app.models.orm import ImportAuditRow

    with session_factory()() as session:
        return session.query(ImportAuditRow).order_by(ImportAuditRow.created_at).all()


def test_single_token_value_parses_and_still_gates(client):
    assert Settings(operator_token="only-one").operator_tokens == ("only-one",)
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 200
    wrong = client.post("/v1/tickets/FR-1842/preview", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401


def test_pair_value_parses_with_whitespace_tolerance():
    assert Settings(operator_token=f"{OLD_TOKEN}, {NEW_TOKEN}").operator_tokens == (
        OLD_TOKEN,
        NEW_TOKEN,
    )


def test_both_rotation_tokens_authorized_with_distinct_audit_fingerprints(client, monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKEN", f"{OLD_TOKEN},{NEW_TOKEN}")
    get_settings.cache_clear()
    with reader_override(recorded_get_transport({})):
        res_old = client.post(
            "/v1/tickets/FR-1842/parity/import",
            json=IMPORT_BODY,
            headers={"Authorization": f"Bearer {OLD_TOKEN}"},
        )
        res_new = client.post(
            "/v1/tickets/FR-1842/parity/import",
            json=IMPORT_BODY,
            headers={"Authorization": f"Bearer {NEW_TOKEN}"},
        )
    assert res_old.status_code == 200
    assert res_new.status_code == 200

    actors = [row.actor for row in _audit_rows()]
    assert actors == [actor_fingerprint(OLD_TOKEN), actor_fingerprint(NEW_TOKEN)]
    assert actors[0] != actors[1]
    for actor in actors:
        assert actor.startswith("op_")
        assert OLD_TOKEN not in actor
        assert NEW_TOKEN not in actor


def test_third_token_is_401_and_ip_metered_during_rotation(client, monkeypatch):
    from app.rate_limit import reset_rate_limiter

    monkeypatch.setenv("OPERATOR_TOKEN", f"{OLD_TOKEN},{NEW_TOKEN}")
    monkeypatch.setenv("MUTATING_RATE_LIMIT", "2")
    get_settings.cache_clear()
    reset_rate_limiter()
    forged = {"Authorization": "Bearer some-third-credential"}
    assert client.post("/v1/tickets/FR-1842/preview", headers=forged).status_code == 401
    assert client.post("/v1/tickets/FR-1842/preview", headers=forged).status_code == 401
    denied = client.post("/v1/tickets/FR-1842/preview", headers=forged)
    assert denied.status_code == 429
    assert int(denied.headers["Retry-After"]) >= 1


def test_dropping_the_old_token_ends_its_access(client, monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKEN", NEW_TOKEN)
    get_settings.cache_clear()
    old = client.post(
        "/v1/tickets/FR-1842/preview", headers={"Authorization": f"Bearer {OLD_TOKEN}"}
    )
    new = client.post(
        "/v1/tickets/FR-1842/preview", headers={"Authorization": f"Bearer {NEW_TOKEN}"}
    )
    assert old.status_code == 401
    assert new.status_code == 200


@pytest.mark.parametrize("bad", ["a,,b", ",", " , ", "a,", ",b"])
def test_empty_token_segments_refuse_to_boot(bad, monkeypatch):
    with pytest.raises(ValidationError):
        Settings(operator_token=bad)
    monkeypatch.setenv("OPERATOR_TOKEN", bad)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_unset_token_still_denies_everyone_without_refusing_boot(client, monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKEN", "")
    get_settings.cache_clear()
    assert Settings(operator_token="").operator_tokens == ()
    assert client.post("/v1/tickets/FR-1842/preview").status_code == 401


def test_constant_time_comparison_is_the_mechanism():
    source = inspect.getsource(require_operator)
    assert "hmac.compare_digest" in source
    # Every candidate is compared; no equality shortcut on the token value.
    assert "|=" in source
    assert "provided ==" not in source and "== provided" not in source
