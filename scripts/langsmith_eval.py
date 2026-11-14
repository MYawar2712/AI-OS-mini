"""Upload the test sets to LangSmith as datasets and run the pipeline as a LangSmith experiment.

    python -m scripts.langsmith_eval --sets dev,adversarial --label v1

Needs LANGSMITH_API_KEY in .env. Privacy: only REDACTED ticket text is uploaded; the pipeline looks the full
(synthetic) ticket up locally by case ID. The held-out set needs --confirm-holdout (ADR-021).
Each experiment scores every case with the same scorer as scripts/run_eval (eval/metrics.py).
"""
from __future__ import annotations

import argparse
import sys

from eval.metrics import score_case
from scripts.run_eval import SETS
from src.observability import tracing_enabled
from src.pipeline.redact import redact
from src.pipeline.run import PIPELINE_VERSION, triage
from src.schemas import load_test_cases
from src.taxonomy import load_settings

FEEDBACK = ["passed", "intent_correct", "priority_exact", "queue_correct", "escalate_correct"]


def sync_dataset(client, name: str, cases) -> str:
    ds_name = f"triage-{name}"
    if client.has_dataset(dataset_name=ds_name):
        ds = client.read_dataset(dataset_name=ds_name)
        have = {e.inputs["case_id"] for e in client.list_examples(dataset_id=ds.id)}
    else:
        ds = client.create_dataset(ds_name, description=f"SYNTHETIC help desk triage test cases ({name} set). "
                                                        "Ticket text is redacted. Source: eval/ in the repo.")
        have = set()
    new = [c for c in cases if c.id not in have]
    if new:
        client.create_examples(dataset_id=ds.id, examples=[{
            "inputs": {"case_id": c.id, "ticket_id": c.ticket.ticket_id, "channel": c.ticket.channel,
                       "subject": redact(c.ticket.subject).text, "body": redact(c.ticket.body).text},
            "outputs": c.expected.model_dump(mode="json"),
            "metadata": {"category": c.category, "title": c.title, "tags": c.tags}} for c in new])
    print(f"dataset {ds_name}: {len(have)} existing, {len(new)} added")
    return ds_name


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="dev,adversarial")
    ap.add_argument("--label", default="v1")
    ap.add_argument("--confirm-holdout", action="store_true")
    ap.add_argument("--upload-only", action="store_true")
    a = ap.parse_args(argv)
    if not tracing_enabled():
        print("LangSmith is not configured. Add LANGSMITH_API_KEY to .env (and pip install langsmith).")
        return 2
    names = [s.strip() for s in a.sets.split(",")]
    if "holdout" in names and not a.confirm_holdout:
        print("Refusing to run the held-out set without --confirm-holdout (ADR-021).")
        return 2

    from langsmith import Client
    client = Client()
    pricing = load_settings()["pricing_usd_per_mtok"]
    for name in names:
        cases = {c.id: c for c in load_test_cases(SETS[name])}
        ds_name = sync_dataset(client, name, list(cases.values()))
        if a.upload_only:
            continue

        def target(inputs: dict) -> dict:
            result, trace = triage(cases[inputs["case_id"]].ticket, tags=["langsmith-eval", name, a.label])
            return {"prediction": result.model_dump(), "status": trace.status, "rules_fired": trace.rules_fired,
                    "latency_ms": trace.total_ms, "input_tokens": trace.input_tokens, "output_tokens": trace.output_tokens}

        def scorer(run, example) -> dict:
            out = run.outputs or {}
            row = score_case(cases[example.inputs["case_id"]],
                             {"prediction": out.get("prediction"), "parse_error": None, "latency_ms": out.get("latency_ms"),
                              "input_tokens": out.get("input_tokens", 0), "output_tokens": out.get("output_tokens", 0),
                              "model": load_settings()["llm"]["model"]}, pricing)
            res = [{"key": k, "score": int(bool(row[k]))} for k in FEEDBACK]
            res.append({"key": "critical_failure", "score": int(bool(row["critical_failures"])),
                        "comment": ", ".join(row["critical_failures"])})
            return {"results": res}

        exp = client.evaluate(target, data=ds_name, evaluators=[scorer], experiment_prefix=f"{a.label}-{name}",
                              max_concurrency=4, metadata={"pipeline_version": PIPELINE_VERSION, "set": name})
        print(f"experiment {exp.experiment_name} finished for {ds_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
