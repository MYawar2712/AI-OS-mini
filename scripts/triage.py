"""v0 interface: triage ONE ticket end to end, with a human approval step.

    python -m scripts.triage --case TC02                 # a ticket from the test set (synthetic)
    python -m scripts.triage --file path/to/ticket.json  # any InboundTicket JSON
    python -m scripts.triage --case TC02 --reviewer "Sam"

Flow: pipeline -> triage card -> reviewer types a/e/r -> outbox + audit log written (data/runs/).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.pipeline.handoff import EDITABLE, record, runs_dir
from src.pipeline.run import triage
from src.schemas import InboundTicket, ReviewDecision, load_test_cases
from src.taxonomy import ROOT


def load_ticket(args) -> InboundTicket:
    if args.file:
        return InboundTicket.model_validate_json(Path(args.file).read_text(encoding="utf-8"))
    for path in ("eval/test_cases.jsonl", "eval/test_cases_holdout.jsonl"):
        for c in load_test_cases(ROOT / path):
            if c.id == args.case:
                return c.ticket
    raise SystemExit(f"case {args.case} not found")


def card(ticket: InboundTicket, r, trace) -> str:
    bar = "=" * 72
    esc = ("YES  ->  " + ", ".join(r.escalation_reasons)) if r.escalate else "no"
    lines = [bar, f" TICKET {ticket.ticket_id}  |  {ticket.subject}  |  from {ticket.from_name}  (SYNTHETIC)", bar,
             f" Category      : {r.intent}" + (f"   (also: {r.secondary_intent})" if r.secondary_intent else ""),
             f" Priority      : {r.priority}",
             f" Send to team  : {r.queue}",
             f" Needs a lead? : {esc}",
             f" Ask customer  : {', '.join(r.missing_info) or '-'}",
             f" Summary       : {r.summary}",
             f" Next step     : {r.suggested_next_action}",
             f" Confidence    : {r.confidence:.0%}",
             "-" * 72,
             f" How decided   : rules fired {', '.join(trace.rules_fired) or '-'}",
             f" Safety checks : redacted={trace.redactions or 'none'}  injection={trace.injection_matches or 'none'}  "
             f"customer_found={trace.customer_found}",
             f" Run           : {trace.status}, {trace.total_ms / 1000:.1f} s, model {trace.model}, "
             f"{trace.input_tokens} in / {trace.output_tokens} out tokens", bar]
    return "\n".join(lines)


def ask(prompt: str) -> str:
    print(prompt, end="", flush=True)
    line = sys.stdin.readline()
    if not line:
        raise SystemExit("\nNo reviewer input: nothing written (human approval is required).")
    return line.strip()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case")
    g.add_argument("--file")
    ap.add_argument("--reviewer", default="tier1_rep")
    args = ap.parse_args()

    ticket = load_ticket(args)
    result, trace = triage(ticket)
    print(card(ticket, result, trace))

    shown = time.perf_counter()
    choice = ask("Review: [a]ccept  [e]dit  [r]eject (human triage) > ").lower()[:1]
    edits: dict[str, str] = {}
    comment = ""
    if choice == "e":
        print(f"Editable fields: {', '.join(EDITABLE)}. Enter field=value, blank line to finish.")
        while (line := ask("  edit> ")):
            k, _, v = line.partition("=")
            edits[k.strip()] = v.strip()
        decision = "edited" if edits else "accepted"
    elif choice == "r":
        decision = "rejected"
        comment = ask("Reason for rejecting > ")
    else:
        decision = "accepted"
    review = ReviewDecision(ticket_id=ticket.ticket_id, reviewer=args.reviewer, decision=decision, edited_fields=edits,
                            comment=comment, reviewed_at=datetime.now(timezone.utc),
                            seconds_to_decide=round(time.perf_counter() - shown, 1))
    final, outbox = record(result, trace, review)
    d = runs_dir().relative_to(ROOT).as_posix()
    if outbox:
        print(f"\nWritten to ticketing outbox ({d}/ticketing_outbox.jsonl):")
        print(json.dumps(outbox.fields, indent=2))
        print("Internal note:\n" + outbox.internal_note)
    else:
        print("\nRejected: nothing written to the ticket; flagged for manual triage.")
    print(f"Audit record appended: {d}/audit.jsonl")


if __name__ == "__main__":
    main()
