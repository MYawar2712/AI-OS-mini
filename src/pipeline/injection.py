"""Step 3: deterministic prompt-injection detector.

Pattern-based, so it works even if the LLM is fooled. Any match -> escalation `prompt_injection_suspected`.
The ticket text is still triaged; the instructions inside it are never followed (they only ever reach the
LLM as delimited, untrusted data, and the LLM cannot set priority/queue/escalation anyway: ADR-017).
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_instructions", re.compile(r"(?i)\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|all|earlier)\b.{0,20}\b(instructions?|rules|prompts?)\b")),
    ("system_note", re.compile(r"(?i)\b(system|developer)\s*(note|prompt|message|instruction)s?\b")),
    ("addressed_to_ai", re.compile(r"(?i)\b(note|message|instruction)s?\s+(for|to)\s+(the\s+)?(ai|assistant|bot|model|triage)\b")),
    ("ai_assistant_mention", re.compile(r"(?i)\b(ai|llm)\s+(assistant|model|system)\b")),
    ("role_override", re.compile(r"(?i)\byou are now\b|\bact as\b|\bnew instructions\b")),
    ("set_triage_fields", re.compile(r"(?i)\b(mark|set|classify|label|route)\b.{0,25}\b(this|ticket|priority|escalat\w*|as)\b.{0,25}\b(P[1-4]|feature_request|false|not escalate)\b")),
    ("do_not_escalate", re.compile(r"(?i)\bdo not escalate\b|\bdon'?t escalate\b|\bescalate\s*(=|to)\s*false\b")),
    ("html_comment", re.compile(r"<!--.*?-->", re.S)),
]


def detect_injection(text: str) -> list[str]:
    """Return the names of matched patterns (empty list = nothing suspicious)."""
    return [name for name, pat in _PATTERNS if pat.search(text)]
