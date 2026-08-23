import pytest

from app.models.schemas import Claim, PartyRole, Polarity
from app.services.planner import (
    MAX_GOAL_WORDS,
    compile_refutation,
    disclose_leaks,
    spoken_word_count,
)


GOLDEN_A = [
    Claim(
        id="clm_9c1",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="pallet_staged",
        entity_ids=["PL-9F21"],
        polarity=Polarity.asserted,
        confidence=0.81,
        evidence_span="rolled nine-foxtrot out of dock three",
    ),
    Claim(
        id="clm_arrive",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="driver_arrived",
        entity_ids=["PL-9F21"],
        polarity=Polarity.asserted,
        confidence=0.88,
    ),
    Claim(
        id="clm_seal",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="seal_recorded",
        entity_ids=["PL-9F21"],
        polarity=Polarity.unknown,
        confidence=0.30,
    ),
]

TICKET = {
    "entities": {"pallet_id": "PL-9F21"},
    "parties": [{"role": "B", "phone_e164": "+15550100002"}],
}


def test_disclosure_filter():
    assert disclose_leaks("The warehouse said you stole the pallet") is True
    assert disclose_leaks("Which dock did you pull to?") is False


def test_planner_golden_abstain_and_entity():
    compiled = compile_refutation(TICKET, GOLDEN_A)
    assert "PL-9F21" in compiled["goal"]
    assert "clm_seal" in compiled["abstain"]
    assert compiled["selected_questions"]
    assert "warehouse said" not in compiled["goal"].lower()
    assert spoken_word_count(compiled["goal"]) <= MAX_GOAL_WORDS


def test_greedy_set_cover_prefers_multi_cover():
    compiled = compile_refutation(TICKET, GOLDEN_A, disclosure_budget=1)
    covers = {hid for q in compiled["selected_questions"] for hid in q["covers"]}
    assert "clm_9c1" in covers
    assert "clm_arrive" in covers
    assert len(compiled["selected_questions"]) == 1


def test_leaky_candidates_never_selected():
    from app.models.schemas import Claim, PartyRole, Polarity
    from app.services.planner import candidate_observables

    claim = Claim(
        id="clm_9c1",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="pallet_staged",
        entity_ids=["PL-9F21"],
        polarity=Polarity.asserted,
        confidence=0.81,
    )
    qs = candidate_observables(claim, [claim])
    assert qs
    assert all(not disclose_leaks(q["question"]) for q in qs)
    compiled = compile_refutation(TICKET, [claim])
    assert "warehouse said" not in compiled["goal"].lower()


def test_refuse_oversize_spoken_goal(monkeypatch):
    from app.services import planner

    monkeypatch.setattr(planner, "MAX_GOAL_WORDS", 3)
    with pytest.raises(ValueError, match="spoken-time"):
        compile_refutation(TICKET, GOLDEN_A[:1])
