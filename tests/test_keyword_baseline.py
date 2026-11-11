import json

import pytest

from baselines import keyword_baseline, naive_llm_baseline
from baselines.common import load_tickets
from src.schemas import TriageResult

TICKETS = load_tickets()


@pytest.mark.parametrize("ticket", TICKETS, ids=lambda t: t.ticket_id)
def test_keyword_baseline_valid_output(ticket):
    res = keyword_baseline.classify(ticket)
    TriageResult.model_validate(res.model_dump())
    assert res.ticket_id == ticket.ticket_id


def test_keyword_baseline_deterministic():
    a = [keyword_baseline.classify(t).model_dump() for t in TICKETS]
    b = [keyword_baseline.classify(t).model_dump() for t in TICKETS]
    assert a == b


def test_naive_parser_handles_typical_free_text():
    t = TICKETS[0]
    text = ("**Intent:** billing_invoice\n**Priority:** P3\n**Queue:** billing\n"
            "**Escalate:** No - routine invoice correction\n**Missing information:** None\n"
            "**Summary:** Customer billed for 18 seats, has 15.\n**Suggested next action:** Issue credit note.")
    pred, err = naive_llm_baseline.parse_free_text(t, text)
    assert err is None
    r = TriageResult.model_validate(pred)
    assert (r.intent, r.priority, r.queue, r.escalate) == ("billing_invoice", "P3", "billing", False)


def test_naive_parser_reports_unparseable():
    pred, err = naive_llm_baseline.parse_free_text(TICKETS[0], "I think this is about money.")
    assert pred is None and "could not parse" in err


def test_naive_baseline_skips_without_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(naive_llm_baseline, "load_dotenv", lambda *a, **k: None)
    assert naive_llm_baseline.run() == "not_run"
    status = json.loads(naive_llm_baseline.STATUS_PATH.read_text())
    assert status["status"] == "not_run"
