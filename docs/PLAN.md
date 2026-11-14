# Implementation plan and tracker (5-day challenge)

> **Single source of truth for progress.** Every brief requirement → status → evidence → next action.
> Legend: ✅ done · 🟡 partial / done with caveat · ❌ not started · 👤 needs the owner (a decision, account, or a real person).
> Last updated: 2026-11-14 (Day 4 built; person-dependent items 3.10 and 4.8 still open).

---

## 0. How to resume (read this first)

When the owner says **"resume Day N"**:
1. Read §2 (status at a glance) and the **Day N** section below. Work top to bottom on the first unchecked `[ ]` task.
2. Health check before changing anything:
   ```powershell
   git status --short; git log --oneline -3
   .venv\Scripts\python -m pytest -q
   ```
   Expect all tests green and the "last commit" noted in §2. If not, fix that first.
3. Check the Day N **owner inputs (👤)**. Ask for any that are still missing *before* building the parts that need them.
4. At the end of the session:
   - Tick the boxes and update §2 and the Day N "status" line.
   - Add new ADRs to `docs/decisions.md` and new assumptions to `docs/assumptions.md`.
   - Give the owner the one-line commit command (never commit or push directly).

Honesty rules that apply to every day:
- Never present estimates or simulated numbers as measured.
- Anything a "user/proxy user" does must actually be done by a person.
- Held-out cases are never used for tuning (ADR-021).

---

## 1. Target architecture (final v1, Day 5)

### 1.1 Layers and boundaries
```
 TRIGGER            INGEST & SAFETY            AI              POLICY            HUMAN              OUTPUT
 ─────────          ───────────────            ──              ──────            ─────              ──────
 ticket source  →   validate → redact →   →  LLM fact     →  rules: P1–P4,  →  review UI:     →  ticketing adapter
 adapter            injection check →         extraction       queue, escalate,  accept / edit /    (fields + internal
 (folder / CSV /    customer context          (strict JSON,    missing info,     reject             note) + notifier
  sheet / form)     adapter (CRM)             no tools)        action guard                         (escalations) +
                                                                                                    audit log + metrics
```
| Layer | Owns | Never does | Module (✅ exists / ❌ planned) |
|---|---|---|---|
| Trigger / ingest | Picking up new tickets, parsing into `InboundTicket` | Business decisions | ✅ `src/adapters/ticket_queue.py` + `src/pipeline/batch.py` |
| Safety | Validation, secret redaction, injection detection | Calling the LLM with raw secrets | ✅ `src/pipeline/redact.py`, `injection.py` |
| Context | Read-only customer lookup | Writing to the CRM; sending CRM data to the LLM | ✅ `context.py` → `src/adapters/crm.py` (SQLite) |
| AI | Reading the ticket into `ExtractedFacts` | Priority, queue, escalation, tools, writes | ✅ `src/pipeline/llm_extract.py`, `src/llm_client.py` |
| Policy | Priority, queue, escalation, missing info, safe action | Free-form judgement | ✅ `src/pipeline/rules.py` + `config/taxonomy.yaml` |
| Human | Approve / edit / reject; escalations | n/a | ✅ CLI `scripts/triage.py` + ✅ web UI `app/review.py` (polish Day 5) |
| Output | Ticket fields + internal note, escalation notice, audit | Customer-facing replies, refunds, account changes | ✅ `handoff.py` → `ticket_queue.write_back`, `notifier.py` |
| Observability | Structured logs, traces, metrics | Storing unredacted secrets | ✅ `src/observability.py` (JSON log, run IDs) + audit; LangSmith optional later |
| Evaluation | Test sets, rubric, metrics, comparisons | Tuning on held-out data | ✅ `eval/`, `scripts/run_day2.py` |

