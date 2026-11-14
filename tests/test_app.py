"""UI tests for the Triage Desk (Streamlit AppTest, fake pipeline: no browser, no network).

AppTest cannot click dataframe rows (browser-only), so tests select a ticket the same way the
inbox does internally: via st.session_state["selected_ticket"]. Each test gets a fresh copy of the sample ticket
queue (tests/conftest.py).
"""
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


def _triage(at, ticket_id="SYN-24102"):
    at.session_state["selected_ticket"] = ticket_id
    at.run()
    at.button(key="triage").click().run()
    assert not at.exception, at.exception
    return at


def test_inbox_loads_with_all_demo_tickets(app):
    at = app.run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 24  # 12 dev + 12 held-out synthetic tickets
    assert at.button(key="triage")


def test_triage_shows_card_with_escalation(app):
    at = _triage(app.run())
    assert any("Needs a lead" in str(e.proto) for e in at.error)
    assert {"accept", "edit", "reject"} <= {b.key for b in at.button}


def test_accept_writes_outbox_and_audit(app, tmp_path):
    at = _triage(app.run())
    at.button(key="accept").click().run()
    assert not at.exception
    assert (tmp_path / "ticketing_outbox.jsonl").exists() and (tmp_path / "audit.jsonl").exists()
    assert len(at.dataframe[0].value) == 23  # reviewed ticket leaves the inbox


def test_reject_writes_audit_only(app, tmp_path):
    at = _triage(app.run())
    at.button(key="reject").click().run()
    next(t for t in at.text_input if t.label == "Why are you rejecting it?").input("needs context")
    next(b for b in at.button if b.label == "Confirm reject").click().run()
    assert not at.exception
    assert (tmp_path / "audit.jsonl").exists() and not (tmp_path / "ticketing_outbox.jsonl").exists()
    assert json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])["review"]["comment"] == "needs context"


def test_edit_priority_is_saved(app, tmp_path):
    at = _triage(app.run())
    at.button(key="edit").click().run()
    # Form widgets only apply on submit: set the value, then submit in the same run.
    at.get_by_key("edit_priority").set_value("P2")
    next(b for b in at.button if b.label == "Save my edit").click().run()
    assert not at.exception
    audit = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])
    assert audit["review"]["decision"] == "edited" and audit["final"]["priority"] == "P2"


@pytest.mark.parametrize("page", ["app_pages/new_ticket.py", "app_pages/activity.py", "app_pages/quality.py",
                                  "app_pages/help.py"])
def test_other_pages_render(app, page):
    at = app.run()
    at.switch_page(page).run()
    assert not at.exception


def test_new_ticket_is_added_and_selected(app):
    at = app.run()
    at.switch_page("app_pages/new_ticket.py").run()
    next(t for t in at.text_input if t.label == "Subject").input("Board empty")
    at.text_area[0].input("Our scheduling board shows nothing since 9am for all planners.")
    next(b for b in at.button if b.label == "Add to inbox").click().run()
    assert not at.exception
    from src import adapters
    snap = adapters.get_queue().read()
    assert len(snap.tickets) == 25 and snap.status[at.session_state["selected_ticket"]] == "new"
    assert at.session_state["selected_ticket"].startswith("SYN-NEW-")
    at.switch_page("app_pages/inbox.py").run()
    assert len(at.dataframe[0].value) == 25


def test_activity_shows_metrics_after_a_decision(app):
    at = _triage(app.run())
    at.button(key="accept").click().run()
    at.switch_page("app_pages/activity.py").run()
    assert not at.exception
    assert at.metric[0].value == "1"


def test_accept_writes_back_to_queue_and_notifies(app, isolated_data):
    from src import adapters
    at = _triage(app.run())
    at.button(key="accept").click().run()
    snap = adapters.get_queue().read()
    row = snap.rows["SYN-24102"]
    assert snap.status["SYN-24102"] == "triaged" and row["priority"] == "P1" and row["escalate"] == "yes"
    assert "Assisted triage, reviewed by" in row["internal_note"]
    assert adapters.get_notifier().recent()[0]["ticket_id"] == "SYN-24102"  # fake facts -> P1 escalation


def test_process_new_tickets_button_prefills_all(app):
    at = app.run()
    at.button(key="process").click().run()
    assert not at.exception
    assert any("Processed 24 new ticket(s)" in str(e.proto) for e in at.success)
    assert at.button(key="accept")  # first ticket now shows a card ready for review, no extra click

def test_inbox_is_sorted_riskiest_first_and_filters(app):
    at = app.run()
    at.button(key="process").click().run()
    df = at.dataframe[0].value
    assert df["Suggested"].iloc[0].startswith("P1")  # fake facts make every ticket a P1 that needs a lead
    at.get_by_key("inbox_filter").set_value("Not processed").run()
    assert not at.exception and any("Nothing here" in str(i.proto) for i in at.info)
    at.get_by_key("inbox_filter").set_value("Needs a lead").run()
    assert len(at.dataframe[0].value) == 24