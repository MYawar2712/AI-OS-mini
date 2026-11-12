"""Triage Desk: review UI for Tier-1 support (non-developers).

    streamlit run app/review.py

Inbox -> Triage -> read the card -> Accept / Edit / Reject -> written to the ticket (outbox) + audit log.
Uses the same pipeline and approval code as the CLI (src/pipeline). All tickets here are SYNTHETIC.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

import src.pipeline.run as pipeline_run  # noqa: E402  (module import so tests can swap triage())
from app import labels as L  # noqa: E402
from src.llm_client import is_configured, api_key_env_var  # noqa: E402
from src.pipeline.context import _customers  # noqa: E402
from src.pipeline.handoff import record, runs_dir  # noqa: E402
from src.schemas import InboundTicket, ReviewDecision, load_test_cases  # noqa: E402
from src.taxonomy import load_settings, load_taxonomy  # noqa: E402

st.set_page_config(page_title="Triage Desk", page_icon="🎫", layout="wide")
TAX = load_taxonomy()


# ---------------------------------------------------------------- data helpers
@st.cache_data
def demo_inbox() -> list[dict]:
    out = []
    for f in ("eval/test_cases.jsonl", "eval/test_cases_holdout.jsonl"):
        out += [c.ticket.model_dump(mode="json") for c in load_test_cases(ROOT / f)]
    return out


def all_tickets() -> list[InboundTicket]:
    return [InboundTicket.model_validate(t) for t in demo_inbox() + st.session_state.get("new_tickets", [])]


def audit_rows() -> list[dict]:
    p = runs_dir() / "audit.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def reviewed_ids() -> dict[str, str]:
    return {r["review"]["ticket_id"]: r["review"]["decision"] for r in audit_rows()}


def customer_line(cid: str | None) -> str:
    c = _customers().get(cid or "")
    if not c:
        return "⚠️ **No matching customer account** for this sender"
    return (f"**{c['company_name']}** · {c['plan_tier'].title()} plan · {c['seat_count']} seats · "
            f"renews {c['contract_renewal_date']} · health {c['account_health']} · open incidents {c['open_incidents']}")


# ---------------------------------------------------------------- UI pieces
def badge(text: str, colour: str) -> str:
    return (f"<span style='background:{colour};color:white;padding:3px 10px;border-radius:12px;"
            f"font-weight:600;font-size:0.9rem'>{text}</span>")


def show_ticket(t: InboundTicket) -> None:
    st.markdown(f"#### {t.subject}")
    st.caption(f"{L.CHANNEL.get(t.channel, t.channel)} · from {t.from_name}"
               + (f" <{t.from_email}>" if t.from_email else "") + f" · {t.received_at:%d %b %Y %H:%M} · `{t.ticket_id}` · synthetic")
    st.markdown(customer_line(t.customer_id))
    with st.container(border=True):
        st.text(t.body)


def show_card(res, trace) -> None:
    label, colour, emoji = L.PRIORITY[res.priority]
    target = TAX["priorities"][res.priority]["target_first_response_minutes"]

    if trace.status == "fallback":
        st.warning("**Automatic triage failed for this ticket.** It is marked for manual triage. "
                   "Please triage it yourself; nothing has been decided for you.", icon="🛠️")
    if res.escalate:
        st.error("**Needs a lead before anyone acts.**\n\n" + "\n".join(f"- {L.REASON.get(r, r)}" for r in res.escalation_reasons),
                 icon="🚨")
    else:
        st.success("**No escalation needed.** Can go straight to the team below once you accept.", icon="✅")

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Category**<br>{L.INTENT[res.intent]}"
                + (f"<br><small>also: {L.INTENT[res.secondary_intent]}</small>" if res.secondary_intent else ""),
                unsafe_allow_html=True)
    c2.markdown(f"**Priority**<br>{badge(f'{emoji} {res.priority} · {label}', colour)}<br>"
                f"<small>reply target: {target // 60 if target >= 60 else target} {'h' if target >= 60 else 'min'}</small>",
                unsafe_allow_html=True)
    c3.markdown(f"**Send to**<br>{L.QUEUE[res.queue]}", unsafe_allow_html=True)

    st.markdown(f"**Summary for the next team:** {res.summary}")
    st.markdown(f"**Suggested next step:** {res.suggested_next_action}")
    if res.missing_info:
        st.markdown("**Ask the customer for:**\n" + "\n".join(f"- {L.missing(m)}" for m in res.missing_info))
    conf = res.confidence
    st.progress(conf, text=f"Assistant confidence: {conf:.0%}"
                + ("  ·  low: check carefully" if conf < TAX["thresholds"]["min_confidence_auto_accept"] else ""))

    with st.expander("Why? (how this was decided)"):
        st.markdown("**The assistant only read the ticket. These written rules decided priority, team and escalation:**")
        for r in trace.rules_fired:
            st.markdown(f"- {L.rule(r)}")
        st.markdown("**Safety checks**")
        st.markdown(f"- Hidden from the AI: {', '.join(trace.redactions) or 'nothing needed'}")
        st.markdown(f"- Instructions aimed at the AI: {', '.join(trace.injection_matches) or 'none found'}")
        st.markdown(f"- Customer account found: {'yes' if trace.customer_found else 'no'}")
        st.caption(f"Run: {trace.status} · {trace.total_ms / 1000:.1f} s · model {trace.model} · "
                   f"{trace.input_tokens} in / {trace.output_tokens} out tokens · attempts {trace.llm_attempts}")


def review_panel(t: InboundTicket, res, trace) -> None:
    st.markdown("### Your decision")
    st.caption("Nothing is written to the ticket until you choose. You stay responsible for the final triage.")
    reviewer = st.session_state.get("reviewer", "tier1_rep")
    shown_at = st.session_state.setdefault(f"shown_{t.ticket_id}", time.perf_counter())

    def finish(decision: str, edits: dict | None = None, comment: str = "") -> None:
        review = ReviewDecision(ticket_id=t.ticket_id, reviewer=reviewer, decision=decision, edited_fields=edits or {},
                                comment=comment, reviewed_at=datetime.now(timezone.utc),
                                seconds_to_decide=round(time.perf_counter() - shown_at, 1))
        try:
            final, outbox = record(res, trace, review)
        except Exception as e:  # invalid edit etc.
            st.error(f"Could not save: {e}. Nothing was written. Please check your edit and try again.")
            return
        st.session_state["done"] = {"ticket_id": t.ticket_id, "decision": decision,
                                    "fields": outbox.fields if outbox else None,
                                    "note": outbox.internal_note if outbox else None}
        st.session_state.pop("result", None)
        st.rerun()

    a, e, r = st.columns(3)
    if a.button("✅ Accept", type="primary", width="stretch", key="accept"):
        finish("accepted")
    mode = st.session_state.get("mode")
    if e.button("✏️ Edit", width="stretch", key="edit"):
        st.session_state["mode"] = mode = "edit"
    if r.button("⛔ Reject (I'll triage manually)", width="stretch", key="reject"):
        st.session_state["mode"] = mode = "reject"

    if mode == "edit":
        with st.form("edit_form"):
            intents, prios, queues = list(TAX["intents"]), list(TAX["priorities"]), list(TAX["queues"])
            ni = st.selectbox("Category", intents, index=intents.index(res.intent), format_func=lambda x: L.INTENT[x])
            np_ = st.selectbox("Priority", prios, index=prios.index(res.priority),
                               format_func=lambda x: f"{x} · {L.PRIORITY[x][0]}")
            nq = st.selectbox("Send to", queues, index=queues.index(res.queue), format_func=lambda x: L.QUEUE[x])
            ne = st.radio("Needs a lead?", ["yes", "no"], index=0 if res.escalate else 1, horizontal=True)
            why = st.text_input("Why are you changing it? (helps improve the system)")
            if st.form_submit_button("Save my edit", type="primary"):
                edits = {k: v for k, v, old in [("intent", ni, res.intent), ("priority", np_, res.priority),
                                                ("queue", nq, res.queue), ("escalate", ne, "yes" if res.escalate else "no")]
                         if v != old}
                st.session_state.pop("mode", None)
                finish("edited" if edits else "accepted", edits, why)
    elif mode == "reject":
        with st.form("reject_form"):
            why = st.text_input("Why? (e.g. wrong category, spam, needs more context)")
            if st.form_submit_button("Confirm reject", type="primary"):
                st.session_state.pop("mode", None)
                finish("rejected", comment=why)


# ---------------------------------------------------------------- pages
def sidebar() -> None:
    with st.sidebar:
        st.title("🎫 Triage Desk")
        st.text_input("Your name", key="reviewer", value=st.session_state.get("reviewer", "tier1_rep"))
        st.divider()
        cfg = load_settings()
        if is_configured():
            st.success(f"Assistant ready · {cfg['llm']['model']}", icon="🟢")
        else:
            st.error(f"Assistant not configured: add `{api_key_env_var()}` to the `.env` file "
                     "(see README). Tickets will go to manual triage until then.", icon="🔴")
        st.caption("All tickets and customers here are **synthetic** demo data.")
        d = runs_dir()
        st.caption(f"Saved to: `{(d.relative_to(ROOT) if d.is_relative_to(ROOT) else d).as_posix()}/`")


def inbox_page() -> None:
    done = st.session_state.pop("done", None)
    if done:
        if done["fields"]:
            st.success(f"Saved ticket `{done['ticket_id']}` ({done['decision']}). Written to the ticket:", icon="💾")
            with st.expander("What was written", expanded=True):
                st.json(done["fields"])
                st.text(done["note"])
        else:
            st.info(f"Ticket `{done['ticket_id']}` rejected: nothing written; it stays for manual triage.", icon="📝")

    tickets = all_tickets()
    status = reviewed_ids()
    show_done = st.toggle("Show already-reviewed tickets", value=False)
    visible = [t for t in tickets if show_done or t.ticket_id not in status]
    left, right = st.columns([1, 2], gap="large")

    with left:
        st.subheader(f"Inbox ({sum(t.ticket_id not in status for t in tickets)} waiting)")
        if not visible:
            st.info("Inbox is empty. Turn on 'Show already-reviewed tickets' or add one under **New ticket**.")
            return
        opts = {t.ticket_id: t for t in visible}
        sel = st.radio("Tickets", list(opts), label_visibility="collapsed",
                       format_func=lambda tid: (f"{'✔️ ' if tid in status else ''}{opts[tid].subject[:45]}"
                                                f"  ·  {opts[tid].from_name}"), key="selected")
    t = opts[sel]

    with right:
        show_ticket(t)
        cached = st.session_state.get("result")
        if cached and cached[0] == t.ticket_id:
            _, res, trace = cached
            show_card(res, trace)
            review_panel(t, res, trace)
        else:
            if t.ticket_id in status:
                st.info(f"Already reviewed ({status[t.ticket_id]}). You can triage it again if needed.")
            if st.button("🔎 Triage this ticket", type="primary", key="triage"):
                with st.spinner("Reading the ticket and applying the rules… (about 5–10 seconds)"):
                    try:
                        res, trace = pipeline_run.triage(t)
                    except Exception as e:
                        st.error(f"Something went wrong before triage could finish: {e}. "
                                 "Nothing was written. Try again, or triage this ticket manually.")
                        return
                st.session_state["result"] = (t.ticket_id, res, trace)
                st.session_state.pop("mode", None)
                st.rerun()


def new_ticket_page() -> None:
    st.subheader("Add a ticket")
    st.caption("Paste a customer message to triage it. Use made-up details only: this is a demo.")
    custs = _customers()
    with st.form("new_ticket", clear_on_submit=True):
        subject = st.text_input("Subject")
        body = st.text_area("Message", height=180)
        c1, c2 = st.columns(2)
        sender = c1.text_input("From (name)", value="Customer")
        channel = c2.selectbox("Channel", ["email", "portal", "chat", "phone_note"], format_func=lambda x: L.CHANNEL[x])
        cid = st.selectbox("Customer account", ["(unknown sender)"] + list(custs),
                           format_func=lambda x: x if x.startswith("(") else f"{x} · {custs[x]['company_name']}")
        if st.form_submit_button("Add to inbox", type="primary"):
            if not subject.strip() or not body.strip():
                st.error("Please fill in both the subject and the message.")
                return
            n = len(st.session_state.get("new_tickets", [])) + 1
            ticket = InboundTicket(ticket_id=f"SYN-NEW-{datetime.now():%H%M%S}-{n}", received_at=datetime.now(timezone.utc),
                                   channel=channel, from_name=sender or "Customer", subject=subject.strip(),
                                   body=body.strip(), customer_id=None if cid.startswith("(") else cid)
            st.session_state.setdefault("new_tickets", []).append(ticket.model_dump(mode="json"))
            st.success("Added. Open the **Inbox** tab to triage it.")


def activity_page() -> None:
    rows = audit_rows()
    st.subheader("Activity")
    if not rows:
        st.info("No reviewed tickets yet.")
        return
    dec = [r["review"]["decision"] for r in rows]
    secs = [r["review"].get("seconds_to_decide") for r in rows if r["review"].get("seconds_to_decide") is not None]
    c = st.columns(5)
    c[0].metric("Reviewed", len(rows))
    c[1].metric("Accepted as-is", f"{dec.count('accepted') / len(rows):.0%}")
    c[2].metric("Edited", dec.count("edited"))
    c[3].metric("Rejected", dec.count("rejected"))
    c[4].metric("Median time to decide", f"{sorted(secs)[len(secs) // 2]:.0f} s" if secs else "n/a")
    table = [{"when": r["logged_at"][:19].replace("T", " "), "ticket": r["review"]["ticket_id"],
              "decision": r["review"]["decision"], "priority": r["final"]["priority"], "team": L.QUEUE[r["final"]["queue"]],
              "escalated": "yes" if r["final"]["escalate"] else "no", "edited": ", ".join(r["review"]["edited_fields"]) or "",
              "reviewer": r["review"]["reviewer"], "assistant": r["trace"]["status"]} for r in reversed(rows)]
    st.dataframe(table, width="stretch", hide_index=True)


def help_page() -> None:
    st.subheader("How to use the Triage Desk")
    st.markdown("""
