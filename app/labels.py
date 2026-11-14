"""Plain-language labels for the review UI. Codes stay in data/contracts; people see these words."""
from __future__ import annotations

from src.taxonomy import load_taxonomy

INTENT = {
    "technical_issue": "Technical problem", "mobile_app_sync": "Mobile app not syncing",
    "billing_invoice": "Invoice / billing question", "payment_failure": "Payment failing",
    "scheduling_dispatch": "Scheduling / dispatch", "account_access": "Login / access",
    "data_import_export": "Data import / export", "feature_request": "Feature request",
    "cancellation_churn_risk": "Cancellation / churn risk", "general_inquiry": "General question",
    "out_of_scope": "Not something we support",
}
QUEUE = {
    "tier1_general": "Tier-1 support desk", "tier2_technical": "Tier-2 technical team", "billing": "Billing team",
    "customer_success_retention": "Customer Success (retention)", "onboarding_data": "Onboarding & data team",
    "product": "Product feedback",
}
PRIORITY = {  # label, colour, emoji
    "P1": ("Critical", "#c0392b", "🔴"), "P2": ("High", "#d35400", "🟠"),
    "P3": ("Normal", "#2c5cc5", "🔵"), "P4": ("Low", "#7f8c8d", "⚪"),
}
REASON = {
    "p1_incident": "Critical incident (P1): a lead must act now",
    "churn_risk": "Customer may cancel or not renew: tell Customer Success today",
    "legal_or_security": "Legal or security concern",
    "conflicting_intents": "Two separate problems for different teams",
    "missing_account_id": "Customer account not identified",
    "prompt_injection_suspected": "Ticket contains instructions aimed at the AI (ignored, please check)",
    "sensitive_data_present": "Card details or a password were pasted in (hidden from the AI)",
    "low_confidence": "Ticket is unclear or the assistant is unsure",
}
RULE = {
    "R-P1": "Priority set to P1: data loss, security issue, or many users blocked with no workaround",
    "R-P2": "Priority set to P2: one user blocked, a job affected today, admin locked out, payment/churn risk",
    "R-P4": "Priority set to P4: request or question with no urgency",
    "R-C1": "Many users affected, a job today is hit and there is no workaround, so the work is treated as blocked",
    "R-T2": "Unclear ticket kept at P3 or higher (never dropped to Low)",
    "R-T4": "Cancellation threat made the main category; the original problem kept as second category",
    "R-M1": "Enterprise customer: normal technical issue raised to High",
    "R-Q": "Team chosen from the category",
    "R-ACT": "Suggested step replaced: refunds/credits/discounts need someone with authority",
    "FALLBACK": "Automatic triage failed, so this ticket goes to manual triage",
}
CHANNEL_TEXT = {"email": "Email", "portal": "Portal", "chat": "Chat", "phone_note": "Phone note"}
CHANNEL_ICON = {"email": ":material/mail:", "portal": ":material/language:", "chat": ":material/chat:",
                "phone_note": ":material/call:"}


def missing(code: str) -> str:
    return load_taxonomy()["missing_info_fields"].get(code, code)


def rule(code: str) -> str:
    if code.startswith("R-E:"):
        return "Needs a lead because: " + ", ".join(code[4:].split(","))
    if code.startswith("R-MI:-"):
        return f"Not asking for '{code[6:]}' (already known)"
    if code.startswith("R-MI:"):
        return f"Added to 'ask the customer': {code[5:]}"
    return RULE.get(code, code)
