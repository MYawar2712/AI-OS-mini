"""Baseline 1 — "manual-style" keyword cheat sheet. Deterministic, no LLM.

Mimics a new Tier-1 rep following a laminated cheat sheet: scan for trigger words, pick the
first matching intent, set priority from a short list of urgency words, route by the intent's
default queue. It was written once as a generic cheat sheet and NOT tuned to the 12 test cases
(tuning it to the test set would make the comparison meaningless).

    python -m baselines.keyword_baseline
"""
from __future__ import annotations

import re
import time

from baselines.common import load_tickets, write_predictions
from src.schemas import InboundTicket, TriageResult
from src.taxonomy import default_queue

NAME = "keyword_baseline"

# Ordered: first intent whose keywords match wins (a cheat sheet is read top to bottom).
CHEAT_SHEET: list[tuple[str, list[str]]] = [
    ("cancellation_churn_risk", ["cancel", "cancellation", "terminate our contract", "close our account"]),
    ("payment_failure", ["declined", "direct debit failed", "payment failed", "card", "suspended"]),
    ("billing_invoice", ["invoice", "charged", "billing", "credit note", "vat", "overcharged"]),
    ("mobile_app_sync", ["mobile app", "app", "sync", "syncing", "phone", "tablet"]),
    ("account_access", ["password", "locked out", "log in", "login", "mfa", "2fa", "reset"]),
    ("data_import_export", ["import", "export", "csv", "spreadsheet", "upload"]),
    ("scheduling_dispatch", ["schedule", "scheduling", "dispatch", "engineer", "visit", "appointment", "reallocate"]),
    ("feature_request", ["feature", "would be great if", "can you add", "suggestion", "wish"]),
    ("technical_issue", ["error", "broken", "bug", "not working", "crash", "blank", "frozen", "freeze"]),
]
P1_WORDS = ["system down", "nobody can", "none of", "all engineers", "everyone", "outage", "data loss"]
P2_WORDS = ["urgent", "asap", "today", "immediately", "locked out", "declined", "suspended"]
LEGAL_SECURITY = ["lawyer", "legal action", "solicitor", "gdpr", "breach", "hacked", "unauthorised", "unauthorized"]


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)


def classify(t: InboundTicket) -> TriageResult:
    text = f"{t.subject}\n{t.body}".lower()
    intent = next((name for name, kws in CHEAT_SHEET if _has(text, kws)), "general_inquiry")

    if _has(text, P1_WORDS):
        priority = "P1"
    elif _has(text, P2_WORDS):
        priority = "P2"
    elif intent in ("feature_request", "general_inquiry"):
        priority = "P4"
    else:
        priority = "P3"

    reasons: list[str] = []
    if priority == "P1":
        reasons.append("p1_incident")
    if intent == "cancellation_churn_risk":
        reasons.append("churn_risk")
    if _has(text, LEGAL_SECURITY):
        reasons.append("legal_or_security")
    if not t.customer_id:
        reasons.append("missing_account_id")

    missing = ["account_id"] if not t.customer_id else []
    if "attached" in text and not t.attachments:
        missing.append("file_sample")

    first_line = next((ln.strip() for ln in t.body.splitlines() if ln.strip()), "")
    return TriageResult(
        ticket_id=t.ticket_id,
        intent=intent,
        priority=priority,
        queue=default_queue(intent),
        escalate=bool(reasons),
        escalation_reasons=reasons,
        missing_info=missing,
        summary=f"[{t.subject}] {first_line[:200]}",
        suggested_next_action=f"Route to {default_queue(intent)} queue.",
        confidence=0.5,
        rationale=f"Keyword cheat sheet matched intent '{intent}'; priority from urgency word list.",
    )


def run() -> str:
    records = []
    for t in load_tickets():
        start = time.perf_counter()
        res = classify(t)
        records.append({
            "ticket_id": t.ticket_id, "prediction": res.model_dump(), "raw_output": None, "parse_error": None,
            "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            "input_tokens": 0, "output_tokens": 0, "model": "keyword_rules",
        })
    return str(write_predictions(NAME, records))


if __name__ == "__main__":
    print("wrote", run())
