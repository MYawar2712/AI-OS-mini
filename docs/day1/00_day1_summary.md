# Day 1 summary: Discover, Map, Baseline

**Project:** AI-assisted Help Desk Triage for a field-service SaaS support team (HVAC, plumbing, electrical, facilities customers).
**Data:** 100% **synthetic**. No production tickets were used. Numbers are labelled **MEASURED-SYN** (measured on our 12 synthetic cases), **ESTIMATE**, or **ASSUMED**.

## The problem in one paragraph (for a support lead)
Every ticket has to be read, matched to a customer, categorised, prioritised, routed, and sometimes escalated, all before anyone starts fixing anything. With 3 reps at ~50 tickets a day, that is an estimated **60 hours a week** of triage and misroute rework (base case; range 22–163 h). The costliest mistakes are rare but serious: an outage logged as routine, a customer about to leave whose message gets read as a bug report, or card details copied into notes. We will build an assistant that **pre-fills the triage and flags risky tickets for a person**, while a rep keeps the final say.

## Key question: is the problem real, recurring, and measurable against a baseline?

| | Answer | Confidence |
|---|---|---|
| **Real?** | Probably yes. Triage is a universal Tier-1 step, and the failure modes ([03 §3](03_evidence_of_pain.md)) are well known in support work. **But no real rep has confirmed the size of the pain yet.** | Medium |
| **Recurring?** | Yes. It happens on every ticket, an estimated ~750 a week. | Medium (volume is assumed, A-03) |
| **Measurable against a baseline?** | **Yes, demonstrated.** A runnable harness scores any system on 12 cases with safety-weighted metrics, and one baseline is already measured below. | High (for the harness); Low (for real-world generalisation, n = 12 synthetic) |

## Baseline results (MEASURED-SYN, from `python -m scripts.run_day1`)

| Metric | Keyword cheat-sheet baseline | Naive LLM baseline | Day 5 target |
|---|---|---|---|
| Case pass rate | **42%** (5/12) | **not run** (no API key yet) | ≥ 83% |
| Escalation recall (safety) | **33%** (2/6) | not run | **100%** |
| Escalation precision | 100% (2/2) | not run | ≥ 75% |
| Under-prioritised P1/P2 | **1** (TC09: on-site no-show → P3) | not run | **0** |
| Injection case (TC10) | **FAIL** | not run | PASS |
| Cases with critical failures | 6 | not run | 0 |
| Intent / priority / routing accuracy | 83% / 83% / 83% | not run | routing ≥ 92% |
| Missing-info recall | 50% | not run | report |
| Schema validity | 100% | not run | 100% |
| Human-touch rate | 50% | not run | ≤ 50% |
| Median latency / cost per ticket | < 1 ms / $0 | not run | < 5 s / < $0.002 |

**What the keyword baseline got wrong:** admin lockout routed as a mobile-app issue (TC04). Second issue not escalated in the multi-intent ticket (TC06). The vague ticket was guessed at rather than flagged (TC07). The churn threat was missed and routed to Tier-1 (TC08). The on-site no-show was under-prioritised (TC09). It obeyed nothing in the injection, but also **didn't flag it** (TC10). Card number copied into the summary (TC11).
Full detail: [`eval/results/baseline_comparison.md`](../../eval/results/baseline_comparison.md).

**Naive LLM baseline:** implemented and tested (parser + skip path) but **not run**, because no API key is available yet. **No numbers are estimated or simulated for it.** To fill the column: add `ANTHROPIC_API_KEY` to `.env`, then run `python -m scripts.run_day1`.

## Honest caveats
- 12 cases → one case = 8.3 points. Use this as a smoke test and a regression bar, not a statistical result.
- Expected labels and the taxonomy were written by one person, with no second annotator yet (A-10).
- The keyword baseline mimics a rep's cheat sheet. **It is not a measurement of human reps.** The human timing protocol is ready but not yet run.
- All pain and cost figures are estimates from low-confidence assumptions.

## Deliverables
| # | Deliverable | Link |
|---|---|---|
| 1 | User, JTBD, stakeholders, interview guide | [01_user_and_jtbd.md](01_user_and_jtbd.md) |
| 2 | Workflow map (table + current/future Mermaid) + bottleneck | [02_workflow_map.md](02_workflow_map.md) |
| 3 | Evidence of pain + cost model + failure modes | [03_evidence_of_pain.md](03_evidence_of_pain.md) · [`config/pain_model.yaml`](../../config/pain_model.yaml) |
| 4 | Taxonomy + contracts + JSON Schemas | [`config/taxonomy.yaml`](../../config/taxonomy.yaml) · [`src/schemas.py`](../../src/schemas.py) · [`schemas/`](../../schemas) |
| 5 | Synthetic data + generator | [`data/synthetic/`](../../data/synthetic) · [`scripts/generate_synthetic.py`](../../scripts/generate_synthetic.py) |
| 6 | 12 test cases + rationale | [`eval/test_cases.jsonl`](../../eval/test_cases.jsonl) · [04_test_cases.md](04_test_cases.md) |
| 7 | Rubric + metrics | [`eval/rubric.md`](../../eval/rubric.md) · [`eval/metrics.py`](../../eval/metrics.py) |
| 8 | Baselines + manual protocol | [`baselines/`](../../baselines) · [05_manual_baseline_protocol.md](05_manual_baseline_protocol.md) · [`eval/manual_timing_template.csv`](../../eval/manual_timing_template.csv) |
| 9 | Success metrics, gates, non-goals | [06_success_metrics_and_non_goals.md](06_success_metrics_and_non_goals.md) |
| 10 | v1 scope, risks, Day 2–5 plan | [07_v1_scope.md](07_v1_scope.md) |
| 11 | Assumptions / decisions | [assumptions.md](../assumptions.md) · [decisions.md](../decisions.md) |

## Validate before Day 2 (with a real support person)
1. **Priority definitions and escalation triggers** (A-08, A-10, A-11): have them label the 12 cases blind and compare with our expected labels.
2. **Volume and minutes per triage** (A-03, A-04): one timed session using [protocol 05](05_manual_baseline_protocol.md), plus a ticket-count export if possible.
3. **Misroute rate and rework cost** (A-05, A-06): ask how often tickets bounce and what it costs. This is the largest lever in the cost model.
