# 06: Success metrics and non-goals

## North-star metric
**Rep minutes per correctly triaged ticket**, subject to the hard constraint **zero under-prioritised P1/P2 and zero missed must-escalate tickets.**

In plain language: we only count time saved if the safety record is perfect. A faster system that misses one outage has failed.

- Baseline (ESTIMATE): ~3 min per ticket of manual triage ([03](03_evidence_of_pain.md)).
- Day 5 target (to measure with [protocol 05](05_manual_baseline_protocol.md) or a rep review session): ≤ 1 min of rep review per ticket on accepted triage. This would save about 25 h/week in the base scenario. Labelled **ESTIMATE** until timed (A-18). The full manual vs AI-assisted time comparison, with measured LLM time, is in [00 summary](00_day1_summary.md#time-per-ticket-manual-vs-ai-assisted).

## Day 5 gates (PASS/FAIL on the 12-case synthetic set; re-run with `make day1` + the Day 2+ pipeline)

Targets are set relative to what we **measured** today. The naive LLM column is the selected model, `qwen3.8-27b`, with one free-text prompt (3-model comparison: `eval/results/model_comparison.md`).

| # | Gate | Keyword baseline (measured) | Naive LLM (measured) | **Day 5 target** |
|---|---|---|---|---|
| G1 | Escalation recall on must-escalate cases | 33% (2/6) | 83% (5/6) | **100% (6/6)** |
| G2 | Under-prioritised P1/P2 | 1 | 0 | **0** |
| G3 | Schema-valid outputs | 100% | 100% (parsed) | **100%** (invalid outputs fall back to human triage) |
| G4 | Injection case (TC10) | FAIL | PASS | **PASS** |
| G5 | Must-not violations (incl. card data leak) | 5 cases | 1 case | **0** |
| G6 | Case pass rate | 42% (5/12) | 50% (6/12) | **≥ 83% (10/12)** |
| G7 | Routing accuracy | 83% (10/12) | 75% (9/12) | **≥ 92% (11/12)** |
| G8 | Escalation precision | 100% (2/2) | 62% (5/8) | **≥ 75%** (no "escalate everything" to game G1) |
| G9 | Median latency per ticket | < 1 ms (rules) | **28 s** | **< 5 s** (needs shorter output / less reasoning than the naive run) |
| G10 | Mean cost per ticket | $0 | price TBC (≈ 262 in / 958 out tokens) | **< $0.002** (confirm once the console price is entered) |
| G11 | Human-touch rate | 50% | 75% | **report only.** About 50% is expected, because half the set is must-escalate by design |

G1–G5 are **safety gates**: failing any one means "not ready", whatever else passes.
**Caveat:** n = 12, so one case is 8.3 points. Gates are a regression bar, not proof of production readiness.

## Non-goals (v1)
| Non-goal | Why |
|---|---|
| Auto-sending replies to customers | Customer-facing errors cost more; triage must be proven first |
| Refunds, credits, discounts, account or plan changes | Financial and authorisation risk; human-only |
| Live integration with a production ticketing system | v1 uses a mock/adapter interface; production needs security review |
| Multi-language support beyond reading mixed English | Owner decision ADR-006: traffic assumed English. Non-English-dominant tickets fall back to human triage |
| Model fine-tuning | Not enough labelled data; prompts + rules + eval loop come first |
| Resolving tickets / troubleshooting steps | Different job; varies by intent |
| Reading attachments (images, CSVs) | Out of scope for 5 days; their absence is flagged as missing info |
| Replacing reps | Goal is time back and fewer errors, with the human still accountable |
