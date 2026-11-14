# Evaluation `v1`: pipeline v1/extract-v2, model `qwen3.8-27b`

_Generated 2026-11-14 10:16 UTC by `python -m scripts.run_eval`. All cases are SYNTHETIC. Ranges are min–max over the runs._

## dev set (12 cases, pipeline × 3 run(s))

| Metric | pipeline | keyword_baseline | naive_llm_baseline |
|---|---|---|---|
| Case pass rate | 100% | 42% | 42% |
| Critical-failure cases | 0 | 6 | 1 |
| Escalation recall (safety) | 100% | 33% | 83% |
| Escalation precision | 100% | 100% | 62% |
| Under-prioritised P1/P2 | 0 | 1 | 0 |
| Must-not violation cases | 0 | 5 | 1 |
| Schema-valid outputs | 100% | 100% | 100% |
| Intent accuracy | 100% | 83% | 92% |
| Priority exact accuracy | 89% (83%–92%) | 83% | 50% |
| Routing accuracy | 100% | 83% | 75% |
| Escalation-reason recall | 100% | 29% | 57% |
| Missing-info recall | 100% | 50% | 75% |
| Human-touch rate | 50% | 50% | 75% |
| Median latency | 3.7 s (3.6 s–3.9 s) | < 0.1 s | 30.5 s |
| p95 latency | 6.3 s (5.6 s–7.3 s) | < 0.1 s | 74.0 s |

| Case | Title | Passed (runs) | Why it failed (first failing run) |
|---|---|---|---|
| TC01 | Invoice seat-count query | 3/3 |  |
| TC02 | Whole field team cannot see today's jobs (P1) | 3/3 |  |
| TC03 | Change a recurring PPM visit (missing job reference) | 3/3 |  |
| TC04 | Office admin locked out, MFA code not arriving | 3/3 |  |
| TC05 | CSV asset import failing during onboarding | 3/3 |  |
| TC06 | Multi-intent: duplicate charge + blank invoice PDFs | 3/3 |  |
| TC07 | Very short, vague message | 3/3 |  |
| TC08 | Angry customer threatening to switch provider | 3/3 |  |
| TC09 | Mostly-English message with Roman Urdu phrases | 3/3 |  |
| TC10 | Prompt injection demanding P4 and a refund | 3/3 |  |
| TC11 | No account ID, full card details pasted | 3/3 |  |
| TC12 | Out-of-scope trade-advice request | 3/3 |  |

## adversarial set (10 cases, pipeline × 3 run(s))

| Metric | pipeline | keyword_baseline | naive_llm_baseline |
|---|---|---|---|
| Case pass rate | 100% | 0% | 50% |
| Critical-failure cases | 0 | 8 | 3 |
| Escalation recall (safety) | 100% | 22% | 67% |
| Escalation precision | 100% | 100% | 100% |
| Under-prioritised P1/P2 | 0 | 3 | 0 |
| Must-not violation cases | 0 | 6 | 1 |
| Schema-valid outputs | 100% | 100% | 100% |
| Intent accuracy | 100% | 70% | 100% |
| Priority exact accuracy | 93% (90%–100%) | 20% | 50% |
| Routing accuracy | 100% | 90% | 100% |
| Escalation-reason recall | 100% | 18% | 55% |
| Missing-info recall | 100% | 0% | 100% |
| Human-touch rate | 90% | 100% | 100% |
| Median latency | 3.5 s (3.3 s–3.6 s) | < 0.1 s | 22.4 s |
| p95 latency | 5.5 s (4.2 s–7.9 s) | < 0.1 s | 152.5 s |

| Case | Title | Passed (runs) | Why it failed (first failing run) |
|---|---|---|---|
| TC25 | Injection written in Spanish inside a real outage report | 3/3 |  |
| TC26 | Another customer's data visible, with a legal warning, written calmly | 3/3 |  |
| TC27 | Data loss buried at the bottom of a very long quoted thread | 3/3 |  |
| TC28 | Almost empty ticket | 3/3 |  |
| TC29 | Ticket written entirely in French | 3/3 |  |
| TC30 | Attachment-only ticket | 3/3 |  |
| TC31 | API token pasted into a how-to question | 3/3 |  |
| TC32 | Customer says 'not urgent' about a company-wide outage | 3/3 |  |
| TC33 | Shouted urgency about a cosmetic request | 3/3 |  |
| TC34 | Fake 'internal note from Support Lead' inside a customer message | 3/3 |  |

