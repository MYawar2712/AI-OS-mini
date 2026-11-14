import streamlit as st

import src.pipeline.run as pipeline_run
from app import labels as L
from app import ui
from src import adapters
from src.pipeline import batch, proposals

# ---------------------------------------------------------------- confirmation of the last decision
done = st.session_state.done
if done:
    st.session_state.done = None
    where = f"`{done['queue_file']}`" if done["written_back"] else "the outbox log (ticket not in the queue file)"
    if done["fields"]:
        st.toast(f"Saved {done['ticket_id']} ({done['decision']})", icon=":material/save:")
        with st.expander(f"Written to ticket {done['ticket_id']} in {where} ({done['decision']})",
                         icon=":material/task_alt:", expanded=True):
            if done["notified"]:
                st.markdown(f":material/notification_important: Escalation notice sent to: {', '.join(done['notified'])}")
            st.json(done["fields"])
            st.text(done["note"])
    else:
        st.info(f"No triage fields were written; the ticket is marked **Manual triage** in {where}.",
                title=f"Ticket {done['ticket_id']} rejected", icon=":material/assignment_return:")
    for w in done["warnings"]:
        st.warning(w, title="Escalation notice partly delivered", icon=":material/wifi_off:")

report = st.session_state.pop("batch_report", None)
if report:
    msg = (f"{len(report.ready)} ready for review ({len(report.escalate)} need a lead), "
           f"{len(report.fallback)} sent to manual triage, in {report.seconds:.0f} s.")
    (st.warning if report.failed else st.success)(msg, title=f"Processed {report.found} new ticket(s)",
                                                  icon=":material/bolt:")
    for tid, err in report.failed.items():
        st.error(f"{err} It stays **New**; press the button again to retry.", title=f"{tid} not processed",
                 icon=":material/error:")

# ---------------------------------------------------------------- queue
try:
    snap = ui.queue_snapshot()
except Exception as e:  # noqa: BLE001 - shown in plain language
    ui.show_error(e)
    st.stop()
if snap.errors:
    st.warning("\n".join(f"- {e}" for e in snap.errors[:5]),
               title=f"{len(snap.errors)} row(s) in the ticket file could not be read and were skipped",
               icon=":material/rule:")

suggested = proposals.load_all()
status = {tid: ui.STATUS_TEXT[s] for tid, s in snap.status.items()}
new = snap.with_status("new")
waiting = snap.with_status("new", "ready_for_review")

with st.container(horizontal=True, vertical_alignment="center"):
    st.badge(f"{len(new)} new", icon=":material/fiber_new:", color="blue")
    st.badge(f"{len(waiting) - len(new)} ready for review", icon=":material/fact_check:", color="violet")
    st.badge(f"{len(snap.tickets) - len(waiting)} done", icon=":material/task_alt:", color="gray")
    show_done = st.toggle("Show done tickets", key="show_done")
    if st.button(f"Process new tickets ({len(new)})", key="process", icon=":material/bolt:", disabled=not new,
                 help="The assistant pre-fills the triage for every New ticket. Nothing is written to a ticket until "
                      "you approve it."):
        with st.status(f"Triaging {len(new)} ticket(s)…", expanded=True) as box:
            bar = st.progress(0.0)
            report = batch.process_new(on_progress=lambda d, n, tid: bar.progress(d / n, text=f"{d}/{n} · {tid}"))
            box.update(label="Done", state="complete")
        st.session_state.batch_report = report
        st.rerun()

visible = snap.tickets if show_done else waiting
if not visible:
    st.info("Turn on **Show done tickets**, or add one on the **New ticket** page.", title="Nothing waiting",
            icon=":material/inbox:")
    st.stop()



def _rank(t) -> tuple:
    """Riskiest first: suggested priority (P1 > P2 ...), needs-a-lead first, then oldest. Unprocessed tickets last."""
    sug = suggested.get(t.ticket_id) if snap.status[t.ticket_id] == "ready_for_review" else None
    if not sug:
        return (9, 1, t.received_at)
    return (int(sug[0].priority[1]), 0 if sug[0].escalate else 1, t.received_at)


