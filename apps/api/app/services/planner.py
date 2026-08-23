from __future__ import annotations

from typing import Any

from app.models.schemas import Claim, RefutationQuestion

ABSTAIN_THRESHOLD = 0.45
SPOKEN_TIME_BUDGET_S = 90
WORDS_PER_SECOND = 2.5
MAX_GOAL_WORDS = int(SPOKEN_TIME_BUDGET_S * WORDS_PER_SECOND)
LEAK_PENALTY_DISCARD = 0.55
LEAK_TOKENS = (
    "warehouse said",
    "they claimed",
    "accusation",
    "they lied",
    "insulin patient",
    "you stole",
    "party a said",
    "they told us you",
    "accused",
)


def disclose_leaks(question: str) -> bool:
    q = question.lower()
    return any(token in q for token in LEAK_TOKENS)


def leak_score(question: str, claims: list[Claim]) -> float:
    """Higher means the question would disclose A's accusation."""
    q = question.lower()
    score = 0.0
    if disclose_leaks(question):
        score += 1.0
    accusatory = ("never staged", "you failed", "you missed", "warehouse asserts")
    if any(tok in q for tok in accusatory):
        score += 0.7
    for claim in claims:
        if claim.polarity.value == "asserted" and claim.predicate.replace("_", " ") in q and "said" in q:
            score += 0.6
    return min(score, 1.0)


def information_gain(question: str, covers: list[str], n_uncovered: int) -> float:
    base = 0.35 * len(covers)
    if "which dock" in question.lower():
        base += 0.4
    if "see" in question.lower() and "jack" in question.lower():
        base += 0.45
    if "arrive" in question.lower():
        base += 0.2
    if "seal" in question.lower():
        base += 0.15
    if "waved" in question.lower() or "who" in question.lower():
        base += 0.25
    coverage_bonus = 0.1 * min(len(covers), max(n_uncovered, 1))
    return min(base + coverage_bonus, 1.0)


def candidate_observables(claim: Claim, all_live: list[Claim]) -> list[dict[str, Any]]:
    pallet = claim.entity_ids[0] if claim.entity_ids else "the pallet"
    live_ids = [c.id for c in all_live]
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
    raw = mapping.get(claim.predicate, [])
    scored: list[dict[str, Any]] = []
    for cand in raw:
        if disclose_leaks(cand["question"]):
            continue
        leak = leak_score(cand["question"], all_live)
        if leak >= LEAK_PENALTY_DISCARD:
            continue
        gain = information_gain(cand["question"], cand["covers"], len(live_ids))
        net = gain - leak
        if net <= 0:
            continue
        scored.append({**cand, "gain": gain, "leak": leak, "net": net})
    return scored


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


def compile_refutation(ticket: dict, claims_a: list[Claim], disclosure_budget: int = 4) -> dict[str, Any]:
    abstain: list[str] = []
    live: list[Claim] = []
    for claim in claims_a:
        if claim.confidence < ABSTAIN_THRESHOLD:
            abstain.append(claim.id)
        else:
            live.append(claim)

    candidates: list[dict[str, Any]] = []
    for claim in live:
        candidates.extend(candidate_observables(claim, live))

    live_ids = {c.id for c in live}
    selected = _greedy_set_cover(candidates, live_ids, disclosure_budget)
    covered = {hid for s in selected for hid in s["covers"]}
    untested = [c.id for c in live if c.id not in covered]
    questions = [s["question"] for s in selected]
    selected_models = [RefutationQuestion(**{k: s[k] for k in ("id", "question", "covers", "gain", "leak", "net") if k in s}) for s in selected]
    goal = "Ask only observable facts. Consent and recording disclosure first. " + " ".join(questions)

    if spoken_word_count(goal) > MAX_GOAL_WORDS:
        raise ValueError("goal exceeds spoken-time budget")
    if len(goal) > 1200:
        raise ValueError("goal exceeds spoken-time budget")

    critical = ticket.get("entities", {}).get("pallet_id")
    if critical and selected and critical not in goal:
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
        "selected_questions": [q.model_dump() for q in selected_models],
        "abstain": abstain,
        "untested": untested,
    }
