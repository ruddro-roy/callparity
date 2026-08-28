"""A crash cannot wedge a ticket's parity behind a stuck job.

Jobs run as background tasks that die with the process. Before this
reconciliation, a row left queued or running by a crash replayed forever
through the idempotency lookup, and because the derived key is constant per
ticket, that ticket could never run parity again. At startup every orphaned
row becomes failed with a clear error and its idempotency key is released,
so a deliberate operator retry starts a fresh run. Nothing re-executes
automatically: in live mode that would redial humans.
"""

import os

import pytest
from app.models.orm import JobRow
from app.services.idempotency import derive_idempotency_key
from app.services.jobs import INTERRUPTED_ERROR, reconcile_interrupted_jobs
from fastapi.testclient import TestClient

OPERATOR_TOKEN = os.environ["OPERATOR_TOKEN"]
AUTH = {"Authorization": f"Bearer {OPERATOR_TOKEN}"}


def make_job(session, job_id: str, key: str, status: str, ticket_id: str = "FR-1842") -> None:
    session.add(
        JobRow(
            id=job_id,
            ticket_id=ticket_id,
            status=status,
            idempotency_key=key,
            phase=status,
        )
    )
    session.commit()


def wait_for_terminal(client, job_id: str) -> dict:
    last = None
    for _ in range(50):
        last = client.get(f"/v1/jobs/{job_id}").json()
        if last["status"] in {"completed", "failed"}:
            return last
    raise AssertionError(f"job stuck: {last}")


def test_orphans_fail_with_clear_error_and_release_their_key(client):
    from app.db import session_factory

    with session_factory()() as session:
        make_job(session, "job_stuckrun01", "key-running", "running")
        make_job(session, "job_stuckqueue", "key-queued", "queued")
        reconciled = reconcile_interrupted_jobs(session)
    assert sorted(reconciled) == ["job_stuckqueue", "job_stuckrun01"]

    with session_factory()() as session:
        for job_id, key in (("job_stuckrun01", "key-running"), ("job_stuckqueue", "key-queued")):
            row = session.get(JobRow, job_id)
            assert row.status == "failed"
            assert row.error == INTERRUPTED_ERROR
            assert row.phase == "failed"
            assert row.idempotency_key == f"{key}#interrupted:{job_id}"
        # A second pass finds nothing: reconciliation is idempotent.
        assert reconcile_interrupted_jobs(session) == []


def test_terminal_rows_keep_their_state_and_keys(client):
    from app.db import session_factory

    with session_factory()() as session:
        make_job(session, "job_done000001", "key-done", "completed")
        make_job(session, "job_failed0001", "key-failed", "failed")
        make_job(session, "job_cancel0001", "key-cancelled", "cancelled")
        assert reconcile_interrupted_jobs(session) == []
        for job_id, status, key in (
            ("job_done000001", "completed", "key-done"),
            ("job_failed0001", "failed", "key-failed"),
            ("job_cancel0001", "cancelled", "key-cancelled"),
        ):
            row = session.get(JobRow, job_id)
            assert row.status == status
            assert row.idempotency_key == key


def test_released_key_fits_the_column_even_for_maximal_header_keys(client):
    from app.db import session_factory

    long_key = "k" * 128  # the widest value the column accepts
    with session_factory()() as session:
        make_job(session, "job_longkey001", long_key, "running")
        reconcile_interrupted_jobs(session)
        row = session.get(JobRow, "job_longkey001")
        assert len(row.idempotency_key) <= 128
        assert row.idempotency_key.endswith("#interrupted:job_longkey001")


@pytest.fixture
def crashed_then_rebooted(tmp_path, monkeypatch):
    """A database holding a job the previous process never finished."""
    db = tmp_path / "crash.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db}")
    monkeypatch.setenv("REDIS_OPTIONAL", "true")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    monkeypatch.setenv("USE_FIXTURES", "true")
    monkeypatch.setenv("PLAYBACK_DELAY_MS", "0")
    monkeypatch.setenv("OPERATOR_TOKEN", OPERATOR_TOKEN)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000000")

    from app.config import get_settings
    from app.db import init_db, reset_engine, session_factory

    get_settings.cache_clear()
    reset_engine()
    init_db()
    from seed_demo_data import seed

    seed()
    stuck_key = derive_idempotency_key("FR-1842", "AB", None)
    with session_factory()() as session:
        make_job(session, "job_diedmidrun", stuck_key, "running")
    yield
    reset_engine()
    get_settings.cache_clear()


def test_startup_unwedges_the_ticket_and_a_retry_completes(crashed_then_rebooted):
    from app.main import app

    with TestClient(app) as client:  # lifespan is the reboot
        client.headers.update(AUTH)

        stuck = client.get("/v1/jobs/job_diedmidrun").json()
        assert stuck["status"] == "failed"
        assert stuck["error"] == INTERRUPTED_ERROR

        # The retry gets a fresh job under the original derived key, instead
        # of replaying the corpse forever.
        rerun = client.post("/v1/tickets/FR-1842/parity")
        assert rerun.status_code == 202
        assert rerun.json()["id"] != "job_diedmidrun"
        finished = wait_for_terminal(client, rerun.json()["id"])
        assert finished["status"] == "completed"
        assert finished["result"]["action"]["action"] == "RESTAGE_AND_RECALL"
