"""Structured logs and plain-language errors.

* `log_event(...)` appends one JSON line to data/runs/app_log.jsonl (run_id, event, ticket_id, timings...).
  Only IDs, counts and redacted metadata are logged, never ticket text. Logging never breaks the workflow.
* `friendly_error(exc)` turns any exception into (what happened, what to do) for a non-developer.
"""
from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

_lock = threading.Lock()


# ---------------------------------------------------------------- LangSmith tracing (optional)
def tracing_enabled() -> bool:
    """On when LANGSMITH_API_KEY is in .env and the langsmith package is installed. TRIAGE_TRACING=off disables it
    (tests set this). Only REDACTED ticket text is ever sent (see src/pipeline/run.py)."""
    import os

    from dotenv import load_dotenv

    from src.taxonomy import ROOT
    load_dotenv(ROOT / ".env")
    if os.environ.get("TRIAGE_TRACING", "on").lower() == "off" or not os.environ.get("LANGSMITH_API_KEY"):
        return False
    try:
        import langsmith  # noqa: F401
    except ImportError:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"  # the SDK only sends runs when this is set
    return True


def tracing_project() -> str:
    import os
    return os.environ.get("LANGSMITH_PROJECT") or "triage-desk"


class _NoRun:
    id = None

    def end(self, **kw) -> None:
        pass

    def add_metadata(self, *a, **kw) -> None:
        pass


@contextmanager
def trace_run(name: str, run_type: str = "chain", inputs: dict | None = None, tags: list[str] | None = None,
              metadata: dict | None = None):
    """A LangSmith run (nested automatically inside an outer trace_run). No-op when tracing is off.
    Tracing problems never break triage."""
    if not tracing_enabled():
        yield _NoRun()
        return
    try:
        import langsmith
        cm = langsmith.trace(name=name, run_type=run_type, inputs=inputs or {}, tags=tags, metadata=metadata,
                             project_name=tracing_project())
        run = cm.__enter__()
    except Exception:  # noqa: BLE001
        yield _NoRun()
        return
    try:
        yield run
    except BaseException as e:
        cm.__exit__(type(e), e, e.__traceback__)
        raise
    else:
        cm.__exit__(None, None, None)


def flush_traces() -> None:
    """Send pending traces before a short-lived script exits."""
    if tracing_enabled():
        try:
            from langsmith.run_trees import get_cached_client
            get_cached_client().flush()
        except Exception:  # noqa: BLE001
            pass


def trace_url(run_id: str | None) -> str | None:
    """Link to a trace in LangSmith (one API call, so call it lazily from the UI)."""
    if not run_id or not tracing_enabled():
        return None
    try:
        from langsmith.run_trees import get_cached_client
        client = get_cached_client()
        project = client.read_project(project_name=tracing_project())
        return f"{project.url}?peek={run_id}&peeked_trace={run_id}" if project.url else None
    except Exception:  # noqa: BLE001
        return None


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
