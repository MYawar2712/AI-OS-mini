# Day 2 summary: design the system, ship v0

**Status:** v0 works end to end. A ticket goes through validation, redaction, the injection check, customer lookup, the LLM and the rules, then a **human approves**, and the result is written to the ticketing outbox and the audit log.
All data is **synthetic**. Numbers are **MEASURED-SYN** unless labelled otherwise.

## Key question: can this design become a repeatable system rather than a one-time generation?

**Yes, with evidence.** The design is repeatable because:

| Property | Evidence |
|---|---|
| Same input → same policy | Priority, team and escalation come from tested rules (`rules.py`, rule IDs in every trace), not free-form model output |
| Every run is checked | Output must pass the `ExtractedFacts` and `TriageResult` contracts; invalid → 1 retry → safe fallback |
| Every run is recorded | Audit log with step timings, tokens, rules fired and the human decision |
| Works on unseen inputs | 11/12 on held-out cases written before the code; dev 12/12 on two separate runs |
| One command, no manual steps | `python -m scripts.triage` (single ticket) and `python -m scripts.run_day2` (whole set) |

**Not yet proven:** that someone else can run it without help (Day 3), and that it stays reliable under deliberate breakage and run-to-run variation (Day 4).

## For a support lead (plain language)
The assistant now reads a ticket and fills in the triage, with the most important judgment calls taken out of the AI's hands:
- **The AI only reads.** It answers fixed questions: how many people are affected, is there a workaround, is a job affected today, is there a security problem, is the customer threatening to leave.
- **Written rules decide** the priority, the team, and whether a lead must look, using the same definitions a rep would use.
- **Card numbers and passwords are blanked out** before the AI sees the ticket.
- **A rep accepts, edits or rejects every result.** Nothing is written to a ticket without that.

## Results

### Held-out set: 12 new cases, written before any pipeline code and never used for tuning
| Metric | Keyword rules | Naive LLM (one prompt) | **Triage pipeline v0** |
|---|---|---|---|
| Cases passed | 0/12 | 4/12 | **11/12** |
| Critical failures | 9 | 2 | **0** |
| Escalation recall (safety) | 50% | 67% | **100%** |
| Escalation precision | 100% | 50% | **100%** |
| Urgent tickets rated too low | 6 | 0 | **0** |
| Injection case (hidden HTML comment) | FAIL | FAIL | **PASS** |
| Priority exact accuracy | 17% | 58% | **83%** |
| Routing accuracy | 58% | 92% | **92%** |
| Tickets needing a human | 92% | 75% | **58%** (50% of the set must escalate by design) |
| Median latency | < 0.1 s | 18.6 s | **6.3 s** (target < 5 s ❌) |

### Dev set: the original 12, visible while building, so optimistic
| | Keyword | Naive LLM | **Pipeline v0** |
|---|---|---|---|
| Cases passed | 5/12 | 6/12 | **12/12** |
| Escalation recall / precision | 33% / 100% | 83% / 62% | **100% / 100%** |
| Priority exact accuracy | 83% | 50% | **83–92%** (two runs) |
| Median latency | < 0.1 s | 28 s | **6.5 s** |

Full tables: [`eval/results/day2/comparison_holdout.md`](../../eval/results/day2/comparison_holdout.md), [`comparison_dev.md`](../../eval/results/day2/comparison_dev.md).

**The one held-out miss (TC19):** "send a quote for 20 extra seats" was read as a general question instead of billing. The route was wrong (Tier-1 instead of Billing), but there was no safety failure. It's recorded and **not tuned on**; it goes into Day 4 error analysis.

**What changed vs Day 1:** priority accuracy rose from 50% to 83% because the rules, not the model, assign it. That is the main finding behind ADR-017.

## Evaluation discipline (checkpoint log)
| Checkpoint | Date | Set | Pipeline | Result | Tuned after? |
|---|---|---|---|---|---|
| CP-1 | 2026-11-12 | dev | v0/extract-v1 | 12/12 | n/a |
| CP-2 | 2026-11-12 | **held-out** (first run) | v0/extract-v1 | **11/12** | **No.** TC19 logged only |
| CP-2b | 2026-11-12 | dev (re-run) | v0/extract-v1 | 12/12 (priority 83% vs 92%: run-to-run variation) | n/a |

## v0 demo (one input through the entire flow)
`python -m scripts.triage --case TC02` (reviewer types `a`). Full output: [`v0_demo_transcript.txt`](v0_demo_transcript.txt).
1. **Ticket:** "none of our 8 engineers can see today's jobs" (phone note, Enterprise customer).
2. **Triage card:** mobile_app_sync, **P1**, tier2_technical, escalate: p1_incident, ask for device/app version.
3. **Rules fired:** `R-P1` (many users blocked, no workaround), `R-MI:-account_id` (the account is known, so don't ask for it).
4. **Reviewer accepted.** Fields and an internal note were written to `data/runs/ticketing_outbox.jsonl`, and the trace and decision to `data/runs/audit.jsonl`.
5. **Timing:** the deterministic steps took < 2 ms in total. The LLM call took the rest (~10 s on this run).

## Deliverables (brief → where)
| Brief item | Deliverable |
|---|---|
| Architecture & end-to-end data flow | [01_system_design.md §1–2](01_system_design.md) |
| Input/output schemas & data contracts | [§3](01_system_design.md#3-schemas-and-data-contracts) · [`src/schemas.py`](../../src/schemas.py) (`ExtractedFacts`, `PipelineTrace`, `ReviewDecision`, `OutboxRecord` added) |
| Model, tool, storage & interface choices | [§4](01_system_design.md#4-model-tool-storage-and-interface-choices) · ADR-017 to ADR-021 in [decisions.md](../decisions.md) |
| Human approval, fallbacks, privacy, permissions | [§5–6](01_system_design.md#5-human-approval-points-fallbacks-permission-boundaries) |
| Evaluation rubric & pass/fail | [§7](01_system_design.md#7-evaluation-rubric-and-passfail-criteria) · [`eval/rubric.md`](../../eval/rubric.md) · held-out set [`eval/test_cases_holdout.jsonl`](../../eval/test_cases_holdout.jsonl) |
| v0 end to end | [`src/pipeline/`](../../src/pipeline) · [`scripts/triage.py`](../../scripts/triage.py) · [demo transcript](v0_demo_transcript.txt) · 32 new tests in [`tests/test_pipeline.py`](../../tests/test_pipeline.py) |

## How to run
```bash
python -m scripts.triage --case TC02          # v0 demo with human approval (needs DASHSCOPE_API_KEY)
python -m scripts.run_day2                    # pipeline on the dev set + comparison
python -m scripts.run_day2 --holdout          # + held-out checkpoint (also runs baselines once)
python -m pytest                              # 162 tests, no network needed
```

## Open items
| Item | When |
|---|---|
| ❌ Latency 6.3 s vs < 5 s target. All of it is the LLM call | Day 3: shorter output, then `deepseek-v4.1-flash` with reasoning off, same eval |
| ⏳ Cost per ticket (needs the `qwen3.8-27b` price per token) | Owner |
| Customer-context and ticketing adapters (replacing v0 mocks) | Day 3 |
| Error analysis incl. TC19, more adversarial cases | Day 4 |
