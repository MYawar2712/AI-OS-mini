"""Loads config/taxonomy.yaml and config/settings.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def load_taxonomy(path: str | None = None) -> dict:
    return yaml.safe_load((Path(path) if path else ROOT / "config" / "taxonomy.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def load_settings(path: str | None = None) -> dict:
    return yaml.safe_load((Path(path) if path else ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def default_queue(intent: str) -> str:
    return load_taxonomy()["intents"][intent]["default_queue"]
