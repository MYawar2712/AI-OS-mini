"""Integration #2: the ticket queue, a CSV file that opens in Excel (data/integrations/ticket_queue.csv).

It is both the ticket SOURCE (rows with status `new` are picked up) and the ticketing system the approved triage
is WRITTEN BACK to (status + triage fields + internal note). A helpdesk API (Zendesk, Freshdesk...) would
implement the same methods.

Status flow:  new -> ready_for_review (assistant pre-filled it) -> triaged (rep accepted/edited)
                                                                -> manual_triage (rep rejected the suggestion)
Rules: bad rows are reported per line and skipped (never crash the whole queue); every write replaces the file
atomically; a file locked by Excel gives a clear "close it and retry" error.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.schemas import InboundTicket, ReviewDecision, TriageResult

TICKET_COLUMNS = ["ticket_id", "received_at", "channel", "from_name", "from_email", "subject", "body",
                  "customer_id", "attachments"]
TRIAGE_COLUMNS = ["status", "priority", "queue", "intent", "secondary_intent", "escalate", "escalation_reasons",
                  "missing_info", "internal_note", "triaged_by", "triaged_at"]
COLUMNS = TICKET_COLUMNS + TRIAGE_COLUMNS
STATUSES = ("new", "ready_for_review", "triaged", "manual_triage")
WAITING = ("new", "ready_for_review")
_lock = threading.RLock()


class QueueError(RuntimeError):
    """The ticket file could not be read or written. The message says what to do."""


@dataclass
class RowError:
    line: int
    ticket_id: str
    message: str

    def __str__(self) -> str:
        return f"line {self.line} ({self.ticket_id or 'no id'}): {self.message}"


@dataclass
class QueueSnapshot:
    tickets: list[InboundTicket] = field(default_factory=list)
    status: dict[str, str] = field(default_factory=dict)
    rows: dict[str, dict] = field(default_factory=dict)
    errors: list[RowError] = field(default_factory=list)

    def with_status(self, *statuses: str) -> list[InboundTicket]:
        return [t for t in self.tickets if self.status[t.ticket_id] in statuses]


def ticket_to_row(t: InboundTicket, status: str = "new") -> dict:
    row = dict.fromkeys(COLUMNS, "")
    row.update(ticket_id=t.ticket_id, received_at=t.received_at.isoformat(), channel=t.channel, from_name=t.from_name,
               from_email=t.from_email or "", subject=t.subject, body=t.body, customer_id=t.customer_id or "",
               attachments=";".join(t.attachments), status=status)
    return row


def _row_to_ticket(row: dict) -> InboundTicket:
    return InboundTicket(
        ticket_id=row["ticket_id"].strip(), received_at=row["received_at"].strip(), channel=row["channel"].strip(),
        from_name=row["from_name"].strip() or "Customer", from_email=row["from_email"].strip() or None,
        subject=row["subject"].strip(), body=row["body"].strip(), customer_id=row["customer_id"].strip() or None,
        attachments=[a.strip() for a in row["attachments"].split(";") if a.strip()])


_FRIENDLY = {  # column -> what a rep should fix (row errors are shown in the app)
    "body": "the message is empty", "ticket_id": "ticket_id must use capital letters, digits and dashes (e.g. SYN-1001)",
    "received_at": "received_at must be a date and time like 2026-11-13T09:30:00+00:00",
    "channel": "channel must be one of: email, portal, chat, phone_note",
}


def _validation_message(e: ValidationError) -> str:
    parts = []
    for err in e.errors():
        col = str(err["loc"][0]) if err["loc"] else "row"
        parts.append(_FRIENDLY.get(col, f"{col}: {err['msg']}"))
    return "; ".join(dict.fromkeys(parts))[:300]


class CsvTicketQueue:
    name = "csv"

    def __init__(self, path: Path, seed: Optional[Path] = None):
        self.path = Path(path)
        with _lock:
            if not self.path.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if seed is not None and Path(seed).exists():
                    shutil.copyfile(seed, self.path)
                else:
                    self._write_rows([])

    # ------------------------------------------------------------ read
    def _read_rows(self) -> list[dict]:
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError as e:
            raise QueueError(f"The ticket file {self.path} is missing. Restart the app to recreate it.") from e
        except PermissionError as e:
            raise QueueError(f"The ticket file {self.path.name} is open in another program (e.g. Excel). "
                             "Close it and try again.") from e
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Excel's default "CSV (Comma delimited)" on Windows saves as cp1252, not UTF-8 (clean-room run, day3/02).
            # Read it as cp1252; the next write saves it back as UTF-8 with BOM, which Excel also opens.
            text = raw.decode("cp1252", errors="replace")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        missing = [c for c in TICKET_COLUMNS + ["status"] if c not in (reader.fieldnames or [])]
        if missing:
            raise QueueError(f"The ticket file {self.path.name} is missing column(s): {', '.join(missing)}. "
                             f"The first row must be: {','.join(COLUMNS)}")
        return [{c: (r.get(c) or "") for c in COLUMNS} for r in reader]

    def read(self) -> QueueSnapshot:
        with _lock:
            rows = self._read_rows()
        snap = QueueSnapshot()
        for line, row in enumerate(rows, start=2):  # line 1 is the header
            tid, status = row["ticket_id"].strip(), (row["status"].strip() or "new").lower()
            if tid in snap.status:
                snap.errors.append(RowError(line, tid, "duplicate ticket_id; only the first row is used"))
                continue
            if status not in STATUSES:
                snap.errors.append(RowError(line, tid, f"unknown status {status!r} (use one of: {', '.join(STATUSES)})"))
                continue
            try:
                t = _row_to_ticket(row)
            except ValidationError as e:
                snap.errors.append(RowError(line, tid, _validation_message(e)))
                continue
            snap.tickets.append(t)
            snap.status[tid] = status
            snap.rows[tid] = row
        return snap

    # ------------------------------------------------------------ write
    def _write_rows(self, rows: list[dict]) -> None:
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        try:
            os.replace(tmp, self.path)
        except PermissionError as e:
            tmp.unlink(missing_ok=True)
            raise QueueError(f"Could not save to {self.path.name}: it is open in another program (e.g. Excel). "
                             "Close it and try again. Nothing was changed.") from e

    def _update(self, ticket_id: str, changes: dict) -> bool:
        with _lock:
            rows = self._read_rows()
            hit = False
            for r in rows:
                if r["ticket_id"].strip() == ticket_id:
                    r.update(changes)
                    hit = True
                    break
            if hit:
                self._write_rows(rows)
            return hit

    def add(self, ticket: InboundTicket) -> None:
        with _lock:
            rows = self._read_rows()
            if any(r["ticket_id"].strip() == ticket.ticket_id for r in rows):
                raise QueueError(f"Ticket {ticket.ticket_id} is already in the queue.")
            rows.append(ticket_to_row(ticket))
            self._write_rows(rows)

    def set_status(self, ticket_id: str, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        return self._update(ticket_id, {"status": status})

    def write_back(self, final: TriageResult, review: ReviewDecision, note: str) -> bool:
        """Write the human-approved triage to the ticket row. Returns False if the ticket is not in this queue."""
        stamp = {"triaged_by": review.reviewer, "triaged_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if review.decision == "rejected":
            return self._update(final.ticket_id, {
                "status": "manual_triage", **dict.fromkeys(TRIAGE_COLUMNS[1:-2], ""), **stamp,
                "internal_note": f"[Assistant suggestion rejected by {review.reviewer}] {review.comment}".strip()})
        return self._update(final.ticket_id, {
            "status": "triaged", "priority": final.priority, "queue": final.queue, "intent": final.intent,
            "secondary_intent": final.secondary_intent or "", "escalate": "yes" if final.escalate else "no",
            "escalation_reasons": ";".join(final.escalation_reasons), "missing_info": ";".join(final.missing_info),
            "internal_note": note, **stamp})
