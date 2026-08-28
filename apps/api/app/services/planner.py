from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.models.schemas import Claim, Polarity, RefutationQuestion

ABSTAIN_THRESHOLD = 0.45
SPOKEN_TIME_BUDGET_S = 90
WORDS_PER_SECOND = 2.5
MAX_GOAL_WORDS = int(SPOKEN_TIME_BUDGET_S * WORDS_PER_SECOND)
LEAK_DROP_THRESHOLD = 0.5

_ATTRIBUTION_VERBS = (
    "said",
    "says",
    "say",
    "told",
    "tells",
    "claimed",
    "claims",
    "reported",
    "reports",
    "insisted",
    "insists",
    "asserted",
    "asserts",
    "mentioned",
    "according to",
)
# Sources whose reported speech would recap Party A to Party B.
_RECAP_SUBJECTS = (
    "party a",
    "the other party",
    "the other side",
    "they",
    "our records",
    "the system",
    "the report",
    "dispatch",
)
_BLAME_PHRASES = (
    "you failed",
    "you missed",
    "you never",
    "you lied",
    "you stole",
    "your fault",
    "why didn't you",
    "you were supposed",
    "accusation",
    "accused",
    "blame",
)
_CLINICAL_TERMS = ("patient", "dose", "dosage", "prescription", "diagnosis")
_POLAR_STARTERS = (
    "did",
    "do",
    "does",
    "is",
    "are",
    "was",
    "were",
    "can",
    "could",
    "has",
    "have",
    "will",
    "would",
)
_PERCEPTION_VERBS = (
    "see",
    "saw",
    "read",
    "hear",
    "heard",
    "notice",
    "noticed",
    "count",
    "counted",
    "speak",
    "spoke",
    "talk",
    "talked",
)
_WH_STARTERS = ("which", "what", "who", "when", "where", "how")
_DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}
# Entity nouns shared by the ticket itself; they never encode A's answer.
_PREDICATE_STOPWORDS = {"pallet", "driver", "seal", "truck", "trailer"}
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


class LeakKind(str, Enum):
    ATTRIBUTION = "attribution"
    ASSERTED_VALUE = "asserted_value"
    POLAR_HYPOTHESIS = "polar_hypothesis"
    BLAME = "blame"
    CLINICAL = "clinical"


_LEAK_SEVERITY = {
    LeakKind.ATTRIBUTION: 1.0,
    LeakKind.BLAME: 1.0,
    LeakKind.CLINICAL: 1.0,
    LeakKind.ASSERTED_VALUE: 0.9,
    LeakKind.POLAR_HYPOTHESIS: 0.7,
}


@dataclass(frozen=True)
class LeakFinding:
    kind: LeakKind
    detail: str


@dataclass(frozen=True)
class DisclosureProfile:
    """Everything Party B could use to recover what Party A asserted.

    attribution_subjects: names for Party A or a recap source.
    asserted_values: normalized slot values that exist only because A said them.
    evidence_shingles: 3-word shingles from A's quoted transcript spans.
    contested_terms: predicate words for A's live world-state claims.
    """

    attribution_subjects: tuple[str, ...]
    asserted_values: tuple[str, ...]
    evidence_shingles: frozenset[str]
    contested_terms: tuple[str, ...]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9:+' ]", " ", text.lower()).strip()


def _value_phrases(slot_key: str, value: Any, shared: set[str]) -> list[str]:
    raw = str(value).strip()
    if not raw or raw.lower() in shared:
        return []
    phrases: list[str] = []
    lowered = raw.lower()
    time_match = _TIME_RE.search(lowered)
    if time_match:
        hh, mm = time_match.groups()
        phrases.extend([f"{hh}:{mm}", f"{int(hh)}:{mm}"])
        return phrases
    if len(lowered) >= 3:
        phrases.append(lowered)
    key = slot_key.replace("_", " ").strip()
    phrases.append(f"{key} {lowered}")
    if lowered in _DIGIT_WORDS:
        phrases.append(f"{key} {_DIGIT_WORDS[lowered]}")
    return phrases


