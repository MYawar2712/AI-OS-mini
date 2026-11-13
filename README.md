# Help Desk Triage Agent (5-day AI workflow challenge)

An AI-assisted triage assistant for Tier-1 support at a B2B field-service SaaS company. For each new ticket it pre-fills **category, priority, team, escalation decision and a short summary**. A support rep accepts, edits or rejects it, and only then is anything written to the ticket.

> ⚠️ **All data in this repo is SYNTHETIC.** No real customers, tickets, or people. Numbers are labelled *measured on synthetic set*, *estimated*, or *assumed*.

**Plan & progress:** [docs/PLAN.md](docs/PLAN.md) · [Day 3 summary](docs/day3/00_day3_summary.md) · [integrations](docs/day3/01_integrations.md) · [system design](docs/day2/01_system_design.md) · [Day 1 summary](docs/day1/00_day1_summary.md)

---

## For support reps: start in 3 steps (Windows)

You need **Python 3.11 or newer** installed ([python.org](https://www.python.org/downloads/), tick "Add Python to PATH"). Open **PowerShell** in this folder (in File Explorer: click the address bar, type `powershell`, press Enter).

**1. Install** (once, about 5–10 minutes; it downloads the libraries the app needs):
```powershell
python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt
```
Red text saying *"A new release of pip is available"* is only a notice, not an error. You can ignore it.

**2. Add the AI key** (once): run this in the same PowerShell window, then replace `sk-REPLACE_ME` with your key in the Notepad window that opens, and save:
```powershell
Copy-Item .env.example .env; notepad .env
```
(No key? The app still works, but every ticket is sent to manual triage.)

**3. Open the Triage Desk** (every time):
```powershell
.venv\Scripts\streamlit run app/review.py
```
Your browser opens the Triage Desk. To stop it, close the PowerShell window.

### Using the Triage Desk
1. **Inbox → Process new tickets.** The assistant reads every *New* ticket (a few seconds each) and pre-fills a triage. Nothing is written yet.
2. **Click a ticket marked *Ready for review*.** Read the card:
   - a **red box** means a lead must look before anyone acts;
   - **Why?** shows exactly which written rules set the priority and team.
3. **Accept**, **Edit** (change category, priority, team or "needs a lead") or **Reject** (you'll triage it yourself).
4. Your decision is written back to the ticket in `data/integrations/ticket_queue.csv` (opens in Excel). If it needs a lead, an escalation notice is sent. Everything is listed under **Activity**.

To add a ticket, use **New ticket** in the app, or add a row to `ticket_queue.csv` with status `new`. Either Excel save format works ("CSV UTF-8" or the default "CSV (Comma delimited)"). Close Excel before going back to the app.
To start the demo again, close the app and delete the `data/integrations` folder.

### If something goes wrong
The sidebar shows any setup problem and what to do. You can also run `.venv\Scripts\python -m scripts.check_setup`.

| You see | What to do |
|---|---|
| "Assistant not configured" | Step 2: put the key in `.env`, then restart the app |
| "The AI service did not respond" | The ticket was sent to manual triage. Check your internet and try again in a minute |
| "Ticket file … is open in another program" | Close `ticket_queue.csv` in Excel, then press the button again. Nothing was changed |
| "row(s) in the ticket file could not be read" | The message names the line and the problem (e.g. missing message, unknown channel). Fix that row in Excel |

---

## For developers

```powershell
.venv\Scripts\python -m pytest                     # 196 tests, no network needed
.venv\Scripts\python -m scripts.process_queue      # trigger without the UI (can be scheduled)
.venv\Scripts\python -m scripts.triage --case TC02 # one ticket end to end in the terminal, with approval
.venv\Scripts\python -m scripts.run_day3 --label x # dev-set quality + latency check (never held-out)
.venv\Scripts\python -m scripts.run_day2 --holdout # Day 2 scoring vs baselines on dev + held-out
.venv\Scripts\python -m scripts.run_day1           # reproduce Day 1 (synthetic data, baselines)
```

How it works: **fixed code** hides card numbers and passwords, flags instructions aimed at the AI, and looks the customer up in the CRM; **the LLM** (`qwen3.8-27b`, Alibaba Cloud) only reads the ticket into a fixed set of facts; **written rules** (`src/pipeline/rules.py`) set priority, team and escalation; **a person** approves before anything is written.

## Repo map

| Path | What |
|---|---|
| `config/taxonomy.yaml` | Intents, P1–P4 definitions + tie-breaks, queues, escalation reasons (single source of truth) |
| `config/settings.yaml` | LLM provider/model, pipeline settings, integrations (file locations, CRM backend), token prices |
| `.env.example` | The only secrets: AI key, optional webhook. Copy to `.env` |
| `app/` | Streamlit "Triage Desk": inbox (ticket queue), triage card, Accept / Edit / Reject, activity, help |
| `src/pipeline/` | Triage pipeline: redact, injection, context, llm_extract, rules, run; `batch` (trigger), `proposals`, `handoff` (the only writer) |
| `src/adapters/` | Integrations: `crm` (SQLite customer DB), `ticket_queue` (CSV source + write-back), `notifier` (escalations, optional webhook) |
| `src/observability.py`, `src/preflight.py` | Structured JSON logs with run IDs, plain-language errors, startup checks |
| `src/schemas.py`, `schemas/` | Pydantic v2 contracts and exported JSON Schemas |
| `data/synthetic/`, `data/sample/` | 25 fictional customer accounts, KB articles; sample ticket queue (24 synthetic tickets) |
| `data/integrations/`, `data/runs/` | Runtime files (git-ignored): live queue, CRM database, escalations; audit log, app log, suggestions |
| `scripts/` | `process_queue`, `check_setup`, `triage`, `run_day1/2/3`, `compare_models`, `build_sample_queue`, … |
| `baselines/`, `eval/` | Keyword + naive LLM baselines; 12 dev + 12 held-out test cases, rubric, metrics, results |
| `docs/` | `PLAN.md` (tracker), `day1/`–`day3/`, `decisions.md` (ADRs), `assumptions.md` |
