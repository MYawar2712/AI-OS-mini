"""Shared helpers for baselines: loading tickets and writing prediction records."""
from __future__ import annotations

import json
from pathlib import Path

from src.schemas import InboundTicket, load_test_cases
from src.taxonomy import ROOT, load_settings


def load_tickets() -> list[InboundTicket]:
    return [c.ticket for c in load_test_cases(ROOT / load_settings()["paths"]["test_cases"])]


def results_path(name: str) -> Path:
    d = ROOT / load_settings()["paths"]["results_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}_predictions.jsonl"


def write_predictions(name: str, records: list[dict]) -> Path:
    p = results_path(name)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    return p
