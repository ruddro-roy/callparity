"""Every import persists who acted, which call ids, the action, and the job id."""

from test_live_import import (
    DRIVER_CALL_ID,
    IMPORT_BODY,
    WAREHOUSE_CALL_ID,
    reader_override,
    recorded_get_transport,
)


def _audit_rows():
    from app.db import session_factory
    from app.models.orm import ImportAuditRow

    with session_factory()() as session:
        return session.query(ImportAuditRow).order_by(ImportAuditRow.created_at).all()


def test_import_writes_audit_row_with_action_and_job(client):
    with reader_override(recorded_get_transport({})):
        res = client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    assert res.status_code == 200
    job_id = res.json()["id"]

    rows = _audit_rows()
    assert rows, "import must persist an audit row"
    row = rows[-1]
    assert row.ticket_id == "FR-1842"
    assert row.call_id_a == WAREHOUSE_CALL_ID
    assert row.call_id_b == DRIVER_CALL_ID
    assert row.action == "RESTAGE_AND_RECALL"
    assert row.job_id == job_id
    assert row.actor.startswith("op_")


def test_audit_never_stores_the_raw_token(client):
    with reader_override(recorded_get_transport({})):
        client.post("/v1/tickets/FR-1842/parity/import", json=IMPORT_BODY)
    for row in _audit_rows():
        assert "test-operator-token" not in row.actor
