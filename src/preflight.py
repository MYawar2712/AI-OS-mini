"""Startup check: is everything in place to run the workflow? Each problem says what to do in plain language.

    python -m scripts.check_setup      (also shown in the Triage Desk sidebar)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    message: str
    fix: str = ""
    blocking: bool = True   # False = the workflow still runs (e.g. without a key tickets go to manual triage)


def run_checks() -> list[Check]:
    out: list[Check] = []
    try:
        from src.taxonomy import load_settings, load_taxonomy
        load_taxonomy(), load_settings()
        out.append(Check("Configuration", True, "config/taxonomy.yaml and config/settings.yaml loaded."))
    except Exception as e:  # noqa: BLE001
        out.append(Check("Configuration", False, f"Could not read the config files ({e}).",
                         "Restore config/ from the repo (git checkout -- config)."))
        return out  # nothing else can work without config

    from src import adapters
    from src.llm_client import api_key_env_var, is_configured
    if is_configured():
        out.append(Check("AI assistant key", True, f"{api_key_env_var()} is set.", blocking=False))
    elif "REPLACE_ME" in os.environ.get(api_key_env_var(), ""):
        out.append(Check("AI assistant key", False, f"{api_key_env_var()} in .env still has the example value "
                         "(sk-REPLACE_ME), so every ticket goes to manual triage.",
                         f"Open .env in Notepad, replace sk-REPLACE_ME with your real key, save, then restart.",
                         blocking=False))
    else:
        out.append(Check("AI assistant key", False, f"{api_key_env_var()} is not set, so every ticket goes to "
                         "manual triage.", f"Copy .env.example to .env and paste your key after {api_key_env_var()}=.",
                         blocking=False))

    try:
        crm = adapters.get_crm()
        out.append(Check("Customer database", True, f"{len(crm.all())} customer accounts ({crm.name})."))
    except Exception as e:  # noqa: BLE001
        out.append(Check("Customer database", False, str(e), "See the message above, then restart."))

    try:
        q = adapters.get_queue()
        snap = q.read()
        waiting = len(snap.with_status("new", "ready_for_review"))
        out.append(Check("Ticket queue", True, f"{q.path.name}: {len(snap.tickets)} tickets, {waiting} waiting."))
        if snap.errors:
            out.append(Check("Ticket queue rows", False, f"{len(snap.errors)} row(s) skipped: "
                             + "; ".join(map(str, snap.errors[:3])), f"Fix those rows in {q.path.name}.",
                             blocking=False))
    except Exception as e:  # noqa: BLE001
        out.append(Check("Ticket queue", False, str(e), "See the message above."))

    try:
        from src.pipeline import handoff
        d = handoff.runs_dir()
        probe = d / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        out.append(Check("Audit log folder", True, f"{d.name}/ is writable."))
    except OSError as e:
        out.append(Check("Audit log folder", False, f"Cannot write decisions ({e}).",
                         "Make sure the project folder is not read-only."))

    hook = load_settings()["integrations"]["notifier"]["webhook_env"]
    out.append(Check("Escalation notices", True, "Saved to escalations.jsonl"
                     + (" and posted to the webhook." if os.environ.get(hook) else
                        f" (optional: set {hook} in .env to also post to Slack/Teams)."), blocking=False))
    return out
