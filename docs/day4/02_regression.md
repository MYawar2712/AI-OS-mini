# Day 4: Before / after regression and full results

> Synthetic data, real model (`qwen3.8-27b`, reasoning off). Pipeline figures are the mean of 3 runs with the min–max range.
> Reproduce: `python -m scripts.run_eval --label v1 --sets dev,adversarial --runs 3 --baselines`. Raw files: `eval/results/day4/`.
> **Before** = v0.3 (end of Day 3). **After** = v1 (fixes F1–F4 in [01_failure_analysis.md](01_failure_analysis.md)).

## 1. Before vs after

| Set | Metric | Before (v0.3) | After (v1) |
|---|---|---|---|
| Dev (12) | Tickets fully correct | 94% (83–100%) | **100%** (all 3 runs) |
| | Dangerous mistakes per run | 0–2 | **0** |
| | Escalations caught | 94% (83–100%) | **100%** |
| | Priority exactly right | 83% (75–92%) | 89% (83–92%) |
| | Median / p95 latency | 4.2 s / 9.3 s | 3.7 s / 6.3 s |
| Break-it (10) | Tickets fully correct | 90% | **100%** (all 3 runs) |
| | Dangerous mistakes per run | 1 | **0** |
| | Escalations caught | 89% | **100%** |
| | Median / p95 latency | 3.7 s / 9.8 s | 3.5 s / 5.5 s |
| Held-out (12) | Tickets fully correct | 92% (Day 2, v0, 1 run) | **94%** (92–100%) |
| | Dangerous mistakes per run | 0 (1 run) | 0–1 (one in 1 of 3 runs, TC24) |
| | Escalations caught | 100% | 100% |
| | Median / p95 latency | 6.3 s / n/a | 3.4 s / 5.5 s |

Reading it honestly:
- Dev and break-it improved because the fixes were made on them. That shows the fixes work, not how good the system is on new tickets.
- The held-out set was not used for tuning and moved from 11/12 on one run to 34/36 over three runs. It is the most trustworthy quality figure here.
- Held-out did **not** get safer on paper: three runs exposed an unstable ticket (TC24) that Day 2's single run did not show. More runs find more, which is the point of running them.

## 2. Against the baselines (after, v1)

| Set | Metric | Keyword rules | Plain AI prompt | Triage assistant (v1) |
|---|---|---|---|---|
| Dev | Tickets fully correct | 42% | 42–58% | 100% |
| | Dangerous mistakes | 6 | 1 | 0 |
| | Escalations caught | 33% | 83% | 100% |
| | Median latency | < 0.1 s | 23–30 s | 3.7 s |
| Break-it | Tickets fully correct | 0% | 50–60% | 100% |
| | Dangerous mistakes | 8 | 3 | 0 |
| | Escalations caught | 22% | 67% | 100% |
| Held-out | Tickets fully correct | 0% (Day 2) | 33% (Day 2) | 94% (92–100%) |
| | Dangerous mistakes | 9 | 2 | 0–1 |

The plain-AI baseline uses the same model with reasoning on and one free-text prompt. It is slower (23–30 s) and less safe than the pipeline, which uses the model only to read facts.

## 3. The four metric families (v1)

| Family | Metric | Dev | Break-it | Held-out |
|---|---|---|---|---|
| Quality | Tickets fully correct | 100% | 100% | 94% (92–100%) |
| | Category right | 100% | 100% | 94% (92–100%) |
| | Priority exactly right | 89% | 93% | 86% (83–92%) |
| | Team right | 100% | 100% | 94% (92–100%) |
| | Escalations caught / precision | 100% / 100% | 100% / 100% | 100% / 100% |
| | Hidden-instruction tickets handled | pass | pass | pass |
| Speed | Median per ticket | 3.7 s | 3.5 s | 3.4 s |
| | p95 per ticket | 6.3 s | 5.5 s | 5.5 s |
| | 24 tickets in the app, 4 in parallel | 26–29 s (Day 3) | | |
| Cost | Tokens per ticket (in / out) | 1,056 / 160 | 1,157 / 158 | 1,056 / 160 |
| | Cost per ticket | **Not known**: the `qwen3.8-27b` price has not been confirmed, so no figure is given | | |
| Human effort | Tickets needing a lead or extra info (human-touch rate) | 50% | 90% | 50–58% |
| | Rep's accept / edit / reject rate, time to decide | **Not measured**: needs real reps. The audit log records both from the first real session | | |

Where the priority is not exact it is one level too **high** (e.g. dev TC06 and TC08 are P1 instead of P2). No under-prioritised P1/P2 in any v1 run on dev or break-it.

## 4. Release gates (same gates as Day 2, [design doc §7](../day2/01_system_design.md))

| Gate | Target | Dev (v1) | Break-it (v1) | Held-out (v1) | Status |
|---|---|---|---|---|---|
| G1 Escalation recall | 100% | 100% | 100% | 100% | **Pass** |
| G2 Under-prioritisation | 0 P1/P2 rated lower | 0 | 0 | 0 | **Pass** |
| G3 Schema validity | 100% | 100% | 100% | 100% | **Pass** |
| G4 Injection cases | pass | pass | pass | pass | **Pass** |
| G5 Must-not violations | 0 | 0 | 0 | **1 in 1 of 3 runs** (TC24, F6) | **Not met on held-out.** Mitigation: a person reviews every ticket |
| G6 Case pass rate | ≥ 83% | 100% | 100% | 94% (92–100%) | **Pass** |
| G7 Routing accuracy | ≥ 92% | 100% | 100% | 94% (92–100%) | **Pass** |
| G8 Escalation precision | ≥ 75% | 100% | 100% | 100% | **Pass** |
| G9 Median latency | < 5 s | 3.7 s | 3.5 s | 3.4 s | **Pass** (was failing on Day 2). p95 is 5.5–6.3 s |
| G10 Cost per ticket | < $0.002 | n/a | n/a | n/a | **Open:** price not confirmed |
## 5. LangSmith
The same scoring runs as LangSmith experiments (`python -m scripts.langsmith_eval`): datasets `triage-dev` and `triage-adversarial` (redacted text only), experiments `v1-dev-…` and `v1-adversarial-…` with per-ticket feedback (`passed`, `critical_failure`, `intent_correct`, `priority_exact`, `queue_correct`, `escalate_correct`). Every triage in the app and in the evaluation is also traced in project `triage-desk`.
