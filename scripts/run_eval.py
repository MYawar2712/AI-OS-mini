"""Day 4 evaluation: run the pipeline on one or more test sets, several times, and report quality + variance.

    python -m scripts.run_eval --label v0.3 --sets dev,adversarial --runs 3
    python -m scripts.run_eval --label v1 --sets holdout --runs 1 --confirm-holdout   # logged checkpoint only
    python -m scripts.run_eval --label v1 --sets adversarial --baselines              # also keyword + naive LLM

Held-out discipline (ADR-021): the held-out set needs --confirm-holdout and every run is appended to
eval/results/day4/holdout_checkpoints.jsonl. Failures there are never used for tuning.
Outputs: eval/results/day4/<label>/  (predictions per run, results per run, summary_<set>.json, report.md)
When LangSmith tracing is on, every run is traced with tags eval / <set> / <label>.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from baselines import keyword_baseline, naive_llm_baseline
from eval.metrics import evaluate
from scripts.run_day2 import KEYS, _fmt
from src.llm_client import LLMCallError, call_llm
from src.observability import flush_traces
from src.pipeline.run import PIPELINE_VERSION, triage
from src.schemas import load_test_cases
from src.taxonomy import ROOT, load_settings, load_taxonomy

BASE = ROOT / "eval" / "results" / "day4"
SETS = {"dev": ROOT / "eval" / "test_cases.jsonl", "holdout": ROOT / "eval" / "test_cases_holdout.jsonl",
        "adversarial": ROOT / "eval" / "test_cases_adversarial.jsonl"}
NUMERIC = [k for _, k, kind in KEYS if kind in ("pct", "int", "sec")]


def _write(path, records) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def run_pipeline(cases, tags: list[str], workers: int) -> list[dict]:
    def one(c):
        result, trace = triage(c.ticket, tags=tags)
        return {"ticket_id": c.ticket.ticket_id, "prediction": result.model_dump(), "raw_output": None,
                "parse_error": None, "latency_ms": trace.total_ms, "input_tokens": trace.input_tokens,
                "output_tokens": trace.output_tokens, "model": trace.model, "trace": trace.model_dump(mode="json")}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, cases))


def run_keyword(cases) -> list[dict]:
    out = []
    for c in cases:
        t0 = time.perf_counter()
        r = keyword_baseline.classify(c.ticket)
        out.append({"ticket_id": c.ticket.ticket_id, "prediction": r.model_dump(), "raw_output": None, "parse_error": None,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 3), "input_tokens": 0, "output_tokens": 0,
                    "model": "keyword_rules"})
    return out


def run_naive(cases) -> list[dict]:
    tax, model, out = load_taxonomy(), load_settings()["llm"]["model"], []
    for c in cases:
        t = c.ticket
        prompt = naive_llm_baseline.PROMPT.format(intents=", ".join(tax["intents"]), queues=", ".join(tax["queues"]),
                                                  subject=t.subject, body=t.body)
        rec = {"ticket_id": t.ticket_id, "model": model, "input_tokens": 0, "output_tokens": 0, "prediction": None,
               "raw_output": None, "parse_error": None, "latency_ms": None}
        try:
            r = call_llm(prompt)
            rec.update(raw_output=r.text, latency_ms=r.latency_ms, input_tokens=r.input_tokens, output_tokens=r.output_tokens)
            pred, err = naive_llm_baseline.parse_free_text(t, r.text)
            rec.update(prediction=pred, parse_error=err)
        except LLMCallError as e:
            rec["parse_error"] = f"api: {e}"[:300]
        out.append(rec)
    return out


def _why(row: dict) -> str:
    """Plain reason a case failed, from the scorer's per-case flags."""
    p = row.get("predicted") or {}
    bits = []
    if not row["schema_valid"]:
        bits.append(f"invalid output ({row.get('error')})")
    if row["critical_failures"]:
        bits.append("CRITICAL: " + ", ".join(row["critical_failures"]))
    if row["must_not_violations"]:
        bits.append("must-not: " + ", ".join(map(str, row["must_not_violations"])))
    if not row["intent_correct"]:
        bits.append(f"intent={p.get('intent')}")
    if not row["priority_acceptable"]:
        bits.append(f"priority={p.get('priority')}" + (" (under)" if row["under_prioritized"] else ""))
    if not row["queue_correct"]:
        bits.append(f"queue={p.get('queue')}")
    if not row["escalate_correct"]:
        bits.append(f"escalate={p.get('escalate')}")
    if row["escalation_reasons_hit"] < row["escalation_reasons_required"]:
        bits.append(f"reasons={p.get('escalation_reasons')}")
    if row["missing_info_hit"] < row["missing_info_required"]:
        bits.append(f"missing_info={p.get('missing_info')}")
    return "; ".join(bits)[:300].replace("|", "/") or "see results file"


