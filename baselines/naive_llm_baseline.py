"""Baseline 2 — "simple ChatGPT-style use": one prompt, free-text answer.

Deliberately naive, to represent what a rep gets by pasting a ticket into a chat assistant:
  * no JSON schema / structured output enforcement
  * no customer context enrichment, no KB, no taxonomy definitions or rules
  * no validation or retry
The label NAMES are given (otherwise the output cannot be scored at all), but not their definitions.
Free text is parsed with best-effort regexes; unparseable fields make the record schema-invalid.

If the provider API key (config llm.api_key_env, e.g. DASHSCOPE_API_KEY) is not set, the run is skipped and recorded as "not_run" — results are never faked.

    python -m baselines.naive_llm_baseline
"""
from __future__ import annotations

import json
import re

from baselines.common import load_tickets, results_path, write_predictions
from src.llm_client import LLMCallError, api_key_env_var, call_llm, is_configured
from src.schemas import InboundTicket
from src.taxonomy import load_settings, load_taxonomy

NAME = "naive_llm_baseline"
STATUS_PATH = results_path(NAME).with_name(f"{NAME}_status.json")

PROMPT = """You are a helpful support assistant. Triage this support ticket.

Tell me:
- Intent (one of: {intents})
- Priority (P1, P2, P3 or P4)
- Queue (one of: {queues})
- Escalate (yes/no) and why
- Missing information, if any
- A short summary
- Suggested next action

Ticket:
Subject: {subject}
{body}
"""

# Best-effort mapping of free-text escalation reasons to the taxonomy enum.
_REASON_HINTS = {
    "churn_risk": ["churn", "cancel", "renew", "switch", "leaving", "retention"],
    "legal_or_security": ["legal", "security", "breach", "gdpr"],
    "p1_incident": ["p1", "critical", "outage", "major incident"],
    "conflicting_intents": ["multiple issues", "two issues", "both", "multi"],
    "missing_account_id": ["account id", "no account", "unidentified", "customer id"],
    "prompt_injection_suspected": ["injection", "instruction", "manipulat", "suspicious note", "untrusted", "system note"],
    "sensitive_data_present": ["card details", "card number", "card data", "pci", "sensitive", "pii", "cvv"],
    "low_confidence": ["unclear", "vague", "insufficient", "not enough information"],
}
_MISSING_HINTS = {
    "account_id": ["account id", "account number", "customer id"],
    "affected_users_count": ["how many users", "number of users", "how many engineers"],
    "device_and_app_version": ["app version", "device"],
    "error_message_or_screenshot": ["error message", "screenshot"],
    "invoice_number": ["invoice number"],
    "job_or_visit_reference": ["job number", "job reference", "visit reference", "job id"],
    "file_sample": ["file", "sample", "attachment"],
    "steps_to_reproduce": ["steps to reproduce", "reproduce"],
    "clear_problem_description": ["what is broken", "description", "more detail", "details of the issue", "what exactly", "symptom"],
}


def _field(text: str, label: str) -> str | None:
    m = re.search(rf"(?im)^\W*{label}\W*[:\-]\s*(.+)$", text)
    return m.group(1).strip() if m else None


_HEADINGS = ("intent", "priority", "queue", "escalat", "missing", "summary", "suggested")
_LABEL_LINE = re.compile(r"^\s*(?:[-*#]+\s*)?\**\s*([A-Za-z][A-Za-z /()-]{1,40}?)\s*\**\s*:\s*\**\s*(.*)$")


def _sections(text: str) -> dict[str, str]:
    """Split free text into {label (lower-case): body}. A section starts at any line like
    '- **Missing information:** ...' / 'Escalate: yes' and runs until the next such line."""
    out: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        m = _LABEL_LINE.match(line)
        # Only the answer's own headings start a section; nested bullets like "- Account details: ..." stay inside it.
        if m and any(k in m.group(1).lower() for k in _HEADINGS):
            current = m.group(1).strip().lower()
            out[current] = m.group(2).strip()
        elif current:
            out[current] += "\n" + line.strip()
    return out


def _section(text: str, label: str) -> str:
    """Body of the first section whose label contains `label` (e.g. 'escalat' matches 'Escalate', 'summary' matches 'Short summary')."""
    return next((body.strip() for name, body in _sections(text).items() if label in name), "")


