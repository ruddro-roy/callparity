import pytest

from app.models.schemas import Claim, PartyRole, Polarity
from app.services.planner import (
    LEAK_DROP_THRESHOLD,
    MAX_GOAL_WORDS,
    LeakKind,
    build_disclosure_profile,
    compile_refutation,
    disclose_leaks,
    leak_findings,
    leak_score,
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


SLOTTED_A = [
    Claim(
        id="clm_staged",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="pallet_staged",
        entity_ids=["PL-9F21"],
        slot={"dock": "3", "at": "2026-08-23T06:40:00+06:00"},
        polarity=Polarity.asserted,
        confidence=0.81,
        evidence_span="rolled nine-foxtrot out of dock three",
    ),
    Claim(
        id="clm_arrived",
        ticket_id="FR-1842",
        source_party=PartyRole.A,
        predicate="driver_arrived",
        entity_ids=["PL-9F21"],
        polarity=Polarity.asserted,
        confidence=0.88,
        evidence_span="Driver pulled in, we waved him toward three.",
    ),
]


def test_leaky_recap_dropped_without_token_match():
    """A recap leaks by structure (asserted values, verbatim quotes), not by magic tokens."""
    profile = build_disclosure_profile(SLOTTED_A, TICKET)

    recap = "Can you confirm PL-9F21 left dock 3 at 06:40?"
    kinds = {f.kind for f in leak_findings(recap, profile)}
    assert LeakKind.ASSERTED_VALUE in kinds
    assert leak_score(recap, profile) >= LEAK_DROP_THRESHOLD

    verbatim = "They rolled nine-foxtrot out of dock three, right?"
    kinds = {f.kind for f in leak_findings(verbatim, profile)}
    assert LeakKind.ASSERTED_VALUE in kinds

    polar = "Was the pallet staged when the truck showed up?"
    kinds = {f.kind for f in leak_findings(polar, profile)}
    assert LeakKind.POLAR_HYPOTHESIS in kinds

    compiled = compile_refutation(TICKET, SLOTTED_A)
    assert compiled["dropped_questions"], "the naive recap candidate must be generated and dropped"
    for dropped in compiled["dropped_questions"]:
        assert dropped["leak"] >= LEAK_DROP_THRESHOLD
        assert dropped["leak_kinds"]
    for q in compiled["selected_questions"]:
        text = q["question"].lower()
        assert "dock 3" not in text
        assert "06:40" not in text
        assert q["leak"] < LEAK_DROP_THRESHOLD


def test_golden_observables_survive_leak_check():
    compiled = compile_refutation(TICKET, SLOTTED_A)
    questions = " ".join(q["question"].lower() for q in compiled["selected_questions"])
    assert "which dock" in questions
    assert "jack" in questions
    assert all(q["leak"] == 0.0 for q in compiled["selected_questions"])
    assert "PL-9F21" in compiled["goal"]


def test_missing_critical_entity_refuses_plan():
    bare = {"entities": {}, "parties": [{"role": "B", "phone_e164": "+15550100002"}]}
    with pytest.raises(ValueError, match="critical entity"):
        compile_refutation(bare, SLOTTED_A)


def test_voicemail_never_confirms():
    from app.ports.calle import RunView
    from app.services.extractor import extract_claims
    from app.services.merger import merge_graph
    from app.models.schemas import ActionKind, EdgeStatus

    voicemail = RunView(
        run_id="run_vm",
        status="voicemail",
        structured_result={"unreachable": True, "disposition": "voicemail"},
        transcript="",
        summary="voicemail",
    )
    assert extract_claims("FR-1842", "B", voicemail) == []
    edges, card = merge_graph("FR-1842", SLOTTED_A, [])
    assert all(e.status != EdgeStatus.CONFIRMED for e in edges)
    assert any(e.status == EdgeStatus.UNREACHABLE for e in edges)
    assert card.action == ActionKind.HOLD_FOR_HUMAN
