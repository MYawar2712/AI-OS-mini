# Day 3: Integrations and the working core flow

> All data is **synthetic**. Integrations run locally with no third-party accounts (owner decision O3.1, ADR-025).

## 1. End-to-end flow (what a rep does vs what the system does)

```
 ticket_queue.csv          Process new tickets             Triage Desk                  written back
 (status = new)   ──────►  redact → injection check  ──►  card + "Why?"  ──► Accept ──►  ticket_queue.csv: status, priority, team,
   ▲  add rows in Excel    → CRM lookup (SQLite)          Edit / Reject      Edit       escalation, missing info, internal note
   │  or "New ticket" page → LLM facts → rules             (a person)        Reject ──►  status = manual_triage (no triage fields)
   │                       → suggestion stored                                          + escalations.jsonl (+ webhook) if needs a lead
   │                         status = ready_for_review                                  + audit.jsonl, ticketing_outbox.jsonl, app_log.jsonl
```

Nothing is written to a ticket before a person decides. A suggestion lives in `data/runs/proposals.jsonl` until then.

## 2. Integrations

| # | Integration | Module | What it does | Real-system replacement |
|---|---|---|---|---|
| 1 | **Customer database (CRM)** | `src/adapters/crm.py` → `SqliteCRM` | `data/integrations/crm.sqlite`, built once from `data/synthetic/customers.json`. Opened **read-only** (`mode=ro`); one SQL query per ticket. Used by the rules only, never sent to the LLM | HubSpot/Salesforce client with `get(customer_id)` and `all()` |
| 2 | **Ticket queue (source + write-back)** | `src/adapters/ticket_queue.py` → `CsvTicketQueue` | `data/integrations/ticket_queue.csv` (opens in Excel), seeded from `data/sample/ticket_queue_sample.csv` (24 synthetic tickets). Reads rows with status `new`; writes the approved triage back to the same row | Zendesk/Freshdesk API: `read()`, `add()`, `set_status()`, `write_back()` |
| 3 | **Escalation notices** | `src/adapters/notifier.py` → `EscalationNotifier` | One line per approved escalation in `data/integrations/escalations.jsonl` (shown on Activity). If `ESCALATION_WEBHOOK_URL` is set, also posts to Slack/Teams | Same class (webhook) or a paging tool |

The pipeline only talks to `src.adapters.get_crm() / get_queue() / get_notifier()`; settings are in `config/settings.yaml → integrations`.

### Status flow in the queue
| Status | Meaning | Set by |
|---|---|---|
| `new` | Waiting for the assistant | Excel row / New ticket page / sample seed |
| `ready_for_review` | Suggestion stored; waiting for a person | Process new tickets, or "Triage this ticket" |
| `triaged` | A person accepted or edited; fields written | `handoff.record()` |
| `manual_triage` | A person rejected the suggestion; no triage fields written | `handoff.record()` |

## 3. Validation and error handling

| Situation | What happens | What the rep sees |
|---|---|---|
| Bad row in the CSV (missing message, bad date, unknown channel/status, duplicate ID) | Row skipped, others processed | "N row(s) could not be read" with line number and reason |
| CSV missing required columns | Nothing processed | The exact header line expected |
| CSV open in Excel during a save | Write refused atomically; file unchanged | "Close it and try again. Nothing was changed." |
| AI key missing | Every ticket gets a "triage manually" suggestion | Sidebar warning with the fix |
| AI service down / invalid JSON twice | That ticket gets a "triage manually" suggestion (fallback), others continue | Orange "Automatic triage failed" box on the card |
| One ticket crashes during a batch | That ticket stays `new`; the rest finish | "SYN-… not processed … press the button again" |
| Webhook down | Escalation still saved to the file | "Escalation notice partly delivered" |
| Customer DB damaged/missing | Clear message; delete the file to rebuild | Sidebar error, app stops before doing anything |

Covered by `tests/test_adapters.py` (21 tests) and `tests/test_app.py` (12 UI tests).

## 4. Logs and audit
- `data/runs/app_log.jsonl`: one JSON line per event (`triage`, `review`, `batch_start/end`, `batch_ticket_failed`) with `run_id`, timings, token counts, status. **No ticket text.**
- `data/runs/audit.jsonl`: per decision: redacted trace (with `run_id`), proposed vs final result, review, where it was delivered.
- `data/runs/ticketing_outbox.jsonl`: append-only copy of every write.

## 5. Config and secrets
- Secrets only in `.env` (git-ignored): `DASHSCOPE_API_KEY` (required for the assistant), `ESCALATION_WEBHOOK_URL` (optional). `.env.example` lists every variable.
- Everything else in `config/settings.yaml` (model, pipeline, integrations, file names) and `config/taxonomy.yaml` (rules' definitions).
- Startup check: `python -m scripts.check_setup` and the app sidebar.

## 6. Verified (2026-11-13)
Real app (headless, agent API) with the real model and a throwaway data folder: 24 new tickets processed in **29 s** (4 in parallel), 0 fallbacks; first ticket (SYN-24102) shown as P1 "needs a lead"; Accept wrote status/fields/note to the CSV row and an escalation notice; Activity listed the decision and the notice; no warnings in the server console.
