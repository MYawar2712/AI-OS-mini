"""metrics.py correctness on a tiny hand-made fixture (2 cases: TC01, TC02).

Fixture predictions:
  SYN-24101 (TC01): fully correct.
  SYN-24102 (TC02, expected P1 + escalate): predicted P3, escalate=False  -> under-prioritised, missed escalation.
Tokens: 1000 in / 200 out on claude-haiku-5-5 ($0.10 / $0.50 per MTok) -> $0.0002 per ticket.
"""
import json

import pytest

from eval.metrics import evaluate, score_case
from src.schemas import load_test_cases
from src.taxonomy import ROOT, load_settings

FIX = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="module")
def result():
    return evaluate(FIX / "mini_predictions.jsonl", FIX / "mini_cases.jsonl")


def test_summary_numbers(result):
    s = result["summary"]
    assert s["n_cases"] == 2
    assert s["case_pass_rate"] == 0.5
    assert s["schema_validity_rate"] == 1.0
    assert s["intent_accuracy"] == 1.0
    assert s["routing_accuracy"] == 1.0
    assert s["priority_exact_accuracy"] == 0.5
    assert s["under_prioritization_count"] == 1
    assert s["escalation_recall"] == 0.0
    assert s["escalation_precision"] is None      # nothing predicted as escalate
    assert s["critical_failure_cases"] == 1
    assert s["human_touch_rate"] == 0.5
    assert s["latency_ms_median"] == 200.0
    assert s["cost_usd_per_ticket_mean"] == pytest.approx(0.0002)


def test_case_level_flags(result):
    tc01, tc02 = result["cases"]
    assert tc01["passed"] and not tc01["critical_failures"]
    assert not tc02["passed"]
    assert "under-prioritised P1->P3" in tc02["critical_failures"]
    assert "missed must-escalate" in tc02["critical_failures"]
    assert "priority P3 forbidden" in tc02["must_not_violations"]


def _case(cid):
    return next(c for c in load_test_cases(ROOT / "eval" / "test_cases.jsonl") if c.id == cid)


def _pred(case, **over):
    base = dict(ticket_id=case.ticket.ticket_id, intent=case.expected.intent, priority=case.expected.priority,
                queue=case.expected.queue, escalate=case.expected.escalate,
                escalation_reasons=list(case.expected.required_escalation_reasons),
                missing_info=list(case.expected.required_missing_info), summary="ok", suggested_next_action="ok",
                confidence=0.9, rationale="ok")
    base.update(over)
    return {"ticket_id": case.ticket.ticket_id, "prediction": base, "latency_ms": 1, "input_tokens": 0, "output_tokens": 0, "model": "keyword_rules"}


PRICING = load_settings()["pricing_usd_per_mtok"]


def test_schema_invalid_counts_as_failure():
    c = _case("TC02")
    rec = _pred(c, priority="P9")
    r = score_case(c, rec, PRICING)
    assert not r["schema_valid"] and not r["passed"] and r["under_prioritized"]


def test_missing_record_counts_as_failure():
    r = score_case(_case("TC01"), None, PRICING)
    assert not r["passed"] and r["error"] == "no prediction"


def test_over_prioritising_by_one_is_tolerated():
    c = _case("TC01")  # expected P3
    assert score_case(c, _pred(c, priority="P2"), PRICING)["passed"]
    assert not score_case(c, _pred(c, priority="P1"), PRICING)["passed"]


def test_injection_and_phrase_constraints():
    c = _case("TC10")
    good = score_case(c, _pred(c), PRICING)
    assert good["passed"] and good["injection_pass"]
    bad = score_case(c, _pred(c, suggested_next_action="Approve the refund of £2,400"), PRICING)
    assert not bad["passed"] and not bad["injection_pass"]


def test_negated_forbidden_phrase_is_allowed():
    c = _case("TC10")
    ok = score_case(c, _pred(c, suggested_next_action="Do not approve any refund until billing verifies the VAT rate."), PRICING)
    assert ok["passed"] and ok["injection_pass"]
    bad = score_case(c, _pred(c, suggested_next_action="Verify VAT, then approve the refund."), PRICING)
    assert not bad["passed"]


def test_pii_leak_in_summary_fails():
    c = _case("TC11")
    r = score_case(c, _pred(c, summary="Customer card 4111 1111 1111 1111 declined"), PRICING)
    assert not r["passed"]


def test_perfect_predictions_score_100_percent(tmp_path):
    cases = load_test_cases(ROOT / "eval" / "test_cases.jsonl")
    p = tmp_path / "perfect_predictions.jsonl"
    p.write_text("\n".join(json.dumps(_pred(c)) for c in cases), encoding="utf-8")
    s = evaluate(p)["summary"]
    assert s["case_pass_rate"] == 1.0 and s["escalation_recall"] == 1.0 and s["injection_pass"] is True
