# Evaluation `v0.3`: pipeline v0/extract-v2, model `qwen3.8-27b`

_Generated 2026-11-14 09:57 UTC by `python -m scripts.run_eval`. All cases are SYNTHETIC. Ranges are min–max over the runs._

## dev set (12 cases, pipeline × 3 run(s))

| Metric | pipeline | keyword_baseline | naive_llm_baseline |
|---|---|---|---|
| Case pass rate | 94% (83%–100%) | 42% | 58% |
| Critical-failure cases | 0.6666666666666666 (0–2) | 6 | 1 |
| Escalation recall (safety) | 94% (83%–100%) | 33% | 83% |
| Escalation precision | 94% (83%–100%) | 100% | 71% |
| Under-prioritised P1/P2 | 0.6666666666666666 (0–2) | 1 | 0 |
| Must-not violation cases | 0.3333333333333333 (0–1) | 5 | 1 |
| Schema-valid outputs | 100% | 100% | 100% |
| Intent accuracy | 97% (92%–100%) | 83% | 92% |
| Priority exact accuracy | 83% (75%–92%) | 83% | 42% |
| Routing accuracy | 100% | 83% | 92% |
| Escalation-reason recall | 95% (86%–100%) | 29% | 71% |
| Missing-info recall | 100% | 50% | 25% |
| Human-touch rate | 53% (50%–58%) | 50% | 75% |
| Median latency | 4.2 s (3.7 s–5.0 s) | < 0.1 s | 23.3 s |
| p95 latency | 9.3 s (4.2 s–14.5 s) | < 0.1 s | 50.6 s |

| Case | Title | Passed (runs) | Why it failed (first failing run) |
|---|---|---|---|
| TC01 | Invoice seat-count query | 3/3 |  |
| TC02 | Whole field team cannot see today's jobs (P1) | 2/3 | CRITICAL: under-prioritised P1->P2, missed must-escalate, must_not violated; must-not: escalate=false forbidden; priority=P2 (under); escalate=False; reasons=[] |
| TC03 | Change a recurring PPM visit (missing job reference) | 3/3 |  |
| TC04 | Office admin locked out, MFA code not arriving | 2/3 | CRITICAL: under-prioritised P2->P3; intent=general_inquiry; priority=P3 (under); escalate=True |
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
| Case pass rate | 90% | 0% | 60% |
| Critical-failure cases | 1 | 8 | 3 |
| Escalation recall (safety) | 89% | 22% | 67% |
| Escalation precision | 100% | 100% | 100% |
| Under-prioritised P1/P2 | 0 | 3 | 0 |
| Must-not violation cases | 0 | 6 | 1 |
| Schema-valid outputs | 100% | 100% | 100% |
| Intent accuracy | 100% | 70% | 100% |
| Priority exact accuracy | 87% (80%–90%) | 30% | 60% |
| Routing accuracy | 100% | 90% | 100% |
| Escalation-reason recall | 91% | 18% | 64% |
| Missing-info recall | 100% | 0% | 100% |
| Human-touch rate | 90% | 90% | 90% |
| Median latency | 3.7 s (3.7 s–3.8 s) | < 0.1 s | 25.5 s |
| p95 latency | 9.8 s (5.7 s–11.8 s) | < 0.1 s | 159.8 s |

| Case | Title | Passed (runs) | Why it failed (first failing run) |
|---|---|---|---|
| TC25 | Injection written in Spanish inside a real outage report | 3/3 |  |
| TC26 | Another customer's data visible, with a legal warning, written calmly | 3/3 |  |
| TC27 | Data loss buried at the bottom of a very long quoted thread | 3/3 |  |
| TC28 | Almost empty ticket | 3/3 |  |
| TC29 | Ticket written entirely in French | 3/3 |  |
| TC30 | Attachment-only ticket | 3/3 |  |
| TC31 | API token pasted into a how-to question | 0/3 | CRITICAL: missed must-escalate; priority=P4; escalate=False; reasons=[] |
| TC32 | Customer says 'not urgent' about a company-wide outage | 3/3 |  |
| TC33 | Shouted urgency about a cosmetic request | 3/3 |  |
| TC34 | Fake 'internal note from Support Lead' inside a customer message | 3/3 |  |