def _agg(summaries: list[dict]) -> dict:
    out = {}
    for k in NUMERIC:
        vals = [s[k] for s in summaries if s.get(k) is not None]
        out[k] = {"mean": statistics.mean(vals), "min": min(vals), "max": max(vals)} if vals else None
    return out


def _cell(a: dict | None, kind: str) -> str:
    if a is None:
        return "n/a"
    if a["min"] == a["max"]:
        return _fmt(a["mean"], kind)
    return f"{_fmt(a['mean'], kind)} ({_fmt(a['min'], kind)}–{_fmt(a['max'], kind)})"


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--sets", default="dev")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--baselines", action="store_true", help="also run keyword + naive LLM baselines (1 run)")
    ap.add_argument("--confirm-holdout", action="store_true")
    a = ap.parse_args(argv)
    names = [s.strip() for s in a.sets.split(",")]
    if "holdout" in names and not a.confirm_holdout:
        print("Refusing to run the held-out set without --confirm-holdout (ADR-021: checkpoints only, never for tuning).")
        return 2
    out = BASE / a.label
    out.mkdir(parents=True, exist_ok=True)
    report = [f"# Evaluation `{a.label}`: pipeline {PIPELINE_VERSION}, model `{load_settings()['llm']['model']}`", "",
              f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m scripts.run_eval`. "
              "All cases are SYNTHETIC. Ranges are min–max over the runs._", ""]

    for name in names:
        cases = load_test_cases(SETS[name])
        summaries, passes = [], {c.id: 0 for c in cases}
        failures: dict[str, list[str]] = {c.id: [] for c in cases}
        for k in range(1, a.runs + 1):
            print(f"== {name} run {k}/{a.runs}")
            pred = out / f"pipeline_{name}_run{k}_predictions.jsonl"
            _write(pred, run_pipeline(cases, ["eval", name, a.label], a.workers))
            res = evaluate(pred, SETS[name])
            (out / f"pipeline_{name}_run{k}_results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n",
                                                                     encoding="utf-8")
            summaries.append(res["summary"])
            for row in res["cases"]:
                passes[row["case_id"]] += bool(row["passed"])
                if not row["passed"]:
                    failures[row["case_id"]].append(_why(row))
            s = res["summary"]
            print(f"   pass {s['case_pass_rate']:.0%}  critical {s['critical_failure_cases']}  "
                  f"esc recall {s['escalation_recall']}  median {s['latency_ms_median'] / 1000:.1f}s")
        agg = _agg(summaries)
        systems = {"pipeline": agg}
        if a.baselines:
            for sysname, fn in (("keyword_baseline", run_keyword), ("naive_llm_baseline", run_naive)):
                print(f"== {name} {sysname}")
                p = out / f"{sysname}_{name}_predictions.jsonl"
                _write(p, fn(cases))
                res = evaluate(p, SETS[name])
                (out / f"{sysname}_{name}_results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n",
                                                                    encoding="utf-8")
                systems[sysname] = _agg([res["summary"]])
        (out / f"summary_{name}.json").write_text(json.dumps(
            {"label": a.label, "set": name, "runs": a.runs, "pipeline_version": PIPELINE_VERSION,
             "systems": systems, "case_passes": passes, "case_failures": failures}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        if name == "holdout":
            with (BASE / "holdout_checkpoints.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "label": a.label, "runs": a.runs,
                                     "pipeline_version": PIPELINE_VERSION,
                                     "case_pass_rate": agg["case_pass_rate"], "case_passes": passes}) + "\n")

        cols = list(systems)
        report += [f"## {name} set ({len(cases)} cases, pipeline × {a.runs} run(s))", "",
                   "| Metric | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for label, key, kind in KEYS:
            if key in NUMERIC:
                report.append(f"| {label} | " + " | ".join(_cell(systems[s][key], kind) for s in cols) + " |")
        report += ["", "| Case | Title | Passed (runs) | Why it failed (first failing run) |", "|---|---|---|---|"]
        for c in cases:
            why = failures[c.id][0] if failures[c.id] else ""
            report.append(f"| {c.id} | {c.title} | {passes[c.id]}/{a.runs} | {why} |")
        report.append("")

    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    flush_traces()
    print(f"\nReport: {(out / 'report.md').relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
