"""Human approval + writing (v0). The ONLY module that writes, and only after a ReviewDecision.

Storage (v0, local JSONL, git-ignored under data/runs/):
  audit.jsonl              one record per triage run: redacted trace + result + review decision
  ticketing_outbox.jsonl   what would be written to the ticketing system (fields + internal note)
Day 3: record() also writes the approved triage back to the ticket queue (src/adapters/ticket_queue.py) and
sends an escalation notice (src/adapters/notifier.py). The outbox stays as an append-only log of every write.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src import adapters
from src.observability import log_event
from src.schemas import OutboxRecord, PipelineTrace, ReviewDecision, TriageResult
from src.taxonomy import ROOT, load_settings

EDITABLE = ("intent", "priority", "queue", "escalate")


def runs_dir() -> Path:
    """Audit/log folder. TRIAGE_RUNS_DIR overrides config (demos, operators)."""
    d = Path(os.environ.get("TRIAGE_RUNS_DIR") or ROOT / load_settings()["pipeline"]["runs_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def apply_edits(result: TriageResult, edits: dict[str, str]) -> TriageResult:
    data = result.model_dump()
    for k, v in edits.items():
        if k not in EDITABLE:
            raise ValueError(f"field {k!r} is not editable in v0 (editable: {', '.join(EDITABLE)})")
        data[k] = (v.strip().lower() in ("true", "yes", "y", "1")) if k == "escalate" else v.strip()
    if data["escalate"] and not data["escalation_reasons"]:
        data["escalation_reasons"] = ["low_confidence"]  # human chose to escalate without a machine reason
    if not data["escalate"]:
        data["escalation_reasons"] = []
    return TriageResult.model_validate(data)  # edits are validated against the contract too


def internal_note(r: TriageResult, review: ReviewDecision) -> str:
    lines = [f"[Assisted triage, reviewed by {review.reviewer}: {review.decision}]",
             f"Summary: {r.summary}",
             f"Next action: {r.suggested_next_action}"]
    if r.escalate:
        lines.append("ESCALATED: " + ", ".join(r.escalation_reasons))
    if r.missing_info:
        lines.append("Ask customer for: " + ", ".join(r.missing_info))
    return "\n".join(lines)


@dataclass
class Delivery:
    """Where an approved decision ended up (shown to the rep as confirmation)."""
    written_back: bool = False          # ticket row updated in the ticket queue
    queue_file: str = ""
    notified: list[str] = field(default_factory=list)   # escalation notice destinations
    warnings: list[str] = field(default_factory=list)   # non-blocking problems (e.g. webhook down)


def record(result: TriageResult, trace: PipelineTrace,
           review: ReviewDecision) -> tuple[TriageResult, OutboxRecord | None, Delivery]:
    """Apply the human decision, then write: ticket queue (write-back) -> outbox -> audit -> escalation notice.

    The ticket write-back goes first: if it fails (e.g. file open in Excel) nothing else is written and the
    error is raised with a message the rep can act on.
    """
    final = apply_edits(result, review.edited_fields) if review.decision == "edited" else result
    note = internal_note(final, review)
    delivery = Delivery()
    queue = adapters.get_queue()
    delivery.queue_file = queue.path.name
    delivery.written_back = queue.write_back(final, review, note)

    outbox = None
    d = runs_dir()
    if review.decision != "rejected":
        outbox = OutboxRecord(
            ticket_id=final.ticket_id,
            fields={"intent": final.intent, "secondary_intent": final.secondary_intent or "", "priority": final.priority,
                    "queue": final.queue, "escalate": str(final.escalate).lower(),
                    "escalation_reasons": ";".join(final.escalation_reasons), "missing_info": ";".join(final.missing_info)},
            internal_note=note, written_at=datetime.now(timezone.utc), review=review)
        with (d / "ticketing_outbox.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(outbox.model_dump_json() + "\n")
        n = adapters.get_notifier().notify(final, review)
        delivery.notified, delivery.warnings = n.delivered_to, n.errors
    audit = {"logged_at": datetime.now(timezone.utc).isoformat(), "trace": trace.model_dump(mode="json"),
             "proposed": result.model_dump(), "final": final.model_dump(), "review": review.model_dump(mode="json"),
             "delivery": asdict(delivery)}
    with (d / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit, ensure_ascii=False) + "\n")
    log_event("review", run_id=trace.run_id, ticket_id=final.ticket_id, decision=review.decision,
              edited=sorted(review.edited_fields), priority=final.priority, escalate=final.escalate,
              written_back=delivery.written_back, notified=delivery.notified, warnings=delivery.warnings,
              seconds_to_decide=review.seconds_to_decide)
    return final, outbox, delivery