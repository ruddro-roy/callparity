import pytest

from app.ports.calle import CallTask, Plan
from app.ports.live import LiveCalleSdk, require_e164_phones


def test_require_e164_refuses_empty():
    with pytest.raises(ValueError, match="empty to_phones"):
        require_e164_phones([])
    with pytest.raises(ValueError, match="empty to_phones"):
        require_e164_phones(["", "  "])
    with pytest.raises(ValueError, match="E.164"):
        require_e164_phones(["5550100001"])
    assert require_e164_phones(["+15550100002"]) == ["+15550100002"]


def test_live_plan_and_run_refuse_empty_phones():
    sdk = LiveCalleSdk("https://example.invalid", token="tok")
    with pytest.raises(ValueError, match="empty to_phones"):
        sdk.plan(
            CallTask(
                ticket_id="FR-1842",
                party_role="B",
                to_phones=[],
                goal="g",
                consent=True,
            )
        )
    plan = Plan(
        plan_id="p",
        ticket_id="FR-1842",
        party_role="B",
        ready_to_run=True,
        authorized=True,
        goal="g",
        to_phones=[],
    )
    with pytest.raises(ValueError, match="empty to_phones"):
        sdk.run(plan)


def test_claim_evidence_quote():
    from app.models.schemas import Claim, PartyRole, Polarity

    c = Claim(
        id="clm_x",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="pallet_staged",
        evidence_span="rolled nine-foxtrot out of dock three",
        polarity=Polarity.asserted,
        confidence=0.81,
    )
    assert c.evidence == {"quote": "rolled nine-foxtrot out of dock three"}
