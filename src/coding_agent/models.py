from __future__ import annotations
from enum import StrEnum
from pathlib import Path
from pydantic import BaseModel, Field

class PlanStep(BaseModel):
    id: str
    description: str
    target_files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)

class Plan(BaseModel):
    summary: str
    in_scope: bool = True
    scope_reason: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    test_command: str = "pytest -q"

class CommandResult(BaseModel):
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False

class VerificationReport(BaseModel):
    passed: bool
    commands: list[CommandResult]
    failure_signature: str = ""

class RunStatus(StrEnum):
    REVIEW_READY = "review_ready"
    ESCALATED = "escalated"
    REJECTED = "rejected"

class RunReport(BaseModel):
    run_id: str
    status: RunStatus
    confidence: float = Field(ge=0, le=1)
    plan: Plan
    patch: str = ""
    attempts: int
    verification: VerificationReport | None = None
    escalation_reason: str = ""
    repo: Path
