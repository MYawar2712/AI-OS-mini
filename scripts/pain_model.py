"""Compute the triage cost model (low/base/high) from config/pain_model.yaml + settings.yaml.

    python -m scripts.pain_model

Output is an ESTIMATE built from assumptions, not a measurement. Writes eval/results/pain_model.md.
"""
from __future__ import annotations

import sys

import yaml

from src.taxonomy import ROOT, load_settings

SCEN = ("low", "base", "high")


def compute() -> dict[str, dict[str, float]]:
    p = yaml.safe_load((ROOT / "config" / "pain_model.yaml").read_text(encoding="utf-8"))
    s = load_settings()
    rate = s["labour_cost_gbp_per_hour"]
    llm = s["pricing_usd_per_mtok"].get(s["llm"]["model"]) or {}
    if llm.get("input") is None or llm.get("output") is None:
        llm_per_ticket = None  # price not confirmed yet -> reported as n/a
    else:
        llm_per_ticket = (p["llm_tokens_per_ticket"]["input"] * llm["input"] + p["llm_tokens_per_ticket"]["output"] * llm["output"]) / 1e6
    out = {}
    for k in SCEN:
        tickets_wk = p["team_tier1_reps"] * p["tickets_per_rep_per_day"][k] * p["working_days_per_week"]
        triage_h = tickets_wk * p["triage_minutes_per_ticket"][k] / 60
        misroutes = tickets_wk * p["misroute_rate"][k]
        rework_h = misroutes * p["rework_minutes_per_misroute"][k] / 60
        out[k] = {
            "tickets_per_week": tickets_wk,
            "triage_hours_per_week": triage_h,
            "misroutes_per_week": misroutes,
            "rework_hours_per_week": rework_h,
            "total_hours_per_week": triage_h + rework_h,
            "fte_equivalent": (triage_h + rework_h) / 37.5,
            "labour_cost_gbp_per_week": (triage_h + rework_h) * rate[k],
            "labour_cost_gbp_per_year": (triage_h + rework_h) * rate[k] * 52,
            "priority_errors_per_week": tickets_wk * p["priority_error_rate"][k],
            "customer_wait_hours_added_per_week": misroutes * p["ttfr_delay_hours_per_misroute"][k],
            "projected_llm_cost_usd_per_week": None if llm_per_ticket is None else tickets_wk * llm_per_ticket,
        }
    return out


def to_markdown(r: dict) -> str:
    fmt = {"tickets_per_week": "{:.0f}", "triage_hours_per_week": "{:.1f}", "misroutes_per_week": "{:.0f}",
           "rework_hours_per_week": "{:.1f}", "total_hours_per_week": "{:.1f}", "fte_equivalent": "{:.2f}",
           "labour_cost_gbp_per_week": "£{:,.0f}", "labour_cost_gbp_per_year": "£{:,.0f}",
           "priority_errors_per_week": "{:.0f}", "customer_wait_hours_added_per_week": "{:.0f}",
           "projected_llm_cost_usd_per_week": "${:.2f}"}
    lines = ["| Metric (ESTIMATE) | Low | Base | High |", "|---|---|---|---|"]
    for k, f in fmt.items():
        lines.append(f"| {k} | " + " | ".join("n/a" if r[s][k] is None else f.format(r[s][k]) for s in SCEN) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    md = "# Triage pain model (ESTIMATE — all inputs assumed, see config/pain_model.yaml)\n\n" + to_markdown(compute())
    out = ROOT / "eval" / "results" / "pain_model.md"
    out.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
