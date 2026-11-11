# 05: Manual baseline protocol (human triage timing)

**Goal:** measure how long a real Tier-1 rep takes to triage the 12 synthetic cases, and how accurately, so the AI system is compared against people and not only against our own baselines.

**Status: NOT YET RUN.** There was no access to support staff during the challenge. The numbers at the bottom are a clearly labelled **ESTIMATE**.

**Approximate effort:** ~45–60 min with a real rep (labelling and timing in one session). If no rep is available, the project owner can run it as a "proxy rep" in ~1 hour (~45 min hands-on). Label the results as proxy / non-expert.

## Setup (10 min)
1. Participant: 1–3 Tier-1 reps, ideally with different levels of experience. Record their role and years of experience.
2. Give them: the 12 tickets (body + subject + customer ID only; **no expected answers**), [`config/taxonomy.yaml`](../../config/taxonomy.yaml) printed as a one-page cheat sheet, and [`data/synthetic/customers.json`](../../data/synthetic/customers.json) as the "CRM".
3. Explain that tickets are synthetic, that this tests the *process* and not them, and that they should work at their normal pace.
4. Randomise ticket order per participant (write the order down).

## Per ticket (stopwatch)
| Step | Record in [`eval/manual_timing_template.csv`](../../eval/manual_timing_template.csv) |
|---|---|
| Start the stopwatch when the ticket is shown | `start_time` |
| Lap when they say "I understand the problem" | `seconds_reading` |
| Note every lookup (CRM, KB, "would ask colleague") | `lookups_used`, `seconds_lookups`, `would_ask_colleague` |
| They fill intent, secondary, priority, queue, escalate + reasons, missing info, a one-line summary | decision columns |
| Stop when they say "done" | `end_time`, `seconds_total` |
| Ask: "How confident are you, 1–5?" | `confidence_1to5` |

## After all 12
- Score their answers with the same rubric: convert the CSV into the predictions format and run `python -m eval.metrics <file>`.
- Ask: "Which ticket was hardest, and why?" and "Did any expected rule surprise you?" Disagreements with our expected labels are **data about the taxonomy**, not participant errors. Log them in `docs/assumptions.md` (A-10).

## Ethics / practicalities
No customer data is used. Get consent to record times. Don't share individual scores with their manager.

## ESTIMATE until a human run exists
| Metric | Estimate | Reasoning |
|---|---|---|
| Median time per ticket | **≈ 3 min** (range 2–5) | Same as pain-model input A-04: ~1 min reading, ~1 min account lookup, ~1 min classify/route/note. Vague (TC07) and multi-intent (TC06) tickets probably take longer. |
| Total for 12 tickets | ≈ 36 min | 12 × 3 |
| Escalation recall | Probably higher than the keyword baseline (33%) | Humans notice churn tone and suspicious instructions. Unknown until measured. |
| Priority agreement with our labels | ≈ 75–85% | No shared written definitions today (A-08) |

These are **not** results. They exist only so the Day 5 comparison has a placeholder. Replace them with measured values.
