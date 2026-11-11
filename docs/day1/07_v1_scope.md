# 07: v1 scope

## What v1 will do (plain language)
When a new support ticket arrives, the assistant reads it, looks up the customer's account, and **pre-fills the triage**: what the ticket is about, how urgent it is, which team should own it, what information is missing, and a short summary. If anything looks risky (a possible outage, an unhappy customer thinking of leaving, card details pasted in, an unidentified customer, a message that tries to trick the system, or a ticket too vague to understand), it **flags the ticket for a person** and says why. A support rep always makes the final call: they accept the suggestion with one click or correct it. Every correction is saved so the system can be measured and improved. It never replies to customers, never issues refunds, and never changes accounts.

## In scope / out of scope

| In scope (v1) | Out of scope (v1) |
|---|---|
| Intent + secondary intent (11 intents) | Customer-facing replies |
| Priority P1–P4 with deterministic floors | Refunds, credits, account changes |
| Routing to 6 queues | Live production ticketing write-access |
| Escalation decision + reasons (8 reasons) | Attachment / image understanding |
| Missing-info list, summary, suggested next action | Non-English-dominant tickets (detected → human) |
| Card/PII detection and redaction before the LLM | Fine-tuning |
| Customer context lookup (synthetic CRM) | Ticket resolution / troubleshooting |
| Schema validation, retry, fallback to human | SSO, multi-tenant deployment |
| Eval harness + feedback log of rep edits | Real-time dashboards (a static report is enough) |
| Simple non-developer review UI (CLI/Streamlit-style or sheet) | |

## Human approval points
1. **Every triage** is a suggestion until a rep accepts or edits it. Nothing is written to the ticket without that step.
2. **Escalated tickets** go to a lead, or to CS for churn, with the reasons listed. The system never resolves an escalation itself.
3. **Prompt-injection or sensitive-data flags** need the rep to confirm that the redaction and the decision are correct.
4. **Taxonomy/rule changes** (new intents, priority definitions) are approved by the support manager. They are versioned in `taxonomy.yaml`.

## Two integrations planned for Day 3
| # | Integration | Why |
|---|---|---|
| 1 | **Customer context lookup** (adapter over `customers.json`; same interface as a CRM API) | Priority and escalation depend on plan tier, renewal date, health and open incidents (rule M1, churn context). It also removes the rep's slowest manual step (CRM lookup). |
| 2 | **Ticketing system adapter**: write the triage result as fields + an internal note, with a CSV/Google-Sheets export implementation for the demo | Gives a real place to accept/edit, and the export doubles as the feedback log for the learning loop. An adapter interface means a Zendesk/Freshdesk connector can be swapped in later without touching triage logic. |

## Top 5 risks and mitigations
| # | Risk | Mitigation |
|---|---|---|
| R1 | LLM under-prioritises an outage or misses an escalation | Deterministic rules can only **raise** priority or **add** escalations. Gates G1/G2 at 100%/0. Low confidence leads to escalation. |
| R2 | Prompt injection via ticket text | Ticket text is treated as data (delimited, never as instructions). Pattern-based injection detector. Schema-constrained output. No tools with side effects. The refund/approval path doesn't exist. |
| R3 | PII/card data sent to the LLM or stored in notes | Regex + Luhn redaction **before** the LLM call. Must-not checks on summary/action. |
| R4 | Overfitting to 12 synthetic cases; results don't generalise | Grow to ≥ 50 cases with a held-out split. Validate the taxonomy with a real rep. Report n and caveats everywhere. |
| R5 | Reps don't trust or ignore suggestions (UX) | Show the rationale and reasons, one-click accept, easy edit. Measure the edit rate. Run a pilot in "suggest-only" mode first. |

## Day-by-day plan
| Day | Focus | Exit criterion |
|---|---|---|
| **2** Build core | Triage pipeline: validation → redaction → LLM structured output (Haiku-class, cheap) → rules layer → fallback. Run the naive LLM baseline once a key is available. Grow the test set toward 30+. | Pipeline produces schema-valid output on all 12. First scores logged. |
| **3** Integrate | Customer context adapter + ticketing/CSV adapter. Retries, timeouts, structured logging, cost tracking. | End-to-end run from inbound JSON to ticket fields + note, with context used in decisions. |
| **4** Evaluate & learn | Error analysis per case. Prompt/rule iteration with before/after scores. Feedback log from simulated rep edits added to eval. LLM-judge or human check for summaries. | Safety gates G1–G5 pass. Regression report committed. |
| **5** UX & ship | Non-developer review screen. Runbook. Final eval vs both baselines. Demo + write-up with honest limits. | All gates evaluated and reported; demo runs from one command. |
