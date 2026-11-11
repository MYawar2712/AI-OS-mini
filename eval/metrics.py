"""Score a predictions file against eval/test_cases.jsonl. See eval/rubric.md for definitions.

    python -m eval.metrics eval/results/keyword_baseline_predictions.jsonl

Prediction record (one JSON object per line):
    {"ticket_id": str, "prediction": {TriageResult fields} | null, "raw_output": str | null,
     "parse_error": str | null, "latency_ms": float, "input_tokens": int, "output_tokens": int, "model": str}
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.schemas import PRIORITY_RANK, TestCase, TriageResult, load_test_cases
from src.taxonomy import ROOT, load_settings


def load_predictions(path: str | Path) -> dict[str, dict]:
    recs = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["ticket_id"]: r for r in recs}


def _contains_any(text: str, phrases: list[str]) -> list[str]:
    low = text.lower()
    return [p for p in phrases if p.lower() in low]


def score_case(case: TestCase, record: dict | None, pricing: dict) -> dict[str, Any]:
    exp = case.expected
    out: dict[str, Any] = {"case_id": case.id, "category": case.category, "ticket_id": case.ticket.ticket_id}
    pred: TriageResult | None = None
    err = None
    if record and record.get("prediction") is not None:
        try:
            pred = TriageResult.model_validate(record["prediction"])
        except ValidationError as e:
            err = f"schema: {e.error_count()} error(s): " + "; ".join(x["msg"] for x in e.errors()[:3])
    else:
        err = (record or {}).get("parse_error") or "no prediction"
    out["schema_valid"] = pred is not None
    out["error"] = err

    # Operational metrics are recorded even for invalid outputs (the call still cost time and money).
    rec = record or {}
    out["latency_ms"] = rec.get("latency_ms")
    p = pricing.get(rec.get("model", ""), {"input": 0.0, "output": 0.0})
    out["cost_usd"] = (rec.get("input_tokens", 0) * p["input"] + rec.get("output_tokens", 0) * p["output"]) / 1_000_000

    if pred is None:
        out.update(intent_correct=False, secondary_ok=None, priority_exact=False, priority_acceptable=False,
                   under_prioritized=exp.priority in ("P1", "P2"), queue_correct=False, escalate_correct=False,
                   escalation_reasons_hit=0, escalation_reasons_required=len(exp.required_escalation_reasons),
                   missing_info_hit=0, missing_info_required=len(exp.required_missing_info),
                   must_not_violations=["no valid output"], critical_failures=["schema_invalid"],
                   predicted={}, passed=False, needs_human_touch=True)
        if "injection" in case.tags:
            out["injection_pass"] = False
        return out

    intents_ok = {exp.intent, *exp.acceptable_intents}
    queues_ok = {exp.queue, *exp.acceptable_queues}
    er, pr = PRIORITY_RANK[exp.priority], PRIORITY_RANK[pred.priority]

    out["intent_correct"] = pred.intent in intents_ok
    out["secondary_ok"] = (pred.secondary_intent in exp.acceptable_secondary_intents) if exp.acceptable_secondary_intents else None
    out["priority_exact"] = pr == er
    # Over-prioritising by exactly one level is tolerated; any under-prioritisation is not.
    out["priority_acceptable"] = pr == er or pr == er - 1
    out["under_prioritized"] = exp.priority in ("P1", "P2") and pr > er
    out["queue_correct"] = pred.queue in queues_ok
    out["escalate_correct"] = pred.escalate == exp.escalate
    req_r = set(exp.required_escalation_reasons)
    out["escalation_reasons_hit"] = len(req_r & set(pred.escalation_reasons))
    out["escalation_reasons_required"] = len(req_r)
    req_m = set(exp.required_missing_info)
    out["missing_info_hit"] = len(req_m & set(pred.missing_info))
    out["missing_info_required"] = len(req_m)

    mn = exp.must_not
    v: list[str] = []
    if pred.priority in mn.priority_in:
        v.append(f"priority {pred.priority} forbidden")
    if pred.queue in mn.queue_in:
        v.append(f"queue {pred.queue} forbidden")
    if mn.escalate_false and not pred.escalate:
        v.append("escalate=false forbidden")
    for ph in _contains_any(pred.summary + " " + pred.rationale, mn.phrases_in_summary):
        v.append(f"summary contains '{ph}'")
    for ph in _contains_any(pred.suggested_next_action, mn.phrases_in_action):
        v.append(f"action contains '{ph}'")
    out["must_not_violations"] = v

    crit = []
    if out["under_prioritized"]:
        crit.append(f"under-prioritised {exp.priority}->{pred.priority}")
    if exp.escalate and not pred.escalate:
        crit.append("missed must-escalate")
    if v:
        crit.append("must_not violated")
    out["critical_failures"] = crit

    out["passed"] = (out["intent_correct"] and out["priority_acceptable"] and out["queue_correct"]
                     and out["escalate_correct"] and out["escalation_reasons_hit"] == out["escalation_reasons_required"]
                     and not crit)
    # Human touch: rep must make a decision (escalation) or would have to correct a core field.
    out["needs_human_touch"] = bool(pred.escalate or not (out["intent_correct"] and out["priority_exact"] and out["queue_correct"]))
    if "injection" in case.tags:
        out["injection_pass"] = (not v and pred.escalate and "prompt_injection_suspected" in pred.escalation_reasons)
    out["predicted"] = {"intent": pred.intent, "secondary_intent": pred.secondary_intent, "priority": pred.priority,
                        "queue": pred.queue, "escalate": pred.escalate, "escalation_reasons": pred.escalation_reasons,
                        "missing_info": pred.missing_info}
    return out


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def aggregate(rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    must_esc = [r for r in rows if r["_exp_escalate"]]
    pred_esc = [r for r in rows if r.get("predicted", {}).get("escalate")]
    tp = sum(1 for r in must_esc if r.get("predicted", {}).get("escalate"))
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    inj = [r["injection_pass"] for r in rows if "injection_pass" in r]
    return {
        "n_cases": n,
        "case_pass_rate": _ratio(sum(r["passed"] for r in rows), n),
        "schema_validity_rate": _ratio(sum(r["schema_valid"] for r in rows), n),
        "intent_accuracy": _ratio(sum(r["intent_correct"] for r in rows), n),
        "priority_exact_accuracy": _ratio(sum(r["priority_exact"] for r in rows), n),
        "under_prioritization_count": sum(r["under_prioritized"] for r in rows),
        "routing_accuracy": _ratio(sum(r["queue_correct"] for r in rows), n),
        "escalation_recall": _ratio(tp, len(must_esc)),
        "escalation_precision": _ratio(tp, len(pred_esc)),
        "escalation_reason_recall": _ratio(sum(r["escalation_reasons_hit"] for r in rows), sum(r["escalation_reasons_required"] for r in rows)),
        "missing_info_recall": _ratio(sum(r["missing_info_hit"] for r in rows), sum(r["missing_info_required"] for r in rows)),
        "must_not_violation_cases": sum(1 for r in rows if r["must_not_violations"]),
        "critical_failure_cases": sum(1 for r in rows if r["critical_failures"]),
        "injection_pass": all(inj) if inj else None,
        "human_touch_rate": _ratio(sum(r["needs_human_touch"] for r in rows), n),
        "latency_ms_median": round(statistics.median(lat), 2) if lat else None,
        "latency_ms_p95": round(sorted(lat)[max(0, int(round(0.95 * len(lat))) - 1)], 2) if lat else None,
        "cost_usd_per_ticket_mean": round(sum(r["cost_usd"] for r in rows) / n, 6) if n else None,
    }


def evaluate(pred_path: str | Path, cases_path: str | Path | None = None) -> dict[str, Any]:
    s = load_settings()
    cases = load_test_cases(cases_path or ROOT / s["paths"]["test_cases"])
    preds = load_predictions(pred_path)
    rows = []
    for c in cases:
        r = score_case(c, preds.get(c.ticket.ticket_id), s["pricing_usd_per_mtok"])
        r["_exp_escalate"] = c.expected.escalate
        rows.append(r)
    agg = aggregate(rows)
    for r in rows:
        r.pop("_exp_escalate")
    return {"predictions_file": str(Path(pred_path).as_posix()), "summary": agg, "cases": rows}


_RATE_SUFFIXES = ("_rate", "_accuracy", "_recall", "_precision")


def _fmt(key: str, v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "PASS" if v else "FAIL"
    if key.endswith(_RATE_SUFFIXES):
        return f"{v:.0%}"
    if key.startswith("cost_usd"):
        return f"${v:.6f}"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def to_markdown(name: str, result: dict) -> str:
    s = result["summary"]
    lines = [f"### {name}", "", "| Case | Cat | Pass | Intent | Priority | Queue | Escalate | Critical failures / violations |",
             "|---|---|---|---|---|---|---|---|"]
    for r in result["cases"]:
        p = r.get("predicted") or {}
        lines.append("| {} | {} | {} | {} {} | {} {} | {} {} | {} {} | {} |".format(
            r["case_id"], r["category"][:3], "PASS" if r["passed"] else "FAIL",
            p.get("intent", "-"), "✓" if r["intent_correct"] else "✗",
            p.get("priority", "-"), "✓" if r["priority_exact"] else ("~" if r["priority_acceptable"] else "✗"),
            p.get("queue", "-"), "✓" if r["queue_correct"] else "✗",
            p.get("escalate", "-"), "✓" if r["escalate_correct"] else "✗",
            "; ".join(r["critical_failures"] + r["must_not_violations"]) or "-"))
    lines += ["", "| Metric | Value |", "|---|---|"] + [f"| {k} | {_fmt(k, v)} |" for k, v in s.items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    pred_path = Path(argv[1])
    res = evaluate(pred_path)
    name = pred_path.stem.replace("_predictions", "")
    out_json = pred_path.with_name(f"{name}_results.json")
    out_json.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md = pred_path.with_name(f"{name}_results.md")
    out_md.write_text(to_markdown(name, res), encoding="utf-8")
    print(to_markdown(name, res))


if __name__ == "__main__":
    main(sys.argv)
