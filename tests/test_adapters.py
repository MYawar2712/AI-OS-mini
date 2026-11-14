"""Day 3 integrations: CRM (SQLite/JSON), CSV ticket queue, escalation notifier, batch trigger, preflight, errors.
No network: the webhook test points at a closed local port."""
import json
from datetime import datetime, timezone

import pytest

from src import adapters
from src.adapters.crm import CRMError, JsonCRM, SqliteCRM
from src.adapters.notifier import EscalationNotifier
from src.adapters.ticket_queue import COLUMNS, CsvTicketQueue, QueueError
from src.llm_client import LLMCallError, LLMResponse
from src.observability import friendly_error
from src.pipeline import batch, proposals
from src.pipeline.run import triage
from src.schemas import InboundTicket, ReviewDecision, TriageResult
from src.taxonomy import ROOT

CUSTOMERS = ROOT / "data/synthetic/customers.json"


# ---------------------------------------------------------------- CRM
def test_sqlite_crm_matches_json_export(tmp_path):
    sql, js = SqliteCRM(tmp_path / "crm.sqlite", seed_json=CUSTOMERS), JsonCRM(CUSTOMERS)
    assert sql.all() == js.all() and len(sql.all()) == 25
    assert sql.get("CUST-1001")["onboarding_in_progress"] is False
    assert sql.get("CUST-NOPE") is None


def test_sqlite_crm_is_built_once_and_read_only(tmp_path):
    db = tmp_path / "crm.sqlite"
    SqliteCRM(db, seed_json=CUSTOMERS)
    mtime = db.stat().st_mtime_ns
    crm = SqliteCRM(db, seed_json=CUSTOMERS)
    assert db.stat().st_mtime_ns == mtime
    with pytest.raises(CRMError):
        crm._query("DELETE FROM customers")  # opened with mode=ro


def test_crm_missing_seed_gives_actionable_error(tmp_path):
    with pytest.raises(CRMError, match="Restore it"):
        SqliteCRM(tmp_path / "crm.sqlite", seed_json=tmp_path / "missing.json")


def test_pipeline_uses_crm_adapter():
    from src.pipeline.context import lookup_customer
    assert lookup_customer("CUST-1001")["company_name"].startswith("Tidewell")
    assert (adapters.data_dir() / "crm.sqlite").exists()


# ---------------------------------------------------------------- ticket queue
def _ticket(tid="SYN-T1", body="Board is empty"):
    return InboundTicket(ticket_id=tid, received_at=datetime(2026, 11, 11, 9, tzinfo=timezone.utc), channel="email",
                         from_name="Sam", subject="Help", body=body, customer_id="CUST-1001", attachments=["a.png"])


def _review(decision="accepted", **kw):
    return ReviewDecision(ticket_id="SYN-T1", reviewer="rep1", decision=decision,
                          reviewed_at=datetime.now(timezone.utc), **kw)


def _result(**kw):
    base = dict(ticket_id="SYN-T1", intent="mobile_app_sync", priority="P1", queue="tier2_technical", escalate=True,
                escalation_reasons=["p1_incident"], summary="s", suggested_next_action="a", confidence=0.9,
                rationale="r")
    base.update(kw)
    return TriageResult(**base)


def test_queue_seeds_from_sample_and_round_trips(tmp_path):
    q = adapters.get_queue()
    snap = q.read()
    assert len(snap.tickets) == 24 and set(snap.status.values()) == {"new"} and not snap.errors
    q2 = CsvTicketQueue(tmp_path / "q.csv")
    q2.add(_ticket(body="line 1\nline 2, with \"quotes\""))
    t = q2.read().tickets[0]
    assert t.body == 'line 1\nline 2, with "quotes"' and t.attachments == ["a.png"]


