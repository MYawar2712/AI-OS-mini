"""The triage pipeline: one InboundTicket in -> one TriageResult + PipelineTrace out.

    validate -> redact -> injection check -> customer lookup -> LLM fact extraction (validated, 1 retry)
             -> deterministic rules -> assemble result   (on LLM failure: safe fallback to human triage)

Never sends anything to customers and never writes anywhere: writing happens only after human review
(see src/pipeline/handoff.py).
"""
from __future__ import annotations

import time
from typing import Callable

from src.llm_client import LLMNotConfigured, LLMResponse, call_llm
from src.pipeline import rules
from src.pipeline.context import lookup_customer
from src.pipeline.injection import detect_injection
from src.pipeline.llm_extract import PROMPT_VERSION, extract_facts
from src.pipeline.redact import redact
from src.schemas import InboundTicket, PipelineTrace, StepTiming, TriageResult
from src.taxonomy import load_settings

PIPELINE_VERSION = f"v0/{PROMPT_VERSION}"


class _Timer:
    def __init__(self, trace: PipelineTrace):
        self.trace = trace

    def step(self, name: str):
        timer = self

        class _Ctx:
            def __enter__(self):
                self.t = time.perf_counter()

            def __exit__(self, *exc):
                timer.trace.steps.append(StepTiming(step=name, ms=round((time.perf_counter() - self.t) * 1000, 2)))
        return _Ctx()


def _fallback(ticket: InboundTicket, trace: PipelineTrace, extra_reasons: list[str]) -> TriageResult:
    """LLM unavailable or invalid twice: produce a VALID result that hands the ticket to a human."""
    reasons = list(dict.fromkeys(["low_confidence", *extra_reasons]))
    return TriageResult(
        ticket_id=ticket.ticket_id, intent="general_inquiry", priority="P3", queue="tier1_general",
        escalate=True, escalation_reasons=reasons,
        missing_info=["account_id"] if not trace.customer_found else [],
        summary="Automatic triage unavailable for this ticket. Human triage required.",
        suggested_next_action="Triage manually; the automatic triage did not produce a valid result.",
        confidence=0.0, rationale="Fallback: " + ("; ".join(trace.llm_errors) or "LLM not available")[:1000])


def triage(ticket: InboundTicket, llm: Callable[..., LLMResponse] = call_llm) -> tuple[TriageResult, PipelineTrace]:
    start = time.perf_counter()
    trace = PipelineTrace(ticket_id=ticket.ticket_id, pipeline_version=PIPELINE_VERSION,
                          model=load_settings()["llm"]["model"], status="ok")
    t = _Timer(trace)

    with t.step("validate"):
        ticket = InboundTicket.model_validate(ticket.model_dump())  # step 1: contract check (raises if invalid)
    with t.step("redact"):
        red_subject, red_body = redact(ticket.subject), redact(ticket.body)
        trace.redactions = sorted(set(red_subject.kinds + red_body.kinds))
    with t.step("injection_check"):
        trace.injection_matches = detect_injection(ticket.subject + "\n" + ticket.body)
    with t.step("customer_lookup"):
        customer = lookup_customer(ticket.customer_id)
        trace.customer_found = customer is not None

    with t.step("llm_extract"):
        try:
            ex = extract_facts(red_subject.text, red_body.text, ticket.channel, llm=llm)
        except LLMNotConfigured as e:
            ex = None
            trace.llm_errors.append(str(e))
    if ex is not None:
        trace.llm_attempts, trace.input_tokens, trace.output_tokens = ex.attempts, ex.input_tokens, ex.output_tokens
        trace.llm_errors += ex.errors

    if ex is None or ex.facts is None:
        trace.status = "fallback"
        extra = (["missing_account_id"] if customer is None else []) \
            + (["prompt_injection_suspected"] if trace.injection_matches else []) \
            + (["sensitive_data_present"] if trace.redactions else [])
        result = _fallback(ticket, trace, extra)
        trace.rules_fired.append("FALLBACK")
        trace.total_ms = round((time.perf_counter() - start) * 1000, 2)
        return result, trace

    f = trace.facts = ex.facts
    fired = trace.rules_fired
    with t.step("rules"):
        intent, secondary = rules.adjust_intent(f, fired)
        prio = rules.priority(f, intent, customer, fired)
        queue = rules.queue_for(intent)
        fired.append("R-Q")
        reasons = rules.escalation(f, intent, secondary, prio, customer=customer,
                                   injection_matches=trace.injection_matches, redactions=trace.redactions,
                                   text=ticket.subject + "\n" + ticket.body, fired=fired)
        missing = rules.missing_info(f, customer=customer, text=ticket.body, attachments=ticket.attachments, fired=fired)
        action = rules.safe_action(f.suggested_next_action, queue, fired)

    with t.step("assemble"):
        # Defence in depth: re-redact model text in case it echoed a secret.
        result = TriageResult(
            ticket_id=ticket.ticket_id, intent=intent, secondary_intent=secondary, priority=prio, queue=queue,
            escalate=bool(reasons), escalation_reasons=reasons, missing_info=missing,
            summary=redact(f.summary).text[:800], suggested_next_action=redact(action).text[:500],
            confidence=f.confidence, rationale=redact(f.rationale).text[:1200])
    trace.total_ms = round((time.perf_counter() - start) * 1000, 2)
    return result, trace
