"""Input/output contracts for the Help Desk Triage Agent.

Enums are hard-coded as Literals (so they appear in the exported JSON Schema and IDEs),
and tests/test_taxonomy_consistency.py asserts they match config/taxonomy.yaml exactly.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intent = Literal[
    "technical_issue",
    "mobile_app_sync",
    "billing_invoice",
    "payment_failure",
    "scheduling_dispatch",
    "account_access",
    "data_import_export",
    "feature_request",
    "cancellation_churn_risk",
    "general_inquiry",
    "out_of_scope",
]
Priority = Literal["P1", "P2", "P3", "P4"]
Queue = Literal[
    "tier1_general",
    "tier2_technical",
    "billing",
    "customer_success_retention",
    "onboarding_data",
    "product",
]
EscalationReason = Literal[
    "low_confidence",
    "churn_risk",
    "legal_or_security",
    "p1_incident",
    "conflicting_intents",
    "missing_account_id",
    "prompt_injection_suspected",
    "sensitive_data_present",
]
MissingInfo = Literal[
    "account_id",
    "affected_users_count",
    "device_and_app_version",
    "error_message_or_screenshot",
    "invoice_number",
    "job_or_visit_reference",
    "file_sample",
    "steps_to_reproduce",
    "clear_problem_description",
]
Channel = Literal["email", "portal", "chat", "phone_note"]

PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InboundTicket(_Strict):
    """What the triage system receives. Mirrors a ticketing-system webhook payload."""

    ticket_id: str = Field(pattern=r"^[A-Z0-9-]+$")
    received_at: datetime
    channel: Channel
    from_name: str
    from_email: Optional[str] = None
    subject: str
    body: str = Field(min_length=1)
    customer_id: Optional[str] = Field(default=None, description="None when the sender could not be matched to an account.")
    attachments: list[str] = Field(default_factory=list)
    synthetic: bool = Field(default=True, description="Always true in this repo: no production data is used.")


class TriageResult(_Strict):
    """What the triage system must return. Validated before anything is written to the ticketing system."""

    ticket_id: str
    intent: Intent
    secondary_intent: Optional[Intent] = None
    priority: Priority
    queue: Queue
    escalate: bool
    escalation_reasons: list[EscalationReason] = Field(default_factory=list)
    missing_info: list[MissingInfo] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=800)
    suggested_next_action: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def _consistency(self) -> "TriageResult":
        if self.escalate and not self.escalation_reasons:
            raise ValueError("escalate=true requires at least one escalation_reason")
        if not self.escalate and self.escalation_reasons:
            raise ValueError("escalation_reasons given but escalate=false")
        if self.secondary_intent is not None and self.secondary_intent == self.intent:
            raise ValueError("secondary_intent must differ from intent")
        return self


# ---------- Evaluation contracts ----------


class MustNot(_Strict):
    """Hard constraints. Any violation fails the case regardless of other fields."""

    priority_in: list[Priority] = Field(default_factory=list)
    queue_in: list[Queue] = Field(default_factory=list)
    escalate_false: bool = False
    phrases_in_summary: list[str] = Field(default_factory=list, description="Case-insensitive substrings forbidden in summary/rationale.")
    phrases_in_action: list[str] = Field(default_factory=list, description="Case-insensitive substrings forbidden in suggested_next_action.")


class ExpectedBehavior(_Strict):
    intent: Intent
    acceptable_intents: list[Intent] = Field(default_factory=list, description="Alternative primary intents also scored correct.")
    acceptable_secondary_intents: list[Intent] = Field(default_factory=list)
    priority: Priority
    queue: Queue
    acceptable_queues: list[Queue] = Field(default_factory=list)
    escalate: bool
    required_escalation_reasons: list[EscalationReason] = Field(default_factory=list)
    required_missing_info: list[MissingInfo] = Field(default_factory=list)
    must_not: MustNot = Field(default_factory=MustNot)

    @model_validator(mode="after")
    def _consistency(self) -> "ExpectedBehavior":
        if self.escalate != bool(self.required_escalation_reasons):
            raise ValueError("escalate must be true iff required_escalation_reasons is non-empty")
        if self.priority == "P1" and "p1_incident" not in self.required_escalation_reasons:
            raise ValueError("P1 expectations must require p1_incident escalation")
        return self


class TestCase(_Strict):
    __test__ = False  # stop pytest trying to collect this class

    id: str = Field(pattern=r"^TC\d{2}$")
    category: Literal["representative", "edge", "failure"]
    title: str
    risk_tested: str
    tags: list[str] = Field(default_factory=list)
    ticket: InboundTicket
    expected: ExpectedBehavior

    @field_validator("ticket")
    @classmethod
    def _synthetic_only(cls, v: InboundTicket) -> InboundTicket:
        if not v.synthetic:
            raise ValueError("test cases must be synthetic")
        return v


def load_test_cases(path: str | Path = "eval/test_cases.jsonl") -> list[TestCase]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [TestCase.model_validate_json(line) for line in lines if line.strip()]


def export_json_schemas(out_dir: str | Path = "schemas") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in {
        "inbound_ticket": InboundTicket,
        "triage_result": TriageResult,
        "test_case": TestCase,
    }.items():
        p = out / f"{name}.schema.json"
        p.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        written.append(p)
    return written
