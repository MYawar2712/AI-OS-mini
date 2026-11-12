"""Human approval + writing (v0). The ONLY module that writes, and only after a ReviewDecision.

Storage (v0, local JSONL, git-ignored under data/runs/):
  audit.jsonl              one record per triage run: redacted trace + result + review decision
  ticketing_outbox.jsonl   what would be written to the ticketing system (fields + internal note)
Day 3 replaces the outbox with a ticketing adapter (CSV/Sheets/mock API) behind the same function.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.schemas import OutboxRecord, PipelineTrace, ReviewDecision, TriageResult
from src.taxonomy import ROOT, load_settings

EDITABLE = ("intent", "priority", "queue", "escalate")


def runs_dir() -> Path:
    d = ROOT / load_settings()["pipeline"]["runs_dir"]
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
    lines = [f"[Triage v0, reviewed by {review.reviewer}: {review.decision}]",
             f"Summary: {r.summary}",
             f"Next action: {r.suggested_next_action}"]
    if r.escalate:
        lines.append("ESCALATED: " + ", ".join(r.escalation_reasons))
    if r.missing_info:
        lines.append("Ask customer for: " + ", ".join(r.missing_info))
    return "\n".join(lines)


def record(result: TriageResult, trace: PipelineTrace, review: ReviewDecision) -> tuple[TriageResult, OutboxRecord | None]:
    """Apply the human decision, write outbox (unless rejected) and audit log. Returns the final result."""
    final = apply_edits(result, review.edited_fields) if review.decision == "edited" else result
    outbox = None
    d = runs_dir()
    if review.decision != "rejected":
        outbox = OutboxRecord(
            ticket_id=final.ticket_id,
            fields={"intent": final.intent, "secondary_intent": final.secondary_intent or "", "priority": final.priority,
                    "queue": final.queue, "escalate": str(final.escalate).lower(),
                    "escalation_reasons": ";".join(final.escalation_reasons), "missing_info": ";".join(final.missing_info)},
            internal_note=internal_note(final, review), written_at=datetime.now(timezone.utc), review=review)
        with (d / "ticketing_outbox.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(outbox.model_dump_json() + "\n")
    audit = {"logged_at": datetime.now(timezone.utc).isoformat(), "trace": trace.model_dump(mode="json"),
             "proposed": result.model_dump(), "final": final.model_dump(), "review": review.model_dump(mode="json")}
    with (d / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit, ensure_ascii=False) + "\n")
    return final, outbox
