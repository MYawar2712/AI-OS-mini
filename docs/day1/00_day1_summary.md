# Day 1 summary: Discover, Map, Baseline

**Project:** AI-assisted Help Desk Triage for a field-service SaaS support team (HVAC, plumbing, electrical, facilities customers).
**LLM provider:** Alibaba Cloud Model Studio (International), model **`qwen3.8-27b`**, selected from 4 candidates (ADR-013, ADR-016): [model_comparison.md](../../eval/results/model_comparison.md).
**Data:** 100% **synthetic**. No production tickets were used. Numbers are labelled **MEASURED-SYN** (measured on our 12 synthetic cases), **ESTIMATE**, or **ASSUMED**.

## The problem in one paragraph (for a support lead)
Every ticket has to be read, matched to a customer, categorised, prioritised, routed, and sometimes escalated, all before anyone starts fixing anything. With 3 reps at ~50 tickets a day, that is an estimated **60 hours a week** of triage and misroute rework (base case; range 22–163 h). The costliest mistakes are rare but serious: an outage logged as routine, a customer about to leave whose message gets read as a bug report, or card details copied into notes. We will build an assistant that **pre-fills the triage and flags risky tickets for a person**, while a rep keeps the final say.

## Key question: is the problem real, recurring, and measurable against a baseline?

| | Answer | Confidence |
|---|---|---|
| **Real?** | Probably yes. Triage is a universal Tier-1 step, and the failure modes ([03 §3](03_evidence_of_pain.md)) are well known in support work. **But no real rep has confirmed the size of the pain yet.** | Medium |
| **Recurring?** | Yes. It happens on every ticket, an estimated ~750 a week. | Medium (volume is assumed, A-03) |
| **Measurable against a baseline?** | **Yes, demonstrated.** A runnable harness scores any system on 12 cases with safety-weighted metrics, and two baselines are measured below. | High (for the harness); Low (for real-world generalisation, n = 12 synthetic) |

## Baseline results (MEASURED-SYN, from `python -m scripts.run_day1`)

| Metric | Keyword cheat-sheet baseline | **Naive LLM: `qwen3.8-27b` (selected)** | Day 5 target |
|---|---|---|---|
| Case pass rate | **42%** (5/12) | **50%** (6/12) | ≥ 83% |
| Escalation recall (safety) | **33%** (2/6) | **83%** (5/6) | **100%** |
| Escalation precision | 100% (2/2) | 62% (5/8) | ≥ 75% |
| Under-prioritised P1/P2 | **1** (TC09: on-site no-show → P3) | **0** | **0** |
| Injection case (TC10) | **FAIL** | **PASS** | PASS |
| Cases with critical failures | 6 | 1 (TC07) | 0 |
| Intent / priority / routing accuracy | 83% / 83% / 83% | 92% / **50%** / 75% | routing ≥ 92% |
| Escalation-reason / missing-info recall | 29% / 50% | 57% / **0%** | report |
| Schema validity | 100% | 100% (after free-text parsing) | 100% |
| Human-touch rate | 50% | **75%** | ≤ 50% |
| Median latency per ticket | < 1 ms | **28 s** (range 15–106 s) | < 5 s |
| Tokens / cost per ticket | 0 / $0 | ≈ 262 in / 958 out / **price not yet confirmed** | < $0.002 |

**Four LLMs were compared** on the same 12 cases with the same prompt and scorer: `qwen3.8-27b`, `deepseek-v4.1-flash`, `qwen3.8-omni-flash` and `deepseek-v4.1-flash-1017`. Full table: [`eval/results/model_comparison.md`](../../eval/results/model_comparison.md).
- **Selection:** a rule fixed *before* the last run picked **`qwen3.8-27b`**. Safety ties across all four, and Qwen then wins on case pass rate (6/12 vs 5/12, 5/12 and 4/12). `qwen3.8-omni-flash` (13 s median) ranked 3rd: it tied `deepseek-v4.1-flash` on pass rate but had the lowest priority accuracy (33%).
- **Caveat:** that is a **one-case margin from a single run**, i.e. noise-level. Qwen is also **~3.5× slower** (28 s median vs ~8 s for DeepSeek) and routes slightly worse (75% vs 83%).
- **Revisit on Day 2:** cut Qwen's latency (e.g. turn off hidden reasoning, cap the output). If it can't get under the 5 s target, `deepseek-v4.1-flash` is the fallback: same safety results, 5/12, and 3.5× faster.

## Time per ticket: manual vs AI-assisted

The value of the AI OS is the **difference** between the two ways of working, not the LLM's speed alone.