def _shingles(span: str, size: int = 3) -> set[str]:
    words = _norm(span).split()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def build_disclosure_profile(
    claims: Iterable[Claim], ticket: dict[str, Any] | None = None
) -> DisclosureProfile:
    claims = list(claims)
    shared: set[str] = set()
    for claim in claims:
        shared.update(e.lower() for e in claim.entity_ids)
    subjects: list[str] = list(_RECAP_SUBJECTS)
    if ticket:
        shared.update(str(v).lower() for v in (ticket.get("entities") or {}).values())
        for party in ticket.get("parties", []):
            if party.get("role") == "A":
                label_words = _norm(str(party.get("label") or "")).split()
                subjects.extend(w for w in label_words if len(w) > 3)
    # Party A is a warehouse in every seeded freight ticket; keep the word as a
    # recap subject even when the ticket omits the label.
    if "warehouse" not in subjects:
        subjects.append("warehouse")

    values: list[str] = []
    shingles: set[str] = set()
    terms: list[str] = []
    for claim in claims:
        for key, value in (claim.slot or {}).items():
            if value is None:
                continue
            values.extend(_value_phrases(key, value, shared))
        if claim.evidence_span:
            shingles.update(_shingles(claim.evidence_span))
        if claim.polarity != Polarity.unknown:
            terms.extend(
                w for w in claim.predicate.split("_") if w not in _PREDICATE_STOPWORDS
            )
    return DisclosureProfile(
        attribution_subjects=tuple(dict.fromkeys(subjects)),
        asserted_values=tuple(dict.fromkeys(values)),
        evidence_shingles=frozenset(shingles),
        contested_terms=tuple(dict.fromkeys(terms)),
    )


_EMPTY_PROFILE = DisclosureProfile(
    attribution_subjects=tuple(_RECAP_SUBJECTS) + ("warehouse",),
    asserted_values=(),
    evidence_shingles=frozenset(),
    contested_terms=(),
)


def leak_findings(question: str, profile: DisclosureProfile | None = None) -> list[LeakFinding]:
    """A question leaks when Party B could recover Party A's assertion from it."""
    profile = profile or _EMPTY_PROFILE
    q = _norm(question)
    tokens = q.split()
    findings: list[LeakFinding] = []

    if any(verb in q for verb in _ATTRIBUTION_VERBS):
        for subject in profile.attribution_subjects:
            if subject in q:
                findings.append(LeakFinding(LeakKind.ATTRIBUTION, f"reported speech of '{subject}'"))
                break

    for value in profile.asserted_values:
        if value in q:
            findings.append(LeakFinding(LeakKind.ASSERTED_VALUE, f"names A's asserted '{value}'"))
    for shingle in profile.evidence_shingles:
        if shingle and shingle in q:
            findings.append(LeakFinding(LeakKind.ASSERTED_VALUE, f"quotes A verbatim: '{shingle}'"))
            break

    if tokens and tokens[0] in _POLAR_STARTERS:
        perception = len(tokens) > 2 and tokens[1] == "you" and tokens[2] in _PERCEPTION_VERBS
        if not perception:
            for term in profile.contested_terms:
                if term in tokens:
                    findings.append(
                        LeakFinding(LeakKind.POLAR_HYPOTHESIS, f"yes/no framing of contested '{term}'")
                    )
                    break

    for phrase in _BLAME_PHRASES:
        if phrase in q:
            findings.append(LeakFinding(LeakKind.BLAME, f"accusatory '{phrase}'"))
            break
    for term in _CLINICAL_TERMS:
        if term in tokens:
            findings.append(LeakFinding(LeakKind.CLINICAL, f"clinical term '{term}'"))
            break
    return findings


