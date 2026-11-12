"""Triage Desk: review UI for Tier-1 support (non-developers).

    streamlit run app/review.py

Inbox -> triage -> read the card -> Accept / Edit / Reject -> written to the ticket (outbox) + audit log.
Uses the same pipeline and approval code as the CLI (src/pipeline). All tickets here are SYNTHETIC.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.ui import runs_dir_label  # noqa: E402
from src.llm_client import api_key_env_var, is_configured  # noqa: E402
from src.taxonomy import load_settings  # noqa: E402

st.set_page_config(page_title="Triage Desk", page_icon=":material/support_agent:", layout="wide")

# Per-user state, initialised in one place (shared across pages).
for key, default in {"reviewer": "tier1_rep", "new_tickets": [], "selected_ticket": None, "result": None,
                     "mode": None, "done": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

PAGES = Path(__file__).parent / "app_pages"
page = st.navigation(
    [
        st.Page(PAGES / "inbox.py", title="Inbox", icon=":material/inbox:", default=True,
                help="Tickets waiting for triage. Pick one, let the assistant pre-fill the triage, then accept, edit or reject it."),
        st.Page(PAGES / "new_ticket.py", title="New ticket", icon=":material/add_circle:",
                help="Paste a customer message to add it to the inbox, for demos and quick checks. Use made-up details only."),
        st.Page(PAGES / "activity.py", title="Activity", icon=":material/monitoring:",
                help="Everything reviewed so far: accepted, edited and rejected tickets, escalations and time to decide."),
        st.Page(PAGES / "help.py", title="Help", icon=":material/help:",
                help="How the Triage Desk works, what the assistant does and never does, and what each priority means."),
    ],
    position="top",
)

with st.sidebar:
    st.text_input("Your name", key="reviewer", help="Recorded with every decision in the audit log.")
    llm = load_settings()["llm"]
    if is_configured():
        st.badge(f"Assistant ready · {llm['model']}", icon=":material/check_circle:", color="green")
    else:
        st.error(f"Add `{api_key_env_var()}` to the `.env` file (see README). Until then, tickets go to manual triage.",
                 title="Assistant not configured", icon=":material/key_off:")
    st.caption("All tickets and customers here are **synthetic** demo data.")
    st.caption(f"Decisions are saved to `{runs_dir_label()}/`.")

st.title(page.title, icon=page.icon, anchor=False)
page.run()