| | Manual (today) | With the AI OS (v1) | Label |
|---|---|---|---|
| Machine time | 0 | **8–28 s** (DeepSeek ~8 s, selected `qwen3.8-27b` ~28 s median) | ✅ MEASURED-SYN (12 cases) |
| Rep time | **~3 min** (range 2–5) to read, look up, classify, route, note | **~1 min** (range 0.5–1) to check and accept or edit the pre-filled triage | 🟡 ESTIMATE (A-04, A-18) |
| Rep time saved per ticket | n/a | **~2 min** (range ~1–4.5) | 🟡 ESTIMATE |
| Rep time saved per week (~750 tickets) | n/a | **~25 h** (range ~12–56 h) | 🟡 ESTIMATE |

- **The LLM runs before the rep opens the ticket.** It processes each ticket on arrival, so its 8–28 s happens in the background and the rep doesn't wait for it.
- **LLM time still matters for urgent tickets.** A P1 must be flagged fast, hence the < 5 s latency target (G9). Qwen's 28 s currently misses it.
- **Why the human numbers are estimates:** no support staff were available to time manual triage or review. The timing protocol ([05](05_manual_baseline_protocol.md)) is ready for when they are.

**What the keyword baseline got wrong:** admin lockout routed as a mobile-app issue (TC04). Second issue not escalated in the multi-intent ticket (TC06). The vague ticket was guessed at rather than flagged (TC07). The churn threat was missed and routed to Tier-1 (TC08). The on-site no-show was under-prioritised (TC09). It obeyed nothing in the injection, but also **didn't flag it** (TC10). Card number copied into the summary (TC11).
Full detail: [`eval/results/baseline_comparison.md`](../../eval/results/baseline_comparison.md).

**What the naive LLMs got wrong (the mirror image, same pattern in all 4 models):** they **over-react**. They push non-outages to P1 (e.g. TC04, TC05, TC06). They escalate routine tickets (TC04, TC05, TC09). They let a "won't renew" threat stay a bug/scheduling ticket instead of making churn primary (TC08). None flagged the vague "its broken again" ticket for a human (TC07). Answers are slow (8–28 s median depending on the model), because ~1,000 output tokens per ticket are mostly hidden reasoning.

**Takeaway:** rules and a bare LLM fail in opposite directions. Rules under-react: they miss escalations and are blind to injection. A bare LLM over-reacts: priority inflation and too many escalations mean 75% of tickets still need a human. That is the case for v1's design: **the LLM reads and drafts, deterministic rules set the priority floors and the escalation logic.**

**Scoring notes (revision 2, same saved outputs, no extra API calls):**
- The first scoring pass under-counted the LLM because of two bugs in *our* harness, now fixed and tested. The free-text parser didn't read `**Escalate:**`-style labels. The must-not phrase check flagged "**Do not** approve any refund" as approving a refund.
- The keyword baseline's results did not change.
- Later revisions (3–4) fixed further parser issues found when new models wrote answers differently. All models are re-scored with identical code (`python -m scripts.compare_models --rescore`). See [`eval/rubric.md`](../../eval/rubric.md) §6.

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

## Validation gaps and how to close them

**Status:** no access to support staff during the challenge. The real-user validation below is **ready but deferred**. Until it is done, the affected numbers stay labelled ASSUMED / ESTIMATE.

**Ideal (with a real Tier-1 rep, ~45–60 min in one session):**
1. **Priority definitions and escalation triggers** (A-08, A-10, A-11): have them label the 12 cases blind and compare with our expected labels.
2. **Volume and minutes per triage** (A-03, A-04): time the same session using [protocol 05](05_manual_baseline_protocol.md), plus a ticket-count export if possible.
3. **Misroute rate and rework cost** (A-05, A-06): ask how often tickets bounce and what it costs. This is the largest lever in the cost model.

**Substitutes without a support person (not yet done; approximate effort):**

| Option | What it gives | Approx. time |
|---|---|---|
| 1. Project owner as a "proxy rep": blind-label and time the 12 tickets | A human baseline (non-expert, so a lower bound) for time per ticket and accuracy | ~1 hour (~45 min hands-on) |
| 2. A second, stronger LLM labels the 12 tickets blind from the taxonomy alone | Measures label ambiguity. Disagreements flag unclear tickets or rules for review | ~25 min |
| 3. Public industry benchmarks for volume, handling time, reassignment rate | Replaces "assumed" with "benchmark (cited source)" in the cost model | ~20 min |
| Update docs with the results | Summary, assumptions, cost model, gates | ~10 min |
| **All three** | | **~1.5 hours** |
| **Options 2 + 3 only** | | **~45 min** |

These substitutes improve the evidence but **do not replace** a real rep. Results from them must be labelled "proxy", "LLM-checked" or "benchmark".