def test_queue_reports_bad_rows_and_keeps_good_ones(tmp_path):
    p = tmp_path / "q.csv"
    good = ["SYN-1", "2026-11-11T09:00:00+00:00", "email", "A", "", "S", "body", "", "", "new"]
    rows = [good, ["SYN-2", "not a date", "email", "A", "", "S", "body", "", "", "new"],
            ["SYN-3", "2026-11-11T09:00:00+00:00", "fax", "A", "", "S", "body", "", "", "new"],
            ["SYN-4", "2026-11-11T09:00:00+00:00", "email", "A", "", "S", "", "", "", "new"],
            ["SYN-5", "2026-11-11T09:00:00+00:00", "email", "A", "", "S", "body", "", "", "lost"], good]
    p.write_text(",".join(COLUMNS[:10]) + "\n" + "\n".join(",".join(r) for r in rows) + "\n", encoding="utf-8")
    snap = CsvTicketQueue(p).read()
    assert [t.ticket_id for t in snap.tickets] == ["SYN-1"]
    assert [e.line for e in snap.errors] == [3, 4, 5, 6, 7]
    assert "duplicate" in str(snap.errors[-1]) and "unknown status" in str(snap.errors[-2])


def test_queue_reads_excel_default_cp1252_csv(tmp_path):
    """Excel's default 'CSV (Comma delimited)' is cp1252, not UTF-8 (found in the clean-room run)."""
    p = tmp_path / "q.csv"
    header = ",".join(COLUMNS[:10])
    p.write_bytes((header + "\r\nSYN-1,2026-11-11T09:00:00+00:00,email,A,,Invoice £0.00,Totals show £0.00,,,new\r\n")
                  .encode("cp1252"))
    q = CsvTicketQueue(p)
    assert q.read().tickets[0].subject == "Invoice £0.00"
    q.set_status("SYN-1", "ready_for_review")  # saved back as UTF-8
    assert q.read().status["SYN-1"] == "ready_for_review" and p.read_bytes().startswith(b"\xef\xbb\xbf")


def test_queue_missing_columns_is_explained(tmp_path):
    p = tmp_path / "q.csv"
    p.write_text("ticket_id,subject\nSYN-1,x\n", encoding="utf-8")
    with pytest.raises(QueueError, match="missing column"):
        CsvTicketQueue(p).read()


def test_queue_locked_file_changes_nothing(tmp_path, monkeypatch):
    q = CsvTicketQueue(tmp_path / "q.csv")
    q.add(_ticket())
    before = q.path.read_bytes()

    def locked(*a):
        raise PermissionError("in use")
    monkeypatch.setattr("src.adapters.ticket_queue.os.replace", locked)
    with pytest.raises(QueueError, match="open in another program"):
        q.set_status("SYN-T1", "ready_for_review")
    assert q.path.read_bytes() == before and not list(tmp_path.glob("*.tmp"))


def test_write_back_accept_and_reject(tmp_path):
    q = CsvTicketQueue(tmp_path / "q.csv")
    q.add(_ticket())
    assert q.write_back(_result(), _review(), "note") is True
    row = q.read().rows["SYN-T1"]
    assert (row["status"], row["priority"], row["escalate"], row["triaged_by"]) == ("triaged", "P1", "yes", "rep1")
    q.write_back(_result(), _review("rejected", comment="spam"), "note")
    row = q.read().rows["SYN-T1"]
    assert row["status"] == "manual_triage" and row["priority"] == "" and "spam" in row["internal_note"]
    assert q.write_back(_result(ticket_id="SYN-OTHER"), _review(), "n") is False  # not in queue: no crash


def test_add_rejects_duplicate(tmp_path):
    q = CsvTicketQueue(tmp_path / "q.csv")
    q.add(_ticket())
    with pytest.raises(QueueError, match="already"):
        q.add(_ticket())


# ---------------------------------------------------------------- notifier
def test_notifier_only_for_escalations(tmp_path):
    n = EscalationNotifier(tmp_path / "esc.jsonl")
    assert n.notify(_result(escalate=False, escalation_reasons=[], priority="P3"), _review()).delivered_to == []
    assert n.notify(_result(), _review()).delivered_to == ["esc.jsonl"]
    assert n.recent()[0]["reasons"] == ["p1_incident"]


def test_webhook_failure_is_reported_not_raised(tmp_path):
    n = EscalationNotifier(tmp_path / "esc.jsonl", webhook_url="http://127.0.0.1:9/hook", timeout=1)
    out = n.notify(_result(), _review())
    assert out.delivered_to == ["esc.jsonl"] and "Webhook not delivered" in out.errors[0]


