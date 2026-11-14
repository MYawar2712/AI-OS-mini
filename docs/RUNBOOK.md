# Operator runbook

For the person who keeps the Triage Desk running. Reps should read the [README](../README.md) instead.
All data in this repo is synthetic. Before using real tickets, read [Limitations](#8-before-real-tickets).

## 1. What runs where

| Piece | Where | Notes |
|---|---|---|
| Triage Desk (UI) | `streamlit run app/review.py` | Single-user local app. One rep per running copy |
| Trigger without the UI | `python -m scripts.process_queue` | Safe to schedule (e.g. Task Scheduler, every 5 min). Only pre-fills; never writes to a ticket |
| Ticket queue | `data/integrations/ticket_queue.csv` | Source and write-back target. Created from `data/sample/` on first run |
| Customer database | `data/integrations/crm.sqlite` | Read-only. Rebuilt from `data/synthetic/customers.json` if deleted |
| Escalation notices | `data/integrations/escalations.jsonl` (+ webhook) | One line per approved escalation |
| Audit log | `data/runs/audit.jsonl` | Every decision: suggestion, final, reviewer, where it was delivered |
| App log | `data/runs/app_log.jsonl` | JSON lines with `run_id`; no ticket text |
| Suggestions | `data/runs/proposals.jsonl` | Pre-filled triage waiting for a person |
| Traces (optional) | LangSmith project `triage-desk` | Redacted text only |

## 2. Configuration

| What | Where |
|---|---|
| Secrets: `DASHSCOPE_API_KEY`, optional `LANGSMITH_API_KEY`, `ESCALATION_WEBHOOK_URL` | `.env` (never committed; template in `.env.example`) |
| Model, provider, timeouts | `config/settings.yaml → llm` |
| Reasoning on/off, output cap, retries | `config/settings.yaml → pipeline` |
| File locations, CRM backend, parallel workers | `config/settings.yaml → integrations` |
| Categories, P1–P4 definitions, teams, escalation reasons, confidence threshold | `config/taxonomy.yaml` |
| Move runtime folders | `TRIAGE_DATA_DIR`, `TRIAGE_RUNS_DIR` in `.env` |
| Turn tracing off | `TRIAGE_TRACING=off` in `.env` |

Check everything at once: `python -m scripts.check_setup` (the same checks show in the app sidebar).

## 3. Daily checks (2 minutes)

1. **Activity page:** accepted-as-is rate and number rejected. A sudden drop in "accepted as-is" means the suggestions got worse or the tickets changed.
2. **Fallbacks:** "Sent to manual triage by the assistant" on the Activity page. More than a few per day means the AI service or key has a problem.
3. `data/runs/app_log.jsonl`: search for `"level": "error"` and `"status": "fallback"`.

## 4. When something breaks

| Symptom | Likely cause | What to do |
|---|---|---|
| Sidebar: "AI assistant key … not set" | `.env` missing or still has `sk-REPLACE_ME` | Put the key in `.env`, restart the app |
| Every ticket shows "Automatic triage failed" | AI service down, key revoked, or no internet | Reps triage manually (the app keeps working). Check `llm_errors` in the app log. Retry later with **Triage it again** |
| "Ticket file … is open in another program" | CSV open in Excel | Close Excel, press the button again. Nothing was changed |
| "N row(s) … could not be read" | Bad row typed into the CSV | The message gives the line and the fix. Other tickets are unaffected |
| "missing column(s)" | Header row edited | Restore the header shown in the message |
| "Customer database …" error | `crm.sqlite` damaged | Delete `data/integrations/crm.sqlite`; it is rebuilt on restart |
| "Escalation notice partly delivered" | Webhook URL wrong or service down | The notice is still in `escalations.jsonl`; fix `ESCALATION_WEBHOOK_URL` |
| A ticket is flagged "Instructions aimed at the AI" | The ticket text tried to steer the assistant | Expected behaviour. A lead reviews it; the hidden instruction was not followed |
| Suggestions look wrong after a config change | Rule or prompt regression | Run the evaluation (section 6) and compare with the last report |
| Start again from scratch (demo) | | Close the app, delete `data/integrations/` and `data/runs/` |

## 5. Changing things safely

**A rule or definition (priority, team, escalation):**
1. Edit `config/taxonomy.yaml` (definitions) or `src/pipeline/rules.py` (logic). Each rule has an ID (`R-P1`, `R-M1`…) that shows in the "Why?" panel.
2. Add or update a test in `tests/test_pipeline.py`.
3. `python -m pytest` then `python -m scripts.run_eval --label <name> --sets dev,adversarial --runs 3`.
4. Compare with the previous `eval/results/day4/<label>/report.md`. No new dangerous mistakes, pass rate not lower.
5. Record the decision in `docs/decisions.md`.

**The prompt:** edit `src/pipeline/llm_extract.py`, bump `PROMPT_VERSION`, then steps 3–5.

**The model:** change `llm.model` in `config/settings.yaml`, then steps 3–5. Keep reasoning off unless latency is not a concern (ADR-018).

**Never tune on the held-out set.** It is run only as a logged checkpoint: `python -m scripts.run_eval --label <name> --sets holdout --confirm-holdout` (ADR-021).

## 6. Evaluation

```powershell
.venv\Scripts\python -m scripts.run_eval --label v1 --sets dev,adversarial --runs 3 --baselines
.venv\Scripts\python -m scripts.langsmith_eval --sets dev,adversarial --label v1    # same scoring, as LangSmith experiments
```
Results: `eval/results/day4/<label>/report.md` and the **Quality** page in the app.

**Add a test case:** append one line to `eval/test_cases.jsonl` (or the adversarial file) following the existing format; write the expected answer *before* running the system on it; `python -m pytest tests/test_taxonomy_consistency.py`.

**Turn a real mistake into a test:** find the decision in `data/runs/audit.jsonl` (the rep's edit is the correct label), anonymise the text, add it as a case.

## 7. Privacy and permissions (what the system can and cannot do)

- Card numbers, CVVs, expiry dates, passwords and API tokens are replaced before any text leaves the machine (model call, traces, logs).
- Customer account data is used only by the local rules; it is never sent to the model.
- The assistant has no tools: it cannot send messages, change accounts, or write to tickets. Only `src/pipeline/handoff.py` writes, and only after a person's decision.
- The model's output cannot set priority, team or escalation; rules do.

## 8. Before real tickets

- The model runs on a third-party cloud (Alibaba Cloud Model Studio, Singapore region). Data-residency and DPA review are required first.
- Redaction is pattern-based; it will miss unusual secret formats. Review `src/pipeline/redact.py` against your real data.
- The CSV queue is single-writer. Replace `src/adapters/ticket_queue.py` with your helpdesk's API (same four methods) for multi-user use.
- Results are measured on synthetic tickets only. Run a shadow period first: suggestions shown, reps decide as today, compare.
