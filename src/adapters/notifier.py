"""Integration #3: escalation notices for tickets a rep approved as "needs a lead".

Always appends one line to data/integrations/escalations.jsonl (the leads' feed, also shown in the UI).
If ESCALATION_WEBHOOK_URL is set in .env, also posts a short message to that Slack/Teams incoming webhook.
A webhook failure never blocks the triage: it is reported back and the file record still exists.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.schemas import ReviewDecision, TriageResult


@dataclass
class NotifyResult:
    delivered_to: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def message_text(final: TriageResult, review: ReviewDecision) -> str:
    return (f":rotating_light: {final.priority} escalation for ticket {final.ticket_id} (synthetic demo)\n"
            f"Reasons: {', '.join(final.escalation_reasons)}\nTeam: {final.queue}\nSummary: {final.summary}\n"
            f"Approved by {review.reviewer}")


class EscalationNotifier:
    def __init__(self, path: Path, webhook_url: Optional[str] = None, timeout: float = 5):
        self.path, self.webhook_url, self.timeout = Path(path), webhook_url, timeout

    def notify(self, final: TriageResult, review: ReviewDecision) -> NotifyResult:
        out = NotifyResult()
        if not final.escalate:
            return out
        rec = {"sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ticket_id": final.ticket_id,
               "priority": final.priority, "queue": final.queue, "reasons": final.escalation_reasons,
               "summary": final.summary, "approved_by": review.reviewer, "synthetic": True}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.delivered_to.append(self.path.name)
        if self.webhook_url:
            body = json.dumps({"text": message_text(final, review)}).encode()
            req = urllib.request.Request(self.webhook_url, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp.read()
                out.delivered_to.append("webhook")
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                out.errors.append(f"Webhook not delivered ({e}). The escalation is still in {self.path.name}; "
                                  "check ESCALATION_WEBHOOK_URL in .env.")
        return out

    def recent(self, limit: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        lines = [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]][::-1]