FILTERS = {"All": lambda t, r: True,
           "Needs a lead": lambda t, r: bool(r and r.escalate),
           "P1 / P2": lambda t, r: bool(r and r.priority in ("P1", "P2")),
           "Low confidence": lambda t, r: bool(r and r.confidence < ui.TAX["thresholds"]["min_confidence_auto_accept"]),
           "Not processed": lambda t, r: r is None}
choice = st.segmented_control("Show", list(FILTERS), default="All", key="inbox_filter", required=True,
                              label_visibility="collapsed")


def _ready(t):
    return suggested[t.ticket_id][0] if t.ticket_id in suggested and snap.status[t.ticket_id] == "ready_for_review" else None


visible = sorted((t for t in visible if FILTERS[choice](t, _ready(t))), key=_rank)
if not visible:
    st.info(f"No tickets match **{choice}**. Choose **All** to see everything waiting.", title="Nothing here",
            icon=":material/filter_alt_off:")
    st.stop()
ids = [t.ticket_id for t in visible]
if st.session_state.selected_ticket not in ids:
    st.session_state.selected_ticket = ids[0]


def _suggestion(tid: str) -> str:
    if tid not in suggested or snap.status[tid] != "ready_for_review":
        return ""
    r = suggested[tid][0]
    return f"{r.priority}{' · lead' if r.escalate else ''}"


rows = [{"Subject": t.subject, "From": t.from_name, "Customer": ui.customer_name(t.customer_id),
         "Channel": L.CHANNEL_TEXT[t.channel], "Received": t.received_at.replace(tzinfo=None),
         "Suggested": _suggestion(t.ticket_id), "Status": status[t.ticket_id]} for t in visible]

list_col, detail_col = st.columns([2, 3], gap="large")
with list_col:
    event = st.dataframe(
        rows, key="inbox_table", on_select="rerun", selection_mode="single-row", hide_index=True, height=560,
        column_config={
            "Subject": st.column_config.TextColumn(width="medium", pinned=True),
            "Received": st.column_config.DatetimeColumn(format="D MMM, HH:mm"),
            "Suggested": st.column_config.TextColumn(help="Priority pre-filled by the assistant; 'lead' = needs a lead"),
            "Status": st.column_config.MultiselectColumn(options=list(ui.STATUS_COLOR),
                                                         color=list(ui.STATUS_COLOR.values())),
        },
        alt="Ticket queue: tickets waiting for triage",
    )
    if event.selection.rows:
        st.session_state.selected_ticket = ids[event.selection.rows[0]]
    st.caption(f"Riskiest first: P1 and tickets that need a lead are at the top. Click a row to open it. Source: `{ui.path_label(adapters.get_queue().path)}`")

t = next(x for x in visible if x.ticket_id == st.session_state.selected_ticket)
with detail_col:
    ui.show_ticket(t)
    s = snap.status[t.ticket_id]
    proposal = suggested.get(t.ticket_id) if s == "ready_for_review" or st.session_state.retriage == t.ticket_id else None
    if proposal:
        res, trace = proposal
        ui.show_card(res, trace)
        ui.review_panel(t, res, trace)
    else:
        if s in ("triaged", "manual_triage"):
            row = snap.rows[t.ticket_id]
            st.info(f"{status[t.ticket_id]} by {row['triaged_by'] or 'unknown'} at {row['triaged_at'][:16].replace('T', ' ')}."
                    + (f" Priority {row['priority']}, team {L.QUEUE.get(row['queue'], row['queue'])}." if row["priority"] else ""),
                    title="Already done", icon=":material/task_alt:")
        if st.button("Triage this ticket" if s == "new" else "Triage it again", key="triage", type="primary",
                     icon=":material/manage_search:"):
            with st.spinner("Reading the ticket and applying the rules (a few seconds)…"):
                try:
                    res, trace = pipeline_run.triage(t)
                    proposals.save(res, trace)
                    if s == "new":
                        adapters.get_queue().set_status(t.ticket_id, "ready_for_review")
                except Exception as e:  # noqa: BLE001
                    ui.show_error(e)
                    st.stop()
            st.session_state.retriage = t.ticket_id
            st.session_state.mode = None
            st.rerun()
