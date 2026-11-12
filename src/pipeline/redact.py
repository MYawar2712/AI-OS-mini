"""Step 2: detect and redact secrets BEFORE any text leaves our process (privacy boundary).

Deterministic, no LLM. Redacts payment card numbers (Luhn-checked), CVV, card expiry, and passwords.
Names and email addresses are kept: triage needs them, and this repo uses synthetic data only (see design doc §6).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_CVV = re.compile(r"(?i)\b(cvv|cvc|security code)\s*[:=]?\s*\d{3,4}\b")
_EXPIRY = re.compile(r"(?i)\b(exp(?:iry|ires)?\.?)\s*[:=]?\s*(0[1-9]|1[0-2])\s*/\s*\d{2,4}\b")
_PASSWORD = re.compile(r"(?i)\b(password|passwd|pwd|passcode)(\s+is|\s*[:=])\s*(\S+)")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


@dataclass
class RedactionResult:
    text: str
    kinds: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.kinds)


def redact(text: str) -> RedactionResult:
    kinds: list[str] = []

    def card_sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            kinds.append("card_number")
            return "[REDACTED_CARD]"
        return m.group(0)

    out = _CARD.sub(card_sub, text)
    if _CVV.search(out):
        kinds.append("cvv")
        out = _CVV.sub(lambda m: f"{m.group(1)} [REDACTED_CVV]", out)
    if _EXPIRY.search(out):
        kinds.append("card_expiry")
        out = _EXPIRY.sub(lambda m: f"{m.group(1)} [REDACTED_EXPIRY]", out)
    if _PASSWORD.search(out):
        kinds.append("password")
        out = _PASSWORD.sub(lambda m: f"{m.group(1)}{m.group(2)} [REDACTED_SECRET]", out)
    return RedactionResult(text=out, kinds=sorted(set(kinds)))
