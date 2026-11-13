"""Integrations behind small interfaces, so a real system can replace each file-based one without touching
the pipeline:

    crm.py           customer lookup (read-only)      SQLite (default) or JSON      -> a CRM API later
    ticket_queue.py  ticket source + write-back       CSV file (opens in Excel)     -> Zendesk/Freshdesk API later
    notifier.py      escalation notices               JSONL file (+ optional webhook) -> Slack/Teams

Factories read config/settings.yaml (`integrations`). Runtime files live in `data_dir()`.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.taxonomy import ROOT, load_settings


def data_dir() -> Path:
    """Folder for runtime integration files. TRIAGE_DATA_DIR overrides config (used by tests and operators)."""
    d = Path(os.environ.get("TRIAGE_DATA_DIR") or ROOT / load_settings()["integrations"]["dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_crm():
    from src.adapters.crm import JsonCRM, SqliteCRM
    s = load_settings()
    cfg, seed = s["integrations"]["crm"], ROOT / s["paths"]["customers"]
    if cfg["backend"] == "json":
        return JsonCRM(seed)
    if cfg["backend"] == "sqlite":
        return SqliteCRM(data_dir() / cfg["file"], seed_json=seed)
    raise ValueError(f"Unknown CRM backend {cfg['backend']!r} in config/settings.yaml (use sqlite or json).")


def get_queue():
    from src.adapters.ticket_queue import CsvTicketQueue
    cfg = load_settings()["integrations"]["ticket_queue"]
    return CsvTicketQueue(data_dir() / cfg["file"], seed=ROOT / cfg["seed"])


def get_notifier():
    from dotenv import load_dotenv

    from src.adapters.notifier import EscalationNotifier
    load_dotenv(ROOT / ".env")
    cfg = load_settings()["integrations"]["notifier"]
    return EscalationNotifier(data_dir() / cfg["file"], webhook_url=os.environ.get(cfg["webhook_env"]) or None,
                              timeout=cfg["timeout_seconds"])
