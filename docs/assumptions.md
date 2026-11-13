# Assumptions log

Confidence: **H** = high, **M** = medium, **L** = low. Nothing here is measured from production. Update this file whenever an interview or measurement changes a value.

> **No access to support staff during the challenge.** Validation with a real user is planned but deferred. Lower-effort substitutes (proxy rep, LLM second labeller, public benchmarks; ~45 min to ~1.5 h) are listed in [00_day1_summary.md → Validation gaps](day1/00_day1_summary.md#validation-gaps-and-how-to-close-them).

| ID | Assumption | Confidence | How to validate with a real user / data |
|---|---|---|---|
| A-01 | Target user is a Tier-1 rep at a B2B field-service SaaS, triaging email/portal/chat/phone-note tickets | M | Interview Q1; shadow one triage session |
| A-02 | Tier-1 team of 3 reps | L | Ask the support manager for headcount and rota |
| A-03 | 35 / 50 / 65 tickets per rep per day (low/base/high) | L | Ticketing-system export: tickets created per day ÷ reps on shift |
| A-04 | 2 / 3 / 5 minutes manual triage per ticket (excl. resolution) | L | Timed run with [protocol 05](day1/05_manual_baseline_protocol.md); ticket "first assignment" timestamps |
| A-05 | 6% / 12% / 20% of tickets misrouted | L | Count tickets with more than one group reassignment in a month of ticket history |
| A-06 | 8 / 15 / 25 minutes of combined rework per misroute | L | Interview Q5; sample 10 reassigned tickets |
| A-07 | Loaded labour cost £12 / £14 / £17 per hour, deliberately low for a demo (owner request) | M (as a modelling choice) | Finance / HR banding, if a real business case is needed |
| A-08 | 8% / 15% / 25% of tickets get the wrong priority | L | Have 2 reps independently label 30 tickets; measure disagreement |
| A-09 | A misroute adds 1 / 3 / 6 hours to customer wait | L | Compare first-response time of reassigned vs not-reassigned tickets |
| A-10 | Our 11 intents, 6 queues and P1–P4 definitions match how the team actually works | M | Walk through `taxonomy.yaml` with a rep and a manager; label the 12 cases blind and compare |
| A-11 | Must-escalate triggers (P1, churn, legal/security, injection, PII, unknown account, conflicting intents, low confidence) are the right set | M | Interview Q8; review with support manager |
| A-12 | Ticket traffic is predominantly English; mixed English + Roman Urdu phrases occur, but non-English-dominant tickets are rare | M (owner statement) | Language-detect a sample of real tickets |
| A-13 | Reps will accept a pre-filled triage if they can see the reasons, and will correct it when wrong | M | Interview Q10; pilot edit-rate |
| A-14 | Customer can usually be identified from a customer ID or sender domain; unknown senders are a minority | M | Share of tickets with no matched organisation in the ticketing system |
| A-15 | A low-cost model (`qwen3.8-27b`, selected from 4) is good enough for triage when combined with rules. All 4 naive runs got 92% intent accuracy but only 33–50% priority accuracy, so priority must come from rules | M | Day 2–4 eval on the growing test set; compare one run with a larger model |
| A-16 | ~2,500 input / 400 output tokens per ticket for the Day 2 pipeline (cost projection). **Measured on the v0 pipeline: ≈ 1,036 in / 280–300 out** (reasoning off); naive runs ≈ 240–260 in / 960–1,040 out | H (measured) | Measure `usage` on Day 2 |
| A-17 | Synthetic tickets are realistic enough to reveal the main failure modes | M | Ask a rep to rate realism of the 12 tickets (1–5) and to supply 5 anonymised real patterns |
| A-18 | With AI pre-filled triage, a rep needs ~0.5–1 min per ticket to check and accept/edit (vs ~2–5 min manual, A-04). The LLM runs on arrival, so its latency isn't rep time | L | Time reps reviewing pre-filled triage in the Day 5 demo / pilot; log accept vs edit and seconds per ticket |
| A-19 | A CSV file and a SQLite database are acceptable stand-ins for the ticketing system and CRM in a demo, because the adapters isolate them | M | Implement one real adapter (e.g. Zendesk sandbox) next iteration without changing pipeline code |
| A-20 | Latency of ~3.6 s median (dev, one run, extract-v2) holds across runs and on held-out tickets | M | Day 4 task 4.2: 3 runs per set, report median/p95 range |
