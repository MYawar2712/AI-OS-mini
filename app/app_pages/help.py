import streamlit as st

st.markdown("""
1. Open the **Inbox**, click a ticket, then **Triage this ticket**.
2. Read the card. **A red box means a lead must look before anyone acts.**
3. Choose **Accept**, **Edit** (change category, priority, team or escalation) or **Reject** (you'll triage it yourself).
4. Only then is the triage written to the ticket. Your decision is logged under **Activity**.
""")

with st.container(horizontal=True):
    with st.container(border=True):
        st.markdown(":material/check_circle: **What the assistant does**")
        st.markdown("Reads the ticket and answers fixed questions: who is affected, is there a workaround, "
                    "is a job affected today, is the customer threatening to leave.")
    with st.container(border=True):
        st.markdown(":material/block: **What it never does**")
        st.markdown("Reply to customers, give refunds or discounts, change accounts, or decide priority on its own. "
                    "Written rules do that.")
    with st.container(border=True):
        st.markdown(":material/visibility_off: **Privacy**")
        st.markdown("Card numbers and passwords are hidden **before** the assistant sees the ticket.")

st.subheader("Priorities", anchor=False)
st.table({
    ":red-badge[:material/emergency: P1 · Critical]": "Data loss, security issue, or many users blocked with no workaround. Reply within 30 min.",
    ":orange-badge[:material/priority_high: P2 · High]": "One user blocked, a job affected today, admin locked out, payment or churn risk. Reply within 2 h.",
    ":blue-badge[:material/flag: P3 · Normal]": "Non-blocking problems, questions with impact, changes for later. Reply within 8 h.",
    ":gray-badge[:material/low_priority: P4 · Low]": "Feature requests and general questions. Reply within 24 h.",
}, border="horizontal")
