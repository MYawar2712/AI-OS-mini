# Day 5 summary: handoff, prove value and present

## Deliverables

| Brief requirement | Status | Evidence |
|---|---|---|
| Live demo or runnable repo | ✅ | Runs locally; CI runs the 238 tests on every push |
| One-command or 3-step setup | ✅ measured | `setup.ps1` then `run.ps1`. Tested on a clean clone: 6 min 56 s, ended "Ready"; tests pass in the clone |
| User README and operator runbook | ✅ | [README](../../README.md) · [RUNBOOK](../RUNBOOK.md) |
| Docs: architecture, data flow, evaluation set, results, limitations | ✅ | [system design](../day2/01_system_design.md) · [integrations and data flow](../day3/01_integrations.md) · [results](../day4/02_regression.md) · [failures](../day4/01_failure_analysis.md) · limitations in the [case study §7](../CASE_STUDY.md) |
| 5-minute screen-recorded demo | 👤 | Script prepared. **The recording itself has to be made by the owner** |
| Portfolio case study | ✅ | [CASE_STUDY.md](../CASE_STUDY.md), all 8 sections |
| Adoption and quality metrics for the first two weeks, next iteration | ✅ | [02_rollout_metrics.md](02_rollout_metrics.md) |
| AI collaboration note | 👤 | Written and kept outside the repo for the owner to submit |

## Key question: can another person understand, run, trust and improve the system?

| | Answer | Evidence |
|---|---|---|
| **Understand** | Yes | One-page case study; architecture diagram; 33 recorded decisions with the alternatives; the "Why?" panel explains each result in plain words |
| **Run** | Yes, on a clean machine | One-command setup tested on a fresh clone; startup checks with a fix for each problem; an automated walkthrough of the README found and fixed 7 setup problems. **Not yet shown with a real non-developer** |
| **Trust** | Partly | Measured against two baselines on three test sets with ranges; dangerous mistakes counted separately; failures published, including two that are still open. **Trust by real reps is unmeasured** |
| **Improve** | Yes | The runbook says how to change a rule, the prompt or the model and re-run the evaluation; every rep edit is logged and can become a test case; held-out discipline is enforced by the tool |

## What is not done
1. **A person using it.** First run (3.10) and feedback (4.8) are open. Nothing was written in their place.
2. **The demo video.** Needs the owner.
3. **Cost per ticket.** Needs the confirmed model price.
4. **Real integrations.** The queue and CRM are file-based stand-ins behind adapters.
