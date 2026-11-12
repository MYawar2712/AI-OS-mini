"""Pipeline tests with a FAKE LLM (no network, no cost): safety steps, rules, retry, fallback, handoff."""
import json
from datetime import datetime, timezone

import pytest

from src.llm_client import LLMCallError, LLMResponse
from src.pipeline import handoff, rules
from src.pipeline.injection import detect_injection
from src.pipeline.redact import redact
from src.pipeline.run import triage
from src.schemas import ExtractedFacts, ReviewDecision, TriageResult, load_test_cases
from src.taxonomy import ROOT

ALL = load_test_cases(ROOT / "eval/test_cases.jsonl") + load_test_cases(ROOT / "eval/test_cases_holdout.jsonl")
BY_ID = {c.id: c for c in ALL}


def facts(**over) -> dict:
    base = dict(intent="billing_invoice", secondary_intent=None, problem_clear=True, scope="single_user",
                core_workflow_blocked=False, workaround_available=None, affects_job_today=False,
                data_loss_or_corruption=False, security_or_unauthorised_access=False, legal_or_regulatory_mention=False,
                payment_suspension_risk=False, duplicate_or_unauthorised_payment=False, churn_signal=False,
                admin_locked_out=False, instructions_to_ai_detected=False, missing_info=[],
                summary="Customer asks about invoice.", suggested_next_action="Route to billing.", confidence=0.9,
                rationale="Invoice question.")
    base.update(over)
    return base


def fake_llm(*responses):
    """Returns each response in turn (a dict -> JSON text, a str -> raw text, an Exception -> raised)."""
    calls = list(responses)

    def _llm(prompt, system=None, **kw):
        _llm.prompts.append(prompt)
        r = calls.pop(0)
        if isinstance(r, Exception):
            raise r
        text = json.dumps(r) if isinstance(r, dict) else r
        return LLMResponse(text=text, input_tokens=100, output_tokens=50, latency_ms=1.0, model="fake")
    _llm.prompts = []
    return _llm


# ---------- redaction ----------

def test_redacts_card_cvv_expiry():
    r = redact("card 4111 1111 1111 1111 exp 09/28 cvv 123 name S Hart")
    assert "4111" not in r.text and "123" not in r.text and "09/28" not in r.text
    assert set(r.kinds) == {"card_number", "cvv", "card_expiry"}


def test_does_not_redact_non_luhn_numbers():
    r = redact("Job JL-55812, invoice INV-20931, call 0113 496 0000, 3,000 assets")
    assert r.kinds == [] and r.text.startswith("Job JL-55812")


def test_redacts_password():
    r = redact("username jo@x.example password is Summer2026! - can you check")
    assert "Summer2026!" not in r.text and r.kinds == ["password"]


# ---------- injection ----------

def test_injection_detector_flags_exactly_the_injection_cases():
    flagged = {c.id for c in ALL if detect_injection(c.ticket.subject + "\n" + c.ticket.body)}
    assert flagged == {c.id for c in ALL if "injection" in c.tags}


# ---------- rules ----------

def _prio(customer=None, **over):
    f = ExtractedFacts.model_validate(facts(**over))
    intent, _ = rules.adjust_intent(f, [])
    return rules.priority(f, intent, customer, [])


@pytest.mark.parametrize("over,expected", [
    ({"data_loss_or_corruption": True}, "P1"),
    ({"security_or_unauthorised_access": True}, "P1"),
    ({"core_workflow_blocked": True, "scope": "whole_team_or_company", "workaround_available": False}, "P1"),
    ({"core_workflow_blocked": True, "scope": "whole_team_or_company", "workaround_available": True}, "P2"),
    ({"core_workflow_blocked": True, "scope": "single_user"}, "P2"),
    ({"affects_job_today": True}, "P2"),
    ({"admin_locked_out": True}, "P2"),
    ({"churn_signal": True}, "P2"),
    ({}, "P3"),
    ({"intent": "feature_request"}, "P4"),
    ({"intent": "general_inquiry", "problem_clear": False}, "P3"),  # T2: unclear never below P3
])
def test_priority_rules(over, expected):
    assert _prio(**over) == expected


def test_m1_enterprise_raises_technical_p3():
    assert _prio({"plan_tier": "enterprise"}, intent="technical_issue") == "P2"
    assert _prio({"plan_tier": "starter"}, intent="technical_issue") == "P3"


def test_t4_churn_becomes_primary():
    f = ExtractedFacts.model_validate(facts(intent="technical_issue", churn_signal=True))
    assert rules.adjust_intent(f, []) == ("cancellation_churn_risk", "technical_issue")


