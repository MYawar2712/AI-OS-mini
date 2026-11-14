# Day 4 summary: evaluate, break and harden

> Synthetic data, real model. Every figure here is measured unless marked otherwise.

## Deliverables

| Brief requirement | Status | Evidence |
|---|---|---|
| Full test-set results and baseline comparison | ✅ | [02_regression.md](02_regression.md): 3 sets (dev 12, break-it 10, held-out 12), 3 runs each, vs keyword rules and a plain AI prompt |
| Quality, latency, cost and manual-touch metrics | 🟡 | Quality and latency measured. Cost: tokens measured, **price not confirmed**. Rep effort: **not measured** (needs a person) |
| At least 3 failure cases with root cause | ✅ 7 | [01_failure_analysis.md](01_failure_analysis.md): F1–F4 fixed, F5–F6 open on purpose (held-out), F7 latency |
| Retries, fallbacks, validation, confidence, human approval | ✅ | Key-spelling repair (F1), consistency rule R-C1 (F2), token redaction (F3), fail-high fallback (F4); all with unit tests |
| Before-and-after regression | ✅ | [02_regression.md §1](02_regression.md) |
| Feedback from the target/proxy user and changes made | ❌👤 | [03_user_feedback.md](03_user_feedback.md): none collected yet; stated as a gap |

## Headline results (v1, mean of 3 runs, range in brackets)

| | Dev | Break-it | Held-out (never tuned on) |
|---|---|---|---|
| Tickets fully correct | 100% | 100% | **94% (92–100%)** |
| Dangerous mistakes per run | 0 | 0 | 0–1 |
| Escalations caught | 100% | 100% | 100% |
| Median latency | 3.7 s | 3.5 s | 3.4 s |
| Same sets, keyword rules | 42% | 0% | 0% |
| Same sets, plain AI prompt | 42–58% | 50–60% | 33% |

## Key question: can you explain quality and failure across multiple conditions, not just one success?
**Yes, with two stated gaps.**

- **Across conditions:** 34 labelled tickets in three groups: everyday tickets, tickets written to break it (Spanish and impersonation injections, French, buried data loss, an API token, fake and played-down urgency), and a held-out group never used for tuning. Each ran 3 times because the model's answers vary.
- **Failures are explained to root cause:** a field-name spelling slip that silently sent correct answers to manual triage; a self-contradicting model answer that under-prioritised an outage; a secret type the redactor did not know. Each was found by reading the model's raw facts in the failing run, fixed in code, and locked in with a test.
- **What a single run hides:** Day 3's one dev run showed 12/12. Three runs showed 2 dangerous mistakes in one of them. Every figure is therefore reported with its range.
- **Gap 1:** two held-out tickets still fail in 1 run of 3 (wrong category). They are logged, not fixed, so the held-out score stays honest.
- **Gap 2:** no person has used it yet, so rep effort and trust are unmeasured.

## Also built today
- **LangSmith:** every triage traced (redacted text only); test sets uploaded as datasets; the evaluation runs as LangSmith experiments (`scripts/langsmith_eval.py`).
- **App:** Quality page (results vs baselines, per-ticket stability), riskiest-first inbox with filters, trace link on each card.
- **Tooling:** `scripts/run_eval.py` (multi-run evaluation with a held-out guard and checkpoint log), `setup.ps1` / `run.ps1`, CI workflow running the 238 tests, [RUNBOOK](../RUNBOOK.md).

## Contracts / config changed
`PIPELINE_VERSION` = `v1/extract-v2`; `PipelineTrace.langsmith_run_id`; redaction kind `api_token`; rule `R-C1`; fallback priority P2; `.env`: `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `TRIAGE_TRACING`. ADR-029 to ADR-033.
