from __future__ import annotations

from app.fixtures.fr1842 import (
    FR1842_A,
    FR1842_B,
    FR1888_A,
    FR1888_B,
    FR1900_A,
    FR1900_B,
)
from app.ports.calle import CallTask, Plan, RunRef, RunView


class FixtureCalle:
    """Deterministic CALL-E adapter. Covers every CallePort method. Never hits the network."""

    def __init__(self) -> None:
        self._plans: dict[str, Plan] = {}
        self._runs: dict[str, RunView] = {}

    def ping(self) -> bool:
        return True

    def plan(self, task: CallTask) -> Plan:
        if not task.consent:
            return Plan(
                plan_id=f"plan_{task.ticket_id}_{task.party_role}",
                ticket_id=task.ticket_id,
                party_role=task.party_role,
                ready_to_run=False,
                authorized=False,
                goal=task.goal,
                result_schema=task.result_schema,
            )
        plan = Plan(
            plan_id=f"plan_{task.ticket_id}_{task.party_role}",
            ticket_id=task.ticket_id,
            party_role=task.party_role,
            ready_to_run=True,
            authorized=True,
            goal=task.goal,
            result_schema=task.result_schema,
        )
        self._plans[plan.plan_id] = plan
        return plan

    def run(self, plan: Plan) -> RunRef:
        if not plan.ready_to_run or not plan.authorized:
            raise PermissionError("plan is not authorized")
        payload = self._payload(plan.ticket_id, plan.party_role)
        run_id = f"run_{plan.ticket_id}_{plan.party_role}"
        self._runs[run_id] = RunView(
            run_id=run_id,
            status=str(payload.get("status") or "completed"),
            structured_result=payload["structured_result"],
            transcript=payload["transcript"],
            summary=payload["summary"],
        )
        return RunRef(run_id=run_id, plan_id=plan.plan_id)

    def get(self, run: RunRef) -> RunView:
        return self._runs[run.run_id]

    def _payload(self, ticket_id: str, party_role: str) -> dict:
        table = {
            ("FR-1842", "A"): FR1842_A,
            ("FR-1842", "B"): FR1842_B,
            ("FR-1900", "A"): FR1900_A,
            ("FR-1900", "B"): FR1900_B,
            ("FR-1888", "A"): FR1888_A,
            ("FR-1888", "B"): FR1888_B,
        }
        if (ticket_id, party_role) not in table:
            return {
                "structured_result": {"unreachable": True, "disposition": "no_fixture"},
                "transcript": "",
                "summary": "no fixture",
                "status": "unreachable",
            }
        return table[(ticket_id, party_role)]
