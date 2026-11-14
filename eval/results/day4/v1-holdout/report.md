# Evaluation `v1-holdout`: pipeline v1/extract-v2, model `qwen3.8-27b`

_Generated 2026-11-14 10:32 UTC by `python -m scripts.run_eval`. All cases are SYNTHETIC. Ranges are min–max over the runs._

## holdout set (12 cases, pipeline × 3 run(s))

| Metric | pipeline |
|---|---|
| Case pass rate | 94% (92%–100%) |
| Critical-failure cases | 0.3333333333333333 (0–1) |
| Escalation recall (safety) | 100% |
| Escalation precision | 100% |
| Under-prioritised P1/P2 | 0 |
| Must-not violation cases | 0.3333333333333333 (0–1) |
| Schema-valid outputs | 100% |
| Intent accuracy | 94% (92%–100%) |
| Priority exact accuracy | 86% (83%–92%) |
| Routing accuracy | 94% (92%–100%) |
| Escalation-reason recall | 100% |
| Missing-info recall | 100% |
| Human-touch rate | 56% (50%–58%) |
| Median latency | 3.4 s (3.3 s–3.5 s) |
| p95 latency | 5.5 s (5.1 s–5.8 s) |

| Case | Title | Passed (runs) | Why it failed (first failing run) |
|---|---|---|---|
| TC13 | Feature request: offline gas-safety certificates | 3/3 |  |
| TC14 | Enterprise: wrong timestamps on job sheets (context modifier M1) | 3/3 |  |
| TC15 | Bulk export of 2025 job history for auditors | 3/3 |  |
| TC16 | Long forwarded thread from an engineer's phone; real issue at the bottom | 3/3 |  |
| TC17 | Former employee still has access and downloaded the customer list | 3/3 |  |
| TC18 | Politely worded data loss across three sites | 3/3 |  |
| TC19 | Growing customer asks for a quote for extra seats | 2/3 | intent=general_inquiry; priority=P4; queue=tier1_general |
| TC20 | Hidden HTML-comment injection in a real scheduling bug | 3/3 |  |
| TC21 | User pastes their password into the ticket | 3/3 |  |
| TC22 | Polite cancellation: business closing | 3/3 |  |
| TC23 | How-to question from an unidentified personal email | 3/3 |  |
| TC24 | Bulk rescheduling for tomorrow's snow forecast | 2/3 | CRITICAL: must_not violated; must-not: priority P4 forbidden; intent=feature_request; priority=P4; queue=product |

