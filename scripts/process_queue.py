"""Triage every NEW ticket in the ticket queue and store the suggestions for review.

    python -m scripts.process_queue

Suggestions are NOT written to the tickets: a person approves each one in the Triage Desk
(`streamlit run app/review.py`). Can be scheduled (e.g. Windows Task Scheduler every 5 minutes).
"""
from __future__ import annotations

import sys

from src.preflight import run_checks
from src.pipeline.batch import process_new


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    problems = [c for c in run_checks() if not c.ok]
    for c in problems:
        print(f"[{'!' if c.blocking else 'i'}] {c.name}: {c.message}\n    What to do: {c.fix}")
    if any(c.blocking for c in problems):
        return 2

    def progress(done: int, total: int, tid: str) -> None:
        print(f"  {done}/{total}  {tid}", flush=True)

    rep = process_new(on_progress=progress)
    if rep.found == 0:
        print("No new tickets in the queue.")
    print(f"\nFound {rep.found} new ticket(s) in {rep.seconds} s: {len(rep.ready)} ready for review "
          f"({len(rep.escalate)} need a lead), {len(rep.fallback)} for manual triage, {len(rep.failed)} failed.")
    for tid, msg in rep.failed.items():
        print(f"  FAILED {tid}: {msg}  (left as 'new'; run again to retry)")
    for e in rep.row_errors:
        print(f"  Skipped row, {e}")
    print("Next: open the Triage Desk (streamlit run app/review.py) to approve them.")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
