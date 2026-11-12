"""Score the Day 2 pipeline against both baselines.

    python -m scripts.run_day2                  # dev set (12 cases): pipeline + compare with saved Day 1 baselines
    python -m scripts.run_day2 --holdout        # ALSO run everything on the 12 held-out cases (checkpoint only)
    python -m scripts.run_day2 --reuse          # re-score saved pipeline predictions, no API calls

Held-out discipline: prompt/rule changes are made by looking at DEV failures only. The held-out set is run at
checkpoints and its failures are not used for tuning (docs/day2/00_day2_summary.md records each checkpoint).
Outputs: eval/results/day2/
"""
from __future__ import annotations

import json
import sys
import time

from baselines import keyword_baseline, naive_llm_baseline
from eval.metrics import evaluate, to_markdown
from src.llm_client import LLMCallError, call_llm
from src.pipeline.run import PIPELINE_VERSION, triage
from src.schemas import load_test_cases
from src.taxonomy import ROOT, load_settings

OUT = ROOT / "eval" / "results" / "day2"
SETS = {"dev": ROOT / "eval" / "test_cases.jsonl", "holdout": ROOT / "eval" / "test_cases_holdout.jsonl"}
KEYS = [("Case pass rate", "case_pass_rate", "pct"), ("Critical-failure cases", "critical_failure_cases", "int"),
        ("Escalation recall (safety)", "escalation_recall", "pct"), ("Escalation precision", "escalation_precision", "pct"),
        ("Under-prioritised P1/P2", "under_prioritization_count", "int"), ("Injection case(s)", "injection_pass", "bool"),
        ("Must-not violation cases", "must_not_violation_cases", "int"), ("Schema-valid outputs", "schema_validity_rate", "pct"),
        ("Intent accuracy", "intent_accuracy", "pct"), ("Priority exact accuracy", "priority_exact_accuracy", "pct"),
        ("Routing accuracy", "routing_accuracy", "pct"), ("Escalation-reason recall", "escalation_reason_recall", "pct"),
        ("Missing-info recall", "missing_info_recall", "pct"), ("Human-touch rate", "human_touch_rate", "pct"),
        ("Median latency", "latency_ms_median", "sec"), ("p95 latency", "latency_ms_p95", "sec"),
        ("Tokens per ticket (in / out)", "tokens_per_ticket_mean", "tok"), ("Cost per ticket", "cost_usd_per_ticket_mean", "usd")]


def _fmt(v, kind):
    if v is None:
        return "TBC" if kind == "usd" else "n/a"
    return {"pct": lambda: f"{v:.0%}", "int": lambda: str(v), "bool": lambda: "PASS" if v else "FAIL",
            "sec": lambda: f"{v / 1000:.1f} s" if v >= 100 else "< 0.1 s", "tok": lambda: f"{v['input']:.0f} / {v['output']:.0f}",
            "usd": lambda: f"${v:.6f}"}[kind]()


def _write(path, records):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def run_pipeline(name: str) -> None:
    recs = []
    for c in load_test_cases(SETS[name]):
        result, trace = triage(c.ticket)
        recs.append({"ticket_id": c.ticket.ticket_id, "prediction": result.model_dump(), "raw_output": None,
                     "parse_error": None, "latency_ms": trace.total_ms, "input_tokens": trace.input_tokens,
                     "output_tokens": trace.output_tokens, "model": trace.model, "trace": trace.model_dump(mode="json")})
        print(f"  {c.id} {trace.status:8} {trace.total_ms / 1000:5.1f}s  {result.intent:24} {result.priority} "
              f"{result.queue:27} esc={result.escalate} {','.join(result.escalation_reasons)}")
    _write(OUT / f"triage_pipeline_{name}_predictions.jsonl", recs)


def run_baselines_on(name: str) -> None:
    """Keyword (free) and naive LLM baselines on a set that has no saved predictions yet (the held-out set)."""
    cases = load_test_cases(SETS[name])
    kw = []
    for c in cases:
        t0 = time.perf_counter()
        r = keyword_baseline.classify(c.ticket)
        kw.append({"ticket_id": c.ticket.ticket_id, "prediction": r.model_dump(), "raw_output": None, "parse_error": None,
                   "latency_ms": round((time.perf_counter() - t0) * 1000, 3), "input_tokens": 0, "output_tokens": 0,
                   "model": "keyword_rules"})
    _write(OUT / f"keyword_baseline_{name}_predictions.jsonl", kw)
    from src.taxonomy import load_taxonomy
    tax = load_taxonomy()
    nv = []
    for c in cases:
        t = c.ticket
        prompt = naive_llm_baseline.PROMPT.format(intents=", ".join(tax["intents"]), queues=", ".join(tax["queues"]),
                                                  subject=t.subject, body=t.body)
        rec = {"ticket_id": t.ticket_id, "model": load_settings()["llm"]["model"], "input_tokens": 0, "output_tokens": 0}
        try:
            r = call_llm(prompt)
            pred, err = naive_llm_baseline.parse_free_text(t, r.text)
            rec.update(prediction=pred, parse_error=err, raw_output=r.text, latency_ms=r.latency_ms,
                       input_tokens=r.input_tokens, output_tokens=r.output_tokens)
        except LLMCallError as e:
            rec.update(prediction=None, parse_error=str(e), raw_output=None, latency_ms=None)
        nv.append(rec)
        print(f"  naive {c.id} done")
    _write(OUT / f"naive_llm_baseline_{name}_predictions.jsonl", nv)


def score(name: str) -> dict:
    systems = {}
    sources = {
        "dev": {"keyword_baseline": ROOT / "eval/results/keyword_baseline_predictions.jsonl",
                "naive_llm_baseline": ROOT / "eval/results/naive_llm_baseline_predictions.jsonl"},
        "holdout": {"keyword_baseline": OUT / "keyword_baseline_holdout_predictions.jsonl",
                    "naive_llm_baseline": OUT / "naive_llm_baseline_holdout_predictions.jsonl"},
    }[name]
    sources["triage_pipeline"] = OUT / f"triage_pipeline_{name}_predictions.jsonl"
    md_parts = []
    for sysname, p in sources.items():
        if not p.exists():
            continue
        res = evaluate(p, SETS[name])
        (OUT / f"{sysname}_{name}_results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        systems[sysname] = res["summary"]
        md_parts.append(to_markdown(f"{sysname} ({name})", res))
    cols = list(systems)
    lines = [f"# Day 2 comparison: {name} set ({len(load_test_cases(SETS[name]))} SYNTHETIC cases)", "",
             f"_Pipeline {PIPELINE_VERSION}, model `{load_settings()['llm']['model']}`, reasoning "
             f"{'on' if load_settings()['pipeline']['thinking'] else 'off'}. Generated by `python -m scripts.run_day2`._", "",
             "| Metric | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for label, key, kind in KEYS:
        lines.append(f"| {label} | " + " | ".join(_fmt(systems[s][key], kind) for s in cols) + " |")
    lines += ["", "## Per-case detail", ""] + md_parts
    (OUT / f"comparison_{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:len(KEYS) + 6]))
    return systems


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    names = ["dev", "holdout"] if "--holdout" in sys.argv else ["dev"]
    for name in names:
        if "--reuse" not in sys.argv:
            print(f"== pipeline on {name}")
            run_pipeline(name)
            if name == "holdout" and not (OUT / "naive_llm_baseline_holdout_predictions.jsonl").exists():
                print("== baselines on holdout (first time only)")
                run_baselines_on(name)
        print(f"== score {name}")
        score(name)


if __name__ == "__main__":
    main()
