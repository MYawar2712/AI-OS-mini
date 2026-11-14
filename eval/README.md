# Evaluation package

Everything needed to check how well the triage assistant works, and to re-run it. All tickets are **synthetic**; all figures are **measured** with the real model (`qwen3.8-27b`) unless marked otherwise.

## Headline (v1, each set run 3 times; range in brackets)

| | Everyday tickets (12) | Tickets written to break it (10) | **Held-out, never tuned on (12)** |
|---|---|---|---|
| **Tickets fully correct** | 100% | 100% | **94% (92–100%)** |
| Dangerous mistakes per run | 0 | 0 | 0–1 |
| Escalations caught | 100% | 100% | 100% |
| Median time per ticket | 3.7 s | 3.5 s | 3.4 s |
| *Keyword rules only* | 42% | 0% | 0% |
| *Plain AI prompt* | 42–58% | 50–60% | 33% |

The first two sets were used to find and fix failures, so the held-out column is the honest estimate.

## What is in the package

| Required item | Where |
|---|---|
| **Test cases and expected behaviour** (34 cases) | [test_cases.jsonl](test_cases.jsonl) (12 everyday) · [test_cases_holdout.jsonl](test_cases_holdout.jsonl) (12 held-out) · [test_cases_adversarial.jsonl](test_cases_adversarial.jsonl) (10 break-it). Each case has the ticket, the expected category, priority, team and escalation, and "must not" rules. Described in [docs/day1/04_test_cases.md](../docs/day1/04_test_cases.md) |
| **How a case is scored, and pass/fail criteria** | [rubric.md](rubric.md) · scorer: [metrics.py](metrics.py) · release gates: [regression §4](../docs/day4/02_regression.md) |
| **Baseline vs final comparison** | [docs/day4/02_regression.md](../docs/day4/02_regression.md): before/after hardening, and against keyword rules and a plain AI prompt |
| **Pass/fail per case** | [results/day4/v1/report.md](results/day4/v1/report.md) (everyday + break-it) · [results/day4/v1-holdout/report.md](results/day4/v1-holdout/report.md) (held-out) · before hardening: [results/day4/v0.3/report.md](results/day4/v0.3/report.md) |
| **Failure analysis** (7 failures to root cause) | [docs/day4/01_failure_analysis.md](../docs/day4/01_failure_analysis.md) |
| **Quality, speed, cost and human-effort metrics** | [regression §3](../docs/day4/02_regression.md). Cost: tokens measured, price not confirmed. Human effort: not measured (no real reps yet) |
| **Raw outputs of every run** | [results/day4/](results/day4/) (predictions, per-run scores, summaries) · earlier days: [results/](results/) |
| **Model selection** (4 models, rule fixed in advance) | [results/model_comparison.md](results/model_comparison.md) |
| **User feedback status** | [docs/day4/03_user_feedback.md](../docs/day4/03_user_feedback.md): none collected yet, stated as a gap |

## Re-run it

```powershell
.venv\Scripts\python -m pytest                                                              # 238 tests, no keys needed
.venv\Scripts\python -m scripts.run_eval --label mine --sets dev,adversarial --runs 3 --baselines
.venv\Scripts\python -m scripts.run_eval --label mine --sets holdout --runs 3 --confirm-holdout   # logged checkpoint; never tune on it
```

The same results are shown in the app on the **Quality** page.

## Limits
- 34 synthetic tickets written by one person: a regression bar, not a statistical result.
- Two held-out tickets still fail in 1 run of 3 (wrong category); left unfixed so that set stays untuned.
- No real support rep has used the system, so time saved and accept/edit rates are unmeasured.