# ---------------------------------------------------------------- batch trigger
def _facts_llm(*a, **k):
    facts = dict(intent="general_inquiry", secondary_intent=None, problem_clear=True, scope="single_user",
                 core_workflow_blocked=False, workaround_available=None, affects_job_today=False,
                 data_loss_or_corruption=False, security_or_unauthorised_access=False, legal_or_regulatory_mention=False,
                 payment_suspension_risk=False, duplicate_or_unauthorised_payment=False, churn_signal=False,
                 admin_locked_out=False, instructions_to_ai_detected=False, missing_info=[], summary="s",
                 suggested_next_action="a", confidence=0.9, rationale="r")
    return LLMResponse(text=json.dumps(facts), input_tokens=1, output_tokens=1, latency_ms=1, model="fake")


def test_batch_processes_new_only_and_survives_a_failure():
    q = adapters.get_queue()
    q.set_status("SYN-24102", "triaged")

    def flaky(t):
        if t.ticket_id == "SYN-24101":
            raise OSError("disk full")
        return triage(t, llm=_facts_llm)
    seen = []
    rep = batch.process_new(triage_fn=flaky, workers=3, on_progress=lambda d, n, tid: seen.append(d))
    assert rep.found == 23 and len(rep.ready) == 22 and list(rep.failed) == ["SYN-24101"]
    assert sorted(seen) == list(range(1, 24))
    snap = q.read()
    assert snap.status["SYN-24101"] == "new" and snap.status["SYN-24102"] == "triaged"
    assert sum(s == "ready_for_review" for s in snap.status.values()) == 22
    assert len(proposals.load_all()) == 22


def test_batch_llm_down_means_manual_triage_suggestions():
    def down(*a, **k):
        raise LLMCallError("timeout")
    rep = batch.process_new(triage_fn=lambda t: triage(t, llm=down), workers=4)
    assert len(rep.fallback) == 24 and not rep.failed
    assert all(r.escalate and r.confidence == 0 for r, _ in proposals.load_all().values())


def test_structured_log_has_run_ids(isolated_data):
    batch.process_new(triage_fn=lambda t: triage(t, llm=_facts_llm), workers=2)
    events = [json.loads(x) for x in (isolated_data["runs"] / "app_log.jsonl").read_text().splitlines()]
    triages = [e for e in events if e["event"] == "triage"]
    assert len(triages) == 24 and all(len(e["run_id"]) == 12 and e["status"] == "ok" for e in triages)
    assert {e["event"] for e in events} >= {"batch_start", "batch_end"}
    assert not any("body" in e for e in events)  # never log ticket text


# ---------------------------------------------------------------- errors + preflight
@pytest.mark.parametrize("exc, title", [
    (QueueError("x"), "Ticket file problem"), (CRMError("x"), "Customer data problem"),
    (LLMCallError("x"), "The AI service did not respond"), (ValueError("bad"), "That change isn't valid"),
    (RuntimeError("boom"), "Something went wrong")])
def test_friendly_errors(exc, title):
    t, what = friendly_error(exc)
    assert t == title and what


def test_preflight_ok_and_missing_key(monkeypatch):
    from src import preflight
    checks = {c.name: c for c in preflight.run_checks()}
    assert checks["Ticket queue"].ok and checks["Customer database"].ok
    monkeypatch.setattr("src.llm_client.is_configured", lambda: False)
    key = next(c for c in preflight.run_checks() if c.name == "AI assistant key")
    assert not key.ok and not key.blocking and ".env" in key.fix


# ---------------------------------------------------------------- tracing privacy
def test_trace_inputs_are_redacted(monkeypatch):
    """Whatever is sent to LangSmith must never contain the raw card number or password."""
    from contextlib import contextmanager

    import src.pipeline.run as run_mod
    seen = {}

    class _Run:
        id = "abc"

        def end(self, outputs=None, **kw):
            seen["outputs"] = outputs

    @contextmanager
    def fake_trace(name, inputs=None, **kw):
        seen["inputs"] = inputs
        yield _Run()
    monkeypatch.setattr(run_mod, "trace_run", fake_trace)
    t = _ticket(body="Card 4111 1111 1111 1111 cvv 123, my password is Hunter2! please fix billing")
    result, trace = run_mod.triage(t, llm=_facts_llm)
    blob = json.dumps(seen)
    assert "4111" not in blob and "Hunter2" not in blob
    assert "[REDACTED_CARD]" in seen["inputs"]["body"] and trace.langsmith_run_id == "abc"