### 1.2 Target repo structure (✅ = exists now)
```
config/            taxonomy.yaml ✅  settings.yaml ✅  pain_model.yaml ✅
src/
  schemas.py ✅  taxonomy.py ✅  llm_client.py ✅
  pipeline/        redact ✅ injection ✅ context ✅ llm_extract ✅ rules ✅ run ✅ handoff ✅
  adapters/  ❌    ticket_source.py  crm.py  ticketing.py  notifier.py      (Day 3)
  observability.py ❌                                                        (Day 3)
app/  ✅           review UI (Streamlit) for non-developers: built early, polish on Day 5
scripts/           run_day1 ✅ run_day2 ✅ triage ✅ compare_models ✅ … run_eval ✅ langsmith_eval ✅
baselines/ ✅      keyword, naive LLM
eval/              test_cases.jsonl ✅(12 dev)  test_cases_holdout.jsonl ✅(12)  test_cases_adversarial.jsonl ✅(10)
                   rubric.md ✅  metrics.py ✅  results/ ✅
data/synthetic/ ✅ customers, KB          data/runs/ (git-ignored) audit + outbox ✅
docs/              PLAN.md ✅  day1/ ✅  day2/ ✅  day3/ ✅  day4/ ✅  day5/ ❌
                   decisions.md ✅  assumptions.md ✅
                   README (user) ✅  RUNBOOK.md ✅  CASE_STUDY.md ❌  AI_COLLABORATION.md ❌👤
tests/ ✅          238 tests (incl. 14 UI, 23 adapter tests), no network needed
```

### 1.3 Contracts (stable; change only with an ADR)
`InboundTicket` → `ExtractedFacts` (LLM) → `TriageResult` + `PipelineTrace` → `ReviewDecision` → `OutboxRecord`. All are in `src/schemas.py`, described in [day2/01_system_design.md §3](day2/01_system_design.md).

---

## 2. Status at a glance

| Day | Status | Last evidence | Blocking items |
|---|---|---|---|
| 1 Discover & baseline | ✅ done (with documented gaps) | [day1/00_day1_summary.md](day1/00_day1_summary.md) | 👤 real-user interview not possible (documented) |
| 2 Design & v0 | ✅ done, pushed (`d611d24`) | [day2/00_day2_summary.md](day2/00_day2_summary.md) | Latency gate G9 fails (6.3 s vs 5 s), carried to Day 3 |
| 3 Working core | 🟡 built and verified; owner run pending | [day3/00_day3_summary.md](day3/00_day3_summary.md) | 👤 owner run (3.10), recorded in [day3/02_proxy_user_run.md](day3/02_proxy_user_run.md) |
| 4 Evaluate & harden | 🟡 built; user feedback open | [day4/00_day4_summary.md](day4/00_day4_summary.md) | 👤 feedback from a person (4.8); 👤 model price (cost metric) |
| 5 Handoff & present | ❌ | n/a | 👤 record the 5-min video; 👤 AI collaboration note decision |

**Built ahead of schedule (2026-11-12, owner request; Day 3 plan left unchanged):** Streamlit review UI `app/review.py` ("Triage Desk"): inbox of synthetic tickets, add-a-ticket form, plain-language triage card, "Why?" panel, Accept / Edit / Reject → outbox + audit, Activity tab, Help tab. 6 UI tests (`tests/test_app.py`), verified with the real model on TC10. Relevant to tasks 3.6 / 5.5. Day 3 integrations will plug into it. **Redesigned the same day** with Streamlit's official bundled agent skill (ADR-024): multipage nav (Inbox / New ticket / Activity / Help), theme config, selectable inbox table, native badges; 10 UI tests; verified via the agent API.

Last pushed commit: `16498b2` (Day 3). Day 4 is uncommitted until the owner runs the commit command.
Owner-wide pending: 👤 `qwen3.8-27b` price per token (cost metric) · 👤 rotate the Alibaba API key.

---

## 3. Day 1: Discover, map and baseline. Status: ✅ done

