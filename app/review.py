"""Triage Desk: review UI for Tier-1 support (non-developers).

    streamlit run app/review.py

Ticket queue (CSV) -> Process new tickets -> read the card -> Accept / Edit / Reject
-> written back to the ticket + escalation notice + audit log.
Uses the same pipeline and approval code as the CLI (src/pipeline). All tickets here are SYNTHETIC.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.ui import path_label  # noqa: E402
from src import adapters  # noqa: E402
from src.pipeline import handoff  # noqa: E402
from src.preflight import run_checks  # noqa: E402
from src.taxonomy import load_settings  # noqa: E402

st.set_page_config(page_title="Triage Desk", page_icon=":material/support_agent:", layout="wide")

# Per-user state, initialised in one place (shared across pages).
for key, default in {"reviewer": "tier1_rep", "selected_ticket": None, "retriage": None, "mode": None,
                     "done": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

PAGES = Path(__file__).parent / "app_pages"
page = st.navigation(
    [
        st.Page(PAGES / "inbox.py", title="Inbox", icon=":material/inbox:", default=True,
                help="Tickets waiting for triage. Pick one, let the assistant pre-fill the triage, then accept, edit or reject it."),
        st.Page(PAGES / "new_ticket.py", title="New ticket", icon=":material/add_circle:",
                help="Add a customer message to the ticket queue, for demos and quick checks. Use made-up details only."),
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
    checks = run_checks()
    problems = [c for c in checks if not c.ok]
    if all(c.ok for c in checks if c.name == "AI assistant key"):
        st.badge(f"Assistant ready · {llm['model']}", icon=":material/check_circle:", color="green")
    for c in problems:
        (st.error if c.blocking else st.warning)(f"{c.message}\n\n**What to do:** {c.fix}", title=c.name,
                                                 icon=":material/error:" if c.blocking else ":material/warning:")
    st.caption("All tickets and customers here are **synthetic** demo data.")
    st.caption(f"Tickets: `{path_label(adapters.data_dir())}/` · decisions: `{path_label(handoff.runs_dir())}/`")

if any(not c.ok and c.blocking for c in checks):
    st.error("Fix the problem shown in the sidebar, then refresh the page.", title="The Triage Desk can't start",
             icon=":material/error:")
    st.stop()
st.title(page.title, icon=page.icon, anchor=False)
page.run()