1. **Inbox** → pick a ticket → **Triage this ticket**.
2. Read the card. **Red box = a lead must look before anyone acts.**
3. Choose **Accept**, **Edit** (change category, priority, team or escalation) or **Reject** (you'll triage it yourself).
4. Only then is the triage written to the ticket. Your decision is logged in **Activity**.

**What the assistant does:** reads the ticket and answers fixed questions (who is affected, is there a workaround, is a job affected today…).
**What it never does:** reply to customers, give refunds or discounts, change accounts, or decide priority on its own: written rules do that.
**Card numbers and passwords** are hidden before the assistant sees the ticket.

| Priority | Meaning | Reply target |
|---|---|---|
| 🔴 P1 Critical | Data loss, security issue, or many users blocked with no workaround | 30 min |
| 🟠 P2 High | One user blocked, a job affected today, admin locked out, payment or churn risk | 2 h |
| 🔵 P3 Normal | Non-blocking problems, questions with impact, changes for later | 8 h |
| ⚪ P4 Low | Feature requests and general questions | 24 h |
""")


def main() -> None:
    sidebar()
    tabs = st.tabs(["📥 Inbox", "➕ New ticket", "📊 Activity", "❓ Help"])
    with tabs[0]:
        inbox_page()
    with tabs[1]:
        new_ticket_page()
    with tabs[2]:
        activity_page()
    with tabs[3]:
        help_page()


main()
