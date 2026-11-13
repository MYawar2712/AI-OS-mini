"""Build the committed sample ticket queue (data/sample/ticket_queue_sample.csv) from the SYNTHETIC test tickets.

    python -m scripts.build_sample_queue

Only the ticket fields are copied (no expected labels). On first run the app copies this file to
data/integrations/ticket_queue.csv, which is the live queue. Delete that file to start the demo again.
"""
from __future__ import annotations

import csv

from src.adapters.ticket_queue import COLUMNS, ticket_to_row
from src.schemas import load_test_cases
from src.taxonomy import ROOT, load_settings

SOURCES = ("eval/test_cases.jsonl", "eval/test_cases_holdout.jsonl")


def main() -> None:
    tickets = [c.ticket for f in SOURCES for c in load_test_cases(ROOT / f)]
    tickets.sort(key=lambda t: t.received_at)
    out = ROOT / load_settings()["integrations"]["ticket_queue"]["seed"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(ticket_to_row(t) for t in tickets)
    print(f"Wrote {len(tickets)} synthetic tickets to {out.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
