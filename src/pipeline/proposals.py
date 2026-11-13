"""Assistant suggestions waiting for a human (data/runs/proposals.jsonl, git-ignored).

"Process new tickets" triages in bulk and stores each suggestion here, so a rep can review later without waiting
for the model. Nothing here is written to the ticket: that only happens in handoff.record() after review.
Append-only; the latest line for a ticket wins.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from src.pipeline import handoff
from src.schemas import PipelineTrace, TriageResult

_lock = threading.Lock()


def _path():
    return handoff.runs_dir() / "proposals.jsonl"


def save(result: TriageResult, trace: PipelineTrace) -> None:
    rec = {"saved_at": datetime.now(timezone.utc).isoformat(), "result": result.model_dump(mode="json"),
           "trace": trace.model_dump(mode="json")}
    with _lock, _path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_all() -> dict[str, tuple[TriageResult, PipelineTrace]]:
    p = _path()
    if not p.exists():
        return {}
    out: dict[str, tuple[TriageResult, PipelineTrace]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            r = TriageResult.model_validate(rec["result"])
            out[r.ticket_id] = (r, PipelineTrace.model_validate(rec["trace"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue  # a damaged line only loses that one suggestion; the ticket can be triaged again
    return out


def get(ticket_id: str) -> tuple[TriageResult, PipelineTrace] | None:
    return load_all().get(ticket_id)
