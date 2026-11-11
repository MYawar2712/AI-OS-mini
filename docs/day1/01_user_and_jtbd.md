# 01: User and job-to-be-done

> **Status: PROXY.** Everything here is built from desk research and general knowledge of B2B SaaS support. No real support rep has been interviewed yet. Numbers are assumptions; IDs refer to [docs/assumptions.md](../assumptions.md).

## Persona: "Sam", Tier-1 Support Representative

| | |
|---|---|
| **Company** | B2B field-service management SaaS (scheduling, job management, mobile app for engineers, invoicing). |
| **Customers** | Service businesses: HVAC, plumbing, electrical, facilities maintenance. Tickets come from **office staff** (planners, admins, accounts) and **field engineers**. |
| **Team** | 3 Tier-1 reps (A-02), backed by Tier-2 technical, Billing, Customer Success, Onboarding/Data, and Product. |
| **Volume** | ~50 tickets/day each, range 35–65 (A-03). Peaks between 07:00 and 10:00, when engineers start jobs. |
| **Channels** | Email (most), customer portal, chat, phone notes typed by whoever answered. |
| **Tools** | Ticketing system (e.g. Zendesk/Freshdesk-type), CRM for account plan/renewal/health, internal KB, billing system, Slack/Teams for "is anyone else seeing this?", status page. |
| **Responsibilities** | Read each ticket → identify intent → look up the account → set priority → route to a queue or engineer → decide whether to escalate → write the internal summary → reply or acknowledge. |
| **Pressures** | First-response SLA; morning spike; vague tickets ("it's broken again"); multi-issue emails; angry customers near renewal; fear of under-prioritising an outage; being blamed for misroutes. |
| **A good day** | No P1 discovered late. Nothing bounced back by Tier-2 as "wrong queue". The queue is cleared by lunch. Escalations arrive with enough context that nobody has to re-ask the customer. |

## Job-to-be-done

> **When** a new ticket lands in the shared inbox, **I want to** quickly know what it is about, how urgent it really is, who should own it, and whether a human lead must look at it now, **so I can** get it to the right person first time, hit our response SLA, and never be the reason an outage or an unhappy customer was missed.

Supporting jobs:
- When a ticket is vague, I want to know exactly what to ask the customer so I only go back to them once.
- When a customer hints they might leave, I want that flagged even if the message is mostly about a bug.

## Secondary stakeholders

| Stakeholder | What they need from a triaged ticket |
|---|---|
| **Tier-2 engineers** | Correct queue (no bounced tickets). Reproduction info: affected users, app version, error text. P1s flagged immediately. |
| **Billing team** | Invoice number, account ID, what is being disputed. Card data **never** stored in tickets. |
| **Customer Success / Retention** | Churn signals the same day, with account context (renewal date, health, open incidents). |
| **Support manager** | Consistent priorities across reps, SLA compliance, accurate categories for reporting, visibility of escalations. |
| **End customer** | A fast, correct first response. Not being asked the same question twice. Urgent on-site problems treated as urgent. |

## Proxy user interview guide (≈30 min, for a real Tier-1 rep)

> Findings section below is **PENDING**. Fill in after the interview and update affected assumptions.

1. Walk me through the last ticket you triaged, from opening it to routing it. What did you look at, and in what order?
2. Roughly how many tickets do you triage on a normal day, and on your worst day? When is the peak?
3. How long does triage take (not resolution)? Which tickets take longest, and why?
4. How do you decide priority? Is there a written definition, and do colleagues apply it the same way?
5. How often does a ticket bounce back as "wrong queue"? What happens when it does, and who loses time?
6. Tell me about a time an urgent issue was missed or prioritised too low. How was it discovered?
7. What account information do you look up, and where? What is annoying about it?
8. What makes you escalate to a lead or another team? Are there things you *must* escalate?
9. What do you do with vague, multi-issue, or angry tickets? Have you ever seen card details or passwords pasted in?
10. If a tool pre-filled intent, priority, queue and summary, what would make you trust it, and what would make you ignore it?

### Answer recording template

| Q | Answer (verbatim where possible) | Number given? | Contradicts assumption # | Confidence (H/M/L) | Follow-up |
|---|---|---|---|---|---|
| 1 | _pending_ | | | | |
| 2 | _pending_ | | A-03 | | |
| 3 | _pending_ | | A-04 | | |
| 4 | _pending_ | | A-08, A-10 | | |
| 5 | _pending_ | | A-05, A-06 | | |
| 6 | _pending_ | | | | |
| 7 | _pending_ | | | | |
| 8 | _pending_ | | A-11 | | |
| 9 | _pending_ | | | | |
| 10 | _pending_ | | A-13 | | |