def leak_score(question: str, profile: DisclosureProfile | None = None) -> float:
    findings = leak_findings(question, profile)
    if not findings:
        return 0.0
    return max(_LEAK_SEVERITY[f.kind] for f in findings)


def disclose_leaks(question: str, profile: DisclosureProfile | None = None) -> bool:
    return leak_score(question, profile) >= LEAK_DROP_THRESHOLD


def information_gain(question: str, covers: list[str], n_uncovered: int) -> float:
    tokens = _norm(question).split()
    base = 0.35 * len(covers)
    if tokens and tokens[0] in _WH_STARTERS:
        base += 0.25
    elif len(tokens) > 2 and tokens[0] in _POLAR_STARTERS and tokens[1] == "you" and tokens[2] in _PERCEPTION_VERBS:
        base += 0.3
    coverage_bonus = 0.1 * min(len(covers), max(n_uncovered, 1))
    return min(base + coverage_bonus, 1.0)


def _naive_recap(claim: Claim, pallet: str) -> str | None:
    """The question a naive follow-up bot would ask. Must always leak-drop."""
    if claim.polarity != Polarity.asserted:
        return None
    slot_bits = []
    for key, value in (claim.slot or {}).items():
        if value is None:
            continue
        raw = str(value)
        time_match = _TIME_RE.search(raw)
        if time_match:
            raw = ":".join(time_match.groups())
        slot_bits.append(f"{key.replace('_', ' ')} {raw}")
    if not slot_bits:
        return None
    predicate = claim.predicate.replace("_", " ")
    return f"Can you confirm {pallet} {predicate} at {' and '.join(slot_bits)}?"


def _raw_candidates(claim: Claim, all_live: list[Claim]) -> list[dict[str, Any]]:
    pallet = claim.entity_ids[0] if claim.entity_ids else "the pallet"
    mapping: dict[str, list[dict[str, Any]]] = {
        "pallet_staged": [
            {
                "id": f"q_{claim.id}_dock",
                "question": f"Which dock did you pull to for {pallet}?",
                "covers": [claim.id],
            },
            {
                "id": f"q_{claim.id}_seen",
                "question": f"Did you see {pallet} on a jack?",
                "covers": [claim.id],
            },
            {
                "id": f"q_{claim.id}_wave",
                "question": "Who waved you off, and from which door?",
                "covers": [claim.id],
            },
        ],
        "driver_arrived": [
            {
                "id": f"q_{claim.id}_arrive",
                "question": "What time did you arrive at the gate?",
                "covers": [claim.id],
            }
        ],
        "seal_recorded": [
            {
                "id": f"q_{claim.id}_seal",
                "question": f"Did you read a seal number on {pallet}?",
                "covers": [claim.id],
            }
        ],
    }
    # Multi-cover observable used by greedy set-cover (arrival + staging).
    if claim.predicate == "pallet_staged":
        arrived = next((c for c in all_live if c.predicate == "driver_arrived"), None)
        if arrived:
            mapping["pallet_staged"].append(
                {
                    "id": f"q_{claim.id}_combo",
                    "question": f"When you arrived, which dock held {pallet}?",
                    "covers": [claim.id, arrived.id],
                }
            )
    candidates = list(mapping.get(claim.predicate, []))
    recap = _naive_recap(claim, pallet)
    if recap:
        candidates.append({"id": f"q_{claim.id}_recap", "question": recap, "covers": [claim.id]})
    return candidates


def candidate_observables(
    claim: Claim,
    all_live: list[Claim],
    profile: DisclosureProfile | None = None,
) -> list[dict[str, Any]]:
    """Scored candidates that survive the leak check."""
    kept, _ = score_candidates(claim, all_live, profile or build_disclosure_profile(all_live))
    return kept


