"""Shared logic and UI pieces for the Triage Desk pages (pages stay direct scripts)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import streamlit as st

from app import labels as L
from src import adapters
from src.adapters.ticket_queue import QueueSnapshot
from src.observability import friendly_error, trace_url, tracing_enabled
from src.pipeline.context import _customers
import src.pipeline.handoff as handoff  # module import: always use the current save location
from src.schemas import InboundTicket, ReviewDecision
from src.taxonomy import ROOT, load_taxonomy

TAX = load_taxonomy()
PRIORITY_BADGE = {"P1": ("red", ":material/emergency:"), "P2": ("orange", ":material/priority_high:"),
                  "P3": ("blue", ":material/flag:"), "P4": ("gray", ":material/low_priority:")}


# ---------------------------------------------------------------- data
STATUS_TEXT = {"new": "New", "ready_for_review": "Ready for review", "triaged": "Triaged",
               "manual_triage": "Manual triage"}
STATUS_COLOR = {"New": "#3B82F6", "Ready for review": "#8B5CF6", "Triaged": "#22C55E", "Manual triage": "#EF4444"}


def queue_snapshot() -> QueueSnapshot:
    """Read the live ticket queue (CSV) every rerun, so edits made in Excel show up straight away."""
    return adapters.get_queue().read()


def audit_rows() -> list[dict]:
    p = handoff.runs_dir() / "audit.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def show_error(e: BaseException) -> None:
    title, what = friendly_error(e)
    st.error(what, title=title, icon=":material/error:")

def customer_name(cid: str | None) -> str:
    c = _customers().get(cid or "")
    return c["company_name"].replace(" (Synthetic)", "") if c else "Unknown sender"


def path_label(d) -> str:
    """Path shown to the rep: relative inside the project, folder/file name only outside it."""
    return d.relative_to(ROOT).as_posix() if d.is_relative_to(ROOT) else d.name


# ---------------------------------------------------------------- display
def show_ticket(t: InboundTicket) -> None:
    st.subheader(t.subject, anchor=False)
    st.caption(f"{L.CHANNEL_TEXT.get(t.channel, t.channel)} · from {t.from_name}"
               + (f" <{t.from_email}>" if t.from_email else "")
               + f" · {t.received_at:%d %b %Y %H:%M} · `{t.ticket_id}` · synthetic")
    c = _customers().get(t.customer_id or "")
    if c:
        with st.container(horizontal=True, gap="small"):
            st.badge(c["company_name"].replace(" (Synthetic)", ""), icon=":material/business:", color="gray")
            st.badge(f"{c['plan_tier'].title()} plan", color="violet" if c["plan_tier"] == "enterprise" else "gray")
            st.badge(f"Renews {c['contract_renewal_date']}", icon=":material/event:", color="gray")
            st.badge(f"Health: {c['account_health']}",
                     color={"green": "green", "amber": "orange", "red": "red"}[c["account_health"]])
            if c["open_incidents"]:
                st.badge(f"{c['open_incidents']} open incident(s)", icon=":material/warning:", color="orange")
    else:
        st.badge("No matching customer account", icon=":material/person_off:", color="orange")
    with st.container(border=True):
        st.text(t.body)


def show_card(res, trace) -> None:
    label = L.PRIORITY[res.priority][0]
    target = TAX["priorities"][res.priority]["target_first_response_minutes"]
    target_txt = f"{target // 60} h" if target >= 60 else f"{target} min"

    if trace.status == "fallback":
        st.warning("It is marked for manual triage. Please triage it yourself; nothing has been decided for you.",
                   title="Automatic triage failed for this ticket", icon=":material/build:")
    if res.escalate:
        st.error("\n".join(f"- {L.REASON.get(r, r)}" for r in res.escalation_reasons),
                 title="Needs a lead before anyone acts", icon=":material/notification_important:")
    else:
        st.success("It can go straight to the team below once you accept.",
                   title="No escalation needed", icon=":material/check_circle:")

    cat, pri, team = st.columns(3, border=True)
    with cat:
        st.caption("Category")
        st.markdown(f"**{L.INTENT[res.intent]}**")
        if res.secondary_intent:
            st.caption(f"Also: {L.INTENT[res.secondary_intent]}")
    with pri:
        st.caption("Priority")
        colour, icon = PRIORITY_BADGE[res.priority]
        st.badge(f"{res.priority} · {label}", icon=icon, color=colour)
        st.caption(f"Reply target: {target_txt}")
    with team:
        st.caption("Send to")
        st.markdown(f"**{L.QUEUE[res.queue]}**")

    st.markdown(f"**Summary for the next team:** {res.summary}")
    st.markdown(f"**Suggested next step:** {res.suggested_next_action}")
    if res.missing_info:
        st.markdown("**Ask the customer for:**\n" + "\n".join(f"- {L.missing(m)}" for m in res.missing_info))
    low = res.confidence < TAX["thresholds"]["min_confidence_auto_accept"]
    st.progress(res.confidence, text=f"Assistant confidence: {res.confidence:.0%}" + (" · low, check carefully" if low else ""))

    with st.expander("Why? How this was decided", icon=":material/rule:"):
        st.markdown("**The assistant only read the ticket. These written rules decided priority, team and escalation:**")
        st.markdown("\n".join(f"- {L.rule(r)}" for r in trace.rules_fired) or "-")
        st.table({
            ":material/visibility_off: Hidden from the AI": ", ".join(trace.redactions) or "nothing needed",
            ":material/shield: Instructions aimed at the AI": ", ".join(trace.injection_matches) or "none found",
            ":material/badge: Customer account found": "yes" if trace.customer_found else "no",
            ":material/timer: Run": f"{trace.status}, {trace.total_ms / 1000:.1f} s, {trace.llm_attempts} attempt(s)",
            ":material/memory: Model": f"{trace.model} · {trace.input_tokens} in / {trace.output_tokens} out tokens",
        }, border="horizontal")
        if trace.langsmith_run_id and tracing_enabled():
            # One API call to build the link, so only on request.
            if st.button("Open the full trace in LangSmith", key=f"trace_{trace.run_id}", icon=":material/account_tree:",
                         help="For the person who maintains this tool: the exact (redacted) text sent to the model and its answer."):
                url = trace_url(trace.langsmith_run_id)
                if url:
                    st.link_button("Open LangSmith", url, icon=":material/open_in_new:")
                else:
                    st.caption("The trace isn't available yet. Try again in a few seconds.")


# ---------------------------------------------------------------- review
def finish(t: InboundTicket, res, trace, decision: str, edits: dict | None = None, comment: str = "") -> None:
    shown_at = st.session_state.get(f"shown_{t.ticket_id}", time.perf_counter())
    review = ReviewDecision(ticket_id=t.ticket_id, reviewer=st.session_state.reviewer or "tier1_rep", decision=decision,
                            edited_fields=edits or {}, comment=comment, reviewed_at=datetime.now(timezone.utc),
                            seconds_to_decide=round(time.perf_counter() - shown_at, 1))
    try:
        _, outbox, delivery = handoff.record(res, trace, review)
    except Exception as e:  # invalid edit, ticket file locked...: nothing is written
        show_error(e)
        return
    st.session_state.done = {"ticket_id": t.ticket_id, "decision": decision,
                             "fields": outbox.fields if outbox else None,
                             "note": outbox.internal_note if outbox else None,
                             "written_back": delivery.written_back, "queue_file": delivery.queue_file,
                             "notified": delivery.notified, "warnings": delivery.warnings}
    st.session_state.mode = None
    st.session_state.retriage = None
    st.session_state.selected_ticket = None  # move on to the next waiting ticket
    st.rerun()


def review_panel(t: InboundTicket, res, trace) -> None:
    st.subheader("Your decision", anchor=False)
    st.caption("Nothing is written to the ticket until you choose. You stay responsible for the final triage.")
    st.session_state.setdefault(f"shown_{t.ticket_id}", time.perf_counter())

    with st.container(horizontal=True):
        if st.button("Accept", key="accept", type="primary", icon=":material/check:"):
            finish(t, res, trace, "accepted")
        if st.button("Edit", key="edit", icon=":material/edit:"):
            st.session_state.mode = "edit"
        if st.button("Reject, I'll triage manually", key="reject", icon=":material/block:"):
            st.session_state.mode = "reject"

    if st.session_state.mode == "edit":
        with st.form("edit_form"):
            intents, prios, queues = list(TAX["intents"]), list(TAX["priorities"]), list(TAX["queues"])
            ni = st.selectbox("Category", intents, index=intents.index(res.intent), format_func=lambda x: L.INTENT[x])
            np_ = st.segmented_control("Priority", prios, default=res.priority, required=True,
                                       format_func=lambda x: f"{x} · {L.PRIORITY[x][0]}", key="edit_priority")
            nq = st.selectbox("Send to", queues, index=queues.index(res.queue), format_func=lambda x: L.QUEUE[x])
            ne = st.segmented_control("Needs a lead?", ["yes", "no"], default="yes" if res.escalate else "no",
                                      required=True, format_func=str.capitalize, key="edit_escalate")
            why = st.text_input("Why are you changing it?", placeholder="Helps improve the system", key="edit_reason")
            if st.form_submit_button("Save my edit", type="primary", icon=":material/save:"):
                edits = {k: v for k, v, old in [("intent", ni, res.intent), ("priority", np_, res.priority),
                                                ("queue", nq, res.queue), ("escalate", ne, "yes" if res.escalate else "no")]
                         if v != old}
                finish(t, res, trace, "edited" if edits else "accepted", edits, why)
    elif st.session_state.mode == "reject":
        with st.form("reject_form", border=False):
            with st.container(horizontal=True, vertical_alignment="bottom"):
                why = st.text_input("Why are you rejecting it?", placeholder="e.g. wrong category, spam, needs more context",
                                    key="reject_reason")
                if st.form_submit_button("Confirm reject", type="primary", icon=":material/block:"):
                    finish(t, res, trace, "rejected", comment=why)
