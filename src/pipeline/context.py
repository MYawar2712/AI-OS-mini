"""Step 4: customer context lookup (read-only).

v0: reads the synthetic CRM file. Day 3 replaces this with an adapter interface (same return type) so a real
CRM API can be plugged in. Customer context is used ONLY by the deterministic rules; it is not sent to the LLM
(data minimisation, design doc §6).
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from src.taxonomy import ROOT, load_settings


@lru_cache(maxsize=1)
def _customers() -> dict[str, dict]:
    data = json.loads((ROOT / load_settings()["paths"]["customers"]).read_text(encoding="utf-8"))
    return {c["customer_id"]: c for c in data["records"]}


def lookup_customer(customer_id: Optional[str]) -> Optional[dict]:
    if not customer_id:
        return None
    return _customers().get(customer_id)
