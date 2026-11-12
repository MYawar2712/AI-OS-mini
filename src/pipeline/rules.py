"""Step 7: deterministic policy. Turns extracted facts + detector flags + customer context into
priority, queue and escalation, following config/taxonomy.yaml. Every rule that fires is recorded (audit).

Rule IDs used in traces:
  R-T4   churn signal -> intent cancellation_churn_risk, original intent -> secondary (tie-break T4)
  R-P1   data loss / security / core workflow down for many users with no workaround -> P1
  R-P2   single-user block, painful workaround, job today, admin lockout, payment suspension, duplicate payment, churn -> P2
  R-P4   feature request / general inquiry / out of scope with no urgency signal -> P4
  R-T2   unclear problem never below P3 (tie-break T2)
  R-M1   enterprise + technical/mobile at P3 -> P2 (context modifier M1)
  R-Q    queue = intent's default queue
  R-E*   escalation reasons (see escalation())
  R-MI   deterministic missing-info additions
  R-ACT  suggested action replaced because it proposed a financial/account action Tier-1 may not take
"""
from __future__ import annotations

import re
from typing import Optional

from src.schemas import PRIORITY_RANK, ExtractedFacts
from src.taxonomy import load_taxonomy

_P4_INTENTS = {"feature_request", "general_inquiry", "out_of_scope"}
_LEGAL_WORDS = re.compile(r"(?i)\b(gdpr|data protection|dpo|solicitor|lawyer|legal action|data breach|ico)\b")
_FORBIDDEN_ACTION = re.compile(r"(?i)\b(approve|issue|process|grant|offer|give)\b[^.]{0,30}\b(refund|credit|discount|free month)s?\b"
                               r"|\b(discount|free month)\b")
_NEGATION = re.compile(r"(?i)\b(not|never|no|don'?t|without|avoid)\b[^.]{0,25}$")


def _rank_to_p(rank: int) -> str:
    return f"P{rank}"


def adjust_intent(f: ExtractedFacts, fired: list[str]) -> tuple[str, Optional[str]]:
    intent, secondary = f.intent, f.secondary_intent
    if f.churn_signal and intent != "cancellation_churn_risk":
        secondary, intent = intent, "cancellation_churn_risk"
        fired.append("R-T4")
    if secondary == intent:
        secondary = None
    return intent, secondary


def priority(f: ExtractedFacts, intent: str, customer: Optional[dict], fired: list[str]) -> str:
    many = f.scope in ("multiple_users", "whole_team_or_company")
    if f.data_loss_or_corruption or f.security_or_unauthorised_access or (
            f.core_workflow_blocked and many and f.workaround_available is not True):
        fired.append("R-P1")
        return "P1"
    if (f.core_workflow_blocked or f.affects_job_today or f.admin_locked_out or f.payment_suspension_risk
            or f.duplicate_or_unauthorised_payment or f.churn_signal or intent == "cancellation_churn_risk"):
        rank = 2
        fired.append("R-P2")
    elif intent in _P4_INTENTS:
        rank = 4
        fired.append("R-P4")
    else:
        rank = 3
    if not f.problem_clear and rank > 3:
        rank = 3
        fired.append("R-T2")
    if (rank == 3 and customer and customer.get("plan_tier") == "enterprise"
            and intent in ("technical_issue", "mobile_app_sync")):
        rank = 2
        fired.append("R-M1")
    return _rank_to_p(rank)


def queue_for(intent: str) -> str:
    return load_taxonomy()["intents"][intent]["default_queue"]


def escalation(f: ExtractedFacts, intent: str, secondary: Optional[str], prio: str, *, customer: Optional[dict],
               injection_matches: list[str], redactions: list[str], text: str, fired: list[str]) -> list[str]:
    tax = load_taxonomy()
    reasons: list[str] = []
    if prio == "P1":
        reasons.append("p1_incident")
    if f.churn_signal or intent == "cancellation_churn_risk":
        reasons.append("churn_risk")
    if f.security_or_unauthorised_access or f.legal_or_regulatory_mention or _LEGAL_WORDS.search(text):
        reasons.append("legal_or_security")
    if secondary and tax["intents"][secondary]["default_queue"] != tax["intents"][intent]["default_queue"]:
        reasons.append("conflicting_intents")
    if customer is None:
        reasons.append("missing_account_id")
    if injection_matches or f.instructions_to_ai_detected:
        reasons.append("prompt_injection_suspected")
    if redactions:
        reasons.append("sensitive_data_present")
    if not f.problem_clear or f.confidence < tax["thresholds"]["min_confidence_auto_accept"]:
        reasons.append("low_confidence")
    if reasons:
        fired.append("R-E:" + ",".join(reasons))
    return reasons


def missing_info(f: ExtractedFacts, *, customer: Optional[dict], text: str, attachments: list[str], fired: list[str]) -> list[str]:
    out = list(dict.fromkeys(f.missing_info))
    if customer is not None and "account_id" in out:
        out.remove("account_id")  # we already know the account from the CRM lookup
        fired.append("R-MI:-account_id")
    if customer is None and "account_id" not in out:
        out.append("account_id")
        fired.append("R-MI:account_id")
    if re.search(r"(?i)\battach(ed|ment)\b", text) and not attachments and "file_sample" not in out:
        out.append("file_sample")
        fired.append("R-MI:file_sample")
    if not f.problem_clear and "clear_problem_description" not in out:
        out.append("clear_problem_description")
        fired.append("R-MI:clear_problem_description")
    return out


def safe_action(action: str, queue: str, fired: list[str]) -> str:
    for m in _FORBIDDEN_ACTION.finditer(action):
        if not _NEGATION.search(action[:m.start()]):
            fired.append("R-ACT")
            return (f"Route to {queue}. Any refund, credit, discount or account change needs approval from a "
                    f"human with authority; do not promise one to the customer.")
    return action


def under(a: str, b: str) -> bool:
    """True if priority a is LESS urgent than b."""
    return PRIORITY_RANK[a] > PRIORITY_RANK[b]
