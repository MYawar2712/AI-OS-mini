import streamlit as st

import src.pipeline.run as pipeline_run
from app import labels as L
from app import ui

done = st.session_state.done
if done:
    st.session_state.done = None
    if done["fields"]:
        st.toast(f"Saved {done['ticket_id']} ({done['decision']})", icon=":material/save:")
        with st.expander(f"Written to ticket {done['ticket_id']} ({done['decision']})", icon=":material/task_alt:",
                         expanded=True):
            st.json(done["fields"])
            st.text(done["note"])
    else:
        st.info("Nothing was written; it stays for manual triage.", title=f"Ticket {done['ticket_id']} rejected",
                icon=":material/assignment_return:")

tickets = ui.all_tickets()
status = ui.reviewed_ids()
waiting = [t for t in tickets if t.ticket_id not in status]

with st.container(horizontal=True, vertical_alignment="center"):
    st.badge(f"{len(waiting)} waiting", icon=":material/hourglass_top:", color="blue")
    st.badge(f"{len(status)} reviewed", icon=":material/task_alt:", color="gray")
    show_done = st.toggle("Show reviewed tickets", key="show_done")

visible = tickets if show_done else waiting
if not visible:
    st.info("Turn on **Show reviewed tickets**, or add one on the **New ticket** page.", title="Inbox is empty",
            icon=":material/inbox:")
    st.stop()

ids = [t.ticket_id for t in visible]
if st.session_state.selected_ticket not in ids:
    st.session_state.selected_ticket = ids[0]

rows = [{"Subject": t.subject, "From": t.from_name, "Customer": ui.customer_name(t.customer_id),
         "Channel": L.CHANNEL_TEXT[t.channel], "Received": t.received_at.replace(tzinfo=None),
         "Status": {"accepted": "Accepted", "edited": "Edited", "rejected": "Rejected"}.get(status.get(t.ticket_id), "Waiting")}
        for t in visible]

list_col, detail_col = st.columns([2, 3], gap="large")
with list_col:
    event = st.dataframe(
        rows, key="inbox_table", on_select="rerun", selection_mode="single-row", hide_index=True, height=560,
        column_config={
            "Subject": st.column_config.TextColumn(width="medium", pinned=True),
            "Received": st.column_config.DatetimeColumn(format="D MMM, HH:mm"),
            "Status": st.column_config.MultiselectColumn(options=["Waiting", "Accepted", "Edited", "Rejected"],
                                                         color=["#3B82F6", "#22C55E", "#F97316", "#EF4444"]),
        },
        alt="Inbox of support tickets waiting for triage",
    )
    if event.selection.rows:
        st.session_state.selected_ticket = ids[event.selection.rows[0]]
    st.caption("Click a row to open the ticket.")

t = next(x for x in visible if x.ticket_id == st.session_state.selected_ticket)
with detail_col:
    ui.show_ticket(t)
    cached = st.session_state.result
    if cached and cached[0] == t.ticket_id:
        _, res, trace = cached
        ui.show_card(res, trace)
        ui.review_panel(t, res, trace)
    else:
        if t.ticket_id in status:
            st.caption(f"Already reviewed ({status[t.ticket_id]}). You can triage it again if needed.")
        if st.button("Triage this ticket", key="triage", type="primary", icon=":material/manage_search:"):
            with st.spinner("Reading the ticket and applying the rules (about 5–10 seconds)…"):
                try:
                    res, trace = pipeline_run.triage(t)
                except Exception as e:
                    st.error(f"{e}. Nothing was written. Try again, or triage this ticket manually.",
                             title="Triage could not finish", icon=":material/error:")
                    st.stop()
            st.session_state.result = (t.ticket_id, res, trace)
            st.session_state.mode = None
            st.rerun()
