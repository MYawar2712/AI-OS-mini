import streamlit as st

from app import labels as L
from app import ui
from src import adapters

rows = ui.audit_rows()
if not rows:
    st.info("Decisions appear here after you accept, edit or reject a ticket in the inbox.", title="Nothing reviewed yet",
            icon=":material/monitoring:")
    st.stop()

decisions = [r["review"]["decision"] for r in rows]
secs = sorted(r["review"]["seconds_to_decide"] for r in rows if r["review"].get("seconds_to_decide") is not None)
escalated = sum(r["final"]["escalate"] for r in rows)
fallbacks = sum(r["trace"]["status"] == "fallback" for r in rows)

with st.grid(5):
    st.metric("Reviewed", len(rows), border=True)
    st.metric("Accepted as-is", f"{decisions.count('accepted') / len(rows):.0%}", border=True,
              help="Share of tickets where the rep accepted the pre-filled triage without changes.")
    st.metric("Edited", decisions.count("edited"), border=True)
    st.metric("Rejected", decisions.count("rejected"), border=True)
    st.metric("Median time to decide", f"{secs[len(secs) // 2]:.0f} s" if secs else "n/a", border=True)

st.caption(f"Escalated to a lead: {escalated} · Sent to manual triage by the assistant: {fallbacks}")

table = [{"When": r["logged_at"][:19].replace("T", " "), "Ticket": r["review"]["ticket_id"],
          "Decision": r["review"]["decision"].capitalize(), "Priority": r["final"]["priority"],
          "Team": L.QUEUE[r["final"]["queue"]], "Lead needed": r["final"]["escalate"],
          "Changed": ", ".join(r["review"]["edited_fields"]) or "", "Reviewer": r["review"]["reviewer"],
          "Comment": r["review"].get("comment", "")} for r in reversed(rows)]
st.dataframe(
    table, hide_index=True,
    column_config={
        "Decision": st.column_config.MultiselectColumn(options=["Accepted", "Edited", "Rejected"],
                                                       color=["#22C55E", "#F97316", "#EF4444"]),
        "Lead needed": st.column_config.CheckboxColumn(),
    },
    alt="Table of every triage decision, newest first",
)

st.subheader("Escalation notices sent to leads", anchor=False)
notifier = adapters.get_notifier()
sent = notifier.recent()
if not sent:
    st.caption("None yet. A notice is sent when you approve a ticket that needs a lead.")
else:
    st.dataframe([{"Sent": s["sent_at"][:16].replace("T", " "), "Ticket": s["ticket_id"], "Priority": s["priority"],
                   "Team": L.QUEUE.get(s["queue"], s["queue"]), "Why": ", ".join(L.REASON.get(r, r) for r in s["reasons"]),
                   "Approved by": s["approved_by"]} for s in sent], hide_index=True,
                 alt="Escalation notices, newest first")
    st.caption(f"Source: `{ui.path_label(notifier.path)}`"
               + (" · also posted to the webhook" if notifier.webhook_url else ""))
