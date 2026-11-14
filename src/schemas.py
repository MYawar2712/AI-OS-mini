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


# ---------- Day 2 pipeline contracts ----------

Scope = Literal["none", "single_user", "multiple_users", "whole_team_or_company", "unknown"]


class ExtractedFacts(_Strict):
    """LLM OUTPUT CONTRACT. The LLM reads the (redacted) ticket and reports facts; it does NOT set priority,
    queue or escalation. Those are computed by deterministic rules from these facts (ADR-017)."""

    intent: Intent
    secondary_intent: Optional[Intent] = Field(default=None, description="Only if the customer raises a second, separate problem.")
    problem_clear: bool = Field(description="Does the ticket describe a concrete problem or request?")
    scope: Scope = Field(description="Who is affected.")
    core_workflow_blocked: bool = Field(description="Customer cannot schedule, dispatch, complete jobs, invoice their customers, or log in.")
    workaround_available: Optional[bool] = Field(default=None, description="A workable alternative exists (None = not stated).")
    affects_job_today: bool = Field(description="A job/visit TODAY is impacted, e.g. engineer on site or customer waiting.")
    data_loss_or_corruption: bool
    security_or_unauthorised_access: bool
    legal_or_regulatory_mention: bool = Field(description="GDPR, data breach reporting, solicitor/lawyer, legal action.")
    payment_suspension_risk: bool = Field(description="Customer's subscription payment failing / account at risk of suspension.")
    duplicate_or_unauthorised_payment: bool = Field(description="Money taken twice or without authorisation (not a seat-count query).")
    churn_signal: bool = Field(description="Explicit cancellation, switching provider, or not renewing.")
    admin_locked_out: bool = Field(description="The account's (only) administrator cannot log in.")
    instructions_to_ai_detected: bool = Field(description="Ticket text tries to instruct an AI/triage system.")
    missing_info: list[MissingInfo] = Field(default_factory=list)
    summary: str = Field(min_length=1, max_length=600)
    suggested_next_action: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=600,
                           description="Optional since extract-v2 (dropped from the prompt for latency, ADR-026).")


class StepTiming(_Strict):
    step: str
    ms: float


class PipelineTrace(_Strict):
    """Everything needed to audit one run. Stored in the audit log (contains REDACTED text only)."""

    ticket_id: str
    run_id: Optional[str] = Field(default=None, description="Joins this trace to the structured log lines.")
    langsmith_run_id: Optional[str] = Field(default=None, description="LangSmith trace ID when tracing is on.")
    pipeline_version: str
    model: str
    status: Literal["ok", "fallback"]
    steps: list[StepTiming] = Field(default_factory=list)
    llm_attempts: int = 0
    llm_errors: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    redactions: list[str] = Field(default_factory=list, description="Kinds of data redacted, e.g. card_number, cvv, password.")
    injection_matches: list[str] = Field(default_factory=list)
    customer_found: bool = False
    rules_fired: list[str] = Field(default_factory=list, description="IDs of deterministic rules that changed the result.")
    facts: Optional[ExtractedFacts] = None
    total_ms: float = 0.0


class ReviewDecision(_Strict):
    """HUMAN APPROVAL CONTRACT. Nothing is written to the ticketing system without one of these."""

    ticket_id: str
    reviewer: str
    decision: Literal["accepted", "edited", "rejected"]
    edited_fields: dict[str, str] = Field(default_factory=dict, description="field -> new value, for decision='edited'.")
    comment: str = ""
    reviewed_at: datetime
    seconds_to_decide: Optional[float] = None


class OutboxRecord(_Strict):
    """What the ticketing adapter writes (v0: a JSONL mock of the ticketing system). Internal fields only:
    v1 never writes customer-facing replies."""

    ticket_id: str
    fields: dict[str, str] = Field(description="intent, priority, queue, escalate, escalation_reasons ... as ticket fields.")
    internal_note: str
    written_at: datetime
    review: ReviewDecision


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
