"""UI tests for the Streamlit review app (Streamlit AppTest, fake pipeline: no browser, no network)."""
import json
from unittest import mock

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from src.llm_client import LLMResponse  # noqa: E402
from src.pipeline import handoff  # noqa: E402
from src.pipeline.run import triage as real_triage  # noqa: E402
from src.taxonomy import ROOT  # noqa: E402

APP = str(ROOT / "app" / "review.py")


def _facts(**over):
    base = dict(intent="mobile_app_sync", secondary_intent=None, problem_clear=True, scope="whole_team_or_company",
                core_workflow_blocked=True, workaround_available=False, affects_job_today=True,
                data_loss_or_corruption=False, security_or_unauthorised_access=False, legal_or_regulatory_mention=False,
                payment_suspension_risk=False, duplicate_or_unauthorised_payment=False, churn_signal=False,
                admin_locked_out=False, instructions_to_ai_detected=False, missing_info=["device_and_app_version"],
                summary="Engineers cannot see today's jobs.", suggested_next_action="Escalate to Tier-2.",
                confidence=0.9, rationale="Whole team blocked.")
    base.update(over)
    return base


def fake_triage(ticket, llm=None):
    def _llm(*a, **k):
        return LLMResponse(text=json.dumps(_facts()), input_tokens=10, output_tokens=5, latency_ms=1, model="fake")
    return real_triage(ticket, llm=_llm)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "runs_dir", lambda: tmp_path)
    with mock.patch("src.pipeline.run.triage", side_effect=fake_triage):
        yield AppTest.from_file(APP, default_timeout=30)


def _button(at, key):
    return next(b for b in at.button if b.key == key)


def test_loads_with_four_tabs_and_full_inbox(app):
    at = app.run()
    assert not at.exception
    assert len(at.tabs) == 4
    assert len(at.radio[0].options) == 24  # 12 dev + 12 held-out demo tickets


def test_triage_shows_card_with_escalation(app):
    at = app.run()
    _button(at, "triage").click().run()
    assert not at.exception
    assert any("Needs a lead" in e.value for e in at.error)
    assert {"accept", "edit", "reject"} <= {b.key for b in at.button}


def test_accept_writes_outbox_and_audit(app, tmp_path):
    at = app.run()
    _button(at, "triage").click().run()
    _button(at, "accept").click().run()
    assert not at.exception
    assert (tmp_path / "ticketing_outbox.jsonl").exists() and (tmp_path / "audit.jsonl").exists()
    assert any("Saved ticket" in s.value for s in at.success)


def test_reject_writes_audit_only(app, tmp_path):
    at = app.run()
    _button(at, "triage").click().run()
    _button(at, "reject").click().run()
    next(t for t in at.text_input if t.label.startswith("Why? (e.g.")).input("needs context")
    next(b for b in at.button if "Confirm reject" in b.label).click().run()
    assert not at.exception
    assert (tmp_path / "audit.jsonl").exists() and not (tmp_path / "ticketing_outbox.jsonl").exists()


def test_edit_priority_is_saved(app, tmp_path):
    at = app.run()
    _button(at, "triage").click().run()
    _button(at, "edit").click().run()
    # Form widgets only apply on submit: set the value, then submit in the same run.
    next(s for s in at.selectbox if s.label == "Priority").set_value("P2")
    next(b for b in at.button if "Save my edit" in b.label).click().run()
    assert not at.exception
    audit = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])
    assert audit["review"]["decision"] == "edited" and audit["final"]["priority"] == "P2"


def test_reviewed_ticket_leaves_the_inbox(app):
    at = app.run()
    _button(at, "triage").click().run()
    _button(at, "accept").click().run()
    assert len(at.radio[0].options) == 23
