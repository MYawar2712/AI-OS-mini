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
from src.observability import log_event, new_run_id, trace_run
from src.pipeline import rules
from src.pipeline.context import lookup_customer
from src.pipeline.injection import detect_injection
from src.pipeline.llm_extract import PROMPT_VERSION, extract_facts
from src.pipeline.redact import redact
from src.schemas import InboundTicket, PipelineTrace, StepTiming, TriageResult
from src.taxonomy import load_settings

PIPELINE_VERSION = f"v1/{PROMPT_VERSION}"  # v1 = Day 4 hardening (R-C1, key aliases, token redaction, fail-high fallback)


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
        # P2, not P3 (Day 4): when the assistant cannot read a ticket its urgency is unknown, so fail high.
        ticket_id=ticket.ticket_id, intent="general_inquiry", priority="P2", queue="tier1_general",
        escalate=True, escalation_reasons=reasons,
        missing_info=["account_id"] if not trace.customer_found else [],
        summary="Automatic triage unavailable for this ticket. Human triage required.",
        suggested_next_action="Triage manually; the automatic triage did not produce a valid result.",
        confidence=0.0, rationale="Fallback: " + ("; ".join(trace.llm_errors) or "LLM not available")[:1000])


def triage(ticket: InboundTicket, llm: Callable[..., LLMResponse] = call_llm,
           tags: list[str] | None = None) -> tuple[TriageResult, PipelineTrace]:
    """Run the pipeline. When LangSmith tracing is on, the run is traced with REDACTED text only."""
    inputs = {"ticket_id": ticket.ticket_id, "channel": ticket.channel, "subject": redact(ticket.subject).text,
              "body": redact(ticket.body).text, "customer_known": ticket.customer_id is not None}
    with trace_run("triage", inputs=inputs, tags=[PIPELINE_VERSION, *(tags or [])],
                   metadata={"pipeline_version": PIPELINE_VERSION, "synthetic": True}) as run:
        result, trace = _triage(ticket, llm)
        trace.langsmith_run_id = str(run.id) if run.id else None
        run.end(outputs={"result": result.model_dump(), "status": trace.status, "rules_fired": trace.rules_fired,
                         "redactions": trace.redactions, "injection_matches": trace.injection_matches,
                         "llm_attempts": trace.llm_attempts, "llm_errors": trace.llm_errors})
    return result, trace


def _triage(ticket: InboundTicket, llm: Callable[..., LLMResponse]) -> tuple[TriageResult, PipelineTrace]:
    start = time.perf_counter()
    trace = PipelineTrace(ticket_id=ticket.ticket_id, run_id=new_run_id(), pipeline_version=PIPELINE_VERSION,
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
        if ex.repairs:
            log_event("llm_output_repaired", run_id=trace.run_id, ticket_id=ticket.ticket_id, repairs=ex.repairs)

    if ex is None or ex.facts is None:
        trace.status = "fallback"
        extra = (["missing_account_id"] if customer is None else []) \
            + (["prompt_injection_suspected"] if trace.injection_matches else []) \
            + (["sensitive_data_present"] if trace.redactions else [])
        result = _fallback(ticket, trace, extra)
        trace.rules_fired.append("FALLBACK")
        trace.total_ms = round((time.perf_counter() - start) * 1000, 2)
        _log(trace, result)
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
            confidence=f.confidence,
            rationale=(redact(f.rationale).text if f.rationale.strip() else _rules_rationale(intent, prio, fired))[:1200])
    trace.total_ms = round((time.perf_counter() - start) * 1000, 2)
    _log(trace, result)
    return result, trace


def _rules_rationale(intent: str, prio: str, fired: list[str]) -> str:
    """extract-v2 asks the model for facts only; the explanation is which rules decided the result."""
    return f"Intent {intent} read by the assistant; {prio} and routing set by rules: {', '.join(fired) or 'defaults'}."


def _log(trace: PipelineTrace, result: TriageResult) -> None:
    log_event("triage", level="warning" if trace.status == "fallback" else "info", run_id=trace.run_id,
              ticket_id=trace.ticket_id, status=trace.status, priority=result.priority, queue=result.queue,
              escalate=result.escalate, total_ms=trace.total_ms, llm_attempts=trace.llm_attempts,
              llm_errors=trace.llm_errors, tokens_in=trace.input_tokens, tokens_out=trace.output_tokens,
              redactions=trace.redactions, injection=bool(trace.injection_matches), model=trace.model)
