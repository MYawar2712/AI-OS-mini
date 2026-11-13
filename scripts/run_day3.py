"""Day 3 latency check (task 3.7): run the pipeline on the DEV set only, score it, and report latency.

    python -m scripts.run_day3 --label before      # current prompt
    python -m scripts.run_day3 --label after       # after a change; compare the two summaries

Never runs the held-out set (ADR-021): latency tuning is done on dev only.
Outputs: eval/results/day3/pipeline_dev_<label>_predictions.jsonl, ..._results.json, latency_<label>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys

from eval.metrics import evaluate
from src.pipeline.run import PIPELINE_VERSION, triage
from src.schemas import load_test_cases
from src.taxonomy import ROOT, load_settings

OUT = ROOT / "eval" / "results" / "day3"
DEV = ROOT / "eval" / "test_cases.jsonl"


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p * (len(xs) - 1)))]


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    recs, llm_ms = [], []
    for c in load_test_cases(DEV):
        result, trace = triage(c.ticket)
        step = next((s.ms for s in trace.steps if s.step == "llm_extract"), None)
        llm_ms.append(step)
        recs.append({"ticket_id": c.ticket.ticket_id, "prediction": result.model_dump(), "raw_output": None,
                     "parse_error": None, "latency_ms": trace.total_ms, "input_tokens": trace.input_tokens,
                     "output_tokens": trace.output_tokens, "model": trace.model, "trace": trace.model_dump(mode="json")})
        print(f"  {c.id:5} {trace.status:8} {trace.total_ms / 1000:5.1f}s  out={trace.output_tokens:4}  "
              f"{result.intent:24} {result.priority} esc={result.escalate}")
    pred = OUT / f"pipeline_dev_{args.label}_predictions.jsonl"
    pred.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    res = evaluate(pred, DEV)
    (OUT / f"pipeline_dev_{args.label}_results.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")

    total = [r["latency_ms"] for r in recs]
    s = res["summary"]
    summary = {"label": args.label, "pipeline_version": PIPELINE_VERSION, "model": load_settings()["llm"]["model"],
               "cases": len(recs), "case_pass_rate": s["case_pass_rate"], "critical_failure_cases": s["critical_failure_cases"],
               "escalation_recall": s["escalation_recall"], "priority_exact_accuracy": s["priority_exact_accuracy"],
               "latency_ms_median": statistics.median(total), "latency_ms_p95": _pct(total, 0.95),
               "llm_ms_median": statistics.median(llm_ms),
               "output_tokens_mean": statistics.mean(r["output_tokens"] for r in recs),
               "input_tokens_mean": statistics.mean(r["input_tokens"] for r in recs)}
    (OUT / f"latency_{args.label}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
