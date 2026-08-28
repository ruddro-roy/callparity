from app.db import session_factory
from app.models.orm import TicketRow
from seed_demo_data import seed


def test_seed_is_idempotent_and_includes_required_tickets(client):
    SessionLocal = session_factory()
    s = SessionLocal()
    seed(s)
    seed(s)
    ids = {row.id for row in s.query(TicketRow).all()}
    assert {"FR-1842", "FR-1900"}.issubset(ids)
    assert s.query(TicketRow).filter(TicketRow.id == "FR-1842").count() == 1
    s.close()
