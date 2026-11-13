"""Step 4: customer context lookup (read-only), through the CRM adapter (src/adapters/crm.py).

Customer context is used ONLY by the deterministic rules; it is not sent to the LLM (data minimisation,
design doc §6).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from src import adapters


@lru_cache(maxsize=1)
def _customers() -> dict[str, dict]:
    """All customers, for display lists in the UI (cached; the per-ticket lookup below always queries the CRM)."""
    return adapters.get_crm().all()


def lookup_customer(customer_id: Optional[str]) -> Optional[dict]:
    if not customer_id:
        return None
    return adapters.get_crm().get(customer_id)
