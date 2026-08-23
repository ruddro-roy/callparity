from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class CallTask(BaseModel):
    ticket_id: str
    party_role: str
    to_phones: list[str]
    goal: str
    result_schema: dict[str, Any] = Field(default_factory=dict)
    consent: bool = False


class Plan(BaseModel):
    plan_id: str
    ticket_id: str
    party_role: str
    ready_to_run: bool
    authorized: bool
    goal: str
    result_schema: dict[str, Any] = Field(default_factory=dict)
    to_phones: list[str] = Field(default_factory=list)


class RunRef(BaseModel):
    run_id: str
    plan_id: str


class RunView(BaseModel):
    run_id: str
    status: str
    structured_result: dict[str, Any] = Field(default_factory=dict)
    transcript: str = ""
    summary: str = ""


class CallePort(Protocol):
    def plan(self, task: CallTask) -> Plan: ...
    def run(self, plan: Plan) -> RunRef: ...
    def get(self, run: RunRef) -> RunView: ...
    def ping(self) -> bool: ...
