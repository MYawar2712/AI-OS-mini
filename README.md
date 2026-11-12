# Help Desk Triage Agent (5-day AI workflow challenge)

An AI-assisted triage assistant for Tier-1 support at a B2B field-service SaaS company. For each incoming ticket it pre-fills **intent, priority, queue, escalation decision and a structured summary**, and a support rep accepts or edits the result.

> ⚠️ **All data in this repo is SYNTHETIC.** No real customers, tickets, or people. Numbers are labelled *measured on synthetic set*, *estimated*, or *assumed*.

**Plan & progress:** [docs/PLAN.md](docs/PLAN.md) · **Start here:** [Day 2 summary](docs/day2/00_day2_summary.md) · [system design](docs/day2/01_system_design.md) · [Day 1 summary](docs/day1/00_day1_summary.md)

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.run_day1     # or: make day1   (reproduces all Day 1 results)
python -m pytest               # or: make test

# Review UI (for support reps): opens in your browser
streamlit run app/review.py

# Day 2: triage pipeline v0
python -m scripts.triage --case TC02     # one ticket end to end, with human approval
python -m scripts.run_day2 --holdout     # score pipeline vs baselines on dev + held-out sets
```

For the naive LLM baseline: `cp .env.example .env` and set `DASHSCOPE_API_KEY` (Alibaba Cloud Model Studio, International region). Without a key, that baseline is recorded as **not run**. Its results are never simulated. To re-score saved LLM outputs without new API calls: `python -m scripts.run_day1 --reuse-llm`.

`run_day1` does the following: it generates synthetic data (seed 42), exports JSON Schemas, validates the 12 test cases, computes the pain model, runs both baselines, scores them, and writes `eval/results/baseline_comparison.md`.

## Repo map

| Path | What |
|---|---|
| `config/taxonomy.yaml` | Intents, P1–P4 definitions + tie-breaks, queues, escalation reasons (single source of truth) |
| `config/settings.yaml` | Seed, LLM provider/model (`qwen3.8-27b` via Alibaba Cloud), token prices, labour-cost assumptions |
| `config/pain_model.yaml` | Pain/cost model inputs (all assumed) |
| `src/llm_client.py` | Provider-agnostic LLM call (Alibaba Cloud OpenAI-compatible endpoint; Anthropic optional) |
| `app/` | Streamlit review UI ("Triage Desk"): inbox, triage card, Accept / Edit / Reject, activity |
| `src/pipeline/` | Day 2 triage pipeline: redact, injection, context, llm_extract, rules, run, handoff |
| `src/schemas.py` | Pydantic v2 contracts: `InboundTicket`, `TriageResult`, `TestCase` |
| `schemas/` | Exported JSON Schemas |
| `data/synthetic/` | 25 fictional customer accounts, 15 KB articles |
| `scripts/` | `run_day1`, `run_day2`, `triage` (v0 demo), `generate_synthetic`, `pain_model`, `compare_models` |
| `baselines/` | `keyword_baseline` (rules, no LLM), `naive_llm_baseline` (one free-text prompt) |
| `eval/` | `test_cases.jsonl` (12 dev), `test_cases_holdout.jsonl` (12 held-out), `rubric.md`, `metrics.py`, `results/`, manual timing template |
| `tests/` | Schema, taxonomy-consistency, metrics and baseline tests |
| `docs/day1/` | Day 1 deliverables 00–07 |
| `docs/day2/` | Day 2 summary, system design, v0 demo transcript |
| `docs/assumptions.md`, `docs/decisions.md` | Assumptions log, ADRs |
