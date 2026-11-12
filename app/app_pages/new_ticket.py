from datetime import datetime, timezone

import streamlit as st

from app import labels as L
from src.pipeline.context import _customers
from src.schemas import InboundTicket

st.caption("Paste a customer message to add it to the inbox. Use made-up details only: this is a demo.")
custs = _customers()

with st.form("new_ticket", clear_on_submit=True):
    subject = st.text_input("Subject")
    body = st.text_area("Message", height=180)
    with st.container(horizontal=True):
        sender = st.text_input("From (name)", value="Customer")
        channel = st.segmented_control("Channel", list(L.CHANNEL_TEXT), default="email", required=True,
                                       format_func=lambda x: f"{L.CHANNEL_ICON[x]} {L.CHANNEL_TEXT[x]}")
    cid = st.selectbox("Customer account", ["(unknown sender)", *custs],
                       format_func=lambda x: x if x.startswith("(") else f"{x} · {custs[x]['company_name']}")
    submitted = st.form_submit_button("Add to inbox", type="primary", icon=":material/add:")

if submitted:
    if not subject.strip() or not body.strip():
        st.error("Please fill in both the subject and the message.", title="Missing details", icon=":material/error:")
    else:
        n = len(st.session_state.new_tickets) + 1
        ticket = InboundTicket(ticket_id=f"SYN-NEW-{datetime.now():%H%M%S}-{n}", received_at=datetime.now(timezone.utc),
                               channel=channel, from_name=sender or "Customer", subject=subject.strip(),
                               body=body.strip(), customer_id=None if cid.startswith("(") else cid)
        st.session_state.new_tickets.append(ticket.model_dump(mode="json"))
        st.session_state.selected_ticket = ticket.ticket_id
        st.success("It's selected in the inbox, ready to triage.", title="Ticket added", icon=":material/check_circle:")
        st.page_link("app_pages/inbox.py", label="Open the inbox", icon=":material/inbox:")
