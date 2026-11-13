"""Structured logs and plain-language errors.

* `log_event(...)` appends one JSON line to data/runs/app_log.jsonl (run_id, event, ticket_id, timings...).
  Only IDs, counts and redacted metadata are logged, never ticket text. Logging never breaks the workflow.
* `friendly_error(exc)` turns any exception into (what happened, what to do) for a non-developer.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone

_lock = threading.Lock()


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def log_event(event: str, level: str = "info", **fields) -> None:
    from src.pipeline import handoff  # late import: tests patch handoff.runs_dir
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "level": level, "event": event, **fields}
    try:
        with _lock, (handoff.runs_dir() / "app_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass  # a full disk or locked log must never stop a ticket being triaged


def friendly_error(exc: BaseException) -> tuple[str, str]:
    """(title, what to do). Specific adapter errors already carry an actionable message."""
    from src.adapters.crm import CRMError
    from src.adapters.ticket_queue import QueueError
    from src.llm_client import LLMCallError, LLMNotConfigured

    if isinstance(exc, QueueError):
        return "Ticket file problem", str(exc)
    if isinstance(exc, CRMError):
        return "Customer data problem", str(exc)
    if isinstance(exc, LLMNotConfigured):
        return ("Assistant not configured",
                "Add your API key to the .env file (see README, step 2), then restart. Until then, tickets are sent "
                "to manual triage.")
    if isinstance(exc, LLMCallError):
        return ("The AI service did not respond",
                "The ticket was sent to manual triage. Check your internet connection and try again in a minute.")
    if isinstance(exc, ValueError):
        return "That change isn't valid", f"{exc}. Nothing was saved; please check and try again."
    if isinstance(exc, OSError):
        return ("Could not read or write a file",
                f"{exc}. Check the file isn't open in another program and that the folder is writable.")
    return ("Something went wrong",
            f"{type(exc).__name__}: {exc}. Nothing was saved. Try again; if it keeps happening, send "
            "data/runs/app_log.jsonl to the person who maintains this tool.")