def score_candidates(
    claim: Claim,
    all_live: list[Claim],
    profile: DisclosureProfile,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    live_ids = [c.id for c in all_live]
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for cand in _raw_candidates(claim, all_live):
        findings = leak_findings(cand["question"], profile)
        leak = max((_LEAK_SEVERITY[f.kind] for f in findings), default=0.0)
        gain = information_gain(cand["question"], cand["covers"], len(live_ids))
        scored = {
            **cand,
            "gain": gain,
            "leak": leak,
            "net": gain - leak,
            "leak_kinds": list(dict.fromkeys(f.kind.value for f in findings)),
        }
        if leak >= LEAK_DROP_THRESHOLD or scored["net"] <= 0:
            dropped.append(scored)
        else:
            kept.append(scored)
    return kept, dropped


def _greedy_set_cover(candidates: list[dict[str, Any]], live_ids: set[str], budget: int) -> list[dict[str, Any]]:
    remaining = set(live_ids)
    selected: list[dict[str, Any]] = []
    pool = list(candidates)
    while remaining and pool and len(selected) < budget:
        def key(c: dict[str, Any]) -> tuple[int, float]:
            cover_count = len(remaining.intersection(c["covers"]))
            return (cover_count, c["net"])

        pool.sort(key=key, reverse=True)
        best = pool.pop(0)
        newly = remaining.intersection(best["covers"])
        if not newly:
            continue
        selected.append(best)
        remaining -= newly
    # Fill leftover budget with unused high-gain observables (demo questions).
    leftover = [c for c in pool if c not in selected]
    leftover.sort(key=lambda c: c["net"], reverse=True)
    for cand in leftover:
        if len(selected) >= budget:
            break
        selected.append(cand)
    return selected


def spoken_word_count(text: str) -> int:
    return len([w for w in text.replace("/", " ").split() if w])


def _to_question_model(cand: dict[str, Any]) -> RefutationQuestion:
    return RefutationQuestion(
        id=cand["id"],
        question=cand["question"],
        covers=cand["covers"],
        gain=cand["gain"],
        leak=cand["leak"],
        net=cand["net"],
        leak_kinds=cand.get("leak_kinds", []),
    )


def compile_refutation(ticket: dict, claims_a: list[Claim], disclosure_budget: int = 4) -> dict[str, Any]:
    critical = (ticket.get("entities") or {}).get("pallet_id")
    if not critical:
        raise ValueError("ticket missing critical entity id (entities.pallet_id)")

    abstain: list[str] = []
    live: list[Claim] = []
    for claim in claims_a:
        if claim.confidence < ABSTAIN_THRESHOLD:
            abstain.append(claim.id)
        else:
            live.append(claim)

    profile = build_disclosure_profile(live, ticket)
    candidates: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for claim in live:
        kept_c, dropped_c = score_candidates(claim, live, profile)
        candidates.extend(kept_c)
        dropped.extend(dropped_c)

    live_ids = {c.id for c in live}
    selected = _greedy_set_cover(candidates, live_ids, disclosure_budget)
    covered = {hid for s in selected for hid in s["covers"]}
    untested = [c.id for c in live if c.id not in covered]
    questions = [s["question"] for s in selected]
    goal = "Ask only observable facts. Consent and recording disclosure first. " + " ".join(questions)

    if spoken_word_count(goal) > MAX_GOAL_WORDS:
        raise ValueError("goal exceeds spoken-time budget")
    if len(goal) > 1200:
        raise ValueError("goal exceeds spoken-time budget")

    if selected and critical not in goal:
        raise ValueError("goal missing critical entity id")

    result_schema = {
        "type": "object",
        "properties": {
            hid: {"type": "object", "properties": {"answer": {"type": "string"}}}
            for s in selected
            for hid in s["covers"]
        },
    }
    party_b = next(p for p in ticket["parties"] if p["role"] == "B")
    return {
        "to_phones": [party_b["phone_e164"]],
        "goal": goal,
        "result_schema": result_schema,
        "selected_questions": [_to_question_model(s).model_dump() for s in selected],
        "dropped_questions": [_to_question_model(d).model_dump() for d in dropped],
        "abstain": abstain,
        "untested": untested,
    }
