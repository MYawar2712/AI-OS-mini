# Adoption and quality metrics for the first two weeks, and the next iteration

> None of these have been measured with real reps yet. The targets are **proposals** to agree with the support lead before the pilot. Every metric below can already be computed from files the system writes.

## 1. Pilot shape
- **Week 1, shadow mode:** 2–3 reps. The assistant pre-fills; reps triage as they do today and record Accept / Edit / Reject. Nothing changes for customers.
- **Week 2, assisted mode:** reps work from the pre-filled card if week 1 meets the gates in section 4.

## 2. Adoption metrics (are people using it, and does it help?)

| Metric | How it is measured | Source | Week-2 target (proposal) |
|---|---|---|---|
| Coverage | Tickets with a decision ÷ tickets in the queue | `ticket_queue.csv` status | ≥ 90% |
| Accepted as-is | `decision = accepted` ÷ all decisions | `audit.jsonl → review.decision` | ≥ 70% |
| Edit rate by field | Count of each key in `review.edited_fields` ÷ decisions | `audit.jsonl` | Priority ≤ 15%, team ≤ 10%, category ≤ 10% |
| Rejection rate | `decision = rejected` ÷ decisions | `audit.jsonl` | ≤ 5% |
| Median time to decide | Median of `review.seconds_to_decide` | `audit.jsonl` | ≤ 60 s (estimate today for manual triage: about 3 min) |
| Rep-reported usefulness | 3 questions at the end of each week (trust, speed, what to remove) | Short form | No rep says "slower than before" |

## 3. Quality and safety metrics (is it right, and is it safe?)

| Metric | How it is measured | Source | Target |
|---|---|---|---|
| Missed escalations | Tickets a rep or lead escalated that the assistant had not flagged | `audit.jsonl`: `proposed.escalate = false` and `final.escalate = true` | **0** per week; each one becomes a test case |
| Under-prioritised P1/P2 | `final.priority` higher than `proposed.priority`, final is P1 or P2 | `audit.jsonl` | **0** per week |
| Escalation precision | Flagged tickets where the rep kept the flag ÷ all flagged | `audit.jsonl` | ≥ 75% |
| Time for a P1 to be flagged | Ticket `received_at` → suggestion saved | queue + `proposals.jsonl` | ≤ 5 min with the scheduled trigger |
| Fallback rate | `trace.status = fallback` ÷ tickets | `app_log.jsonl`, event `triage` | ≤ 2% |
| Repaired model answers | Events `llm_output_repaired` | `app_log.jsonl` | Watch; a rise means the model or prompt drifted |
| Latency | Median and p95 of `total_ms` | `app_log.jsonl` / LangSmith | Median < 5 s, p95 < 8 s |
| Cost per ticket and per day | Tokens × price | `app_log.jsonl` tokens; price in `config/settings.yaml` | Set once the price is confirmed |
| Secrets found | Count by `redactions` kind | `app_log.jsonl` | Report weekly to the lead |
| Regression score | `scripts/run_eval` on dev + break-it, 3 runs | `eval/results/` | No dangerous mistakes; pass rate not lower than the last release |

## 4. Gates between week 1 and week 2

| Gate | Continue to assisted mode if |
|---|---|
| Safety | 0 missed escalations and 0 under-prioritised P1/P2 that a rep did not catch on the card |
| Usefulness | Accepted as-is ≥ 60% in shadow mode and no field edited on more than 25% of tickets |
| Reliability | Fallback rate ≤ 5%, no data-handling incident |

If a gate fails: stay in shadow mode, add the failing tickets to the test set, fix, re-run the evaluation, try again.

## 5. Next iteration (in priority order)

| # | Change | Why | Evidence it is needed |
|---|---|---|---|
| 1 | Real tickets in the test set (100+ anonymised, second labeller on a sample) | Today's sets are synthetic and written by one person | Limitation 2 in the case study |
| 2 | Cross-check the category | It is the one decision the model makes alone | Held-out failures F5 and F6 |
| 3 | Real helpdesk and CRM adapters | CSV and SQLite are stand-ins | ADR-025 |
| 4 | Possible-incident alert: several tickets about the same problem | One P1 often arrives as many "small" tickets | Design gap; not built |
| 5 | Multi-user hosting with sign-in | The app is single-user and local | ADR-023 |
| 6 | Suggested help articles on the card | Speeds up the rep's next step | The 15 synthetic KB articles are unused today |
| 7 | Automatic acceptance for a narrow, proven class (e.g. P4 general questions) | Only after weeks of ≥ 95% accepted-as-is for that class | Not before the pilot data exists |