| Brief requirement | Status | Evidence |
|---|---|---|
| Target user and job-to-be-done | ✅ | [day1/01_user_and_jtbd.md](day1/01_user_and_jtbd.md) |
| Workflow map: trigger, input, judgement, tool, approval, output, exception | ✅ | [day1/02_workflow_map.md](day1/02_workflow_map.md) (table + current/future diagrams) |
| Evidence of pain (frequency, time, rework, errors) | 🟡 | [day1/03_evidence_of_pain.md](day1/03_evidence_of_pain.md): cost model, all inputs **assumed** |
| Interview notes or observational evidence | 🟡👤 | Guide ready; **no support staff available**, documented in [00 summary → Validation gaps](day1/00_day1_summary.md#validation-gaps-and-how-to-close-them) |
| Baseline: manual process or simple ChatGPT use | ✅ | Keyword + naive LLM measured; 4-model comparison [model_comparison.md](../eval/results/model_comparison.md); manual time is an **estimate** |
| Success metric and non-goals | ✅ | [day1/06_success_metrics_and_non_goals.md](day1/06_success_metrics_and_non_goals.md) |
| 8–12 test cases (representative / edge / failure) | ✅ | 12 dev cases [eval/test_cases.jsonl](../eval/test_cases.jsonl), [04_test_cases.md](day1/04_test_cases.md) |
| v1 scope for Day 5 | ✅ | [day1/07_v1_scope.md](day1/07_v1_scope.md) |
| Key question answered | ✅ | [00_day1_summary.md](day1/00_day1_summary.md) |

Optional, any time (improves evidence; see the Validation gaps section in the Day 1 summary): LLM second labeller (~25 min) · public benchmarks with sources (~20 min) · owner as proxy rep (~1 h).

---

## 4. Day 2: Design the system and ship v0. Status: ✅ done (not pushed)

| Brief requirement | Status | Evidence |
|---|---|---|
| Architecture and end-to-end data flow | ✅ | [day2/01_system_design.md §1–2](day2/01_system_design.md) |
| Input/output schemas and data contracts | ✅ | §3 + [src/schemas.py](../src/schemas.py) + [schemas/](../schemas) |
| Model, tool, storage, interface choices with rationale | ✅ | §4 + ADR-013, 016–022 |
| Human approval, fallbacks, privacy, permission boundaries | ✅ | §5–6 |
| Evaluation rubric and pass/fail criteria | ✅ | §7 + [eval/rubric.md](../eval/rubric.md); 10/11 gates pass |
| v0 moving one real input through the entire flow | ✅ | `python -m scripts.triage --case TC02`, [transcript](day2/v0_demo_transcript.txt) |
| Key question answered | ✅ | [00_day2_summary.md](day2/00_day2_summary.md) |

Results: held-out **11/12**, 0 critical failures (keyword 0/12, naive LLM 4/12). Dev 12/12.
Carried forward: ❌ latency 6.3 s (gate < 5 s) → Day 3 task 3.7 · TC19 miss → Day 4 RCA.

---

## 5. Day 3: Build the working core. Status: 🟡 built and verified (2026-11-13); 3.10 owner run pending

Owner decisions: O3.1 = default (SQLite CRM, CSV ticket queue with write-back, escalation file + optional webhook); O3.2 = Streamlit; O3.3 = owner runs it as fallback proxy (labelled as such).

**Brief:** working core flow trigger → final output for a non-developer · ≥ 2 real data-source/tool integrations · validation, structured outputs, logs, useful error messages · config/secrets separated · one interface · first execution by the target or a proxy user.
**Key question:** can someone else run the core workflow when you are not beside them?

### 👤 Owner inputs needed at the start of Day 3
| # | Decision | Options (default first) |
|---|---|---|
| O3.1 | Integrations to use (need ≥ 2 real ones) | **Default (no accounts needed): (a) SQLite customer database as the CRM, (b) Excel/CSV ticket queue: read new tickets, write triage back, (c) LangSmith tracing (owner has a key).** Upgrades if the owner has accounts: Google Sheets ticket queue, Slack/Teams webhook for P1 escalations, email inbox (IMAP) |
| O3.2 | Interface for non-developers | **Default: Streamlit web page** (ticket queue → triage card → Accept/Edit/Reject buttons). Alternative: keep CLI only (weaker on UX score) |
| O3.3 | Proxy user for the first run | A non-developer who follows the README **without help** (friend/colleague, or the owner as fallback, labelled as such). Must actually happen |

### Tasks
- [x] **3.1 Adapters (integration #1: customer data).** `src/adapters/crm.py`: an interface with a SQLite implementation (seeded from `customers.json`) plus the existing JSON one. `context.py` calls the interface. Tests.
- [x] **3.2 Adapters (integration #2: ticket queue).** `src/adapters/ticket_source.py` reads new tickets (CSV/Excel or Sheets) with validation and clear per-row errors. `src/adapters/ticketing.py` writes approved triage back (status, fields, internal note). Tests with temp files.
- [x] **3.3 Integration #3 (optional): notifications / tracing.** Escalation notifier (Slack/Teams webhook, or a file-based "escalations" log), and/or LangSmith tracing when `LANGSMITH_API_KEY` is set. *(Done: escalation file + optional webhook. LangSmith waits for the owner's key.)*
- [x] **3.4 Trigger.** "Process new tickets" picks up every ticket with status `new` from the queue (button in the UI plus the CLI `python -m scripts.process_queue`).
- [x] **3.5 Logging and useful errors.** `src/observability.py`: structured JSON logs with a run ID per ticket. Each error message tells a non-developer **what happened and what to do** (missing key, bad file, API down → "ticket sent to manual triage").
- [x] **3.6 Interface.** `app/review.py` (Streamlit): queue view, triage card in plain language, why (rules fired), Accept / Edit / Reject, confirmation of what was written. Launch: `streamlit run app/review.py`.
- [x] **3.7 Latency fix (gate G9 < 5 s).** Shorter output contract (drop or trim `rationale`, cap summary). Re-measure. If still > 5 s, run `deepseek-v4.1-flash` with reasoning off under the same dev eval and decide by ADR. **Never on held-out.** *(Done: extract-v2, median 6.0 → 3.6 s, quality unchanged, ADR-026; no model switch.)*
- [x] **3.8 Config/secrets audit.** Everything configurable in `config/*.yaml`; secrets only in `.env`; `.env.example` complete (Alibaba, LangSmith, webhook). Startup check with a friendly message.
- [x] **3.9 User README v1 + quick start** (≤ 3 steps) written for a non-developer.
- [ ] **3.10 👤 First execution by a proxy user.** *(Still open. An automated clean-room README walkthrough was done instead on 2026-11-13, labelled as such, with 7 findings fixed: [day3/03_cleanroom_walkthrough.md](day3/03_cleanroom_walkthrough.md). It is not a substitute for a person.)* They follow the README alone. Record in `docs/day3/02_proxy_user_run.md`: who, setup time, where they got stuck, what they understood or misread on the card, their verbatim quotes. **Real session only.**
- [x] **3.11 Day 3 docs.** `docs/day3/00_day3_summary.md` (incl. key-question answer), `01_integrations.md`; ADRs; update §2 of this plan.

**Exit criteria:**
- A non-developer processes the queue in the UI, end to end: new tickets → triage → approve → written back plus an escalation notice.
- ≥ 2 real integrations are working.
- All tests are green.
- Dev score is not lower than Day 2 (12/12).
- Latency gate decided (pass, or documented trade-off).

---

## 6. Day 4: Evaluate, break and harden. Status: 🟡 built 2026-11-14; 4.8 (person) open

**Brief:** full test-set results + baseline comparison · quality/latency/cost/manual-touch metrics · ≥ 3 failure cases with root cause · retries/fallbacks/validation/confidence/human approval as needed · before-and-after regression · feedback from the target/proxy user + changes made.
**Key question:** can you explain quality and failure across multiple conditions, not just one success?

### Tasks
- [x] **4.1 Full results.** All systems (keyword, naive LLM, pipeline v0, pipeline v1) on dev + held-out. One script: `scripts/run_eval.py` → `eval/results/day4/`.
- [x] **4.2 Variance.** Run the pipeline 3× on each set and report mean ± range (model non-determinism, seen on Day 2: priority 83–92%).
- [x] **4.3 Break it (adversarial set).** `eval/test_cases_adversarial.jsonl` (~8–10): new injection styles (non-English, base64, "as the admin…"), very long threads, empty body, non-English-dominant text, attachment-only ticket, API timeout / invalid JSON (fault injection), missing customer file, malformed CSV row.
- [x] **4.4 ≥ 3 failure analyses** in `docs/day4/01_failure_analysis.md`: symptom → root cause → fix → evidence. Candidates:
  - TC19: a quote read as a general question
  - latency
  - run-to-run priority variance
  - adversarial misses
  - a proxy-user confusion from Day 3
- [x] **4.5 Hardening.** Targeted fixes (rules, prompt, retries, confidence indicator on the card, extra human-approval triggers). Each fix tied to a failure ID.
- [x] **4.6 Before/after regression.** v0 vs v1 on dev, held-out and adversarial, in one table (`docs/day4/02_regression.md`). Report honestly where nothing improved. Held-out is run **once** for v1 and logged.
- [x] **4.7 Metrics.** *(Quality + latency measured; cost waits for the price; rep effort waits for a person.)* Quality (pass rate, escalation recall/precision, priority/routing), latency (median/p95), cost (needs the 👤 price), manual-touch (human-touch rate + edit rate from the audit log).
- [ ] **4.8 👤 Proxy-user feedback round 2.** *(Open: no person yet. Stated as a gap in day4/03_user_feedback.md.)* Same or new proxy user tries v1. Record feedback → changes → status in `docs/day4/03_user_feedback.md`.
- [x] **4.9 Day 4 summary** with the key-question answer; ADRs; update §2.

**Exit criteria:**
- Safety gates G1–G5 pass on dev + held-out + adversarial (or each failure is explained).
- ≥ 3 RCAs written.
- Regression table committed.
- Proxy feedback recorded with responses.

---

## 7. Day 5: Handoff, prove value and present. Status: ❌

**Brief:** live demo / runnable repo · one-command or 3-step setup · user README + operator runbook · docs (architecture, data flow, eval set, results, limitations) · 5-min screen-recorded demo · portfolio case study · adoption and quality metrics for the first two weeks + next iteration plan.
**Key question:** can another person understand, run, trust and improve the system?

### Tasks
- [ ] **5.1 Setup in ≤ 3 steps**, tested on a clean clone (e.g. `setup.ps1` / `make setup`): venv + install, copy `.env.example`, run the UI.
- [ ] **5.2 User README** (non-developer: what it does, how to triage, what the card means, when to escalate).
- [ ] **5.3 Operator runbook** `docs/RUNBOOK.md`: config, keys, model switch, logs/audit, failure playbook (API down, bad file, injection alert), how to add a test case, how to re-run the eval, how to change a rule safely.
- [ ] **5.4 Final docs pack**: architecture + data flow (update the design doc to v1), evaluation set description, final results vs baselines, limitations.
- [ ] **5.5 Polished review UI** (non-developer UX): clear approval points, confidence indicator, "why" panel, error states.
- [ ] **5.6 Case study** `docs/CASE_STUDY.md` covering:
  - user and problem
  - workflow and bottleneck
  - scope and non-goals
  - architecture and trade-offs
  - AI vs human work split
  - failures, changes and results
  - limitations
  - next two-week plan
- [ ] **5.7 Adoption and quality metrics for the first two weeks + next-iteration plan** (`docs/day5/02_rollout_metrics.md`). Example metrics: acceptance rate, edit rate by field, escalation precision, P1 time-to-flag, median review seconds, fallback rate, cost/day. Include targets and how each is measured from the audit log.
- [ ] **5.8 👤 AI collaboration note** `docs/AI_COLLABORATION.md`: tools used and their roles, work delegated, how results were verified, outputs rejected or corrected, decisions owned. **Required by the brief; see open decision D1.**
- [ ] **5.9 Demo script** (5 min: problem + baseline → live flow → non-dev UX → eval + failure handling → results + main limitation) + 👤 **owner records the video**.
- [ ] **5.10 Final check** against the deliverables (§8) and the scoring rubric (§9); update this plan to "complete".

---

## 8. Final deliverables checklist (from the brief)

| Deliverable | Required content | Status | Where |
|---|---|---|---|
| Working system | Runnable repo, sample data, executable core path, example config without secrets | ✅ UI + 3 integrations (Day 3); clean-clone test on Day 5 | repo, `.env.example`, `data/synthetic/` |
| Evaluation package: test cases + expected behaviour | 8–12+ cases | ✅ 12 dev + 12 held-out | `eval/` |
| Evaluation package: baseline vs final | comparison | 🟡 vs v0 (Day 2); final on Day 4 | `eval/results/day2/` |
| Evaluation package: pass/fail + failure analysis | per case + RCA | 🟡 pass/fail ✅, RCA Day 4 | n/a |
| Evaluation package: quality/speed/cost/human metrics | all four | 🟡 cost TBC 👤 | n/a |
| Case study | 8 sections | ❌ Day 5 | `docs/CASE_STUDY.md` |
| AI collaboration note | 5 sections | ❌👤 Day 5 (D1) | `docs/AI_COLLABORATION.md` |
| Demo video (5 min) | 6 beats | ❌👤 Day 5 | script in `docs/day5/` |

## 9. Scoring rubric → where it's earned

| Criterion (weight) | Main evidence | Gap to close |
|---|---|---|
| Problem leverage & scope (15%) | Day 1 docs, non-goals, north-star tied to rep time | Real-user evidence (👤, documented as a gap) |
| Architecture & engineering (20%) | Design doc, contracts, ADR-017 facts→rules, adapters | Day 3 adapters + trigger |
| Working product & reliability (20%) | v0 flow, fallbacks, audit, 162 tests | Day 3 UI + integrations; Day 4 hardening; reproducible setup |
| Evaluation & learning loop (20%) | Baselines, held-out set, checkpoint log, scoring-fix changelog | Day 4 RCAs, adversarial set, before/after, variance |
| Non-developer UX & adoption (15%) | Plain-language triage card | Day 3/5 web UI, README, runbook, real proxy-user run |
| Ownership & communication (10%) | Decisions log, honest caveats | Case study, demo video, AI collaboration note |

## 10. Open decisions for the owner
| ID | Decision | Why it matters | Needed by |
|---|---|---|---|
| D1 | **AI collaboration note vs the "no AI attribution in repo files" rule.** The brief *requires* a note describing the AI tools used. Options: (a) put it in the repo as `docs/AI_COLLABORATION.md`; (b) keep it outside the repo and submit it separately. Commit metadata stays owner-only either way | Missing it loses part of "Ownership & communication"; misstating AI use is worse | Day 5 |
| D2 | ~~Integrations (O3.1) and interface (O3.2)~~ decided 2026-11-13: default offline integrations + Streamlit | n/a | done |
| D3 | Proxy user (O3.3, 4.8) | Brief requires a real first run and real feedback | Day 3 / Day 4 |
| D4 | `qwen3.8-27b` price per token | Cost metric and G10 | Day 4 |
| D5 | Rotate the Alibaba API key | Security hygiene (it was pasted in chat) | Any time |
