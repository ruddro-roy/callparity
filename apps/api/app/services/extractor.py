from __future__ import annotations

from app.models.schemas import Claim, PartyRole, Polarity
from app.ports.calle import RunView


def extract_claims(ticket_id: str, party: str, run: RunView) -> list[Claim]:
    """Normalize fixture or live structured results plus transcript spans into Claims."""
    sr = run.structured_result or {}
    role = PartyRole(party)
    claims: list[Claim] = []
    if sr.get("unreachable") or run.status in {"voicemail", "unreachable", "no_answer"}:
        return claims

    if isinstance(sr.get("claims"), list):
        for raw in sr["claims"]:
            claims.append(_from_raw(ticket_id, role, run, raw))
        return claims

    pallet = sr.get("pallet_id") or _find_entity(run.transcript) or "unknown-pallet"

    if "pallet_staged" in sr:
        claims.append(
            Claim(
                id=f"clm_{ticket_id}_{party}_pallet_staged",
                ticket_id=ticket_id,
                source_party=role,
                predicate="pallet_staged",
                entity_ids=[pallet],
                slot={"dock": sr.get("dock"), "at": sr.get("at")},
                polarity=_bool_polarity(sr.get("pallet_staged")),
                confidence=_conf(sr, "pallet_staged_confidence", default=0.81 if party == "A" else 0.9),
                evidence_span=span(run.transcript, ("dock", "staged", "rolled", "jack")),
                call_run_id=run.run_id,
            )
        )

    if sr.get("driver_seen") is True or sr.get("arrived") is True:
        claims.append(
            Claim(
                id=f"clm_{ticket_id}_{party}_driver_arrived",
                ticket_id=ticket_id,
                source_party=role,
                predicate="driver_arrived",
                entity_ids=[pallet],
                slot={"at": sr.get("arrived_at")},
                polarity=Polarity.asserted,
                confidence=_conf(sr, "arrived_confidence", default=0.88),
                evidence_span=span(run.transcript, ("driver", "pulled", "arrive", "gate")),
                call_run_id=run.run_id,
            )
        )

    if "seal_number" in sr:
        seal = sr.get("seal_number")
        claims.append(
            Claim(
                id=f"clm_{ticket_id}_{party}_seal_recorded",
                ticket_id=ticket_id,
                source_party=role,
                predicate="seal_recorded",
                entity_ids=[pallet],
                slot={"seal": seal},
                polarity=Polarity.asserted if seal else Polarity.unknown,
                confidence=0.50 if not seal else 0.92,
                evidence_span=span(run.transcript, ("seal",)),
                call_run_id=run.run_id,
            )
        )

    if party == "B" and "saw_pallet_pl9f21" in sr:
        seen = bool(sr.get("saw_pallet_pl9f21"))
        claims.append(
            Claim(
                id=f"clm_{ticket_id}_B_saw_pallet",
                ticket_id=ticket_id,
                source_party=role,
                predicate="pallet_visible_to_driver",
                entity_ids=[pallet],
                slot={"dock_pulled_to": sr.get("dock_pulled_to"), "dock_3_state": sr.get("dock_3_state")},
                polarity=Polarity.asserted if seen else Polarity.denied,
                confidence=0.86,
                evidence_span=span(run.transcript, ("never saw", "empty", "pallet")),
                call_run_id=run.run_id,
            )
        )

    return claims


def span(transcript: str, needles: tuple[str, ...]) -> str:
    if not transcript:
        return ""
    lower = transcript.lower()
    for needle in needles:
        idx = lower.find(needle.lower())
        if idx >= 0:
            start = max(0, idx - 24)
            end = min(len(transcript), idx + 52)
            # Trim to word boundaries so quoted spans never cut mid-word.
            if start > 0:
                space = transcript.find(" ", start, idx)
                if space >= 0:
                    start = space + 1
            if end < len(transcript):
                space = transcript.rfind(" ", idx + len(needle), end)
                if space > idx:
                    end = space
            return transcript[start:end].strip()
    # No needle spoken: no quote. An invented span would fake evidence.
    return ""


def _from_raw(ticket_id: str, role: PartyRole, run: RunView, raw: dict) -> Claim:
    pred = raw.get("predicate") or "unknown"
    return Claim(
        id=raw.get("id") or f"clm_{ticket_id}_{role.value}_{pred}",
        ticket_id=ticket_id,
        source_party=role,
        predicate=pred,
        entity_ids=list(raw.get("entity_ids") or []),
        slot=dict(raw.get("slot") or {}),
        polarity=Polarity(raw.get("polarity") or "asserted"),
        confidence=float(raw.get("confidence") or 0.5),
        evidence_span=raw.get("evidence_span") or span(run.transcript, (pred.replace("_", " "),)),
        call_run_id=run.run_id,
    )


def _bool_polarity(value: object) -> Polarity:
    if value is True:
        return Polarity.asserted
    if value is False:
        return Polarity.denied
    return Polarity.unknown


def _conf(sr: dict, key: str, default: float) -> float:
    try:
        return float(sr[key])
    except (KeyError, TypeError, ValueError):
        return default


def _find_entity(transcript: str) -> str | None:
    if not transcript:
        return None
    for token in transcript.split():
        if token.upper().startswith("PL-"):
            return token.strip(".,")
    return None
