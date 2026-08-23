from app.fixtures.calle import FixtureCalle
from app.models.schemas import ActionKind, EdgeStatus
from app.ports.calle import CallTask
from app.services.extractor import extract_claims
from app.services.merger import merge_graph


def _views(ticket_id: str):
    calle = FixtureCalle()
    pa = calle.plan(CallTask(ticket_id=ticket_id, party_role="A", to_phones=["+15550100001"], goal="g", consent=True))
    va = calle.get(calle.run(pa))
    pb = calle.plan(CallTask(ticket_id=ticket_id, party_role="B", to_phones=["+15550100002"], goal="g", consent=True))
    vb = calle.get(calle.run(pb))
    return extract_claims(ticket_id, "A", va), extract_claims(ticket_id, "B", vb)


def test_fr1842_contradicted_restage():
    claims_a, claims_b = _views("FR-1842")
    edges, card = merge_graph("FR-1842", claims_a, claims_b)
    staged = next(e for e in edges if e.predicate == "pallet_staged")
    assert staged.status == EdgeStatus.CONTRADICTED
    assert card.action == ActionKind.RESTAGE_AND_RECALL
    arrived = next(e for e in edges if e.predicate == "driver_arrived")
    assert arrived.status == EdgeStatus.CONFIRMED
    seal = next(e for e in edges if e.predicate == "seal_recorded")
    assert seal.status in {EdgeStatus.UNTESTED, EdgeStatus.ABSTAIN}


def test_control_confirmed_release():
    claims_a, claims_b = _views("FR-1900")
    edges, card = merge_graph("FR-1900", claims_a, claims_b)
    staged = next(e for e in edges if e.predicate == "pallet_staged")
    assert staged.status == EdgeStatus.CONFIRMED
    assert card.action == ActionKind.RELEASE_TRUCK


def test_unreachable_when_b_silent():
    claims_a, _ = _views("FR-1842")
    edges, card = merge_graph("FR-1842", claims_a, [])
    assert any(e.status == EdgeStatus.UNREACHABLE for e in edges)
    assert card.action == ActionKind.HOLD_FOR_HUMAN
    assert "human" in card.rationale.lower()