@pytest.mark.parametrize("action,blocked", [
    ("Approve the refund of £2,400.", True),
    ("Offer a 20% discount to keep them.", True),
    ("Do not approve any refund until billing verifies.", False),
    ("Route to billing for VAT review.", False),
])
def test_safe_action_blocks_financial_promises(action, blocked):
    out = rules.safe_action(action, "billing", fired := [])
    assert (out != action) is blocked and ("R-ACT" in fired) is blocked


# ---------- pipeline (fake LLM) ----------

def test_happy_path_valid_result_and_trace():
    llm = fake_llm(facts())
    r, tr = triage(BY_ID["TC01"].ticket, llm=llm)
    assert isinstance(r, TriageResult) and tr.status == "ok" and tr.llm_attempts == 1
    assert (r.intent, r.priority, r.queue, r.escalate) == ("billing_invoice", "P3", "billing", False)
    assert [s.step for s in tr.steps] == ["validate", "redact", "injection_check", "customer_lookup", "llm_extract", "rules", "assemble"]


def test_llm_cannot_lower_safety_priority_or_skip_escalation():
    """Even if the model under-reports, deterministic detectors still escalate the injection case."""
    llm = fake_llm(facts(instructions_to_ai_detected=False))
    r, tr = triage(BY_ID["TC10"].ticket, llm=llm)
    assert r.escalate and "prompt_injection_suspected" in r.escalation_reasons and tr.injection_matches


def test_secrets_never_reach_the_llm_and_are_flagged():
    llm = fake_llm(facts(intent="payment_failure", payment_suspension_risk=True))
    r, tr = triage(BY_ID["TC11"].ticket, llm=llm)
    assert "4111" not in llm.prompts[0] and "cvv 123" not in llm.prompts[0].lower()
    assert {"sensitive_data_present", "missing_account_id"} <= set(r.escalation_reasons) and "account_id" in r.missing_info


def test_model_echoing_a_secret_is_re_redacted():
    llm = fake_llm(facts(summary="Card 4111 1111 1111 1111 declined."))
    r, _ = triage(BY_ID["TC11"].ticket, llm=llm)
    assert "4111" not in r.summary


def test_invalid_json_then_valid_retries_once():
    llm = fake_llm("not json at all", facts())
    r, tr = triage(BY_ID["TC01"].ticket, llm=llm)
    assert tr.status == "ok" and tr.llm_attempts == 2 and len(tr.llm_errors) == 1
    assert "previous answer was invalid" in llm.prompts[1]


@pytest.mark.parametrize("responses", [
    ("nope", "still nope"),
    (facts(intent="refund_request"), facts(priority="P1")),
    (LLMCallError("timeout"), LLMCallError("timeout")),
])
def test_two_failures_fall_back_to_valid_human_triage(responses):
    r, tr = triage(BY_ID["TC11"].ticket, llm=fake_llm(*responses))
    assert tr.status == "fallback" and r.escalate and "low_confidence" in r.escalation_reasons
    assert {"missing_account_id", "sensitive_data_present"} <= set(r.escalation_reasons)
    TriageResult.model_validate(r.model_dump())


# ---------- handoff / human approval ----------

def _review(decision, **kw):
    return ReviewDecision(ticket_id="SYN-24101", reviewer="t", decision=decision, reviewed_at=datetime.now(timezone.utc), **kw)


def test_accept_writes_outbox_and_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "runs_dir", lambda: tmp_path)
    r, tr = triage(BY_ID["TC01"].ticket, llm=fake_llm(facts()))
    final, outbox = handoff.record(r, tr, _review("accepted"))
    assert outbox and outbox.fields["queue"] == "billing"
    assert (tmp_path / "ticketing_outbox.jsonl").exists() and (tmp_path / "audit.jsonl").exists()


def test_reject_writes_audit_only(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "runs_dir", lambda: tmp_path)
    r, tr = triage(BY_ID["TC01"].ticket, llm=fake_llm(facts()))
    _, outbox = handoff.record(r, tr, _review("rejected", comment="wrong"))
    assert outbox is None and not (tmp_path / "ticketing_outbox.jsonl").exists() and (tmp_path / "audit.jsonl").exists()


def test_edits_are_validated_against_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "runs_dir", lambda: tmp_path)
    r, tr = triage(BY_ID["TC01"].ticket, llm=fake_llm(facts()))
    final, _ = handoff.record(r, tr, _review("edited", edited_fields={"priority": "P2", "escalate": "yes"}))
    assert final.priority == "P2" and final.escalate and final.escalation_reasons
    with pytest.raises(Exception):
        handoff.apply_edits(r, {"priority": "P9"})
    with pytest.raises(ValueError):
        handoff.apply_edits(r, {"summary": "x"})
