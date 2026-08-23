from app.fixtures.calle import FixtureCalle
from app.ports.calle import CallTask
from app.services.extractor import extract_claims, span


def test_extracts_spans_from_fixture_a():
    calle = FixtureCalle()
    pa = calle.plan(CallTask(ticket_id="FR-1842", party_role="A", to_phones=["+15550100001"], goal="g", consent=True))
    va = calle.get(calle.run(pa))
    claims = extract_claims("FR-1842", "A", va)
    preds = {c.predicate for c in claims}
    assert "pallet_staged" in preds
    assert any(c.evidence_span for c in claims)
    assert "dock" in span(va.transcript, ("dock",)).lower()
