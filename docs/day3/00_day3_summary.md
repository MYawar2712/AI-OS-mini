# Day 3 summary: the working core

> Synthetic data only. "Measured" = measured on the synthetic set in this repo.

## What was built
| Brief requirement | Status | Evidence |
|---|---|---|
| Working core flow, trigger → final output, for a non-developer | ✅ | Triage Desk: **Process new tickets** → review card → Accept/Edit/Reject → written back to the ticket + escalation notice ([01_integrations.md §1](01_integrations.md)) |
| ≥ 2 real data-source / tool integrations | ✅ 3 | SQLite customer database (read), CSV ticket queue (read + write-back), escalation notifier (file + optional Slack/Teams webhook). ADR-025 |
| Validation, structured outputs, logs, useful errors | ✅ | Per-row CSV validation; Pydantic contracts end to end; JSON app log with run IDs; every error says what to do ([01 §3–4](01_integrations.md)) |
| Config and secrets separated | ✅ | `.env` (secrets only, `.env.example` complete) vs `config/*.yaml`; startup check `scripts/check_setup` + sidebar |
| One interface | ✅ | Streamlit Triage Desk (`streamlit run app/review.py`), plus CLI `scripts/process_queue` for scheduling |
| First execution by the target user or a proxy | 🟡👤 | Owner will run it as a fallback proxy (O3.3). Template: [02_proxy_user_run.md](02_proxy_user_run.md). **Not done yet; nothing recorded until it happens** |

## Measured results
| Check | Result |
|---|---|
| Tests | **196 passing** (was 172): 22 adapter/batch/error/preflight tests, 2 new UI tests; no network needed |
| Dev quality after the Day 3 changes (12 cases, real model, 1 run) | **12/12 pass**, 0 critical failures, escalation recall 100%, priority exact 83% (same as Day 2) |
| Latency gate G9 (< 5 s per ticket) | **Pass on dev:** median **6.0 s → 3.6 s**, p95 10.7 s → 4.8 s; output tokens 285 → 157 (prompt extract-v2, ADR-026) |
| Bulk processing in the real app | 24 tickets in **29 s** (4 in parallel), 0 fallbacks |
| Clean-room README walkthrough (automated, not a user test) | Fresh copy, README steps only: install 6 min 19 s, 24 tickets in 26 s, accept/edit/reject all written correctly. **7 findings fixed**, the main one: a CSV saved by Excel in its default format stopped the app ([03_cleanroom_walkthrough.md](03_cleanroom_walkthrough.md)) |
| End-to-end in the real app (agent API) | Process → P1 card → Accept → CSV row written + escalation notice + audit; no console warnings |

Not run today, by design: the held-out set (ADR-021; Day 4 runs it once for v1). Latency was measured once; Day 4 measures run-to-run variance.

## Key question: can someone else run the core workflow when you are not beside them?
**Mostly yes, by design. Not yet proven with a real person.**

- **Setup:** 3 steps in the README (install, paste the key into `.env`, start the app). Everything else (customer database, ticket queue) is created automatically on first run.
- **Running it:** one button processes all new tickets. Each ticket shows a plain-language card with a red box when a lead is needed and a "Why?" panel listing the rules. A person approves each one, and the confirmation shows exactly what was written where.
- **When things go wrong:** the sidebar runs a startup check, and every failure the rep can hit (missing key, AI down, file open in Excel, bad row, webhook down) has a message saying what to do. A failure on one ticket never stops the others, and a failed write changes nothing.
- **Partly checked:** an automated clean-room walkthrough of the README found and fixed 7 problems, but it is not a person.
- **Not yet proven:** the first run by someone other than the developer (task 3.10) hasn't happened. The owner is the fallback proxy, which is weaker evidence because they know the system. That record will be filled in only from a real session.

## Changes to contracts / config
- `PipelineTrace.run_id` (new, optional); `ExtractedFacts.rationale` now optional (extract-v2); `handoff.record()` returns `(final, outbox, delivery)`.
- `config/settings.yaml → integrations` (new); `.env.example` adds `ESCALATION_WEBHOOK_URL`, `TRIAGE_DATA_DIR`, `TRIAGE_RUNS_DIR`.
- ADR-025 to ADR-028; assumptions A-19, A-20.

## Carried to Day 4
- 3.10 owner run (record findings, then fix them).
- Variance (3 runs), held-out checkpoint for v1, adversarial set, RCAs (TC19 and others).
- Optional: LangSmith tracing when the owner adds the key (3.3).
