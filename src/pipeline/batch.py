"""Trigger: triage every ticket with status `new` in the queue and store the suggestions for review.

Used by the "Process new tickets" button and by `python -m scripts.process_queue`. Tickets are triaged in
parallel (the model call is the slow part); queue writes happen one at a time. One ticket failing never stops
the others: it is reported and left as `new` so it can be retried.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from src import adapters
from src.observability import friendly_error, log_event, new_run_id
from src.pipeline import proposals
from src.taxonomy import load_settings


@dataclass
class BatchReport:
    found: int = 0
    ready: list[str] = field(default_factory=list)
    fallback: list[str] = field(default_factory=list)   # LLM failed -> suggestion says "triage manually"
    escalate: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # ticket_id -> plain-language error
    row_errors: list[str] = field(default_factory=list)
    seconds: float = 0.0


def process_new(triage_fn: Optional[Callable] = None, workers: Optional[int] = None,
                on_progress: Optional[Callable[[int, int, str], None]] = None) -> BatchReport:
    if triage_fn is None:
        import src.pipeline.run as pipeline_run  # module lookup so tests/UI patches apply
        triage_fn = pipeline_run.triage
    workers = workers or load_settings()["integrations"]["process_workers"]
    start, batch_id = time.perf_counter(), new_run_id()
    queue = adapters.get_queue()
    snap = queue.read()
    todo = snap.with_status("new")
    rep = BatchReport(found=len(todo), row_errors=[str(e) for e in snap.errors])
    log_event("batch_start", batch_id=batch_id, found=len(todo), row_errors=len(snap.errors))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(triage_fn, t): t.ticket_id for t in todo}
        for done, fut in enumerate(as_completed(futures), start=1):
            tid = futures[fut]
            try:
                result, trace = fut.result()
                proposals.save(result, trace)
                queue.set_status(tid, "ready_for_review")
                (rep.fallback if trace.status == "fallback" else rep.ready).append(tid)
                if result.escalate:
                    rep.escalate.append(tid)
            except Exception as e:  # noqa: BLE001 - report per ticket, keep going
                title, what = friendly_error(e)
                rep.failed[tid] = f"{title}: {what}"
                log_event("batch_ticket_failed", level="error", batch_id=batch_id, ticket_id=tid,
                          error=f"{type(e).__name__}: {e}"[:300])
            if on_progress:
                on_progress(done, len(todo), tid)

    rep.seconds = round(time.perf_counter() - start, 1)
    log_event("batch_end", batch_id=batch_id, ready=len(rep.ready), fallback=len(rep.fallback),
              failed=len(rep.failed), seconds=rep.seconds)
    return rep
