from __future__ import annotations

from app.models.schemas import ActionCard, ActionKind, Claim, EdgeStatus, GraphEdge, Polarity


def _a_claim(claims_a: list[Claim], predicate: str) -> Claim | None:
    for c in claims_a:
        if c.predicate == predicate:
            return c
    return None


def merge_graph(ticket_id: str, claims_a: list[Claim], claims_b: list[Claim]) -> tuple[list[GraphEdge], ActionCard]:
    edges: list[GraphEdge] = []
    b_by_pred = {c.predicate: c for c in claims_b}
    saw = next((c for c in claims_b if c.predicate == "pallet_visible_to_driver"), None)

    for claim in claims_a:
        if claim.confidence < 0.45:
            edges.append(
                GraphEdge(
                    hypothesis_id=claim.id,
                    status=EdgeStatus.ABSTAIN,
                    a_span=claim.evidence_span,
                    b_span="",
                    predicate=claim.predicate,
                )
            )
            continue

        if claim.predicate == "pallet_staged":
            contradicted = False
            b_span = ""
            if saw and saw.polarity == Polarity.denied:
                contradicted = True
                b_span = saw.evidence_span
            if saw and saw.slot.get("dock_3_state") == "empty" and (claim.slot or {}).get("dock") == "3":
                contradicted = True
                b_span = saw.evidence_span
            if contradicted:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.CONTRADICTED,
                        a_span=claim.evidence_span,
                        b_span=b_span,
                        action=ActionKind.RESTAGE_AND_RECALL,
                        predicate=claim.predicate,
                    )
                )
            elif saw and saw.polarity == Polarity.asserted:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.CONFIRMED,
                        a_span=claim.evidence_span,
                        b_span=saw.evidence_span,
                        action=ActionKind.RELEASE_TRUCK,
                        predicate=claim.predicate,
                    )
                )
            elif not claims_b:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.UNREACHABLE,
                        a_span=claim.evidence_span,
                        predicate=claim.predicate,
                        action=ActionKind.HOLD_FOR_HUMAN,
                    )
                )
            else:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.UNTESTED,
                        a_span=claim.evidence_span,
                        predicate=claim.predicate,
                    )
                )
            continue

        if claim.predicate == "driver_arrived":
            b = b_by_pred.get("driver_arrived")
            if b and b.polarity == Polarity.asserted:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.CONFIRMED,
                        a_span=claim.evidence_span,
                        b_span=b.evidence_span,
                        predicate=claim.predicate,
                    )
                )
            elif not claims_b:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.UNREACHABLE,
                        a_span=claim.evidence_span,
                        predicate=claim.predicate,
                        action=ActionKind.HOLD_FOR_HUMAN,
                    )
                )
            else:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.UNTESTED,
                        a_span=claim.evidence_span,
                        predicate=claim.predicate,
                    )
                )
            continue

        if claim.predicate == "seal_recorded":
            b = b_by_pred.get("seal_recorded")
            if claim.polarity == Polarity.unknown and (not b or b.polarity == Polarity.unknown):
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.UNTESTED,
                        a_span=claim.evidence_span,
                        b_span=b.evidence_span if b else "",
                        predicate=claim.predicate,
                    )
                )
            elif b and claim.slot.get("seal") and claim.slot.get("seal") == b.slot.get("seal"):
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.CONFIRMED,
                        a_span=claim.evidence_span,
                        b_span=b.evidence_span,
                        predicate=claim.predicate,
                    )
                )
            else:
                edges.append(
                    GraphEdge(
                        hypothesis_id=claim.id,
                        status=EdgeStatus.UNTESTED,
                        a_span=claim.evidence_span,
                        predicate=claim.predicate,
                    )
                )
            continue

        if not claims_b:
            edges.append(
                GraphEdge(
                    hypothesis_id=claim.id,
                    status=EdgeStatus.UNREACHABLE,
                    a_span=claim.evidence_span,
                    predicate=claim.predicate,
                    action=ActionKind.HOLD_FOR_HUMAN,
                )
            )
        else:
            edges.append(
                GraphEdge(
                    hypothesis_id=claim.id,
                    status=EdgeStatus.UNTESTED,
                    a_span=claim.evidence_span,
                    predicate=claim.predicate,
                )
            )

    action = _choose_action(edges)
    card = ActionCard(
        action=action,
        ticket_id=ticket_id,
        rationale=_rationale(action, edges),
        edges=edges,
    )
    return edges, card


def _choose_action(edges: list[GraphEdge]) -> ActionKind:
    if any(e.status == EdgeStatus.UNREACHABLE for e in edges):
        return ActionKind.HOLD_FOR_HUMAN
    if any(e.status == EdgeStatus.CONTRADICTED and e.predicate == "pallet_staged" for e in edges):
        return ActionKind.RESTAGE_AND_RECALL
    if any(e.status == EdgeStatus.CONFIRMED and e.predicate == "pallet_staged" for e in edges):
        return ActionKind.RELEASE_TRUCK
    return ActionKind.HOLD_FOR_HUMAN


def _rationale(action: ActionKind, edges: list[GraphEdge]) -> str:
    if action == ActionKind.RESTAGE_AND_RECALL:
        return (
            "Warehouse and driver disagree on pallet_staged. Restage PL-9F21 and recall the driver to the door."
        )
    if action == ActionKind.RELEASE_TRUCK:
        return "Both parties confirm the pallet is staged. Release the truck."
    return (
        "Insufficient or unreachable evidence. Hold for a human dispatcher. "
        "CallParity does not place commitments; a human owns this card."
    )