def parse_free_text(ticket: InboundTicket, text: str) -> tuple[dict | None, str | None]:
    tax = load_taxonomy()
    low = text.lower()
    intent = next((i for i in tax["intents"] if re.search(rf"intent\W*[:\-][^\n]*\b{i}\b", low)), None)
    if intent is None:  # fall back: first label mentioned anywhere
        intent = next((i for i in tax["intents"] if i in low), None)
    pm = re.search(r"priority\W*[:\-][^\n]*?\b(P[1-4])\b", text, re.I)
    queue = next((q for q in tax["queues"] if re.search(rf"queue\W*[:\-][^\n]*\b{q}\b", low)), None)
    em = re.search(r"escalat\w*\W*[:\-]?\W*(yes|no)\b", low)
    missing_errs = [n for n, v in [("intent", intent), ("priority", pm), ("queue", queue), ("escalate", em)] if v is None]
    if missing_errs:
        return None, f"could not parse: {', '.join(missing_errs)}"
    escalate = em.group(1) == "yes"
    esc_text = _section(text, "escalat").lower()
    reasons = [r for r, hints in _REASON_HINTS.items() if any(h in esc_text for h in hints)] if escalate else []
    # Taxonomy rule: an escalated P1 is a p1_incident escalation, whatever words the model used (rubric rev 3).
    if escalate and pm.group(1).upper() == "P1" and "p1_incident" not in reasons:
        reasons.append("p1_incident")
    if escalate and not reasons:
        reasons = ["low_confidence"]  # unmapped free-text reason; documented in eval/rubric.md
    miss_text = _section(text, "missing").lower()
    missing = [] if re.match(r"^\W*(none|n/a|no\b)", miss_text) else [m for m, hints in _MISSING_HINTS.items() if any(h in miss_text for h in hints)]
    return {
        "ticket_id": ticket.ticket_id, "intent": intent, "secondary_intent": None, "priority": pm.group(1).upper(),
        "queue": queue, "escalate": escalate, "escalation_reasons": reasons, "missing_info": missing,
        "summary": (_section(text, "summary") or text)[:800],
        "suggested_next_action": (_section(text, "suggested next action") or "n/a")[:500],
        "confidence": 0.5, "rationale": "naive free-text baseline (no rationale field requested)",
    }, None


def run() -> str:
    s = load_settings()["llm"]
    if not is_configured():
        status = {"baseline": NAME, "status": "not_run", "reason": f"{api_key_env_var()} not set in .env",
                  "provider": s["provider"], "model": s["model"]}
        STATUS_PATH.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        results_path(NAME).unlink(missing_ok=True)  # never leave stale predictions behind
        print(f"[naive_llm_baseline] SKIPPED: {status['reason']}. Recorded as not_run (no results fabricated).")
        return "not_run"

    tax = load_taxonomy()
    records = []
    for t in load_tickets():
        prompt = PROMPT.format(intents=", ".join(tax["intents"]), queues=", ".join(tax["queues"]),
                               subject=t.subject, body=t.body)
        rec = {"ticket_id": t.ticket_id, "model": s["model"], "input_tokens": 0, "output_tokens": 0, "latency_ms": None}
        try:
            r = call_llm(prompt)
            rec.update(input_tokens=r.input_tokens, output_tokens=r.output_tokens, latency_ms=r.latency_ms, raw_output=r.text)
            pred, err = parse_free_text(t, r.text)
            rec.update(prediction=pred, parse_error=err)
        except LLMCallError as e:
            rec.update(prediction=None, raw_output=None, parse_error=f"api_error: {e}")
        records.append(rec)
        print(f"  {t.ticket_id}: {'ok' if rec.get('prediction') else 'FAILED - ' + str(rec.get('parse_error'))}")
    STATUS_PATH.write_text(json.dumps({"baseline": NAME, "status": "run", "provider": s["provider"], "model": s["model"],
                                       "n": len(records)}, indent=2) + "\n", encoding="utf-8")
    return str(write_predictions(NAME, records))


def reparse(path=None) -> str:
    """Re-run the parser over saved raw outputs (no API calls, no cost). Use after parser fixes.
    `path` defaults to the current predictions file; pass an archived file to re-parse an older model's run."""
    path = path or results_path(NAME)
    if not path.exists():
        return "not_run"
    tickets = {t.ticket_id: t for t in load_tickets()}
    records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for rec in records:
        if rec.get("raw_output"):
            pred, err = parse_free_text(tickets[rec["ticket_id"]], rec["raw_output"])
            rec.update(prediction=pred, parse_error=err)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    import sys

    print(reparse() if "--reparse" in sys.argv else run())
